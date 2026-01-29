"""Skill Creator Agent for TARS.

Implements the "Moltbot" capability to generate new tools/skills dynamically.
"""
import os
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class SkillCreatorAgent:
    """Agent that creates new skills/tools for TARS."""
    
    def __init__(self, base_path: str = "skills"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        self.name = "skill_creator"
        self.description = "Creates new capabilities/skills for TARS by writing code and metadata."

    async def execute(self, args: Dict[str, Any]) -> str:
        """Execute skill creation.
        
        Args:
            args: {
                "skill_name": "name_of_skill",
                "instruction": "description of what the skill should do",
                "code_content": "optional python code provided by the LLM"
            }
        """
        skill_name = args.get("skill_name")
        instruction = args.get("instruction")
        code_content = args.get("code_content")
        
        if not skill_name or not instruction:
            return "Please provide both skill_name and instruction/description."
            
        # Sanitize name
        skill_name = skill_name.lower().replace(" ", "_")
        skill_dir = self.base_path / skill_name
        skill_dir.mkdir(exist_ok=True)
        
        # 1. Create SKILL.md
        skill_md_content = f"""---
name: {skill_name}
description: {instruction}
---
# {skill_name}

{instruction}

## Usage
Automatically generated skill.
"""
        with open(skill_dir / "SKILL.md", "w") as f:
            f.write(skill_md_content)
            
        # 2. Create tool.py (if provided, otherwise create a placeholder or use Internal Monologue to write it)
        # Note: In a full "Moltbot" loop, the LLM would write the code. 
        # Here we assume the calling LLM provides the code OR we generate a stub.
        
        if not code_content:
             # Basic template if no code provided
             code_content = f"""
def {skill_name}(args):
    \"\"\"{instruction}\"\"\"
    return f"Executed {skill_name} with {{args}}"
"""

        with open(skill_dir / "tool.py", "w") as f:
            f.write(code_content)
            
        return f"Skill '{skill_name}' created at {skill_dir}. Please restart TARS to load it (Dynamic loading V2 pending)."

