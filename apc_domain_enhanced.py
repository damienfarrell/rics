# apc_domain_enhanced.py - Enhanced domain service with external template loading

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from apc_domain import APCDomainService

logger = logging.getLogger(__name__)

class APCDomainServiceEnhanced(APCDomainService):
    """Enhanced domain service that loads templates from external files."""
    
    def __init__(self, config_path: Path = Path("config.yaml"), templates_dir: Path = Path("templates")):
        self.templates_dir = templates_dir
        super().__init__(config_path)
    
    def _load_templates(self) -> Dict[str, Any]:
        """Load templates from external JSON files."""
        templates = {}
        
        # Load each template file
        template_files = {
            "issue_templates": "issue_templates.json",
            "competency_templates": "competency_templates.json",
            "case_study_outline": "case_study_outline.json",
            "section_requirements": "section_requirements.json"
        }
        
        for template_key, filename in template_files.items():
            file_path = self.templates_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        templates[template_key] = json.load(f)
                    logger.info(f"Loaded template: {filename}")
                except Exception as e:
                    logger.error(f"Error loading template {filename}: {e}")
                    # Fall back to default templates
                    templates[template_key] = self._get_default_template(template_key)
            else:
                # Use default if file doesn't exist
                templates[template_key] = self._get_default_template(template_key)
        
        return templates
    
    def _get_default_template(self, template_key: str) -> Any:
        """Get default template if external file not found."""
        defaults = {
            "issue_templates": super()._get_issue_templates(),
            "competency_templates": super()._get_competency_templates(),
            "case_study_outline": super()._get_case_study_outline_template(),
            "section_requirements": super()._get_section_requirements()
        }
        return defaults.get(template_key, {})
    
    def reload_templates(self) -> None:
        """Reload templates from disk (useful for development)."""
        self.templates = self._load_templates()
        logger.info("Templates reloaded")
    
    def save_template(self, template_key: str, content: Dict[str, Any]) -> bool:
        """Save a template back to disk."""
        if template_key not in ["issue_templates", "competency_templates", "case_study_outline", "section_requirements"]:
            logger.error(f"Unknown template key: {template_key}")
            return False
        
        file_path = self.templates_dir / f"{template_key}.json"
        try:
            # Ensure templates directory exists
            self.templates_dir.mkdir(parents=True, exist_ok=True)
            
            # Save with pretty formatting
            with open(file_path, 'w') as f:
                json.dump(content, f, indent=2)
            
            # Update in-memory templates
            self.templates[template_key] = content
            logger.info(f"Saved template: {template_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving template {template_key}: {e}")
            return False
    
    def get_template_metadata(self) -> Dict[str, Any]:
        """Get metadata about loaded templates."""
        metadata = {}
        for key, template in self.templates.items():
            if isinstance(template, dict):
                metadata[key] = {
                    "count": len(template),
                    "keys": list(template.keys())[:5]  # First 5 keys
                }
            elif isinstance(template, str):
                metadata[key] = {
                    "type": "string",
                    "length": len(template)
                }
            else:
                metadata[key] = {
                    "type": type(template).__name__
                }
        return metadata


# Example usage:
if __name__ == "__main__":
    # Initialize enhanced domain service
    domain = APCDomainServiceEnhanced()
    
    # Get template metadata
    print("Loaded templates:", domain.get_template_metadata())
    
    # Use a template
    issue_template = domain.get_issue_template("cost_control_and_budget_management")
    if issue_template:
        print(f"\nIssue Template: {issue_template.title}")
        print(f"Scenarios: {len(issue_template.typical_scenarios)}")
    
    # Modify and save a template
    new_scenario = "Brexit-related material shortages"
    if "issue_templates" in domain.templates:
        templates = domain.templates["issue_templates"]
        if "cost_control_and_budget_management" in templates:
            templates["cost_control_and_budget_management"]["typical_scenarios"].append(new_scenario)
            domain.save_template("issue_templates", templates)
            print(f"\nAdded new scenario: {new_scenario}")