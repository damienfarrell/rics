# tool_registry.py - Tool registry for managing and executing tools

import logging
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass
import mcp.types as types
from models import ToolSchema

logger = logging.getLogger(__name__)

@dataclass
class RegisteredTool:
    """A registered tool with its handler and schema."""
    name: str
    handler: Callable
    schema: Dict[str, Any]
    description: str

class ToolRegistry:
    """Registry for managing MCP tools."""
    
    def __init__(self):
        self._tools: Dict[str, RegisteredTool] = {}
    
    def register(self, name: str, handler: Callable, schema: Dict[str, Any], description: str = "") -> None:
        """Register a tool with its handler and schema."""
        if name in self._tools:
            logger.warning(f"Tool '{name}' already registered, overwriting.")
        
        self._tools[name] = RegisteredTool(
            name=name,
            handler=handler,
            schema=schema,
            description=description or schema.get("description", "")
        )
        logger.info(f"Registered tool: {name}")
    
    def register_from_schema(self, schema: ToolSchema, handler: Callable) -> None:
        """Register a tool from a ToolSchema object."""
        self.register(
            name=schema.name,
            handler=handler,
            schema=schema.input_schema,
            description=schema.description
        )
    
    def list_tools(self) -> List[types.Tool]:
        """List all registered tools in MCP format."""
        tools = []
        for name, tool in self._tools.items():
            tools.append(types.Tool(
                name=name,
                description=tool.description,
                inputSchema=tool.schema
            ))
        return tools
    
    async def execute(self, name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
        """Execute a tool by name with given arguments."""
        if name not in self._tools:
            logger.error(f"Unknown tool requested: {name}")
            return [types.TextContent(
                type="text",
                text=f"Unknown tool: {name}. Available tools: {', '.join(self._tools.keys())}"
            )]
        
        tool = self._tools[name]
        logger.info(f"Executing tool: {name} with arguments: {arguments}")
        
        try:
            # Call the handler with arguments
            result = await tool.handler(**arguments)
            
            # Ensure result is in correct format
            if isinstance(result, str):
                return [types.TextContent(type="text", text=result)]
            elif isinstance(result, list) and all(isinstance(item, types.TextContent) for item in result):
                return result
            else:
                # Convert to TextContent if needed
                return [types.TextContent(type="text", text=str(result))]
                
        except TypeError as e:
            logger.error(f"Invalid arguments for tool {name}: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Invalid arguments for tool {name}: {str(e)}"
            )]
        except Exception as e:
            logger.error(f"Error executing tool {name}: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error executing tool {name}: {str(e)}"
            )]
    
    def get_tool_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get the schema for a specific tool."""
        if name in self._tools:
            return self._tools[name].schema
        return None
    
    def get_tool_names(self) -> List[str]:
        """Get list of all registered tool names."""
        return list(self._tools.keys())
    
    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        logger.info("Cleared all registered tools")