import os
import json
import logging
from pathlib import Path
from typing import Any, Optional, Dict, List, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import aiofiles
import aiofiles.os
from functools import lru_cache

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
SERVER_NAME = "apc-case-study-generator"
SERVER_VERSION = "1.0.0"
URI_PREFIX = "file:///"
JSON_EXTENSION = ".json"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Resource categories
class ResourceCategory(Enum):
    USER_DATA = "user_data"
    EXAMPLE = "example"
    GUIDE = "guide"
    GENERAL = "general"

# Section types for extraction
class SectionType(Enum):
    INTRODUCTION = "introduction"
    KEY_ISSUES = "key_issues"
    ACHIEVEMENTS = "achievements"
    REFLECTION = "reflection"
    ALL = "all"

@dataclass
class ResourceInfo:
    """Information about a resource file."""
    path: Path
    relative_path: Path
    category: ResourceCategory
    name: str
    description: str

class APCCaseStudyServer:
    """MCP Server for APC Case Study Generation."""
    
    def __init__(self, resource_dir: Path):
        self.server = Server(SERVER_NAME)
        self.resource_dir = resource_dir.resolve()
        
        # Define specific directories
        self.user_data_dir = self.resource_dir / "user_data"
        self.examples_dir = self.resource_dir / "apc_example_submissions"
        self.guides_dir = self.resource_dir / "apc_submission_guides"
        
        # Initialize directories
        self._ensure_directories_exist()
        
        # Setup server handlers
        self._setup_handlers()
        
        # Cache for file contents
        self._file_cache: Dict[str, Dict[str, Any]] = {}
    
    def _ensure_directories_exist(self) -> None:
        """Ensure all required directories exist."""
        for directory in [self.resource_dir, self.user_data_dir, self.examples_dir, self.guides_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured directory exists: {directory}")
    
    def _setup_handlers(self) -> None:
        """Setup all server handlers."""
        self.server.list_resources()(self.handle_list_resources)
        self.server.read_resource()(self.handle_read_resource)
        self.server.list_tools()(self.handle_list_tools)
        self.server.call_tool()(self.handle_call_tool)
    
    def _categorize_file(self, relative_path: Path) -> ResourceCategory:
        """Categorize a file based on its path."""
        path_str = str(relative_path)
        if "user_data" in path_str:
            return ResourceCategory.USER_DATA
        elif "apc_example_submissions" in path_str:
            return ResourceCategory.EXAMPLE
        elif "apc_submission_guides" in path_str:
            return ResourceCategory.GUIDE
        return ResourceCategory.GENERAL
    
    def _is_valid_json_file(self, file_path: Path) -> bool:
        """Check if a file is a valid JSON file."""
        return (
            file_path.is_file() and
            file_path.suffix == JSON_EXTENSION and
            not any(part.startswith('.') for part in file_path.parts)
        )
    
    def _validate_path_security(self, file_path: Path) -> None:
        """Validate that a path is within the resource directory."""
        try:
            resolved_path = file_path.resolve()
            resolved_path.relative_to(self.resource_dir)
        except (ValueError, RuntimeError) as e:
            raise ValueError(f"Path outside resource directory: {file_path}") from e
    
    async def _read_json_file_async(self, file_path: Path) -> Dict[str, Any]:
        """Read and parse a JSON file asynchronously."""
        # Check cache first
        cache_key = str(file_path)
        if cache_key in self._file_cache:
            return self._file_cache[cache_key]
        
        # Check file size
        stat = await aiofiles.os.stat(file_path)
        if stat.st_size > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {file_path} ({stat.st_size} bytes)")
        
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
                # Cache the result
                self._file_cache[cache_key] = data
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {str(e)}")
            raise ValueError(f"Invalid JSON in {file_path}: {str(e)}") from e
        except Exception as e:
            logger.error(f"Error reading {file_path}: {str(e)}")
            raise RuntimeError(f"Error reading {file_path}: {str(e)}") from e
    
    def _extract_text_from_json_document(self, json_data: Dict[str, Any]) -> str:
        """Extract text content from the JSON document structure."""
        if 'content' in json_data and 'chunks' in json_data['content']:
            texts = []
            for chunk in json_data['content']['chunks']:
                if 'text' in chunk:
                    texts.append(chunk['text'])
            return '\n\n'.join(texts)
        return json.dumps(json_data, indent=2)
    
    async def _get_available_files(self, directory: Path, extension: str = JSON_EXTENSION) -> List[str]:
        """Get list of available files in a directory."""
        try:
            files = []
            for file_path in directory.glob(f"*{extension}"):
                if self._is_valid_json_file(file_path):
                    files.append(file_path.stem)
            return sorted(files)
        except Exception as e:
            logger.error(f"Error listing files in {directory}: {str(e)}")
            return []
    
    def _parse_resource_uri(self, uri: str) -> Path:
        """Parse a resource URI and return the corresponding file path."""
        if not uri.startswith(URI_PREFIX):
            raise ValueError(f"Invalid URI scheme: {uri}")
        
        path_str = uri[len(URI_PREFIX):]
        file_path = self.resource_dir / path_str
        
        # Security validation
        self._validate_path_security(file_path)
        
        return file_path
    
    async def handle_list_resources(self) -> List[types.Resource]:
        """List all JSON files in the mcp_resource directory."""
        resources = []
        
        if not self.resource_dir.exists():
            logger.warning(f"Resource directory does not exist: {self.resource_dir}")
            return resources
        
        try:
            # Walk through all files in the resource directory
            for root, _, files in os.walk(self.resource_dir):
                root_path = Path(root)
                for file in files:
                    if not file.endswith(JSON_EXTENSION):
                        continue
                    
                    file_path = root_path / file
                    
                    if not self._is_valid_json_file(file_path):
                        continue
                    
                    # Get relative path from RESOURCE_DIR
                    try:
                        relative_path = file_path.relative_to(self.resource_dir)
                    except ValueError:
                        continue
                    
                    # Categorize the resource
                    category = self._categorize_file(relative_path)
                    
                    resource = types.Resource(
                        uri=f"{URI_PREFIX}{relative_path.as_posix()}",
                        name=file_path.stem,
                        description=f"{category.value.replace('_', ' ').title()}: {relative_path}",
                        mimeType="application/json",
                    )
                    
                    resources.append(resource)
            
            logger.info(f"Listed {len(resources)} resources")
            return resources
            
        except Exception as e:
            logger.error(f"Error listing resources: {str(e)}")
            return []
    
    async def handle_read_resource(self, uri: str) -> str:
        """Read a JSON file from the mcp_resource directory."""
        try:
            file_path = self._parse_resource_uri(uri)
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            if not self._is_valid_json_file(file_path):
                raise ValueError(f"Not a valid JSON file: {file_path}")
            
            # Read file asynchronously
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            logger.info(f"Successfully read resource: {uri}")
            return content
            
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {str(e)}")
            raise
    
    async def handle_list_tools(self) -> List[types.Tool]:
        """List available tools."""
        tools = [
            types.Tool(
                name="read_user_data",
                description="Read user's APC experience data from their Summary of Experience",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            types.Tool(
                name="read_example_submission",
                description="Read a specific example APC submission to understand structure and content",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Name of the example submission file (without .json extension)"
                        }
                    },
                    "required": ["filename"]
                }
            ),
            types.Tool(
                name="read_submission_guide",
                description="Read a specific APC submission guide for best practices and requirements",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Name of the guide file (without .json extension)"
                        }
                    },
                    "required": ["filename"]
                }
            ),
            types.Tool(
                name="list_available_resources",
                description="List all available examples and guides in the system",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "resource_type": {
                            "type": "string",
                            "description": "Type of resources to list",
                            "enum": ["examples", "guides", "all"]
                        }
                    },
                    "required": ["resource_type"]
                }
            ),
            types.Tool(
                name="generate_case_study_outline",
                description="Generate a structured case study outline based on user data and RICS guidelines",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Name of the project from user's experience"
                        }
                    },
                    "required": ["project_name"]
                }
            ),
            types.Tool(
                name="extract_key_sections",
                description="Extract key section requirements from guides for case study writing",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "section_type": {
                            "type": "string",
                            "description": "Type of section to extract",
                            "enum": [s.value for s in SectionType]
                        }
                    },
                    "required": ["section_type"]
                }
            )
        ]
        
        logger.info(f"Listed {len(tools)} tools")
        return tools
    
    async def _handle_read_user_data(self) -> List[types.TextContent]:
        """Handle reading user data."""
        try:
            user_file = self.user_data_dir / "APC Summary of Experience.json"
            if not user_file.exists():
                return [types.TextContent(
                    type="text",
                    text="Error: User data file not found. Please ensure 'APC Summary of Experience.json' exists in the user_data directory."
                )]
            
            data = await self._read_json_file_async(user_file)
            text_content = self._extract_text_from_json_document(data)
            
            return [types.TextContent(
                type="text",
                text=f"User APC Experience Data:\n\n{text_content}"
            )]
        except Exception as e:
            logger.error(f"Error reading user data: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error reading user data: {str(e)}"
            )]
    
    async def _handle_read_file_from_directory(
        self, 
        directory: Path, 
        filename: str, 
        file_type: str
    ) -> List[types.TextContent]:
        """Generic handler for reading files from a specific directory."""
        if not filename:
            return [types.TextContent(
                type="text",
                text="Error: Please provide a filename"
            )]
        
        try:
            file_path = directory / f"{filename}{JSON_EXTENSION}"
            if not file_path.exists():
                available = await self._get_available_files(directory)
                return [types.TextContent(
                    type="text",
                    text=f"Error: File '{filename}' not found. Available {file_type}s: {', '.join(available)}"
                )]
            
            data = await self._read_json_file_async(file_path)
            text_content = self._extract_text_from_json_document(data)
            
            return [types.TextContent(
                type="text",
                text=f"{file_type} - {filename}:\n\n{text_content}"
            )]
        except Exception as e:
            logger.error(f"Error reading {file_type}: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error reading {file_type}: {str(e)}"
            )]
    
    async def _handle_list_available_resources(self, resource_type: str) -> List[types.TextContent]:
        """Handle listing available resources."""
        result = []
        
        try:
            if resource_type in ["examples", "all"]:
                examples = await self._get_available_files(self.examples_dir)
                if examples:
                    result.append(f"Available Example Submissions ({len(examples)}):\n" + 
                                "\n".join(f"  - {ex}" for ex in examples))
                else:
                    result.append("No example submissions found.")
            
            if resource_type in ["guides", "all"]:
                guides = await self._get_available_files(self.guides_dir)
                if guides:
                    result.append(f"Available Submission Guides ({len(guides)}):\n" + 
                                "\n".join(f"  - {g}" for g in guides))
                else:
                    result.append("No submission guides found.")
            
            if not result:
                result.append(f"No resources found for type: {resource_type}")
            
            return [types.TextContent(
                type="text",
                text="\n\n".join(result)
            )]
        except Exception as e:
            logger.error(f"Error listing resources: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error listing resources: {str(e)}"
            )]
    
    def _get_case_study_outline(self, project_name: str) -> str:
        """Generate a case study outline template."""
        return f"""Case Study Outline for: {project_name}

Based on RICS APC Case Study Guidelines:

1. INTRODUCTION (approx. 600 words)
   - Project overview
     • Scope and objectives
     • Value (construction/project cost)
     • Timeline (start and end dates)
     • Location and context
   - My roles and responsibilities
     • Position within the organization
     • Specific duties on this project
     • Reporting structure
   - Key stakeholders
     • Client/employer details
     • Design team members
     • Contractors and suppliers
     • End users
     • Include stakeholder map/organogram
   - Procurement details
     • Procurement route chosen
     • Contract type and rationale

2. MY APPROACH (approx. 1,500 words)
   - Key issue(s)/challenge(s)/anomalies faced
     • Identify 2-3 significant challenges
     • Explain why these were critical
     • Show complexity beyond routine work
   - Options analysis and evaluation
     • Present multiple solutions considered
     • Evaluation criteria used
     • Decision matrix or similar tools
   - Reasons for acceptance/rejection of options
     • Detailed rationale for each option
     • Risk assessment
     • Cost-benefit analysis
   - Implementation approach
     • Step-by-step process
     • Timeline and milestones
     • Resource allocation

3. MY ACHIEVEMENTS (approx. 600 words)
   - What was achieved and how
     • Specific outcomes delivered
     • Metrics and KPIs met
     • Problems solved
   - Examples of reasoned advice (Level 3)
     • Professional judgment exercised
     • Complex decisions made
     • Advice given to stakeholders
   - Rationale and justification
     • Evidence-based reasoning
     • Reference to standards/best practice
   - Value added to the project
     • Cost savings achieved
     • Time efficiencies
     • Quality improvements
     • Risk mitigation

4. CONCLUSION (approx. 300 words)
   - Reflection and self-analysis
     • Personal performance assessment
     • Strengths demonstrated
     • Areas for improvement
   - Learning points
     • Technical knowledge gained
     • Soft skills developed
     • Professional insights
   - Professional development
     • How this links to APC competencies
     • CPD opportunities identified
   - How this experience will influence future practice
     • Changes to approach
     • New methodologies to adopt
     • Enhanced professional judgment

APPENDICES:
   - Appendix A: Competencies demonstrated
     • Map to specific RICS competencies
     • Show achievement levels
   - Appendix B: Supporting documentation
     • Photographs
     • Drawings/plans
     • Programme/Gantt charts
     • Correspondence extracts
   - Declaration of confidentiality

KEY REQUIREMENTS:
✓ Total word count: 3,000 words (strict limit)
✓ Must demonstrate critical appraisal
✓ Include visual information where relevant
✓ Show honest self-reflection
✓ Demonstrate problem-solving ability
✓ Use professional language throughout
✓ Ensure logical flow and structure
✓ Reference relevant standards/regulations
✓ Maintain confidentiality throughout"""
    
    def _get_section_requirements(self) -> Dict[str, str]:
        """Get requirements for each section type."""
        return {
            SectionType.INTRODUCTION.value: """Introduction Requirements:
- Clear project overview with costs and timescales
- Your specific roles and responsibilities (not generic job description)
- Stakeholder identification and relationships (consider using a diagram)
- Context setting for the case study
- Brief outline of why this project was selected
- Procurement route and contract details
- Geographic and market context if relevant""",
            
            SectionType.KEY_ISSUES.value: """Key Issues/Challenges:
- Must identify significant challenges or anomalies (not routine tasks)
- Examples of suitable issues:
  • Budget constraints or cost overruns
  • Technical difficulties or design changes
  • Stakeholder conflicts or communication breakdowns
  • Regulatory or compliance challenges
  • Time pressures or programme delays
  • Quality issues or defects
  • Health & safety concerns
  • Environmental or sustainability challenges
- Should demonstrate problem-solving ability
- Show how issues were interconnected
- Explain why these were critical to project success""",
            
            SectionType.ACHIEVEMENTS.value: """Achievements Section:
- Specific examples of your contributions (not team achievements)
- Demonstrate Level 3 competencies (reasoned advice)
- Include:
  • Professional advice given
  • Decisions made and rationale
  • Value engineering contributions
  • Risk mitigation strategies implemented
  • Innovations introduced
- Quantify impact where possible:
  • Cost savings (£ or %)
  • Time savings (days/weeks)
  • Quality improvements
  • Risk reductions
- Link to APC competencies being demonstrated""",
            
            SectionType.REFLECTION.value: """Reflection Requirements:
- Honest self-assessment (assessors value authenticity)
- Structure your reflection:
  • What went well and why
  • What could be improved and how
  • Specific learning points identified
  • Skills developed during the project
- How experience will influence future practice:
  • New approaches to adopt
  • Processes to implement
  • Knowledge to share with team
- Professional development needs identified
- Never allocate blame to others
- Maintain confidentiality throughout
- Show emotional intelligence and self-awareness
- Demonstrate commitment to continuous improvement"""
        }
    
    async def _handle_generate_case_study_outline(self, project_name: str) -> List[types.TextContent]:
        """Handle generating a case study outline."""
        try:
            outline = self._get_case_study_outline(project_name)
            
            logger.info(f"Generated case study outline for project: {project_name}")
            return [types.TextContent(
                type="text",
                text=outline
            )]
        except Exception as e:
            logger.error(f"Error generating outline: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error generating outline: {str(e)}"
            )]
    
    async def _handle_extract_key_sections(self, section_type: str) -> List[types.TextContent]:
        """Handle extracting key sections from guides."""
        try:
            sections = self._get_section_requirements()
            
            if section_type == SectionType.ALL.value:
                result = "\n\n".join(f"{k.upper().replace('_', ' ')}:\n{v}" 
                                   for k, v in sections.items())
            else:
                result = sections.get(section_type, f"Section type '{section_type}' not found")
            
            return [types.TextContent(
                type="text",
                text=result
            )]
        except Exception as e:
            logger.error(f"Error extracting sections: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error extracting sections: {str(e)}"
            )]
    
    async def handle_call_tool(
        self, 
        name: str, 
        arguments: Dict[str, Any]
    ) -> List[types.TextContent]:
        """Handle tool execution."""
        logger.info(f"Executing tool: {name} with arguments: {arguments}")
        
        try:
            if name == "read_user_data":
                return await self._handle_read_user_data()
            
            elif name == "read_example_submission":
                filename = arguments.get("filename", "")
                return await self._handle_read_file_from_directory(
                    self.examples_dir, filename, "Example Submission"
                )
            
            elif name == "read_submission_guide":
                filename = arguments.get("filename", "")
                return await self._handle_read_file_from_directory(
                    self.guides_dir, filename, "Submission Guide"
                )
            
            elif name == "list_available_resources":
                resource_type = arguments.get("resource_type", "all")
                return await self._handle_list_available_resources(resource_type)
            
            elif name == "generate_case_study_outline":
                project_name = arguments.get("project_name", "Unnamed Project")
                return await self._handle_generate_case_study_outline(project_name)
            
            elif name == "extract_key_sections":
                section_type = arguments.get("section_type", SectionType.ALL.value)
                return await self._handle_extract_key_sections(section_type)
            
            else:
                logger.warning(f"Unknown tool requested: {name}")
                return [types.TextContent(
                    type="text",
                    text=f"Unknown tool: {name}. Available tools: read_user_data, read_example_submission, "
                         f"read_submission_guide, list_available_resources, generate_case_study_outline, "
                         f"extract_key_sections"
                )]
                
        except Exception as e:
            logger.error(f"Error executing tool {name}: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error executing tool {name}: {str(e)}"
            )]
    
    async def run(self):
        """Run the MCP server."""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name=SERVER_NAME,
                    server_version=SERVER_VERSION,
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )

async def main():
    """Main entry point."""
    # Configure the resource directory
    resource_dir = Path("mcp_resources")
    
    # Create and run the server
    server = APCCaseStudyServer(resource_dir)
    
    logger.info(f"Starting {SERVER_NAME} v{SERVER_VERSION}")
    logger.info(f"Resource directory: {resource_dir.resolve()}")
    
    await server.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())