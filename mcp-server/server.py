import asyncio
import os
import logging
from typing import Dict, Any  # FIXED: Added missing imports
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
        # FIXED: Actually register the tools
        
        # Buy tool
        self.mcp_handler.register_tool(
            name="buy_crypto",
            description="Execute a cryptocurrency buy order",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Cryptocurrency symbol (e.g., BTC, ETH)"},
                    "amount": {"type": "number", "description": "Amount to buy"}
                },
                "required": ["symbol", "amount"]
            },
            handler=self.trading_tools.crypto_buy
        )
        
        # Sell tool
        self.mcp_handler.register_tool(
            name="sell_crypto", 
            description="Execute a cryptocurrency sell order",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Cryptocurrency symbol (e.g., BTC, ETH)"},
                    "amount": {"type": "number", "description": "Amount to sell"}
                },
                "required": ["symbol", "amount"]
            },
            handler=self.trading_tools.crypto_sell
        )
        
        # Hold tool
        self.mcp_handler.register_tool(
            name="hold",
            description="Hold current position (no action)",
            parameters={
                "type": "object", 
                "properties": {
                    "reason": {"type": "string", "description": "Reason for holding"}
                },
                "required": []
            },
            handler=self.trading_tools.crypto_hold
        )
        
        logger.info("Registered 3 trading tools")
    
    async def handle_market_data(self, data: Dict[str, Any]):
        """Handle market data from website and broadcast to MCP clients"""
        await self.mcp_handler.broadcast_notification(
            method="market_data",
            params=data
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