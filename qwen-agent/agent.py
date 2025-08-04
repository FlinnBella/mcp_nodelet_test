import os
import asyncio
import json
import uuid
import logging
import websockets
from typing import Dict, Any, Set, Optional
from mcp_client import MCPClient
import time

logger = logging.getLogger(__name__)

class MCPToKaggleBridge:
    def __init__(self):
        self.mcp_client: Optional[MCPClient] = None
        self.kaggle_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.mcp_tools: list = []
        self.running = False
        
    async def initialize(self):
        """Initialize MCP client connection"""
        # Connect to MCP server
        mcp_server_url = os.getenv("MCP_SERVER_URL", "ws://mcp-server:8001")
        self.mcp_client = MCPClient(mcp_server_url)

        try:
            await self.mcp_client.connect()
            logger.info("Connected to mcp-server container")
        except Exception as e:
             logger.error(f"Failed to connect due to: {e}")
             raise 
        
        # Set up market data callback to forward to Kaggle
        self.mcp_client.set_market_data_callback(self.forward_market_data_to_kaggle)
        
        # Get tools from MCP server
        self.mcp_tools = self.mcp_client.tools.copy()
        
        print(f"MCP Bridge initialized with {len(self.mcp_tools)} tools from MCP server")
        logger.info(f"Available tools: {[tool.name for tool in self.mcp_tools]}")
        
    async def forward_market_data_to_kaggle(self, mcp_notification: Dict[str, Any]):
        """Forward market data from MCP server to all connected Kaggle clients"""
        if not self.kaggle_clients:
            logger.debug("No Kaggle clients connected, skipping market data forward")
            return
        
        # Extract the complete payload from MCP notification
        params = mcp_notification.get("params", {})
        payload_data = params.get("data", {})
        timestamp = params.get("timestamp")
        
        # Extract components from the complex payload structure
        market_data = payload_data.get("marketData", {})
        portfolio = payload_data.get("portfolio", {})
        current_prices = payload_data.get("currentPrices", {})
        risk_config = payload_data.get("riskConfig", {})
        difficulty = payload_data.get("difficulty", "medium")
        original_request_id = payload_data.get("requestId")
        
        logger.info(f"Forwarding complex market data to Kaggle - difficulty: {difficulty}, original requestId: {original_request_id}")
            
        # Create message for Kaggle in expected format
        message = {
            "type": "market_data_request",
            "request_id": original_request_id or str(uuid.uuid4()),
            "market_data": {
                "marketData": market_data,
                "portfolio": portfolio,
                "currentPrices": current_prices,
                "riskConfig": risk_config,
                "timestamp": timestamp
            },
            "difficulty": difficulty,
            "timestamp": timestamp or asyncio.get_event_loop().time()
        }
        
        # Send to all connected Kaggle clients
        disconnected_clients = set()
        for client in self.kaggle_clients.copy():
            try:
                await client.send(json.dumps(message))
                logger.debug(f"Complex market data forwarded to Kaggle client: {client.remote_address}")
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Error forwarding market data to client: {e}")
                disconnected_clients.add(client)
        
        # Clean up disconnected clients
        for client in disconnected_clients:
            self.kaggle_clients.discard(client)
    
    async def handle_kaggle_client(self, websocket):
        """Handle incoming Kaggle WebSocket connections"""
        client_addr = websocket.remote_address
        self.kaggle_clients.add(websocket)
        logger.info(f"Kaggle client connected: {client_addr}")
        
        # Send connection confirmation
        await websocket.send(json.dumps({
            "type": "connection_established",
            "message": "Connected to MCP Bridge successfully"
        }))
        
        try:
            async for message in websocket:
                await self.process_kaggle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Kaggle client disconnected: {client_addr}")
        except Exception as e:
            logger.error(f"Error handling Kaggle client {client_addr}: {e}")
        finally:
            self.kaggle_clients.discard(websocket)
    
    async def process_kaggle_message(self, websocket, message: str):
        """Process incoming messages from Kaggle clients"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            logger.debug(f"Received message from Kaggle: {message_type}")
            
            if message_type == "request_tools":
                await self.handle_tools_request(websocket)
                
            elif message_type == "status":
                await self.handle_status_message(websocket, data)
                
            elif message_type == "heartbeat":
                await self.handle_heartbeat(websocket, data)
                
            elif message_type == "market_data_response":
                await self.handle_market_data_response(data)
            
            elif message_type == "market_data_error":
		error = data.get("error")
                logger.error(f"Error from Kaggle with marketdata: {error}")
                
            else:
                logger.warning(f"Unknown message type from Kaggle: {message_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from Kaggle client: {e}")
        except Exception as e:
            logger.error(f"Error processing Kaggle message: {e}")
    
    async def handle_tools_request(self, websocket):
        """Send MCP tools to Kaggle client in exact MCP specification format"""
        try:
            # Convert MCPTool objects to proper MCP specification format
            tools_data = []
            for tool in self.mcp_tools:
                logger.info(f"{tool.name} has inputSchema {tool.inputSchema}")
                tool_dict = {
                    "type": "function",
                    "function": {
                    	"name": tool.name,
                    	"description": tool.description,
                        "parameters": tool.inputSchema  # MCP spec uses inputSchema, not parameters
                    }
                }
                tools_data.append(tool_dict)
            
             #Need to make this OPENAI compatible
             #possibly just let response equal tools_data?
            response = {
		"type": "tools_response",
            	"tools": tools_data
            
            await websocket.send(json.dumps(response))
            logger.info(f"Sent {len(tools_data)} tools to Kaggle client in MCP format")
            
        except Exception as e:
            logger.error(f"Error sending tools to Kaggle: {e}")
    
    async def handle_status_message(self, websocket, data):
        """Handle status updates from Kaggle"""
        status = data.get("status")
        logger.info(f"Kaggle client status: {status}")
        
        # Acknowledge status
        await websocket.send(json.dumps({
            "type": "status_ack",
            "received_status": status
        }))
    
    async def handle_heartbeat(self, websocket, data):
        """Handle heartbeat from Kaggle and respond"""
        await websocket.send(json.dumps({
            "type": "heartbeat_ack",
            "timestamp": time.time()
        }))
    
    async def handle_market_data_response(self, data):
        """Handle trading decisions from Kaggle and route to MCP server"""
        request_id = data.get("request_id")
        response = data.get("response")
        
        logger.info(f"Received trading decision from Kaggle for request {request_id}")
        
        # Parse the trading decision and forward to MCP server
        try:
            if response:
                # Handle both dict and string response formats
                if isinstance(response, str):
                    try:
                        response = json.loads(response)
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse response as JSON: {response}")
                        return
                
                if isinstance(response, dict):
                    function_call = response.get("function_call")
                    if function_call:
                        tool_name = function_call.get("name")
                        arguments = function_call.get("arguments", {})
                        
                        if isinstance(arguments, str):
                            try:
                                arguments = json.loads(arguments)
                            except json.JSONDecodeError:
                                logger.warning(f"Could not parse arguments as JSON: {arguments}")
                                return
                        
                        # Forward tool call to MCP server
                        if self.mcp_client and tool_name:
                            logger.info(f"Forwarding tool call to MCP server: {tool_name} with args {arguments}")
                            result = await self.mcp_client.call_tool(tool_name, arguments)
                            logger.info(f"MCP server tool execution result: {result}")
                        else:
                            logger.warning("No tool name found in trading decision or MCP client not available")
                    else:
                        logger.debug("No function call in trading response, likely a hold decision")
                else:
                    logger.warning(f"Invalid response format from Kaggle: {type(response)}")
            else:
                logger.warning("Empty response from Kaggle")
                
        except Exception as e:
            logger.error(f"Error processing trading decision: {e}")
            logger.error(f"Request data: {data}")
            logger.error(f"Response data: {response}")
    
    async def start_websocket_server(self, host: str = "0.0.0.0", port: int = 8004):
        """Start WebSocket server for Kaggle connections"""
        logger.info(f"Starting WebSocket server for Kaggle on {host}:{port}")
        
        async with websockets.serve(self.handle_kaggle_client, host, port):
            logger.info(f"WebSocket server running on ws://{host}:{port}")
            self.running = True
            
            # Keep the server running
            try:
                while self.running:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down WebSocket server...")
            finally:
                self.running = False
    
    async def run(self):
        """Main bridge loop"""
        await self.initialize()
        
        logger.info("MCP to Kaggle Bridge is running...")
        logger.info("Waiting for Kaggle connections and market data...")
        
        # Start WebSocket server for Kaggle connections
        await self.start_websocket_server()

async def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    bridge = MCPToKaggleBridge()
    
    try:
        await bridge.run()
    except KeyboardInterrupt:
        logger.info("Shutting down bridge...")
    except Exception as e:
        logger.error(f"Bridge error: {e}")
    finally:
        if bridge.mcp_client:
            await bridge.mcp_client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
