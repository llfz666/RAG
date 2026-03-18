"""Smart Agent Hub Dashboard - Streamlit Application.

This dashboard provides:
1. Session History - View and search past sessions
2. Execution Trace - Visualize Thought-Action-Observation flow
3. Memory View - Browse long-term memories
4. Statistics - Agent usage metrics

Usage:
    streamlit run dashboard/app.py

Requirements:
    pip install streamlit pandas
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st


# ============================================================================
# Configuration
# ============================================================================

DB_PATH = "data/db/agent_sessions.db"
LOG_PATH = "data/logs/agent_traces.jsonl"
MEMORY_PATH = "data/db/long_term_memory.jsonl"  # Fixed: Memory is saved to data/db/ not data/logs/

# Configure custom port to avoid conflict with RAG Dashboard (port 8501)
# Run with: streamlit run dashboard/app.py --server.port 8502

st.set_page_config(
    page_title="Smart Agent Hub Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)



# ============================================================================
# Data Loading Functions
# ============================================================================

@st.cache_data(ttl=60)
def load_sessions(db_path: str, limit: int = 100) -> pd.DataFrame:
    """Load sessions from database."""
    if not Path(db_path).exists():
        return pd.DataFrame()
    
    conn = sqlite3.connect(db_path)
    
    query = """
        SELECT 
            s.session_id,
            s.created_at,
            s.updated_at,
            s.metadata,
            COUNT(DISTINCT t.task_id) as task_count,
            MAX(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END) as has_completed
        FROM sessions s
        LEFT JOIN tasks t ON s.session_id = t.session_id
        GROUP BY s.session_id
        ORDER BY s.updated_at DESC
        LIMIT ?
    """
    
    df = pd.read_sql_query(query, conn, params=(limit,))
    conn.close()
    
    # Parse metadata JSON
    if not df.empty:
        df["metadata_parsed"] = df["metadata"].apply(
            lambda x: json.loads(x) if x else {}
        )
        df["query_preview"] = df["metadata_parsed"].apply(
            lambda x: x.get("query", "N/A")[:100]
        )
    
    return df


@st.cache_data(ttl=60)
def load_tasks_for_session(db_path: str, session_id: str) -> pd.DataFrame:
    """Load tasks for a specific session."""
    if not Path(db_path).exists():
        return pd.DataFrame()
    
    conn = sqlite3.connect(db_path)
    
    query = """
        SELECT 
            task_id,
            user_query,
            status,
            final_result,
            created_at,
            updated_at
        FROM tasks
        WHERE session_id = ?
        ORDER BY created_at DESC
    """
    
    df = pd.read_sql_query(query, conn, params=(session_id,))
    conn.close()
    
    return df


@st.cache_data(ttl=60)
def load_steps_for_task(db_path: str, task_id: str) -> pd.DataFrame:
    """Load steps for a specific task."""
    if not Path(db_path).exists():
        return pd.DataFrame()
    
    conn = sqlite3.connect(db_path)
    
    query = """
        SELECT 
            step_index,
            thought,
            action,
            action_input,
            observation,
            error,
            latency_ms,
            is_final,
            final_answer,
            created_at
        FROM steps
        WHERE task_id = ?
        ORDER BY step_index
    """
    
    df = pd.read_sql_query(query, conn, params=(task_id,))
    conn.close()
    
    return df


@st.cache_data(ttl=60)
def load_jsonl_logs(log_path: str, session_id: Optional[str] = None) -> list[dict]:
    """Load events from JSONL log file."""
    path = Path(log_path)
    if not path.exists():
        return []
    
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                event = json.loads(line.strip())
                if session_id is None or event.get("session_id") == session_id:
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


def get_session_stats(db_path: str) -> dict[str, Any]:
    """Get overall statistics."""
    if not Path(db_path).exists():
        return {
            "total_sessions": 0,
            "total_tasks": 0,
            "completed_tasks": 0,
            "total_steps": 0,
        }
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Total sessions
    cursor.execute("SELECT COUNT(*) FROM sessions")
    total_sessions = cursor.fetchone()[0]
    
    # Total tasks
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cursor.fetchone()[0]
    
    # Completed tasks
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
    completed_tasks = cursor.fetchone()[0]
    
    # Total steps
    cursor.execute("SELECT COUNT(*) FROM steps")
    total_steps = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_sessions": total_sessions,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "total_steps": total_steps,
    }


# ============================================================================
# UI Components
# ============================================================================

def render_stats_card(title: str, value: str | int, icon: str = "📊") -> None:
    """Render a statistics card."""
    st.metric(
        label=title,
        value=value,
    )


def render_step_expander(step: dict, index: int) -> None:
    """Render a step as an expander."""
    is_final = bool(step.get("is_final", False))
    has_error = bool(step.get("error"))
    
    # Determine icon based on step type
    if is_final:
        icon = "✅"
        title = f"Step {index}: Final Answer"
    elif step.get("action"):
        icon = "🔧"
        title = f"Step {index}: Action - {step['action']}"
    elif step.get("thought"):
        icon = "🤔"
        title = f"Step {index}: Thought"
    else:
        icon = "📝"
        title = f"Step {index}"
    
    if has_error:
        icon = "❌"
        title += " (Error)"
    
    with st.expander(f"{icon} {title}", expanded=False):
        if step.get("thought"):
            thought = json.loads(step["thought"]) if isinstance(step["thought"], str) else step["thought"]
            st.markdown("**Thought:**")
            st.markdown(str(thought))
        
        if step.get("action"):
            st.markdown(f"**Action:** `{step['action']}`")
            
            if step.get("action_input"):
                action_input = json.loads(step["action_input"]) if isinstance(step["action_input"], str) else step["action_input"]
                st.markdown("**Input:**")
                st.json(action_input)
        
        if step.get("observation"):
            st.markdown("**Observation:**")
            st.text(str(step["observation"])[:2000])
        
        if step.get("error"):
            st.error(f"**Error:** {step['error']}")
        
        if step.get("final_answer"):
            st.markdown("**Final Answer:**")
            st.markdown(str(step["final_answer"])[:2000])
        
        if step.get("latency_ms"):
            st.caption(f"Latency: {step['latency_ms']:.2f}ms")


def render_trace_visualization(steps_df: pd.DataFrame) -> None:
    """Render a visual trace of the execution flow."""
    if steps_df.empty:
        st.info("No steps to visualize")
        return
    
    # Create flow diagram using Streamlit columns
    st.markdown("### 🔍 Execution Flow")
    
    for idx, row in steps_df.iterrows():
        is_final = bool(row.get("is_final", False))
        
        # Thought
        if row.get("thought"):
            thought = json.loads(row["thought"]) if isinstance(row["thought"], str) else row["thought"]
            st.markdown(f"**🤔 Thought {idx}:**")
            with st.container(border=True):
                st.markdown(str(thought)[:500])
        
        # Action
        if row.get("action"):
            st.markdown(f"**🔧 Action {idx}:** `{row['action']}`")
            
            if row.get("action_input"):
                try:
                    action_input = json.loads(row["action_input"]) if isinstance(row["action_input"], str) else row["action_input"]
                    with st.container(border=True):
                        st.json(action_input)
                except:
                    pass
        
        # Observation
        if row.get("observation"):
            st.markdown(f"**📦 Observation {idx}:**")
            with st.container(border=True):
                obs = str(row["observation"])
                if len(obs) > 1000:
                    obs = obs[:1000] + "... (truncated)"
                st.text(obs)
        
        # Error
        if row.get("error"):
            st.error(f"**❌ Error {idx}:** {row['error']}")
        
        # Final Answer
        if is_final and row.get("final_answer"):
            st.success("**✅ Final Answer:**")
            with st.container(border=True):
                st.markdown(str(row["final_answer"])[:2000])
        
        # Divider
        st.divider()


# ============================================================================
# Page Layout
# ============================================================================

def main():
    """Main dashboard application."""
    
    # Sidebar navigation
    st.sidebar.title("🤖 Smart Agent Hub")
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio(
        "Navigation",
        ["💬 Chat", "📊 Overview", "📜 Session History", "🔍 Execution Trace", "🧠 Memory View", "⚙️ Settings"],
    )
    
    st.sidebar.markdown("---")
    
    # Load and display stats in sidebar
    stats = get_session_stats(DB_PATH)
    st.sidebar.metric("Total Sessions", stats["total_sessions"])
    st.sidebar.metric("Total Tasks", stats["total_tasks"])
    st.sidebar.metric("Completed", stats["completed_tasks"])
    st.sidebar.metric("Total Steps", stats["total_steps"])
    
    # =========================================================================
    # Chat Page
    # =========================================================================
    
    if page == "💬 Chat":
        try:
            from dashboard.chat_page import chat_page
        except ImportError:
            from chat_page import chat_page
        chat_page()
        return
    
    # =========================================================================
    # Overview Page
    # =========================================================================
    
    if page == "📊 Overview":
        st.title("📊 Dashboard Overview")
        st.markdown("Welcome to the Smart Agent Hub Dashboard!")
        
        # Stats cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            render_stats_card("Total Sessions", stats["total_sessions"], "💾")
        with col2:
            render_stats_card("Total Tasks", stats["total_tasks"], "📋")
        with col3:
            render_stats_card("Completed", stats["completed_tasks"], "✅")
        with col4:
            render_stats_card("Total Steps", stats["total_steps"], "👣")
        
        st.markdown("---")
        
        # Recent sessions table
        st.markdown("### Recent Sessions")
        sessions_df = load_sessions(DB_PATH, limit=10)
        
        if not sessions_df.empty:
            # Format for display
            display_df = sessions_df.copy()
            # Handle mixed datetime formats (ISO8601 and SQLite formats)
            display_df["created_at"] = pd.to_datetime(display_df["created_at"], format="mixed").dt.strftime("%Y-%m-%d %H:%M")
            display_df["updated_at"] = pd.to_datetime(display_df["updated_at"], format="mixed").dt.strftime("%Y-%m-%d %H:%M")
            
            display_df = display_df[["created_at", "updated_at", "query_preview", "task_count", "has_completed"]]
            display_df.columns = ["Created", "Updated", "Query Preview", "Tasks", "Completed"]
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No sessions found. Start using the agent to create sessions!")
        
        # Quick actions
        st.markdown("---")
        st.markdown("### Quick Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("️ Clear All Data", use_container_width=True):
                st.warning("This will delete all sessions, tasks, and steps. This action cannot be undone!")
                if st.button("Confirm Delete"):
                    # Delete database
                    if Path(DB_PATH).exists():
                        Path(DB_PATH).unlink()
                    # Delete logs
                    if Path(LOG_PATH).exists():
                        Path(LOG_PATH).unlink()
                    st.success("Data cleared! Please refresh the page.")
                    st.rerun()
        
        with col2:
            if st.button("🔄 Refresh Data", use_container_width=True):
                st.rerun()
    
    # =========================================================================
    # Session History Page
    # =========================================================================
    
    elif page == "📜 Session History":
        st.title("📜 Session History")
        
        # Search and filter
        col1, col2 = st.columns([3, 1])
        
        with col1:
            search_query = st.text_input("🔍 Search sessions", placeholder="Search by query content...")
        
        with col2:
            limit = st.selectbox("Limit", [10, 25, 50, 100], index=1)
        
        # Load sessions
        sessions_df = load_sessions(DB_PATH, limit=limit)
        
        if sessions_df.empty:
            st.info("No sessions found.")
            return
        
        # Filter by search
        if search_query:
            mask = sessions_df["query_preview"].str.lower().str.contains(search_query.lower())
            sessions_df = sessions_df[mask]
        
        if sessions_df.empty:
            st.info(f"No sessions matching '{search_query}'")
            return
        
        # Display sessions
        st.markdown(f"### Found {len(sessions_df)} sessions")
        
        for idx, row in sessions_df.iterrows():
            with st.expander(
                f"📁 Session: {row['session_id'][:8]}... - {row['query_preview'][:80]}",
                expanded=False,
            ):
                # Session info
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Created", row["created_at"][:10] if row["created_at"] else "N/A")
                with col2:
                    st.metric("Updated", row["updated_at"][:10] if row["updated_at"] else "N/A")
                with col3:
                    st.metric("Tasks", row["task_count"])
                
                # Load tasks for this session
                tasks_df = load_tasks_for_session(DB_PATH, row["session_id"])
                
                if not tasks_df.empty:
                    st.markdown("#### Tasks")
                    
                    for task_idx, task_row in tasks_df.iterrows():
                        status_icon = "✅" if task_row["status"] == "completed" else "⏳" if task_row["status"] == "running" else "❌"
                        
                        with st.expander(f"{status_icon} Task: {task_row['user_query'][:60]}..."):
                            st.markdown(f"**Query:** {task_row['user_query']}")
                            st.markdown(f"**Status:** {task_row['status']}")
                            
                            if task_row.get("final_result"):
                                st.markdown(f"**Result:** {task_row['final_result'][:500]}")
                            
                            # Load steps
                            steps_df = load_steps_for_task(DB_PATH, task_row["task_id"])
                            
                            if not steps_df.empty:
                                st.markdown(f"**Steps:** {len(steps_df)}")
                                
                                # Visualize trace
                                if st.button("Visualize Trace", key=f"trace_{task_row['task_id']}"):
                                    render_trace_visualization(steps_df)
    
    # =========================================================================
    # Execution Trace Page
    # =========================================================================
    
    elif page == "🔍 Execution Trace":
        st.title("🔍 Execution Trace")
        st.markdown("View detailed execution traces for tasks.")
        
        # Select session
        sessions_df = load_sessions(DB_PATH, limit=50)
        
        if sessions_df.empty:
            st.info("No sessions available.")
            return
        
        session_options = sessions_df.apply(
            lambda row: f"{row['session_id'][:8]}... - {row['query_preview'][:50]}",
            axis=1,
        )
        
        selected_session = st.selectbox(
            "Select Session",
            session_options.tolist(),
        )
        
        if not selected_session:
            return
        
        # Get session ID
        selected_idx = session_options.tolist().index(selected_session)
        session_id = sessions_df.iloc[selected_idx]["session_id"]
        
        # Load tasks
        tasks_df = load_tasks_for_session(DB_PATH, session_id)
        
        if tasks_df.empty:
            st.info("No tasks for this session.")
            return
        
        # Select task
        task_options = tasks_df.apply(
            lambda row: f"[{row['status']}] {row['user_query'][:50]}",
            axis=1,
        )
        
        selected_task = st.selectbox(
            "Select Task",
            task_options.tolist(),
            key="task_select",
        )
        
        if not selected_task:
            return
        
        # Get task ID
        selected_task_idx = task_options.tolist().index(selected_task)
        task_id = tasks_df.iloc[selected_task_idx]["task_id"]
        
        # Load and display steps
        steps_df = load_steps_for_task(DB_PATH, task_id)
        
        if steps_df.empty:
            st.info("No steps for this task.")
            return
        
        # Task info
        task_info = tasks_df.iloc[selected_task_idx]
        st.markdown(f"### Task: {task_info['user_query']}")
        st.markdown(f"**Status:** {task_info['status']}")
        
        if task_info.get("final_result"):
            st.success(f"**Final Result:** {task_info['final_result'][:500]}")
        
        st.markdown("---")
        
        # Visualization options
        view_mode = st.radio(
            "View Mode",
            ["📊 Visual Flow", "📋 Step List"],
            horizontal=True,
        )
        
        if view_mode == "📊 Visual Flow":
            render_trace_visualization(steps_df)
        else:
            # Step list with expanders
            for idx, row in steps_df.iterrows():
                render_step_expander(row.to_dict(), idx)
    
    # =========================================================================
    # Memory View Page
    # =========================================================================
    
    elif page == "🧠 Memory View":
        st.title("🧠 Long-term Memory")
        st.markdown("Browse and search stored memories.")
        
        # Load memories
        memories_df = load_memories(MEMORY_PATH)
        
        if memories_df.empty:
            st.info("No memories stored yet.")
            return
        
        # Stats
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Memories", len(memories_df))
        
        with col2:
            avg_importance = memories_df["importance"].mean() if "importance" in memories_df.columns else 0
            st.metric("Avg Importance", f"{avg_importance:.2f}")
        
        with col3:
            total_access = memories_df["access_count"].sum() if "access_count" in memories_df.columns else 0
            st.metric("Total Accesses", total_access)
        
        st.markdown("---")
        
        # Filter by type
        if "entry_type" in memories_df.columns:
            types = memories_df["entry_type"].unique()
            selected_type = st.selectbox("Filter by Type", ["All"] + list(types))
            
            if selected_type != "All":
                memories_df = memories_df[memories_df["entry_type"] == selected_type]
        
        # Search
        search_query = st.text_input("🔍 Search memories", placeholder="Search by content...")
        
        if search_query:
            mask = memories_df["content"].str.lower().str.contains(search_query.lower())
            memories_df = memories_df[mask]
        
        # Display memories
        st.markdown(f"### {len(memories_df)} memories")
        
        for idx, row in memories_df.iterrows():
            importance = row.get("importance", 0.5)
            access_count = row.get("access_count", 0)
            entry_type = row.get("entry_type", "unknown")
            content = row.get("content", "")
            created_at = row.get("created_at", "")
            
            # Icon based on type
            type_icon = "📝" if entry_type == "conversation" else "💡" if entry_type == "experience" else "📚"
            
            with st.expander(
                f"{type_icon} [{entry_type}] {content[:80]}...",
                expanded=False,
            ):
                st.markdown(f"**Type:** {entry_type}")
                st.markdown(f"**Importance:** {importance:.2f}")
                st.markdown(f"**Access Count:** {access_count}")
                st.markdown(f"**Created:** {created_at}")
                st.markdown("---")
                st.markdown(f"**Content:**\n\n{content}")
                
                # Delete button
                if st.button("🗑️ Delete", key=f"del_{row.get('id', idx)}"):
                    st.warning("Delete functionality not implemented in read-only mode")
    
    # =========================================================================
    # Settings Page
    # =========================================================================
    
    elif page == "⚙️ Settings":
        st.title("⚙️ Settings")
        
        st.markdown("### Data Paths")
        
        st.code(f"Database: {DB_PATH}", language="text")
        st.code(f"Logs: {LOG_PATH}", language="text")
        st.code(f"Memory: {MEMORY_PATH}", language="text")
        
        st.markdown("---")
        
        st.markdown("### About")
        st.markdown("""
        **Smart Agent Hub Dashboard**
        
        A Streamlit-based dashboard for monitoring and analyzing 
        Smart Agent Hub sessions, tasks, and execution traces.
        
        **Features:**
        - Session history browsing
        - Execution trace visualization
        - Long-term memory inspection
        - Usage statistics
        
        **Usage:**
        ```bash
        streamlit run dashboard/app.py
        ```
        """)


if __name__ == "__main__":
    main()