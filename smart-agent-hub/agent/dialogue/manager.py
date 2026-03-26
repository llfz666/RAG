"""对话管理器 - 管理对话状态和流程控制。"""

from __future__ import annotations

from typing import Any, Optional

from agent.intent.models import IntentResult, IntentType, INTENT_SLOTS
from agent.sentiment.models import SentimentResult
from agent.dialogue.models import (
    DialogueState,
    FlowStage,
    DialogueContext,
    DialogueAct,
    DialogueTurn,
)


class DialogueManager:
    """对话管理器 - 管理对话状态、槽位填充和流程控制。
    
    主要功能：
    1. 对话状态追踪 (DST)
    2. 槽位填充管理
    3. 对话流程控制
    4. 上下文管理
    """
    
    def __init__(self, context: Optional[DialogueContext] = None):
        """初始化对话管理器。
        
        Args:
            context: 对话上下文，如果为 None 则创建新的上下文。
        """
        self.context = context or DialogueContext()
        
        # 问候语模板
        self.greeting_templates = [
            "您好！欢迎咨询创意广告设计公司，我是您的智能助手。请问有什么可以帮您？",
            "您好！这里是创意广告设计公司客服中心。请问您需要什么帮助？",
            "欢迎光临！我们提供专业的广告设计服务。请问您想了解什么？",
        ]
        
        # 告别语模板
        self.farewell_templates = [
            "感谢您的咨询，祝您生活愉快！如有其他问题随时联系我们。",
            "谢谢您的来电，期待与您的合作。再见！",
            "感谢您的咨询，如有需要随时联系我们。祝您工作顺利！",
        ]
        
        # 确认模板
        self.confirm_templates = [
            "好的，我确认一下您的需求：{summary}。请问还有其他需要补充的吗？",
            "明白了，您需要{summary}。对吗？",
            "让我确认一下：{summary}。是这样吗？",
        ]
        
        # 请求信息模板
        self.request_templates = {
            "service_type": "请问您需要什么类型的服务？比如 Logo 设计、VI 设计、包装设计等。",
            "quantity": "请问您需要制作多少个/份？",
            "budget": "请问您的预算大概是多少？",
            "deadline": "请问您什么时候需要？有具体的截止时间吗？",
            "industry": "请问您所在的行业是什么？",
            "project_name": "请问这个项目的名称是什么？",
            "revision_reason": "请问您具体需要修改哪些地方？",
        }
    
    def start_dialogue(self, user_id: Optional[str] = None) -> str:
        """开始新的对话。
        
        Args:
            user_id: 用户 ID。
            
        Returns:
            str: 问候语。
        """
        self.context = DialogueContext()
        self.context.user_id = user_id
        self.context.state = DialogueState.ACTIVE
        self.context.flow_stage = FlowStage.GREETING
        
        greeting = self.greeting_templates[0]
        
        # 记录对话轮次
        self.context.add_turn(
            user_input="",
            system_response=greeting,
        )
        
        return greeting
    
    def process_input(
        self,
        user_input: str,
        intent_result: IntentResult,
        sentiment_result: Optional[SentimentResult] = None,
    ) -> tuple[str, DialogueState]:
        """处理用户输入。
        
        Args:
            user_input: 用户输入文本。
            intent_result: 意图识别结果。
            sentiment_result: 情感分析结果。
            
        Returns:
            tuple[str, DialogueState]: 系统回复和新的对话状态。
        """
        # 更新上下文
        self._update_context(intent_result, sentiment_result)
        
        # 根据意图和当前状态决定回复
        response = self._generate_response(user_input, intent_result, sentiment_result)
        
        # 记录对话轮次
        self.context.add_turn(
            user_input=user_input,
            system_response=response,
            intent_result=intent_result,
            sentiment_result=sentiment_result,
        )
        
        return response, self.context.state
    
    def _update_context(
        self,
        intent_result: IntentResult,
        sentiment_result: Optional[SentimentResult],
    ) -> None:
        """更新对话上下文。
        
        Args:
            intent_result: 意图识别结果。
            sentiment_result: 情感分析结果。
        """
        # 更新当前意图
        self.context.current_intent = intent_result.intent
        
        # 更新槽位
        if intent_result.slots:
            self.context.update_slots(intent_result.slots)
        
        # 更新指代信息
        if intent_result.entities:
            self.context.update_references(intent_result.entities)
        
        # 根据意图更新流程阶段
        if intent_result.intent in [IntentType.GREETING, IntentType.FAREWELL]:
            pass  # 保持当前阶段
        elif intent_result.intent == IntentType.HANDOFF:
            self.context.state = DialogueState.HANDOFF
        elif intent_result.needs_more_info:
            self.context.flow_stage = FlowStage.SLOT_FILLING
            self.context.pending_slots = intent_result.missing_slots
        else:
            self.context.flow_stage = FlowStage.CONFIRMATION
    
    def _generate_response(
        self,
        user_input: str,
        intent_result: IntentResult,
        sentiment_result: Optional[SentimentResult],
    ) -> str:
        """生成系统回复。
        
        Args:
            user_input: 用户输入。
            intent_result: 意图识别结果。
            sentiment_result: 情感分析结果。
            
        Returns:
            str: 系统回复。
        """
        intent = intent_result.intent
        
        # 处理特殊意图
        if intent == IntentType.GREETING:
            return self._handle_greeting(intent_result)
        
        if intent == IntentType.FAREWELL:
            return self._handle_farewell(intent_result)
        
        if intent == IntentType.HANDOFF:
            return self._handle_handoff(intent_result)
        
        if intent == IntentType.CONFIRM:
            return self._handle_confirm(intent_result)
        
        # 检查是否需要填充槽位
        if intent_result.needs_more_info:
            return self._request_missing_slots(intent_result)
        
        # 处理槽位填充阶段
        if self.context.flow_stage == FlowStage.SLOT_FILLING:
            return self._handle_slot_filling(intent_result)
        
        # 确认阶段
        if self.context.flow_stage == FlowStage.CONFIRMATION:
            return self._handle_confirmation(intent_result)
        
        # 根据意图类型生成回复
        return self._handle_intent_response(intent_result, sentiment_result)
    
    def _handle_greeting(self, intent_result: IntentResult) -> str:
        """处理问候。"""
        self.context.flow_stage = FlowStage.INTENT_RECOGNITION
        return "您好！欢迎咨询创意广告设计公司，我是您的智能助手。请问有什么可以帮您？"
    
    def _handle_farewell(self, intent_result: IntentResult) -> str:
        """处理告别。"""
        self.context.state = DialogueState.CLOSED
        return self.farewell_templates[0]
    
    def _handle_handoff(self, intent_result: IntentResult) -> str:
        """处理转人工。"""
        self.context.state = DialogueState.HANDOFF
        return "好的，正在为您转接人工客服，请稍候...\n\n（转接中，预计等待时间：1-2 分钟）"
    
    def _handle_confirm(self, intent_result: IntentResult) -> str:
        """处理用户确认。"""
        # 用户确认了信息，进入解决方案阶段
        self.context.flow_stage = FlowStage.SOLUTION
        return "好的，已确认您的需求。正在为您处理..."
    
    def _request_missing_slots(self, intent_result: IntentResult) -> str:
        """请求缺失的槽位信息。
        
        Args:
            intent_result: 意图识别结果。
            
        Returns:
            str: 请求信息的回复。
        """
        missing = intent_result.missing_slots
        
        if not missing:
            return ""
        
        # 获取第一个缺失槽位的提示
        slot = missing[0]
        
        if slot in self.request_templates:
            return self.request_templates[slot]
        
        return f"请问您能提供关于{slot}的信息吗？"
    
    def _handle_slot_filling(self, intent_result: IntentResult) -> str:
        """处理槽位填充阶段。
        
        Args:
            intent_result: 意图识别结果。
            
        Returns:
            str: 系统回复。
        """
        # 检查是否所有槽位都已填充
        required_slots = INTENT_SLOTS.get(self.context.current_intent, [])
        
        if not required_slots:
            self.context.flow_stage = FlowStage.CONFIRMATION
            return self._handle_confirmation(intent_result)
        
        # 检查缺失的槽位
        missing_slots = [
            s for s in required_slots
            if s not in self.context.filled_slots
        ]
        
        if not missing_slots:
            self.context.flow_stage = FlowStage.CONFIRMATION
            return self._handle_confirmation(intent_result)
        
        # 请求缺失的槽位
        self.context.pending_slots = missing_slots
        return self._request_missing_slots(intent_result)
    
    def _handle_confirmation(self, intent_result: IntentResult) -> str:
        """处理确认阶段。
        
        Args:
            intent_result: 意图识别结果。
            
        Returns:
            str: 确认回复。
        """
        # 生成需求摘要
        summary = self._generate_summary()
        
        # 使用确认模板
        response = self.confirm_templates[0].format(summary=summary)
        
        return response
    
    def _handle_intent_response(
        self,
        intent_result: IntentResult,
        sentiment_result: Optional[SentimentResult],
    ) -> str:
        """根据意图生成回复。
        
        Args:
            intent_result: 意图识别结果。
            sentiment_result: 情感分析结果。
            
        Returns:
            str: 系统回复。
        """
        intent = intent_result.intent
        
        # 共情回应（如果有情感分析结果）
        empathy = ""
        if sentiment_result and sentiment_result.needs_empathy:
            from agent.sentiment.analyzer import SentimentAnalyzer
            analyzer = SentimentAnalyzer()
            empathy = analyzer.get_empathy_response(sentiment_result)
        
        # 根据意图类型返回相应回复
        responses = {
            IntentType.SERVICE_INQUIRY: self._reply_service_inquiry,
            IntentType.PRICE_QUOTE: self._reply_price_quote,
            IntentType.CASE_PORTFOLIO: self._reply_case_portfolio,
            IntentType.TIMELINE: self._reply_timeline,
            IntentType.COMPANY_INFO: self._reply_company_info,
            IntentType.REVISION: self._reply_revision,
            IntentType.URGENT: self._reply_urgent,
            IntentType.FOLLOW_UP: self._reply_follow_up,
            IntentType.COMPLAINT: self._reply_complaint,
            IntentType.PRAISE: self._reply_praise,
            IntentType.FAQ: self._reply_faq,
        }
        
        handler = responses.get(intent, self._reply_unknown)
        base_response = handler(intent_result)
        
        # 如果有共情回应，放在前面
        if empathy:
            return f"{empathy}\n\n{base_response}"
        
        return base_response
    
    def _generate_summary(self) -> str:
        """生成需求摘要。"""
        slots = self.context.filled_slots
        
        parts = []
        if "service_type" in slots:
            parts.append(f"服务类型：{slots['service_type']}")
        if "quantity" in slots:
            parts.append(f"数量：{slots['quantity']}")
        if "budget" in slots:
            parts.append(f"预算：{slots['budget']}")
        if "deadline" in slots:
            parts.append(f"截止时间：{slots['deadline']}")
        if "industry" in slots:
            parts.append(f"行业：{slots['industry']}")
        
        return "；".join(parts) if parts else "暂无明确需求"
    
    # 各意图的回复处理方法
    def _reply_service_inquiry(self, intent_result: IntentResult) -> str:
        """回复服务咨询。"""
        return """我们提供以下广告设计服务：

📐 **品牌设计**
- Logo 设计
- VI 视觉识别系统
- SI 空间形象设计

📦 **包装设计**
- 产品包装设计
- 包装盒设计
- 标签设计

📢 **广告设计**
- 海报设计
- 宣传册/画册设计
- 易拉宝/展架设计
- 横幅/广告图设计

💻 **数字媒体**
- 网页设计
- UI/UX 设计
- H5 页面设计
- 公众号推文排版

🎬 **视频动画**
- 企业宣传片
- 产品动画
- 短视频制作

请问您对哪类服务感兴趣？"""
    
    def _reply_price_quote(self, intent_result: IntentResult) -> str:
        """回复报价咨询。"""
        service_type = self.context.get_slot("service_type", "具体服务")
        
        return f"""关于{service_type}的报价，价格会根据以下因素有所不同：

💰 **影响价格的因素**
- 设计复杂程度
- 设计师级别
- 修改次数
- 交付周期
- 使用范围授权

📋 **参考价格范围**
- Logo 设计：¥2,000 - ¥20,000
- VI 设计：¥10,000 - ¥50,000
- 包装设计：¥3,000 - ¥15,000/款
- 海报设计：¥1,000 - ¥5,000

为了给您更准确的报价，请告诉我：
1. 具体的设计需求
2. 期望的设计风格
3. 预算范围

我们可以根据您的预算提供最适合的方案。"""
    
    def _reply_case_portfolio(self, intent_result: IntentResult) -> str:
        """回复案例展示请求。"""
        return """当然可以！以下是我们部分优秀作品：

🏆 **品牌设计案例**
- [某知名科技公司] Logo 及 VI 设计
- [某连锁餐饮品牌] 全套视觉形象设计

📦 **包装设计案例**
- [某高端茶叶品牌] 礼盒包装设计
- [某化妆品品牌] 产品系列包装设计

📢 **广告设计案例**
- [某汽车品牌的] 年度 campaign 视觉设计
- [某电商平台的] 双 11 活动主视觉

请问您想查看哪类案例的详细展示？我可以发更多作品给您参考。"""
    
    def _reply_timeline(self, intent_result: IntentResult) -> str:
        """回复周期咨询。"""
        service_type = self.context.get_slot("service_type", "具体服务")
        
        return f"""关于{service_type}的设计周期：

⏱️ **标准交付周期**
- Logo 设计：3-5 个工作日
- VI 设计：10-15 个工作日
- 包装设计：5-10 个工作日/款
- 海报设计：2-3 个工作日

🚀 **加急服务**
我们提供加急服务，最快可 24 小时内交付：
- 24 小时加急：+50% 加急费
- 48 小时加急：+30% 加急费
- 72 小时加急：+20% 加急费

请问您什么时候需要？我们可以根据您的时间安排。"""
    
    def _reply_company_info(self, intent_result: IntentResult) -> str:
        """回复公司信息咨询。"""
        return """关于我们：

🏢 **公司简介**
创意广告设计公司成立于 2010 年，是一家专注于品牌策略与创意设计的综合性广告公司。

📊 **公司规模**
- 50+ 专业设计师团队
- 服务 500+ 知名品牌客户
- 10+ 年行业经验

🏆 **荣誉资质**
- 中国广告协会理事单位
- 红点、iF 等国际设计大奖获得者
- 年度最佳设计机构

📍 **公司地址**
上海市静安区创意产业园 A 座 8 楼

📞 **联系方式**
- 电话：400-XXX-XXXX
- 邮箱：hello@creative-ad.com
- 微信：CreativeAdDesign

请问还有什么想了解的吗？"""
    
    def _reply_revision(self, intent_result: IntentResult) -> str:
        """回复修改请求。"""
        return """好的，我们支持设计修改服务。

📝 **修改流程**
1. 请具体描述需要修改的地方
2. 我们的设计师会进行评估
3. 确认修改方案
4. 进行修改设计
5. 提交修改稿给您确认

🔄 **修改政策**
- 初稿后包含 3 次免费修改
- 超出次数按 ¥500/次收费
- 重大方向调整可能产生额外费用

请告诉我您具体需要修改哪些地方？"""
    
    def _reply_urgent(self, intent_result: IntentResult) -> str:
        """回复紧急需求。"""
        return """理解您的需求很紧急！

🚨 **紧急需求处理流程**
1. 我们会优先安排设计师处理
2. 确认具体交付时间
3. 启动加急流程

⚡ **最快交付时间**
- 简单设计：2-4 小时
- 中等复杂：8-12 小时
- 复杂设计：24 小时

请告诉我：
1. 具体需要什么设计？
2. 最晚什么时候要？
3. 有什么特殊要求？

我们会全力配合您的时间安排！"""
    
    def _reply_follow_up(self, intent_result: IntentResult) -> str:
        """回复进度跟进。"""
        project_name = self.context.get_slot("project_name", "您的项目")
        
        return f"""关于{project_name}的进度查询：

📋 **查询方式**
请提供以下信息帮您查询：
1. 项目编号/合同号
2. 负责人姓名
3. 下单时留的联系方式

📱 **自助查询**
您也可以：
- 登录官网会员中心查看
- 关注官方微信公众号查询
- 联系您的专属客服经理

请问您能提供项目编号吗？"""
    
    def _reply_complaint(self, intent_result: IntentResult) -> str:
        """回复投诉。"""
        return """非常抱歉给您带来了不好的体验！

🙏 **我们非常重视您的反馈**

请您详细描述一下遇到的问题：
1. 具体是什么问题？
2. 发生在哪个环节？
3. 您期望如何解决？

我们会：
- 立即安排专人处理
- 2 小时内给您回复
- 给出满意的解决方案

您的满意是我们最大的追求！"""
    
    def _reply_praise(self, intent_result: IntentResult) -> str:
        """回复表扬。"""
        return """非常感谢您的认可和好评！😊

您的满意是我们最大的动力！我们会继续努力，为您提供更优质的服务。

如果您有朋友需要设计服务，也欢迎推荐给我们！

祝您工作顺利，生活愉快！"""
    
    def _reply_faq(self, intent_result: IntentResult) -> str:
        """回复常见问题。"""
        return """常见问题解答：

💳 **付款方式**
- 支持银行转账、支付宝、微信支付
- 50% 预付款，50% 尾款（交付前）

🧾 **发票事宜**
- 可开具增值税普通/专用发票
- 发票内容：设计服务费
- 尾款结清后开具

📄 **合同签署**
- 支持电子合同/纸质合同
- 合同盖章后生效
- 可提供合同模板预览

🔒 **版权说明**
- 尾款结清后版权归客户所有
- 设计源文件可另行购买
- 我方保留作品展示权

还有其他问题吗？"""
    
    def _reply_unknown(self, intent_result: IntentResult) -> str:
        """回复未知意图。"""
        return """抱歉，我还没有完全理解您的需求。

您可以问我：
- "你们提供哪些设计服务？"
- "Logo 设计多少钱？"
- "多久能做完？"
- "能看看你们的作品吗？"

或者直接描述您的需求，我会尽力帮您解答！"""
    
    def get_context(self) -> DialogueContext:
        """获取对话上下文。
        
        Returns:
            DialogueContext: 对话上下文。
        """
        return self.context
    
    def reset(self) -> None:
        """重置对话。"""
        self.context = DialogueContext()