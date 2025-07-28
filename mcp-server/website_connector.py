import asyncio
import json
import websockets
from typing import Dict, Any, Optional, Callable, Set
import logging

logger = logging.getLogger(__name__)

class WebsiteConnector:
    def __init__(self, market_data_callback: Optional[Callable] = None):
        self.market_data_callback = market_data_callback
        self.website_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server = None
        
    async def handle_website_client(self, websocket, path):
        """Handle incoming connections from your website"""
        self.website_clients.add(websocket)
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"Website client connected: {client_info}")
        
        try:
            # Send welcome message
            await websocket.send(json.dumps({
                "type": "connection_established",
                "message": "Connected to MCP Trading Server"
            }))
            
            # Listen for messages from website
            async for message in websocket:
                await self.handle_website_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Website client disconnected: {client_info}")
        except Exception as e:
            logger.error(f"Error handling website client {client_info}: {e}")
        finally:
            self.website_clients.discard(websocket)
    
    async def handle_website_message(self, websocket, message: str):
        """Process messages from your website"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "market_data":
                # Market data from your website
                market_data = data.get("data", {})
                logger.info(f"Received market data: {market_data}")
                
                if self.market_data_callback:
                    await self.market_data_callback(market_data)
                    
            elif message_type == "trade_confirmation":
                # Trade execution confirmation from your website
                confirmation = data.get("data", {})
                logger.info(f"Trade confirmed: {confirmation}")
                # Handle confirmation if needed
                
            elif message_type == "ping":
                # Heartbeat from website
                await websocket.send(json.dumps({"type": "pong"}))
                
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.error("Received invalid JSON from website")
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Invalid JSON format"
            }))
        except Exception as e:
            logger.error(f"Error processing website message: {e}")
    
    async def execute_trade(self, action: str, symbol: str, amount: float) -> Dict[str, Any]:
        """Send trade command to all connected websites"""
        if not self.website_clients:
            raise Exception("No website clients connected")
        
        command = {
            "type": "trade_command",
            "data": {
                "action": action,
                "symbol": symbol,
                "amount": amount,
                "timestamp": asyncio.get_event_loop().time()
            }
        }
        
        results = []
        for client in self.website_clients.copy():
            try:
                await client.send(json.dumps(command))
                logger.info(f"Sent trade command to {client.remote_address}: {command}")
                results.append({"client": str(client.remote_address), "status": "sent"})
            except websockets.exceptions.ConnectionClosed:
                self.website_clients.discard(client)
                logger.warning(f"Removed disconnected client: {client.remote_address}")
            except Exception as e:
                logger.error(f"Failed to send to {client.remote_address}: {e}")
                results.append({"client": str(client.remote_address), "status": "failed", "error": str(e)})
        
        return {"results": results, "command": command["data"]}
    
    async def broadcast_message(self, message_type: str, data: Dict[str, Any]):
        """Broadcast message to all connected websites"""
        message = {
            "type": message_type,
            "data": data
        }
        
        for client in self.website_clients.copy():
            try:
                await client.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                self.website_clients.discard(client)
            except Exception as e:
                logger.error(f"Broadcast failed to {client.remote_address}: {e}")
    
    async def start_server(self, host: str = "0.0.0.0", port: int = 8002):
        """Start WebSocket server for website connections"""
        logger.info(f"Starting Website WebSocket server on {host}:{port}")
        self.server = await websockets.serve(
            self.handle_website_client, 
            host, 
            port
        )
        return self.server
    
    async def stop_server(self):
        """Stop the WebSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Website WebSocket server stopped")
    
    def get_connected_clients(self) -> int:
        """Get number of connected website clients"""
        return len(self.website_clients)