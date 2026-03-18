"""Table Splitter for Markdown-formatted tables.

This module implements a specialized text splitter for Markdown tables,
ensuring that each table row remains intact as a single chunk. This is
critical for structured data (Excel exports, CSV, database results) where
row-level integrity must be preserved for accurate retrieval.

Key Features:
- Detects Markdown tables automatically
- Splits by row, keeping header + separator + data row together
- Handles multiple tables in the same document
- Falls back to RecursiveSplitter for non-table content
- Preserves metadata about table structure
"""

from __future__ import annotations

import logging
import re
from typing import Any, List, Optional, Tuple

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None  # type: ignore[misc, assignment]

from src.core.settings import Settings
from src.libs.splitter.base_splitter import BaseSplitter

logger = logging.getLogger(__name__)


class TableSplitter(BaseSplitter):
    """Specialized splitter for Markdown-formatted tables.
    
    This splitter detects Markdown tables and splits them by rows, ensuring
    each row (with header) remains intact. This is essential for structured
    data retrieval where row-level context is required.
    
    Table Format Example:
        | Header 1 | Header 2 | Header 3 |
        |----------|----------|----------|
        | Row1-Col1| Row1-Col2| Row1-Col3|
        | Row2-Col1| Row2-Col2| Row2-Col3|
    
    Each output chunk contains:
        | Header 1 | Header 2 | Header 3 |
        |----------|----------|----------|
        | RowX-Col1| RowX-Col2| RowX-Col3|
    
    Design Principles Applied:
    - Pluggable: Implements BaseSplitter interface for factory registration.
    - Config-Driven: Reads chunk_size and chunk_overlap from settings.
    - Fail-Fast: Validates inputs and provides clear error messages.
    - Graceful Degradation: Falls back to RecursiveSplitter for non-table content.
    
    Attributes:
        chunk_size: Maximum size of each chunk in characters.
        chunk_overlap: Number of overlapping characters between chunks.
        fallback_splitter: RecursiveSplitter instance for non-table content.
    """
    
    # Regex pattern to detect Markdown tables
    # Matches: header row, separator row, and data rows
    TABLE_PATTERN = re.compile(
        r'^(\|.*\|\n)'           # Header row
        r'^(\|[-:]+\|.*\n)'      # Separator row (with alignment markers)
        r'((?:\|.*\|\n?)+)',     # Data rows (one or more)
        re.MULTILINE
    )
    
    # Pattern to match a complete table block
    TABLE_BLOCK_PATTERN = re.compile(
        r'(\|[^|\n]+\|[^|\n]*\|.*\n)'  # Header row
        r'(\|[-:| ]+\|[-:| ]*\|.*\n)'  # Separator row
        r'((?:\|[^|\n]+\|[^|\n]*\|.*\n?)*)',  # Data rows
        re.MULTILINE
    )
    
    def __init__(
        self,
        settings: Settings,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize TableSplitter.
        
        Args:
            settings: Application settings containing ingestion configuration.
            chunk_size: Optional override for chunk size (defaults to settings.ingestion.chunk_size).
            chunk_overlap: Optional override for overlap (defaults to settings.ingestion.chunk_overlap).
            **kwargs: Additional parameters (currently unused).
        
        Raises:
            ImportError: If langchain-text-splitters is not installed (for fallback).
            ValueError: If chunk_size or chunk_overlap is invalid.
        """
        self.settings = settings
        
        # Extract configuration from settings with overrides
        try:
            ingestion_config = settings.ingestion
            self.chunk_size = chunk_size if chunk_size is not None else ingestion_config.chunk_size
            self.chunk_overlap = chunk_overlap if chunk_overlap is not None else ingestion_config.chunk_overlap
        except AttributeError as e:
            raise ValueError(
                "Missing ingestion configuration in settings. "
                "Expected settings.ingestion.chunk_size and settings.ingestion.chunk_overlap"
            ) from e
        
        # Validate configuration
        if not isinstance(self.chunk_size, int) or self.chunk_size <= 0:
            raise ValueError(f"chunk_size must be a positive integer, got: {self.chunk_size}")
        
        if not isinstance(self.chunk_overlap, int) or self.chunk_overlap < 0:
            raise ValueError(f"chunk_overlap must be a non-negative integer, got: {self.chunk_overlap}")
        
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be less than "
                f"chunk_size ({self.chunk_size})"
            )
        
        # Initialize fallback splitter for non-table content
        self._init_fallback_splitter()
        
        logger.info(
            f"TableSplitter initialized with chunk_size={self.chunk_size}, "
            f"chunk_overlap={self.chunk_overlap}"
        )
    
    def _init_fallback_splitter(self) -> None:
        """Initialize fallback RecursiveSplitter for non-table content."""
        if RecursiveCharacterTextSplitter is None:
            logger.warning(
                "langchain-text-splitters not available. "
                "TableSplitter will use simple line-based splitting as fallback."
            )
            self._fallback_splitter = None
        else:
            self._fallback_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", ". ", " ", ""],
                length_function=len,
                is_separator_regex=False,
            )
    
    def split_text(
        self,
        text: str,
        trace: Optional[Any] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Split text into chunks, preserving table row integrity.
        
        This method:
        1. Detects Markdown tables in the text
        2. For each table, splits by row (header + separator + data row)
        3. For non-table content, uses fallback splitter
        
        Args:
            text: Input text to split. Must be a non-empty string.
            trace: Optional TraceContext for observability (reserved for Stage F).
            **kwargs: Additional parameters (currently unused).
        
        Returns:
            List of text chunks. Table rows are kept intact, each containing
            header + separator + single data row for context.
        
        Raises:
            ValueError: If input text is invalid.
            RuntimeError: If splitting fails unexpectedly.
        """
        # Validate input
        self.validate_text(text)
        
        try:
            # Try to detect and split tables
            chunks = self._split_tables(text)
            
            # If no tables found, use fallback splitter
            if not chunks:
                logger.debug("No tables detected, using fallback splitter")
                chunks = self._fallback_split(text)
            
            # Handle edge case: empty chunks
            if not chunks:
                chunks = [text]
            
            # Validate output
            self.validate_chunks(chunks)
            
            logger.debug(f"Split text into {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            # Catch any errors and provide context
            raise RuntimeError(
                f"TableSplitter failed to split text: {e}. "
                f"Text length: {len(text)}, chunk_size: {self.chunk_size}, "
                f"chunk_overlap: {self.chunk_overlap}"
            ) from e
    
    def _split_tables(self, text: str) -> List[str]:
        """Detect and split Markdown tables into row-level chunks.
        
        Args:
            text: Input text potentially containing Markdown tables.
        
        Returns:
            List of chunks, each containing header + separator + data row.
            Empty list if no tables detected.
        """
        chunks = []
        
        # Find all table blocks in the text
        table_blocks = self._find_table_blocks(text)
        
        if not table_blocks:
            return []
        
        logger.debug(f"Found {len(table_blocks)} table blocks in text")
        
        for table_block in table_blocks:
            table_chunks = self._split_table_block(table_block)
            chunks.extend(table_chunks)
        
        return chunks
    
    def _find_table_blocks(self, text: str) -> List[str]:
        """Find all Markdown table blocks in text.
        
        Args:
            text: Input text to search for tables.
        
        Returns:
            List of table block strings.
        """
        table_blocks = []
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Check if line looks like table header (starts and ends with |)
            if line.startswith('|') and line.endswith('|'):
                # Check if next line is separator row
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if self._is_table_separator(next_line):
                        # Found a table, collect all rows
                        table_lines = [lines[i], lines[i + 1]]
                        j = i + 2
                        
                        while j < len(lines):
                            data_line = lines[j].strip()
                            if data_line.startswith('|') and data_line.endswith('|'):
                                table_lines.append(lines[j])
                                j += 1
                            else:
                                break
                        
                        table_blocks.append('\n'.join(table_lines))
                        i = j
                        continue
            
            i += 1
        
        return table_blocks
    
    def _is_table_separator(self, line: str) -> bool:
        """Check if a line is a Markdown table separator row.
        
        Separator row format: |---|---|---| or | :---: | ---: | :--- |
        
        Args:
            line: Line to check.
        
        Returns:
            True if line is a valid table separator.
        """
        line = line.strip()
        if not line.startswith('|') or not line.endswith('|'):
            return False
        
        # Remove leading/trailing | and split by |
        cells = [c.strip() for c in line[1:-1].split('|')]
        
        if not cells:
            return False
        
        # Each cell should contain only -, :, and spaces
        separator_pattern = re.compile(r'^[-:\s]+$')
        
        for cell in cells:
            if not cell or not separator_pattern.match(cell):
                return False
        
        return True
    
    def _split_table_block(self, table_block: str) -> List[str]:
        """Split a single table block into row-level chunks.
        
        Each chunk contains: header + separator + one data row
        
        Args:
            table_block: Complete table block string.
        
        Returns:
            List of chunks, each with header + separator + data row.
        """
        lines = table_block.split('\n')
        
        if len(lines) < 3:
            # Invalid table (needs header, separator, at least one data row)
            logger.warning(f"Invalid table block (too few lines): {len(lines)} lines")
            return [table_block] if table_block.strip() else []
        
        header = lines[0]
        separator = lines[1]
        data_rows = lines[2:]
        
        chunks = []
        
        for row in data_rows:
            if row.strip():
                # Create chunk with header + separator + data row
                chunk = f"{header}\n{separator}\n{row}"
                chunks.append(chunk)
        
        logger.debug(f"Split table into {len(chunks)} row chunks")
        return chunks
    
    def _fallback_split(self, text: str) -> List[str]:
        """Use fallback splitter for non-table content.
        
        Args:
            text: Input text to split.
        
        Returns:
            List of chunks from fallback splitter.
        """
        if self._fallback_splitter is None:
            # Simple line-based splitting as last resort
            lines = text.split('\n')
            chunks = []
            current_chunk = ""
            
            for line in lines:
                if len(current_chunk) + len(line) <= self.chunk_size:
                    current_chunk += line + "\n"
                else:
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                    current_chunk = line + "\n"
            
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            
            return chunks
        else:
            return self._fallback_splitter.split_text(text)
    
    def _parse_table_row(self, row: str) -> List[str]:
        """Parse a Markdown table row into cell values.
        
        Args:
            row: Table row string (e.g., "| Cell 1 | Cell 2 |").
        
        Returns:
            List of cell values.
        """
        row = row.strip()
        if not row.startswith('|') or not row.endswith('|'):
            return [row]
        
        # Remove leading/trailing | and split
        cells = [c.strip() for c in row[1:-1].split('|')]
        return cells