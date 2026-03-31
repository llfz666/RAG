"""Document Quality Checking Module.

This module provides document quality checking capabilities for the RAG ingestion pipeline.
It performs pre-processing quality assessment to filter out low-quality documents before
they enter the knowledge base.

Key Features:
- Effective character ratio calculation
- Text density analysis
- Garbage/scrambled text detection
- Minimum text length validation

Usage:
    >>> from src.ingestion.quality import DocumentQualityChecker, QualityCheckFailed
    >>> checker = DocumentQualityChecker(threshold=0.80)
    >>> result = checker.check("document.pdf")
    >>> if not result.passed:
    ...     raise QualityCheckFailed(result.details)
"""

from src.ingestion.quality.exceptions import QualityCheckFailed, InvalidDocumentError
from src.ingestion.quality.metrics import QualityMetrics, QualityCheckResult
from src.ingestion.quality.checker import DocumentQualityChecker

__all__ = [
    "DocumentQualityChecker",
    "QualityCheckFailed",
    "InvalidDocumentError",
    "QualityMetrics",
    "QualityCheckResult",
]