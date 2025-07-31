import asyncio
import json
import uuid
from typing import Dict, Any, Callable, Optional, List
from websockets.server import serve
from websockets.exceptions import ConnectionClosed
import logging

from shared.mcp_types import MCPRequest, MCPResponse, MCPTool, MCPCapabilities

logger = logging.getLogger(__name__)

class MCPProtocolHandler:
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.tool_definitions: List[MCPTool] = []
        self.clients = set()
        self.agent_response_callback: Optional[Callable] = None
        
    def register_tool(self, name: str, description: str, inputSchema: Dict[str, Any], handler: Callable):
        """Register a tool with the MCP server"""
        tool = MCPTool(name=name, description=description, inputSchema=inputSchema)
        self.tool_definitions.append(tool)
        self.tools[name] = handler
        logger.info(f"Registered tool: {name}")
    
    def set_agent_response_callback(self, callback: Callable):
        """Set callback for handling agent responses"""
        self.agent_response_callback = callback
    
    async def handle_client(self, websocket, path):
        """Handle MCP client connections"""
        self.clients.add(websocket)
        logger.info(f"New MCP client connected: {websocket.remote_address}")
        
        try:
            async for message in websocket:
                await self.process_message(websocket, message)
        except ConnectionClosed:
            logger.info(f"MCP client disconnected: {websocket.remote_address}")
        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            self.clients.discard(websocket)
    
    async def process_message(self, websocket, message: str):
        """Process incoming MCP messages"""
        try:
            data = json.loads(message)
            request = MCPRequest(
                id=data.get("id", str(uuid.uuid4())),
                method=data.get("method"),
                params=data.get("params", {})
            )
            
            response = await self.handle_request(request)
            # MCP over WebSocket - add required jsonrpc field
            response_msg = {"jsonrpc": "2.0", "id": response.id}
            if response.error:
                response_msg["error"] = response.error
            else:
                response_msg["result"] = response.result
            await websocket.send(json.dumps(response_msg))
            
        except json.JSONDecodeError:
            # MCP error response over WebSocket
            error_msg = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"}
            }
            await websocket.send(json.dumps(error_msg))
        except Exception as e:
            # MCP error response over WebSocket
            error_msg = {
                "jsonrpc": "2.0",
                "id": data.get("id") if 'data' in locals() else None,
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
            }
            await websocket.send(json.dumps(error_msg))
    
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle specific MCP requests"""
        if request.method == "initialize":
            # Proper MCP initialization response
            return MCPResponse(
                id=request.id,
                result={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {
                            "listChanged": True
                        }
                    },
                    "serverInfo": {
                        "name": "mcp-trading-server",
                        "version": "1.0.0"
                    }
                }
            )
        
        elif request.method == "notifications/initialized":
            # Client confirms initialization is complete
            logger.info("MCP client initialization completed")
            return MCPResponse(id=request.id, result={})
        
        elif request.method == "tools/list":
            # Return available tools for discovery
            return MCPResponse(
                id=request.id,
                result={
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        } for tool in self.tool_definitions
                    ]
                }
            )
        
        elif request.method == "tools/call":
            tool_name = request.params.get("name")
            arguments = request.params.get("arguments", {})
            
            if tool_name not in self.tools:
                return MCPResponse(
                    id=request.id,
                    error={"code": -32601, "message": f"Tool not found: {tool_name}"}
                )
            
            try:
                result = await self.tools[tool_name](arguments)
                # Proper MCP tool response format
                return MCPResponse(
                    id=request.id,
                    result={
                        "content": [
                            {
                                "type": "text",
                                "text": str(result)
                            }
                        ],
                        "isError": False
                    }
                )
            except Exception as e:
                logger.error(f"Tool execution error for {tool_name}: {e}")
                # Tool errors should be in result.isError, not protocol errors
                return MCPResponse(
                    id=request.id,
                    result={
                        "content": [
                            {
                                "type": "text",
                                "text": f"Tool execution error: {str(e)}"
                            }
                        ],
                        "isError": True
                    }
                )
        
        elif request.method == "agent_response":
            # Handle agent response and forward to website
            response_data = request.params.get("response", "")
            logger.info(f"Received agent response, forwarding to website")
            
            if self.agent_response_callback:
                try:
                    await self.agent_response_callback(response_data)
                except Exception as e:
                    logger.error(f"Error forwarding agent response: {e}")
            
            return MCPResponse(
                id=request.id,
                result={"status": "response_forwarded"}
            )
        
        else:
            return MCPResponse(
                id=request.id,
                error={"code": -32601, "message": f"Method not found: {request.method}"}
            )
    
    async def broadcast_notification(self, method: str, params: Dict[str, Any]):
        """Send MCP notifications over WebSocket to all connected clients"""
        # MCP notification format (no id field for notifications)
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        message = json.dumps(notification)
        
        for client in self.clients.copy():
            try:
                await client.send(message)
            except ConnectionClosed:
                self.clients.discard(client)
    
    async def start_server(self, host: str = "0.0.0.0", port: int = 8001):
        """Start the MCP server"""
        logger.info(f"Starting MCP server on {host}:{port}")
        await serve(self.handle_client, host, port)
