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
        max_retries = 3
        retry_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to MCP server: {self.server_url} (attempt {attempt + 1}/{max_retries})")
                self.websocket = await websockets.connect(self.server_url)
                self.connected = True
                logger.info(f"Connected to MCP server: {self.server_url}")
                
                # Start message handler
                asyncio.create_task(self.message_handler())
                
                # Initialize connection and get capabilities
                await self.initialize()
                return
                
            except (ConnectionRefusedError, OSError) as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    logger.error(f"Failed to connect after {max_retries} attempts")
                    self.connected = False
                    raise
            except Exception as e:
                logger.error(f"Unexpected error connecting to MCP server: {e}")
                self.connected = False
                raise
    
    async def message_handler(self):
        """Handle incoming messages from MCP server"""
        try:
            async for message in self.websocket:
                await self.process_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.error("DEBUG: MCP server connection closed unexpectedly!")
            self.connected = False
        except Exception as e:
            logger.error(f"DEBUG: Error in message handler: {e}")
            self.connected = False
    
    async def process_message(self, message: str):
        """Process incoming MCP messages"""
        try:
            logger.info(f"DEBUG: Received message: {message}")
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
                logger.info(f"DEBUG: Checking method: {data.get('method')}")
                if data["method"] == "market_data" and self.market_data_callback:
                    await self.market_data_callback(data["params"])
            
        except json.JSONDecodeError:
            logger.error("Received invalid JSON from MCP server")
        except Exception as e:
            logger.error(f"Error processing MCP message: {e}")
    
    async def send_request(self, method: str, params: Dict[str, Any] = None) -> Any:
        """Send MCP request and wait for response"""
        if not self.connected or not self.websocket:
            logger.error(f"Cannot send {method} request: not connected to MCP server")
            raise Exception("Not connected to MCP server")
            
        logger.debug(f"Sending MCP request: {method}")
        
        request_id = str(uuid.uuid4())
        request = {
            "jsonrpc": "2.0",
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
            logger.debug(f"MCP request {method} completed successfully")
            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            logger.error(f"MCP request {method} timed out after 30 seconds")
            raise Exception(f"MCP request {method} timeout")
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            logger.error(f"MCP request {method} failed: {e}")
            raise
    
    async def initialize(self):
        """Initialize MCP connection and get server capabilities"""
        try:
            # Send proper MCP initialization
            result = await self.send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {"sampling": {}},
                "clientInfo": {"name": "qwen-trading-client", "version": "1.0.0"}
            })
            
            logger.info(f"MCP server initialized: {result.get('serverInfo', {})}")
            
            # Send initialized notification
            await self.send_notification("notifications/initialized", {})
            
            # Get available tools
            tools_result = await self.send_request("tools/list", {})
            if "tools" in tools_result:
                self.tools = [
                    MCPTool(**tool_data) 
                    for tool_data in tools_result["tools"]
                ]
                logger.info(f"Available tools: {[tool.name for tool in self.tools]}")
            else:
                logger.warning("No tools available from MCP server")
                
        except Exception as e:
            logger.error(f"MCP initialization failed: {e}")
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on the MCP server"""
        logger.info(f"DEBUG: ===== MCP CLIENT TOOL CALL =====")
        logger.info(f"DEBUG: Calling tool '{tool_name}' with arguments: {arguments}")
        
        result = await self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        logger.info(f"DEBUG: MCP server returned result: {result}")
        return result.get("content", "")
    
    def set_market_data_callback(self, callback: callable):
        """Set callback for market data notifications"""
        self.market_data_callback = callback
    
    async def send_notification(self, method: str, params: Dict[str, Any]):
        """Send MCP notification (no response expected)"""
        if not self.connected or not self.websocket:
            return
            
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        
        try:
            await self.websocket.send(json.dumps(notification))
            logger.debug(f"Sent MCP notification: {method}")
        except Exception as e:
            logger.error(f"Failed to send notification {method}: {e}")
    
    async def disconnect(self):
        """Disconnect from MCP server"""
        if self.websocket:
            try:
                await self.websocket.close()
                logger.info("Disconnected from MCP server")
            except Exception as e:
                logger.error(f"Error disconnecting from MCP server: {e}")
        self.connected = False
