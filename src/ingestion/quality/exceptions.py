"""Exception classes for document quality checking."""

from __future__ import annotations

from typing import Any, Dict


class QualityCheckFailed(Exception):
    """Exception raised when document quality check fails.
    
    This exception is raised when a document fails the quality pre-check
    before ingestion. It includes detailed information about why the
    document was rejected.
    
    Attributes:
        message: Human-readable error message
        effective_char_ratio: The calculated effective character ratio
        text_density: The calculated text density
        garbage_ratio: The calculated garbage/scrambled text ratio
        min_text_length: The minimum text length found
        thresholds: The thresholds that were not met
        file_path: Path to the rejected file
    """
    
    def __init__(
        self,
        message: str,
        effective_char_ratio: float = 0.0,
        text_density: float = 0.0,
        garbage_ratio: float = 0.0,
        min_text_length: int = 0,
        thresholds: Dict[str, Any] = None,
        file_path: str = "",
    ):
        self.message = message
        self.effective_char_ratio = effective_char_ratio
        self.text_density = text_density
        self.garbage_ratio = garbage_ratio
        self.min_text_length = min_text_length
        self.thresholds = thresholds or {}
        self.file_path = file_path
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception details to dictionary."""
        return {
            "error_type": "QualityCheckFailed",
            "message": self.message,
            "metrics": {
                "effective_char_ratio": self.effective_char_ratio,
                "text_density": self.text_density,
                "garbage_ratio": self.garbage_ratio,
                "min_text_length": self.min_text_length,
            },
            "thresholds": self.thresholds,
            "file_path": self.file_path,
        }


class InvalidDocumentError(Exception):
    """Exception raised when a document is invalid or cannot be processed.
    
    This exception is raised for fundamental document issues like:
    - File not found
    - Corrupted file
    - Unsupported file format
    - Empty document
    
    Attributes:
        message: Human-readable error message
        file_path: Path to the invalid file
        reason: Specific reason for invalidity
    """
    
    def __init__(
        self,
        message: str,
        file_path: str = "",
        reason: str = "",
    ):
        self.message = message
        self.file_path = file_path
        self.reason = reason
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception details to dictionary."""
        return {
            "error_type": "InvalidDocumentError",
            "message": self.message,
            "file_path": self.file_path,
            "reason": self.reason,
        }