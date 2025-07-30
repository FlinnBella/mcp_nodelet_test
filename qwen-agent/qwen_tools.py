from qwen_agent.tools import BaseTool
from typing import Dict, Any
from mcp_client import MCPClient
import asyncio
import concurrent.futures
import logging

logger = logging.getLogger(__name__)

class MCPTool(BaseTool):
    """Qwen-Agent tool that calls MCP server"""
    
    def __init__(self, tool_name: str, description: str, parameters: Dict[str, Any], mcp_client: MCPClient):
        self.name = tool_name
        self.description = description
        self.parameters = parameters
        self.mcp_client = mcp_client
        super().__init__()
    
    def call(self, params: dict, **kwargs) -> str:
        """Called by Qwen-Agent when LLM decides to use this tool"""
        logger.info(f"🔧 Tool {self.name} called with params: {params}")
        
        try:
            # First try simple asyncio.run approach
            try:
                result = asyncio.run(self._call_mcp_tool(params))
                logger.info(f"✅ Tool {self.name} succeeded: {result}")
                return str(result)
                
            except RuntimeError as e:
                if "asyncio.run() cannot be called from a running event loop" in str(e):
                    # Use concurrent.futures for better sync capabilities 
                    return self._call_with_concurrent_futures(params)
                else:
                    raise e
                    
        except Exception as e:
            error_msg = f"Tool {self.name} failed: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _call_with_concurrent_futures(self, params: dict) -> str:
        """Use concurrent.futures for robust async/sync bridging"""
        logger.info(f"🔄 Using concurrent.futures for tool {self.name}")
        
        try:
            # Use ThreadPoolExecutor for better control and reliability
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                # Submit the async task to run in a separate thread
                future = executor.submit(self._run_async_in_new_loop, params)
                
                try:
                    # Wait for result with timeout - this blocks until complete
                    result = future.result(timeout=30)
                    logger.info(f"✅ Tool {self.name} completed via futures: {result}")
                    return str(result)
                    
                except concurrent.futures.TimeoutError:
                    error_msg = f"Tool {self.name} timed out after 30 seconds"
                    logger.error(error_msg)
                    return error_msg
                    
                except Exception as e:
                    error_msg = f"Tool {self.name} execution error: {str(e)}"
                    logger.error(error_msg)
                    return error_msg
                    
        except Exception as e:
            error_msg = f"Tool {self.name} futures setup error: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _run_async_in_new_loop(self, params: dict) -> str:
        """Run the async MCP call in a new event loop (for concurrent.futures)"""
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Check MCP client connection
            if not self.mcp_client.connected:
                raise Exception("MCP client not connected")
            
            # Run the async call
            result = loop.run_until_complete(self._call_mcp_tool(params))
            return str(result)
            
        except Exception as e:
            logger.error(f"Error in async loop for tool {self.name}: {e}")
            raise e
            
        finally:
            try:
                # Clean up the event loop
                loop.close()
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up event loop: {cleanup_error}")
    
    async def _call_mcp_tool(self, params: dict) -> str:
        """Async method to call MCP tool"""
        if not self.mcp_client.connected:
            raise Exception("MCP client not connected")
        
        try:
            result = await self.mcp_client.call_tool(self.name, params)
            return result
        except Exception as e:
            logger.error(f"MCP call error for tool {self.name}: {e}")
            raise e

def create_tools_from_mcp(mcp_client: MCPClient) -> list:
    """Create Qwen-Agent tools from MCP server capabilities"""
    tools = []
    
    if not mcp_client.tools:
        logger.warning("⚠️ No tools available from MCP server")
        return tools
    
    for mcp_tool in mcp_client.tools:
        try:
            qwen_tool = MCPTool(
                tool_name=mcp_tool.name,
                description=mcp_tool.description,
                parameters=mcp_tool.parameters,
                mcp_client=mcp_client
            )
            tools.append(qwen_tool)
            logger.info(f"✅ Created tool: {mcp_tool.name}")
        except Exception as e:
            logger.error(f"❌ Failed to create tool {mcp_tool.name}: {e}")
    
    logger.info(f"🔧 Created {len(tools)} tools total")
    return tools
