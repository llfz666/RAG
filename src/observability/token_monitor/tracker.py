"""
Token Tracker - Token 使用追踪器核心模块

负责：
1. 记录每次 LLM 调用的 token 使用
2. 提供查询和统计接口
3. 管理数据存储（SQLite + JSONL）
"""

import sqlite3
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager

from .config import TokenMonitorConfig
from .models import TokenUsage, TokenStatus, UsageStats, ModelBreakdown, UserBreakdown


class TokenTracker:
    """
    Token 使用追踪器
    
    线程安全设计：
    - 使用连接池管理 SQLite 连接
    - 使用 WAL 模式支持并发读写
    - 批量写入优化性能
    
    使用示例：
        config = TokenMonitorConfig.from_yaml("config/settings.yaml")
        tracker = TokenTracker(config)
        
        # 记录使用
        tracker.record(
            model="gpt-3.5-turbo",
            prompt_tokens=100,
            completion_tokens=50,
            user_id="user_123",
            task_type="chat"
        )
        
        # 查询统计
        stats = tracker.get_stats(days=7)
    """
    
    # SQLite 初始化 SQL
    INIT_SQL = """
    -- 启用 WAL 模式支持并发
    PRAGMA journal_mode = WAL;
    PRAGMA synchronous = NORMAL;
    PRAGMA busy_timeout = 5000;
    
    -- Token 使用记录表
    CREATE TABLE IF NOT EXISTS token_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model TEXT NOT NULL,
        prompt_tokens INTEGER NOT NULL,
        completion_tokens INTEGER NOT NULL,
        total_tokens INTEGER NOT NULL,
        cost REAL NOT NULL,
        timestamp TEXT NOT NULL,
        user_id TEXT,
        session_id TEXT,
        task_type TEXT,
        status TEXT NOT NULL DEFAULT 'success',
        error_message TEXT,
        duration_ms INTEGER,
        metadata TEXT,
        namespace TEXT DEFAULT 'default'
    );
    
    -- 告警记录表
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        user_id TEXT,
        is_resolved INTEGER DEFAULT 0,
        resolved_at TEXT,
        metadata TEXT
    );
    
    -- 用户预算配置表
    CREATE TABLE IF NOT EXISTS user_budgets (
        user_id TEXT PRIMARY KEY,
        daily_budget REAL NOT NULL,
        monthly_budget REAL NOT NULL,
        alert_threshold REAL NOT NULL DEFAULT 0.8,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    
    -- 索引优化查询性能
    CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON token_usage(timestamp);
    CREATE INDEX IF NOT EXISTS idx_usage_user ON token_usage(user_id);
    CREATE INDEX IF NOT EXISTS idx_usage_model ON token_usage(model);
    CREATE INDEX IF NOT EXISTS idx_usage_namespace ON token_usage(namespace);
    CREATE INDEX IF NOT EXISTS idx_usage_status ON token_usage(status);
    """
    
    def __init__(self, config: TokenMonitorConfig):
        """
        初始化 TokenTracker
        
        Args:
            config: 配置对象
        """
        self.config = config
        self._local = threading.local()
        
        # 确保目录存在
        self._ensure_directories()
        
        # 初始化数据库
        self._init_database()
        
        # 写入缓冲区（用于批量写入）
        self._buffer: List[TokenUsage] = []
        self._buffer_lock = threading.Lock()
        self._max_buffer_size = 100
        
        # 内存缓存（用于快速统计）
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(seconds=30)
    
    def _ensure_directories(self) -> None:
        """确保数据库和日志目录存在"""
        db_path = Path(self.config.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        log_path = Path(self.config.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self) -> None:
        """初始化数据库"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 执行初始化 SQL
            for statement in self.INIT_SQL.split(';'):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(
            self.config.database_path,
            timeout=30.0,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key in self._cache:
            if datetime.now() - self._cache_time[key] < self._cache_ttl:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._cache_time[key]
        return None
    
    def _set_cached(self, key: str, value: Any) -> None:
        """设置缓存值"""
        self._cache[key] = value
        self._cache_time[key] = datetime.now()
    
    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_type: Optional[str] = None,
        status: TokenStatus = TokenStatus.SUCCESS,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        sync: bool = False,
    ) -> TokenUsage:
        """
        记录一次 Token 使用
        
        Args:
            model: 模型名称
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数
            user_id: 用户 ID
            session_id: 会话 ID
            task_type: 任务类型
            status: 状态
            error_message: 错误消息
            duration_ms: 耗时（毫秒）
            metadata: 额外元数据
            namespace: 命名空间（用于隔离不同应用）
            sync: 是否同步写入（默认 False，异步批量写入）
        
        Returns:
            TokenUsage 记录对象
        """
        # 检查是否启用
        if not self.config.enabled:
            usage = TokenUsage(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                cost=0.0,
                user_id=user_id,
                session_id=session_id,
                task_type=task_type,
                status=status,
                error_message=error_message,
                duration_ms=duration_ms,
                metadata=metadata or {},
                namespace=namespace or self.config.namespace,
            )
            return usage
        
        # 采样检查
        if self.config.sampling_enabled:
            import random
            if random.random() > self.config.sampling_rate:
                # 跳过记录
                usage = TokenUsage(
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    cost=0.0,
                    user_id=user_id,
                    session_id=session_id,
                    task_type=task_type,
                    status=status,
                    error_message=error_message,
                    duration_ms=duration_ms,
                    metadata=metadata or {},
                    namespace=namespace or self.config.namespace,
                )
                return usage
        
        # 计算成本
        cost = self.config.calculate_cost(model, prompt_tokens, completion_tokens)
        
        # 创建记录
        usage = TokenUsage(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=cost,
            user_id=user_id,
            session_id=session_id,
            task_type=task_type,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
            metadata=metadata or {},
            namespace=namespace or self.config.namespace,
        )
        
        # 写入存储
        if sync:
            self._write_usage_sync(usage)
        else:
            self._write_usage_buffered(usage)
        
        # 写入 JSONL 日志
        self._write_jsonl_log(usage)
        
        # 使缓存失效
        self._invalidate_cache()
        
        return usage
    
    def _write_usage_sync(self, usage: TokenUsage) -> None:
        """同步写入数据库"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO token_usage 
                (model, prompt_tokens, completion_tokens, total_tokens, cost,
                 timestamp, user_id, session_id, task_type, status, 
                 error_message, duration_ms, metadata, namespace)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                usage.model,
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
                usage.cost,
                usage.timestamp.isoformat(),
                usage.user_id,
                usage.session_id,
                usage.task_type,
                usage.status.value,
                usage.error_message,
                usage.duration_ms,
                json.dumps(usage.metadata, ensure_ascii=False) if usage.metadata else None,
                usage.namespace,
            ))
            conn.commit()
    
    def _write_usage_buffered(self, usage: TokenUsage) -> None:
        """缓冲写入（批量）"""
        with self._buffer_lock:
            self._buffer.append(usage)
            
            if len(self._buffer) >= self._max_buffer_size:
                self._flush_buffer()
    
    def _flush_buffer(self) -> None:
        """刷新缓冲区"""
        with self._buffer_lock:
            if not self._buffer:
                return
            
            buffer_copy = self._buffer.copy()
            self._buffer.clear()
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT INTO token_usage 
                    (model, prompt_tokens, completion_tokens, total_tokens, cost,
                     timestamp, user_id, session_id, task_type, status, 
                     error_message, duration_ms, metadata, namespace)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    (
                        u.model,
                        u.prompt_tokens,
                        u.completion_tokens,
                        u.total_tokens,
                        u.cost,
                        u.timestamp.isoformat(),
                        u.user_id,
                        u.session_id,
                        u.task_type,
                        u.status.value,
                        u.error_message,
                        u.duration_ms,
                        json.dumps(u.metadata, ensure_ascii=False) if u.metadata else None,
                        u.namespace,
                    )
                    for u in buffer_copy
                ])
                conn.commit()
        except Exception as e:
            # 写入失败，将数据放回缓冲区
            with self._buffer_lock:
                self._buffer.extend(buffer_copy)
            # 记录错误（但不抛出异常，避免影响主流程）
            print(f"TokenTracker: 批量写入失败：{e}")
    
    def _write_jsonl_log(self, usage: TokenUsage) -> None:
        """写入 JSONL 日志文件"""
        try:
            log_path = Path(self.config.log_file)
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(usage.to_dict(), ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"TokenTracker: JSONL 日志写入失败：{e}")
    
    def _invalidate_cache(self) -> None:
        """使所有缓存失效"""
        self._cache.clear()
        self._cache_time.clear()
    
    def get_stats(
        self,
        days: int = 7,
        user_id: Optional[str] = None,
        namespace: Optional[str] = None,
    ) -> UsageStats:
        """
        获取用量统计
        
        Args:
            days: 统计天数
            user_id: 用户 ID（可选，限制到特定用户）
            namespace: 命名空间（可选，限制到特定应用）
        
        Returns:
            UsageStats 统计对象
        """
        cache_key = f"stats:{days}:{user_id}:{namespace}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        namespace = namespace or self.config.namespace
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 基础查询条件
            base_query = "FROM token_usage WHERE timestamp >= ?"
            base_params: List[Any] = [cutoff]
            
            if user_id:
                base_query += " AND user_id = ?"
                base_params.append(user_id)
            
            if namespace:
                base_query += " AND namespace = ?"
                base_params.append(namespace)
            
            # 总量统计
            cursor.execute(f"""
                SELECT 
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(cost), 0) as total_cost,
                    COUNT(*) as total_requests
                {base_query}
            """, base_params)
            row = cursor.fetchone()
            
            stats = UsageStats(
                total_tokens=row['total_tokens'] or 0,
                total_cost=row['total_cost'] or 0.0,
                total_requests=row['total_requests'] or 0,
                start_time=datetime.fromisoformat(cutoff),
                end_time=datetime.now(),
            )
            
            # 按模型分组
            cursor.execute(f"""
                SELECT 
                    model,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost,
                    COUNT(*) as request_count
                {base_query}
                GROUP BY model
            """, base_params)
            
            stats.by_model = {
                row['model']: {
                    'total_tokens': row['total_tokens'] or 0,
                    'total_cost': row['total_cost'] or 0.0,
                    'request_count': row['request_count'] or 0,
                }
                for row in cursor.fetchall()
            }
            
            # 按用户分组
            cursor.execute(f"""
                SELECT 
                    user_id,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost,
                    COUNT(*) as request_count
                {base_query}
                GROUP BY user_id
            """, base_params)
            
            stats.by_user = {
                row['user_id'] or 'anonymous': {
                    'total_tokens': row['total_tokens'] or 0,
                    'total_cost': row['total_cost'] or 0.0,
                    'request_count': row['request_count'] or 0,
                }
                for row in cursor.fetchall()
            }
            
            # 按任务类型分组
            cursor.execute(f"""
                SELECT 
                    task_type,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost,
                    COUNT(*) as request_count
                {base_query}
                GROUP BY task_type
            """, base_params)
            
            stats.by_task_type = {
                row['task_type'] or 'other': {
                    'total_tokens': row['total_tokens'] or 0,
                    'total_cost': row['total_cost'] or 0.0,
                    'request_count': row['request_count'] or 0,
                }
                for row in cursor.fetchall()
            }
        
        self._set_cached(cache_key, stats)
        return stats
    
    def get_today_usage(self, user_id: Optional[str] = None) -> float:
        """获取今日用量（成本）"""
        stats = self.get_stats(days=1, user_id=user_id)
        return stats.total_cost
    
    def get_month_usage(self, user_id: Optional[str] = None) -> float:
        """获取本月用量（成本）"""
        stats = self.get_stats(days=30, user_id=user_id)
        return stats.total_cost
    
    def get_model_breakdown(self, days: int = 7) -> List[ModelBreakdown]:
        """获取模型用量明细"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        namespace = self.config.namespace
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    model,
                    SUM(total_tokens) as total_tokens,
                    SUM(prompt_tokens) as prompt_tokens,
                    SUM(completion_tokens) as completion_tokens,
                    SUM(cost) as total_cost,
                    COUNT(*) as request_count
                FROM token_usage
                WHERE timestamp >= ? AND namespace = ?
                GROUP BY model
                ORDER BY total_cost DESC
            """, [cutoff, namespace])
            
            return [
                ModelBreakdown(
                    model=row['model'],
                    total_tokens=row['total_tokens'] or 0,
                    prompt_tokens=row['prompt_tokens'] or 0,
                    completion_tokens=row['completion_tokens'] or 0,
                    total_cost=row['total_cost'] or 0.0,
                    request_count=row['request_count'] or 0,
                )
                for row in cursor.fetchall()
            ]
    
    def get_user_breakdown(self, days: int = 7) -> List[UserBreakdown]:
        """获取用户用量明细"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        namespace = self.config.namespace
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    user_id,
                    SUM(total_tokens) as total_tokens,
                    SUM(cost) as total_cost,
                    COUNT(*) as request_count,
                    MAX(timestamp) as last_activity
                FROM token_usage
                WHERE timestamp >= ? AND namespace = ? AND user_id IS NOT NULL
                GROUP BY user_id
                ORDER BY total_cost DESC
            """, [cutoff, namespace])
            
            return [
                UserBreakdown(
                    user_id=row['user_id'],
                    total_tokens=row['total_tokens'] or 0,
                    total_cost=row['total_cost'] or 0.0,
                    request_count=row['request_count'] or 0,
                    last_activity=datetime.fromisoformat(row['last_activity']) if row['last_activity'] else None,
                )
                for row in cursor.fetchall()
            ]
    
    def get_recent_usage(self, limit: int = 50) -> List[TokenUsage]:
        """获取最近使用记录"""
        namespace = self.config.namespace
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM token_usage
                WHERE namespace = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, [namespace, limit])
            
            return [
                TokenUsage(
                    id=row['id'],
                    model=row['model'],
                    prompt_tokens=row['prompt_tokens'],
                    completion_tokens=row['completion_tokens'],
                    total_tokens=row['total_tokens'],
                    cost=row['cost'],
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    user_id=row['user_id'],
                    session_id=row['session_id'],
                    task_type=row['task_type'],
                    status=TokenStatus(row['status']),
                    error_message=row['error_message'],
                    duration_ms=row['duration_ms'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else None,
                )
                for row in cursor.fetchall()
            ]
    
    def flush(self) -> None:
        """强制刷新缓冲区"""
        self._flush_buffer()
    
    def close(self) -> None:
        """关闭追踪器，刷新所有缓冲区"""
        self.flush()