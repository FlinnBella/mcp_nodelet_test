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

def get_system_prompt(difficulty: str = "medium") -> str:
    """Generate system prompt based on difficulty level"""
    
    base_tools = """
Available tools:
- buy_crypto: Execute buy order {"symbol": "BTC|ETH|SOL|DOGE", "amount": [USD_amount], "reason": "[detailed_reasoning]"}
- sell_crypto: Execute sell order {"symbol": "BTC|ETH|SOL|DOGE", "amount": [USD_amount], "reason": "[detailed_reasoning]"}  
- hold: Hold position {"reason": "[detailed_reasoning]"}

CRITICAL RISK RULES:
- ONLY trade if portfolio.riskMetrics.canTrade = true
- Respect availableBuyingPower for buy orders
- Check tradesRemainingToday and tradesRemainingThisHour limits
- Consider riskScore, consecutiveLosses, and maxDrawdownToday
- Never exceed position limits or risk thresholds

You MUST call exactly ONE tool for every market update.
"""
    
    if difficulty == "easy":
        return f"""
You are a SIMPLE crypto trading bot. Make quick, basic decisions.

SIMPLE RULES:
- Buy when prices drop
- Sell when prices rise  
- ONLY trade if portfolio.riskMetrics.canTrade = true
- Trade 5-15% of availableBuyingPower per trade
- Check tradesRemainingToday and tradesRemainingThisHour
- If unsure, just hold

BASIC STRATEGY:
- Price going up = sell if you own it
- Price going down = buy with some cash
- Don't overthink it - just trade!
- Always provide detailed reasoning in the reason field

{base_tools}

Keep it simple. Trade fast.
"""
    
    elif difficulty == "hard":
        return f"""
You are an EXPERT crypto trading analyst with advanced market insight.

SOPHISTICATED ANALYSIS FRAMEWORK:
- Portfolio risk metrics: Analyze riskScore, consecutiveLosses, maxDrawdownToday
- Risk-adjusted position sizing based on availableBuyingPower and risk constraints
- Multi-timeframe trend analysis using price momentum and market structure
- Dynamic position sizing: 2-8% for high-risk, 8-20% for moderate-risk opportunities
- Risk management: Never exceed tradesRemainingToday/tradesRemainingThisHour limits

ADVANCED DECISION CRITERIA:
- Evaluate portfolio correlation and concentration risk
- Consider market regime (trending vs ranging) and volatility environment  
- Implement proper entry/exit timing based on technical confluences
- Factor in opportunity cost across all available assets
- Execute only high-probability setups with favorable risk/reward

EXPERT RISK MANAGEMENT:
- Respect all risk constraints: maxDrawdownToday, consecutiveLosses limits
- Position size inversely proportional to recent losses and portfolio heat
- Consider market correlation during portfolio construction
- Execute tactical rebalancing based on changing market conditions
- ALWAYS check portfolio.riskMetrics.canTrade before any action

{base_tools}

Apply institutional-level analysis. Trade with precision and discipline.
"""
    
    else:  # medium (default)
        return f"""
You are a BALANCED crypto trading agent with market analysis skills.

TRADING APPROACH:
- Analyze market data AND risk metrics before trading
- Consider portfolio balance, risk score, and trading limits  
- Use 8-25% of availableBuyingPower for trades based on confidence
- Respect risk constraints: check portfolio.riskMetrics.canTrade, tradesRemaining, consecutiveLosses

DECISION PROCESS:
1. Check if trading is allowed (portfolio.riskMetrics.canTrade = true)
2. Analyze current prices vs portfolio holdings
3. Consider risk metrics and daily/hourly trade limits
4. Make calculated buy/sell decisions
5. Use appropriate position sizing based on risk

RISK AWARENESS:
- Monitor consecutiveLosses and maxDrawdownToday
- Reduce position sizes after losses
- Increase position sizes during profitable streaks
- Balance portfolio across BTC, ETH, SOL, DOGE
- Always provide detailed reasoning in the reason field

{base_tools}

Trade thoughtfully with calculated risk management.
"""

# Default system prompt for backwards compatibility  
SYSTEM_PROMPT = get_system_prompt("medium")

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
               'thought_in_content' : False,
           }
        }
        
        self.agent = Assistant(
            llm=llm_config,
            system_message=SYSTEM_PROMPT,
            function_list=tools
        )
        
        print(f"Agent initialized with {len(tools)} tools")
    
    def get_difficulty_config(self, difficulty: str) -> Dict[str, Any]:
        """Get LLM configuration based on difficulty level"""
        ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        model_name = os.getenv("MODEL_NAME", "hf.co/unsloth/Qwen3-1.7B-GGUF:Q4_K_M")
        
        base_config = {
            'model': model_name,
            'model_server': f'{ollama_url}/v1',
            'api_key': 'EMPTY',
        }
        
        if difficulty == "easy":
            base_config['generate_cfg'] = {
                'temperature': 0.4,    # Higher randomness for impulsive decisions
                'max_tokens': 150,     # Short responses  
                'top_p': 0.2,         # Allow more creative responses
                'thought_in_content' : False,
            }
        elif difficulty == "hard":
            base_config['generate_cfg'] = {
                'temperature': 0.1,    # Lower randomness for calculated decisions
                'max_tokens': 400,     # Longer analysis
                'top_p': 0.1,         # More focused responses
                'thought_in_content' : False,
            }
        else:  # medium
            base_config['generate_cfg'] = {
                'temperature': 0.2,    # Balanced randomness
                'max_tokens': 250,     # Moderate analysis
                'top_p': 0.2,         # Balanced creativity
                'thought_in_content' : False,
            }
        
        return base_config
    
    async def handle_market_data(self, params: Dict[str, Any]):
        """Handle market data from MCP server"""
        logger.info("DEBUG: handle_market_data called!")
        try:
            # Extract difficulty and data from params
            difficulty = params.get("difficulty", "medium")
            data = params.get("data", {})
            logger.info(f"DEBUG: Processing with difficulty '{difficulty}': {data}")
            # Get difficulty-specific configuration
            llm_config = self.get_difficulty_config(difficulty)
            tools = create_tools_from_mcp(self.mcp_client)
            
            # Create dynamic agent for this difficulty level
            agent = Assistant(
                llm=llm_config,
                system_message=get_system_prompt(difficulty),
                function_list=tools,
            )
            
            prompt = f"""
Market Data Analysis:
{json.dumps(data, indent=2)}

CRITICAL RISK CONTEXT:
- Portfolio Value: ${data.get('portfolio', {}).get('totalValue', 0):,.2f}
- Daily Change: {data.get('portfolio', {}).get('dailyChangePercent', 0):.2f}%
- Available Buying Power: ${data.get('portfolio', {}).get('availableBuyingPower', 0):,.2f}
- Risk Score: {data.get('portfolio', {}).get('riskMetrics', {}).get('riskScore', 0)}/100
- Can Trade: {data.get('portfolio', {}).get('riskMetrics', {}).get('canTrade', False)}
- Trades Remaining Today: {data.get('portfolio', {}).get('riskMetrics', {}).get('tradesRemainingToday', 0)}
- Trades Remaining This Hour: {data.get('portfolio', {}).get('riskMetrics', {}).get('tradesRemainingThisHour', 0)}
- Consecutive Losses: {data.get('portfolio', {}).get('riskMetrics', {}).get('consecutiveLosses', 0)}
- Max Drawdown Today: {data.get('portfolio', {}).get('riskMetrics', {}).get('maxDrawdownToday', 0):.2f}%

Execute your trading decision now. Remember to check portfolio.riskMetrics.canTrade before any action.
"""
            
            logger.info(f"DEBUG: Processing market data with difficulty '{difficulty}': {data}")
            logger.info(f"DEBUG: About to call agent.run with prompt length: {len(prompt)}")

            messages = [{'role': 'user', 'content': prompt}]

            logger.info(f"DEBUG: Processing market data with {difficulty} difficulty agent...")
            
            # Process agent response using documented pattern
            logger.info("DEBUG: Starting agent.run loop...")
            final_response = None
            for response_chunk in agent.run(messages=messages):
                logger.info(f"DEBUG: Got response chunk: {response_chunk}")
                final_response = response_chunk  # Last iteration contains final response
            
            logger.info(f"DEBUG: Agent.run loop completed, final_response: {final_response}")
            if final_response:
                # Check if response contains function_call
                has_function_call = False
                if isinstance(final_response, list):
                    for msg in final_response:
                        if isinstance(msg, dict) and 'function_call' in msg:
                            has_function_call = True
                            logger.info(f"DEBUG: ===== FUNCTION CALL DETECTED =====")
                            logger.info(f"DEBUG: Function call: {msg['function_call']}")
                            break
                
                if has_function_call:
                    logger.info(f"DEBUG: Tool execution should have completed")
                    print(f"Agent decision: {final_response}")
                    await self.send_agent_response_to_website(final_response)
                else:
                    logger.warning(f"DEBUG: No function call detected in response")
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
                    is_connected = self.mcp_client.connected if self.mcp_client else False
                    task_alive = hasattr(self.mcp_client, 'message_handler_task') and not self.mcp_client.message_handler_task.done()
                    logger.info(f"DEBUG: MCP client connected: {is_connected}, message handler alive: {task_alive}")
                    if not is_connected and self.mcp_client:
                        logger.error("DEBUG: Connection lost! Attempting reconnect...")
                        try:
                            await self.mcp_client.connect()
                        except Exception as e:
                            logger.error(f"DEBUG: Reconnect failed: {e}")
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
