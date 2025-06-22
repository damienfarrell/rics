import os
import json
from pathlib import Path
from typing import Any, Dict, List
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("RICS Case Study")

# Constants
RESOURCES_DIR = Path(r"C:\Users\Damien\projects\rics\mcp_resources")

def get_all_json_files() -> List[Path]:
    """Recursively find all JSON files in the resources directory."""
    json_files = []
    if RESOURCES_DIR.exists():
        for file_path in RESOURCES_DIR.rglob("*.json"):
            json_files.append(file_path)
    return json_files

def load_json_file(file_path: Path) -> Dict[str, Any] | None:
    """Load and parse a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"Failed to load {file_path}: {str(e)}"}

@mcp.resource("json://files/list")
def list_json_files() -> str:
    """List all available JSON files in the RICS resources directory."""
    files = get_all_json_files()
    file_list = []
    for file_path in files:
        relative_path = file_path.relative_to(RESOURCES_DIR)
        file_list.append(str(relative_path))
    
    return "\n".join([
        f"Available RICS Case Study JSON Files ({len(file_list)} total):",
        "=" * 50,
        "\n".join(file_list)
    ])

@mcp.tool()
def read_json_file(path: str) -> str:
    """Read a specific JSON file from the resources directory.
    
    Args:
        path: Path to the JSON file relative to the resources directory
    """
    file_path = RESOURCES_DIR / path
    # Security check - ensure the path doesn't escape our resources directory
    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(RESOURCES_DIR.resolve())):
            return json.dumps({"error": "Invalid path - access denied"}, indent=2)
    except:
        return json.dumps({"error": "Invalid path"}, indent=2)
    
    if not file_path.exists():
        return json.dumps({"error": f"File not found: {path}"}, indent=2)
    
    if not file_path.suffix.lower() == '.json':
        return json.dumps({"error": "Only JSON files are supported"}, indent=2)
    
    data = load_json_file(file_path)
    return json.dumps(data, indent=2)

@mcp.tool()
def search_json_content(keyword: str, case_sensitive: bool = False) -> str:
    """Search for a keyword across all JSON files in the RICS resources.
    
    Args:
        keyword: The keyword to search for
        case_sensitive: Whether the search should be case-sensitive (default: False)
    """
    results = []
    files = get_all_json_files()
    
    search_term = keyword if case_sensitive else keyword.lower()
    
    for file_path in files:
        try:
            content = json.dumps(load_json_file(file_path))
            search_content = content if case_sensitive else content.lower()
            
            if search_term in search_content:
                relative_path = file_path.relative_to(RESOURCES_DIR)
                # Find the lines containing the keyword
                lines = content.split('\n')
                matching_lines = []
                for i, line in enumerate(lines):
                    line_to_search = line if case_sensitive else line.lower()
                    if search_term in line_to_search:
                        matching_lines.append(f"  Line {i+1}: {line.strip()}")
                
                results.append({
                    "file": str(relative_path),
                    "matches": len(matching_lines),
                    "preview": matching_lines[:3]  # Show first 3 matching lines
                })
        except Exception as e:
            continue
    
    if not results:
        return f"No matches found for '{keyword}'"
    
    output = [f"Search results for '{keyword}' ({'case-sensitive' if case_sensitive else 'case-insensitive'}):"]
    output.append("=" * 50)
    
    for result in results:
        output.append(f"\nFile: {result['file']}")
        output.append(f"Matches: {result['matches']}")
        output.append("Preview:")
        output.extend(result['preview'])
        if result['matches'] > 3:
            output.append(f"  ... and {result['matches'] - 3} more matches")
    
    return "\n".join(output)

@mcp.tool()
def get_json_structure(path: str, max_depth: int = 3) -> str:
    """Get the structure of a JSON file without showing all the data.
    
    Args:
        path: Path to the JSON file relative to the resources directory
        max_depth: Maximum depth to explore (default: 3)
    """
    file_path = RESOURCES_DIR / path
    
    # Security check
    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(RESOURCES_DIR.resolve())):
            return "Error: Invalid path - access denied"
    except:
        return "Error: Invalid path"
    
    if not file_path.exists():
        return f"Error: File not found: {path}"
    
    data = load_json_file(file_path)
    if data is None:
        return "Error: Failed to load JSON file"
    
    def explore_structure(obj: Any, depth: int = 0, prefix: str = "") -> List[str]:
        lines = []
        if depth > max_depth:
            lines.append(f"{prefix}...")
            return lines
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{prefix}{key}: {type(value).__name__}")
                    lines.extend(explore_structure(value, depth + 1, prefix + "  "))
                else:
                    lines.append(f"{prefix}{key}: {type(value).__name__}")
        elif isinstance(obj, list):
            if obj:
                lines.append(f"{prefix}[0]: {type(obj[0]).__name__}")
                if isinstance(obj[0], (dict, list)):
                    lines.extend(explore_structure(obj[0], depth + 1, prefix + "  "))
            lines.append(f"{prefix}... ({len(obj)} items total)")
        
        return lines
    
    output = [f"Structure of {path}:", "=" * 50]
    output.extend(explore_structure(data))
    return "\n".join(output)

@mcp.prompt()
def case_study_drafting() -> str:
    """Draft a RICS Case Study"""
    return """
    
Create a RICS APC Quantity Surveying case study that will pass assessment by following these steps:

STEP 1 - UNDERSTAND FILE STRUCTURE:
- Read `/mcp_index.json` and `/folder_map.json` to understand the data structure
- Use `get_json_structure` to preview file contents before reading
- Note the types of documents available (guidance notes, examples, user data)

STEP 2 - ANALYZE CANDIDATE PROFILE:
- Read ALL json files in `/user_data/` to understand the candidate's experience
- Use `search_json_content` to find mentions of the candidate's name across all files
- Extract: project names, values, roles, competencies demonstrated, achievements

STEP 3 - LEARN FROM SUCCESSFUL EXAMPLES:
- Read case studies from `/apc_example_submissions/`
- Extract successful patterns:
  * How complex issues are introduced
  * How personal leadership is demonstrated  
  * How achievements are quantified
  * How competencies are linked
  * Common phrases for Level 3 demonstration
  * Typical financial impact ranges (£1m-£10m+)
  * Structure of option analysis

STEP 4 - UNDERSTAND REQUIREMENTS:
- Read `/apc_submission_guides/Case Study Essentials.json` for structure requirements
- Read `/apc_submission_guides/APC-Candidate-guide_final_February-2024.json` for assessment criteria
- Document: word limits, required sections, competency requirements

STEP 5 - SEARCH FOR RELEVANT GUIDANCE:
Before selecting issues:
- Use `search_json_content("commercial management")` for baseline understanding
- Search for potential issue types: "variation", "acceleration", "dispute", "risk", "value engineering"
- Map search results to specific guidance notes

STEP 6 - SELECT TWO ISSUES:
ISSUE SELECTION FRAMEWORK - Score each potential issue (1-5):
- Financial Impact: £1-2m (3), £2-5m (4), £5m+ (5)
- Decision Authority: Assisted (1), Led (3), Sole decision-maker (5)  
- Complexity: 3 options (3), 4-5 options (4), 6+ options (5)
- Innovation: Standard approach (1), Modified approach (3), Novel solution (5)
- Measurability: Estimated outcome (3), Partial metrics (4), Full quantification (5)

Select issues scoring 15+ total points that:
✓ Demonstrate DIFFERENT core competencies
✓ Show progression from analysis to implementation
✓ Have clear, quantifiable outcomes
✓ Required YOUR judgment (not following procedures)

STEP 7 - READ TARGETED GUIDANCE:
For each selected issue:
- First read `/guidance_notes/Commercial-management-of-construction_1st-edition.json`
- Use `search_json_content` with issue-specific terms
- Read the 2-3 most relevant guidance notes
- Document which guidance informed your technical approach

Common guidance note mappings:
- Variations: Valuing-change_1st-edition_120325.json
- Delays/Acceleration: Extensions-of-time.json, Acceleration_2nd-ed_2024.json
- Disputes: Conflict-avoidance-and-dispute-resolution-in-construction_1st-edition.json
- Final Accounts: final_account_procedures_1st_edition_rics.json
- Risk: Management-of-risk_1st-edition_120325.json
- Loss/Expense: Ascertaining-loss-and-expense_2nd_July-2024.json

STEP 8 - WRITE CASE STUDY:

INTRODUCTION (600 words):
Project: [Name from user data, £Xm value, duration, location, procurement route]
Role: "As [exact title], I was responsible for..." [5-7 specific duties]
Team: "I managed a team of..." / "I reported to..."
Selection: "I selected this project because it presented complex challenges including..."
[List 3-4 complexity factors that link to your issues]

MY APPROACH (1,500 words - 750 per issue):

Issue 1: [Descriptive title]
CHALLENGE:
"The project faced [specific situation] which threatened to [impact] resulting in potential [£X cost/Y week delay]."

ANALYSIS:
"Drawing on RICS guidance on [topic - cite specific guidance note], I evaluated the following options:"

Option 1: [Traditional approach]
- Advantages: [2-3 points with cost/time implications]  
- Disadvantages: [2-3 points with risks]
- Financial Impact: £X cost/saving
- Programme Impact: Y weeks delay/acceleration

Option 2: [Alternative approach]
- Advantages: [2-3 points]
- Disadvantages: [2-3 points]  
- Financial Impact: £X
- Programme Impact: Y weeks

Option 3: [Innovative approach]
- Advantages: [2-3 points]
- Disadvantages: [2-3 points]
- Financial Impact: £X  
- Programme Impact: Y weeks

DECISION:
"After consulting with [stakeholders], I recommended Option [X] because..."
"I presented this to the client emphasizing..."

IMPLEMENTATION:
"I led the implementation by..."
"Key challenges during execution included..."

OUTCOME:
"This resulted in:"
- Financial: "Saved £X / Recovered £Y / Avoided £Z exposure"
- Programme: "Accelerated completion by X weeks"
- Relationship: "Client commended the approach, stating..."

Issue 2: [Follow same structure]

MY ACHIEVEMENTS (600 words):

COMPETENCY EVIDENCE MAP:
Primary Competency - [e.g., Commercial Management Level 3]:
"I demonstrated strategic cost management by [specific example with quantified outcome]"

Secondary Competency - [e.g., Contract Practice Level 3]:  
"I showed advanced contractual expertise through [specific example]"

Supporting Competency - [e.g., Client Care Level 2]:
"I maintained stakeholder relationships by [specific example]"

KEY ACHIEVEMENTS:
Financial:
- "Saved £X through [specific action]"
- "Recovered £Y by [specific action]"
- "Mitigated £Z risk exposure"

Programme:
- "Accelerated programme by X weeks"
- "Avoided Y weeks delay"

Recognition:
- "Client feedback: '[specific quote]'"
- "Project won [award/commendation]"
- "Approach adopted as best practice"

CONCLUSION (300 words):

SUCCESS FACTORS:
"My approach succeeded due to:
1. [Factor] - which enabled [outcome]
2. [Factor] - which resulted in [outcome]
3. [Factor] - which achieved [outcome]"

LESSONS LEARNED:
"Key insights from this experience:
1. [Learning point] - I now apply this by...
2. [Learning point] - This has improved my...
3. [Learning point] - I share this with my team through..."

PROFESSIONAL DEVELOPMENT:
"This project advanced my competencies by..."
"I continue to apply these learnings in my current role by..."

STEP 9 - VALIDATE CASE STUDY:
✓ Word count: Introduction (600), Approach (1500), Achievements (600), Conclusion (300)
✓ Two distinct issues demonstrating different competencies
✓ Minimum £1m impact per issue clearly stated
✓ 3+ options analyzed with advantages/disadvantages
✓ Personal pronouns used ("I" not "we")  
✓ Quantified outcomes for each issue
✓ Technical accuracy aligned with RICS guidance
✓ Clear competency evidence at Level 3
✓ Specific examples not generic statements

KEY PHRASES TO INCLUDE:
- "I identified that..."
- "My analysis concluded..."
- "I recommended to the client..."
- "I took responsibility for..."
- "This achieved a saving of £..."
- "I mitigated the risk by..."
- "The client acknowledged that..."

IF INSUFFICIENT PROJECT COMPLEXITY:
- Aggregate related smaller issues into strategic themes
- Emphasize innovative approaches to routine challenges
- Highlight risk mitigation preventing larger issues
- Show process improvements with cumulative impact
- Demonstrate how standard procedures were enhanced

THROUGHOUT:
✓ Use active voice and "I" statements
✓ Be specific with numbers, dates, and outcomes
✓ Reference RICS guidance for technical credibility
✓ Show progression from problem to solution
✓ Demonstrate judgment not just process following
✓ Link every achievement to competency evidence

COMPETENCY EVIDENCE
Ensure you demonstrate these at Level 3:
 Commercial Management - strategic cost advice
 Contract Practice - complex contractual issues
 Financial Control - reporting and forecasting

"""

if __name__ == "__main__":
    # Run the server
    mcp.run(transport='stdio')