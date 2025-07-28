from qwen_agent.tools import BaseTool
from typing import Dict, Any
from mcp_client import MCPClient

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
        import asyncio
        
        try:
            # Get current event loop
            loop = asyncio.get_event_loop()
            
            if loop.is_running():
                # We're in an async context, create a task
                future = asyncio.run_coroutine_threadsafe(
                    self.mcp_client.call_tool(self.name, params),
                    loop
                )
                result = future.result(timeout=30)
            else:
                # No event loop, create one
                result = asyncio.run(
                    self.mcp_client.call_tool(self.name, params)
                )
            
            return result
            
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