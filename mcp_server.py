import os
import json
import logging
import re
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
    
    # NEW: Issue/Challenge Templates for Quantity Surveying
    def _get_qs_issue_templates(self) -> Dict[str, Any]:
        """Get quantity surveying issue/challenge templates."""
        return {
            "cost_control_and_budget_management": {
                "title": "Cost Overrun and Budget Recovery",
                "description": "Project experiencing significant cost overruns requiring intervention",
                "typical_scenarios": [
                    "Unforeseen ground conditions increasing foundation costs",
                    "Material price escalation beyond contract allowances",
                    "Scope creep without proper change control",
                    "Productivity issues affecting labour costs",
                    "Design changes post-contract award"
                ],
                "options_framework": [
                    "Value engineering to reduce costs",
                    "Renegotiate contract terms",
                    "Seek additional funding from client",
                    "Absorb costs and reduce profit margin",
                    "Claim compensation events under contract"
                ],
                "competencies_demonstrated": [
                    "Commercial management of construction (Level 3)",
                    "Project financial control and reporting (Level 3)",
                    "Quantification and costing of construction works (Level 3)",
                    "Contract practice (Level 2)",
                    "Communication and negotiation (Level 2)"
                ],
                "evidence_to_collect": [
                    "Original and revised budgets",
                    "Cost reports and CVRs",
                    "Meeting minutes discussing options",
                    "Value engineering proposals",
                    "Client correspondence"
                ]
            },
            "contract_administration_challenges": {
                "title": "Complex Variation Management",
                "description": "Managing significant variations while maintaining programme and budget",
                "typical_scenarios": [
                    "Client-instructed design changes mid-construction",
                    "Regulatory requirement changes affecting scope",
                    "Unforeseen utility diversions required",
                    "Weather-related programme extensions",
                    "Specification upgrades for performance requirements"
                ],
                "options_framework": [
                    "Standard contract variation procedure",
                    "Negotiate lump sum settlement",
                    "Implement daywork rates",
                    "Seek time extension with costs",
                    "Dispute and refer to adjudication"
                ],
                "competencies_demonstrated": [
                    "Contract practice (Level 3)",
                    "Commercial management of construction (Level 3)",
                    "Quantification and costing of construction works (Level 2)",
                    "Conflict avoidance, management and dispute resolution (Level 2)",
                    "Communication and negotiation (Level 3)"
                ],
                "evidence_to_collect": [
                    "Variation instructions and valuations",
                    "Programme impact assessments",
                    "Negotiation correspondence",
                    "Cost build-ups and supporting calculations",
                    "Contract clause references"
                ]
            },
            "procurement_and_tendering": {
                "title": "Subcontractor Procurement Challenges",
                "description": "Difficulties in procuring suitable subcontractors within budget and programme",
                "typical_scenarios": [
                    "Limited market interest in specialist works",
                    "All tenders received over budget allowance",
                    "Preferred contractor fails financial checks",
                    "Late design information affecting tender returns",
                    "Skills shortage in local market"
                ],
                "options_framework": [
                    "Expand geographical search area",
                    "Split package into smaller lots",
                    "Consider alternative technical solutions",
                    "Negotiate directly with preferred bidder",
                    "Delay works to improve market conditions"
                ],
                "competencies_demonstrated": [
                    "Procurement and tendering (Level 3)",
                    "Commercial management of construction (Level 2)",
                    "Communication and negotiation (Level 2)",
                    "Contract practice (Level 2)",
                    "Project financial control and reporting (Level 2)"
                ],
                "evidence_to_collect": [
                    "Tender documents and analysis",
                    "Market research evidence",
                    "Risk assessments",
                    "Recommendation reports",
                    "Final procurement strategy"
                ]
            },
            "measurement_and_valuation_disputes": {
                "title": "Final Account Disagreement",
                "description": "Significant disagreement on measurement and valuation requiring resolution",
                "typical_scenarios": [
                    "Disputed measurement of complex steelwork",
                    "Disagreement on daywork rates and hours",
                    "Retention release conditions not met",
                    "Claims for prolongation and disruption",
                    "Defects rectification cost disputes"
                ],
                "options_framework": [
                    "Independent expert determination",
                    "Mediation between parties",
                    "Detailed re-measurement exercise",
                    "Negotiate global settlement",
                    "Formal adjudication process"
                ],
                "competencies_demonstrated": [
                    "Quantification and costing of construction works (Level 3)",
                    "Conflict avoidance, management and dispute resolution (Level 3)",
                    "Contract practice (Level 3)",
                    "Communication and negotiation (Level 3)",
                    "Ethics, rules of conduct and professionalism (Level 2)"
                ],
                "evidence_to_collect": [
                    "Measurement records and calculations",
                    "Supporting drawings and specifications",
                    "Site records and photographs",
                    "Correspondence trail",
                    "Expert reports or opinions"
                ]
            },
            "programme_and_cash_flow": {
                "title": "Cash Flow and Payment Issues",
                "description": "Managing cash flow problems affecting project delivery",
                "typical_scenarios": [
                    "Client delaying interim payments",
                    "Subcontractor cash flow difficulties",
                    "Front-loaded programme requiring high early spend",
                    "Retention limits affecting working capital",
                    "Payment application disputes causing delays"
                ],
                "options_framework": [
                    "Renegotiate payment terms",
                    "Seek alternative financing arrangements",
                    "Implement programme acceleration",
                    "Request advance payments",
                    "Enforce payment notice procedures"
                ],
                "competencies_demonstrated": [
                    "Project financial control and reporting (Level 3)",
                    "Commercial management of construction (Level 2)",
                    "Contract practice (Level 2)",
                    "Accounting principles and procedures (Level 1)",
                    "Communication and negotiation (Level 2)"
                ],
                "evidence_to_collect": [
                    "Cash flow forecasts",
                    "Payment applications and certificates",
                    "Correspondence with client/bank",
                    "Programme analysis",
                    "Working capital calculations"
                ]
            },
            "risk_management": {
                "title": "Significant Risk Materialization",
                "description": "Major project risk becoming reality requiring mitigation strategy",
                "typical_scenarios": [
                    "Archaeological finds halting excavation",
                    "Key subcontractor insolvency",
                    "Material supply chain disruption",
                    "Extreme weather affecting programme",
                    "Planning condition compliance issues"
                ],
                "options_framework": [
                    "Implement contingency plans",
                    "Transfer risk through insurance claims",
                    "Renegotiate contract risk allocation",
                    "Seek time and cost extensions",
                    "Develop alternative delivery methods"
                ],
                "competencies_demonstrated": [
                    "Commercial management of construction (Level 3)",
                    "Project financial control and reporting (Level 2)",
                    "Contract practice (Level 2)",
                    "Communication and negotiation (Level 2)",
                    "Client care (Level 2)"
                ],
                "evidence_to_collect": [
                    "Risk registers and assessments",
                    "Mitigation strategy documents",
                    "Insurance correspondence",
                    "Impact assessments",
                    "Stakeholder communications"
                ]
            }
        }
    
    # NEW: Competency Mapping Tools for Quantity Surveying
    def _get_qs_competency_mapping(self) -> Dict[str, Any]:
        """Get quantity surveying competency mapping tools."""
        return {
            "core_competencies": {
                "commercial_management_of_construction": {
                    "level_1_requirements": {
                        "knowledge_descriptor": "Understanding of project costs, CVRs, and cost management principles",
                        "example_evidence": [
                            "Attended training on cost management systems",
                            "Studied company procedures for CVR preparation",
                            "Researched earned value analysis techniques",
                            "Learned about value engineering principles"
                        ],
                        "typical_activities": [
                            "Assisting with CVR preparation",
                            "Inputting cost data into systems",
                            "Observing value engineering exercises",
                            "Learning cost codes and structures"
                        ]
                    },
                    "level_2_requirements": {
                        "knowledge_descriptor": "Application of cost management techniques on real projects",
                        "example_evidence": [
                            "Prepared monthly CVRs for £2M project",
                            "Conducted cost/benefit analysis for design options",
                            "Managed subcontractor cost reporting",
                            "Implemented earned value analysis"
                        ],
                        "typical_activities": [
                            "Regular CVR preparation and reporting",
                            "Cost forecasting and variance analysis",
                            "Value engineering implementation",
                            "Cost benchmarking exercises"
                        ]
                    },
                    "level_3_requirements": {
                        "knowledge_descriptor": "Providing reasoned advice on commercial strategy and complex cost issues",
                        "example_evidence": [
                            "Advised client on procurement strategy saving £500k",
                            "Developed commercial recovery plan for troubled project",
                            "Recommended contract amendments to improve cost certainty",
                            "Led value engineering workshop saving 15% on costs"
                        ],
                        "typical_activities": [
                            "Strategic commercial advice to senior management",
                            "Complex cost dispute resolution",
                            "Commercial risk assessment and mitigation",
                            "Leading cost management initiatives"
                        ],
                        "reasoned_advice_examples": [
                            "Recommended target cost contract over lump sum due to design uncertainty, reducing client risk exposure by £200k",
                            "Advised against lowest tender due to insufficient programme float, preventing potential £1M delay costs",
                            "Proposed phased handover strategy to accelerate client revenue generation by 6 months"
                        ]
                    }
                },
                "contract_practice": {
                    "level_1_requirements": {
                        "knowledge_descriptor": "Understanding of contract formation, standard forms, and key provisions",
                        "example_evidence": [
                            "Studied JCT, NEC, and FIDIC contract forms",
                            "Attended training on Construction Act payment provisions",
                            "Researched case law on contract interpretation",
                            "Learned about collateral warranties and bonds"
                        ]
                    },
                    "level_2_requirements": {
                        "knowledge_descriptor": "Practical application of contract procedures and administration",
                        "example_evidence": [
                            "Administered NEC3 contract including compensation events",
                            "Prepared and issued payment notices under Construction Act",
                            "Managed contract variations totaling £800k",
                            "Drafted subcontract terms back-to-back with main contract"
                        ]
                    },
                    "level_3_requirements": {
                        "knowledge_descriptor": "Advising on complex contract issues and dispute resolution",
                        "reasoned_advice_examples": [
                            "Advised against liquidated damages clause due to client-caused delays, preventing wrongful deduction of £150k",
                            "Recommended early contractor involvement to reduce design risk, improving programme certainty by 8 weeks",
                            "Proposed contract amendment for shared savings mechanism, improving collaborative working"
                        ]
                    }
                },
                "quantification_and_costing": {
                    "level_1_requirements": {
                        "knowledge_descriptor": "Understanding of measurement rules and costing principles",
                        "example_evidence": [
                            "Studied NRM2 and CESMM4 measurement rules",
                            "Learned about different measurement methods and applications",
                            "Researched pricing databases and cost sources",
                            "Understanding of labour, plant, and material rates"
                        ]
                    },
                    "level_2_requirements": {
                        "knowledge_descriptor": "Practical measurement and valuation of construction works",
                        "example_evidence": [
                            "Measured and valued variations worth £1.2M using NRM2",
                            "Prepared interim valuations for 18-month project",
                            "Negotiated rates for new work items not in original BOQ",
                            "Agreed final account within 5% of forecast"
                        ]
                    },
                    "level_3_requirements": {
                        "knowledge_descriptor": "Complex measurement issues and providing valuation advice",
                        "reasoned_advice_examples": [
                            "Advised on measurement methodology for complex curved facade, establishing precedent for future projects",
                            "Recommended daywork rates for emergency works to ensure fair valuation under time pressure",
                            "Developed bespoke measurement approach for refurbishment works where standard rules insufficient"
                        ]
                    }
                },
                "project_financial_control": {
                    "level_3_requirements": {
                        "reasoned_advice_examples": [
                            "Implemented accrual accounting system improving cost visibility by 95%, enabling early intervention on budget variances",
                            "Advised on cash flow acceleration through revised payment terms, improving working capital by £2M",
                            "Developed risk-based contingency model, optimizing reserve allocation and reducing overall project costs by 3%"
                        ]
                    }
                },
                "procurement_and_tendering": {
                    "level_3_requirements": {
                        "reasoned_advice_examples": [
                            "Recommended two-stage tendering for complex M&E package, reducing design risk and improving contractor buy-in",
                            "Advised on framework vs single project procurement, delivering 12% cost savings through aggregated buying power",
                            "Proposed alternative technical solutions during tender clarifications, achieving £300k saving without compromising quality"
                        ]
                    }
                }
            },
            "issue_competency_matrix": {
                "cost_overrun_budget_recovery": {
                    "primary_competencies": [
                        "Commercial management of construction (Level 3)",
                        "Project financial control and reporting (Level 3)",
                        "Quantification and costing of construction works (Level 3)"
                    ],
                    "secondary_competencies": [
                        "Communication and negotiation (Level 2)",
                        "Contract practice (Level 2)",
                        "Client care (Level 2)"
                    ]
                },
                "variation_management": {
                    "primary_competencies": [
                        "Contract practice (Level 3)",
                        "Quantification and costing of construction works (Level 3)",
                        "Commercial management of construction (Level 2)"
                    ],
                    "secondary_competencies": [
                        "Communication and negotiation (Level 3)",
                        "Conflict avoidance and dispute resolution (Level 2)"
                    ]
                },
                "procurement_challenges": {
                    "primary_competencies": [
                        "Procurement and tendering (Level 3)",
                        "Commercial management of construction (Level 2)",
                        "Communication and negotiation (Level 2)"
                    ],
                    "secondary_competencies": [
                        "Contract practice (Level 2)",
                        "Project financial control and reporting (Level 2)"
                    ]
                },
                "final_account_disputes": {
                    "primary_competencies": [
                        "Quantification and costing of construction works (Level 3)",
                        "Conflict avoidance and dispute resolution (Level 3)",
                        "Contract practice (Level 3)"
                    ],
                    "secondary_competencies": [
                        "Communication and negotiation (Level 3)",
                        "Ethics and professional conduct (Level 2)"
                    ]
                }
            },
            "level_3_advice_framework": {
                "decision_making_process": [
                    "1. Problem identification and analysis",
                    "2. Stakeholder impact assessment",
                    "3. Option generation and evaluation",
                    "4. Risk assessment and mitigation",
                    "5. Cost-benefit analysis",
                    "6. Recommendation with clear rationale",
                    "7. Implementation planning",
                    "8. Success measurement criteria"
                ],
                "evidence_requirements": [
                    "Clear statement of the advice given",
                    "Explanation of the analysis undertaken",
                    "Justification for the recommendation",
                    "Evidence of implementation",
                    "Measurement of outcomes achieved"
                ],
                "quality_indicators": [
                    "Demonstrates technical competence",
                    "Shows commercial awareness",
                    "Considers multiple stakeholder perspectives",
                    "Balances cost, time, quality, and risk",
                    "Provides measurable benefits",
                    "Follows ethical and professional standards"
                ]
            },
            "competency_demonstration_checklist": {
                "mandatory_competencies": {
                    "must_achieve_level_2": [
                        "Ethics, rules of conduct and professionalism",
                        "Client care",
                        "Communication and negotiation",
                        "Health and safety",
                        "Accounting principles and procedures",
                        "Business planning",
                        "Conflict avoidance, management and dispute resolution",
                        "Data management",
                        "Diversity, inclusion and teamworking",
                        "Inclusive environments",
                        "Sustainability"
                    ]
                },
                "core_technical_competencies": {
                    "must_achieve_level_3": [
                        "Commercial management of construction",
                        "Contract practice",
                        "Construction technology and environmental services",
                        "Procurement and tendering",
                        "Project financial control and reporting",
                        "Quantification and costing of construction works"
                    ]
                },
                "optional_technical_competencies": {
                    "choose_2_achieve_level_2": [
                        "Contract administration",
                        "Programming and planning",
                        "Risk management",
                        "Value management",
                        "Project management",
                        "Construction law",
                        "Insolvency",
                        "Expert witness"
                    ]
                }
            },
            "writing_guidance": {
                "level_3_evidence_structure": {
                    "situation": "Describe the context and challenge faced",
                    "task": "Explain your specific role and responsibilities",
                    "action": "Detail the analysis, options considered, and advice given",
                    "result": "Quantify the outcome and lessons learned"
                },
                "professional_language_examples": {
                    "weak": "I helped with the cost report",
                    "strong": "I prepared comprehensive monthly CVRs, analyzing variances and forecasting final account position with 95% accuracy"
                },
                "quantification_examples": [
                    "Achieved cost savings of £250k (8% of project value)",
                    "Reduced programme duration by 6 weeks through value engineering",
                    "Negotiated final account settlement within 2% of forecast",
                    "Improved cash flow by £500k through payment term renegotiation"
                ]
            }
        }

    # NEW: Competency-specific templates
    def _get_competency_templates(self) -> Dict[str, Dict[str, str]]:
        """Get templates for different competencies."""
        return {
            "commercial_management": {
                "level_1": """Understanding of cost components (labour, plant, materials, overheads), CVR compilation, 
                value engineering principles, subcontractor management basics, and cost/benefit analysis concepts.""",
                "level_2": """Experience in cost forecasting, change management, interim valuations, earned value analysis, 
                subcontractor procurement, and financial reporting to senior management.""",
                "level_3": """Providing strategic cost advice to project teams and clients, leading commercial decisions, 
                implementing innovative cost management solutions, and advising on complex commercial issues with 
                significant financial implications."""
            },
            "contract_practice": {
                "level_1": """Knowledge of contract formation principles, standard forms (JCT, NEC, FIDIC), 
                statutory requirements (HGCRA, LDEDCA), and basic contract mechanisms.""",
                "level_2": """Experience administering contracts, managing variations and change control, 
                payment processes, and subcontract arrangements using standard forms.""",
                "level_3": """Advising on contract strategy, complex contractual interpretations, dispute resolution, 
                and providing reasoned advice on contractual risks and opportunities."""
            },
            "project_financial_control": {
                "level_1": """Understanding of CVR compilation, cost monitoring techniques, forecasting principles, 
                and change control procedures.""",
                "level_2": """Experience in budget management, cost reporting, variance analysis, and implementing 
                cost control systems on live projects.""",
                "level_3": """Providing strategic financial advice, implementing improved cost control systems, 
                and advising on complex financial scenarios with significant project implications."""
            },
            "procurement_and_tendering": {
                "level_1": """Knowledge of procurement routes, tendering procedures, evaluation criteria, 
                and EU procurement regulations.""",
                "level_2": """Experience in tender preparation, evaluation processes, contractor selection, 
                and managing procurement exercises.""",
                "level_3": """Advising on procurement strategy, complex tender evaluations, and providing 
                reasoned advice on contractor selection with significant commercial implications."""
            },
            "quantification_and_costing": {
                "level_1": """Understanding of measurement rules (NRM, CESMM), pricing principles, 
                and basic cost analysis techniques.""",
                "level_2": """Experience in taking off quantities, pricing variations, interim valuations, 
                and final account preparation.""",
                "level_3": """Providing expert advice on complex measurement issues, innovative costing approaches, 
                and resolving disputes over quantities and pricing."""
            }
        }
    
    # NEW: Competency mapping
    def _analyze_user_experience_for_competencies(self, user_data: str) -> Dict[str, Any]:
        """Analyze user's experience and suggest which competencies they can demonstrate."""
        competency_keywords = {
            "commercial_management": ["cost", "commercial", "budget", "CVR", "value engineering", "subcontractor", "profit"],
            "contract_practice": ["contract", "NEC", "JCT", "variation", "change", "dispute", "payment", "clause"],
            "project_financial_control": ["forecast", "budget", "financial", "reporting", "variance", "cash flow"],
            "procurement_and_tendering": ["tender", "procurement", "contractor selection", "evaluation", "quotation"],
            "quantification_and_costing": ["measurement", "quantities", "pricing", "rates", "valuation", "CESMM", "NRM"]
        }
        
        analysis = {
            "suggested_competencies": [],
            "strength_indicators": {},
            "experience_gaps": [],
            "suitable_projects": []
        }
        
        user_text = user_data.lower()
        
        for competency, keywords in competency_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in user_text)
            strength = "strong" if matches >= 5 else "moderate" if matches >= 3 else "weak"
            
            if matches >= 3:
                analysis["suggested_competencies"].append(competency)
                analysis["strength_indicators"][competency] = {
                    "strength": strength,
                    "keyword_matches": matches,
                    "keywords_found": [kw for kw in keywords if kw in user_text]
                }
            else:
                analysis["experience_gaps"].append(competency)
        
        return analysis
    
    # NEW: Content quality checker
    def _validate_case_study_content(self, content: str) -> Dict[str, Any]:
        """Validate case study against RICS requirements."""
        
        def count_words(text: str) -> int:
            return len(text.split())
        
        def check_structure(text: str) -> Dict[str, bool]:
            required_sections = ["introduction", "approach", "achievement", "conclusion"]
            section_checks = {}
            
            for section in required_sections:
                # Check for section headers (case insensitive)
                pattern = rf"\b{section}\b"
                section_checks[section] = bool(re.search(pattern, text, re.IGNORECASE))
            
            return section_checks
        
        def assess_reflection_depth(text: str) -> Dict[str, Any]:
            reflection_indicators = [
                "learnt", "learning", "reflect", "improved", "develop", "experience", 
                "future", "better", "mistake", "challenge", "growth"
            ]
            
            reflection_count = sum(1 for indicator in reflection_indicators if indicator in text.lower())
            
            return {
                "reflection_indicators_found": reflection_count,
                "depth_assessment": "strong" if reflection_count >= 8 else "moderate" if reflection_count >= 4 else "weak",
                "suggestions": self._generate_reflection_suggestions(reflection_count)
            }
        
        word_count = count_words(content)
        structure_check = check_structure(content)
        reflection_assessment = assess_reflection_depth(content)
        
        validation_result = {
            "word_count": {
                "current": word_count,
                "target": 3000,
                "status": "within_limit" if word_count <= 3000 else "over_limit",
                "percentage_used": round((word_count / 3000) * 100, 1)
            },
            "structure_check": structure_check,
            "structure_score": sum(structure_check.values()) / len(structure_check),
            "reflection_quality": reflection_assessment,
            "overall_score": self._calculate_overall_score(word_count, structure_check, reflection_assessment),
            "improvement_suggestions": self._generate_improvement_suggestions(word_count, structure_check, reflection_assessment)
        }
        
        return validation_result
    
    def _generate_reflection_suggestions(self, reflection_count: int) -> List[str]:
        """Generate suggestions for improving reflection."""
        suggestions = []
        
        if reflection_count < 4:
            suggestions.extend([
                "Add more reflection on what you learned from the experience",
                "Include discussion of how this experience will influence future practice",
                "Reflect on both positive outcomes and areas for improvement"
            ])
        elif reflection_count < 8:
            suggestions.extend([
                "Deepen your reflection with more specific examples",
                "Consider adding reflection on professional development gained"
            ])
        
        return suggestions
    
    def _calculate_overall_score(self, word_count: int, structure_check: Dict[str, bool], reflection_assessment: Dict[str, Any]) -> float:
        """Calculate an overall quality score."""
        word_score = 1.0 if word_count <= 3000 else max(0.5, 3000 / word_count)
        structure_score = sum(structure_check.values()) / len(structure_check)
        reflection_score = {"strong": 1.0, "moderate": 0.7, "weak": 0.4}[reflection_assessment["depth_assessment"]]
        
        return round((word_score * 0.3 + structure_score * 0.4 + reflection_score * 0.3), 2)
    
    def _generate_improvement_suggestions(self, word_count: int, structure_check: Dict[str, bool], reflection_assessment: Dict[str, Any]) -> List[str]:
        """Generate specific improvement suggestions."""
        suggestions = []
        
        if word_count > 3000:
            suggestions.append(f"Reduce word count by {word_count - 3000} words to meet the 3000 word limit")
        
        missing_sections = [section for section, present in structure_check.items() if not present]
        if missing_sections:
            suggestions.append(f"Add missing sections: {', '.join(missing_sections)}")
        
        suggestions.extend(reflection_assessment["suggestions"])
        
        return suggestions
    
    # NEW: Quality Assurance Features
    def _check_confidentiality_compliance(self, content: str) -> List[str]:
        """Check for potential confidentiality breaches."""
        warnings = []
        
        # Check for specific patterns that might indicate confidentiality issues
        patterns = {
            "specific_amounts": r"£[\d,]+\.?\d*",
            "company_names": r"\b[A-Z][a-z]+ (Ltd|Limited|Corporation|Corp|Inc)\b",
            "personal_names": r"\b[A-Z][a-z]+ [A-Z][a-z]+\b",
            "phone_numbers": r"\b\d{4,5}\s?\d{6}\b",
            "email_addresses": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        }
        
        for pattern_name, pattern in patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                warnings.append(f"Potential confidentiality issue - {pattern_name}: {len(matches)} instances found")
        
        return warnings
    
    def _assess_competency_demonstration_strength(self, content: str, competency: str) -> Dict[str, Any]:
        """Assess how well content demonstrates specific competencies."""
        competency_templates = self._get_competency_templates()
        
        if competency not in competency_templates:
            return {"error": f"Unknown competency: {competency}"}
        
        # Extract key terms from the competency template
        level_3_indicators = [
            "advised", "recommended", "strategic", "complex", "innovative", 
            "leadership", "decision", "significant", "critical", "expert"
        ]
        
        content_lower = content.lower()
        level_3_count = sum(1 for indicator in level_3_indicators if indicator in content_lower)
        
        # Look for specific evidence patterns
        evidence_patterns = [
            r"£[\d,]+", r"\d+%", r"\d+ weeks?", r"\d+ months?", 
            "saved", "reduced", "improved", "implemented"
        ]
        
        evidence_count = sum(len(re.findall(pattern, content)) for pattern in evidence_patterns)
        
        assessment = {
            "strength": "strong" if level_3_count >= 5 and evidence_count >= 3 else 
                       "moderate" if level_3_count >= 3 or evidence_count >= 2 else "weak",
            "level_3_indicators": level_3_count,
            "evidence_count": evidence_count,
            "level_demonstration": "clearly L3" if level_3_count >= 5 else "needs enhancement",
            "suggestions": self._generate_competency_suggestions(level_3_count, evidence_count)
        }
        
        return assessment
    
    def _generate_competency_suggestions(self, level_3_count: int, evidence_count: int) -> List[str]:
        """Generate suggestions for improving competency demonstration."""
        suggestions = []
        
        if level_3_count < 3:
            suggestions.append("Include more examples of strategic advice and complex decision-making")
        
        if evidence_count < 2:
            suggestions.append("Add quantified outcomes (cost savings, time reductions, etc.)")
        
        if level_3_count < 5:
            suggestions.append("Strengthen demonstration of Level 3 competency with more leadership examples")
        
        return suggestions
    
    # NEW: AI-assisted content enhancement
    def _enhance_reflection_section(self, basic_reflection: str, project_context: str) -> str:
        """Enhance reflection with deeper analysis and professional insights."""
        enhanced_reflection = f"""
**Enhanced Reflection on {project_context}:**

{basic_reflection}

**Professional Development Analysis:**
This experience significantly enhanced my professional capabilities in several key areas:

**Technical Skills:** The project challenged me to develop advanced cost management techniques, particularly in [specific area]. This experience demonstrated the importance of continuous learning and adaptation in complex project environments.

**Leadership and Decision-Making:** The key decisions I made, particularly around [specific decision], required careful consideration of multiple stakeholders' interests and demonstrated my ability to provide Level 3 professional advice.

**Future Practice Implications:**
- **Process Improvements:** I will implement [specific improvements] in future projects based on lessons learned
- **Risk Management:** This experience highlighted the importance of [specific risk management approach]
- **Stakeholder Engagement:** Future projects will benefit from [enhanced stakeholder management approach]

**Competency Development:**
This project provided substantial evidence for demonstrating RICS competencies at Level 3, particularly in areas of strategic thinking, complex problem-solving, and professional leadership.
"""
        return enhanced_reflection
    
    def _generate_options_analysis(self, issue_description: str, industry: str) -> str:
        """Generate realistic options analysis for given issues."""
        
        industry_factors = {
            "rail": {
                "considerations": ["possession constraints", "safety requirements", "Network Rail standards"],
                "typical_costs": "£50k-500k for minor works, £1M+ for major interventions",
                "timeframes": "6-18 months including approvals"
            },
            "commercial": {
                "considerations": ["tenant disruption", "retail trading impact", "planning constraints"],
                "typical_costs": "£100k-2M depending on scale",
                "timeframes": "3-12 months typical delivery"
            },
            "infrastructure": {
                "considerations": ["public impact", "utility diversions", "environmental constraints"],
                "typical_costs": "£500k-10M+ for major works",
                "timeframes": "12-36 months including consents"
            }
        }
        
        factors = industry_factors.get(industry, industry_factors["commercial"])
        
        analysis = f"""
**Options Analysis for: {issue_description}**

**Option 1: [Conservative Approach]**
- Cost Impact: {factors['typical_costs']} (lower end)
- Programme Impact: Standard timeframe - {factors['timeframes']}
- Key Considerations: {', '.join(factors['considerations'])}
- Risk Level: Low - proven methodology
- Benefits: Minimal disruption, established processes

**Option 2: [Innovative Solution]**
- Cost Impact: Premium of 15-25% for innovation
- Programme Impact: Potential 20-30% time saving
- Key Considerations: Technology adoption, specialist resources
- Risk Level: Medium - new methodology requires validation
- Benefits: Efficiency gains, potential for future replication

**Option 3: [Hybrid Approach]**
- Cost Impact: Balanced cost profile
- Programme Impact: Optimized timeline balancing risk and efficiency
- Key Considerations: Combines proven and innovative elements
- Risk Level: Medium-Low - managed innovation
- Benefits: Best of both approaches with controlled risk

**Evaluation Criteria:**
1. Cost effectiveness and value for money
2. Programme delivery certainty
3. Quality and performance outcomes
4. Risk profile and mitigation
5. Stakeholder impact and acceptance
"""
        return analysis

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
            ),
            # NEW QS-SPECIFIC TOOLS
            types.Tool(
                name="get_issue_template",
                description="Get detailed template for specific QS issue/challenge type",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "issue_type": {
                            "type": "string",
                            "enum": [
                                "cost_control_and_budget_management",
                                "contract_administration_challenges", 
                                "procurement_and_tendering",
                                "measurement_and_valuation_disputes",
                                "programme_and_cash_flow",
                                "risk_management"
                            ],
                            "description": "Type of QS issue/challenge"
                        }
                    },
                    "required": ["issue_type"]
                }
            ),
            types.Tool(
                name="get_competency_guidance",
                description="Get detailed guidance for demonstrating specific QS competency at required level",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "competency": {
                            "type": "string",
                            "enum": [
                                "commercial_management_of_construction",
                                "contract_practice",
                                "quantification_and_costing",
                                "project_financial_control",
                                "procurement_and_tendering",
                                "construction_technology"
                            ],
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
                }
            ),
            types.Tool(
                name="map_issue_to_competencies",
                description="Show which competencies can be demonstrated through specific issue types",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "issue_type": {
                            "type": "string",
                            "enum": [
                                "cost_control_and_budget_management",
                                "contract_administration_challenges",
                                "procurement_and_tendering", 
                                "measurement_and_valuation_disputes",
                                "programme_and_cash_flow",
                                "risk_management"
                            ],
                            "description": "Type of issue being used in case study"
                        }
                    },
                    "required": ["issue_type"]
                }
            ),
            types.Tool(
                name="get_level_3_advice_framework",
                description="Get structured framework for demonstrating Level 3 competencies with reasoned advice",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            types.Tool(
                name="analyze_user_competency_gaps",
                description="Analyze user's experience against pathway requirements and identify gaps",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pathway": {
                            "type": "string", 
                            "enum": ["quantity_surveying", "building_surveying", "project_management"],
                            "description": "APC pathway to analyze against"
                        },
                        "target_competencies": {
                            "type": "array", 
                            "items": {"type": "string"},
                            "description": "List of competencies to focus analysis on"
                        }
                    },
                    "required": ["pathway"]
                }
            ),
            types.Tool(
                name="generate_competency_evidence",
                description="Generate specific evidence statements for competencies based on user's projects",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "competency": {
                            "type": "string",
                            "description": "Specific competency to generate evidence for"
                        },
                        "level": {
                            "type": "integer", 
                            "minimum": 1, 
                            "maximum": 3,
                            "description": "Target competency level"
                        },
                        "project_context": {
                            "type": "string",
                            "description": "Project or context for the evidence"
                        }
                    },
                    "required": ["competency", "level", "project_context"]
                }
            ),
            types.Tool(
                name="validate_case_study_structure",
                description="Validate case study against RICS requirements and provide improvement suggestions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "case_study_text": {
                            "type": "string",
                            "description": "The case study content to validate"
                        },
                        "pathway": {
                            "type": "string",
                            "description": "APC pathway for validation"
                        }
                    },
                    "required": ["case_study_text"]
                }
            ),
            types.Tool(
                name="enhance_reflection_content",
                description="Enhance reflection section with deeper analysis and professional insights",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "basic_reflection": {
                            "type": "string",
                            "description": "Basic reflection content to enhance"
                        },
                        "project_context": {
                            "type": "string",
                            "description": "Project context for the reflection"
                        }
                    },
                    "required": ["basic_reflection", "project_context"]
                }
            ),
            types.Tool(
                name="generate_options_analysis",
                description="Generate realistic options analysis for project issues",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "issue_description": {
                            "type": "string",
                            "description": "Description of the issue requiring options analysis"
                        },
                        "industry": {
                            "type": "string",
                            "enum": ["rail", "commercial", "infrastructure", "residential", "healthcare"],
                            "description": "Industry context for the analysis"
                        }
                    },
                    "required": ["issue_description", "industry"]
                }
            ),
            types.Tool(
                name="check_confidentiality_compliance",
                description="Check case study content for potential confidentiality breaches",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Content to check for confidentiality issues"
                        }
                    },
                    "required": ["content"]
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
    
    # NEW QS-SPECIFIC TOOL HANDLERS
    async def _handle_get_issue_template(self, issue_type: str) -> List[types.TextContent]:
        """Handle getting issue template."""
        try:
            templates = self._get_qs_issue_templates()
            
            if issue_type not in templates:
                available = ", ".join(templates.keys())
                return [types.TextContent(
                    type="text",
                    text=f"Error: Unknown issue type '{issue_type}'. Available types: {available}"
                )]
            
            template = templates[issue_type]
            
            result = f"""
**QS Issue Template: {template['title']}**

**Description:** {template['description']}

**Typical Scenarios:**
{chr(10).join(f"• {scenario}" for scenario in template['typical_scenarios'])}

**Options Framework:**
{chr(10).join(f"• {option}" for option in template['options_framework'])}

**Competencies Demonstrated:**
{chr(10).join(f"• {comp}" for comp in template['competencies_demonstrated'])}

**Evidence to Collect:**
{chr(10).join(f"• {evidence}" for evidence in template['evidence_to_collect'])}

**Case Study Structure Suggestions:**
1. **Problem Statement:** Describe which scenario occurred and why it was significant
2. **Options Analysis:** Evaluate the options framework systematically
3. **Decision Making:** Explain your recommendation and rationale
4. **Implementation:** Detail how the solution was executed
5. **Outcomes:** Quantify the results and lessons learned
"""
            
            return [types.TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error getting issue template: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error getting issue template: {str(e)}"
            )]
    
    async def _handle_get_competency_guidance(self, competency: str, level: int) -> List[types.TextContent]:
        """Handle getting competency guidance."""
        try:
            mapping = self._get_qs_competency_mapping()
            core_competencies = mapping.get("core_competencies", {})
            
            if competency not in core_competencies:
                available = ", ".join(core_competencies.keys())
                return [types.TextContent(
                    type="text",
                    text=f"Error: Unknown competency '{competency}'. Available: {available}"
                )]
            
            comp_data = core_competencies[competency]
            level_key = f"level_{level}_requirements"
            
            if level_key not in comp_data:
                return [types.TextContent(
                    type="text",
                    text=f"Error: Level {level} guidance not available for {competency}"
                )]
            
            level_data = comp_data[level_key]
            
            result = f"""
**{competency.replace('_', ' ').title()} - Level {level} Guidance**

**Knowledge Descriptor:**
{level_data['knowledge_descriptor']}

**Example Evidence:**
{chr(10).join(f"• {evidence}" for evidence in level_data.get('example_evidence', []))}

**Typical Activities:**
{chr(10).join(f"• {activity}" for activity in level_data.get('typical_activities', []))}
"""
            
            if level == 3 and 'reasoned_advice_examples' in level_data:
                result += f"""

**Reasoned Advice Examples:**
{chr(10).join(f"• {example}" for example in level_data['reasoned_advice_examples'])}
"""
            
            return [types.TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error getting competency guidance: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error getting competency guidance: {str(e)}"
            )]
    
    async def _handle_map_issue_to_competencies(self, issue_type: str) -> List[types.TextContent]:
        """Handle mapping issues to competencies."""
        try:
            mapping = self._get_qs_competency_mapping()
            issue_matrix = mapping.get("issue_competency_matrix", {})
            
            # Map issue types to matrix keys
            issue_mapping = {
                "cost_control_and_budget_management": "cost_overrun_budget_recovery",
                "contract_administration_challenges": "variation_management",
                "procurement_and_tendering": "procurement_challenges",
                "measurement_and_valuation_disputes": "final_account_disputes"
            }
            
            matrix_key = issue_mapping.get(issue_type, issue_type)
            
            if matrix_key not in issue_matrix:
                available = ", ".join(issue_matrix.keys())
                return [types.TextContent(
                    type="text",
                    text=f"Error: No competency mapping found for '{issue_type}'. Available: {available}"
                )]
            
            competency_map = issue_matrix[matrix_key]
            
            result = f"""
**Competency Mapping for: {issue_type.replace('_', ' ').title()}**

**Primary Competencies (Main focus for case study):**
{chr(10).join(f"• {comp}" for comp in competency_map['primary_competencies'])}

**Secondary Competencies (Supporting evidence):**
{chr(10).join(f"• {comp}" for comp in competency_map['secondary_competencies'])}

**Recommendation:**
Focus your case study on demonstrating the primary competencies at the specified levels. Use the secondary competencies to provide supporting evidence and show the interconnected nature of professional practice.

**Writing Tip:**
Ensure your case study clearly demonstrates Level 3 competencies through examples of reasoned professional advice, strategic decision-making, and complex problem-solving.
"""
            
            return [types.TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error mapping issue to competencies: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error mapping issue to competencies: {str(e)}"
            )]
    
    async def _handle_get_level_3_advice_framework(self) -> List[types.TextContent]:
        """Handle getting Level 3 advice framework."""
        try:
            mapping = self._get_qs_competency_mapping()
            framework = mapping.get("level_3_advice_framework", {})
            
            result = f"""
**Level 3 Competency Demonstration Framework**

**Decision-Making Process:**
{chr(10).join(f"{step}" for step in framework.get('decision_making_process', []))}

**Evidence Requirements:**
{chr(10).join(f"• {req}" for req in framework.get('evidence_requirements', []))}

**Quality Indicators:**
{chr(10).join(f"• {indicator}" for indicator in framework.get('quality_indicators', []))}

**Level 3 Writing Structure (STAR Method):**
- **Situation:** Set the context and explain the complexity
- **Task:** Define your specific role and responsibilities  
- **Action:** Detail your analysis, options considered, and advice given
- **Result:** Quantify outcomes and demonstrate impact

**Key Level 3 Verbs to Use:**
- Advised, recommended, proposed, evaluated, assessed
- Led, directed, managed, coordinated, implemented
- Innovated, developed, designed, created, established
- Analyzed, investigated, researched, determined, concluded

**Quantification Examples:**
- Cost savings/increases (£ amounts or percentages)
- Time savings/extensions (days, weeks, months)
- Risk reduction/mitigation measures
- Process improvements and efficiency gains
- Stakeholder satisfaction metrics
"""
            
            return [types.TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error getting Level 3 framework: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error getting Level 3 framework: {str(e)}"
            )]
    
    # ENHANCED TOOL HANDLERS (keeping existing ones)
    async def _handle_analyze_user_competency_gaps(self, pathway: str, target_competencies: List[str] = None) -> List[types.TextContent]:
        """Handle analyzing user competency gaps."""
        try:
            # Read user data
            user_file = self.user_data_dir / "APC Summary of Experience.json"
            if not user_file.exists():
                return [types.TextContent(
                    type="text",
                    text="Error: User data file not found for competency analysis."
                )]
            
            data = await self._read_json_file_async(user_file)
            user_text = self._extract_text_from_json_document(data)
            
            # Analyze competencies
            analysis = self._analyze_user_experience_for_competencies(user_text)
            
            result = f"""
**Competency Gap Analysis for {pathway.replace('_', ' ').title()} Pathway**

**Suggested Competencies (Strong Evidence Found):**
{chr(10).join(f"• {comp.replace('_', ' ').title()}" for comp in analysis['suggested_competencies'])}

**Strength Indicators:**
"""
            for comp, details in analysis['strength_indicators'].items():
                result += f"\n**{comp.replace('_', ' ').title()}:** {details['strength']} ({details['keyword_matches']} keyword matches)"
            
            result += f"""

**Experience Gaps to Address:**
{chr(10).join(f"• {comp.replace('_', ' ').title()}" for comp in analysis['experience_gaps'])}

**Recommendations:**
1. Focus case study on competencies with strong evidence
2. Consider additional projects to address experience gaps
3. Ensure Level 3 demonstration in chosen competencies
"""
            
            return [types.TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error analyzing competency gaps: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error analyzing competency gaps: {str(e)}"
            )]
    
    async def _handle_generate_competency_evidence(self, competency: str, level: int, project_context: str) -> List[types.TextContent]:
        """Handle generating competency evidence."""
        try:
            templates = self._get_competency_templates()
            
            if competency not in templates:
                available = ", ".join(templates.keys())
                return [types.TextContent(
                    type="text",
                    text=f"Error: Unknown competency '{competency}'. Available: {available}"
                )]
            
            level_key = f"level_{level}"
            if level_key not in templates[competency]:
                return [types.TextContent(
                    type="text",
                    text=f"Error: Level {level} not available for {competency}"
                )]
            
            evidence_template = templates[competency][level_key]
            
            result = f"""
**Evidence Statement for {competency.replace('_', ' ').title()} - Level {level}**

**Project Context:** {project_context}

**Level {level} Requirements:**
{evidence_template}

**Suggested Evidence Structure:**
1. **Situation:** Describe the project challenge requiring {competency.replace('_', ' ')} expertise
2. **Task:** Explain your specific role and responsibilities
3. **Action:** Detail the {competency.replace('_', ' ')} activities you undertook
4. **Result:** Quantify the outcomes and impact of your actions

**Level {level} Demonstration Tips:**
"""
            
            if level == 3:
                result += """
- Show strategic thinking and complex decision-making
- Demonstrate provision of reasoned professional advice
- Include examples of leadership and innovation
- Quantify significant impacts and outcomes
"""
            elif level == 2:
                result += """
- Show practical application of knowledge
- Demonstrate competent delivery of tasks
- Include examples of problem-solving
- Show progression from Level 1 understanding
"""
            else:
                result += """
- Show understanding of principles and concepts
- Demonstrate awareness of relevant standards
- Include examples of learning and development
- Reference relevant CPD activities
"""
            
            return [types.TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error generating competency evidence: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error generating competency evidence: {str(e)}"
            )]
    
    async def _handle_validate_case_study_structure(self, case_study_text: str, pathway: str = "quantity_surveying") -> List[types.TextContent]:
        """Handle validating case study structure."""
        try:
            validation = self._validate_case_study_content(case_study_text)
            confidentiality_warnings = self._check_confidentiality_compliance(case_study_text)
            
            result = f"""
**Case Study Validation Report**

**Word Count Analysis:**
- Current: {validation['word_count']['current']} words
- Target: {validation['word_count']['target']} words
- Status: {validation['word_count']['status']}
- Usage: {validation['word_count']['percentage_used']}%

**Structure Check:**
"""
            for section, present in validation['structure_check'].items():
                status = "✓" if present else "✗"
                result += f"\n{status} {section.title()}: {'Present' if present else 'Missing'}"
            
            result += f"""

**Structure Score:** {validation['structure_score']:.1%}

**Reflection Quality Assessment:**
- Depth: {validation['reflection_quality']['depth_assessment']}
- Indicators found: {validation['reflection_quality']['reflection_indicators_found']}

**Overall Quality Score:** {validation['overall_score']}/1.0

**Improvement Suggestions:**
{chr(10).join(f"• {suggestion}" for suggestion in validation['improvement_suggestions'])}
"""
            
            if confidentiality_warnings:
                result += f"""

**⚠️ Confidentiality Warnings:**
{chr(10).join(f"• {warning}" for warning in confidentiality_warnings)}
"""
            
            return [types.TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error validating case study: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error validating case study: {str(e)}"
            )]
    
    async def _handle_enhance_reflection_content(self, basic_reflection: str, project_context: str) -> List[types.TextContent]:
        """Handle enhancing reflection content."""
        try:
            enhanced = self._enhance_reflection_section(basic_reflection, project_context)
            
            return [types.TextContent(type="text", text=enhanced)]
            
        except Exception as e:
            logger.error(f"Error enhancing reflection: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error enhancing reflection: {str(e)}"
            )]
    
    async def _handle_generate_options_analysis(self, issue_description: str, industry: str) -> List[types.TextContent]:
        """Handle generating options analysis."""
        try:
            analysis = self._generate_options_analysis(issue_description, industry)
            
            return [types.TextContent(type="text", text=analysis)]
            
        except Exception as e:
            logger.error(f"Error generating options analysis: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error generating options analysis: {str(e)}"
            )]
    
    async def _handle_check_confidentiality_compliance(self, content: str) -> List[types.TextContent]:
        """Handle checking confidentiality compliance."""
        try:
            warnings = self._check_confidentiality_compliance(content)
            
            if not warnings:
                result = "✅ No obvious confidentiality issues detected."
            else:
                result = f"⚠️ Potential confidentiality issues found:\n\n"
                result += "\n".join(f"• {warning}" for warning in warnings)
                result += "\n\n**Recommendations:**\n"
                result += "• Review highlighted areas and consider anonymization\n"
                result += "• Replace specific amounts with ranges (e.g., '£2.5M' → '£2-3M')\n"
                result += "• Use generic descriptions (e.g., 'Contractor A', 'Major UK Bank')\n"
                result += "• Remove personal names and contact details\n"
                result += "• Ensure client approval for any specific information"
            
            return [types.TextContent(type="text", text=result)]
            
        except Exception as e:
            logger.error(f"Error checking confidentiality: {str(e)}")
            return [types.TextContent(
                type="text",
                text=f"Error checking confidentiality: {str(e)}"
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
            
            # NEW QS-SPECIFIC TOOL HANDLERS
            elif name == "get_issue_template":
                issue_type = arguments.get("issue_type", "")
                return await self._handle_get_issue_template(issue_type)
            
            elif name == "get_competency_guidance":
                competency = arguments.get("competency", "")
                level = arguments.get("level", 3)
                return await self._handle_get_competency_guidance(competency, level)
            
            elif name == "map_issue_to_competencies":
                issue_type = arguments.get("issue_type", "")
                return await self._handle_map_issue_to_competencies(issue_type)
            
            elif name == "get_level_3_advice_framework":
                return await self._handle_get_level_3_advice_framework()
            
            # ENHANCED TOOL HANDLERS
            elif name == "analyze_user_competency_gaps":
                pathway = arguments.get("pathway", "quantity_surveying")
                target_competencies = arguments.get("target_competencies", [])
                return await self._handle_analyze_user_competency_gaps(pathway, target_competencies)
            
            elif name == "generate_competency_evidence":
                competency = arguments.get("competency", "")
                level = arguments.get("level", 3)
                project_context = arguments.get("project_context", "")
                return await self._handle_generate_competency_evidence(competency, level, project_context)
            
            elif name == "validate_case_study_structure":
                case_study_text = arguments.get("case_study_text", "")
                pathway = arguments.get("pathway", "quantity_surveying")
                return await self._handle_validate_case_study_structure(case_study_text, pathway)
            
            elif name == "enhance_reflection_content":
                basic_reflection = arguments.get("basic_reflection", "")
                project_context = arguments.get("project_context", "")
                return await self._handle_enhance_reflection_content(basic_reflection, project_context)
            
            elif name == "generate_options_analysis":
                issue_description = arguments.get("issue_description", "")
                industry = arguments.get("industry", "commercial")
                return await self._handle_generate_options_analysis(issue_description, industry)
            
            elif name == "check_confidentiality_compliance":
                content = arguments.get("content", "")
                return await self._handle_check_confidentiality_compliance(content)
            
            else:
                logger.warning(f"Unknown tool requested: {name}")
                return [types.TextContent(
                    type="text",
                    text=f"Unknown tool: {name}. Use list_tools to see available tools."
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