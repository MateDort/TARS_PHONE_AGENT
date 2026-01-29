"""Self-Healing - Git restore and error recovery for TARS.

Enables TARS to recover from broken states by:
- Identifying what broke
- Restoring from git if self-inflicted
- Trying alternative approaches for external issues
"""
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from core.config import Config

logger = logging.getLogger(__name__)


@dataclass
class ErrorAnalysis:
    """Result of error analysis."""
    error_type: str  # 'self_inflicted', 'external', 'configuration', 'unknown'
    affected_files: List[str]
    root_cause: str
    is_recoverable: bool
    suggested_action: str
    confidence: float  # 0.0 to 1.0


class SelfHealer:
    """Self-healing capabilities for TARS.
    
    When TARS breaks itself (through code edits), this class can:
    - Detect the broken state
    - Identify which files were changed
    - Restore from git history
    - Stash broken changes for analysis
    - Request a restart via the supervisor
    """
    
    def __init__(self, project_path: Optional[str] = None):
        """Initialize self-healer.
        
        Args:
            project_path: Path to project (defaults to TARS_ROOT)
        """
        self.project_path = Path(project_path or Config.TARS_ROOT)
        self.anthropic_client = None
        
        if Config.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
            except Exception as e:
                logger.warning(f"Failed to initialize Claude for SelfHealer: {e}")
    
    async def analyze_errors(self, errors: List[str]) -> ErrorAnalysis:
        """Analyze errors to determine cause and recovery path.
        
        Args:
            errors: List of error messages
            
        Returns:
            ErrorAnalysis with diagnosis and suggested action
        """
        errors_text = "\n".join(errors[-10:])  # Last 10 errors
        
        # Check for common self-inflicted patterns
        self_inflicted_patterns = [
            "SyntaxError", "IndentationError", "ImportError",
            "ModuleNotFoundError", "NameError", "AttributeError",
            "No such file or directory", "Permission denied"
        ]
        
        affected_files = self._extract_file_paths(errors_text)
        
        # Quick pattern matching
        is_syntax_error = any(p in errors_text for p in ["SyntaxError", "IndentationError"])
        is_import_error = any(p in errors_text for p in ["ImportError", "ModuleNotFoundError"])
        
        # Check if affected files are in TARS directory
        tars_files = [f for f in affected_files if str(self.project_path) in f]
        is_self_inflicted = len(tars_files) > 0 and (is_syntax_error or is_import_error)
        
        # Use AI for deeper analysis if available
        if self.anthropic_client and not is_self_inflicted:
            return await self._analyze_with_ai(errors_text, affected_files)
        
        # Fallback to pattern-based analysis
        if is_self_inflicted:
            return ErrorAnalysis(
                error_type='self_inflicted',
                affected_files=tars_files,
                root_cause=f"Code modification caused {'syntax' if is_syntax_error else 'import'} error",
                is_recoverable=True,
                suggested_action='git_restore',
                confidence=0.85
            )
        elif "ConnectionError" in errors_text or "TimeoutError" in errors_text:
            return ErrorAnalysis(
                error_type='external',
                affected_files=[],
                root_cause="Network or service connectivity issue",
                is_recoverable=True,
                suggested_action='retry',
                confidence=0.75
            )
        else:
            return ErrorAnalysis(
                error_type='unknown',
                affected_files=affected_files,
                root_cause="Unable to determine root cause",
                is_recoverable=False,
                suggested_action='escalate',
                confidence=0.3
            )
    
    def _extract_file_paths(self, text: str) -> List[str]:
        """Extract file paths from error text."""
        import re
        
        # Match common file path patterns
        patterns = [
            r'File "([^"]+\.py)"',  # Python traceback
            r'([/\w]+\.py):(\d+)',  # file.py:line
            r'([/\w]+\.(?:js|ts|tsx|jsx)):(\d+)',  # JS/TS files
        ]
        
        files = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    files.add(match[0])
                else:
                    files.add(match)
        
        return list(files)
    
    async def _analyze_with_ai(
        self,
        errors_text: str,
        affected_files: List[str]
    ) -> ErrorAnalysis:
        """Use Claude to analyze errors."""
        
        prompt = f"""Analyze these errors and determine the cause:

ERRORS:
{errors_text}

AFFECTED FILES:
{affected_files}

TARS PROJECT PATH: {self.project_path}

Respond with JSON:
{{
    "error_type": "self_inflicted" | "external" | "configuration" | "unknown",
    "root_cause": "Brief explanation",
    "is_recoverable": true | false,
    "suggested_action": "git_restore" | "retry" | "reconfigure" | "escalate",
    "confidence": 0.0-1.0
}}"""

        try:
            response = self.anthropic_client.messages.create(
                model=Config.CLAUDE_FAST_MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            
            import json
            import re
            text = response.content[0].text
            
            match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if match:
                result = json.loads(match.group())
                return ErrorAnalysis(
                    error_type=result.get('error_type', 'unknown'),
                    affected_files=affected_files,
                    root_cause=result.get('root_cause', 'AI analysis'),
                    is_recoverable=result.get('is_recoverable', False),
                    suggested_action=result.get('suggested_action', 'escalate'),
                    confidence=result.get('confidence', 0.5)
                )
                
        except Exception as e:
            logger.error(f"AI error analysis failed: {e}")
        
        return ErrorAnalysis(
            error_type='unknown',
            affected_files=affected_files,
            root_cause="Failed to analyze",
            is_recoverable=False,
            suggested_action='escalate',
            confidence=0.2
        )
    
    async def self_heal(self, context: Dict[str, Any]) -> bool:
        """Attempt to recover from a broken state.
        
        Args:
            context: Current execution context with errors
            
        Returns:
            True if recovery was successful
        """
        errors = context.get('errors', [])
        if not errors:
            logger.info("No errors to heal")
            return True
        
        # Analyze the errors
        analysis = await self.analyze_errors(errors)
        logger.info(f"Error analysis: {analysis}")
        
        if not analysis.is_recoverable:
            logger.warning(f"Error not recoverable: {analysis.root_cause}")
            return False
        
        # Take recovery action
        if analysis.suggested_action == 'git_restore':
            return await self._restore_from_git(analysis)
        elif analysis.suggested_action == 'retry':
            return True  # Just continue, let caller retry
        elif analysis.suggested_action == 'reconfigure':
            return await self._attempt_reconfiguration(analysis)
        else:
            return False
    
    async def _restore_from_git(self, analysis: ErrorAnalysis) -> bool:
        """Restore broken files from git.
        
        Args:
            analysis: Error analysis with affected files
            
        Returns:
            True if restore was successful
        """
        if not analysis.affected_files:
            logger.warning("No files to restore")
            return False
        
        try:
            # First, stash the broken changes
            stash_result = subprocess.run(
                ["git", "stash", "push", "-m", "TARS self-heal backup"],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            logger.info(f"Stashed broken changes: {stash_result.stdout}")
            
            # Restore files from HEAD~1
            for filepath in analysis.affected_files:
                if str(self.project_path) in filepath:
                    relative_path = filepath.replace(str(self.project_path) + "/", "")
                    
                    restore_result = subprocess.run(
                        ["git", "checkout", "HEAD~1", "--", relative_path],
                        cwd=self.project_path,
                        capture_output=True,
                        text=True
                    )
                    
                    if restore_result.returncode == 0:
                        logger.info(f"Restored: {relative_path}")
                    else:
                        logger.error(f"Failed to restore {relative_path}: {restore_result.stderr}")
            
            # Request restart
            await self.request_restart()
            return True
            
        except Exception as e:
            logger.error(f"Git restore failed: {e}")
            return False
    
    async def _attempt_reconfiguration(self, analysis: ErrorAnalysis) -> bool:
        """Try to fix configuration issues.
        
        Args:
            analysis: Error analysis
            
        Returns:
            True if reconfiguration was successful
        """
        # Reload configuration
        try:
            Config.reload()
            logger.info("Configuration reloaded")
            return True
        except Exception as e:
            logger.error(f"Reconfiguration failed: {e}")
            return False
    
    async def request_restart(self):
        """Request a graceful restart via the supervisor."""
        restart_flag = self.project_path / ".tars_restart"
        
        try:
            restart_flag.touch()
            logger.info("Restart requested via .tars_restart flag")
        except Exception as e:
            logger.error(f"Failed to request restart: {e}")
    
    def get_recent_commits(self, count: int = 5) -> List[Dict[str, str]]:
        """Get recent git commits for potential rollback.
        
        Args:
            count: Number of commits to retrieve
            
        Returns:
            List of commit info dicts
        """
        try:
            result = subprocess.run(
                ["git", "log", f"-{count}", "--format=%H|%s|%ai"],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            commits = []
            for line in result.stdout.strip().split("\n"):
                if "|" in line:
                    parts = line.split("|")
                    commits.append({
                        'hash': parts[0][:8],
                        'message': parts[1],
                        'date': parts[2] if len(parts) > 2 else ''
                    })
            
            return commits
            
        except Exception as e:
            logger.error(f"Failed to get recent commits: {e}")
            return []
    
    async def rollback_to_commit(self, commit_hash: str) -> bool:
        """Rollback to a specific commit.
        
        CAUTION: This is a destructive operation.
        
        Args:
            commit_hash: Git commit hash to rollback to
            
        Returns:
            True if rollback was successful
        """
        try:
            # Create backup branch first
            backup_branch = f"tars-backup-{subprocess.run(['date', '+%Y%m%d_%H%M%S'], capture_output=True, text=True).stdout.strip()}"
            subprocess.run(
                ["git", "branch", backup_branch],
                cwd=self.project_path
            )
            logger.info(f"Created backup branch: {backup_branch}")
            
            # Reset to commit
            result = subprocess.run(
                ["git", "reset", "--hard", commit_hash],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Rolled back to {commit_hash}")
                await self.request_restart()
                return True
            else:
                logger.error(f"Rollback failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Rollback error: {e}")
            return False


# Global instance
_self_healer = None


def get_self_healer() -> SelfHealer:
    """Get or create the global SelfHealer instance."""
    global _self_healer
    if _self_healer is None:
        _self_healer = SelfHealer()
    return _self_healer
