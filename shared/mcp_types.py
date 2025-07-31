from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

class MCPMessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"

@dataclass
class MCPRequest:
    id: str
    method: str
    params: Dict[str, Any]
    
@dataclass 
class MCPResponse:
    id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

@dataclass
class MCPTool:
    name: str
    description: str
    inputSchema: Dict[str, Any]

@dataclass
class MCPCapabilities:
    tools: List[MCPTool]
    version: str = "1.0"
