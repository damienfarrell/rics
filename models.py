# models.py - Data classes and models for APC Case Study Generator

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from pathlib import Path

# Enums
class ResourceCategory(Enum):
    USER_DATA = "user_data"
    EXAMPLE = "example"
    GUIDE = "guide"
    GENERAL = "general"

class SectionType(Enum):
    INTRODUCTION = "introduction"
    KEY_ISSUES = "key_issues"
    ACHIEVEMENTS = "achievements"
    REFLECTION = "reflection"
    ALL = "all"

class IssueType(Enum):
    COST_CONTROL = "cost_control_and_budget_management"
    CONTRACT_ADMIN = "contract_administration_challenges"
    PROCUREMENT = "procurement_and_tendering"
    MEASUREMENT = "measurement_and_valuation_disputes"
    CASH_FLOW = "programme_and_cash_flow"
    RISK = "risk_management"

class CompetencyLevel(Enum):
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3

# Data Classes
@dataclass
class ResourceInfo:
    """Information about a resource file."""
    path: Path
    relative_path: Path
    category: ResourceCategory
    name: str
    description: str

@dataclass
class ValidationResult:
    """Result of case study validation."""
    word_count: int
    target_word_count: int = 3000
    structure_checks: Dict[str, bool] = field(default_factory=dict)
    reflection_quality: str = "weak"
    reflection_indicators_found: int = 0
    suggestions: List[str] = field(default_factory=list)
    confidentiality_warnings: List[str] = field(default_factory=list)
    
    @property
    def is_within_limit(self) -> bool:
        return self.word_count <= self.target_word_count
    
    @property
    def percentage_used(self) -> float:
        return round((self.word_count / self.target_word_count) * 100, 1)
    
    @property
    def structure_score(self) -> float:
        if not self.structure_checks:
            return 0.0
        return sum(self.structure_checks.values()) / len(self.structure_checks)
    
    @property
    def overall_score(self) -> float:
        word_score = 1.0 if self.is_within_limit else max(0.5, self.target_word_count / self.word_count)
        structure_score = self.structure_score
        reflection_score = {"strong": 1.0, "moderate": 0.7, "weak": 0.4}.get(self.reflection_quality, 0.4)
        return round((word_score * 0.3 + structure_score * 0.4 + reflection_score * 0.3), 2)

@dataclass
class CompetencyAnalysis:
    """Analysis of user's competency evidence."""
    suggested_competencies: List[str] = field(default_factory=list)
    strength_indicators: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    experience_gaps: List[str] = field(default_factory=list)
    suitable_projects: List[str] = field(default_factory=list)

@dataclass
class CompetencyEvidence:
    """Evidence for demonstrating a competency."""
    competency: str
    level: CompetencyLevel
    strength: str  # "strong", "moderate", "weak"
    level_indicators_count: int
    evidence_count: int
    suggestions: List[str] = field(default_factory=list)
    
    @property
    def level_demonstration(self) -> str:
        if self.level == CompetencyLevel.LEVEL_3:
            return "clearly L3" if self.level_indicators_count >= 5 else "needs enhancement"
        return f"meets L{self.level.value} requirements"

@dataclass
class IssueTemplate:
    """Template for a QS issue/challenge."""
    issue_type: IssueType
    title: str
    description: str
    typical_scenarios: List[str]
    options_framework: List[str]
    competencies_demonstrated: List[str]
    evidence_to_collect: List[str]

@dataclass
class OptionsAnalysis:
    """Options analysis for an issue."""
    issue_description: str
    industry: str
    options: List[Dict[str, Any]]
    evaluation_criteria: List[str]
    recommendation: Optional[str] = None

@dataclass
class QSMetrics:
    """Realistic QS metrics for case studies."""
    project_type: str
    project_value: float
    prelims_percentage: float
    contingency_percentage: float
    professional_fees_percentage: float
    variation_range: tuple  # (min, max)
    final_account_variance: float
    payment_terms: str
    defects_period: str

@dataclass
class ToolSchema:
    """Schema for a tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler_name: str  # Name of the handler method