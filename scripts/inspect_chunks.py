#!/usr/bin/env python
"""Inspect chunks in ChromaDB to analyze data distribution.

This script helps debug retrieval issues by showing:
1. All chunks in a collection
2. Chunks matching specific keywords
3. How data is distributed across chunks
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.settings import load_settings
from src.libs.vector_store.vector_store_factory import VectorStoreFactory


def main():
    parser = argparse.ArgumentParser(description="Inspect ChromaDB chunks")
    parser.add_argument(
        "--collection",
        type=str,
        default="default",
        help="Collection name to inspect"
    )
    parser.add_argument(
        "--keyword",
        type=str,
        default=None,
        help="Optional keyword to filter chunks"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum chunks to display"
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show all chunk content without truncation"
    )
    args = parser.parse_args()
    
    # Load settings
    settings = load_settings()
    
    # Get vector store
    vector_store = VectorStoreFactory.create(settings, collection_name=args.collection)
    
    print(f"\n{'='*60}")
    print(f"Inspecting collection: {args.collection}")
    print(f"{'='*60}\n")
    
    # Get all chunks or filtered by keyword
    # First we need to get the embedding for the query
    from src.libs.embedding.embedding_factory import EmbeddingFactory
    
    embedding_client = EmbeddingFactory.create(settings)
    
    try:
        # Try to get all records
        if args.keyword:
            print(f"Searching for keyword: {args.keyword}\n")
            # Get embedding for query
            query_embedding = embedding_client.embed_query(args.keyword)
            results = vector_store.query(
                vector=query_embedding,
                top_k=args.limit,
            )
        else:
            # Get all by querying with empty string
            query_embedding = embedding_client.embed_query("")
            results = vector_store.query(
                vector=query_embedding,
                top_k=args.limit,
            )
    except Exception as e:
        print(f"Error querying ChromaDB: {e}")
        import traceback
        traceback.print_exc()
        return
    
    if not results:
        print("No chunks found in collection.")
        return
    
    print(f"Found {len(results)} chunks:\n")
    print("-" * 60)
    
    for i, result in enumerate(results):
        chunk_id = result.get('id', 'unknown')
        text = result.get('text', '')
        metadata = result.get('metadata', {})
        distance = result.get('distance', 0)
        
        # Truncate text if not --show-all
        if not args.show_all and len(text) > 300:
            display_text = text[:300] + "..."
        else:
            display_text = text
        
        print(f"\n[Chunk {i+1}] {chunk_id}")
        print(f"  Distance: {distance:.4f}")
        print(f"  Metadata:")
        for key, value in metadata.items():
            print(f"    {key}: {value}")
        print(f"  Content:\n{display_text}")
        print("-" * 60)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total chunks shown: {len(results)}")
    
    # Check for specific patterns
    投保人_chunks = [r for r in results if '投保人' in r.get('text', '')]
    if 投保人_chunks:
        print(f"  Chunks containing '投保人': {len(投保人_chunks)}")
        for chunk in 投保人_chunks:
            text = chunk.get('text', '')
            # Extract 投保 人 numbers
            import re
            matches = re.findall(r'投保人 (\d+)', text)
            if matches:
                print(f"    - 投保人 {', '.join(matches)}")


if __name__ == "__main__":
    main()
