from qwen_agent.tools import BaseTool
from typing import Dict, Any
from mcp_client import MCPClient
import asyncio
import threading
import time

class MCPTool(BaseTool):
    """Qwen-Agent tool that calls MCP server"""
    
    def __init__(self, tool_name: str, description: str, parameters: Dict[str, Any], mcp_client: MCPClient):
        super().__init__()
        self.name = tool_name
        self.description = description
        self.parameters = parameters
        self.mcp_client = mcp_client
    
    def call(self, params: dict) -> str:
        """Called by Qwen-Agent when LLM decides to use this tool"""
        
        def run_async_tool():
            """Run the async MCP call in a new event loop"""
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Run the MCP call
                result = loop.run_until_complete(
                    self.mcp_client.call_tool(self.name, params)
                )
                
                loop.close()
                return result
                
            except Exception as e:
                return f"Error calling MCP tool {self.name}: {str(e)}"
        
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
                
                thread = threading.Thread(target=thread_target)
                thread.start()
                thread.join(timeout=30)  # 30 second timeout
                
                if thread.is_alive():
                    return f"MCP tool {self.name} timed out"
                
                if 'error' in exception_container:
                    raise exception_container['error']
                
                return result_container.get('result', f"No result from MCP tool {self.name}")
                
            except RuntimeError:
                # No event loop running, safe to use asyncio.run
                return asyncio.run(
                    self.mcp_client.call_tool(self.name, params)
                )
            
        except Exception as e:
            error_msg = f"Error calling MCP tool {self.name}: {str(e)}"
            print(error_msg)
            return error_msg

def create_tools_from_mcp(mcp_client: MCPClient) -> list:
    """Create Qwen-Agent tools from MCP server capabilities"""
    tools = []
    
    for mcp_tool in mcp_client.tools:
        qwen_tool = MCPTool(
            tool_name=mcp_tool.name,
            description=mcp_tool.description,
            parameters=mcp_tool.parameters,
            mcp_client=mcp_client
        )
        tools.append(qwen_tool)
    
    return tools