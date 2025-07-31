import asyncio
import json
import uuid
import websockets
from typing import Dict, Any, List, Optional
import logging

from shared.mcp_types import MCPRequest, MCPResponse, MCPTool

logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.tools: List[MCPTool] = []
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.connected = False
        self.market_data_callback: Optional[callable] = None
    
    async def connect(self):
        """Connect to MCP server"""
        try:
            self.websocket = await websockets.connect(self.server_url)
            self.connected = True
            logger.info(f"Connected to MCP server: {self.server_url}")
            
            # Start message handler
            asyncio.create_task(self.message_handler())
            
            # Initialize connection and get capabilities
            await self.initialize()
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            self.connected = False
            raise
    
    async def message_handler(self):
        """Handle incoming messages from MCP server"""
        try:
            async for message in self.websocket:
                await self.process_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.info("MCP server connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
            self.connected = False
    
    async def process_message(self, message: str):
        """Process incoming MCP messages"""
        try:
            data = json.loads(message)
            
            # Handle responses to our requests
            if "id" in data and data["id"] in self.pending_requests:
                future = self.pending_requests.pop(data["id"])
                if "error" in data and data["error"]:
                    future.set_exception(Exception(data["error"]["message"]))
                else:
                    future.set_result(data.get("result"))
            
            # Handle notifications (like market data)
            elif "method" in data:
                if data["method"] == "market_data" and self.market_data_callback:
                    await self.market_data_callback(data["params"])
            
        except json.JSONDecodeError:
            logger.error("Received invalid JSON from MCP server")
        except Exception as e:
            logger.error(f"Error processing MCP message: {e}")
    
    async def send_request(self, method: str, params: Dict[str, Any] = None) -> Any:
        """Send MCP request and wait for response"""
        if not self.connected or not self.websocket:
            raise Exception("Not connected to MCP server")
        
        request_id = str(uuid.uuid4())
        request = {
            "id": request_id,
            "method": method,
            "params": params or {}
        }
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        # Send request
        await self.websocket.send(json.dumps(request))
        
        # Wait for response
        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise Exception("MCP request timeout")
    
    async def initialize(self):
        """Initialize MCP connection and get server capabilities"""
        result = await self.send_request("initialize", {"version": "1.0"})
        
        # Extract available tools
        if "capabilities" in result and "tools" in result["capabilities"]:
            self.tools = [
                MCPTool(**tool_data) 
                for tool_data in result["capabilities"]["tools"]
            ]
            logger.info(f"Available tools: {[tool.name for tool in self.tools]}")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on the MCP server"""
        result = await self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        return result.get("content", "")
    
    def set_market_data_callback(self, callback: callable):
        """Set callback for market data notifications"""
        self.market_data_callback = callback
    
    async def disconnect(self):
        """Disconnect from MCP server"""
        if self.websocket:
            await self.websocket.close()
        self.connected = False
