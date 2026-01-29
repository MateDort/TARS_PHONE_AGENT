"""Task Router - AI-powered decision maker for routing tasks to foreground or background."""
import logging
from enum import Enum
from typing import Optional, Dict, Any
from core.config import Config

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Classification of task types based on expected duration."""
    INSTANT = "instant"      # < 2 seconds - simple answers, time, weather
    SHORT = "short"          # < 30 seconds - file read, git status, simple search
    BACKGROUND = "background"  # > 30 seconds - programming, research, calls


class TaskRouter:
    """Routes tasks to appropriate execution mode based on AI classification.
    
    Uses fast Gemini classification to decide if a task should:
    - Run instantly (foreground, immediate response)
    - Run as short task (foreground, wait for result)
    - Run in background (queue for worker, return immediately)
    """
    
    # Keywords that strongly indicate background tasks (Redis Queue workers)
    # NOTE: "call/phone" are NOT here - calls create new Gemini sessions via Twilio,
    # they don't use background workers and have their own session limit
    BACKGROUND_KEYWORDS = [
        "build", "create project", "code", "program", "develop",
        "research", "deep dive", "analyze in depth", "comprehensive",
        "fix all", "refactor", "migrate", "update all",
        "test", "run tests", "debug",
        "control computer", "use computer", "click", "type", "open app", "screenshot"
    ]
    
    # Keywords that indicate instant responses
    INSTANT_KEYWORDS = [
        "what time", "what's the time", "current time",
        "what day", "what date", "today",
        "weather", "temperature",
        "hello", "hi", "hey", "thanks", "thank you",
        "yes", "no", "okay", "ok", "sure",
        "how are you", "what's up"
    ]
    
    # Keywords that indicate short tasks
    SHORT_KEYWORDS = [
        "git status", "git log", "git diff",
        "list files", "show files", "ls",
        "read file", "cat", "show me",
        "search for", "find", "grep",
        "quick", "simple", "just"
    ]
    
    def __init__(self, gemini_client=None):
        """Initialize task router.
        
        Args:
            gemini_client: Optional Gemini client for AI classification
        """
        self.gemini_client = gemini_client
        
        # Try to initialize Gemini if not provided
        if not self.gemini_client and Config.GEMINI_API_KEY:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)
                logger.info("TaskRouter: Gemini client initialized")
            except Exception as e:
                logger.warning(f"TaskRouter: Could not initialize Gemini: {e}")
    
    def classify_task(self, user_request: str) -> TaskType:
        """Classify a user request into task type.
        
        Uses a two-stage approach:
        1. Fast keyword matching (no API call)
        2. AI classification if uncertain (Gemini)
        
        Args:
            user_request: The user's request text
            
        Returns:
            TaskType indicating how the task should be executed
        """
        request_lower = user_request.lower()
        
        # Stage 1: Fast keyword matching
        keyword_result = self._classify_by_keywords(request_lower)
        if keyword_result:
            logger.debug(f"Task classified by keywords: {keyword_result.value}")
            return keyword_result
        
        # Stage 2: AI classification (if Gemini available)
        if self.gemini_client:
            try:
                ai_result = self._classify_with_ai(user_request)
                logger.debug(f"Task classified by AI: {ai_result.value}")
                return ai_result
            except Exception as e:
                logger.warning(f"AI classification failed: {e}")
        
        # Default: treat as short task
        logger.debug("Task classification defaulted to SHORT")
        return TaskType.SHORT
    
    def _classify_by_keywords(self, request_lower: str) -> Optional[TaskType]:
        """Fast classification using keyword matching."""
        # Check for background keywords
        for keyword in self.BACKGROUND_KEYWORDS:
            if keyword in request_lower:
                return TaskType.BACKGROUND
        
        # Check for instant keywords
        for keyword in self.INSTANT_KEYWORDS:
            if keyword in request_lower:
                return TaskType.INSTANT
        
        # Check for short keywords
        for keyword in self.SHORT_KEYWORDS:
            if keyword in request_lower:
                return TaskType.SHORT
        
        # Length heuristic: very short requests are usually instant
        if len(request_lower) < 20:
            return TaskType.INSTANT
        
        return None  # Uncertain, needs AI classification
    
    def _classify_with_ai(self, user_request: str) -> TaskType:
        """Use Gemini to classify task type."""
        prompt = f"""Classify this user request into one of three categories based on how long it would take to complete:

Request: "{user_request}"

Categories:
- INSTANT: Simple greetings, time/date questions, yes/no answers, weather (< 2 seconds)
- SHORT: File operations, git status, simple searches, quick lookups (< 30 seconds)
- BACKGROUND: Programming tasks, deep research, phone calls, multi-step operations (> 30 seconds)

Respond with ONLY one word: INSTANT, SHORT, or BACKGROUND"""

        try:
            response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            
            result = response.text.strip().upper()
            
            if "INSTANT" in result:
                return TaskType.INSTANT
            elif "BACKGROUND" in result:
                return TaskType.BACKGROUND
            else:
                return TaskType.SHORT
                
        except Exception as e:
            logger.error(f"Gemini classification error: {e}")
            return TaskType.SHORT
    
    def should_run_in_background(self, user_request: str) -> bool:
        """Quick check if a task should run in background.
        
        Args:
            user_request: The user's request
            
        Returns:
            True if task should be queued for background execution
        """
        task_type = self.classify_task(user_request)
        return task_type == TaskType.BACKGROUND
    
    def get_routing_info(self, user_request: str) -> Dict[str, Any]:
        """Get detailed routing information for a request.
        
        Args:
            user_request: The user's request
            
        Returns:
            Dict with routing details
        """
        task_type = self.classify_task(user_request)
        
        return {
            "task_type": task_type.value,
            "run_in_background": task_type == TaskType.BACKGROUND,
            "expected_duration": self._get_duration_estimate(task_type),
            "user_message": self._get_user_message(task_type, user_request)
        }
    
    def _get_duration_estimate(self, task_type: TaskType) -> str:
        """Get human-readable duration estimate."""
        estimates = {
            TaskType.INSTANT: "< 2 seconds",
            TaskType.SHORT: "< 30 seconds",
            TaskType.BACKGROUND: "1-15 minutes"
        }
        return estimates.get(task_type, "unknown")
    
    def _get_user_message(self, task_type: TaskType, request: str) -> Optional[str]:
        """Get optional message to send to user about task routing."""
        if task_type == TaskType.BACKGROUND:
            return f"I'll work on this in the background and update you when it's done."
        return None


# Global router instance (lazy initialization)
_router_instance = None


def get_task_router() -> TaskRouter:
    """Get or create the global TaskRouter instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = TaskRouter()
    return _router_instance
