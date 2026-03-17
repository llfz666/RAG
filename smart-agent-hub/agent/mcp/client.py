"""MCP Client for connecting to MCP Servers.

This client uses stdio transport to communicate with MCP servers.
It can discover available tools and invoke them remotely.

Reference implementation based on ragent project:
https://github.com/nageoffer/ragent

Key differences from standard MCP client:
1. Manual JSON-RPC message handling for better control
2. Background task for reading server responses
3. Proper cleanup of subprocess resources
"""

from __future__ import annotations

import asyncio
import json
import sys
import subprocess
from contextlib import asynccontextmanager
from typing import Any, Optional
from pathlib import Path


class MCPClient:
    """MCP Client - Connects to external MCP Server via stdio.
    
    This implementation manually handles JSON-RPC messaging to have
    better control over the initialization handshake and avoid anyio
    TaskGroup issues.
    """

    def __init__(self, server_config: dict):
        """Initialize MCP Client.

        Args:
            server_config: Server configuration with keys:
                - command: Command to run (e.g., "python")
                - args: Command arguments (e.g., ["main.py"])
                - cwd: Working directory (default: ".")
                - timeout: Connection timeout in seconds (default: 120)
        """
        self.server_config = server_config
        self._process: Optional[subprocess.Popen] = None
        self._tools_cache: list[dict] = []
        self._connected = False
        self._request_id = 0
        self._pending_responses: dict[int, asyncio.Future] = {}
        self._background_task: Optional[asyncio.Task] = None
        self._init_timeout = server_config.get("timeout", 120)
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to server."""
        return self._connected and self._process is not None

    def _next_id(self) -> int:
        """Generate next request ID."""
        self._request_id += 1
        return self._request_id

    def _create_request(self, method: str, params: dict) -> dict:
        """Create JSON-RPC 2.0 request."""
        return {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }

    def _create_notification(self, method: str, params: Optional[dict] = None) -> dict:
        """Create JSON-RPC 2.0 notification (no response expected)."""
        return {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }

    async def _read_loop(self):
        """Background task to read server responses."""
        assert self._process is not None
        assert self._process.stdout is not None
        
        try:
            while True:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self._process.stdout.readline
                )
                if not line:
                    break  # EOF
                    
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    msg = json.loads(line)
                    
                    # Handle response
                    if "id" in msg:
                        request_id = msg["id"]
                        if request_id in self._pending_responses:
                            self._pending_responses[request_id].set_result(msg)
                            del self._pending_responses[request_id]
                    
                    # Handle notification from server (if any)
                    elif "method" in msg:
                        print(f"[DEBUG] Server notification: {msg['method']}", file=sys.stderr)
                        
                except json.JSONDecodeError:
                    print(f"[DEBUG] Invalid JSON from server: {line[:100]}", file=sys.stderr)
                    
        except Exception as e:
            print(f"[DEBUG] Read loop error: {e}", file=sys.stderr)

    async def _send_message(self, msg: dict) -> None:
        """Send message to server."""
        assert self._process is not None
        assert self._process.stdin is not None
        
        line = json.dumps(msg) + "\n"
        await asyncio.get_event_loop().run_in_executor(
            None, self._process.stdin.write, line
        )
        await asyncio.get_event_loop().run_in_executor(
            None, self._process.stdin.flush
        )

    async def _send_request(self, method: str, params: dict, timeout: Optional[float] = None) -> dict:
        """Send request and wait for response."""
        async with self._lock:
            request = self._create_request(method, params)
            request_id = request["id"]
            
            future = asyncio.get_event_loop().create_future()
            self._pending_responses[request_id] = future
            
            await self._send_message(request)
            
            try:
                response = await asyncio.wait_for(future, timeout=timeout)
                
                if "error" in response:
                    raise RuntimeError(f"Server error: {response['error']}")
                
                return response.get("result", {})
                
            except asyncio.TimeoutError:
                del self._pending_responses[request_id]
                raise

    async def connect(self, timeout: Optional[int] = None) -> None:
        """Connect to MCP Server.

        This method:
        1. Starts the MCP server subprocess
        2. Sends initialize request
        3. Sends initialized notification
        4. Fetches available tools
        """
        init_timeout = timeout if timeout is not None else self._init_timeout

        # Resolve cwd to absolute path and validate
        cwd = self.server_config.get("cwd", ".")
        cwd_path = Path(cwd)
        if not cwd_path.is_absolute():
            cwd_path = Path.cwd() / cwd
            cwd_path = cwd_path.resolve()
        
        if not cwd_path.exists():
            raise RuntimeError(f"MCP Server cwd does not exist: {cwd_path}")
        
        if not cwd_path.is_dir():
            raise RuntimeError(f"MCP Server cwd is not a directory: {cwd_path}")
        
        cmd = [self.server_config["command"]] + self.server_config.get("args", [])
        
        print(f"[DEBUG] Starting MCP Server: {' '.join(cmd)}", file=sys.stderr)
        print(f"[DEBUG] Working directory: {cwd_path}", file=sys.stderr)
        
        try:
            # Start subprocess with UTF-8 encoding to handle non-ASCII characters
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace undecodable characters instead of failing
                cwd=str(cwd_path),
            )
            
            print(f"[DEBUG] Process started with PID {self._process.pid}", file=sys.stderr)
            
            # Start background read loop
            self._background_task = asyncio.create_task(self._read_loop())
            
            # Give server a moment to start
            await asyncio.sleep(0.5)
            
            # Send initialize request
            print(f"[DEBUG] Sending initialize request...", file=sys.stderr)
            init_result = await self._send_request(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "clientInfo": {"name": "smart-agent-hub", "version": "0.1.0"},
                    "capabilities": {},
                },
                timeout=init_timeout,
            )
            print(f"[DEBUG] Initialize result: {init_result}", file=sys.stderr)
            
            # Send initialized notification
            print(f"[DEBUG] Sending initialized notification...", file=sys.stderr)
            await self._send_message(self._create_notification("notifications/initialized"))
            
            # Get available tools
            print(f"[DEBUG] Listing tools...", file=sys.stderr)
            tools_result = await self._send_request(
                "tools/list",
                {},
                timeout=30,
            )
            
            self._tools_cache = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "schema": t.get("inputSchema", {}),
                }
                for t in tools_result.get("tools", [])
            ]

            self._connected = True
            print(f"[DEBUG] Connected to MCP Server successfully", file=sys.stderr)
            print(f"[DEBUG] Available tools: {[t['name'] for t in self._tools_cache]}", file=sys.stderr)
            
        except Exception as e:
            print(f"[DEBUG] Connection failed: {e}", file=sys.stderr)
            await self._cleanup_resources()
            raise

    async def _cleanup_resources(self) -> None:
        """Internal cleanup of resources."""
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None
        
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except:
                try:
                    self._process.kill()
                    self._process.wait()
                except:
                    pass
            self._process = None
        
        self._pending_responses.clear()
        self._connected = False
        self._tools_cache = []

    async def disconnect(self) -> None:
        """Disconnect from MCP Server."""
        print(f"[DEBUG] Disconnecting from MCP Server...", file=sys.stderr)
        await self._cleanup_resources()
        print(f"[DEBUG] Disconnected", file=sys.stderr)

    def get_available_tools(self) -> list[dict]:
        """Get list of available tools from the server."""
        return self._tools_cache.copy()

    def get_tool_schema(self, tool_name: str) -> Optional[dict]:
        """Get schema for a specific tool."""
        for tool in self._tools_cache:
            if tool["name"] == tool_name:
                return tool
        return None

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: Optional[int] = None,
    ) -> Any:
        """Call a tool on the server.

        Args:
            name: Tool name.
            arguments: Tool arguments as a dictionary.
            timeout: Call timeout in seconds.

        Returns:
            Tool result content.
        """
        if not self._connected:
            raise RuntimeError("Not connected to MCP Server")

        tool = self.get_tool_schema(name)
        if tool is None:
            available = [t["name"] for t in self._tools_cache]
            raise ValueError(
                f"Unknown tool: {name}. Available tools: {available}"
            )

        timeout = timeout or self.server_config.get("timeout", 60)
        
        result = await self._send_request(
            "tools/call",
            {"name": name, "arguments": arguments},
            timeout=timeout,
        )
        
        return result

    @asynccontextmanager
    async def connection(self):
        """Context manager for connection lifecycle."""
        await self.connect()
        try:
            yield self
        finally:
            await self.disconnect()