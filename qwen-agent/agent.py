import os
import asyncio
import json
from typing import Dict, Any
from qwen_agent.agents import Assistant
from mcp_client import MCPClient
from qwen_tools import create_tools_from_mcp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a crypto trading agent connected to trading tools via MCP protocol.

You will receive real-time market data and must analyze it to make trading decisions.

Available tools:
- buy_crypto: Execute a buy order (requires symbol and amount)
- sell_crypto: Execute a sell order (requires symbol and amount)
- hold: Hold current position (optional reason parameter)

Trading guidelines:
- Only trade when you have high confidence
- Consider market trends, volume, and portfolio balance
- Manage risk appropriately 
- Provide clear reasoning for your decisions

When you decide to take action, call the appropriate tool with the correct parameters. Always use one of the avaliable tools when making an action
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

        try:
            await self.mcp_client.connect()
            logger.info("Connected to mcp-server container")
        except Exception as e:
             logger.error(f"Failed to connect due to: {e}")
             raise 
        
        # Set up market data callback
        self.mcp_client.set_market_data_callback(self.handle_market_data)
        
        # Create tools from MCP server capabilities
        tools = create_tools_from_mcp(self.mcp_client)
        
        # Initialize Qwen agent
        ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        model_name = os.getenv("MODEL_NAME", "hf.co/unsloth/Qwen3-1.7B-GGUF:Q4_K_M")

        llm_config = {
           'model' : model_name,
           'model_server' : f'{ollama_url}/v1',
           'api_key' : 'EMPTY',
           'generate_cfg': {
           
               'extra_body':{
                   'chat_template_kwargs': {'enable_thinking': False}
               },
               'fncall_prompt_type': 'nous',
               'thought_in_content': True,
           }
        }
        
        self.agent = Assistant(
            llm=llm_config,
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

            print("LLM RESPONSE:")
            response_text = ""

            
            for response in self.agent.run(messages):
                print(f"Response chunk: {response}")
            
                # Handle different response types
                if hasattr(response, 'response'):
                    content = response.response
                elif hasattr(response, 'content'):
                    content = response.content
                elif isinstance(response, str):
                    content = response
                else:
                    content = str(response)
            
                response_text += content
                print(content, end="", flush=True)
        
            print("\n" + "=" * 50)
            print(f"COMPLETE AGENT DECISION: {response_text}")
            print("=" * 50)

            
           
            
        except Exception as e:
            print(f"Error processing market data: {e}")
    
    async def run(self):
        """Main agent loop"""
        
        # Keep the agent running
        try:
            await self.initialize()

            logger.info("QWEN_AGENT RUNNING")
  
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down agent...")
        except Exception as e:
            logger.error(f"Agent error: {e}")
            raise
        finally:
            if self.mcp_client:
                await self.mcp_client.disconnect()
