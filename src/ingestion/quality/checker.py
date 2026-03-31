"""Document Quality Checker - Pre-processing quality assessment for RAG ingestion."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.ingestion.quality.exceptions import QualityCheckFailed, InvalidDocumentError
from src.ingestion.quality.metrics import (
    QualityMetrics,
    QualityCheckResult,
    MetricsCalculator,
)

logger = logging.getLogger(__name__)


@dataclass
class QualityThresholds:
    """Quality thresholds for document validation.
    
    Attributes:
        min_effective_char_ratio: Minimum ratio of non-whitespace characters (default: 0.80)
        min_text_density: Minimum ratio of non-empty lines (default: 0.70)
        max_garbage_ratio: Maximum ratio of garbage characters (default: 0.05)
        min_text_length: Minimum total text length (default: 500)
        max_replacement_chars: Maximum number of replacement characters () (default: 10)
    """
    
    min_effective_char_ratio: float = 0.80
    min_text_density: float = 0.70
    max_garbage_ratio: float = 0.05
    min_text_length: int = 500
    max_replacement_chars: int = 10
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert thresholds to dictionary."""
        return {
            "min_effective_char_ratio": self.min_effective_char_ratio,
            "min_text_density": self.min_text_density,
            "max_garbage_ratio": self.max_garbage_ratio,
            "min_text_length": self.min_text_length,
            "max_replacement_chars": self.max_replacement_chars,
        }


class DocumentQualityChecker:
    """Document quality checker for RAG ingestion pipeline.
    
    This checker performs pre-processing quality assessment on documents
    before they enter the knowledge base. It extracts text from the first
    few pages and calculates various quality metrics to determine if the
    document is suitable for ingestion.
    
    Quality Metrics:
    - Effective Character Ratio: Ratio of non-whitespace characters
    - Text Density: Ratio of non-empty lines to total lines
    - Garbage Ratio: Ratio of scrambled/unreadable characters
    - Minimum Text Length: Total length of extracted text
    
    Usage:
        >>> checker = DocumentQualityChecker(threshold=0.80)
        >>> result = checker.check("document.pdf")
        >>> if not result.passed:
        ...     print(f"Quality check failed: {result.details}")
    """
    
    def __init__(
        self,
        threshold: float = 0.80,
        max_pages: int = 5,
        dpi: int = 150,
        strict_mode: bool = False,
    ):
        """Initialize the document quality checker.
        
        Args:
            threshold: Minimum effective character ratio threshold (default: 0.80)
            max_pages: Maximum number of pages to analyze (default: 5)
            dpi: DPI for rendering pages (default: 150)
            strict_mode: If True, use stricter thresholds for all metrics
        """
        self.threshold = threshold
        self.max_pages = max_pages
        self.dpi = dpi
        self.strict_mode = strict_mode
        
        # Configure thresholds based on mode
        if strict_mode:
            self.thresholds = QualityThresholds(
                min_effective_char_ratio=0.85,
                min_text_density=0.80,
                max_garbage_ratio=0.03,
                min_text_length=1000,
                max_replacement_chars=5,
            )
        else:
            self.thresholds = QualityThresholds(
                min_effective_char_ratio=threshold,
                min_text_density=0.70,
                max_garbage_ratio=0.05,
                min_text_length=500,
                max_replacement_chars=10,
            )
        
        self.metrics_calculator = MetricsCalculator()
        self._pymupdf_available = self._check_pymupdf()
    
    def _check_pymupdf(self) -> bool:
        """Check if PyMuPDF is available."""
        try:
            import fitz  # noqa: F401
            return True
        except ImportError:
            logger.warning("PyMuPDF not available. Install with: pip install pymupdf")
            return False
    
    def check(self, file_path: str) -> QualityCheckResult:
        """Perform quality check on a document.
        
        Args:
            file_path: Path to the document file.
            
        Returns:
            QualityCheckResult with pass/fail status and detailed metrics.
            
        Raises:
            InvalidDocumentError: If the file cannot be opened or is not a valid PDF.
        """
        path = Path(file_path)
        
        # Validate file exists
        if not path.exists():
            raise InvalidDocumentError(
                f"File not found: {file_path}",
                file_path=file_path,
                reason="file_not_found",
            )
        
        # Check file size
        file_size = path.stat().st_size
        if file_size == 0:
            raise InvalidDocumentError(
                f"File is empty: {file_path}",
                file_path=file_path,
                reason="empty_file",
            )
        
        # Extract text from first max_pages pages
        text, pages_analyzed = self._extract_text(path)
        
        if not text:
            raise InvalidDocumentError(
                f"No text could be extracted from: {file_path}",
                file_path=file_path,
                reason="no_text_extracted",
            )
        
        # Calculate metrics
        metrics = self.metrics_calculator.calculate(text)
        metrics.pages_analyzed = pages_analyzed  # type: ignore
        
        # Check against thresholds
        failures, warnings = self._check_thresholds(metrics)
        
        # Build result
        passed = len(failures) == 0
        details = self._build_details_report(metrics, failures, warnings)
        
        result = QualityCheckResult(
            passed=passed,
            file_path=file_path,
            pages_analyzed=pages_analyzed,
            text_extracted=text[:2000],  # Keep preview for debugging
            metrics=metrics,
            failures=failures,
            details=details,
            warnings=warnings,
        )
        
        if passed:
            logger.info(f"Quality check PASSED for {file_path}")
        else:
            logger.warning(f"Quality check FAILED for {file_path}: {details}")
        
        return result
    
    def check_or_raise(self, file_path: str) -> QualityCheckResult:
        """Perform quality check and raise exception if failed.
        
        Args:
            file_path: Path to the document file.
            
        Returns:
            QualityCheckResult if check passed.
            
        Raises:
            QualityCheckFailed: If the document fails the quality check.
            InvalidDocumentError: If the file cannot be processed.
        """
        result = self.check(file_path)
        
        if not result.passed:
            raise QualityCheckFailed(
                message=result.details,
                effective_char_ratio=result.metrics.effective_char_ratio,
                text_density=result.metrics.text_density,
                garbage_ratio=result.metrics.garbage_ratio,
                min_text_length=result.metrics.min_text_length,
                thresholds=self.thresholds.to_dict(),
                file_path=file_path,
            )
        
        return result
    
    def _extract_text(self, file_path: Path) -> Tuple[str, int]:
        """Extract text from the first max_pages pages of a PDF.
        
        Args:
            file_path: Path to the PDF file.
            
        Returns:
            Tuple of (extracted_text, pages_analyzed).
        """
        if not self._pymupdf_available:
            raise InvalidDocumentError(
                "PyMuPDF is required for quality checking",
                file_path=str(file_path),
                reason="missing_dependency",
            )
        
        import fitz  # PyMuPDF
        
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise InvalidDocumentError(
                f"Failed to open PDF: {e}",
                file_path=str(file_path),
                reason="corrupted_file",
            )
        
        text_parts = []
        pages_to_analyze = min(self.max_pages, len(doc))
        
        for page_num in range(pages_to_analyze):
            page = doc[page_num]
            
            # Try to extract text directly first
            page_text = page.get_text()
            
            # If no text found, try rendering and OCR (optional)
            if not page_text.strip():
                # Page might be an image - mark as warning
                pass
            
            text_parts.append(page_text)
        
        doc.close()
        
        return "\n\n".join(text_parts), pages_to_analyze
    
    def _check_thresholds(
        self, metrics: QualityMetrics
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Check metrics against configured thresholds.
        
        Args:
            metrics: Calculated quality metrics.
            
        Returns:
            Tuple of (failures, warnings).
        """
        failures = []
        warnings = []
        
        # Check effective character ratio
        if metrics.effective_char_ratio < self.thresholds.min_effective_char_ratio:
            failures.append({
                "metric": "effective_char_ratio",
                "value": metrics.effective_char_ratio,
                "threshold": self.thresholds.min_effective_char_ratio,
                "message": f"有效字符占比过低：{metrics.effective_char_ratio:.2%} (要求 ≥{self.thresholds.min_effective_char_ratio:.0%})",
            })
        elif metrics.effective_char_ratio < 0.90:
            warnings.append(f"有效字符占比偏低：{metrics.effective_char_ratio:.2%}")
        
        # Check text density
        if metrics.text_density < self.thresholds.min_text_density:
            failures.append({
                "metric": "text_density",
                "value": metrics.text_density,
                "threshold": self.thresholds.min_text_density,
                "message": f"可识别文本密度过低：{metrics.text_density:.2%} (要求 ≥{self.thresholds.min_text_density:.0%})",
            })
        elif metrics.text_density < 0.85:
            warnings.append(f"文本密度偏低：{metrics.text_density:.2%}")
        
        # Check garbage ratio
        if metrics.garbage_ratio > self.thresholds.max_garbage_ratio:
            failures.append({
                "metric": "garbage_ratio",
                "value": metrics.garbage_ratio,
                "threshold": self.thresholds.max_garbage_ratio,
                "message": f"乱码比例过高：{metrics.garbage_ratio:.2%} (要求 ≤{self.thresholds.max_garbage_ratio:.0%})",
            })
        elif metrics.garbage_ratio > 0.02:
            warnings.append(f"检测到少量乱码：{metrics.garbage_ratio:.2%}")
        
        # Check minimum text length
        if metrics.min_text_length < self.thresholds.min_text_length:
            failures.append({
                "metric": "min_text_length",
                "value": metrics.min_text_length,
                "threshold": self.thresholds.min_text_length,
                "message": f"文本长度过短：{metrics.min_text_length} 字符 (要求 ≥{self.thresholds.min_text_length})",
            })
        
        # Check replacement characters
        replacement_count = metrics.unicode_ranges.get("other", 0)
        if '\ufffd' in str(metrics.unicode_ranges) or replacement_count > self.thresholds.max_replacement_chars:
            failures.append({
                "metric": "replacement_chars",
                "value": replacement_count,
                "threshold": self.thresholds.max_replacement_chars,
                "message": f"发现过多替换字符 ()：{replacement_count} 个 (要求 ≤{self.thresholds.max_replacement_chars})",
            })
        
        return failures, warnings
    
    def _build_details_report(
        self,
        metrics: QualityMetrics,
        failures: List[Dict[str, Any]],
        warnings: List[str],
    ) -> str:
        """Build a human-readable details report.
        
        Args:
            metrics: Calculated quality metrics.
            failures: List of failed checks.
            warnings: List of warnings.
            
        Returns:
            Formatted report string.
        """
        lines = []
        
        # Header
        if failures:
            lines.append("❌ 文档质量不达标")
        else:
            lines.append("✅ 文档质量检查通过")
        
        lines.append("")
        lines.append("=== 检测结果 ===")
        lines.append(f"分析页数：{getattr(metrics, 'pages_analyzed', 0)}")
        lines.append(f"文本总长度：{metrics.min_text_length} 字符")
        lines.append("")
        
        # Metrics summary
        lines.append("=== 质量指标 ===")
        lines.append(f"有效字符占比：{metrics.effective_char_ratio:.2%}")
        lines.append(f"可识别文本密度：{metrics.text_density:.2%}")
        lines.append(f"乱码比例：{metrics.garbage_ratio:.2%}")
        lines.append("")
        
        # Failures
        if failures:
            lines.append("=== 失败项 ===")
            for failure in failures:
                lines.append(f"  • {failure['message']}")
            lines.append("")
        
        # Warnings
        if warnings:
            lines.append("=== 警告 ===")
            for warning in warnings:
                lines.append(f"  • {warning}")
            lines.append("")
        
        # Suggestions
        if failures:
            lines.append("=== 建议 ===")
            lines.append("  • 检查原始文档是否清晰可读")
            lines.append("  • 如为扫描件，尝试 OCR 增强版本")
            lines.append("  • 联系文档提供方获取可编辑版本")
        
        return "\n".join(lines)