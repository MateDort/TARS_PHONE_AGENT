"""Self-Updater - Safe self-modification with test verification.

Enables TARS to update its own code safely by:
1. Making code changes
2. Running the test suite
3. Committing if tests pass
4. Rolling back if tests fail
5. Requesting restart via supervisor
"""
import logging
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime

from core.config import Config

logger = logging.getLogger(__name__)


@dataclass
class UpdateResult:
    """Result of a self-update operation."""
    success: bool
    changes_made: List[str]
    tests_passed: bool
    commit_hash: Optional[str]
    error_message: Optional[str]
    rollback_needed: bool


class SelfUpdater:
    """Safe self-modification for TARS.
    
    This class allows TARS to update its own code while ensuring:
    - Changes are tested before being applied
    - Backups are created
    - Rollback is possible if tests fail
    - Restart is coordinated with supervisor
    """
    
    def __init__(self, project_path: Optional[str] = None):
        """Initialize self-updater.
        
        Args:
            project_path: Path to TARS project (defaults to TARS_ROOT)
        """
        self.project_path = Path(project_path or Config.TARS_ROOT)
        self.backup_branch = None
        self.original_commit = None
    
    def _run_git(self, *args, check: bool = True) -> Tuple[bool, str]:
        """Run a git command.
        
        Args:
            *args: Git command arguments
            check: Whether to raise on failure
            
        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                if check:
                    logger.error(f"Git command failed: {result.stderr}")
                return False, result.stderr
            
            return True, result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            return False, "Git command timed out"
        except Exception as e:
            return False, str(e)
    
    async def create_backup(self) -> bool:
        """Create a backup before making changes.
        
        Creates a backup branch with current state.
        
        Returns:
            True if backup was created successfully
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_branch = f"tars-update-backup-{timestamp}"
        
        # Get current commit hash
        success, commit = self._run_git("rev-parse", "HEAD")
        if success:
            self.original_commit = commit[:8]
        
        # Create backup branch
        success, output = self._run_git("branch", self.backup_branch)
        if success:
            logger.info(f"Created backup branch: {self.backup_branch}")
            return True
        else:
            logger.error(f"Failed to create backup: {output}")
            return False
    
    async def run_tests(self, test_command: Optional[str] = None) -> Tuple[bool, str]:
        """Run the test suite.
        
        Args:
            test_command: Custom test command (optional)
            
        Returns:
            Tuple of (all_passed, output_summary)
        """
        # Default test command based on project
        if test_command is None:
            # Check for pytest
            if (self.project_path / "pytest.ini").exists() or \
               (self.project_path / "tests").exists():
                test_command = "python -m pytest tests/ -v --tb=short"
            # Check for basic Python import test
            else:
                test_command = "python -c 'import main_tars; print(\"Import OK\")'"
        
        logger.info(f"Running tests: {test_command}")
        
        try:
            result = subprocess.run(
                test_command,
                shell=True,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout for tests
            )
            
            output = result.stdout + result.stderr
            
            if result.returncode == 0:
                logger.info("Tests passed!")
                return True, output[-500:]  # Last 500 chars
            else:
                logger.error(f"Tests failed with code {result.returncode}")
                return False, output[-500:]
                
        except subprocess.TimeoutExpired:
            return False, "Tests timed out after 2 minutes"
        except Exception as e:
            return False, f"Test error: {str(e)}"
    
    async def commit_changes(self, message: str) -> Optional[str]:
        """Commit current changes.
        
        Args:
            message: Commit message
            
        Returns:
            Commit hash if successful, None if failed
        """
        # Stage all changes
        success, _ = self._run_git("add", "-A")
        if not success:
            return None
        
        # Check if there are changes to commit
        success, status = self._run_git("status", "--porcelain")
        if not status.strip():
            logger.info("No changes to commit")
            return self.original_commit
        
        # Commit
        full_message = f"[TARS Self-Update] {message}"
        success, output = self._run_git("commit", "-m", full_message)
        
        if success:
            # Get new commit hash
            success, commit = self._run_git("rev-parse", "HEAD")
            if success:
                logger.info(f"Committed: {commit[:8]}")
                return commit[:8]
        
        return None
    
    async def rollback(self) -> bool:
        """Rollback to the backup state.
        
        Returns:
            True if rollback was successful
        """
        if not self.original_commit:
            logger.error("No original commit to rollback to")
            return False
        
        # Reset to original commit
        success, output = self._run_git("reset", "--hard", self.original_commit)
        
        if success:
            logger.info(f"Rolled back to {self.original_commit}")
            return True
        else:
            logger.error(f"Rollback failed: {output}")
            return False
    
    async def request_restart(self):
        """Request a graceful restart via the supervisor."""
        restart_flag = self.project_path / ".tars_restart"
        
        try:
            restart_flag.touch()
            logger.info("Restart requested via .tars_restart flag")
        except Exception as e:
            logger.error(f"Failed to request restart: {e}")
    
    async def push_changes(self, force: bool = False) -> bool:
        """Push changes to remote.
        
        Args:
            force: Whether to force push (use with caution!)
            
        Returns:
            True if push was successful
        """
        branch = Config.TARS_GITHUB_BRANCH
        
        if force:
            success, output = self._run_git("push", "-f", "origin", branch)
        else:
            success, output = self._run_git("push", "origin", branch)
        
        if success:
            logger.info(f"Pushed to origin/{branch}")
            return True
        else:
            logger.error(f"Push failed: {output}")
            return False
    
    async def safe_update(
        self,
        change_description: str,
        code_changes: Dict[str, str],
        run_tests: bool = True,
        auto_push: bool = False
    ) -> UpdateResult:
        """Safely update TARS code.
        
        The main entry point for self-modification.
        
        Args:
            change_description: What is being changed
            code_changes: Dict of filepath -> new content
            run_tests: Whether to run tests after changes
            auto_push: Whether to push after successful update
            
        Returns:
            UpdateResult with details of the operation
        """
        logger.info(f"Starting self-update: {change_description}")
        
        # Create backup
        if not await self.create_backup():
            return UpdateResult(
                success=False,
                changes_made=[],
                tests_passed=False,
                commit_hash=None,
                error_message="Failed to create backup",
                rollback_needed=False
            )
        
        changes_made = []
        
        try:
            # Apply code changes
            for filepath, content in code_changes.items():
                file_path = self.project_path / filepath
                
                # Create parent directories if needed
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write new content
                file_path.write_text(content)
                changes_made.append(filepath)
                logger.info(f"Updated: {filepath}")
            
            # Run tests if requested
            tests_passed = True
            test_output = ""
            if run_tests:
                tests_passed, test_output = await self.run_tests()
            
            if not tests_passed:
                logger.warning("Tests failed, rolling back...")
                await self.rollback()
                return UpdateResult(
                    success=False,
                    changes_made=changes_made,
                    tests_passed=False,
                    commit_hash=None,
                    error_message=f"Tests failed: {test_output}",
                    rollback_needed=True
                )
            
            # Commit changes
            commit_hash = await self.commit_changes(change_description)
            
            if not commit_hash:
                logger.warning("Commit failed, rolling back...")
                await self.rollback()
                return UpdateResult(
                    success=False,
                    changes_made=changes_made,
                    tests_passed=tests_passed,
                    commit_hash=None,
                    error_message="Failed to commit changes",
                    rollback_needed=True
                )
            
            # Push if requested
            if auto_push:
                push_success = await self.push_changes()
                if not push_success:
                    logger.warning("Push failed (changes are still committed locally)")
            
            # Request restart to load new code
            await self.request_restart()
            
            return UpdateResult(
                success=True,
                changes_made=changes_made,
                tests_passed=tests_passed,
                commit_hash=commit_hash,
                error_message=None,
                rollback_needed=False
            )
            
        except Exception as e:
            logger.error(f"Self-update error: {e}")
            await self.rollback()
            return UpdateResult(
                success=False,
                changes_made=changes_made,
                tests_passed=False,
                commit_hash=None,
                error_message=str(e),
                rollback_needed=True
            )
    
    async def apply_feature_request(
        self,
        feature_description: str,
        target_file: Optional[str] = None
    ) -> UpdateResult:
        """Apply a feature request using Claude.
        
        This is the high-level method called when user says
        "add this feature to yourself".
        
        Args:
            feature_description: What feature to add
            target_file: Which file to modify (optional)
            
        Returns:
            UpdateResult with details
        """
        import anthropic
        
        if not Config.ANTHROPIC_API_KEY:
            return UpdateResult(
                success=False,
                changes_made=[],
                tests_passed=False,
                commit_hash=None,
                error_message="Claude API key not configured",
                rollback_needed=False
            )
        
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        
        # Determine target file
        if not target_file:
            # Default to sub_agents_tars.py for new features
            target_file = "sub_agents_tars.py"
        
        target_path = self.project_path / target_file
        
        if not target_path.exists():
            return UpdateResult(
                success=False,
                changes_made=[],
                tests_passed=False,
                commit_hash=None,
                error_message=f"Target file not found: {target_file}",
                rollback_needed=False
            )
        
        # Read current file content
        current_content = target_path.read_text()
        
        # Ask Claude to implement the feature
        prompt = f"""You are modifying TARS (a voice AI assistant) to add a new feature.

FEATURE REQUEST:
{feature_description}

TARGET FILE: {target_file}

CURRENT FILE CONTENT:
```python
{current_content[:50000]}  # Limit to avoid token overflow
```

Generate the COMPLETE updated file content with the new feature implemented.
Include appropriate error handling and logging.
Maintain the existing code style.

Respond with ONLY the complete Python file content, no explanations."""

        try:
            response = client.messages.create(
                model=Config.CLAUDE_COMPLEX_MODEL,
                max_tokens=100000,  # Large for full file
                messages=[{"role": "user", "content": prompt}]
            )
            
            new_content = response.content[0].text
            
            # Clean up markdown if present
            if "```python" in new_content:
                import re
                match = re.search(r'```python\s*(.*?)```', new_content, re.DOTALL)
                if match:
                    new_content = match.group(1)
            
            # Apply the update
            return await self.safe_update(
                change_description=f"Add feature: {feature_description[:50]}",
                code_changes={target_file: new_content},
                run_tests=True,
                auto_push=Config.AUTO_GIT_PUSH
            )
            
        except Exception as e:
            return UpdateResult(
                success=False,
                changes_made=[],
                tests_passed=False,
                commit_hash=None,
                error_message=f"Claude error: {str(e)}",
                rollback_needed=False
            )


# Global instance
_self_updater = None


def get_self_updater() -> SelfUpdater:
    """Get or create the global SelfUpdater instance."""
    global _self_updater
    if _self_updater is None:
        _self_updater = SelfUpdater()
    return _self_updater
