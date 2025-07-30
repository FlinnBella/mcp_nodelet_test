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
        
    def register_tool(self, name: str, description: str, parameters: Dict[str, Any], handler: Callable):
        """Register a tool with the MCP server"""
        tool = MCPTool(name=name, description=description, parameters=parameters)
        self.tool_definitions.append(tool)
        self.tools[name] = handler
        logger.info(f"Registered tool: {name}")
    
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
            await websocket.send(json.dumps({
                "id": response.id,
                "result": response.result,
                "error": response.error
            }))
            
        except json.JSONDecodeError:
            error_response = MCPResponse(
                id="unknown",
                error={"code": -32700, "message": "Parse error"}
            )
            await websocket.send(json.dumps(error_response.__dict__))
        except Exception as e:
            error_response = MCPResponse(
                id=data.get("id", "unknown"),
                error={"code": -32603, "message": f"Internal error: {str(e)}"}
            )
            await websocket.send(json.dumps(error_response.__dict__))
    
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle specific MCP requests"""
        if request.method == "initialize":
            return MCPResponse(
                id=request.id,
                result={
                    "capabilities": {
                        "tools": [tool.__dict__ for tool in self.tool_definitions]
                    }
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
                return MCPResponse(
                    id=request.id,
                    result={"content": result}
                )
            except Exception as e:
                return MCPResponse(
                    id=request.id,
                    error={"code": -32603, "message": f"Tool execution error: {str(e)}"}
                )
        
        else:
            return MCPResponse(
                id=request.id,
                error={"code": -32601, "message": f"Method not found: {request.method}"}
            )
    
    async def broadcast_notification(self, method: str, params: Dict[str, Any]):
        """Send notifications to all connected clients"""
        message = json.dumps({
            "method": method,
            "params": params
        })
        
        for client in self.clients.copy():
            try:
                await client.send(message)
            except ConnectionClosed:
                self.clients.discard(client)
    
    async def start_server(self, host: str = "0.0.0.0", port: int = 8001):
        """Start the MCP server"""
        logger.info(f"Starting MCP server on {host}:{port}")
        await serve(self.handle_client, host, port)
