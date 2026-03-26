#!/usr/bin/env python3
"""广告公司客服模拟数据生成器。

生成用于训练和测试的客服对话数据，包括：
- FAQ 问答对
- 意图识别示例
- 多轮对话样本
"""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any


# ==================== 配置 ====================

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "customer_service"
NUM_FAQ = 50
NUM_INTENT_EXAMPLES = 200
NUM_DIALOGUES = 100


# ==================== FAQ 数据 ====================

FAQ_DATA = {
    "service_inquiry": [
        {"q": "你们公司提供哪些服务？", "a": "我们提供品牌设计（Logo、VI、SI）、包装设计、广告设计（海报、画册、易拉宝）、数字媒体设计（网页、UI、H5）以及视频动画制作等服务。"},
        {"q": "你们能做 Logo 设计吗？", "a": "当然可以！Logo 设计是我们的核心服务之一，我们有专业的设计团队为您打造独特的品牌形象。"},
        {"q": "VI 设计包括哪些内容？", "a": "VI 设计包括基础系统（Logo、标准字、标准色）和应用系统（名片、信纸、画册、包装等）的完整视觉规范。"},
        {"q": "你们做包装设计吗？", "a": "是的，我们提供产品包装设计、包装盒设计、标签设计等全套包装解决方案。"},
        {"q": "能做海报设计吗？", "a": "可以的，我们提供活动海报、宣传海报、促销海报等各类海报设计服务。"},
    ],
    "price_quote": [
        {"q": "Logo 设计多少钱？", "a": "Logo 设计价格根据设计复杂度和设计师级别，一般在¥2,000-¥20,000 之间。具体价格需要了解您的需求后报价。"},
        {"q": "VI 设计怎么收费？", "a": "VI 设计根据项目规模，基础版¥10,000 起，完整版¥30,000-¥50,000。我们会根据您的具体需求提供详细报价。"},
        {"q": "包装设计贵吗？", "a": "包装设计按款收费，单款设计¥3,000-¥15,000 不等。多款设计有优惠，具体请咨询客服。"},
        {"q": "有优惠吗？", "a": "我们为新客户提供首次合作 9 折优惠，多款设计打包也有优惠。具体优惠方案请咨询客服。"},
        {"q": "付款方式是什么？", "a": "我们支持 50% 预付款 +50% 尾款的付款方式，支持银行转账、支付宝、微信支付。"},
    ],
    "timeline": [
        {"q": "Logo 设计需要多久？", "a": "Logo 设计标准周期是 3-5 个工作日，我们提供加急服务，最快 24 小时可交付。"},
        {"q": "你们最快多久能做完？", "a": "根据设计类型，最快 24 小时可交付简单设计。加急服务会收取相应加急费。"},
        {"q": "VI 设计周期是多久？", "a": "VI 设计标准周期是 10-15 个工作日，具体根据项目规模和复杂程度确定。"},
        {"q": "加急怎么收费？", "a": "24 小时加急 +50%，48 小时加急 +30%，72 小时加急 +20% 的设计费。"},
        {"q": "周末上班吗？", "a": "我们工作日正常上班，周末可安排加班处理加急项目，需提前预约。"},
    ],
    "revision": [
        {"q": "设计不满意可以改吗？", "a": "可以的，我们提供 3 次免费修改服务。超出次数按¥500/次收费。"},
        {"q": "修改要收费吗？", "a": "3 次以内免费修改，超出次数按¥500/次收费。重大方向调整可能产生额外费用。"},
        {"q": "可以重新设计吗？", "a": "如初稿完全不符合需求，我们可以安排重新设计，具体方案请与客服沟通。"},
        {"q": "修改需要多久？", "a": "小修改 1-2 个工作日，大修改 3-5 个工作日。加急修改可安排优先处理。"},
        {"q": "能换设计师吗？", "a": "如对设计方案不满意，可以安排更换设计师，请与客服沟通您的需求。"},
    ],
    "company_info": [
        {"q": "你们公司在哪里？", "a": "公司位于上海市静安区创意产业园 A 座 8 楼，欢迎来访参观。"},
        {"q": "公司成立多久了？", "a": "公司成立于 2010 年，已有 10 多年广告设计行业经验。"},
        {"q": "怎么联系你们？", "a": "电话：400-XXX-XXXX，邮箱：hello@creative-ad.com，微信：CreativeAdDesign"},
        {"q": "你们团队有多少人？", "a": "我们有 50+ 专业设计师团队，包括资深设计师、美术指导、创意总监等。"},
        {"q": "有成功案例吗？", "a": "我们服务过 500+ 知名品牌客户，涵盖科技、金融、快消、医疗等多个行业。"},
    ],
    "payment": [
        {"q": "可以开发票吗？", "a": "可以开具增值税普通发票或专用发票，发票内容为设计服务费。"},
        {"q": "支持分期吗？", "a": "大金额项目支持分期付款，具体方案根据项目金额和周期协商确定。"},
        {"q": "尾款什么时候付？", "a": "尾款在设计完成后、交付源文件前支付。"},
        {"q": "退款政策是什么？", "a": "项目启动后预付款不予退还。如对设计不满意，可协商更换设计师或调整方案。"},
        {"q": "合同怎么签？", "a": "支持电子合同或纸质合同，合同盖章后生效。我们提供标准合同模板。"},
    ],
}


# ==================== 意图识别示例 ====================

INTENT_EXAMPLES = {
    "greeting": [
        "你好", "您好", "早上好", "下午好", "晚上好",
        "嗨喽", "哈喽", "hello", "hi", "在吗",
        "有人吗", "客服在吗", "请问有人在吗", "你好呀",
    ],
    "farewell": [
        "再见", "拜拜", "下次聊", "先这样", "那先挂了",
        "不打扰了", "我去忙了", "回聊", "改天再聊", "bye",
    ],
    "service_inquiry": [
        "你们提供什么服务", "你们公司是做什么的", "有什么业务",
        "能做 Logo 设计吗", "可以设计包装吗", "你们做 VI 吗",
        "海报设计能做吗", "网页设计有吗", "UI 设计服务",
        "视频动画可以做吗", "宣传册设计", "画册设计",
    ],
    "price_quote": [
        "多少钱", "怎么收费", "价格多少", "报价",
        "Logo 设计贵吗", "做个 VI 要多少钱", "包装设计费用",
        "预算大概多少", "有优惠吗", "便宜点",
        "太贵了", "能打折吗", "付款方式",
    ],
    "case_portfolio": [
        "看看你们的作品", "有案例吗", "之前的作品",
        "成功案例", "设计案例", "作品参考",
        "看看你们做得怎么样", "有没有类似的案例", "展示一下作品",
    ],
    "timeline": [
        "多久能做完", "设计周期", "什么时候能好",
        "来得及吗", "时间够吗", "最快多久",
        "今天能好吗", "明天能交稿吗", "加急",
        "很急", "赶时间", "时间紧",
    ],
    "revision": [
        "不满意", "要修改", "改一下",
        "这个不行", "重新设计", "换个设计师",
        "调整一下", "颜色改改", "字体换换",
        "再改改", "还是不满意", "设计太丑",
    ],
    "urgent": [
        "很急", "急用", "今天必须",
        "明天要", "快点", "赶紧",
        "马上要", "在线等", "十万火急",
        "加急", "优先处理", "插个队",
    ],
    "follow_up": [
        "进度怎么样了", "做完没有", "进行到哪一步了",
        "什么时候能好", "催一下", "怎么还没好",
        "项目进度", "查询进度", "跟进一下",
    ],
    "complaint": [
        "太差了", "不满意", "投诉",
        "什么破设计", "太慢了", "态度不好",
        "要退款", "垃圾", "骗子",
        "失望", "生气", "无法接受",
    ],
    "handoff": [
        "转人工", "找客服", "要真人",
        "和人说", "不要机器人", "人工服务",
        "电话多少", "联系方式", "找你们经理",
    ],
    "confirm": [
        "好的", "可以", "没问题",
        "对的", "是的", "确认",
        "就这样", "同意", "ok",
    ],
    "cancel": [
        "不要了", "取消", "算了",
        "不做了", "退款", "撤销",
        "暂停", "先不做", "改天吧",
    ],
    "faq": [
        "怎么付款", "能开发票吗", "合同怎么签",
        "有售后吗", "保修多久", "版权怎么算",
        "源文件给吗", "修改收费吗", "多久回复",
    ],
}


# ==================== 多轮对话样本 ====================

DIALOGUE_TEMPLATES = [
    # 服务咨询场景
    {
        "scenario": "service_inquiry",
        "turns": [
            {"user": "你好", "system": "您好！欢迎咨询创意广告设计公司，我是您的智能助手。请问有什么可以帮您？"},
            {"user": "你们公司提供哪些设计服务？", "system": "我们提供品牌设计（Logo、VI、SI）、包装设计、广告设计、数字媒体设计以及视频动画制作等服务。请问您对哪类服务感兴趣？"},
            {"user": "Logo 设计", "system": "好的，Logo 设计是我们的核心服务。我们有专业的设计团队为您打造独特的品牌形象。请问您是什么行业的？"},
            {"user": "科技公司", "system": "明白了，科技公司的 Logo 设计我们很有经验。请问您有什么风格偏好吗？比如简约、现代、科技感等。"},
            {"user": "简约现代一点", "system": "好的，简约现代风格很适合科技公司。我们会为您设计简洁、有辨识度的 Logo。您还有其他要求吗？"},
        ],
    },
    # 报价咨询场景
    {
        "scenario": "price_quote",
        "turns": [
            {"user": "你好", "system": "您好！欢迎咨询创意广告设计公司，我是您的智能助手。请问有什么可以帮您？"},
            {"user": "做个 Logo 多少钱？", "system": "Logo 设计价格根据设计复杂度和设计师级别，一般在¥2,000-¥20,000 之间。请问您有什么具体需求吗？"},
            {"user": "简单一点的", "system": "简单款式的 Logo 设计大概在¥2,000-¥5,000 左右。请问您是什么行业的？"},
            {"user": "餐饮", "system": "好的，餐饮行业的 Logo 设计我们很有经验。请问您需要包含哪些元素？比如餐具、食物、文字等。"},
            {"user": "就文字加个图标", "system": "明白了，文字 + 图标的组合 Logo。我们会根据您的品牌名称和定位设计合适的方案。您什么时候需要？"},
        ],
    },
    # 紧急需求场景
    {
        "scenario": "urgent",
        "turns": [
            {"user": "在吗，很急", "system": "您好！我在的，请问有什么紧急需求？我会优先帮您处理。"},
            {"user": "明天要一个海报", "system": "理解您的需求很紧急！明天交付的话我们需要启动加急流程。请问海报的尺寸和内容要求是什么？"},
            {"user": "活动宣传海报，A1 尺寸", "system": "好的，A1 尺寸的活动海报。请问活动的主题、时间、地点等信息能提供吗？"},
            {"user": "主题是新品发布会，时间是下周五", "system": "明白了。我们会安排设计师优先处理您的需求。加急服务会收取 50% 加急费，您可以接受吗？"},
            {"user": "可以", "system": "好的，已为您安排加急。设计师会在今天下午开始设计，明天可以交付初稿。"},
        ],
    },
    # 投诉处理场景
    {
        "scenario": "complaint",
        "turns": [
            {"user": "你们设计的是什么啊，太丑了", "system": "非常抱歉给您带来了不好的体验！您的反馈我们非常重视。请问具体是哪些方面不满意呢？"},
            {"user": "颜色太难看了", "system": "我理解您的失望。颜色确实对设计效果影响很大。请问您偏好什么色系？我们马上安排调整。"},
            {"user": "蓝色系，但是要清新一点", "system": "好的，清新蓝色系。我记下了您的要求，马上安排设计师重新调整配色方案。"},
            {"user": "多久能改好", "system": "颜色调整大概需要 1-2 小时。改好后会第一时间发给您确认。非常抱歉给您带来困扰。"},
        ],
    },
    # 进度查询场景
    {
        "scenario": "follow_up",
        "turns": [
            {"user": "你好", "system": "您好！欢迎咨询创意广告设计公司，我是您的智能助手。请问有什么可以帮您？"},
            {"user": "我的项目进度怎么样了", "system": "您好，请问您能提供项目编号或下单时留的联系方式吗？我帮您查询。"},
            {"user": "手机号 138xxxx1234", "system": "好的，请稍等...查到您的项目是 VI 设计，目前正在进行基础系统设计阶段。"},
            {"user": "什么时候能好", "system": "根据您的项目计划，预计后天可以完成初稿。我们会按时交付。"},
            {"user": "好的谢谢", "system": "不客气！如有其他问题随时联系我们。祝您工作顺利！"},
        ],
    },
]


# ==================== 数据生成函数 ====================

def generate_faq_data() -> list[dict[str, Any]]:
    """生成 FAQ 数据。"""
    faq_list = []
    
    for category, examples in FAQ_DATA.items():
        for item in examples:
            faq_list.append({
                "category": category,
                "question": item["q"],
                "answer": item["a"],
                "keywords": extract_keywords(item["q"]),
            })
    
    # 添加额外变体
    additional_faqs = []
    for faq in faq_list[:20]:
        variant = {
            "category": faq["category"],
            "question": generate_question_variant(faq["question"]),
            "answer": faq["answer"],
            "keywords": extract_keywords(faq["question"]),
        }
        additional_faqs.append(variant)
    
    return faq_list + additional_faqs


def generate_question_variant(question: str) -> str:
    """生成问题变体。"""
    variants = [
        f"请问{question}",
        f"{question}？",
        f"我想问{question}",
        f"能不能{question}",
        f"{question}呢",
    ]
    return random.choice(variants)


def extract_keywords(question: str) -> list[str]:
    """提取问题关键词。"""
    # 简单分词
    words = []
    keywords_map = {
        "多少钱": ["价格", "费用", "报价"],
        "多久": ["时间", "周期", "工期"],
        "服务": ["业务", "产品", "设计"],
        "Logo": ["logo", "LOGO", "标志"],
        "VI": ["vi", "视觉", "形象"],
        "包装": ["盒子", "外盒", "标签"],
        "修改": ["调整", "改动", "重做"],
        "加急": ["急", "快点", "赶紧"],
    }
    
    for kw, synonyms in keywords_map.items():
        if kw in question or any(s in question for s in synonyms):
            words.append(kw)
    
    return words if words else ["咨询"]


def generate_intent_examples() -> list[dict[str, Any]]:
    """生成意图识别示例数据。"""
    examples = []
    
    for intent, utterances in INTENT_EXAMPLES.items():
        for utterance in utterances:
            examples.append({
                "text": utterance,
                "intent": intent,
                "confidence": 1.0,
            })
            
            # 添加变体
            for _ in range(2):
                variant = add_noise(utterance)
                examples.append({
                    "text": variant,
                    "intent": intent,
                    "confidence": 0.9,
                })
    
    return examples


def add_noise(text: str) -> str:
    """添加噪声（拼写错误、语气词等）。"""
    noise_map = {
        "吗": "嘛",
        "呢": "呐",
        "啊": "呀",
        "的": "滴",
        "是": "系",
        "什么": "啥",
        "怎么": "咋",
    }
    
    result = text
    for original, noise in noise_map.items():
        if original in result and random.random() < 0.3:
            result = result.replace(original, noise, 1)
            break
    
    # 添加语气词
    if random.random() < 0.2:
        particles = ["啊", "呢", "嘛", "呀", "哦"]
        result = result + random.choice(particles)
    
    return result


def generate_dialogues() -> list[dict[str, Any]]:
    """生成多轮对话数据。"""
    dialogues = []
    
    for template in DIALOGUE_TEMPLATES:
        dialogue = {
            "scenario": template["scenario"],
            "turns": template["turns"],
            "metadata": {
                "total_turns": len(template["turns"]),
                "created_at": datetime.now().isoformat(),
            },
        }
        dialogues.append(dialogue)
    
    # 生成更多对话变体
    for _ in range(NUM_DIALOGUES - len(DIALOGUE_TEMPLATES)):
        dialogue = generate_random_dialogue()
        dialogues.append(dialogue)
    
    return dialogues


def generate_random_dialogue() -> dict[str, Any]:
    """生成随机对话。"""
    scenarios = list(INTENT_EXAMPLES.keys())
    scenario = random.choice(scenarios)
    
    turns = []
    # 开场
    turns.append({
        "user": random.choice(INTENT_EXAMPLES["greeting"]),
        "system": "您好！欢迎咨询创意广告设计公司，我是您的智能助手。请问有什么可以帮您？",
    })
    
    # 主意图
    intent_utterance = random.choice(INTENT_EXAMPLES[scenario])
    turns.append({
        "user": intent_utterance,
        "system": generate_system_response(scenario, intent_utterance),
    })
    
    # 后续对话
    for _ in range(random.randint(1, 3)):
        turns.append({
            "user": generate_follow_up(scenario),
            "system": generate_system_response(scenario, ""),
        })
    
    # 结束
    turns.append({
        "user": random.choice(INTENT_EXAMPLES["farewell"]),
        "system": "感谢您的咨询，祝您生活愉快！如有其他问题随时联系我们。",
    })
    
    return {
        "scenario": scenario,
        "turns": turns,
        "metadata": {
            "total_turns": len(turns),
            "created_at": datetime.now().isoformat(),
        },
    }


def generate_system_response(scenario: str, user_input: str) -> str:
    """生成系统回复。"""
    responses = {
        "service_inquiry": "我们提供品牌设计、包装设计、广告设计等服务。请问您对哪类感兴趣？",
        "price_quote": "价格根据设计复杂度和需求有所不同。请问您具体需要什么服务？",
        "timeline": "标准周期根据设计类型不同，一般 3-15 个工作日。请问您什么时候需要？",
        "case_portfolio": "我们有很多成功案例。请问您想看哪类案例？",
        "revision": "我们提供 3 次免费修改服务。请问具体需要修改哪里？",
        "urgent": "理解您的需求很紧急！我们会优先处理。请问具体要求是什么？",
        "follow_up": "您好，请问您能提供项目编号或联系方式吗？我帮您查询。",
        "complaint": "非常抱歉给您带来不好的体验！请问具体是什么问题？",
        "handoff": "好的，正在为您转接人工客服，请稍候。",
        "confirm": "好的，已确认您的需求。",
        "cancel": "好的，已为您取消。如有需要随时联系我们。",
        "faq": "请问您具体想了解什么？",
        "greeting": "您好！有什么可以帮您？",
        "farewell": "感谢您的咨询，祝您生活愉快！",
    }
    
    return responses.get(scenario, "好的，我明白了。")


def generate_follow_up(scenario: str) -> str:
    """生成后续对话。"""
    follow_ups = {
        "service_inquiry": ["Logo 设计多少钱", "多久能做完", "有案例吗"],
        "price_quote": ["便宜点", "包含几次修改", "付款方式"],
        "timeline": ["加急怎么收费", "今天能好吗", "周末上班吗"],
        "case_portfolio": ["看看科技行业的", "有类似的吗", "发我邮箱"],
        "revision": ["修改要钱吗", "多久能改好", "能换设计师吗"],
        "urgent": ["最快多久", "今天能好吗", "多少钱"],
        "follow_up": ["项目号 xxx", "手机号 138xxxx", "什么时候好"],
        "complaint": ["颜色太丑", "设计不行", "要退款"],
    }
    
    return random.choice(follow_ups.get(scenario, ["好的", "明白了", "谢谢"]))


# ==================== 主函数 ====================

def main():
    """主函数。"""
    print("开始生成客服模拟数据...")
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 生成 FAQ 数据
    print(f"生成 {NUM_FAQ}+ FAQ 问答对...")
    faq_data = generate_faq_data()
    
    # 生成意图示例数据
    print(f"生成 {NUM_INTENT_EXAMPLES}+ 意图识别示例...")
    intent_data = generate_intent_examples()
    
    # 生成对话数据
    print(f"生成 {NUM_DIALOGUES}+ 多轮对话样本...")
    dialogue_data = generate_dialogues()
    
    # 保存数据
    faq_file = OUTPUT_DIR / "faq.json"
    intent_file = OUTPUT_DIR / "intent_examples.json"
    dialogue_file = OUTPUT_DIR / "dialogue_samples.json"
    
    with open(faq_file, "w", encoding="utf-8") as f:
        json.dump(faq_data, f, ensure_ascii=False, indent=2)
    print(f"已保存 FAQ 数据到：{faq_file}")
    
    with open(intent_file, "w", encoding="utf-8") as f:
        json.dump(intent_data, f, ensure_ascii=False, indent=2)
    print(f"已保存意图示例数据到：{intent_file}")
    
    with open(dialogue_file, "w", encoding="utf-8") as f:
        json.dump(dialogue_data, f, ensure_ascii=False, indent=2)
    print(f"已保存对话数据到：{dialogue_file}")
    
    # 生成统计信息
    stats = {
        "faq_count": len(faq_data),
        "intent_examples_count": len(intent_data),
        "dialogues_count": len(dialogue_data),
        "intents": list(INTENT_EXAMPLES.keys()),
        "categories": list(FAQ_DATA.keys()),
        "generated_at": datetime.now().isoformat(),
    }
    
    stats_file = OUTPUT_DIR / "data_stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"已保存统计信息到：{stats_file}")
    
    print("\n数据生成完成！")
    print(f"  - FAQ 问答对：{len(faq_data)} 条")
    print(f"  - 意图示例：{len(intent_data)} 条")
    print(f"  - 多轮对话：{len(dialogue_data)} 条")


if __name__ == "__main__":
    main()