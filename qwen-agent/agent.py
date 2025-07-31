import os
import asyncio
import json
import httpx
from typing import Dict, Any
from qwen_agent.agents import Assistant
from mcp_client import MCPClient
from qwen_tools import create_tools_from_mcp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a crypto trading agent. You MUST ALWAYS call exactly ONE tool for every market data update.

CRITICAL RULES:
1. You MUST call a tool - never just provide text responses
2. You MUST choose ONE action: buy_crypto, sell_crypto, or hold
3. You MUST call the tool immediately - no explanations first
4. If unsure, call hold with a reason

Available tools:
- buy_crypto: Execute a buy order (symbol: string, amount: number)
- sell_crypto: Execute a sell order (symbol: string, amount: number)  
- hold: Hold current position (reason: string)

EXAMPLE RESPONSES (you must follow this format):
- For buying: Call buy_crypto with {"symbol": "BTC", "amount": 100}
- For selling: Call sell_crypto with {"symbol": "ETH", "amount": 50}
- For waiting: Call hold with {"reason": "Market conditions unclear"}

REMEMBER: You MUST call a tool. Never provide text-only responses.
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
        logger.info("DEBUG: Market data callback registered")
        
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
               'temperature': 0.1,
               'max_tokens': 200,
               'top_p': 0.8,
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
        logger.info("DEBUG: handle_market_data called!")
        try:
            prompt = f"""
Market data: {json.dumps(data, indent=2)}

REQUIRED ACTION: Call exactly ONE tool now:
- buy_crypto if you want to buy (specify symbol and amount)
- sell_crypto if you want to sell (specify symbol and amount)  
- hold if you want to wait (specify reason)

Do NOT provide explanations. Call a tool immediately.
"""
            
            logger.info(f"DEBUG: Processing market data: {data}")
            logger.info(f"DEBUG: About to call agent.run with prompt length: {len(prompt)}")

            messages = [{'role': 'user', 'content': prompt}]

            logger.info("DEBUG: Processing market data with agent...")
            
            # Process agent response using documented pattern
            logger.info("DEBUG: Starting agent.run loop...")
            final_response = None
            for response_chunk in self.agent.run(messages=messages):
                logger.info(f"DEBUG: Got response chunk: {response_chunk}")
                final_response = response_chunk  # Last iteration contains final response
            
            logger.info(f"DEBUG: Agent.run loop completed, final_response: {final_response}")
            if final_response:
                # Check if response contains tool calls
                response_text = str(final_response)
                if any(tool_name in response_text.lower() for tool_name in ['buy_crypto', 'sell_crypto', 'hold']):
                    logger.info(f"DEBUG: Tool call detected in response")
                    print(f"Agent decision: {final_response}")
                    await self.send_agent_response_to_website(final_response)
                else:
                    logger.warning(f"DEBUG: No tool call detected, forcing hold action")
                    # Force a hold action if no tool was called
                    fallback_response = "Agent failed to call tool, defaulting to hold position"
                    print(f"Agent decision (fallback): {fallback_response}")
                    await self.send_agent_response_to_website(fallback_response)
            else:
                logger.error("DEBUG: No response from agent!")
                print("No response from agent")

            
           
            
        except Exception as e:
            logger.error(f"DEBUG: Exception in handle_market_data: {e}", exc_info=True)
            print(f"Error processing market data: {e}")
            # Send error notification back to website
            await self.send_agent_response_to_website(f"Error: {str(e)}")
    
    async def run(self):
        """Main agent loop"""
        
        # Keep the agent running
        try:
            await self.initialize()

            logger.info("QWEN_AGENT RUNNING")
  
            while True:
                await asyncio.sleep(1)
                # Check connection status every 30 seconds
                if asyncio.get_event_loop().time() % 30 < 1:
                    logger.info(f"DEBUG: MCP client connected: {self.mcp_client.connected if self.mcp_client else False}")
        except KeyboardInterrupt:
            print("Shutting down agent...")
        except Exception as e:
            logger.error(f"Agent error: {e}")
            raise
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
