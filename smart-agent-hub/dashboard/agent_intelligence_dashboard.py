"""Agent Intelligence Evaluation Dashboard.

This dashboard provides metrics to evaluate and track agent intelligence improvements:
1. Task Efficiency Metrics - Steps, retries, tool selection accuracy
2. Memory Quality Metrics - Entries, importance distribution, reuse rate
3. Answer Quality Metrics - Success rate, context utilization
4. Historical Comparison - Day-over-day improvements

Usage:
    streamlit run dashboard/agent_intelligence_dashboard.py

Requirements:
    pip install streamlit pandas plotly
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st

# ============================================================================
# Configuration
# ============================================================================

DB_PATH = "data/db/agent_sessions.db"
LOG_PATH = "data/logs/agent_traces.jsonl"
MEMORY_PATH = "data/db/long_term_memory.jsonl"

st.set_page_config(
    page_title="Agent Intelligence Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# Data Loading Functions
# ============================================================================


@st.cache_data(ttl=60)
def load_agent_traces(log_path: str) -> list[dict]:
    """Load agent traces from JSONL file."""
    path = Path(log_path)
    if not path.exists():
        return []
    
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                events.append(event)
            except json.JSONDecodeError:
                continue
    
    return events


@st.cache_data(ttl=60)
def load_memories(memory_path: str) -> pd.DataFrame:
    """Load memories from JSONL file."""
    path = Path(memory_path)
    if not path.exists():
        return pd.DataFrame()
    
    memories = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                memories.append(data)
            except json.JSONDecodeError:
                continue
    
    return pd.DataFrame(memories)


def parse_traces_to_tasks(traces: list[dict]) -> pd.DataFrame:
    """Parse agent traces into task-level metrics."""
    tasks = {}
    
    for event in traces:
        event_type = event.get("type")
        session_id = event.get("session_id")
        task_id = event.get("task_id")
        timestamp = event.get("timestamp", "")
        
        if not task_id:
            continue
        
        if task_id not in tasks:
            tasks[task_id] = {
                "task_id": task_id,
                "session_id": session_id,
                "query": "",
                "start_time": timestamp,
                "end_time": "",
                "thought_count": 0,
                "action_count": 0,
                "observation_count": 0,
                "error_count": 0,
                "has_final_answer": False,
                "final_answer": "",
                "tools_used": [],
                "success": False,
            }
        
        task = tasks[task_id]
        
        if event_type == "task_start":
            task["query"] = event.get("query", "")
            task["start_time"] = timestamp
        
        elif event_type == "thought":
            task["thought_count"] += 1
        
        elif event_type == "action":
            task["action_count"] += 1
            tool = event.get("tool")
            if tool and tool not in task["tools_used"]:
                task["tools_used"].append(tool)
        
        elif event_type == "observation":
            task["observation_count"] += 1
            if event.get("error"):
                task["error_count"] += 1
        
        elif event_type == "final_answer":
            task["has_final_answer"] = True
            task["final_answer"] = event.get("content", "")
            task["end_time"] = timestamp
            task["success"] = event.get("success", False)
    
    # Calculate metrics
    for task in tasks.values():
        task["total_steps"] = task["thought_count"] + task["action_count"]
        task["tool_count"] = len(task["tools_used"])
        
        # Calculate duration
        try:
            start = datetime.fromisoformat(task["start_time"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(task["end_time"].replace("Z", "+00:00"))
            task["duration_ms"] = (end - start).total_seconds() * 1000
        except:
            task["duration_ms"] = 0
    
    return pd.DataFrame(tasks.values())


def calculate_daily_metrics(traces: list[dict]) -> pd.DataFrame:
    """Calculate daily aggregated metrics."""
    tasks_df = parse_traces_to_tasks(traces)
    
    if tasks_df.empty:
        return pd.DataFrame()
    
    # Parse dates
    tasks_df["date"] = pd.to_datetime(tasks_df["start_time"]).dt.date
    
    # Group by date
    daily = tasks_df.groupby("date").agg({
        "task_id": "count",
        "thought_count": "mean",
        "action_count": "mean",
        "total_steps": "mean",
        "error_count": "sum",
        "success": "mean",
        "has_final_answer": "mean",
        "duration_ms": "mean",
    }).reset_index()
    
    daily.columns = [
        "date", "tasks_completed", "avg_thoughts", "avg_actions",
        "avg_steps", "total_errors", "success_rate",
        "final_answer_rate", "avg_duration_ms"
    ]
    
    return daily.sort_values("date")


def calculate_intelligence_score(
    avg_steps: float,
    success_rate: float,
    error_rate: float,
    memory_reuse: float,
    avg_importance: float,
) -> float:
    """Calculate overall intelligence score (0-100).
    
    Scoring formula:
    - Efficiency (30%): Fewer steps = higher score
    - Success Rate (30%): Higher success = higher score
    - Error Handling (15%): Fewer errors = higher score
    - Memory Reuse (15%): More reuse = higher score
    - Memory Quality (10%): Higher importance = higher score
    """
    # Efficiency score (inverse of steps, normalized)
    efficiency = max(0, min(100, (10 - avg_steps) * 10)) if avg_steps > 0 else 50
    
    # Success score
    success_score = success_rate * 100
    
    # Error handling score
    error_score = max(0, 100 - error_rate * 20)
    
    # Memory reuse score
    memory_reuse_score = min(100, memory_reuse * 20)
    
    # Memory quality score
    memory_quality_score = avg_importance * 100
    
    # Weighted average
    total_score = (
        efficiency * 0.30 +
        success_score * 0.30 +
        error_score * 0.15 +
        memory_reuse_score * 0.15 +
        memory_quality_score * 0.10
    )
    
    return round(total_score, 1)


# ============================================================================
# Analysis Functions
# ============================================================================


def analyze_task_efficiency(tasks_df: pd.DataFrame) -> dict[str, Any]:
    """Analyze task execution efficiency."""
    if tasks_df.empty:
        return {}
    
    return {
        "total_tasks": len(tasks_df),
        "avg_steps": tasks_df["total_steps"].mean(),
        "avg_thoughts": tasks_df["thought_count"].mean(),
        "avg_actions": tasks_df["action_count"].mean(),
        "avg_duration_ms": tasks_df["duration_ms"].mean(),
        "success_rate": tasks_df["success"].mean(),
        "final_answer_rate": tasks_df["has_final_answer"].mean(),
        "total_errors": tasks_df["error_count"].sum(),
        "error_rate": tasks_df["error_count"].mean(),
    }


def analyze_memory_quality(memories_df: pd.DataFrame) -> dict[str, Any]:
    """Analyze long-term memory quality."""
    if memories_df.empty:
        return {
            "total_memories": 0,
            "avg_importance": 0,
            "high_importance_count": 0,
            "total_accesses": 0,
            "avg_accesses": 0,
            "by_type": {},
        }
    
    by_type = memories_df.groupby("entry_type").size().to_dict() if "entry_type" in memories_df.columns else {}
    
    return {
        "total_memories": len(memories_df),
        "avg_importance": memories_df["importance"].mean() if "importance" in memories_df.columns else 0,
        "high_importance_count": len(memories_df[memories_df.get("importance", pd.Series([0])) > 0.7]),
        "total_accesses": memories_df["access_count"].sum() if "access_count" in memories_df.columns else 0,
        "avg_accesses": memories_df["access_count"].mean() if "access_count" in memories_df.columns else 0,
        "by_type": by_type,
    }


def compare_periods(
    today_metrics: dict,
    yesterday_metrics: dict,
) -> dict[str, Any]:
    """Compare today's metrics with yesterday's."""
    comparison = {}
    
    metrics_to_compare = [
        ("avg_steps", "↓", "lower"),
        ("success_rate", "↑", "higher"),
        ("error_rate", "↓", "lower"),
        ("avg_duration_ms", "↓", "lower"),
    ]
    
    for metric, better_icon, direction in metrics_to_compare:
        today_val = today_metrics.get(metric, 0)
        yesterday_val = yesterday_metrics.get(metric, 0)
        
        if yesterday_val == 0:
            change_pct = 0
            improved = True
        else:
            change_pct = ((today_val - yesterday_val) / yesterday_val) * 100
            if direction == "lower":
                improved = today_val < yesterday_val
            else:
                improved = today_val > yesterday_val
        
        comparison[metric] = {
            "today": today_val,
            "yesterday": yesterday_val,
            "change_pct": change_pct,
            "improved": improved,
            "icon": "✅" if improved else "📉",
        }
    
    return comparison


# ============================================================================
# UI Components
# ============================================================================


def render_intelligence_score_card(score: float, yesterday_score: Optional[float] = None) -> None:
    """Render the main intelligence score card."""
    st.markdown("### 🧠 Agent Intelligence Score")
    
    # Score gauge using progress bar
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.progress(min(score / 100, 1.0))
    
    with col2:
        if yesterday_score:
            change = score - yesterday_score
            change_icon = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            st.metric("Score", f"{score:.1f}", f"{change_icon} {change:+.1f}")
        else:
            st.metric("Score", f"{score:.1f}")
    
    # Score interpretation
    if score >= 80:
        st.success("🌟 Excellent! Agent is performing at peak intelligence.")
    elif score >= 60:
        st.info("👍 Good performance. Room for minor improvements.")
    elif score >= 40:
        st.warning("⚠️ Moderate performance. Consider reviewing efficiency metrics.")
    else:
        st.error("🔴 Low score. Agent needs optimization.")


def render_metric_cards(metrics: dict[str, Any], prefix: str = "") -> None:
    """Render a row of metric cards."""
    cols = st.columns(5)
    
    metric_configs = [
        ("avg_steps", "Avg Steps", "👣", True),  # lower is better
        ("success_rate", "Success Rate", "✅", False),
        ("error_rate", "Error Rate", "❌", True),
        ("avg_duration_ms", "Avg Duration", "⏱️", True),
        ("final_answer_rate", "Answer Rate", "💬", False),
    ]
    
    for i, (key, label, icon, lower_better) in enumerate(metric_configs):
        if key in metrics:
            value = metrics[key]
            if key in ["success_rate", "final_answer_rate"]:
                display_value = f"{value:.1%}"
            elif key == "avg_duration_ms":
                display_value = f"{value/1000:.2f}s"
            else:
                display_value = f"{value:.2f}"
            
            cols[i].metric(f"{prefix}{label}", display_value, icon)


def render_daily_trend_chart(daily_df: pd.DataFrame) -> None:
    """Render daily trend chart for key metrics."""
    if daily_df.empty:
        st.info("No daily data available for trend analysis.")
        return
    
    st.markdown("### 📈 Daily Trends")
    
    # Create tabs for different metrics
    tab1, tab2, tab3 = st.tabs(["Efficiency", "Quality", "Errors"])
    
    with tab1:
        st.markdown("**Average Steps per Task** (lower is better)")
        st.line_chart(daily_df.set_index("date")[["avg_steps"]])
        
        st.markdown("**Average Duration** (seconds)")
        daily_df["avg_duration_s"] = daily_df["avg_duration_ms"] / 1000
        st.line_chart(daily_df.set_index("date")[["avg_duration_s"]])
    
    with tab2:
        st.markdown("**Success Rate** (higher is better)")
        st.line_chart(daily_df.set_index("date")[["success_rate"]])
        
        st.markdown("**Final Answer Rate**")
        st.line_chart(daily_df.set_index("date")[["final_answer_rate"]])
    
    with tab3:
        st.markdown("**Error Count** (lower is better)")
        st.bar_chart(daily_df.set_index("date")[["total_errors"]])


def render_memory_analysis(memories_df: pd.DataFrame) -> None:
    """Render memory quality analysis."""
    st.markdown("### 🧠 Memory Quality Analysis")
    
    if memories_df.empty:
        st.info("No memories stored yet.")
        return
    
    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    
    total = len(memories_df)
    avg_importance = memories_df["importance"].mean() if "importance" in memories_df.columns else 0
    high_importance = len(memories_df[memories_df.get("importance", pd.Series([0])) > 0.7])
    total_accesses = memories_df["access_count"].sum() if "access_count" in memories_df.columns else 0
    
    col1.metric("Total Memories", total)
    col2.metric("Avg Importance", f"{avg_importance:.2f}")
    col3.metric("High Importance (>0.7)", high_importance)
    col4.metric("Total Accesses", total_accesses)
    
    st.markdown("---")
    
    # Importance distribution
    st.markdown("**Importance Distribution**")
    if "importance" in memories_df.columns:
        importance_bins = pd.cut(memories_df["importance"], bins=[0, 0.3, 0.5, 0.7, 1.0], labels=["0-0.3", "0.3-0.5", "0.5-0.7", "0.7-1.0"])
        importance_dist = importance_bins.value_counts()
        st.bar_chart(importance_dist)
    
    # Memory type distribution
    if "entry_type" in memories_df.columns:
        st.markdown("**Memory Type Distribution**")
        type_dist = memories_df["entry_type"].value_counts()
        st.bar_chart(type_dist)
    
    # Recent memories table
    st.markdown("**Recent High-Value Memories**")
    high_value = memories_df[memories_df.get("importance", pd.Series([0])) > 0.7].head(10)
    if not high_value.empty:
        display_cols = ["content", "importance", "access_count", "entry_type"]
        available_cols = [c for c in display_cols if c in high_value.columns]
        st.dataframe(high_value[available_cols], use_container_width=True)
    else:
        st.info("No high-importance memories yet.")


def render_task_efficiency_analysis(tasks_df: pd.DataFrame) -> None:
    """Render task efficiency analysis."""
    st.markdown("### ⚡ Task Efficiency Analysis")
    
    if tasks_df.empty:
        st.info("No task data available.")
        return
    
    # Steps distribution
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Steps Distribution**")
        st.bar_chart(tasks_df["total_steps"].value_counts().sort_index())
    
    with col2:
        st.markdown("**Success vs Failed Tasks**")
        success_counts = tasks_df["success"].value_counts()
        st.bar_chart(success_counts)
    
    # Tool usage analysis
    st.markdown("**Tool Usage Frequency**")
    all_tools = []
    for tools in tasks_df["tools_used"]:
        all_tools.extend(tools)
    if all_tools:
        tool_counts = pd.Series(all_tools).value_counts()
        st.bar_chart(tool_counts)
    
    # Recent tasks table
    st.markdown("**Recent Tasks**")
    display_df = tasks_df.sort_values("start_time", ascending=False).head(20)
    display_cols = ["task_id", "query", "total_steps", "success", "duration_ms"]
    available_cols = [c for c in display_cols if c in display_df.columns]
    
    # Format for display
    display_df["duration_s"] = display_df["duration_ms"] / 1000
    display_df["success_icon"] = display_df["success"].apply(lambda x: "✅" if x else "❌")
    
    st.dataframe(
        display_df[["task_id", "query", "total_steps", "success_icon", "duration_s"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "task_id": "Task ID",
            "query": "Query",
            "total_steps": "Steps",
            "success_icon": "Status",
            "duration_s": st.column_config.NumberColumn("Duration (s)", format="%.2f"),
        }
    )


# ============================================================================
# Main Application
# ============================================================================


def main():
    """Main dashboard application."""
    
    st.title("🧠 Agent Intelligence Evaluation Dashboard")
    st.markdown("""
    Track and compare your agent's intelligence metrics over time.
    This dashboard helps quantify improvements in task efficiency, memory quality, and answer accuracy.
    """)
    
    # Load data
    traces = load_agent_traces(LOG_PATH)
    memories_df = load_memories(MEMORY_PATH)
    
    if not traces:
        st.warning("No agent traces found. Run some tasks first!")
        return
    
    # Parse traces to tasks
    tasks_df = parse_traces_to_tasks(traces)
    daily_df = calculate_daily_metrics(traces)
    
    # Calculate overall metrics
    efficiency_metrics = analyze_task_efficiency(tasks_df)
    memory_metrics = analyze_memory_quality(memories_df)
    
    # Calculate intelligence score
    intelligence_score = calculate_intelligence_score(
        avg_steps=efficiency_metrics.get("avg_steps", 5),
        success_rate=efficiency_metrics.get("success_rate", 0.5),
        error_rate=efficiency_metrics.get("error_rate", 0.1),
        memory_reuse=memory_metrics.get("avg_accesses", 0),
        avg_importance=memory_metrics.get("avg_importance", 0.5),
    )
    
    # Calculate yesterday's score for comparison
    yesterday_score = None
    if not daily_df.empty and len(daily_df) > 1:
        yesterday_row = daily_df.iloc[-2]
        yesterday_score = calculate_intelligence_score(
            avg_steps=yesterday_row.get("avg_steps", 5),
            success_rate=yesterday_row.get("success_rate", 0.5),
            error_rate=yesterday_row.get("total_errors", 0) / max(yesterday_row.get("tasks_completed", 1), 1),
            memory_reuse=memory_metrics.get("avg_accesses", 0) * 0.8,  # Estimate
            avg_importance=memory_metrics.get("avg_importance", 0.5),
        )
    
    # Render main score card
    render_intelligence_score_card(intelligence_score, yesterday_score)
    
    st.markdown("---")
    
    # Render metric cards
    render_metric_cards(efficiency_metrics)
    
    st.markdown("---")
    
    # Main analysis sections
    tab1, tab2, tab3 = st.tabs(["📊 Daily Trends", "⚡ Task Efficiency", "🧠 Memory Analysis"])
    
    with tab1:
        render_daily_trend_chart(daily_df)
    
    with tab2:
        render_task_efficiency_analysis(tasks_df)
    
    with tab3:
        render_memory_analysis(memories_df)
    
    # Export functionality
    st.markdown("---")
    st.markdown("### 📥 Export Data")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Download Task Metrics CSV", use_container_width=True):
            csv = tasks_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"agent_tasks_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
    
    with col2:
        if st.button("Download Daily Summary CSV", use_container_width=True):
            csv = daily_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"agent_daily_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
    
    with col3:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Help section
    with st.expander("📖 How to Interpret These Metrics"):
        st.markdown("""
        ### Intelligence Score Components
        
        | Component | Weight | Description |
        |-----------|--------|-------------|
        | Efficiency | 30% | Fewer steps to complete tasks = better |
        | Success Rate | 30% | Higher task completion success = better |
        | Error Handling | 15% | Fewer errors during execution = better |
        | Memory Reuse | 15% | More frequent memory access = better learning |
        | Memory Quality | 10% | Higher importance scores = better prioritization |
        
        ### Key Metrics Explained
        
        - **Avg Steps**: Average number of thought+action cycles per task (lower is better)
        - **Success Rate**: Percentage of tasks completed successfully
        - **Error Rate**: Average errors per task (lower is better)
        - **Avg Duration**: Average time to complete a task
        - **Memory Importance**: How well the agent prioritizes valuable experiences
        
        ### Day-over-Day Comparison
        
        Compare today's metrics with yesterday's to see if your agent is improving:
        - ✅ Green indicators show improvement
        - 📉 Red indicators show decline
        - Focus on trends over multiple days for reliable assessment
        """)


if __name__ == "__main__":
    main()