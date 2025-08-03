import asyncio
import os
import logging
from typing import Dict, Any
from mcp_protocol import MCPProtocolHandler
from trading_tools import TradingTools
from website_connector import WebsiteConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPTradingServer:
    def __init__(self):
        self.mcp_handler = MCPProtocolHandler()
        self.website_connector = WebsiteConnector(
            market_data_callback=self.handle_market_data
        )
        self.trading_tools = TradingTools(self.website_connector)
        
        # Register tools with MCP protocol
        self.register_tools()
    
    def register_tools(self):
        """Register trading tools with MCP handler"""
        # Register buy_crypto tool (frontend naming)
        self.mcp_handler.register_tool(
            name="buy_crypto",
            description="Execute a cryptocurrency buy order",
            inputSchema={
                "type": "object",
                "properties": {
                    "crypto": {
                        "type": "string",
                        "description": "The cryptocurrency symbol to buy (e.g., BTC, ETH)"
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount to buy"
                    }
                },
                "required": ["crypto", "amount"]
            },
            handler=self.trading_tools.buy_crypto
        )
        
        # Register sell_crypto tool (frontend naming)
        self.mcp_handler.register_tool(
            name="sell_crypto",
            description="Execute a cryptocurrency sell order",
            inputSchema={
                "type": "object",
                "properties": {
                    "crypto": {
                        "type": "string",
                        "description": "The cryptocurrency symbol to sell (e.g., BTC, ETH)"
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount to sell"
                    }
                },
                "required": ["crypto", "amount"]
            },
            handler=self.trading_tools.sell_crypto
        )
        
        # Register hold tool (frontend naming)
        self.mcp_handler.register_tool(
            name="hold",
            description="Hold current position without taking any action",
            inputSchema={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "The reasoning for holding the position"
                    }
                },
                "required": []
            },
            handler=self.trading_tools.hold
        )
    
    async def handle_market_data(self, payload: Dict[str, Any]):
        """Handle complex market data payload from website and broadcast to MCP clients"""
        # Extract the nested data structure
        payload_data = payload.get("data", {})
        difficulty = payload_data.get("difficulty", "medium")
        request_id = payload_data.get("requestId")
        timestamp = payload.get("timestamp")
        
        logger.info(f"Broadcasting market data to MCP clients - difficulty: {difficulty}, requestId: {request_id}")
        
        # Broadcast the complete payload structure to all MCP clients (including agent.py)
        await self.mcp_handler.broadcast_notification(
            method="market_data",
            params={
                "type": "market_data",
                "data": payload_data,  # Pass the complete nested data structure
                "timestamp": timestamp
            }
        )
    
    async def start(self):
        """Start both MCP server and Website WebSocket server"""
        # Start website WebSocket server
        website_host = os.getenv("WEBSITE_HOST", "0.0.0.0")
        website_port = int(os.getenv("WEBSITE_PORT", "8002"))
        await self.website_connector.start_server(website_host, website_port)
        
        # Start MCP protocol server
        mcp_host = os.getenv("MCP_HOST", "0.0.0.0")
        mcp_port = int(os.getenv("MCP_PORT", "8001"))
        
        logger.info("Starting MCP Trading Server...")
        logger.info(f"Website connections: ws://{website_host}:{website_port}")
        logger.info(f"MCP connections: ws://{mcp_host}:{mcp_port}")
        
        # Run both servers concurrently
        await asyncio.gather(
            self.mcp_handler.start_server(mcp_host, mcp_port),
            self.keep_running()
        )
    
    async def keep_running(self):
        """Keep the server running"""
        try:
            while True:
                await asyncio.sleep(1)
                # Optional: Log connected clients periodically
                if asyncio.get_event_loop().time() % 60 < 1:  # Every ~60 seconds
                    logger.info(f"Connected websites: {self.website_connector.get_connected_clients()}")
        except KeyboardInterrupt:
            logger.info("Shutting down servers...")
            await self.website_connector.stop_server()

async def main():
    server = MCPTradingServer()
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
