from qwen_agent.tools import BaseTool
from typing import Dict, Any
from mcp_client import MCPClient
import asyncio
import logging

logger = logging.getLogger(__name__)

class MCPTool(BaseTool):
    """Qwen-Agent tool that calls MCP server"""
    
    def __init__(self, tool_name: str, description: str, inputSchema: Dict[str, Any], mcp_client: MCPClient):
        self.name = tool_name
        self.description = description
        self.parameters = inputSchema
        self.mcp_client = mcp_client
        super().__init__()
    
    def call(self, params: dict, **kwargs) -> str:
        """Called by Qwen-Agent when LLM decides to use this tool"""
        logger.info(f"DEBUG: ===== TOOL CALL STARTED =====")
        logger.info(f"DEBUG: Tool {self.name} called with params: {params}")
        logger.info(f"DEBUG: Tool {self.name} kwargs: {list(kwargs.keys())}")
        print(f"Tool {self.name}:")
        print(f"   params:{params}")
        print(f"   kwargs: {list(kwargs.keys())}")
        
        async def run_mcp_call():
            """Async wrapper for MCP call with proper timeout"""
            try:
                result = await asyncio.wait_for(
                    self.mcp_client.call_tool(self.name, params),
                    timeout=25.0
                )
                return result
            except asyncio.TimeoutError:
                return f"MCP tool {self.name} timed out after 25 seconds"
            except Exception as e:
                logger.error(f"MCP tool {self.name} call failed: {e}")
                return f"Error calling MCP tool {self.name}: {str(e)}"
        
        try:
            # Check if we're in an async context
            try:
                current_loop = asyncio.get_running_loop()
                # We're in an async context, use asyncio.to_thread (Python 3.9+)
                # This is the recommended approach per websockets 15+ documentation
                try:
                    # Use run_coroutine_threadsafe for running async code from sync context
                    future = asyncio.run_coroutine_threadsafe(run_mcp_call(), current_loop)
                    result = future.result(timeout=30.0)  # 30 second timeout
                    return result if result else f"No result from MCP tool {self.name}"
                except Exception as e:
                    # Fallback to asyncio.to_thread if available (Python 3.9+)
                    import sys
                    if sys.version_info >= (3, 9):
                        # Create a sync wrapper and run it in a thread
                        def sync_wrapper():
                            return asyncio.run(run_mcp_call())
                        
                        future = asyncio.run_coroutine_threadsafe(
                            asyncio.to_thread(sync_wrapper), current_loop
                        )
                        return future.result(timeout=30.0)
                    else:
                        raise e
                        
            except RuntimeError:
                # No event loop running, safe to use asyncio.run
                try:
                    return asyncio.run(run_mcp_call())
                except Exception as e:
                    logger.error(f"Asyncio.run failed for tool {self.name}: {e}")
                    return f"Error running MCP tool {self.name}: {str(e)}"
            
        except Exception as e:
            error_msg = f"Unexpected error in MCP tool {self.name}: {str(e)}"
            logger.error(error_msg)
            print(error_msg)
            return error_msg

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
                inputSchema=mcp_tool.inputSchema,
                mcp_client=mcp_client
            )
            tools.append(qwen_tool)
            logger.info(f"✅ Created tool: {mcp_tool.name}")
        except Exception as e:
            logger.error(f"❌ Failed to create tool {mcp_tool.name}: {e}")
    
    logger.info(f"🔧 Created {len(tools)} tools total")
    return tools
