"""Security Monitor - AI-based action risk evaluation.

Replaces hardcoded destructive patterns with intelligent Claude-based
security evaluation that considers context and intent.
"""
import logging
from enum import IntEnum
from typing import Dict, Any, Optional
from dataclasses import dataclass

from core.config import Config

logger = logging.getLogger(__name__)


class RiskLevel(IntEnum):
    """Risk levels for actions."""
    SAFE = 0       # No confirmation needed
    LOW = 1        # Log only
    MEDIUM = 2     # Notify via Discord
    HIGH = 3       # Require confirmation code
    CRITICAL = 4   # Block and alert


@dataclass
class SecurityDecision:
    """Result of security evaluation."""
    risk: RiskLevel
    reasoning: str
    action_type: str
    requires_confirmation: bool
    notification_channel: Optional[str] = None
    blocked: bool = False


class SecurityMonitor:
    """AI-powered security monitor for TARS actions.
    
    Uses Claude to evaluate the risk level of actions based on:
    - Action type (terminal command, file operation, etc.)
    - Context (what project, what files affected)
    - Intent (what the user is trying to achieve)
    - Historical patterns (learned from user approvals/rejections)
    """
    
    # Known safe patterns (fast-path, no AI needed)
    SAFE_PATTERNS = [
        # Read-only commands
        'ls', 'pwd', 'cat', 'head', 'tail', 'less', 'more',
        'git status', 'git log', 'git diff', 'git branch',
        'pip list', 'npm list', 'which', 'whereis', 'echo',
        # Version checks
        'python --version', 'node --version', 'npm --version',
    ]
    
    # Known high-risk patterns (always require confirmation)
    HIGH_RISK_PATTERNS = [
        'rm -rf', 'rm -r /', 'sudo rm',
        'git push --force', 'git reset --hard',
        'dd if=', 'mkfs',
        'chmod 777', 'chown root',
        'DROP TABLE', 'DELETE FROM',
    ]
    
    # Patterns that require medium-level attention
    MEDIUM_RISK_PATTERNS = [
        'rm ', 'rmdir',
        'git push', 'git commit',
        'pip install', 'npm install',
        'chmod', 'chown',
    ]
    
    def __init__(self):
        """Initialize security monitor."""
        self.anthropic_client = None
        self.enabled = Config.SECURITY_MONITOR_ENABLED
        self.default_threshold = self._parse_threshold(Config.DEFAULT_RISK_THRESHOLD)
        
        if self.enabled and Config.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
                logger.info("SecurityMonitor initialized with Claude")
            except Exception as e:
                logger.warning(f"Failed to initialize Claude for SecurityMonitor: {e}")
    
    def _parse_threshold(self, threshold_str: str) -> RiskLevel:
        """Parse threshold string to RiskLevel."""
        mapping = {
            'low': RiskLevel.LOW,
            'medium': RiskLevel.MEDIUM,
            'high': RiskLevel.HIGH,
        }
        return mapping.get(threshold_str.lower(), RiskLevel.MEDIUM)
    
    async def evaluate_action(
        self,
        action_type: str,
        action_details: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> SecurityDecision:
        """Evaluate the security risk of an action.
        
        Args:
            action_type: Type of action (terminal_command, file_operation, etc.)
            action_details: Details about the action
            context: Optional context (current project, user, etc.)
            
        Returns:
            SecurityDecision with risk level and reasoning
        """
        if not self.enabled:
            return SecurityDecision(
                risk=RiskLevel.SAFE,
                reasoning="Security monitor disabled",
                action_type=action_type,
                requires_confirmation=False
            )
        
        # Fast-path for known patterns
        fast_result = self._check_known_patterns(action_type, action_details)
        if fast_result:
            return fast_result
        
        # Use AI for complex evaluation
        if self.anthropic_client:
            return await self._evaluate_with_ai(action_type, action_details, context)
        
        # Fallback to conservative approach
        return SecurityDecision(
            risk=RiskLevel.MEDIUM,
            reasoning="AI evaluation unavailable, defaulting to medium risk",
            action_type=action_type,
            requires_confirmation=True,
            notification_channel="discord"
        )
    
    def _check_known_patterns(
        self,
        action_type: str,
        action_details: Dict[str, Any]
    ) -> Optional[SecurityDecision]:
        """Fast-path check for known patterns."""
        
        if action_type == "terminal_command":
            command = action_details.get("command", "")
            command_lower = command.lower().strip()
            
            # Check safe patterns
            for pattern in self.SAFE_PATTERNS:
                if command_lower.startswith(pattern) or command_lower == pattern:
                    return SecurityDecision(
                        risk=RiskLevel.SAFE,
                        reasoning=f"Known safe command: {pattern}",
                        action_type=action_type,
                        requires_confirmation=False
                    )
            
            # Check high-risk patterns
            for pattern in self.HIGH_RISK_PATTERNS:
                if pattern in command_lower:
                    return SecurityDecision(
                        risk=RiskLevel.HIGH,
                        reasoning=f"High-risk pattern detected: {pattern}",
                        action_type=action_type,
                        requires_confirmation=True,
                        notification_channel="telegram"
                    )
            
            # Check medium-risk patterns
            for pattern in self.MEDIUM_RISK_PATTERNS:
                if pattern in command_lower:
                    return SecurityDecision(
                        risk=RiskLevel.MEDIUM,
                        reasoning=f"Medium-risk pattern: {pattern}",
                        action_type=action_type,
                        requires_confirmation=False,
                        notification_channel="discord"
                    )
        
        elif action_type == "file_operation":
            operation = action_details.get("operation", "")
            
            if operation in ["read", "list"]:
                return SecurityDecision(
                    risk=RiskLevel.SAFE,
                    reasoning="Read-only file operation",
                    action_type=action_type,
                    requires_confirmation=False
                )
            
            if operation == "delete":
                return SecurityDecision(
                    risk=RiskLevel.HIGH,
                    reasoning="File deletion requires confirmation",
                    action_type=action_type,
                    requires_confirmation=True,
                    notification_channel="telegram"
                )
        
        return None  # Unknown pattern, needs AI evaluation
    
    async def _evaluate_with_ai(
        self,
        action_type: str,
        action_details: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> SecurityDecision:
        """Use Claude to evaluate action risk."""
        
        prompt = f"""Evaluate the security risk of this action:

Action Type: {action_type}
Action Details: {action_details}
Context: {context or 'No additional context'}

Risk Levels:
- SAFE (0): No confirmation needed - read operations, version checks, etc.
- LOW (1): Log only - minor changes, safe installs
- MEDIUM (2): Notify via Discord - file modifications, git commits
- HIGH (3): Require confirmation code - deletions, force push, system changes
- CRITICAL (4): Block completely - dangerous system commands, credential exposure

Respond with a JSON object:
{{
    "risk_level": 0-4,
    "reasoning": "Brief explanation",
    "requires_confirmation": true/false,
    "notification_channel": "discord" or "telegram" or null
}}"""

        try:
            response = self.anthropic_client.messages.create(
                model=Config.CLAUDE_FAST_MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            
            import json
            text = response.content[0].text.strip()
            
            # Extract JSON from response
            if '{' in text and '}' in text:
                start = text.index('{')
                end = text.rindex('}') + 1
                result = json.loads(text[start:end])
                
                risk = RiskLevel(result.get('risk_level', 2))
                
                return SecurityDecision(
                    risk=risk,
                    reasoning=result.get('reasoning', 'AI evaluation'),
                    action_type=action_type,
                    requires_confirmation=result.get('requires_confirmation', risk >= RiskLevel.HIGH),
                    notification_channel=result.get('notification_channel'),
                    blocked=risk >= RiskLevel.CRITICAL
                )
                
        except Exception as e:
            logger.error(f"AI security evaluation failed: {e}")
        
        # Fallback
        return SecurityDecision(
            risk=RiskLevel.MEDIUM,
            reasoning="AI evaluation failed, defaulting to medium risk",
            action_type=action_type,
            requires_confirmation=True,
            notification_channel="discord"
        )
    
    def should_block(self, decision: SecurityDecision) -> bool:
        """Check if action should be blocked entirely."""
        return decision.blocked or decision.risk >= RiskLevel.CRITICAL
    
    def should_notify(self, decision: SecurityDecision) -> bool:
        """Check if action requires notification."""
        return decision.risk >= RiskLevel.MEDIUM
    
    def should_require_confirmation(self, decision: SecurityDecision) -> bool:
        """Check if action requires confirmation code."""
        return decision.requires_confirmation or decision.risk >= RiskLevel.HIGH


# Global instance
_security_monitor = None


def get_security_monitor() -> SecurityMonitor:
    """Get or create the global SecurityMonitor instance."""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor()
    return _security_monitor
