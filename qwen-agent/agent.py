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
        model_name = os.getenv("MODEL_NAME", "hf.co/unsloth/Qwen3-1.7B-GGUF:Q4_K_M")
        
        self.agent = Assistant(
            llm={
                'model': model_name,
                'model_server': f'{ollama_url}/v1',
                'api_key' : 'EMPTY'
            },
            system_message=SYSTEM_PROMPT,
            function_list=tools
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

            messages = [{'role': 'user', 'content': prompt}]

            print("Processing market data with agent...")
            
            # Process agent response using documented pattern
            final_response = None
            for response_chunk in self.agent.run(messages=messages):
                final_response = response_chunk  # Last iteration contains final response
            
            if final_response:
                print(f"Agent decision: {final_response}")
                # Send agent response back to website via MCP server
                await self.send_agent_response_to_website(final_response)
            else:
                print("No response from agent")

            
           
            
        except Exception as e:
            print(f"Error processing market data: {e}")
            # Send error notification back to website
            await self.send_agent_response_to_website(f"Error: {str(e)}")
    
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
    
    async def send_agent_response_to_website(self, response):
        """Send agent decision/response back to website via MCP server"""
        try:
            if self.mcp_client and self.mcp_client.connected:
                await self.mcp_client.send_request("agent_response", {
                    "response": str(response),
                    "timestamp": asyncio.get_event_loop().time()
                })
                print(f"Sent agent response to MCP server")
        except Exception as e:
            print(f"Failed to send agent response to website: {e}")
