"""Quality metrics calculation for document quality checking."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class QualityMetrics:
    """Quality metrics calculated from document text.
    
    This class holds all the metrics calculated during quality assessment.
    
    Attributes:
        total_chars: Total number of characters in the text
        effective_chars: Number of non-whitespace characters
        effective_char_ratio: Ratio of effective characters to total
        total_lines: Total number of lines
        empty_lines: Number of empty/whitespace-only lines
        text_density: Ratio of non-empty lines to total lines
        garbage_chars: Number of detected garbage/scrambled characters
        garbage_ratio: Ratio of garbage characters to effective characters
        min_text_length: Minimum text length across analyzed pages
        avg_line_length: Average line length
        unicode_ranges: Distribution of characters by Unicode range
    """
    
    total_chars: int = 0
    effective_chars: int = 0
    effective_char_ratio: float = 0.0
    total_lines: int = 0
    empty_lines: int = 0
    text_density: float = 0.0
    garbage_chars: int = 0
    garbage_ratio: float = 0.0
    min_text_length: int = 0
    avg_line_length: float = 0.0
    unicode_ranges: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_chars": self.total_chars,
            "effective_chars": self.effective_chars,
            "effective_char_ratio": self.effective_char_ratio,
            "total_lines": self.total_lines,
            "empty_lines": self.empty_lines,
            "text_density": self.text_density,
            "garbage_chars": self.garbage_chars,
            "garbage_ratio": self.garbage_ratio,
            "min_text_length": self.min_text_length,
            "avg_line_length": self.avg_line_length,
            "unicode_ranges": self.unicode_ranges,
        }


@dataclass
class QualityCheckResult:
    """Result of a document quality check.
    
    Attributes:
        passed: Whether the document passed the quality check
        file_path: Path to the checked file
        pages_analyzed: Number of pages analyzed
        text_extracted: The text extracted from analyzed pages
        metrics: Calculated quality metrics
        failures: List of failed checks with details
        details: Human-readable detailed report
        warnings: List of warnings (non-fatal issues)
    """
    
    passed: bool = True
    file_path: str = ""
    pages_analyzed: int = 0
    text_extracted: str = ""
    metrics: QualityMetrics = field(default_factory=QualityMetrics)
    failures: List[Dict[str, Any]] = field(default_factory=list)
    details: str = ""
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "passed": self.passed,
            "file_path": self.file_path,
            "pages_analyzed": self.pages_analyzed,
            "metrics": self.metrics.to_dict(),
            "failures": self.failures,
            "details": self.details,
            "warnings": self.warnings,
        }


class MetricsCalculator:
    """Calculator for document quality metrics."""
    
    # Garbage character patterns
    # These patterns detect scrambled text, encoding errors, or non-text content
    GARBAGE_PATTERNS = [
        # Replacement character
        r'\ufffd',  # 
        # Control characters (except newline, tab, carriage return)
        r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]',
        # Unicode private use area
        r'[\ue000-\uf8ff]',
        # Special Unicode symbols that often indicate garbage
        r'[\u2066-\u2069]',  # Isolating controls
        # Excessive consecutive special characters
        r'[^\w\s\u4e00-\u9fff]{5,}',  # 5+ consecutive special chars
    ]
    
    # Valid text patterns (for reference)
    VALID_TEXT_RANGES = [
        # Basic Latin (ASCII printable)
        (0x0020, 0x007E),
        # Latin-1 Supplement (printable)
        (0x00A0, 0x00FF),
        # Latin Extended
        (0x0100, 0x024F),
        # CJK Unified Ideographs
        (0x4E00, 0x9FFF),
        # CJK Radicals Supplement
        (0x2E80, 0x2EFF),
        # CJK Strokes
        (0x31C0, 0x31EF),
        # Hiragana
        (0x3040, 0x309F),
        # Katakana
        (0x30A0, 0x30FF),
        # Hangul
        (0xAC00, 0xD7AF),
        # General Punctuation
        (0x2000, 0x206F),
        # CJK Symbols and Punctuation
        (0x3000, 0x303F),
    ]
    
    def __init__(self):
        """Initialize the metrics calculator."""
        self._compiled_patterns = [
            re.compile(pattern) for pattern in self.GARBAGE_PATTERNS
        ]
    
    def calculate(self, text: str) -> QualityMetrics:
        """Calculate all quality metrics for the given text.
        
        Args:
            text: The text to analyze.
            
        Returns:
            QualityMetrics with all calculated values.
        """
        if not text:
            return QualityMetrics()
        
        metrics = QualityMetrics()
        
        # Basic character counts
        metrics.total_chars = len(text)
        metrics.effective_chars = len(text.replace(' ', '').replace('\n', '').replace('\r', '').replace('\t', ''))
        
        # Effective character ratio
        if metrics.total_chars > 0:
            metrics.effective_char_ratio = metrics.effective_chars / metrics.total_chars
        
        # Line analysis
        lines = text.split('\n')
        metrics.total_lines = len(lines)
        metrics.empty_lines = sum(1 for line in lines if not line.strip())
        
        # Text density
        if metrics.total_lines > 0:
            metrics.text_density = (metrics.total_lines - metrics.empty_lines) / metrics.total_lines
        
        # Garbage character detection
        metrics.garbage_chars = self._count_garbage_chars(text)
        if metrics.effective_chars > 0:
            metrics.garbage_ratio = metrics.garbage_chars / metrics.effective_chars
        
        # Minimum text length (for single text input, it's the total length)
        metrics.min_text_length = len(text)
        
        # Average line length
        non_empty_lines = [line for line in lines if line.strip()]
        if non_empty_lines:
            metrics.avg_line_length = sum(len(line) for line in non_empty_lines) / len(non_empty_lines)
        
        # Unicode range distribution
        metrics.unicode_ranges = self._analyze_unicode_ranges(text)
        
        return metrics
    
    def _count_garbage_chars(self, text: str) -> int:
        """Count garbage/scrambled characters in text."""
        garbage_count = 0
        
        # Count matches from garbage patterns
        for pattern in self._compiled_patterns:
            matches = pattern.findall(text)
            garbage_count += len(''.join(matches))
        
        return garbage_count
    
    def _analyze_unicode_ranges(self, text: str) -> Dict[str, int]:
        """Analyze the distribution of characters across Unicode ranges."""
        ranges = {
            "ascii": 0,
            "latin": 0,
            "cjk": 0,
            "hiragana": 0,
            "katakana": 0,
            "hangul": 0,
            "punctuation": 0,
            "symbols": 0,
            "control": 0,
            "other": 0,
        }
        
        for char in text:
            code = ord(char)
            
            if char in '\n\r\t ':
                continue  # Skip whitespace
            
            # ASCII
            if 0x0020 <= code <= 0x007E:
                ranges["ascii"] += 1
            # Latin-1 Supplement
            elif 0x00A0 <= code <= 0x00FF:
                ranges["latin"] += 1
            # Latin Extended
            elif 0x0100 <= code <= 0x024F:
                ranges["latin"] += 1
            # CJK
            elif 0x4E00 <= code <= 0x9FFF or 0x2E80 <= code <= 0x31EF:
                ranges["cjk"] += 1
            # Hiragana
            elif 0x3040 <= code <= 0x309F:
                ranges["hiragana"] += 1
            # Katakana
            elif 0x30A0 <= code <= 0x30FF:
                ranges["katakana"] += 1
            # Hangul
            elif 0xAC00 <= code <= 0xD7AF:
                ranges["hangul"] += 1
            # Punctuation
            elif 0x2000 <= code <= 0x206F or 0x3000 <= code <= 0x303F:
                ranges["punctuation"] += 1
            # Symbols
            elif 0x20A0 <= code <= 0x20CF or 0x2100 <= code <= 0x214F:
                ranges["symbols"] += 1
            # Control characters
            elif code < 0x0020 or 0x007F <= code <= 0x009F:
                ranges["control"] += 1
            else:
                ranges["other"] += 1
        
        return ranges
    
    def check_text_validity(self, text: str) -> tuple[bool, List[str]]:
        """Check if text is valid and identify issues.
        
        Args:
            text: The text to validate.
            
        Returns:
            Tuple of (is_valid, list_of_issues).
        """
        issues = []
        metrics = self.calculate(text)
        
        # Check effective character ratio
        if metrics.effective_char_ratio < 0.5:
            issues.append(f"Effective character ratio too low: {metrics.effective_char_ratio:.2%}")
        
        # Check text density
        if metrics.text_density < 0.3:
            issues.append(f"Text density too low: {metrics.text_density:.2%}")
        
        # Check garbage ratio
        if metrics.garbage_ratio > 0.1:
            issues.append(f"Garbage ratio too high: {metrics.garbage_ratio:.2%}")
        
        # Check for replacement characters
        if '\ufffd' in text:
            count = text.count('\ufffd')
            issues.append(f"Found {count} replacement characters ()")
        
        # Check for excessive control characters
        if metrics.unicode_ranges.get("control", 0) > metrics.effective_chars * 0.05:
            issues.append("Excessive control characters detected")
        
        return len(issues) == 0, issues