"""Context management for autonomous programming tasks."""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages context window size and compacts history when needed."""
    
    def __init__(self, max_tokens: int = 180000):
        """Initialize context manager.
        
        Args:
            max_tokens: Maximum tokens to allow before compaction (default: 180k)
        """
        self.max_tokens = max_tokens
        self.threshold = max_tokens * 0.8  # Compact at 80% capacity
        
        # Priority levels for context elements (1 = highest priority)
        self.priority_levels = {
            'system_prompt': 1,
            'tarsrules': 1,
            'current_phase_plan': 2,
            'phase_artifacts': 2,
            'recent_edits': 3,
            'error_log': 3,
            'recent_commands': 3,
            'old_history': 4,
            'completed_actions': 4
        }
        
        logger.info(f"ContextManager initialized with max_tokens={max_tokens}")
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.
        
        Uses rough approximation: 1 token ≈ 4 characters
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        
        return len(str(text)) // 4
    
    def estimate_context_size(self, context: Dict[str, Any]) -> int:
        """Estimate total token count for entire context.
        
        Args:
            context: Context dictionary
            
        Returns:
            Estimated total tokens
        """
        total = 0
        
        for key, value in context.items():
            if isinstance(value, list):
                # Sum tokens for list items
                for item in value:
                    total += self.estimate_tokens(str(item))
            elif isinstance(value, dict):
                # Sum tokens for dict values
                for v in value.values():
                    total += self.estimate_tokens(str(v))
            else:
                total += self.estimate_tokens(str(value))
        
        return total
    
    async def compact_if_needed(
        self,
        context: Dict[str, Any],
        claude_client = None
    ) -> Dict[str, Any]:
        """Check if context needs compaction and compress if needed.
        
        Args:
            context: Current context dictionary
            claude_client: Optional Claude client for AI-powered summarization
            
        Returns:
            Potentially compacted context
        """
        current_size = self.estimate_context_size(context)
        
        if current_size < self.threshold:
            logger.debug(f"Context size OK: {current_size}/{self.max_tokens} tokens")
            return context
        
        logger.warning(f"Context approaching limit: {current_size}/{self.max_tokens} tokens. Compacting...")
        
        # Compact completed actions (keep recent, summarize old)
        if 'completed_actions' in context and len(context['completed_actions']) > 10:
            context = await self._compact_completed_actions(context, claude_client)
        
        # Compact error log (keep recent errors only)
        if 'errors' in context and len(context['errors']) > 10:
            context['errors'] = context['errors'][-10:]
            logger.info("Trimmed error log to last 10 entries")
        
        # Compact recent commands (sliding window)
        if 'recent_commands' in context and len(context['recent_commands']) > 10:
            context['recent_commands'] = context['recent_commands'][-10:]
            logger.info("Trimmed recent commands to last 10")
        
        # Compact file edits (sliding window)
        if 'recent_file_edits' in context and len(context['recent_file_edits']) > 10:
            context['recent_file_edits'] = context['recent_file_edits'][-10:]
            logger.info("Trimmed recent file edits to last 10")
        
        new_size = self.estimate_context_size(context)
        logger.info(f"Context compacted: {current_size} -> {new_size} tokens (saved {current_size - new_size})")
        
        return context
    
    async def _compact_completed_actions(
        self,
        context: Dict[str, Any],
        claude_client = None
    ) -> Dict[str, Any]:
        """Compact completed actions list by summarizing old entries.
        
        Args:
            context: Context with completed_actions
            claude_client: Optional Claude client for summarization
            
        Returns:
            Context with compacted completed_actions
        """
        actions = context.get('completed_actions', [])
        
        if len(actions) <= 10:
            return context
        
        # Keep last 10 actions as-is
        recent_actions = actions[-10:]
        old_actions = actions[:-10]
        
        # If Claude client available, get AI summary
        if claude_client:
            try:
                summary = await self._summarize_with_claude(old_actions, claude_client)
                context['completed_actions'] = [f"[SUMMARY] {summary}"] + recent_actions
                logger.info("Summarized old actions with Claude")
                return context
            except Exception as e:
                logger.warning(f"Claude summarization failed: {e}, falling back to simple compaction")
        
        # Fallback: simple text compaction
        action_summary = f"[Earlier actions: {len(old_actions)} operations including {', '.join(set(a.split()[0] for a in old_actions[:5] if a))}]"
        context['completed_actions'] = [action_summary] + recent_actions
        logger.info("Used simple compaction for actions")
        
        return context
    
    async def _summarize_with_claude(
        self,
        actions: list,
        claude_client
    ) -> str:
        """Use Claude to generate concise summary of actions.
        
        Args:
            actions: List of action strings to summarize
            claude_client: Anthropic Claude client
            
        Returns:
            Concise summary string
        """
        from core.config import Config
        
        actions_text = '\n'.join(f"- {action}" for action in actions[:30])  # Limit to 30 items
        
        try:
            response = claude_client.messages.create(
                model=Config.CLAUDE_FAST_MODEL,  # Use fast model (Sonnet 4) for summaries
                max_tokens=1000,
                messages=[{
                    "role": "user",
                    "content": f"Summarize these coding actions concisely in 2-3 sentences:\n\n{actions_text}"
                }]
            )
            
            summary = response.content[0].text.strip()
            return summary
            
        except Exception as e:
            logger.error(f"Claude API error during summarization: {e}")
            raise
    
    def get_priority_info(self) -> Dict[str, int]:
        """Get priority levels for context elements.
        
        Returns:
            Dictionary mapping element names to priority levels
        """
        return self.priority_levels.copy()
    
    def should_compact(self, context: Dict[str, Any]) -> bool:
        """Check if context should be compacted.
        
        Args:
            context: Context to check
            
        Returns:
            True if compaction recommended
        """
        current_size = self.estimate_context_size(context)
        return current_size >= self.threshold
