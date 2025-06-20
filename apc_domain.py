# apc_domain.py - APC-specific domain logic and services

import json
import random
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import yaml

from models import (
    IssueType, CompetencyLevel, SectionType,
    ValidationResult, CompetencyAnalysis, CompetencyEvidence,
    IssueTemplate, OptionsAnalysis, QSMetrics
)
from utils import (
    count_words, check_section_exists, find_patterns,
    extract_percentages, extract_amounts, assess_depth,
    format_bullet_list, render_template
)

logger = logging.getLogger(__name__)

class APCDomainService:
    """Service handling all APC-specific domain logic."""
    
    def __init__(self, config_path: Path = Path("config.yaml")):
        self.config = self._load_config(config_path)
        self.templates = self._load_templates()
        self.competency_mappings = self._load_competency_mappings()
    
    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
    
    def _load_templates(self) -> Dict[str, Any]:
        """Load templates from files or return defaults."""
        # In production, load from JSON files
        # For now, return essential templates
        return {
            "case_study_outline": self._get_case_study_outline_template(),
            "section_requirements": self._get_section_requirements(),
            "issue_templates": self._get_issue_templates(),
            "competency_templates": self._get_competency_templates()
        }
    
    def _load_competency_mappings(self) -> Dict[str, Any]:
        """Load competency mappings."""
        return {
            "core_competencies": self._get_core_competencies(),
            "issue_competency_matrix": self._get_issue_competency_matrix(),
            "level_3_framework": self._get_level_3_framework()
        }
    
    # Validation methods
    def validate_case_study(self, content: str) -> ValidationResult:
        """Validate case study against RICS requirements."""
        result = ValidationResult(word_count=count_words(content))
        
        # Check structure
        required_sections = self.config['validation']['required_sections']
        for section in required_sections:
            result.structure_checks[section] = check_section_exists(content, section)
        
        # Assess reflection quality
        indicators = self.config['validation']['reflection_indicators']
        count, depth = assess_depth(content, indicators)
        result.reflection_indicators_found = count
        result.reflection_quality = depth
        
        # Generate suggestions
        result.suggestions = self._generate_improvement_suggestions(result)
        
        # Check confidentiality
        result.confidentiality_warnings = self.check_confidentiality(content)
        
        return result
    
    def check_confidentiality(self, content: str) -> List[str]:
        """Check for potential confidentiality breaches."""
        warnings = []
        patterns = self.config.get('confidentiality_patterns', {})
        
        matches = find_patterns(content, patterns)
        for pattern_name, found in matches.items():
            warnings.append(f"Potential {pattern_name.replace('_', ' ')}: {len(found)} instances found")
        
        return warnings
    
    def _generate_improvement_suggestions(self, result: ValidationResult) -> List[str]:
        """Generate improvement suggestions based on validation result."""
        suggestions = []
        
        if not result.is_within_limit:
            over = result.word_count - result.target_word_count
            suggestions.append(f"Reduce word count by {over} words to meet the {result.target_word_count} word limit")
        
        missing_sections = [s for s, present in result.structure_checks.items() if not present]
        if missing_sections:
            suggestions.append(f"Add missing sections: {', '.join(missing_sections)}")
        
        if result.reflection_quality == "weak":
            suggestions.append("Strengthen reflection with more specific examples of learning and development")
        elif result.reflection_quality == "moderate":
            suggestions.append("Deepen reflection with more analysis of professional growth")
        
        return suggestions
    
    # Competency analysis
    def analyze_user_competencies(self, user_experience: str) -> CompetencyAnalysis:
        """Analyze user's experience for competency evidence."""
        analysis = CompetencyAnalysis()
        
        competency_keywords = {
            "commercial_management": ["cost", "commercial", "budget", "CVR", "value engineering"],
            "contract_practice": ["contract", "NEC", "JCT", "variation", "change", "dispute"],
            "project_financial_control": ["forecast", "budget", "financial", "reporting", "variance"],
            "procurement_and_tendering": ["tender", "procurement", "contractor", "evaluation"],
            "quantification_and_costing": ["measurement", "quantities", "pricing", "rates", "valuation"]
        }
        
        user_text_lower = user_experience.lower()
        
        for competency, keywords in competency_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in user_text_lower)
            
            if matches >= 3:
                analysis.suggested_competencies.append(competency)
                strength = "strong" if matches >= 5 else "moderate"
                analysis.strength_indicators[competency] = {
                    "strength": strength,
                    "keyword_matches": matches,
                    "keywords_found": [kw for kw in keywords if kw in user_text_lower]
                }
            else:
                analysis.experience_gaps.append(competency)
        
        return analysis
    
    def assess_competency_evidence(self, content: str, competency: str, level: int) -> CompetencyEvidence:
        """Assess how well content demonstrates a specific competency."""
        level_indicators = self.config['competency_levels']['level_3_indicators']
        content_lower = content.lower()
        
        indicator_count = sum(1 for indicator in level_indicators if indicator in content_lower)
        
        # Count quantified evidence
        percentages = extract_percentages(content)
        amounts = extract_amounts(content)
        evidence_count = len(percentages) + len(amounts)
        
        evidence = CompetencyEvidence(
            competency=competency,
            level=CompetencyLevel(level),
            strength="strong" if indicator_count >= 5 and evidence_count >= 3 else
                     "moderate" if indicator_count >= 3 or evidence_count >= 2 else "weak",
            level_indicators_count=indicator_count,
            evidence_count=evidence_count
        )
        
        # Generate suggestions
        if indicator_count < 5:
            evidence.suggestions.append("Include more examples of strategic advice and complex decision-making")
        if evidence_count < 3:
            evidence.suggestions.append("Add quantified outcomes (cost savings, time reductions, etc.)")
        
        return evidence
    
    # Issue templates
    def get_issue_template(self, issue_type: str) -> Optional[IssueTemplate]:
        """Get template for a specific issue type."""
        templates = self.templates.get("issue_templates", {})
        if issue_type in templates:
            data = templates[issue_type]
            return IssueTemplate(
                issue_type=IssueType(issue_type),
                title=data['title'],
                description=data['description'],
                typical_scenarios=data['typical_scenarios'],
                options_framework=data['options_framework'],
                competencies_demonstrated=data['competencies_demonstrated'],
                evidence_to_collect=data['evidence_to_collect']
            )
        return None
    
    def generate_options_analysis(self, issue_description: str, industry: str) -> OptionsAnalysis:
        """Generate options analysis for an issue."""
        factors = self.config['industry_factors'].get(industry, 
                                                      self.config['industry_factors']['commercial'])
        
        options = [
            {
                "title": "Conservative Approach",
                "cost_impact": f"{factors['typical_costs']} (lower end)",
                "programme_impact": f"Standard timeframe - {factors['timeframes']}",
                "risk_level": "Low",
                "benefits": "Minimal disruption, established processes"
            },
            {
                "title": "Innovative Solution",
                "cost_impact": "Premium of 15-25% for innovation",
                "programme_impact": "Potential 20-30% time saving",
                "risk_level": "Medium",
                "benefits": "Efficiency gains, future replication potential"
            },
            {
                "title": "Hybrid Approach",
                "cost_impact": "Balanced cost profile",
                "programme_impact": "Optimized timeline",
                "risk_level": "Medium-Low",
                "benefits": "Best of both approaches"
            }
        ]
        
        return OptionsAnalysis(
            issue_description=issue_description,
            industry=industry,
            options=options,
            evaluation_criteria=[
                "Cost effectiveness",
                "Programme certainty",
                "Quality outcomes",
                "Risk profile",
                "Stakeholder impact"
            ]
        )
    
    def generate_qs_metrics(self, project_type: str, project_value: float) -> QSMetrics:
        """Generate realistic QS metrics."""
        return QSMetrics(
            project_type=project_type,
            project_value=project_value,
            prelims_percentage=random.uniform(12, 18),
            contingency_percentage=random.uniform(3, 5),
            professional_fees_percentage=random.uniform(8, 12),
            variation_range=(random.uniform(-5, 0), random.uniform(5, 15)),
            final_account_variance=random.uniform(-2, 3),
            payment_terms="Monthly valuations, 5% retention",
            defects_period="12 months"
        )
    
    # Template methods (simplified versions)
    def _get_case_study_outline_template(self) -> str:
        """Get case study outline template."""
        return """Case Study Outline for: {project_name}

1. INTRODUCTION (approx. 600 words)
   - Project overview (scope, value, timeline)
   - My roles and responsibilities
   - Key stakeholders
   - Procurement details

2. MY APPROACH (approx. 1,500 words)
   - Key issues/challenges faced
   - Options analysis and evaluation
   - Implementation approach

3. MY ACHIEVEMENTS (approx. 600 words)
   - Outcomes delivered
   - Examples of reasoned advice (Level 3)
   - Value added to the project

4. CONCLUSION (approx. 300 words)
   - Reflection and self-analysis
   - Learning points
   - Professional development

APPENDICES:
   - Competencies demonstrated
   - Supporting documentation"""
    
    def _get_section_requirements(self) -> Dict[str, str]:
        """Get section requirements."""
        return {
            "introduction": "Clear project overview with costs, roles, stakeholders",
            "key_issues": "Significant challenges demonstrating problem-solving",
            "achievements": "Specific contributions with quantified impact",
            "reflection": "Honest self-assessment and learning points"
        }
    
    def _get_issue_templates(self) -> Dict[str, Any]:
        """Get issue templates."""
        return {
            "cost_control_and_budget_management": {
                "title": "Cost Overrun and Budget Recovery",
                "description": "Project experiencing significant cost overruns",
                "typical_scenarios": [
                    "Unforeseen ground conditions",
                    "Material price escalation",
                    "Scope creep"
                ],
                "options_framework": [
                    "Value engineering",
                    "Contract renegotiation",
                    "Additional funding"
                ],
                "competencies_demonstrated": [
                    "Commercial management (L3)",
                    "Project financial control (L3)"
                ],
                "evidence_to_collect": [
                    "Cost reports",
                    "Value engineering proposals",
                    "Client correspondence"
                ]
            }
        }
    
    def _get_competency_templates(self) -> Dict[str, Dict[str, str]]:
        """Get competency templates."""
        return {
            "commercial_management": {
                "level_1": "Understanding of cost components and CVR principles",
                "level_2": "Experience in cost forecasting and change management",
                "level_3": "Strategic cost advice and complex commercial decisions"
            }
        }
    
    def _get_core_competencies(self) -> Dict[str, Any]:
        """Get core competencies structure."""
        return {
            "commercial_management_of_construction": {
                "level_3_requirements": {
                    "knowledge_descriptor": "Providing reasoned advice on commercial strategy",
                    "reasoned_advice_examples": [
                        "Recommended target cost contract saving £200k risk exposure",
                        "Advised phased handover accelerating revenue by 6 months"
                    ]
                }
            }
        }
    
    def _get_issue_competency_matrix(self) -> Dict[str, Any]:
        """Get issue to competency mapping."""
        return {
            "cost_overrun_budget_recovery": {
                "primary_competencies": [
                    "Commercial management (L3)",
                    "Project financial control (L3)"
                ],
                "secondary_competencies": [
                    "Communication and negotiation (L2)"
                ]
            }
        }
    
    def _get_level_3_framework(self) -> Dict[str, Any]:
        """Get Level 3 competency framework."""
        return {
            "decision_making_process": [
                "1. Problem identification",
                "2. Stakeholder assessment",
                "3. Option evaluation",
                "4. Risk assessment",
                "5. Recommendation",
                "6. Implementation"
            ],
            "evidence_requirements": [
                "Clear advice statement",
                "Analysis justification",
                "Implementation evidence",
                "Outcome measurement"
            ]
        }