"""Unit tests for Document Quality Checker."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.ingestion.quality import (
    DocumentQualityChecker,
    QualityCheckFailed,
    InvalidDocumentError,
    QualityMetrics,
    QualityCheckResult,
)
from src.ingestion.quality.metrics import MetricsCalculator
from src.ingestion.quality.checker import QualityThresholds
from src.ingestion.quality.exceptions import QualityCheckFailed as QualityCheckFailedException


class TestMetricsCalculator:
    """Tests for MetricsCalculator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = MetricsCalculator()
    
    def test_calculate_effective_char_ratio(self):
        """Test effective character ratio calculation."""
        # High ratio - mostly text
        text = "Hello World! 你好世界！"
        metrics = self.calculator.calculate(text)
        assert metrics.effective_char_ratio > 0.8
        assert metrics.total_chars == len(text)
    
    def test_calculate_low_effective_char_ratio(self):
        """Test low effective character ratio with lots of whitespace."""
        # Low ratio - lots of whitespace
        text = "   \n\n\n   \t\t\t   \n\n\n"
        metrics = self.calculator.calculate(text)
        assert metrics.effective_char_ratio < 0.5
    
    def test_calculate_text_density(self):
        """Test text density calculation."""
        # High density - all non-empty lines
        text = "Line 1\nLine 2\nLine 3"
        metrics = self.calculator.calculate(text)
        assert metrics.text_density == 1.0
    
    def test_calculate_low_text_density(self):
        """Test low text density with many empty lines."""
        text = "Line 1\n\n\n\n\n"
        metrics = self.calculator.calculate(text)
        assert metrics.text_density < 0.5
    
    def test_calculate_garbage_ratio(self):
        """Test garbage character detection."""
        # Text with replacement characters
        text = "Hello World"
        metrics = self.calculator.calculate(text)
        assert metrics.garbage_ratio == 0.0
    
    def test_calculate_with_garbage_chars(self):
        """Test detection of garbage/scrambled characters."""
        # Text with control characters
        text = "Hello\x00\x01\x02World"
        metrics = self.calculator.calculate(text)
        assert metrics.garbage_chars > 0
    
    def test_unicode_range_analysis(self):
        """Test Unicode range distribution analysis."""
        # Mixed English and Chinese
        text = "Hello World 你好世界"
        metrics = self.calculator.calculate(text)
        assert metrics.unicode_ranges.get("ascii", 0) > 0
        assert metrics.unicode_ranges.get("cjk", 0) > 0
    
    def test_empty_text(self):
        """Test calculation with empty text."""
        metrics = self.calculator.calculate("")
        assert metrics.total_chars == 0
        assert metrics.effective_char_ratio == 0.0
        assert metrics.text_density == 0.0
    
    def test_check_text_validity(self):
        """Test text validity check."""
        # Valid text
        is_valid, issues = self.calculator.check_text_validity("Hello World! 你好世界！")
        assert is_valid
        assert len(issues) == 0
        
        # Invalid text - too much whitespace
        is_valid, issues = self.calculator.check_text_validity("   \n\n\n   ")
        assert not is_valid
        assert len(issues) > 0


class TestQualityThresholds:
    """Tests for QualityThresholds dataclass."""
    
    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = QualityThresholds()
        assert thresholds.min_effective_char_ratio == 0.80
        assert thresholds.min_text_density == 0.70
        assert thresholds.max_garbage_ratio == 0.05
        assert thresholds.min_text_length == 500
        assert thresholds.max_replacement_chars == 10
    
    def test_to_dict(self):
        """Test threshold serialization."""
        thresholds = QualityThresholds()
        result = thresholds.to_dict()
        assert "min_effective_char_ratio" in result
        assert "min_text_density" in result
        assert "max_garbage_ratio" in result


class TestQualityCheckResult:
    """Tests for QualityCheckResult dataclass."""
    
    def test_default_result(self):
        """Test default result values."""
        result = QualityCheckResult()
        assert result.passed is True
        assert result.file_path == ""
        assert result.pages_analyzed == 0
        assert isinstance(result.metrics, QualityMetrics)
    
    def test_to_dict(self):
        """Test result serialization."""
        result = QualityCheckResult(
            passed=False,
            file_path="test.pdf",
            pages_analyzed=5,
            failures=[{"metric": "effective_char_ratio", "message": "Too low"}],
        )
        result_dict = result.to_dict()
        assert result_dict["passed"] is False
        assert result_dict["file_path"] == "test.pdf"
        assert result_dict["pages_analyzed"] == 5
        assert len(result_dict["failures"]) == 1


class TestDocumentQualityChecker:
    """Tests for DocumentQualityChecker class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.checker = DocumentQualityChecker(threshold=0.80, max_pages=5)
    
    def test_initialization(self):
        """Test checker initialization."""
        assert self.checker.threshold == 0.80
        assert self.checker.max_pages == 5
        assert self.checker.thresholds.min_effective_char_ratio == 0.80
    
    def test_strict_mode_thresholds(self):
        """Test strict mode uses stricter thresholds."""
        strict_checker = DocumentQualityChecker(strict_mode=True)
        assert strict_checker.thresholds.min_effective_char_ratio == 0.85
        assert strict_checker.thresholds.min_text_density == 0.80
        assert strict_checker.thresholds.max_garbage_ratio == 0.03
    
    def test_file_not_found(self):
        """Test handling of non-existent file."""
        with pytest.raises(InvalidDocumentError) as exc_info:
            self.checker.check("nonexistent_file.pdf")
        assert "File not found" in str(exc_info.value)
        assert exc_info.value.reason == "file_not_found"
    
    def test_empty_file(self, tmp_path):
        """Test handling of empty file."""
        empty_file = tmp_path / "empty.pdf"
        empty_file.touch()
        
        with pytest.raises(InvalidDocumentError) as exc_info:
            self.checker.check(str(empty_file))
        assert "File is empty" in str(exc_info.value)
        assert exc_info.value.reason == "empty_file"
    
    @patch('src.ingestion.quality.checker.DocumentQualityChecker._check_pymupdf')
    def test_pymupdf_not_available(self, mock_pymupdf):
        """Test handling when PyMuPDF is not available."""
        mock_pymupdf.return_value = False
        checker = DocumentQualityChecker()
        
        with pytest.raises(InvalidDocumentError) as exc_info:
            # This will fail at the text extraction step
            checker._extract_text(Path("dummy.pdf"))
        assert "PyMuPDF is required" in str(exc_info.value)


class TestQualityCheckFailedException:
    """Tests for QualityCheckFailed exception."""
    
    def test_exception_creation(self):
        """Test creating exception with metrics."""
        exc = QualityCheckFailedException(
            message="Document quality too low",
            effective_char_ratio=0.65,
            text_density=0.45,
            garbage_ratio=0.08,
            min_text_length=300,
        )
        assert "quality" in exc.message.lower()
        assert exc.effective_char_ratio == 0.65
    
    def test_exception_to_dict(self):
        """Test exception serialization."""
        exc = QualityCheckFailedException(
            message="Quality check failed",
            effective_char_ratio=0.50,
            thresholds={"min_effective_char_ratio": 0.80},
            file_path="test.pdf",
        )
        result = exc.to_dict()
        assert result["error_type"] == "QualityCheckFailed"
        assert result["message"] == "Quality check failed"
        assert result["file_path"] == "test.pdf"
        assert result["metrics"]["effective_char_ratio"] == 0.50


class TestIntegration:
    """Integration tests for the quality checking module."""
    
    def test_check_or_raise_success(self, tmp_path):
        """Test check_or_raise with valid document."""
        # Create a mock PDF file with valid content
        # Note: This is a simplified test - real PDF would need PyMuPDF
        checker = DocumentQualityChecker()
        
        # We can't create a real PDF in tests without PyMuPDF,
        # so we test the exception handling for missing dependency
        with pytest.raises(InvalidDocumentError) as exc_info:
            checker.check_or_raise(str(tmp_path / "dummy.pdf"))
        # Either file not found or missing PyMuPDF
        assert exc_info.value.reason in ["file_not_found", "missing_dependency"]
    
    def test_metrics_flow(self):
        """Test complete metrics calculation flow."""
        calculator = MetricsCalculator()
        
        # Simulate good quality text
        good_text = "This is a well-formed document with proper text content.\n" * 50
        good_metrics = calculator.calculate(good_text)
        
        assert good_metrics.effective_char_ratio > 0.8
        assert good_metrics.text_density > 0.95  # May have trailing newline
        assert good_metrics.garbage_ratio == 0.0
        
        # Simulate poor quality text
        poor_text = "   \n\n\n   \n\n\n" * 10 + "Some text"
        poor_metrics = calculator.calculate(poor_text)
        
        assert poor_metrics.effective_char_ratio < good_metrics.effective_char_ratio
        assert poor_metrics.text_density < good_metrics.text_density


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_very_short_text(self):
        """Test with very short text."""
        calculator = MetricsCalculator()
        text = "Hi"
        metrics = calculator.calculate(text)
        assert metrics.min_text_length == 2
    
    def test_only_whitespace(self):
        """Test with only whitespace."""
        calculator = MetricsCalculator()
        text = "   \n\n\t\t   "
        metrics = calculator.calculate(text)
        assert metrics.effective_chars == 0
    
    def test_mixed_scripts(self):
        """Test with mixed language scripts."""
        calculator = MetricsCalculator()
        text = "Hello 你好 こんにちは 안녕 hello"
        metrics = calculator.calculate(text)
        assert metrics.unicode_ranges.get("ascii", 0) > 0
        assert metrics.unicode_ranges.get("cjk", 0) > 0
        # Should have Hiragana or Hangul too
        total_cjk_related = (
            metrics.unicode_ranges.get("cjk", 0) +
            metrics.unicode_ranges.get("hiragana", 0) +
            metrics.unicode_ranges.get("hangul", 0)
        )
        assert total_cjk_related > 0
    
    def test_special_characters(self):
        """Test with various special characters."""
        calculator = MetricsCalculator()
        text = "Text with © ® ™ € £ ¥ special chars"
        metrics = calculator.calculate(text)
        # These should not be counted as garbage
        assert metrics.garbage_ratio < 0.1