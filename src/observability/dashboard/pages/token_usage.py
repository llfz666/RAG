"""
Token Usage Dashboard - Token 使用监控面板

Streamlit 页面，展示：
1. 实时用量统计
2. 预算状态
3. 模型用量排名
4. 用户用量排名
5. 最近使用记录
6. 告警历史
"""

import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.observability.token_monitor import (
    global_registry,
    TokenMonitorRegistry,
)
from src.observability.token_monitor.models import AlertType


def initialize_token_monitor():
    """初始化 Token Monitor"""
    if not global_registry._initialized:
        try:
            # 尝试主项目配置
            config_path = "config/settings.yaml"
            global_registry.initialize(config_path)
        except FileNotFoundError:
            # 尝试 smart-agent-hub 配置
            config_path = "smart-agent-hub/config/settings.yaml"
            global_registry.initialize(config_path)


def format_currency(value: float) -> str:
    """格式化货币显示"""
    return f"¥{value:.2f}"


def format_number(value: int) -> str:
    """格式化数字显示"""
    if value >= 1000000:
        return f"{value / 1000000:.1f}M"
    elif value >= 1000:
        return f"{value / 1000:.1f}K"
    return str(value)


def render_budget_gauge(status, budget_type: str):
    """渲染预算进度条"""
    if budget_type == "daily":
        current = status.today_cost
        total = status.daily_budget
        ratio = status.daily_usage_ratio
    else:
        current = status.month_cost
        total = status.monthly_budget
        ratio = status.monthly_usage_ratio
    
    # 颜色判断
    if ratio >= 1.0:
        color = "red"
        icon = "🚨"
    elif ratio >= 0.8:
        color = "orange"
        icon = "⚠️"
    elif ratio >= 0.5:
        color = "yellow"
        icon = "📊"
    else:
        color = "green"
        icon = "✅"
    
    # 进度条
    st.progress(min(ratio, 1.0))
    
    # 状态文本
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label=f"{budget_type.title()} Budget",
            value=format_currency(current),
            delta=f"{ratio*100:.1f}%",
            delta_color="inverse" if ratio > 0.8 else "normal"
        )
    with col2:
        st.metric(
            label="Remaining",
            value=format_currency(status.remaining_daily if budget_type == "daily" else status.remaining_monthly)
        )
    with col3:
        st.metric(
            label="Total Budget",
            value=format_currency(total)
        )
    
    # 状态消息
    if status.is_over_budget:
        st.error(f"{icon} 预算已用尽！")
    elif status.needs_warning:
        st.warning(f"{icon} 预算使用已达{ratio*100:.1f}%，请注意控制用量")
    else:
        st.success(f"{icon} 预算使用正常")


def render_model_breakdown(breakdowns):
    """渲染模型用量明细"""
    if not breakdowns:
        st.info("暂无数据")
        return
    
    # 创建表格
    data = []
    for item in breakdowns:
        data.append({
            "模型": item.model,
            "Token 消耗": format_number(item.total_tokens),
            "输入 Token": format_number(item.prompt_tokens),
            "输出 Token": format_number(item.completion_tokens),
            "成本": format_currency(item.total_cost),
            "调用次数": item.request_count,
        })
    
    st.dataframe(data, use_container_width=True, hide_index=True)


def render_user_breakdown(breakdowns):
    """渲染用户用量明细"""
    if not breakdowns:
        st.info("暂无数据")
        return
    
    data = []
    for item in breakdowns:
        data.append({
            "用户 ID": item.user_id,
            "Token 消耗": format_number(item.total_tokens),
            "成本": format_currency(item.total_cost),
            "调用次数": item.request_count,
            "最后活跃": item.last_activity.strftime("%Y-%m-%d %H:%M") if item.last_activity else "N/A",
        })
    
    st.dataframe(data, use_container_width=True, hide_index=True)


def render_recent_usage(records):
    """渲染最近使用记录"""
    if not records:
        st.info("暂无数据")
        return
    
    data = []
    for record in records[:20]:  # 只显示最近 20 条
        status_icon = "✅" if record.status.value == "success" else "❌"
        data.append({
            "时间": record.timestamp.strftime("%H:%M:%S"),
            "模型": record.model,
            "Token": f"{format_number(record.prompt_tokens)} → {format_number(record.completion_tokens)}",
            "成本": format_currency(record.cost),
            "状态": f"{status_icon} {record.status.value}",
            "任务类型": record.task_type or "-",
        })
    
    st.dataframe(data, use_container_width=True, hide_index=True)


def render_alerts(alerts):
    """渲染告警历史"""
    if not alerts:
        st.info("暂无告警")
        return
    
    for alert in alerts[:10]:  # 只显示最近 10 条
        if alert.alert_type == AlertType.BUDGET_EXCEEDED:
            icon = "🚨"
            color = "error"
        elif alert.alert_type == AlertType.BUDGET_WARNING:
            icon = "⚠️"
            color = "warning"
        else:
            icon = "📊"
            color = "info"
        
        with st.container():
            st.markdown(f"""
                <div style="padding: 10px; border-left: 4px solid {'red' if color == 'error' else 'orange' if color == 'warning' else 'blue'}; background-color: {'#ffe6e6' if color == 'error' else '#fff3e6' if color == 'warning' else '#e6f3ff'}; border-radius: 4px; margin-bottom: 10px;">
                    <strong>{icon} {alert.alert_type.value}</strong><br>
                    <small>{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</small><br>
                    {alert.message}
                </div>
            """, unsafe_allow_html=True)


def main():
    """主页面"""
    st.set_page_config(
        page_title="Token Usage Monitor",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Token Usage Monitor")
    st.markdown("---")
    
    # 初始化 Token Monitor
    try:
        initialize_token_monitor()
        tracker = global_registry.tracker
        budget_manager = global_registry.budget_manager
        config = global_registry.config
    except Exception as e:
        st.error(f"初始化 Token Monitor 失败：{e}")
        st.info("请确保已正确配置 config/settings.yaml 并调用 global_registry.initialize()")
        return
    
    # 侧边栏配置
    st.sidebar.header("⚙️ 设置")
    
    # 时间范围选择
    time_range = st.sidebar.selectbox(
        "时间范围",
        options=["今日", "最近 7 天", "最近 30 天"],
        index=1
    )
    days_map = {"今日": 1, "最近 7 天": 7, "最近 30 天": 30}
    days = days_map[time_range]
    
    # 用户筛选
    all_users = ["全部"] + [u.user_id for u in tracker.get_user_breakdown(days=days)]
    selected_user = st.sidebar.selectbox("用户", options=all_users)
    user_id = None if selected_user == "全部" else selected_user
    
    # 刷新按钮
    if st.sidebar.button("🔄 刷新数据"):
        st.rerun()
    
    # 获取数据
    stats = tracker.get_stats(days=days, user_id=user_id)
    budget_status = budget_manager.check_budget(user_id)
    model_breakdown = tracker.get_model_breakdown(days=days)
    user_breakdown = tracker.get_user_breakdown(days=days)
    recent_usage = tracker.get_recent_usage(limit=50)
    alerts = budget_manager.get_alerts(days=days)
    
    # 第一行：预算状态
    st.subheader("💰 预算状态")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 今日预算")
        render_budget_gauge(budget_status, "daily")
    
    with col2:
        st.markdown("#### 本月预算")
        render_budget_gauge(budget_status, "monthly")
    
    st.markdown("---")
    
    # 第二行：总体统计
    st.subheader("📈 总体统计")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总 Token 消耗", format_number(stats.total_tokens))
    with col2:
        st.metric("总调用次数", f"{stats.total_requests:,}")
    with col3:
        st.metric("总成本", format_currency(stats.total_cost))
    with col4:
        avg_cost = stats.total_cost / stats.total_requests if stats.total_requests > 0 else 0
        st.metric("平均调用成本", format_currency(avg_cost))
    
    st.markdown("---")
    
    # 第三行：模型和用户用量
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🤖 模型用量排名")
        render_model_breakdown(model_breakdown)
    
    with col2:
        st.subheader("👤 用户用量排名")
        render_user_breakdown(user_breakdown)
    
    st.markdown("---")
    
    # 第四行：最近使用和告警
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📝 最近使用记录")
        render_recent_usage(recent_usage)
    
    with col2:
        st.subheader("🚨 告警历史")
        render_alerts(alerts)
    
    # 底部：配置信息
    with st.expander("⚙️ 配置信息"):
        st.json({
            "enabled": config.enabled,
            "database_path": config.database_path,
            "log_file": config.log_file,
            "daily_budget": config.default_daily_budget,
            "monthly_budget": config.default_monthly_budget,
            "alert_threshold": config.alert_threshold,
            "sampling_enabled": config.sampling_enabled,
            "sampling_rate": config.sampling_rate,
        })


if __name__ == "__main__":
    main()