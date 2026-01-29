"""Phase management system for autonomous coding tasks."""
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# Phase definitions - defines the workflow and constraints for each phase
PHASES = {
    'DISCOVER': {
        'allowed_actions': ['read_file', 'run_command', 'list_directory', 'list_files', 'complete_phase'],
        'forbidden_actions': ['edit_file', 'create_file', 'delete_file'],
        'system_prompt_template': """You are in DISCOVERY phase. Your goal is to UNDERSTAND the project before making any changes.

ALLOWED ACTIONS (respond with JSON):
- {{"action": "read_file", "file_path": "path/to/file"}} - Read a file to understand its contents
- {{"action": "list_files", "directory": "path/to/dir"}} - List files in a directory
- {{"action": "run_command", "command": "ls -la"}} - Run read-only commands

FORBIDDEN ACTIONS:
- edit_file, create_file, delete_file (no modifications in this phase)

Your task: Map the project structure, understand existing code patterns, identify key files.

When you have a complete understanding, respond with:
{{"action": "complete_phase", "summary": "Brief overview of what you discovered"}}""",
        'max_iterations': 10,
        'output_artifact': '.tars_phases/discovery.md',
        'auto_transition': False,  # Requires explicit completion
        'next_phase': 'PLAN'
    },
    'PLAN': {
        'allowed_actions': ['read_file', 'list_files', 'ask_user_question', 'complete_phase'],
        'forbidden_actions': ['edit_file', 'create_file', 'run_command', 'delete_file'],
        'system_prompt_template': """You are in PLANNING phase. Generate a detailed step-by-step plan BEFORE coding.

ALLOWED ACTIONS (respond with JSON):
- {{"action": "read_file", "file_path": "path/to/file"}} - Review code that needs modification
- {{"action": "list_files", "directory": "path"}} - Explore project structure
- {{"action": "ask_user_question", "question": "...", "options": ["A", "B"]}} - Clarify requirements

FORBIDDEN ACTIONS:
- edit_file, create_file, run_command (NO execution, only planning)

Your task: Create a comprehensive plan with:
1. Architecture decisions
2. Files to create/modify (in order)
3. Testing strategy
4. Potential risks

When plan is complete, respond with:
{{"action": "complete_phase", "summary": "### IMPLEMENTATION PLAN\\n\\n[Your detailed plan here]"}}""",
        'max_iterations': 5,
        'output_artifact': '.tars_phases/PLAN.md',
        'auto_transition': False,  # User must approve plan
        'next_phase': 'EXECUTE'
    },
    'EXECUTE': {
        'allowed_actions': ['edit_file', 'create_file', 'run_command', 'read_file', 'list_files', 'complete_phase', 'complete'],
        'forbidden_actions': [],
        'system_prompt_template': """You are in EXECUTION phase. Follow the PLAN exactly. Commit after each logical step.

ALLOWED ACTIONS (respond with JSON):
- {{"action": "edit_file", "file_path": "path", "changes": "description of changes"}}
- {{"action": "read_file", "file_path": "path"}} - Check file contents
- {{"action": "run_command", "command": "npm install"}} - Run commands
- {{"action": "list_files", "directory": "path"}} - List directory contents
- {{"action": "complete"}} - Task finished

EXECUTION RULES:
1. Follow the plan from .tars_phases/PLAN.md
2. Work incrementally - one logical change at a time
3. Git commits happen automatically after successful edits
4. If you encounter errors, read relevant files and fix them

When all plan items are complete, respond with:
{{"action": "complete_phase", "summary": "Completed all implementation tasks"}}""",
        'max_iterations': 30,
        'output_artifact': None,
        'auto_transition': True,
        'git_policy': 'commit_per_step',
        'next_phase': 'VERIFY'
    },
    'VERIFY': {
        'allowed_actions': ['run_command', 'read_file', 'edit_file'],
        'forbidden_actions': [],
        'system_prompt_template': """You are in VERIFICATION phase. Run tests and fix any failures.

ALLOWED ACTIONS:
- run_command: Run test commands
- read_file: Read test output and error logs
- edit_file: Fix bugs found during testing

VERIFICATION TASKS:
1. Tests will run automatically
2. If tests fail, read the error output
3. Fix the issues by editing code
4. Tests will re-run automatically

When all tests pass, respond with:
{{"action": "complete_phase", "summary": "All tests passing"}}""",
        'max_iterations': 10,
        'output_artifact': '.tars_phases/test_results.md',
        'auto_transition': True,
        'auto_test': True,
        'next_phase': 'PUBLISH'
    },
    'PUBLISH': {
        'allowed_actions': ['git_push', 'run_command', 'complete_phase'],
        'forbidden_actions': ['edit_file', 'create_file'],
        'system_prompt_template': """You are in PUBLISH phase. Push code to GitHub and generate summary.

ALLOWED ACTIONS:
- git_push: Push commits to remote repository
- run_command: Generate build artifacts if needed

FORBIDDEN ACTIONS:
- edit_file, create_file (no code changes in this phase)

PUBLISH TASKS:
1. Push all commits to GitHub
2. Generate deployment summary
3. Document what was built

When complete, respond with:
{{"action": "complete_phase", "summary": "Published to GitHub. [Brief summary]"}}""",
        'max_iterations': 3,
        'output_artifact': '.tars_phases/deployment.md',
        'auto_transition': True,
        'next_phase': 'COMPLETE'
    }
}


class PhaseManager:
    """Manages phase transitions and validates actions for autonomous coding."""
    
    def __init__(self, project_path: str):
        """Initialize phase manager.
        
        Args:
            project_path: Root directory of the project
        """
        self.project_path = Path(project_path)
        self.phases_dir = self.project_path / '.tars_phases'
        
        # Create phases directory if it doesn't exist
        self.phases_dir.mkdir(exist_ok=True)
        
        logger.info(f"PhaseManager initialized for {project_path}")
    
    def validate_action(self, phase: str, action: str) -> bool:
        """Check if an action is allowed in the current phase.
        
        Args:
            phase: Current phase name (DISCOVER, PLAN, EXECUTE, etc.)
            action: Action to validate
            
        Returns:
            True if action is allowed, False otherwise
        """
        if phase not in PHASES:
            logger.error(f"Unknown phase: {phase}")
            return False
        
        phase_config = PHASES[phase]
        
        # Check forbidden actions first
        if action in phase_config.get('forbidden_actions', []):
            logger.warning(f"Action '{action}' is forbidden in {phase} phase")
            return False
        
        # If allowed_actions is specified, check if action is in it
        allowed = phase_config.get('allowed_actions', [])
        if allowed and action not in allowed:
            logger.warning(f"Action '{action}' not in allowed list for {phase} phase")
            return False
        
        return True
    
    def get_phase_prompt(
        self,
        phase: str,
        context: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> str:
        """Generate phase-specific system prompt.
        
        Args:
            phase: Current phase name
            context: Task context (goal, iteration, errors, etc.)
            project_context: Project-specific context (rules, type, owner profile)
            
        Returns:
            Complete system prompt for Claude
        """
        if phase not in PHASES:
            raise ValueError(f"Unknown phase: {phase}")
        
        phase_config = PHASES[phase]
        base_prompt = phase_config['system_prompt_template']
        
        # Build comprehensive prompt
        prompt_parts = [
            f"=== PHASE: {phase} ===",
            base_prompt,
            "",
            f"=== PROJECT GOAL ===",
            f"{context.get('goal', 'No goal specified')}",
            "",
            f"=== PROJECT CONTEXT ===",
            f"Path: {context.get('project_path')}",
            f"Type: {project_context.get('project_type', 'unknown')}",
            ""
        ]
        
        # Add project rules if available
        if project_context.get('rules'):
            prompt_parts.extend([
                "=== PROJECT RULES (.tarsrules) ===",
                project_context['rules'],
                ""
            ])
        
        # Add owner preferences
        if project_context.get('owner_profile'):
            prompt_parts.extend([
                "=== OWNER PREFERENCES ===",
                project_context['owner_profile'][:500],  # Truncate for token management
                ""
            ])
        
        # Add phase-specific artifacts
        if phase != 'DISCOVER':
            # Load previous phase artifacts
            artifacts = self.load_phase_artifacts()
            if artifacts.get('discovery'):
                prompt_parts.extend([
                    "=== DISCOVERY SUMMARY ===",
                    artifacts['discovery'][:1000],
                    ""
                ])
            
            if phase not in ['DISCOVER', 'PLAN'] and artifacts.get('plan'):
                prompt_parts.extend([
                    "=== APPROVED PLAN ===",
                    artifacts['plan'],
                    ""
                ])
        
        # Add iteration context
        prompt_parts.extend([
            f"=== CURRENT PROGRESS ===",
            f"Iteration: {context.get('iteration', 0)}/{phase_config['max_iterations']}",
            f"Recent actions: {context.get('completed_actions', [])[-5:]}",
            f"Recent errors: {context.get('errors', [])[-3:]}",
            ""
        ])
        
        # Add action format reminder
        prompt_parts.extend([
            "=== RESPONSE FORMAT ===",
            "Respond with valid JSON:",
            '{{"action": "action_name", "file_path": "path/to/file", "changes": "description", "reason": "why"}}',
            "",
            "Available actions for this phase:",
            f"- {', '.join(phase_config['allowed_actions'])}",
            ""
        ])
        
        return "\n".join(prompt_parts)
    
    def get_next_phase(self, current_phase: str) -> str:
        """Get the next phase in the workflow.
        
        Args:
            current_phase: Current phase name
            
        Returns:
            Next phase name, or 'COMPLETE' if workflow is done
        """
        if current_phase not in PHASES:
            return 'COMPLETE'
        
        return PHASES[current_phase].get('next_phase', 'COMPLETE')
    
    def save_phase_artifact(self, phase: str, content: str) -> bool:
        """Save phase output artifact.
        
        Args:
            phase: Phase name
            content: Artifact content
            
        Returns:
            True if saved successfully
        """
        if phase not in PHASES:
            logger.error(f"Unknown phase: {phase}")
            return False
        
        artifact_path = PHASES[phase].get('output_artifact')
        if not artifact_path:
            logger.info(f"Phase {phase} has no output artifact configured")
            return True
        
        try:
            full_path = self.project_path / artifact_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Add metadata header
            artifact_content = f"""# {phase} Phase Output
Generated: {datetime.now().isoformat()}

{content}
"""
            
            full_path.write_text(artifact_content)
            logger.info(f"Saved {phase} artifact to {full_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving phase artifact: {e}")
            return False
    
    def load_phase_artifacts(self) -> Dict[str, str]:
        """Load all phase artifacts from disk.
        
        Returns:
            Dictionary mapping phase names to their artifact content
        """
        artifacts = {}
        
        for phase, config in PHASES.items():
            artifact_path = config.get('output_artifact')
            if not artifact_path:
                continue
            
            full_path = self.project_path / artifact_path
            if full_path.exists():
                try:
                    artifacts[phase.lower()] = full_path.read_text()
                    logger.debug(f"Loaded {phase} artifact from {full_path}")
                except Exception as e:
                    logger.warning(f"Could not load {phase} artifact: {e}")
        
        return artifacts
    
    def get_phase_config(self, phase: str) -> Dict[str, Any]:
        """Get configuration for a specific phase.
        
        Args:
            phase: Phase name
            
        Returns:
            Phase configuration dictionary
        """
        return PHASES.get(phase, {})
    
    def should_auto_transition(self, phase: str) -> bool:
        """Check if phase should automatically transition to next.
        
        Args:
            phase: Phase name
            
        Returns:
            True if auto-transition enabled
        """
        return PHASES.get(phase, {}).get('auto_transition', False)
    
    def requires_user_approval(self, phase: str) -> bool:
        """Check if phase requires user approval before transitioning.
        
        Args:
            phase: Phase name
            
        Returns:
            True if user approval required
        """
        return not self.should_auto_transition(phase)
