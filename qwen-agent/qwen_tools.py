from qwen_agent.tools import BaseTool
from typing import Dict, Any
from mcp_client import MCPClient
import asyncio
import concurrent.futures
import threading
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
        def run_async_tool():
            """Run the async MCP call in a new event loop"""
            loop = None
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run the MCP call with timeout
                result = loop.run_until_complete(
                    asyncio.wait_for(
                        self.mcp_client.call_tool(self.name, params),
                        timeout=25.0  # 25s timeout, less than thread timeout
                    )
                )
                
                return result
                
            except asyncio.TimeoutError:
                return f"MCP tool {self.name} timed out after 25 seconds"
            except Exception as e:
                return f"Error calling MCP tool {self.name}: {str(e)}"
            finally:
                if loop and not loop.is_closed():
                    try:
                        loop.close()
                    except Exception:
                        pass  # Ignore cleanup errors
        
        try:
            # FIXED: Use threading instead of asyncio.run_coroutine_threadsafe
            # This avoids potential deadlocks with the main event loop
            
            # Check if we're in the main thread with an event loop
            try:
                current_loop = asyncio.get_running_loop()
                # We're in an async context, use a thread
                result_container = {}
                exception_container = {}
                
                def thread_target():
                    try:
                        result_container['result'] = run_async_tool()
                    except Exception as e:
                        exception_container['error'] = e
                
                thread = threading.Thread(target=thread_target, daemon=True)
                thread.start()
                thread.join(timeout=30)  # 30 second timeout
                
                if thread.is_alive():
                    print(f"Warning: MCP tool {self.name} thread still running after timeout")
                    return f"MCP tool {self.name} timed out after 30 seconds"
                
                if 'error' in exception_container:
                    error = exception_container['error']
                    print(f"MCP tool {self.name} error: {error}")
                    return f"Error in MCP tool {self.name}: {str(error)}"
                
                result = result_container.get('result')
                if result is None:
                    return f"No result from MCP tool {self.name}"
                
                return result
                
            except RuntimeError:
                # No event loop running, safe to use asyncio.run
                try:
                    return asyncio.run(
                        asyncio.wait_for(
                            self.mcp_client.call_tool(self.name, params),
                            timeout=30.0
                        )
                    )
                except asyncio.TimeoutError:
                    return f"MCP tool {self.name} timed out after 30 seconds"
            
        except Exception as e:
            error_msg = f"Unexpected error in MCP tool {self.name}: {str(e)}"
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
