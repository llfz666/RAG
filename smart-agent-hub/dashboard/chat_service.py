"""Chat Service - 完整版，使用 HybridSearch 直接搜索并保存对话历史.

这个版本直接调用 HybridSearch 执行知识库搜索，
然后使用 LLM 生成答案，并使用 MemorySystem 保存对话历史。
同时使用 TraceCollector 记录到主 RAG 项目的日志系统。
并保存到 SQLite 数据库以在 Dashboard 的 Session History 中显示。
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import json
from pathlib import Path
from typing import AsyncGenerator, Optional, List
from datetime import datetime

from .chat_models import ChatMessage, MessageType, ConnectionStatus, SessionState
from agent.core.memory import MemorySystem
from agent.storage.jsonl_logger import JSONLLogger

logger = logging.getLogger(__name__)

# 修复 Streamlit 中的事件循环问题 - 延迟应用到有事件循环时
_nest_asyncio_applied = False


def _ensure_event_loop():
    """确保当前线程有事件循环。"""
    try:
        loop = asyncio.get_event_loop()
        return loop
    except RuntimeError:
        # 没有事件循环，创建一个新的
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def _apply_nest_asyncio():
    """应用 nest_asyncio 补丁（仅在有事件循环时）。"""
    global _nest_asyncio_applied
    if _nest_asyncio_applied:
        return
    
    try:
        import nest_asyncio
        loop = _ensure_event_loop()
        nest_asyncio.apply(loop)
        _nest_asyncio_applied = True
        logger.debug("nest_asyncio applied successfully")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to apply nest_asyncio: {e}")


class ChatService:
    """聊天服务 - 完整版.
    
    该服务使用 HybridSearch 进行知识库搜索，然后使用 LLM 生成答案。
    """
    
    _instance: Optional["ChatService"] = None
    _initialized: bool = False
    _initializing: bool = False
    
    def __new__(cls) -> "ChatService":
        """单例模式实现."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_state()
        return cls._instance
    
    def _init_state(self) -> None:
        """初始化内部状态."""
        self._llm_client = None
        self._settings = None
        self._hybrid_search = None
        self._memory_system: Optional[MemorySystem] = None
        self._trace_logger: Optional[JSONLLogger] = None
        self._rag_trace_collector = None  # 主 RAG 项目的 TraceCollector
        self._config_path: Optional[str] = None
        self._db_path: str = "data/db/agent_sessions.db"
    
    def _calculate_importance(
        self,
        query: str,
        answer: str,
        search_results: list,
        sources: list,
    ) -> float:
        """动态计算记忆重要性.
        
        计算策略：
        1. 基础重要性：0.5
        2. 搜索结果越多越重要：+0.05 × 结果数 (最多 +0.2)
        3. 答案越长越重要：>300 字 +0.1, >500 字 +0.15
        4. 有来源信息更重要：+0.1
        5. 问题长度适中（非简单问题）：+0.05
        
        Args:
            query: 用户问题
            answer: Agent 回答
            search_results: 搜索结果列表
            sources: 来源列表
            
        Returns:
            重要性分数 (0.0-1.0)
        """
        # 基础重要性
        importance = 0.5
        
        # 1. 搜索结果数量加分（最多 +0.2）
        result_bonus = min(0.2, len(search_results) * 0.05)
        importance += result_bonus
        
        # 2. 答案长度加分
        answer_length = len(answer)
        if answer_length > 500:
            importance += 0.15
        elif answer_length > 300:
            importance += 0.1
        elif answer_length > 100:
            importance += 0.05
        
        # 3. 来源信息加分
        if sources and len(sources) > 0:
            importance += 0.1
        
        # 4. 问题复杂度加分（非简单问题）
        query_length = len(query)
        if query_length > 20:  # 较长的问题通常更复杂
            importance += 0.05
        
        # 限制在 0-1 范围内
        return min(1.0, max(0.0, importance))
    
    @property
    def is_initialized(self) -> bool:
        """检查服务是否已初始化."""
        return self._initialized
    
    @property
    def is_initializing(self) -> bool:
        """检查服务是否正在初始化."""
        return self._initializing
    
    async def initialize(self, config_path: Optional[str] = None) -> None:
        """初始化 Agent 组件.
        
        初始化 LLM 客户端和 HybridSearch。
        """
        if self._initialized:
            logger.debug("ChatService already initialized")
            return
        
        if self._initializing:
            logger.debug("ChatService is already initializing, waiting...")
            while self._initializing:
                await asyncio.sleep(0.1)
            return
        
        self._initializing = True
        self._config_path = config_path
        
        try:
            # 应用 nest_asyncio 补丁（在事件循环中）
            _apply_nest_asyncio()
            
            logger.info("Initializing ChatService...")
            
            # 延迟导入
            from agent.core.settings import load_settings
            from agent.llm.client import LLMClient
            
            # 加载配置
            self._settings = load_settings(config_path)
            logger.debug("Settings loaded")
            
            # 初始化 LLM Client
            llm_config = self._settings.llm
            self._llm_client = LLMClient.create(
                provider=llm_config.provider,
                settings=llm_config,
                api_key=llm_config.api_key,
            )
            logger.debug(f"LLM Client initialized with provider: {llm_config.provider}")
            
            # 初始化 Memory System
            try:
                storage_config = self._settings.storage
                self._trace_logger = JSONLLogger(
                    log_path=storage_config.log_path,
                )
                self._memory_system = MemorySystem(
                    short_term_max_turns=20,
                    long_term_storage_path=str(Path(storage_config.db_path).parent / "long_term_memory.jsonl"),
                    logger=self._trace_logger,
                )
                logger.debug("Memory System initialized")
            except Exception as e:
                logger.warning(f"Memory System initialization failed: {e}")
                self._memory_system = None
                self._trace_logger = None
            
            # 初始化主 RAG 项目的 TraceCollector
            try:
                # 添加主项目路径到 sys.path
                import sys
                parent_dir = Path(__file__).parent.parent.parent
                if str(parent_dir) not in sys.path:
                    sys.path.insert(0, str(parent_dir))
                
                from src.core.trace.trace_collector import TraceCollector
                from src.core.settings import resolve_path
                
                # 使用主 RAG 项目的 traces 路径
                traces_path = resolve_path("logs/traces.jsonl")
                self._rag_trace_collector = TraceCollector(traces_path=traces_path)
                logger.debug(f"RAG TraceCollector initialized: {traces_path}")
            except Exception as e:
                logger.warning(f"RAG TraceCollector initialization failed: {e}")
                self._rag_trace_collector = None
            
            # 初始化 HybridSearch
            try:
                import sys
                parent_dir = Path(__file__).parent.parent.parent
                if str(parent_dir) not in sys.path:
                    sys.path.insert(0, str(parent_dir))
                
                from src.core.query_engine.hybrid_search import create_hybrid_search
                from src.core.query_engine.query_processor import QueryProcessor
                from src.core.query_engine.dense_retriever import create_dense_retriever
                from src.core.query_engine.sparse_retriever import create_sparse_retriever
                from src.ingestion.storage.bm25_indexer import BM25Indexer
                from src.libs.embedding.embedding_factory import EmbeddingFactory
                from src.libs.vector_store.vector_store_factory import VectorStoreFactory
                
                # 创建嵌入客户端
                embedding_client = EmbeddingFactory.create(self._settings)
                
                # 创建向量存储
                vector_store = VectorStoreFactory.create(
                    self._settings,
                    collection_name="default",
                )
                
                # 创建密集检索器和稀疏检索器
                dense_retriever = create_dense_retriever(
                    settings=self._settings,
                    embedding_client=embedding_client,
                    vector_store=vector_store,
                )
                
                bm25_indexer = BM25Indexer(index_dir=str(Path("data/db/bm25/default")))
                sparse_retriever = create_sparse_retriever(
                    settings=self._settings,
                    bm25_indexer=bm25_indexer,
                    vector_store=vector_store,
                )
                sparse_retriever.default_collection = "default"
                
                # 创建查询处理器
                query_processor = QueryProcessor()
                
                # 创建 HybridSearch
                self._hybrid_search = create_hybrid_search(
                    settings=self._settings,
                    query_processor=query_processor,
                    dense_retriever=dense_retriever,
                    sparse_retriever=sparse_retriever,
                )
                
                logger.info("HybridSearch initialized")
                
            except Exception as e:
                logger.warning(f"HybridSearch initialization failed: {e}")
                self._hybrid_search = None
            
            self._initialized = True
            logger.info("ChatService initialized successfully")
            
        except Exception as e:
            logger.exception(f"Failed to initialize ChatService: {e}")
            self._initialized = False
            raise RuntimeError(f"初始化失败：{e}") from e
        
        finally:
            self._initializing = False
    
    async def shutdown(self) -> None:
        """关闭连接并清理资源."""
        logger.info("Shutting down ChatService...")
        
        self._llm_client = None
        self._hybrid_search = None
        self._initialized = False
        
        logger.info("ChatService shut down complete")
    
    async def process_query(
        self,
        query: str,
        session_id: str,
    ) -> AsyncGenerator[ChatMessage, None]:
        """处理用户查询，流式返回消息.
        
        流程：
        1. 使用 HybridSearch 搜索知识库
        2. 使用 LLM 综合信息给出答案
        """
        # 验证输入
        if not query or not query.strip():
            raise ValueError("查询不能为空")
        
        # 确保已初始化
        if not self._initialized:
            await self.initialize()
        
        logger.info(f"Processing query for session {session_id}: {query[:50]}...")
        
        try:
            # 1. 思考
            yield ChatMessage(
                role=MessageType.THOUGHT,
                content=f"分析用户问题：{query[:100]}",
                metadata={"session_id": session_id},
            )
            
            # 2. 搜索知识库
            search_results = None
            if self._hybrid_search and self._settings.chat.enable_rag:
                yield ChatMessage(
                    role=MessageType.ACTION,
                    content="调用工具：query_knowledge_hub",
                    metadata={"tool": "query_knowledge_hub", "input": {"query": query}},
                )

                try:
                    # 执行搜索
                    search_results = await asyncio.to_thread(
                        self._hybrid_search.search,
                        query=query,
                        top_k=5,
                        filters=None,
                        trace=None,
                        return_details=False,
                    )

                    # 处理搜索结果
                    result_count = len(search_results) if search_results else 0

                    # 严格 RAG 模式：如果搜索结果为空且不允许 fallback，直接返回
                    if not search_results and not self._settings.chat.fallback_to_llm:
                        yield ChatMessage(
                            role=MessageType.FINAL_ANSWER,
                            content=self._settings.chat.empty_search_message,
                            metadata={"session_id": session_id, "rag_only": True},
                        )
                        # 保存对话记录
                        await self._save_conversation(session_id, query, self._settings.chat.empty_search_message, [])
                        return

                    yield ChatMessage(
                        role=MessageType.OBSERVATION,
                        content=f"知识库返回 {result_count} 条结果",
                        metadata={"session_id": session_id, "result_count": result_count},
                    )
                except Exception as e:
                    logger.warning(f"Hybrid search failed: {e}")
                    search_results = None
                    if not self._settings.chat.fallback_to_llm:
                        yield ChatMessage(
                            role=MessageType.FINAL_ANSWER,
                            content="知识库搜索失败，且已禁用 LLM 回退。",
                            metadata={"session_id": session_id, "error": str(e)},
                        )
                        return
                    yield ChatMessage(
                        role=MessageType.OBSERVATION,
                        content="知识库搜索失败，将使用纯 LLM 回答",
                        metadata={"session_id": session_id, "error": str(e)},
                    )
            
            # 3. 使用 LLM 生成答案
            yield ChatMessage(
                role=MessageType.THOUGHT,
                content="正在生成答案...",
                metadata={"session_id": session_id},
            )
            
            # 构建提示词
            context = None
            if search_results:
                chunks = []
                for i, r in enumerate(search_results[:3]):
                    # 处理 RetrievalResult 对象
                    text = getattr(r, 'text', None) or getattr(r, 'content', None)
                    if text:
                        source = getattr(r, 'metadata', {})
                        if isinstance(source, dict):
                            source = source.get('source_path', source.get('source', ''))
                        chunks.append(f"[{i+1}] {text[:200]}... (来源：{source})")
                
                if chunks:
                    context = "\n\n".join(chunks)
            
            if context:
                prompt = f"""基于以下上下文回答问题：

上下文：
{context}

问题：{query}

请用中文详细回答。"""
            else:
                prompt = f"请用中文详细回答以下问题：{query}"
            
            # 调用 LLM
            from agent.llm.client import LLMMessage
            
            async def call_llm():
                try:
                    response = await self._llm_client.chat(
                        messages=[LLMMessage(role="user", content=prompt)],
                        max_tokens=2048,
                    )
                    return response.content
                except Exception as e:
                    # 详细的错误处理
                    error_msg = str(e)
                    error_type = type(e).__name__
                    logger.exception(f"LLM call failed: {error_type}: {error_msg}")
                    
                    if "timeout" in error_msg.lower() or "Timeout" in error_msg:
                        return "抱歉，LLM 服务响应超时。请检查：\n1. 网络连接是否正常\n2. API 密钥配置是否正确\n3. 配额是否充足"
                    elif "api_key" in error_msg.lower() or "401" in error_msg:
                        return "抱歉，API 密钥验证失败。请检查 config/settings.yaml 中的 API 密钥配置。"
                    elif "404" in error_msg:
                        return "抱歉，LLM 服务地址不存在。请检查 base_url 配置是否正确。"
                    elif "connection" in error_msg.lower():
                        return "抱歉，无法连接到 LLM 服务。请检查网络连接。"
                    else:
                        return f"抱歉，LLM 服务调用失败：{error_type}: {error_msg[:300]}"
            
            answer = await call_llm()
            
            # 确保答案不为空
            if not answer or not answer.strip():
                answer = "抱歉，LLM 返回了空答案。请尝试重新提问。"
            
            # 4. 返回最终答案
            final_answer_msg = ChatMessage(
                role=MessageType.FINAL_ANSWER,
                content=answer,
                metadata={"session_id": session_id},
            )
            yield final_answer_msg
            
            # 5. 保存对话到 Memory System
            await self._save_conversation(session_id, query, answer, search_results)
            
            # 6. 记录到主 RAG 项目的 TraceCollector
            if self._rag_trace_collector:
                self._record_to_rag_trace(query, search_results, session_id)
            
            # 7. 保存到 SQLite 数据库（用于 Dashboard Session History）
            self._save_to_sqlite(session_id, query, answer, search_results)
            
            logger.info(f"Query completed for session {session_id}")
            
        except Exception as e:
            logger.exception(f"Query failed: {e}")
            error_msg = ChatMessage(
                role=MessageType.ERROR,
                content=f"处理查询时出错：{str(e)}",
                metadata={"error_type": type(e).__name__},
            )
            yield error_msg
            
            # 保存错误信息
            if self._trace_logger:
                self._trace_logger.log({
                    "type": "query_error",
                    "session_id": session_id,
                    "query": query[:200],
                    "error": str(e),
                })
    
    async def simple_query(self, query: str) -> str:
        """简单查询接口（返回最终答案）."""
        final_answer = ""
        async for msg in self.process_query(query, "simple_session"):
            if msg.role == MessageType.FINAL_ANSWER:
                final_answer = msg.content
                break
            elif msg.role == MessageType.ERROR:
                raise RuntimeError(msg.content)
        
        return final_answer if final_answer else "未获取到答案"
    
    async def _save_conversation(
        self,
        session_id: str,
        query: str,
        answer: str,
        search_results: Optional[List] = None,
    ) -> None:
        """保存对话到 Memory System.
        
        Args:
            session_id: 会话 ID
            query: 用户问题
            answer: Agent 回答
            search_results: 搜索结果（可选）
        """
        if not self._memory_system:
            logger.debug("Memory System not available, skipping save")
            return
        
        try:
            # 保存用户问题
            self._memory_system.add_conversation(
                role="user",
                content=query,
                metadata={"session_id": session_id},
            )
            
            # 保存 Agent 回答
            self._memory_system.add_conversation(
                role="assistant",
                content=answer,
                metadata={"session_id": session_id},
            )
            
            # 如果有搜索结果，保存为经验
            if search_results and len(search_results) > 0:
                # 提取来源信息
                sources = []
                for r in search_results[:3]:
                    source = getattr(r, 'metadata', {})
                    if isinstance(source, dict):
                        src = source.get('source_path', source.get('source', ''))
                        if src:
                            sources.append(src)
                
                # 动态计算重要性
                importance = self._calculate_importance(
                    query=query,
                    answer=answer,
                    search_results=search_results,
                    sources=sources,
                )
                
                # 保存经验
                self._memory_system.add_experience(
                    content=f"Query: {query[:200]}\nAnswer: {answer[:200]}...\nSources: {', '.join(sources) if sources else 'N/A'}",
                    importance=importance,
                    metadata={
                        "session_id": session_id,
                        "sources": sources,
                        "result_count": len(search_results),
                        "answer_length": len(answer),
                    },
                )
            
            logger.debug(f"Conversation saved for session {session_id}")
            
        except Exception as e:
            logger.warning(f"Failed to save conversation: {e}")
    
    def _record_to_rag_trace(
        self,
        query: str,
        search_results: Optional[List],
        session_id: str,
    ) -> None:
        """记录查询到主 RAG 项目的 TraceCollector.
        
        这使得查询可以在 RAG Observability Dashboard 的 Query Traces 页面中查看。
        
        Args:
            query: 用户问题
            search_results: 搜索结果
            session_id: 会话 ID
        """
        if not self._rag_trace_collector:
            return
        
        try:
            from src.core.trace.trace_context import TraceContext
            
            # 创建 TraceContext - 注意：必须设置 trace_type="query" 才能在 Dashboard 中显示
            # 注意：TraceContext 不接受 query 参数，query 需要放在 metadata 中
            trace = TraceContext(
                trace_id=session_id,
                trace_type="query",  # 关键字段！Dashboard 通过此字段过滤 query traces
                metadata={
                    "source": "mcp",
                    "top_k": 5,
                    "collection": "default",
                    "query": query,  # query 放在 metadata 中
                },
            )
            
            # 添加 Query Processing 阶段 - 使用 record_stage 方法
            trace.record_stage(
                stage_name="query_processing",
                data={
                    "original_query": query,
                    "method": "direct",
                    "keywords": query.split(),
                },
            )
            
            # 添加 Dense Retrieval 阶段
            dense_count = len(search_results) if search_results else 0
            trace.record_stage(
                stage_name="dense_retrieval",
                data={
                    "method": "dense",
                    "provider": "chroma",
                    "result_count": dense_count,
                    "top_k": 5,
                    "chunks": [
                        {
                            "chunk_id": getattr(r, 'id', ''),
                            "text": getattr(r, 'text', getattr(r, 'content', ''))[:500],
                            "score": getattr(r, 'score', 0),
                            "source": getattr(r, 'metadata', {}).get('source_path', '') if isinstance(getattr(r, 'metadata', {}), dict) else '',
                        }
                        for r in (search_results or [])[:5]
                    ],
                },
            )
            
            # 完成 trace
            trace.finish()
            
            # 收集 trace
            self._rag_trace_collector.collect(trace)
            logger.debug(f"Trace recorded to RAG: {trace.trace_id}")
            
        except Exception as e:
            logger.warning(f"Failed to record trace to RAG: {e}")
    
    def _save_to_sqlite(
        self,
        session_id: str,
        query: str,
        answer: str,
        search_results: Optional[List],
    ) -> None:
        """保存会话到 SQLite 数据库（用于 Dashboard Session History）.
        
        Args:
            session_id: 会话 ID
            query: 用户问题
            answer: Agent 回答
            search_results: 搜索结果（可选）
        """
        try:
            db_path = Path(self._db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 创建表（如果不存在）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    updated_at TEXT,
                    metadata TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    user_query TEXT,
                    status TEXT,
                    final_result TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    step_index INTEGER,
                    thought TEXT,
                    action TEXT,
                    action_input TEXT,
                    observation TEXT,
                    error TEXT,
                    latency_ms REAL,
                    is_final INTEGER,
                    final_answer TEXT,
                    created_at TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            
            now = datetime.now().isoformat()
            import uuid
            task_id = str(uuid.uuid4())
            
            # 插入或更新 session
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (session_id, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?)
            """, (session_id, now, now, json.dumps({"query": query, "source": "chat_page"})))
            
            # 插入 task
            cursor.execute("""
                INSERT OR REPLACE INTO tasks (task_id, session_id, user_query, status, final_result, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (task_id, session_id, query, "completed", answer, now, now))
            
            # 插入 step（简化版，只记录最终答案）
            cursor.execute("""
                INSERT INTO steps (task_id, step_index, thought, action, action_input, observation, error, latency_ms, is_final, final_answer, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                0,
                json.dumps({"content": f"分析用户问题：{query[:100]}"}),
                "query_knowledge_hub",
                json.dumps({"query": query}),
                f"知识库返回 {len(search_results) if search_results else 0} 条结果",
                None,
                0,
                1,
                answer,
                now,
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Saved session {session_id} to SQLite database")
            
        except Exception as e:
            logger.warning(f"Failed to save to SQLite: {e}")


# 全局服务实例（用于 Streamlit）
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """获取 ChatService 单例实例."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


async def initialize_chat_service(config_path: Optional[str] = None) -> ChatService:
    """初始化并获取 ChatService 实例."""
    service = get_chat_service()
    await service.initialize(config_path)
    return service


async def shutdown_chat_service() -> None:
    """关闭 ChatService 实例."""
    service = get_chat_service()
    await service.shutdown()