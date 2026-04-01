"""Ingestion Manager page – upload files, trigger ingestion, delete documents.

Layout:
1. File uploader + collection selector
2. Ingest button → progress bar (using on_progress callback)
3. Document list with delete buttons
"""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import mktemp

import streamlit as st

from src.observability.dashboard.services.data_service import DataService


@st.cache_resource
def _get_data_service() -> DataService:
    """Get cached DataService instance to avoid re-initializing storage objects."""
    return DataService()


def _run_ingestion(
    uploaded_file: "st.runtime.uploaded_file_manager.UploadedFile",
    collection: str,
    progress_bar: "st.delta_generator.DeltaGenerator",
    status_text: "st.delta_generator.DeltaGenerator",
) -> None:
    """Save the uploaded file to a temp location and run the pipeline."""
    from src.core.settings import load_settings
    from src.core.trace import TraceContext, TraceCollector
    from src.ingestion.pipeline import IngestionPipeline

    settings = load_settings()

    # Write uploaded file to a temp location with proper extension
    # Use mktemp to create a temp filename with the correct extension
    suffix = Path(uploaded_file.name).suffix.lower()
    
    # Ensure suffix starts with a dot
    if suffix and not suffix.startswith('.'):
        suffix = '.' + suffix
    
    # Create temp file with proper extension
    tmp_path = mktemp(suffix=suffix)
    
    try:
        with open(tmp_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
    except Exception as e:
        status_text.error(f"Failed to save uploaded file: {e}")
        return

    _STAGE_LABELS = {
        "integrity": "🔍 Checking file integrity…",
        "load": "📄 Loading document…",
        "split": "✂️ Chunking document…",
        "transform": "🔄 Transforming chunks (LLM refine + enrich)…",
        "embed": "🔢 Encoding vectors…",
        "upsert": "💾 Storing to database…",
    }

    def on_progress(stage: str, current: int, total: int) -> None:
        frac = (current - 1) / total  # stage just started, show partial progress
        label = _STAGE_LABELS.get(stage, stage)
        progress_bar.progress(frac, text=f"[{current}/{total}] {label}")
        status_text.caption(label)

    trace = TraceContext(trace_type="ingestion")
    trace.metadata["source_path"] = uploaded_file.name
    trace.metadata["collection"] = collection
    trace.metadata["source"] = "dashboard"

    try:
        pipeline = IngestionPipeline(settings, collection=collection)
        result = pipeline.run(
            file_path=tmp_path,
            trace=trace,
            on_progress=on_progress,
        )
        
        # Check if pipeline failed due to quality check
        if not result.success:
            if "文档质量不达标" in result.error or "quality_check" in result.stages:
                # Quality check failed - show detailed error
                status_text.error("❌ 文档质量检查未通过")
                
                quality_info = result.stages.get("quality_check", {})
                if quality_info:
                    st.divider()
                    st.subheader("📊 质量检测报告")
                    
                    # Show metrics if available
                    reason = quality_info.get("reason", {})
                    if reason:
                        metrics = reason.get("metrics", {})
                        thresholds = reason.get("thresholds", {})
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("### 检测值")
                            st.metric("有效字符占比", f"{metrics.get('effective_char_ratio', 0):.1%}")
                            st.metric("文本密度", f"{metrics.get('text_density', 0):.1%}")
                            st.metric("乱码比例", f"{metrics.get('garbage_ratio', 0):.1%}")
                        
                        with col2:
                            st.markdown("### 阈值要求")
                            st.metric("有效字符占比", f"{thresholds.get('min_effective_char_ratio', 0.8):.0%}")
                            st.metric("文本密度", f"{thresholds.get('min_text_density', 0.7):.0%}")
                            st.metric("乱码比例", f"≤{thresholds.get('max_garbage_ratio', 0.05):.0%}")
                        
                        st.divider()
                        st.markdown("### 💡 建议")
                        st.markdown("""
                        - 检查原始文档是否清晰可读
                        - 如为扫描件，尝试使用 OCR 增强版本
                        - 联系文档提供方获取可编辑版本（如 Word 格式）
                        - 确保 PDF 包含可选择的文本层，而非纯图片
                        """)
                    return
            else:
                # Other error
                status_text.error(f"Ingestion failed: {result.error}")
                return
        
        progress_bar.progress(1.0, text="✅ Complete")
        status_text.success(f"Successfully ingested **{uploaded_file.name}** into collection **{collection}**.")
    except Exception as exc:
        status_text.error(f"Ingestion failed: {exc}")
    finally:
        TraceCollector().collect(trace)
        # Clean up temp file
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


def render() -> None:
    """Render the Ingestion Manager page."""
    st.header("📥 Ingestion Manager")

    # ── Upload section ─────────────────────────────────────────────
    st.subheader("📤 Upload & Ingest")

    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded = st.file_uploader(
            "Select a file to ingest",
            type=["pdf", "txt", "md", "docx", "pptx", "xlsx", "xlsm"],
            key="ingest_uploader",
        )
    with col2:
        collection = st.text_input("Collection", value="default", key="ingest_collection")

    if uploaded is not None:
        if st.button("🚀 Start Ingestion", key="btn_ingest"):
            progress_bar = st.progress(0, text="Preparing…")
            status_text = st.empty()
            _run_ingestion(uploaded, collection.strip() or "default", progress_bar, status_text)

    st.divider()

    # ── Document management section ────────────────────────────────
    st.subheader("🗑️ Manage Documents")

    try:
        # Use cached DataService to avoid re-initializing storage objects on every render
        svc = _get_data_service()
        docs = svc.list_documents()
    except Exception as exc:
        st.error(f"Failed to load documents: {exc}")
        return

    if not docs:
        st.info(
            "**No documents ingested yet.** "
            "Upload a PDF, TXT, MD, DOCX, PPTX, XLSX, or XLSM file above and click \"Start Ingestion\" to begin."
        )
        return

    for idx, doc in enumerate(docs):
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.markdown(
                f"**{doc['source_path']}** — "
                f"collection: `{doc.get('collection', '—')}` | "
                f"chunks: {doc['chunk_count']} | "
                f"images: {doc['image_count']}"
            )
        with col_btn:
            if st.button("🗑️ Delete", key=f"del_{idx}"):
                try:
                    result = svc.delete_document(
                        source_path=doc["source_path"],
                        collection=doc.get("collection", "default"),
                        source_hash=doc.get("source_hash"),
                    )
                    if result.success:
                        st.success(
                            f"Deleted: {result.chunks_deleted} chunks, "
                            f"{result.images_deleted} images removed."
                        )
                        st.rerun()
                    else:
                        st.warning(f"Partial delete. Errors: {result.errors}")
                except Exception as exc:
                    st.error(f"Delete failed: {exc}")
