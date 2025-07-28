import os
import asyncio
import json
from typing import Dict, Any
from qwen_agent.agents import Assistant
from mcp_client import MCPClient
from qwen_tools import create_tools_from_mcp

SYSTEM_PROMPT = """
You are a crypto trading agent connected to trading tools via MCP protocol.

You will receive real-time market data and must analyze it to make trading decisions.

Available tools will be dynamically loaded from the MCP server.

Trading guidelines:
- Only trade when you have high confidence
- Consider market trends, volume, and portfolio balance
- Manage risk appropriately 
- Provide clear reasoning for your decisions

When you decide to take action, call the appropriate tool with the correct parameters.
"""

class QwenTradingAgent:
    def __init__(self):
        self.mcp_client = None
        self.agent = None
        
    async def initialize(self):
        """Initialize MCP client and Qwen agent"""
        # Connect to MCP server
        mcp_server_url = os.getenv("MCP_SERVER_URL", "ws://mcp-server:8001")
        self.mcp_client = MCPClient(mcp_server_url)
        await self.mcp_client.connect()
        
        # Set up market data callback
        self.mcp_client.set_market_data_callback(self.handle_market_data)
        
        # Create tools from MCP server capabilities
        tools = create_tools_from_mcp(self.mcp_client)
        
        # Initialize Qwen agent
        ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        model_name = os.getenv("MODEL_NAME", "qwen:14b")
        
        self.agent = Assistant(
            llm_cfg={
                'model': model_name,
                'api_base': f'{ollama_url}/v1',
                'api_key': 'dummy',
                'model_server': 'ollama'
            },
            system_message=SYSTEM_PROMPT,
            tools=tools
        )
        
        print(f"Agent initialized with {len(tools)} tools")
    
    async def handle_market_data(self, data: Dict[str, Any]):
        """Handle market data from MCP server"""
        try:
            prompt = f"""
New market data received:
{json.dumps(data, indent=2)}

Analyze this data and decide if any action should be taken.
Consider the current market conditions, trends, and your trading strategy.

If you decide to trade, use the appropriate tool with correct parameters.
If you decide to hold, use the crypto_hold tool with your reasoning.
"""
            
            print(f"Processing market data: {data}")
            
            # Run agent in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self.agent.run,
                prompt
            )
            
            print(f"Agent decision: {response}")
            
        except Exception as e:
            print(f"Error processing market data: {e}")
    
    async def run(self):
        """Main agent loop"""
        await self.initialize()
        
        print("Qwen Trading Agent is running...")
        print("Waiting for market data...")
        
        # Keep the agent running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down agent...")
        finally:
            if self.mcp_client:
                await self.mcp_client.disconnect()