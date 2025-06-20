# utils.py - Utility functions for APC Case Study Generator

import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import aiofiles
import aiofiles.os
import mcp.types as types

logger = logging.getLogger(__name__)

# Response helpers
def error_response(message: str) -> List[types.TextContent]:
    """Create an error response."""
    logger.error(message)
    return [types.TextContent(type="text", text=f"Error: {message}")]

def success_response(content: str) -> List[types.TextContent]:
    """Create a success response."""
    return [types.TextContent(type="text", text=content)]

# Text processing
def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())

def extract_text_from_json_document(json_data: Dict[str, Any]) -> str:
    """Extract text content from the JSON document structure."""
    if 'content' in json_data and 'chunks' in json_data['content']:
        texts = []
        for chunk in json_data['content']['chunks']:
            if 'text' in chunk:
                texts.append(chunk['text'])
        return '\n\n'.join(texts)
    return json.dumps(json_data, indent=2)

# File operations
async def read_json_file_async(file_path: Path, max_size: int = 10 * 1024 * 1024) -> Dict[str, Any]:
    """Read and parse a JSON file asynchronously."""
    # Check file size
    stat = await aiofiles.os.stat(file_path)
    if stat.st_size > max_size:
        raise ValueError(f"File too large: {file_path} ({stat.st_size} bytes)")
    
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {str(e)}")
        raise ValueError(f"Invalid JSON in {file_path}: {str(e)}") from e

async def get_available_files(directory: Path, extension: str = ".json") -> List[str]:
    """Get list of available files in a directory."""
    try:
        files = []
        for file_path in directory.glob(f"*{extension}"):
            if is_valid_json_file(file_path):
                files.append(file_path.stem)
        return sorted(files)
    except Exception as e:
        logger.error(f"Error listing files in {directory}: {str(e)}")
        return []

def is_valid_json_file(file_path: Path) -> bool:
    """Check if a file is a valid JSON file."""
    return (
        file_path.is_file() and
        file_path.suffix == ".json" and
        not any(part.startswith('.') for part in file_path.parts)
    )

def validate_path_security(file_path: Path, base_dir: Path) -> None:
    """Validate that a path is within the base directory."""
    try:
        resolved_path = file_path.resolve()
        resolved_path.relative_to(base_dir)
    except (ValueError, RuntimeError) as e:
        raise ValueError(f"Path outside base directory: {file_path}") from e

# Pattern matching
def find_patterns(text: str, patterns: Dict[str, str]) -> Dict[str, List[str]]:
    """Find all pattern matches in text."""
    results = {}
    for pattern_name, pattern in patterns.items():
        matches = re.findall(pattern, text)
        if matches:
            results[pattern_name] = matches
    return results

def check_section_exists(text: str, section: str) -> bool:
    """Check if a section exists in text."""
    pattern = rf"\b{section}\b"
    return bool(re.search(pattern, text, re.IGNORECASE))

# Metrics extraction
def extract_percentages(text: str) -> List[int]:
    """Extract percentage values from text."""
    percentages = re.findall(r'(\d+)%', text)
    return [int(p) for p in percentages]

def extract_amounts(text: str) -> List[str]:
    """Extract currency amounts from text."""
    return re.findall(r'£([\d,]+\.?\d*)', text)

# Template rendering
def render_template(template: str, context: Dict[str, Any]) -> str:
    """Simple template rendering with {variable} placeholders."""
    result = template
    for key, value in context.items():
        if isinstance(value, list):
            value = '\n'.join(f"• {item}" for item in value)
        result = result.replace(f"{{{key}}}", str(value))
    return result

def format_bullet_list(items: List[str], indent: str = "") -> str:
    """Format a list of items as bullet points."""
    return '\n'.join(f"{indent}• {item}" for item in items)

def format_numbered_list(items: List[str], indent: str = "") -> str:
    """Format a list of items as numbered points."""
    return '\n'.join(f"{indent}{i+1}. {item}" for i, item in enumerate(items))

# Validation helpers
def validate_word_count(text: str, limit: int) -> Tuple[bool, int, float]:
    """Validate word count against limit."""
    word_count = count_words(text)
    is_valid = word_count <= limit
    percentage = round((word_count / limit) * 100, 1)
    return is_valid, word_count, percentage

def assess_depth(text: str, indicators: List[str]) -> Tuple[int, str]:
    """Assess depth based on indicator presence."""
    text_lower = text.lower()
    count = sum(1 for indicator in indicators if indicator in text_lower)
    
    if count >= 8:
        depth = "strong"
    elif count >= 4:
        depth = "moderate"
    else:
        depth = "weak"
    
    return count, depth

# JSON Schema helpers
def create_enum_schema(name: str, description: str, values: List[str]) -> Dict[str, Any]:
    """Create a JSON schema for an enum parameter."""
    return {
        "type": "string",
        "description": description,
        "enum": values
    }

def create_object_schema(properties: Dict[str, Dict[str, Any]], required: List[str]) -> Dict[str, Any]:
    """Create a JSON schema for an object parameter."""
    return {
        "type": "object",
        "properties": properties,
        "required": required
    }

# Path utilities
def parse_resource_uri(uri: str, prefix: str = "file:///") -> str:
    """Parse a resource URI and return the path component."""
    if not uri.startswith(prefix):
        raise ValueError(f"Invalid URI scheme: {uri}")
    return uri[len(prefix):]

# Caching decorator
from functools import lru_cache

def cached_async(maxsize: int = 128):
    """Decorator for caching async function results."""
    def decorator(func):
        cache = {}
        
        async def wrapper(*args, **kwargs):
            key = str(args) + str(kwargs)
            if key in cache:
                return cache[key]
            result = await func(*args, **kwargs)
            if len(cache) >= maxsize:
                # Simple FIFO eviction
                cache.pop(next(iter(cache)))
            cache[key] = result
            return result
        
        wrapper.cache_clear = lambda: cache.clear()
        return wrapper
    
    return decorator