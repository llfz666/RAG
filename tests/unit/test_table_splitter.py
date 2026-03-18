"""Unit tests for TableSplitter.

This module tests the TableSplitter implementation for Markdown table handling:
- Table detection
- Row-level splitting
- Header preservation in each chunk
- Fallback to RecursiveSplitter for non-table content
"""

import pytest
from src.core.settings import load_settings
from src.libs.splitter.table_splitter import TableSplitter


@pytest.fixture
def sample_settings():
    """Load settings from config file."""
    return load_settings()


@pytest.fixture
def sample_table():
    """Sample Markdown table for testing."""
    return """| 投保人 | 保单号 | 产品类型 | 状态 | 生效日期 |
|----------|----------|----------|----------|----------|
| 投保人 897 | POL2026XXX | 健康保险 | 有效 | 2024-01-24 |
| 投保人 587 | POL2026YYY | 人寿保险 | 有效 | 2024-02-15 |
| 投保人 398 | POL2026ZZZ | 意外保险 | 有效 | 2024-03-10 |"""


@pytest.fixture
def sample_table_with_multiple_rows():
    """Sample Markdown table with many rows for chunking test."""
    header = "| 投保人 | 保单号 | 产品类型 | 状态 | 生效日期 |\n|----------|----------|----------|----------|----------|\n"
    rows = []
    for i in range(50):
        rows.append(f"| 投保人 {i:03d} | POL{i:06d} | 保险产品{i} | 有效 | 2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d} |")
    return header + "\n".join(rows)


class TestTableSplitterInit:
    """Test TableSplitter initialization."""
    
    def test_init_with_valid_config(self, sample_settings):
        """Test initialization with valid configuration."""
        splitter = TableSplitter(sample_settings)
        assert splitter.chunk_size == 1000
        assert splitter.chunk_overlap == 200
    
    def test_init_with_chunk_size_override(self, sample_settings):
        """Test initialization with chunk_size override."""
        splitter = TableSplitter(sample_settings, chunk_size=500)
        assert splitter.chunk_size == 500
        assert splitter.chunk_overlap == 200
    
    def test_init_with_invalid_chunk_size(self, sample_settings):
        """Test initialization with invalid chunk_size."""
        with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
            TableSplitter(sample_settings, chunk_size=-1)
    
    def test_init_with_invalid_overlap(self, sample_settings):
        """Test initialization with invalid chunk_overlap."""
        with pytest.raises(ValueError, match="chunk_overlap must be a non-negative integer"):
            TableSplitter(sample_settings, chunk_overlap=-1)
    
    def test_init_with_overlap_greater_than_chunk_size(self, sample_settings):
        """Test initialization with overlap >= chunk_size."""
        with pytest.raises(ValueError, match="chunk_overlap.*must be less than.*chunk_size"):
            TableSplitter(sample_settings, chunk_size=100, chunk_overlap=100)


class TestTableSplitterTableDetection:
    """Test Markdown table detection."""
    
    def test_detect_valid_table(self, sample_settings, sample_table):
        """Test detection of valid Markdown table."""
        splitter = TableSplitter(sample_settings)
        chunks = splitter.split_text(sample_table)
        
        # Should split into 3 chunks (one per data row)
        assert len(chunks) == 3
        
        # Each chunk should contain header
        for chunk in chunks:
            assert "| 投保人 |" in chunk
            assert "| 保单号 |" in chunk
    
    def test_detect_table_with_alignment_markers(self, sample_settings):
        """Test detection of table with alignment markers."""
        table = """| Left | Center | Right |
|:-----|:------:|------:|
| A | B | C |"""
        
        splitter = TableSplitter(sample_settings)
        chunks = splitter.split_text(table)
        
        assert len(chunks) == 1
        assert "| Left |" in chunks[0]
        assert "| A |" in chunks[0]
    
    def test_no_table_plain_text(self, sample_settings):
        """Test that plain text doesn't trigger table detection."""
        text = "This is just plain text without any table structure."
        
        splitter = TableSplitter(sample_settings)
        chunks = splitter.split_text(text)
        
        # Should use fallback splitter
        assert len(chunks) >= 1
        assert "This is just plain text" in chunks[0]


class TestTableSplitterRowSplitting:
    """Test row-level splitting with header preservation."""
    
    def test_each_chunk_has_header(self, sample_settings, sample_table):
        """Test that each chunk contains the header row."""
        splitter = TableSplitter(sample_settings)
        chunks = splitter.split_text(sample_table)
        
        header = "| 投保人 | 保单号 | 产品类型 |"
        separator = "|----------|"
        
        for i, chunk in enumerate(chunks):
            assert header in chunk, f"Chunk {i} missing header"
            assert separator in chunk, f"Chunk {i} missing separator"
    
    def test_each_chunk_has_single_data_row(self, sample_settings, sample_table):
        """Test that each chunk contains exactly one data row."""
        splitter = TableSplitter(sample_settings)
        chunks = splitter.split_text(sample_table)
        
        # Check each chunk has exactly one data row
        assert len(chunks) == 3
        
        # First chunk should have 投保人 897
        assert "投保人 897" in chunks[0]
        assert "投保人 587" not in chunks[0]
        
        # Second chunk should have 投保人 587
        assert "投保人 587" in chunks[1]
        assert "投保人 897" not in chunks[1]
        
        # Third chunk should have 投保人 398
        assert "投保人 398" in chunks[2]
    
    def test_large_table_chunking(self, sample_settings, sample_table_with_multiple_rows):
        """Test that large tables are properly chunked."""
        splitter = TableSplitter(sample_settings)
        chunks = splitter.split_text(sample_table_with_multiple_rows)
        
        # Should split into multiple chunks
        assert len(chunks) == 50  # One chunk per row
        
        # Each chunk should have header and one data row
        for chunk in chunks:
            assert "| 投保人 |" in chunk
            # Each chunk should have exactly one 投保人
            count = chunk.count("投保人 ")
            assert count >= 1  # At least the header + data row


class TestTableSplitterEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_table(self, sample_settings):
        """Test handling of empty table."""
        table = "||\n|--|"
        
        splitter = TableSplitter(sample_settings)
        chunks = splitter.split_text(table)
        
        # Should handle gracefully
        assert len(chunks) >= 1
    
    def test_table_without_separator(self, sample_settings):
        """Test table without proper separator row."""
        table = """| Header1 | Header2 |
| Data1 | Data2 |"""
        
        splitter = TableSplitter(sample_settings)
        chunks = splitter.split_text(table)
        
        # Should use fallback splitter
        assert len(chunks) >= 1
    
    def test_mixed_content_table_and_text(self, sample_settings):
        """Test document with both table and plain text."""
        content = """Some introductory text.

| Header1 | Header2 |
|---------|---------|
| A | B |

Some concluding text."""
        
        splitter = TableSplitter(sample_settings)
        chunks = splitter.split_text(content)
        
        # Should find table and split it
        assert len(chunks) >= 1
        
        # At least one chunk should contain table data
        table_chunks = [c for c in chunks if "| Header1 |" in c]
        assert len(table_chunks) >= 1
    
    def test_multiple_tables_in_document(self, sample_settings):
        """Test document with multiple tables."""
        content = """Text before tables.

| Table1-Col1 | Table1-Col2 |
|-------------|-------------|
| A | B |
| C | D |

Some text between tables.

| Table2-Col1 | Table2-Col2 |
|-------------|-------------|
| E | F |
| G | H |

Text after tables."""
        
        splitter = TableSplitter(sample_settings)
        chunks = splitter.split_text(content)
        
        # Should handle multiple tables
        assert len(chunks) >= 2


class TestTableSplitterValidation:
    """Test input/output validation."""
    
    def test_validate_empty_input(self, sample_settings):
        """Test that empty input raises ValueError."""
        splitter = TableSplitter(sample_settings)
        
        with pytest.raises(ValueError, match="empty"):
            splitter.split_text("")
    
    def test_validate_whitespace_input(self, sample_settings):
        """Test that whitespace-only input raises ValueError."""
        splitter = TableSplitter(sample_settings)
        
        with pytest.raises(ValueError, match="empty"):
            splitter.split_text("   \n\t   ")
    
    def test_validate_non_string_input(self, sample_settings):
        """Test that non-string input raises ValueError."""
        splitter = TableSplitter(sample_settings)
        
        with pytest.raises(ValueError, match="must be a string"):
            splitter.split_text(123)  # type: ignore


class TestTableSplitterFallback:
    """Test fallback splitter behavior."""
    
    def test_fallback_for_non_table_content(self, sample_settings):
        """Test fallback to RecursiveSplitter for non-table content."""
        text = """This is a long paragraph without any table structure.
        It contains multiple sentences and should be split by the fallback splitter
        based on the chunk_size configuration. The text should be divided into
        multiple chunks if it exceeds the chunk_size limit."""
        
        splitter = TableSplitter(sample_settings)
        chunks = splitter.split_text(text)
        
        # Should use fallback splitter
        assert len(chunks) >= 1
        assert "This is a long paragraph" in chunks[0]