"""情感分析器 - 基于规则和 LLM 的情感理解。"""

from __future__ import annotations

import json
import re
from typing import Optional

from agent.sentiment.models import (
    SentimentType,
    EmotionType,
    UrgencyLevel,
    SentimentResult,
    EMOTION_RESPONSE_STRATEGIES,
    SENTIMENT_RESPONSE_TONES,
    URGENCY_RESPONSE_TIMES,
)
from agent.llm.client import BaseLLMClient, LLMMessage


class SentimentAnalyzer:
    """情感分析器 - 分析用户输入的情感和情绪。
    
    支持两种模式：
    1. 基于规则的分析（快速，适用于明显情绪）
    2. 基于 LLM 的分析（精确，适用于复杂情绪）
    """
    
    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        use_rule_based: bool = False,
    ):
        """初始化情感分析器。
        
        Args:
            llm_client: LLM 客户端，用于精确分析。
            use_rule_based: 是否使用基于规则的分析。
        """
        self.llm_client = llm_client
        self.use_rule_based = use_rule_based
        
        # 初始化规则模式
        self._init_patterns()
    
    def _init_patterns(self) -> None:
        """初始化情感关键词模式。"""
        # 积极情感关键词
        self.positive_words = [
            "好", "棒", "满意", "喜欢", "感谢", "谢谢", "不错", "优秀",
            "完美", "赞", "好评", "推荐", "开心", "高兴", "愉快", "放心",
            "专业", "靠谱", "效率", "满意", "合作", "信任",
        ]
        
        # 消极情感关键词
        self.negative_words = [
            "差", "烂", "失望", "不满", "投诉", "垃圾", "骗子", "退款",
            "慢", "糟糕", "恶心", "愤怒", "生气", "烦", "讨厌", "垃圾",
            "不专业", "不靠谱", "浪费时间", "再也不", "避雷", "坑",
        ]
        
        # 愤怒情绪关键词
        self.anger_words = [
            "气死", "愤怒", "生气", "火大", "恼火", "怒火", "混蛋",
            "什么破", "什么鬼", "太过分", "无法接受", "必须投诉",
        ]
        
        # 焦虑/担忧情绪关键词
        self.fear_words = [
            "担心", "焦虑", "害怕", "恐怕", "万一", "怎么办", "着急",
            "怕", "担忧", "不安", "紧张", "慌",
        ]
        
        # 悲伤情绪关键词
        self.sadness_words = [
            "失望", "难过", "伤心", "失落", "沮丧", "无奈", "心累",
            "无语", "唉", "哎", "可惜", "遗憾",
        ]
        
        # 惊讶情绪关键词
        self.surprise_words = [
            "惊讶", "震惊", "没想到", "居然", "竟然", "意外", "哇",
            "啊", "咦", "哦", "哈",
        ]
        
        # 困惑情绪关键词
        self.confused_words = [
            "不懂", "不明白", "不知道", "困惑", "疑惑", "啥", "怎么",
            "为什么", "如何", "请问", "问一下",
        ]
        
        # 紧急情绪关键词
        self.urgent_words = [
            "急", "赶紧", "快点", "马上", "立刻", "尽快", "加急",
            "今天", "现在", "立刻", "马上", "在线等", "很急",
        ]
        
        # 沮丧情绪关键词
        self.frustrated_words = [
            "无语", "服了", "醉了", "呵呵", "唉", "算了", "随便",
            "反正", "总是", "每次", "又", "还", "再",
        ]
        
        # 程度副词（用于计算情感强度）
        self.intensifiers = [
            "非常", "特别", "极其", "太", "很", "真", "真的", "确实",
            "超级", "十分", "格外", "尤为", "尤其", "相当",
        ]
        
        # 否定词
        self.negators = ["不", "没", "没有", "别", "勿", "非", "无"]
    
    async def analyze(self, text: str) -> SentimentResult:
        """分析文本的情感和情绪。
        
        Args:
            text: 用户输入文本。
            
        Returns:
            SentimentResult: 情感分析结果。
        """
        if self.use_rule_based or not self.llm_client:
            return self._analyze_by_rules(text)
        else:
            return await self._analyze_by_llm(text)
    
    def _analyze_by_rules(self, text: str) -> SentimentResult:
        """基于规则进行情感分析。
        
        Args:
            text: 用户输入文本。
            
        Returns:
            SentimentResult: 情感分析结果。
        """
        text_lower = text.lower()
        
        # 计算积极和消极得分
        positive_score = sum(1 for word in self.positive_words if word in text_lower)
        negative_score = sum(1 for word in self.negative_words if word in text_lower)
        
        # 检查程度副词（增加强度）
        intensifier_count = sum(1 for word in self.intensifiers if word in text_lower)
        intensity_bonus = min(0.5, intensifier_count * 0.1)
        
        # 检查否定词（反转情感）
        negator_count = sum(1 for word in self.negators if word in text_lower)
        
        # 确定总体情感
        if positive_score > negative_score:
            sentiment = SentimentType.POSITIVE
            base_intensity = min(1.0, 0.3 + (positive_score - negative_score) * 0.2)
        elif negative_score > positive_score:
            sentiment = SentimentType.NEGATIVE
            base_intensity = min(1.0, 0.3 + (negative_score - positive_score) * 0.2)
        else:
            sentiment = SentimentType.NEUTRAL
            base_intensity = 0.1
        
        sentiment_intensity = min(1.0, base_intensity + intensity_bonus)
        
        # 检测主要情绪
        emotion_scores: dict[EmotionType, int] = {}
        
        # 愤怒
        anger_score = sum(1 for word in self.anger_words if word in text_lower)
        if anger_score > 0:
            emotion_scores[EmotionType.ANGER] = anger_score
        
        # 焦虑/担忧
        fear_score = sum(1 for word in self.fear_words if word in text_lower)
        if fear_score > 0:
            emotion_scores[EmotionType.FEAR] = fear_score
        
        # 悲伤
        sadness_score = sum(1 for word in self.sadness_words if word in text_lower)
        if sadness_score > 0:
            emotion_scores[EmotionType.SADNESS] = sadness_score
        
        # 惊讶
        surprise_score = sum(1 for word in self.surprise_words if word in text_lower)
        if surprise_score > 0:
            emotion_scores[EmotionType.SURPRISE] = surprise_score
        
        # 困惑
        confused_score = sum(1 for word in self.confused_words if word in text_lower)
        if confused_score > 0:
            emotion_scores[EmotionType.CONFUSED] = confused_score
        
        # 紧急
        urgent_score = sum(1 for word in self.urgent_words if word in text_lower)
        if urgent_score > 0:
            emotion_scores[EmotionType.URGENT] = urgent_score
        
        # 沮丧
        frustrated_score = sum(1 for word in self.frustrated_words if word in text_lower)
        if frustrated_score > 0:
            emotion_scores[EmotionType.FRUSTRATED] = frustrated_score
        
        # 确定主要情绪
        primary_emotion = None
        emotion_intensity = 0.0
        secondary_emotions = []
        
        if emotion_scores:
            sorted_emotions = sorted(
                emotion_scores.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            primary_emotion = sorted_emotions[0][0]
            emotion_intensity = min(1.0, 0.3 + sorted_emotions[0][1] * 0.2)
            
            for emotion, score in sorted_emotions[1:]:
                if score > 0:
                    secondary_emotions.append((emotion, min(1.0, 0.2 + score * 0.15)))
        
        # 确定紧急程度
        if urgent_score >= 3 or "立刻" in text_lower or "马上" in text_lower:
            urgency_level = UrgencyLevel.CRITICAL
        elif urgent_score >= 2 or emotion_scores.get(EmotionType.ANGER, 0) >= 2:
            urgency_level = UrgencyLevel.HIGH
        elif urgent_score >= 1 or negative_score >= 2:
            urgency_level = UrgencyLevel.MEDIUM
        else:
            urgency_level = UrgencyLevel.LOW
        
        # 判断是否需要共情回应
        needs_empathy = (
            sentiment == SentimentType.NEGATIVE or
            primary_emotion in [EmotionType.ANGER, EmotionType.SADNESS, EmotionType.FRUSTRATED] or
            urgency_level in [UrgencyLevel.HIGH, UrgencyLevel.CRITICAL]
        )
        
        # 确定回应策略
        response_strategy = self._get_response_strategy(primary_emotion, sentiment)
        
        # 计算置信度
        confidence = min(0.95, 0.5 + (positive_score + negative_score) * 0.1)
        
        return SentimentResult(
            sentiment=sentiment,
            sentiment_intensity=sentiment_intensity,
            primary_emotion=primary_emotion,
            emotion_intensity=emotion_intensity,
            secondary_emotions=secondary_emotions,
            urgency_level=urgency_level,
            raw_text=text,
            confidence=confidence,
            needs_empathy=needs_empathy,
            response_strategy=response_strategy,
        )
    
    async def _analyze_by_llm(self, text: str) -> SentimentResult:
        """基于 LLM 进行情感分析。
        
        Args:
            text: 用户输入文本。
            
        Returns:
            SentimentResult: 情感分析结果。
        """
        prompt = f"""你是一个专业的情感分析助手。请分析以下用户输入的情感和情绪。

## 情感类型
- positive: 积极（满意、高兴、感谢等）
- neutral: 中性（平静、客观等）
- negative: 消极（不满、失望、愤怒等）

## 情绪类型
- joy: 高兴
- trust: 信任
- fear: 恐惧/担忧
- surprise: 惊讶
- sadness: 悲伤/失望
- disgust: 厌恶
- anger: 愤怒
- anticipation: 期待
- confused: 困惑
- urgent: 急切
- frustrated: 沮丧

## 紧急程度
- low: 低
- medium: 中
- high: 高
- critical: 紧急

## 输出格式
请严格输出 JSON 格式：
{{
    "sentiment": "positive|neutral|negative",
    "sentiment_intensity": 0.8,
    "primary_emotion": "anger",
    "emotion_intensity": 0.7,
    "secondary_emotions": [
        {{"emotion": "frustrated", "intensity": 0.5}}
    ],
    "urgency_level": "high",
    "needs_empathy": true,
    "response_strategy": "冷静处理，优先安抚情绪"
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
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group()
            
            result_dict = json.loads(content)
            
            # 转换为 SentimentResult
            sentiment = SentimentType(result_dict.get("sentiment", "neutral"))
            primary_emotion_str = result_dict.get("primary_emotion")
            primary_emotion = None
            if primary_emotion_str:
                try:
                    primary_emotion = EmotionType(primary_emotion_str)
                except ValueError:
                    pass
            
            secondary_emotions = []
            for se in result_dict.get("secondary_emotions", []):
                try:
                    emotion = EmotionType(se.get("emotion", ""))
                    intensity = se.get("intensity", 0.5)
                    secondary_emotions.append((emotion, intensity))
                except ValueError:
                    continue
            
            urgency_level = UrgencyLevel(result_dict.get("urgency_level", "medium"))
            
            return SentimentResult(
                sentiment=sentiment,
                sentiment_intensity=result_dict.get("sentiment_intensity", 0.5),
                primary_emotion=primary_emotion,
                emotion_intensity=result_dict.get("emotion_intensity", 0.5),
                secondary_emotions=secondary_emotions,
                urgency_level=urgency_level,
                raw_text=text,
                confidence=result_dict.get("confidence", 0.8),
                needs_empathy=result_dict.get("needs_empathy", False),
                response_strategy=result_dict.get("response_strategy", ""),
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            # LLM 响应解析失败，回退到规则匹配
            return self._analyze_by_rules(text)
    
    def _get_response_strategy(
        self,
        primary_emotion: Optional[EmotionType],
        sentiment: SentimentType,
    ) -> str:
        """获取建议的回应策略。
        
        Args:
            primary_emotion: 主要情绪。
            sentiment: 总体情感。
            
        Returns:
            str: 回应策略描述。
        """
        if primary_emotion and primary_emotion in EMOTION_RESPONSE_STRATEGIES:
            return EMOTION_RESPONSE_STRATEGIES[primary_emotion]
        
        return SENTIMENT_RESPONSE_TONES.get(sentiment, "专业礼貌")
    
    def get_empathy_response(self, result: SentimentResult) -> str:
        """根据情感分析结果生成共情回应。
        
        Args:
            result: 情感分析结果。
            
        Returns:
            str: 共情回应文本。
        """
        if not result.needs_empathy:
            return ""
        
        # 根据情绪返回共情语句
        if result.primary_emotion == EmotionType.ANGER:
            return "我非常理解您的心情，遇到这种情况确实会让人感到生气。"
        elif result.primary_emotion == EmotionType.SADNESS:
            return "我能理解您的失望，这确实不是我们想要看到的。"
        elif result.primary_emotion == EmotionType.FRUSTRATED:
            return "我明白这给您带来了困扰，我们一起来看看如何解决。"
        elif result.primary_emotion == EmotionType.FEAR:
            return "请放心，我们会负责到底，确保问题得到解决。"
        elif result.urgency_level == UrgencyLevel.CRITICAL:
            return "我理解这件事非常紧急，我们会立即为您处理。"
        elif result.sentiment == SentimentType.NEGATIVE:
            return "非常抱歉给您带来了不好的体验。"
        
        return ""