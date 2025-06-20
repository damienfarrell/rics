# mcp_server.py - Refactored APC Case Study Generator MCP Server

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from models import (
    ResourceCategory, SectionType, IssueType, CompetencyLevel,
    ValidationResult, ToolSchema
)
from tool_registry import ToolRegistry
from apc_domain import APCDomainService
from utils import (
    error_response, success_response, 
    read_json_file_async, extract_text_from_json_document,
    get_available_files, is_valid_json_file, validate_path_security,
    parse_resource_uri, format_bullet_list, render_template
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class APCCaseStudyServer:
    """Simplified MCP Server for APC Case Study Generation."""
    
    def __init__(self, resource_dir: Path = Path("mcp_resources")):
        # Load configuration
        self.config = self._load_config()
        
        # Initialize server
        self.server = Server(self.config['server']['name'])
        
        # Setup directories
        self.resource_dir = resource_dir.resolve()
        self.user_data_dir = self.resource_dir / self.config['directories']['user_data']
        self.examples_dir = self.resource_dir / self.config['directories']['examples']
        self.guides_dir = self.resource_dir / self.config['directories']['guides']
        
        # Initialize services
        self.domain = APCDomainService()
        self.tools = ToolRegistry()
        
        # Setup
        self._ensure_directories_exist()
        self._register_tools()
        self._setup_handlers()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config_path = Path("config.yaml")
        if config_path.exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Default configuration
            return {
                "server": {"name": "apc-case-study-generator", "version": "1.0.0"},
                "directories": {
                    "user_data": "user_data",
                    "examples": "apc_example_submissions",
                    "guides": "apc_submission_guides"
                }
            }
    
    def _ensure_directories_exist(self) -> None:
        """Ensure all required directories exist."""
        for directory in [self.resource_dir, self.user_data_dir, self.examples_dir, self.guides_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured directory exists: {directory}")
    
    def _setup_handlers(self) -> None:
        """Setup server protocol handlers."""
        self.server.list_resources()(self._handle_list_resources)
        self.server.read_resource()(self._handle_read_resource)
        self.server.list_tools()(lambda: self.tools.list_tools())
        self.server.call_tool()(self.tools.execute)
    
    def _register_tools(self) -> None:
        """Register all tools with their handlers."""
        # Basic file operations
        self.tools.register(
            name="read_user_data",
            handler=self._read_user_data,
            schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            description="Read user's APC experience data"
        )
        
        self.tools.register(
            name="read_example_submission",
            handler=self._read_example_submission,
            schema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the example file (without .json)"
                    }
                },
                "required": ["filename"]
            },
            description="Read a specific example APC submission"
        )
        
        self.tools.register(
            name="list_available_resources",
            handler=self._list_available_resources,
            schema={
                "type": "object",
                "properties": {
                    "resource_type": {
                        "type": "string",
                        "enum": ["examples", "guides", "all"],
                        "description": "Type of resources to list"
                    }
                },
                "required": ["resource_type"]
            },
            description="List all available examples and guides"
        )
        
        # Case study generation
        self.tools.register(
            name="generate_case_study_outline",
            handler=self._generate_case_study_outline,
            schema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project"
                    }
                },
                "required": ["project_name"]
            },
            description="Generate a structured case study outline"
        )
        
        # QS-specific tools
        self.tools.register(
            name="get_issue_template",
            handler=self._get_issue_template,
            schema={
                "type": "object",
                "properties": {
                    "issue_type": {
                        "type": "string",
                        "enum": [e.value for e in IssueType],
                        "description": "Type of QS issue/challenge"
                    }
                },
                "required": ["issue_type"]
            },
            description="Get detailed template for specific QS issue type"
        )
        
        self.tools.register(
            name="get_competency_guidance",
            handler=self._get_competency_guidance,
            schema={
                "type": "object",
                "properties": {
                    "competency": {
                        "type": "string",
                        "description": "RICS competency name"
                    },
                    "level": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 3,
                        "description": "Required competency level"
                    }
                },
                "required": ["competency", "level"]
            },
            description="Get guidance for demonstrating specific competency"
        )
        
        # Validation tools
        self.tools.register(
            name="validate_case_study",
            handler=self._validate_case_study,
            schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Case study content to validate"
                    }
                },
                "required": ["content"]
            },
            description="Validate case study against RICS requirements"
        )
        
        self.tools.register(
            name="check_confidentiality",
            handler=self._check_confidentiality,
            schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to check"
                    }
                },
                "required": ["content"]
            },
            description="Check for potential confidentiality breaches"
        )
        
        # Analysis tools
        self.tools.register(
            name="analyze_user_competencies",
            handler=self._analyze_user_competencies,
            schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            description="Analyze user's experience for competency evidence"
        )
        
        self.tools.register(
            name="generate_options_analysis",
            handler=self._generate_options_analysis,
            schema={
                "type": "object",
                "properties": {
                    "issue_description": {
                        "type": "string",
                        "description": "Description of the issue"
                    },
                    "industry": {
                        "type": "string",
                        "enum": ["rail", "commercial", "infrastructure"],
                        "description": "Industry context"
                    }
                },
                "required": ["issue_description", "industry"]
            },
            description="Generate options analysis for project issues"
        )
    
    # Generic file reading handler
    async def _read_resource_file(self, resource_type: str, filename: Optional[str] = None) -> str:
        """Generic handler for reading resource files."""
        directories = {
            "user_data": (self.user_data_dir, "APC Summary of Experience.json"),
            "example": (self.examples_dir, f"{filename}.json" if filename else ""),
            "guide": (self.guides_dir, f"{filename}.json" if filename else "")
        }
        
        if resource_type not in directories:
            return f"Unknown resource type: {resource_type}"
        
        directory, file_pattern = directories[resource_type]
        file_path = directory / file_pattern if file_pattern else None
        
        if not file_path or not file_path.exists():
            available = await get_available_files(directory)
            return f"File not found. Available files: {', '.join(available)}"
        
        try:
            data = await read_json_file_async(file_path)
            content = extract_text_from_json_document(data)
            return f"{resource_type.title()}: {content}"
        except Exception as e:
            return f"Error reading {resource_type}: {str(e)}"
    
    # Tool handlers (simplified)
    async def _read_user_data(self) -> str:
        """Read user's APC experience data."""
        return await self._read_resource_file("user_data")
    
    async def _read_example_submission(self, filename: str) -> str:
        """Read a specific example submission."""
        return await self._read_resource_file("example", filename)
    
    async def _list_available_resources(self, resource_type: str) -> str:
        """List available resources."""
        result = []
        
        if resource_type in ["examples", "all"]:
            examples = await get_available_files(self.examples_dir)
            if examples:
                result.append(f"Example Submissions:\n{format_bullet_list(examples)}")
        
        if resource_type in ["guides", "all"]:
            guides = await get_available_files(self.guides_dir)
            if guides:
                result.append(f"Submission Guides:\n{format_bullet_list(guides)}")
        
        return "\n\n".join(result) if result else f"No resources found for type: {resource_type}"
    
    async def _generate_case_study_outline(self, project_name: str) -> str:
        """Generate case study outline."""
        template = self.domain.templates.get("case_study_outline", "")
        return render_template(template, {"project_name": project_name})
    
    async def _get_issue_template(self, issue_type: str) -> str:
        """Get issue template."""
        template = self.domain.get_issue_template(issue_type)
        if not template:
            return f"Unknown issue type: {issue_type}"
        
        return f"""**QS Issue Template: {template.title}**

**Description:** {template.description}

**Typical Scenarios:**
{format_bullet_list(template.typical_scenarios)}

**Options Framework:**
{format_bullet_list(template.options_framework)}

**Competencies Demonstrated:**
{format_bullet_list(template.competencies_demonstrated)}"""
    
    async def _get_competency_guidance(self, competency: str, level: int) -> str:
        """Get competency guidance."""
        # Get from domain service
        mappings = self.domain.competency_mappings.get("core_competencies", {})
        if competency not in mappings:
            return f"Unknown competency: {competency}"
        
        return f"**{competency.replace('_', ' ').title()} - Level {level} Guidance**\n\n[Guidance content here]"
    
    async def _validate_case_study(self, content: str) -> str:
        """Validate case study content."""
        result = self.domain.validate_case_study(content)
        
        return f"""**Case Study Validation Report**

**Word Count:** {result.word_count}/{result.target_word_count} ({result.percentage_used}%)
**Structure Score:** {result.structure_score:.1%}
**Reflection Quality:** {result.reflection_quality}
**Overall Score:** {result.overall_score}/1.0

**Suggestions:**
{format_bullet_list(result.suggestions)}"""
    
    async def _check_confidentiality(self, content: str) -> str:
        """Check confidentiality compliance."""
        warnings = self.domain.check_confidentiality(content)
        
        if not warnings:
            return "✅ No confidentiality issues detected."
        
        return f"⚠️ Potential issues:\n{format_bullet_list(warnings)}"
    
    async def _analyze_user_competencies(self) -> str:
        """Analyze user competencies."""
        # Read user data first
        user_data = await self._read_user_data()
        if user_data.startswith("Error"):
            return user_data
        
        analysis = self.domain.analyze_user_competencies(user_data)
        
        return f"""**Competency Analysis**

**Suggested Competencies:**
{format_bullet_list(analysis.suggested_competencies)}

**Experience Gaps:**
{format_bullet_list(analysis.experience_gaps)}"""
    
    async def _generate_options_analysis(self, issue_description: str, industry: str) -> str:
        """Generate options analysis."""
        analysis = self.domain.generate_options_analysis(issue_description, industry)
        
        result = f"**Options Analysis for: {issue_description}**\n\n"
        
        for i, option in enumerate(analysis.options, 1):
            result += f"**Option {i}: {option['title']}**\n"
            result += f"- Cost Impact: {option['cost_impact']}\n"
            result += f"- Programme Impact: {option['programme_impact']}\n"
            result += f"- Risk Level: {option['risk_level']}\n"
            result += f"- Benefits: {option['benefits']}\n\n"
        
        return result
    
    # Resource handlers
    async def _handle_list_resources(self) -> List[types.Resource]:
        """List all resources."""
        resources = []
        
        if not self.resource_dir.exists():
            return resources
        
        for root, _, files in os.walk(self.resource_dir):
            root_path = Path(root)
            for file in files:
                if not file.endswith(".json"):
                    continue
                
                file_path = root_path / file
                if not is_valid_json_file(file_path):
                    continue
                
                try:
                    relative_path = file_path.relative_to(self.resource_dir)
                    resources.append(types.Resource(
                        uri=f"file:///{relative_path.as_posix()}",
                        name=file_path.stem,
                        description=str(relative_path),
                        mimeType="application/json"
                    ))
                except ValueError:
                    continue
        
        return resources
    
    async def _handle_read_resource(self, uri: str) -> str:
        """Read a resource by URI."""
        try:
            path_str = parse_resource_uri(uri)
            file_path = self.resource_dir / path_str
            
            validate_path_security(file_path, self.resource_dir)
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            data = await read_json_file_async(file_path)
            return extract_text_from_json_document(data)
            
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {str(e)}")
            raise
    
    async def run(self):
        """Run the MCP server."""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name=self.config['server']['name'],
                    server_version=self.config['server']['version'],
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

async def main():
    """Main entry point."""
    resource_dir = Path("mcp_resources")
    server = APCCaseStudyServer(resource_dir)
    
    logger.info(f"Starting APC Case Study Generator Server")
    logger.info(f"Resource directory: {resource_dir.resolve()}")
    
    await server.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())