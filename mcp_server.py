import os
import base64
import mimetypes
from pathlib import Path
from typing import Any, Optional
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Initialize MCP server
server = Server("file-reader")

# Configure the resource directory
RESOURCE_DIR = Path("mcp_resources")

def get_mime_type(file_path: Path) -> str:
    """Get MIME type for a file."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"

def is_text_file(mime_type: str) -> bool:
    """Check if a file is likely text based on MIME type."""
    text_types = [
        "text/",
        "application/json",
        "application/xml",
        "application/javascript",
        "application/typescript",
        "application/yaml",
        "application/toml",
    ]
    return any(mime_type.startswith(t) for t in text_types)

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List all files in the mcp_resource directory."""
    resources = []
    
    if not RESOURCE_DIR.exists():
        return resources
    
    # Walk through all files in the resource directory
    for root, _, files in os.walk(RESOURCE_DIR):
        root_path = Path(root)
        for file in files:
            file_path = root_path / file
            
            # Get relative path from RESOURCE_DIR
            try:
                relative_path = file_path.relative_to(RESOURCE_DIR)
            except ValueError:
                continue
            
            # Skip hidden files
            if any(part.startswith('.') for part in relative_path.parts):
                continue
            
            mime_type = get_mime_type(file_path)
            
            resource = types.Resource(
                uri=f"file:///{relative_path.as_posix()}",
                name=file_path.name,
                description=f"File: {relative_path}",
                mimeType=mime_type,
            )
            
            resources.append(resource)
    
    return resources

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read a file from the mcp_resource directory."""
    # Parse the URI to get the path
    if not uri.startswith("file:///"):
        raise ValueError(f"Invalid URI scheme: {uri}")
    
    path = uri[8:]  # Remove "file:///"
    file_path = RESOURCE_DIR / path
    
    # Security: Ensure the resolved path is within RESOURCE_DIR
    try:
        file_path = file_path.resolve()
        RESOURCE_DIR.resolve()
        file_path.relative_to(RESOURCE_DIR.resolve())
    except (ValueError, RuntimeError):
        raise ValueError(f"Invalid path: {path}")
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    if not file_path.is_file():
        raise ValueError(f"Not a file: {path}")
    
    mime_type = get_mime_type(file_path)
    
    # Read file content
    try:
        if is_text_file(mime_type):
            # Read as text
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        else:
            # Read as binary and encode to base64
            with open(file_path, 'rb') as f:
                binary_content = f.read()
            # Return base64 encoded content for binary files
            return base64.b64encode(binary_content).decode('ascii')
    except Exception as e:
        raise RuntimeError(f"Error reading file: {str(e)}")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="read_file_content",
            description="Read file content from the mcp_resource directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file within mcp_resource directory"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding - 'auto' (default), 'text', or 'binary'",
                        "enum": ["auto", "text", "binary"],
                        "default": "auto"
                    }
                },
                "required": ["path"]
            }
        ),
        types.Tool(
            name="list_directory",
            description="List files and directories in a specific path within mcp_resource",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path within mcp_resource directory (empty for root)",
                        "default": ""
                    }
                },
                "required": []
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution."""
    
    if name == "read_file_content":
        path = arguments.get("path", "")
        encoding = arguments.get("encoding", "auto")
        
        file_path = RESOURCE_DIR / path
        
        # Security: Ensure the resolved path is within RESOURCE_DIR
        try:
            file_path = file_path.resolve()
            RESOURCE_DIR.resolve()
            file_path.relative_to(RESOURCE_DIR.resolve())
        except (ValueError, RuntimeError):
            return [types.TextContent(
                type="text",
                text=f"Error: Invalid path: {path}"
            )]
        
        if not file_path.exists():
            return [types.TextContent(
                type="text",
                text=f"Error: File not found: {path}"
            )]
        
        if not file_path.is_file():
            return [types.TextContent(
                type="text",
                text=f"Error: Not a file: {path}"
            )]
        
        mime_type = get_mime_type(file_path)
        file_size = file_path.stat().st_size
        
        try:
            if encoding == "binary" or (encoding == "auto" and not is_text_file(mime_type)):
                # Read as binary
                with open(file_path, 'rb') as f:
                    binary_content = f.read()
                content = base64.b64encode(binary_content).decode('ascii')
                return [types.TextContent(
                    type="text",
                    text=f"File: {path}\nMIME Type: {mime_type}\nSize: {file_size} bytes\nEncoding: base64\n\n{content}"
                )]
            else:
                # Read as text
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return [types.TextContent(
                    type="text",
                    text=f"File: {path}\nMIME Type: {mime_type}\nSize: {file_size} bytes\nEncoding: text\n\n{content}"
                )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"Error reading file: {str(e)}"
            )]
    
    elif name == "list_directory":
        path = arguments.get("path", "")
        dir_path = RESOURCE_DIR / path if path else RESOURCE_DIR
        
        # Security: Ensure the resolved path is within RESOURCE_DIR
        try:
            dir_path = dir_path.resolve()
            RESOURCE_DIR.resolve()
            dir_path.relative_to(RESOURCE_DIR.resolve())
        except (ValueError, RuntimeError):
            return [types.TextContent(
                type="text",
                text=f"Error: Invalid path: {path}"
            )]
        
        if not dir_path.exists():
            return [types.TextContent(
                type="text",
                text=f"Error: Directory not found: {path}"
            )]
        
        if not dir_path.is_dir():
            return [types.TextContent(
                type="text",
                text=f"Error: Not a directory: {path}"
            )]
        
        items = []
        
        try:
            for item in dir_path.iterdir():
                # Skip hidden files
                if item.name.startswith('.'):
                    continue
                
                if item.is_dir():
                    items.append(f"[DIR]  {item.name}/")
                else:
                    mime_type = get_mime_type(item)
                    size = item.stat().st_size
                    items.append(f"[FILE] {item.name} ({size} bytes, {mime_type})")
            
            # Sort directories first, then files
            items.sort(key=lambda x: (not x.startswith("[DIR]"), x.lower()))
            
            result = f"Directory listing for: {path or '/'}\n"
            result += "\n".join(items) if items else "Empty directory"
            
            return [types.TextContent(
                type="text",
                text=result
            )]
        
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"Error reading directory: {str(e)}"
            )]
    
    else:
        return [types.TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]

async def run():
    """Run the MCP server."""
    # Create the resource directory if it doesn't exist
    RESOURCE_DIR.mkdir(exist_ok=True)
    
    # Create a sample file if the directory is empty
    sample_file = RESOURCE_DIR / "readme.txt"
    if not any(RESOURCE_DIR.iterdir()):
        sample_file.write_text(
            "This is a sample file in the mcp_resource directory.\n"
            "Add more files here to make them available through the MCP server."
        )
    
    # Run the server using stdio transport
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="file-reader",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())