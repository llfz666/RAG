"""Test MCP connection directly."""

import asyncio
import sys
from pathlib import Path

# Add agent package to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agent.mcp.client import MCPClient


async def test_connection():
    """Test MCP connection."""
    # Use the same config as settings.yaml
    config = {
        "command": "python",
        "args": ["-m", "src.mcp_server.server"],
        "cwd": "E:/code/MODULAR-RAG-MCP-SERVER",
        "timeout": 120,
    }
    
    print(f"Using config: {config}")
    
    client = MCPClient(config)
    
    try:
        print("Connecting to MCP server...")
        await client.connect(timeout=120)
        print(f"Connected successfully!")
        print(f"Available tools: {client.get_available_tools()}")
        
        # Test calling a tool
        try:
            result = await client.call_tool("list_collections", {})
            print(f"Tool result: {result}")
        except Exception as e:
            print(f"Tool call error: {e}")
        
    except Exception as e:
        print(f"Connection error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    asyncio.run(test_connection())