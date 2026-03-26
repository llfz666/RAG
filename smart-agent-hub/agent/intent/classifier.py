"""意图分类器 - 基于 LLM 的意图识别和实体抽取。"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from agent.intent.models import (
    IntentType,
    EntityType,
    Entity,
    IntentResult,
    INTENT_SLOTS,
    INTENT_DESCRIPTIONS,
)
from agent.llm.client import BaseLLMClient, LLMMessage


class IntentClassifier:
    """意图分类器 - 使用 LLM 进行意图识别和实体抽取。
    
    支持两种模式：
    1. 基于 LLM 的分类（高精度）
    2. 基于规则的快速匹配（低延迟）
    """
    
    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        use_rule_based: bool = False,
    ):
        """初始化意图分类器。
        
        Args:
            llm_client: LLM 客户端，用于高精度分类。
            use_rule_based: 是否使用基于规则的分类（快速但精度较低）。
        """
        self.llm_client = llm_client
        self.use_rule_based = use_rule_based
        
        # 规则匹配的关键词映射
        self._init_rule_patterns()
    
    def _init_rule_patterns(self) -> None:
        """初始化规则匹配模式。"""
        # 意图关键词映射
        self.intent_keywords: dict[IntentType, list[str]] = {
            IntentType.GREETING: ["你好", "您好", "早上好", "下午好", "晚上好", "嗨", "hello", "hi"],
            IntentType.FAREWELL: ["再见", "拜拜", "下次聊", "先这样", "挂了", "bye", "goodbye"],
            IntentType.SERVICE_INQUIRY: ["服务", "业务", "能做", "提供", "设计", "制作"],
            IntentType.PRICE_QUOTE: ["多少钱", "价格", "费用", "报价", "收费", "贵", "预算"],
            IntentType.CASE_PORTFOLIO: ["案例", "作品", "样品", "参考", "看看", "示例"],
            IntentType.TIMELINE: ["多久", "多长时间", "几天", "周期", "什么时候", "来得及"],
            IntentType.REVISION: ["修改", "改一下", "调整", "不满意", "重做", "换个"],
            IntentType.URGENT: ["急", "赶紧", "快点", "马上", "今天", "明天", "加急"],
            IntentType.FOLLOW_UP: ["进度", "怎么样了", "做完没", "进行", "跟进"],
            IntentType.COMPLAINT: ["投诉", "太差", "不满意", "垃圾", "骗子", "退款"],
            IntentType.HANDOFF: ["人工", "客服", "电话", "联系", "转接", "真人"],
            IntentType.CONFIRM: ["确认", "确定", "是的", "对的", "没错", "好的"],
            IntentType.CANCEL: ["取消", "不要了", "退了", "撤销", "不做了"],
            IntentType.FAQ: ["发票", "付款", "支付", "合同", "售后", "保修"],
        }
        
        # 实体关键词映射
        self.entity_keywords: dict[EntityType, list[str]] = {
            EntityType.SERVICE_TYPE: [
                "logo", "VI", "SI", "包装", "海报", "画册", "宣传册", "名片",
                "展架", "易拉宝", "横幅", "广告", "视频", "动画", "3D", "渲染",
                "平面", "UI", "网页", "H5", "推文", "公众号", "小程序",
            ],
            EntityType.DEADLINE: [
                "今天", "明天", "后天", "本周", "下周", "月底", "月底",
                "周一", "周五", "周末", "号", "号前", "之前", "之前",
            ],
            EntityType.DURATION: [
                "天", "周", "月", "小时", "工作日", "星期", "号到",
            ],
            EntityType.BUDGET: [
                "元", "万", "千", "预算", "左右", "以内", "以上", "以下",
            ],
            EntityType.QUANTITY: [
                "个", "份", "套", "张", "页", "款", "版", "次",
            ],
        }
    
    async def classify(self, text: str) -> IntentResult:
        """对用户输入进行意图分类。
        
        Args:
            text: 用户输入文本。
            
        Returns:
            IntentResult: 意图识别结果。
        """
        if self.use_rule_based or not self.llm_client:
            return self._classify_by_rules(text)
        else:
            return await self._classify_by_llm(text)
    
    def _classify_by_rules(self, text: str) -> IntentResult:
        """基于规则进行意图分类。
        
        Args:
            text: 用户输入文本。
            
        Returns:
            IntentResult: 意图识别结果。
        """
        text_lower = text.lower()
        
        # 匹配意图
        best_intent = IntentType.UNKNOWN
        best_score = 0
        
        for intent, keywords in self.intent_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_intent = intent
        
        # 提取实体
        entities = self._extract_entities(text)
        
        # 计算置信度
        confidence = min(0.9, 0.3 + best_score * 0.2)
        
        # 检查是否需要更多信息
        missing_slots = self._check_missing_slots(best_intent, entities)
        
        return IntentResult(
            intent=best_intent,
            confidence=confidence,
            entities=entities,
            raw_text=text,
            needs_more_info=len(missing_slots) > 0,
            missing_slots=missing_slots,
        )
    
    async def _classify_by_llm(self, text: str) -> IntentResult:
        """基于 LLM 进行意图分类。
        
        Args:
            text: 用户输入文本。
            
        Returns:
            IntentResult: 意图识别结果。
        """
        # 构建 Prompt
        intent_list = "\n".join([
            f"- {intent.value}: {desc}"
            for intent, desc in INTENT_DESCRIPTIONS.items()
            if intent != IntentType.UNKNOWN
        ])
        
        prompt = f"""你是一个广告公司客服系统的意图识别助手。请分析用户输入的意图并提取实体。

## 可用意图类型
{intent_list}

## 实体类型
- service_type: 服务类型（如 Logo 设计、VI 设计、包装设计等）
- deadline: 截止时间
- duration: 周期时长
- budget: 预算
- price: 价格
- project_name: 项目名称
- industry: 行业类型
- company_name: 公司名称
- contact: 联系方式
- quantity: 数量

## 输出格式
请严格输出 JSON 格式，不要有其他内容：
{{
    "intent": "意图类型",
    "confidence": 0.95,
    "entities": [
        {{"type": "entity_type", "value": "实体值", "confidence": 0.9}}
    ],
    "slots": {{
        "slot_name": "slot_value"
    }},
    "needs_more_info": true,
    "missing_slots": ["slot1", "slot2"]
}}

## 用户输入
{text}

## JSON 输出
"""
        
        try:
            response = await self.llm_client.chat([
                LLMMessage(role="user", content=prompt)
            ])
            
            # 解析 JSON 响应
            content = response.content.strip()
            # 尝试提取 JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group()
            
            result_dict = json.loads(content)
            
            # 转换为 IntentResult
            intent = IntentType(result_dict.get("intent", "unknown"))
            confidence = result_dict.get("confidence", 0.5)
            
            entities = []
            for e in result_dict.get("entities", []):
                try:
                    entity_type = EntityType(e.get("type", ""))
                    entities.append(Entity(
                        entity_type=entity_type,
                        value=e.get("value", ""),
                        confidence=e.get("confidence", 1.0),
                    ))
                except ValueError:
                    continue
            
            slots = result_dict.get("slots", {})
            needs_more_info = result_dict.get("needs_more_info", False)
            missing_slots = result_dict.get("missing_slots", [])
            
            return IntentResult(
                intent=intent,
                confidence=confidence,
                entities=entities,
                raw_text=text,
                slots=slots,
                needs_more_info=needs_more_info,
                missing_slots=missing_slots,
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            # LLM 响应解析失败，回退到规则匹配
            return self._classify_by_rules(text)
    
    def _extract_entities(self, text: str) -> list[Entity]:
        """从文本中提取实体。
        
        Args:
            text: 输入文本。
            
        Returns:
            list[Entity]: 实体列表。
        """
        entities = []
        text_lower = text.lower()
        
        for entity_type, keywords in self.entity_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    # 尝试提取完整的实体值
                    start = text_lower.find(kw)
                    end = start + len(kw)
                    
                    # 向后扩展获取完整值
                    value = self._extract_entity_value(text, start, end)
                    
                    entities.append(Entity(
                        entity_type=entity_type,
                        value=value,
                        start_pos=start,
                        end_pos=end,
                    ))
        
        return entities
    
    def _extract_entity_value(
        self,
        text: str,
        start: int,
        end: int,
        max_length: int = 20,
    ) -> str:
        """提取实体的完整值。
        
        Args:
            text: 原始文本。
            start: 关键词开始位置。
            end: 关键词结束位置。
            max_length: 最大提取长度。
            
        Returns:
            str: 实体值。
        """
        # 向后扩展（数字、中文数字等）
        value = text[start:end]
        i = end
        while i < len(text) and i - start < max_length:
            char = text[i]
            if char.isdigit() or char in "零一二三四五六七八九十百千万亿块元份套张页":
                value += char
                i += 1
            else:
                break
        
        # 向前扩展（数字、货币符号等）
        i = start - 1
        prefix = ""
        while i >= 0 and start - i <= max_length:
            char = text[i]
            if char.isdigit() or char in "¥$零一二三四五六七八九十百千万亿":
                prefix = char + prefix
                i -= 1
            else:
                break
        
        return prefix + value
    
    def _check_missing_slots(
        self,
        intent: IntentType,
        entities: list[Entity],
    ) -> list[str]:
        """检查缺失的槽位。
        
        Args:
            intent: 意图类型。
            entities: 已识别的实体。
            
        Returns:
            list[str]: 缺失的槽位列表。
        """
        required_slots = INTENT_SLOTS.get(intent, [])
        if not required_slots:
            return []
        
        # 将实体转换为槽位
        existing_slots = set()
        for entity in entities:
            slot_name = entity.entity_type.value
            existing_slots.add(slot_name)
        
        # 找出缺失的槽位
        missing = [s for s in required_slots if s not in existing_slots]
        
        return missing
    
    def get_required_slots(self, intent: IntentType) -> list[str]:
        """获取指定意图所需的槽位。
        
        Args:
            intent: 意图类型。
            
        Returns:
            list[str]: 所需槽位列表。
        """
        return INTENT_SLOTS.get(intent, [])