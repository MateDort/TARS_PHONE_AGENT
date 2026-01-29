"""Background worker for autonomous programming tasks."""
import asyncio
import logging
import time
import json
import subprocess
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from redis import Redis
from rq import get_current_job
import anthropic

from core.config import Config
from core.security import verify_confirmation_code

logger = logging.getLogger(__name__)


def detect_project_type(project_path: str) -> str:
    """Auto-detect project type from files in directory.
    
    Args:
        project_path: Path to project directory
        
    Returns:
        Project type string (python, node, react, nextjs, rust, etc.)
    """
    path = Path(project_path)
    
    # Check for specific framework files
    if (path / "next.config.js").exists() or (path / "next.config.mjs").exists():
        return "nextjs"
    elif (path / "package.json").exists():
        try:
            package_json = json.loads((path / "package.json").read_text())
            deps = {**package_json.get("dependencies", {}), **package_json.get("devDependencies", {})}
            if "react" in deps:
                return "react"
            elif "vue" in deps:
                return "vue"
            elif "express" in deps:
                return "node-express"
            else:
                return "node"
        except:
            return "node"
    elif (path / "requirements.txt").exists() or (path / "setup.py").exists() or (path / "pyproject.toml").exists():
        return "python"
    elif (path / "Cargo.toml").exists():
        return "rust"
    elif (path / "go.mod").exists():
        return "go"
    elif (path / "pom.xml").exists():
        return "java-maven"
    elif (path / "build.gradle").exists():
        return "java-gradle"
    else:
        return "unknown"


def generate_default_tarsrules(project_path: str, project_type: str) -> str:
    """Generate default .tarsrules file based on project type.
    
    Args:
        project_path: Path to project directory
        project_type: Detected project type
        
    Returns:
        Default .tarsrules content
    """
    project_name = Path(project_path).name
    
    # Base template
    template = f"""# TARS Coding Rules for {project_name}

## Project Type
- Type: {project_type}
- Auto-generated: {datetime.now().strftime('%Y-%m-%d')}

## Language & Style
"""
    
    # Add language-specific rules
    if project_type in ['python']:
        template += """- Python 3.11+
- Use type hints always
- Follow PEP 8 style guide
- Async/await for I/O operations
- Use pathlib for file paths
"""
    elif project_type in ['nextjs', 'react', 'node']:
        template += """- TypeScript preferred
- Use modern ES6+ syntax
- Async/await over promises
- Use const/let, never var
- Follow Airbnb style guide
"""
    elif project_type == 'rust':
        template += """- Rust stable edition
- Follow clippy recommendations
- Use Result<T, E> for error handling
- Prefer ? operator over unwrap()
"""
    else:
        template += """- [Auto-detected or user-specified]
"""
    
    template += """
## Architecture Patterns
- Modular design with clear separation of concerns
- Keep functions small and focused
- Write self-documenting code with clear names

## Git Policy
- Commit message format: "[PHASE] Action: brief description"
- Push after each phase completion
- Create feature branches for major changes

## Testing Requirements
"""
    
    # Add test command detection
    path = Path(project_path)
    if (path / "package.json").exists():
        template += """- Run: npm test
- Write tests for new features
"""
    elif project_type == 'python':
        template += """- Run: pytest
- Write tests for new features
- Aim for >80% coverage
"""
    else:
        template += """- [Auto-detected test commands]
"""
    
    template += """
## Custom Instructions
# Add project-specific rules below:
# - Specific libraries to use/avoid
# - API patterns
# - File organization rules
"""
    
    return template


async def load_project_context(project_path: str) -> dict:
    """Load project-specific context including .tarsrules and owner preferences.
    
    Args:
        project_path: Path to project directory
        
    Returns:
        Dictionary with project context (rules, owner_profile, project_type)
    """
    context = {}
    path = Path(project_path)
    
    # Detect project type
    context['project_type'] = detect_project_type(project_path)
    
    # Load .tarsrules
    rules_path = path / ".tarsrules"
    if rules_path.exists():
        try:
            context['rules'] = rules_path.read_text()
            logger.info(f"Loaded .tarsrules from {rules_path}")
        except Exception as e:
            logger.warning(f"Could not load .tarsrules: {e}")
            context['rules'] = generate_default_tarsrules(project_path, context['project_type'])
    else:
        # Create default .tarsrules
        context['rules'] = generate_default_tarsrules(project_path, context['project_type'])
        try:
            rules_path.write_text(context['rules'])
            logger.info(f"Created default .tarsrules at {rules_path}")
        except Exception as e:
            logger.warning(f"Could not create .tarsrules: {e}")
    
    # Load Máté's preferences
    mate_path = Path(__file__).parent.parent / "Máté.md"
    if mate_path.exists():
        try:
            context['owner_profile'] = mate_path.read_text()
            logger.info("Loaded owner preferences from Máté.md")
        except Exception as e:
            logger.warning(f"Could not load Máté.md: {e}")
    
    # Load TARS identity
    tars_path = Path(__file__).parent.parent / "TARS.md"
    if tars_path.exists():
        try:
            context['tars_identity'] = tars_path.read_text()
        except Exception as e:
            logger.warning(f"Could not load TARS.md: {e}")
    
    return context


class TaskProgressTracker:
    """Tracks and reports progress of background tasks.
    
    Programming logs ONLY go to Discord (never Telegram).
    Confirmations and questions go to Telegram via KIPP.
    """
    
    def __init__(self, task_id: str, discord_updates: bool = True):
        self.task_id = task_id
        self.discord_updates = discord_updates
        self.phase = "init"
        self.iteration = 0
    
    async def send_update(self, message: str, phase: Optional[str] = None, command: Optional[str] = None):
        """Send progress update to Discord ONLY.
        
        Programming task logs always go to Discord, never Telegram.
        
        Args:
            message: Update message
            phase: Current phase (planning, coding, testing, etc.)
            command: Terminal command if applicable
        """
        if phase:
            self.phase = phase
        
        # Check if we should send this update (respect verbosity setting)
        if not Config.ENABLE_DETAILED_UPDATES and not phase and not command:
            # Skip detailed updates if verbosity is off
            return
        
        # Update job metadata
        job = get_current_job()
        if job:
            job.meta['progress'] = message
            if phase:
                job.meta['phase'] = phase
            job.save_meta()
        
        # Send to Discord ONLY (programming logs never go to Telegram)
        if self.discord_updates:
            await send_programming_log({
                'task_id': self.task_id,
                'type': 'progress' if not phase else 'phase_complete',
                'message': message,
                'phase': phase,
                'command': command
            })
        
        logger.info(f"Task {self.task_id}: {message}")

    async def send_research_to_gmail(self, goal: str, report: str):
        """Send research results via Gmail through KIPP.
        
        Args:
            goal: Research topic/goal
            report: Full research report text
        """
        import aiohttp
        
        webhook_url = Config.N8N_WEBHOOK_URL
        if not webhook_url:
            logger.warning("N8N webhook not configured - cannot send research to Gmail")
            return
        
        email_subject = f"TARS Research Complete: {goal[:50]}"
        email_body = f"""
<h2>Deep Research Report</h2>
<p><strong>Topic:</strong> {goal}</p>
<p><strong>Task ID:</strong> {self.task_id}</p>
<p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<hr>

<h3>Report</h3>
<pre style="white-space: pre-wrap; font-family: sans-serif;">
{report}
</pre>

<hr>
<p><em>Generated by TARS Deep Research Agent (Background Worker)</em></p>
"""
        
        gmail_payload = {
            "target": "gmail",
            "source": "deep_research",
            "message_type": "research_report",
            "routing_instruction": "send_via_gmail",
            "subject": email_subject,
            "body": email_body,
            "message": f"Research report for: {goal}",
            "task_id": self.task_id
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=gmail_payload,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Research report sent to Gmail via KIPP for task {self.task_id}")
                    else:
                        logger.warning(f"KIPP Gmail webhook returned {response.status}")
        except Exception as e:
            logger.error(f"Failed to send research to Gmail via KIPP: {e}")


async def send_programming_log(data: dict):
    """Send PROGRAMMING LOG to Discord ONLY via KIPP.
    
    Programming task logs always go to Discord, never Telegram.
    This ensures clean separation: logs to Discord, confirmations to Telegram.
    
    Args:
        data: {
            'task_id': str,
            'type': str (task_started|progress|phase_complete|task_complete|error),
            'message': str,
            'command': str (optional),
            'phase': str (optional)
        }
    """
    webhook_url = Config.N8N_WEBHOOK_URL
    
    if not webhook_url:
        logger.warning("N8N webhook not configured for updates")
        return
    
    # Programming logs ALWAYS go to Discord
    payload = {
        "target": "discord",  # ALWAYS Discord for programming logs
        "routing_instruction": "send_via_discord",  # Explicit instruction for KIPP
        "message_type": "programming_log",  # This is a programming log
        "source": "background_task",
        "task_id": data.get('task_id'),
        "type": data.get('type'),
        "message": data.get('message'),
        "timestamp": datetime.now().isoformat()
    }
    
    if 'command' in data:
        payload['command'] = data['command']
    if 'phase' in data:
        payload['phase'] = data['phase']
    if 'goal' in data:
        payload['goal'] = data['goal']
    if 'project' in data:
        payload['project'] = data['project']
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    logger.debug(f"Sent programming log to Discord: {data.get('message', '')[:50]}")
                else:
                    logger.warning(f"KIPP webhook returned {response.status}")
    except Exception as e:
        logger.error(f"Failed to send programming log via KIPP: {e}")


async def send_log_update(data: dict):
    """Send LOG/STATUS update via KIPP to configured channel (Discord or Telegram).
    
    Uses Config.LOG_CHANNEL to determine where logs go.
    For confirmations/questions that need user response, use send_confirmation_request().
    
    Args:
        data: {
            'task_id': str,
            'type': str (task_started|progress|phase_complete|task_complete|error),
            'message': str,
            'command': str (optional),
            'phase': str (optional)
        }
    """
    webhook_url = Config.N8N_WEBHOOK_URL
    
    if not webhook_url:
        logger.warning("N8N webhook not configured for updates")
        return
    
    # Use configured log channel (default: discord)
    log_channel = Config.LOG_CHANNEL.lower()
    
    # Format payload for KIPP/N8N
    payload = {
        "target": log_channel,  # KIPP routes based on this
        "routing_instruction": f"send_via_{log_channel}",  # Clear instruction for KIPP
        "message_type": "log",  # This is a log message, not a confirmation
        "source": "background_task",
        "task_id": data.get('task_id'),
        "type": data.get('type'),
        "message": data.get('message'),
        "timestamp": datetime.now().isoformat()
    }
    
    if 'command' in data:
        payload['command'] = data['command']
    if 'phase' in data:
        payload['phase'] = data['phase']
    if 'goal' in data:
        payload['goal'] = data['goal']
    if 'project' in data:
        payload['project'] = data['project']
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    logger.info(f"Sent log to {log_channel} via KIPP: {data.get('message', '')[:50]}")
                else:
                    logger.warning(f"KIPP webhook returned {response.status}")
    except Exception as e:
        logger.error(f"Failed to send log update via KIPP: {e}")


# Alias for backward compatibility
send_discord_update = send_log_update


async def send_confirmation_request(data: dict):
    """Send CONFIRMATION REQUEST via KIPP to configured channel (Discord or Telegram).
    
    Uses Config.CONFIRMATION_CHANNEL to determine where confirmations go.
    This is for confirmations, questions, and plan approvals that need user response.
    
    Args:
        data: {
            'task_id': str,
            'type': str (confirmation_request|user_question|plan_approval_request),
            'message': str,
            'command': str (optional),
            'options': list (optional),
            'reason': str (optional)
        }
    """
    webhook_url = Config.N8N_WEBHOOK_URL
    
    if not webhook_url:
        logger.warning("N8N webhook not configured for confirmations")
        return
    
    # Use configured confirmation channel (default: telegram)
    confirm_channel = Config.CONFIRMATION_CHANNEL.lower()
    
    # Format payload for KIPP/N8N
    payload = {
        "target": confirm_channel,  # KIPP routes based on this
        "routing_instruction": f"send_via_{confirm_channel}",  # Clear instruction for KIPP
        "message_type": "confirmation",  # This needs user response
        "source": "background_task",
        "task_id": data.get('task_id'),
        "type": data.get('type'),
        "message": data.get('message'),
        "awaiting_response": True,  # KIPP knows to expect a reply
        "timestamp": datetime.now().isoformat()
    }
    
    if 'command' in data:
        payload['command'] = data['command']
    if 'options' in data:
        payload['options'] = data['options']
    if 'reason' in data:
        payload['reason'] = data['reason']
    if 'plan' in data:
        payload['plan'] = data['plan']
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    logger.info(f"Sent confirmation to {confirm_channel} via KIPP: {data.get('message', '')[:50]}")
                else:
                    logger.warning(f"KIPP webhook returned {response.status}")
    except Exception as e:
        logger.error(f"Failed to send confirmation via KIPP: {e}")


# Alias for backward compatibility
send_telegram_confirmation = send_confirmation_request


def get_command_reason(command: str) -> str:
    """Get a short reason why a command needs confirmation.
    
    Returns a brief explanation like "delete files", "modify database", etc.
    """
    command_lower = command.lower()
    
    if 'rm ' in command_lower or 'delete' in command_lower:
        return "delete files"
    elif 'drop ' in command_lower or 'truncate' in command_lower:
        return "modify database"
    elif 'push' in command_lower and 'force' in command_lower:
        return "force push to git (destructive)"
    elif 'reset --hard' in command_lower:
        return "discard all changes"
    elif 'chmod' in command_lower or 'chown' in command_lower:
        return "change permissions"
    elif 'kill' in command_lower or 'pkill' in command_lower:
        return "terminate processes"
    elif 'sudo' in command_lower:
        return "run with elevated privileges"
    else:
        return "run a potentially destructive command"


async def request_confirmation_dual_channel(
    task_id: str,
    command: str,
    reason: str,
    session_manager,
    timeout_seconds: int = 300  # 5 minutes
) -> Optional[str]:
    """Request confirmation code via Discord AND voice call (if active).
    
    This pauses the background task and:
    1. Sends Discord message with command + reason
    2. If user is in an active call, also asks via voice
    3. Waits for confirmation code from either channel
    
    Args:
        task_id: Background task ID
        command: The command that needs confirmation
        reason: Short explanation of why (e.g., "deletes files", "modifies database")
        session_manager: To check for active user sessions
        timeout_seconds: How long to wait for response
    
    Returns:
        Confirmation code if provided, None if timeout
    """
    # Format the confirmation message
    telegram_message = (
        f"⚠️ **Background Task #{task_id} Needs Confirmation**\n\n"
        f"**Command:** `{command}`\n"
        f"**Reason:** {reason}\n\n"
        f"Reply with your confirmation code to proceed."
    )
    
    voice_message = (
        f"Sir, the background programming task needs your confirmation code. "
        f"I need to run: {command}. "
        f"This is needed to {reason}. "
        f"Please provide your confirmation code."
    )
    
    # 1. Send Telegram confirmation request (confirmations go to Telegram for easy reply)
    await send_telegram_confirmation({
        'task_id': task_id,
        'type': 'confirmation_request',
        'command': command,
        'reason': reason,
        'message': telegram_message
    })
    
    # 2. Check if user is in an active call
    # Note: Background worker runs in separate process, so we use Redis to communicate
    # Store a flag that main TARS process can check
    redis_conn = Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB
    )
    
    # Set a flag for main TARS to check
    redis_conn.setex(
        f"task:{task_id}:needs_voice_confirm",
        300,  # 5 minutes
        json.dumps({
            'command': command,
            'reason': reason,
            'voice_message': voice_message
        })
    )
    
    # If session_manager is available (shouldn't be in worker, but just in case)
    if session_manager:
        try:
            user_session = await session_manager.get_active_user_session()
            if user_session:
                await session_manager.send_message_to_session(
                    session_id=user_session.id,
                    message=voice_message,
                    interrupt=True
                )
                logger.info(f"Requested confirmation via voice and Discord for task {task_id}")
            else:
                logger.info(f"Requested confirmation via Discord only for task {task_id}")
        except Exception as e:
            logger.warning(f"Could not send voice confirmation (worker process limitation): {e}")
            logger.info(f"Requested confirmation via Discord only for task {task_id}")
    else:
        logger.info(f"Requested confirmation via Discord (worker runs in separate process)")
    
    # 3. Mark task as awaiting confirmation in job metadata
    current_job = get_current_job()
    if current_job:
        current_job.meta['awaiting_confirmation'] = True
        current_job.meta['confirmation_command'] = command
        current_job.save_meta()
    
    # 4. Poll Redis for response (can come from Discord webhook OR voice call)
    redis_conn = Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB
    )
    confirmation_key = f"task:{task_id}:confirmation"
    
    start_time = time.time()
    while (time.time() - start_time) < timeout_seconds:
        code = redis_conn.get(confirmation_key)
        if code:
            redis_conn.delete(confirmation_key)
            
            # Clear awaiting confirmation flag
            if current_job:
                current_job.meta['awaiting_confirmation'] = False
                current_job.save_meta()
            
            logger.info(f"Received confirmation code for task {task_id}")
            return code.decode('utf-8')
        await asyncio.sleep(2)  # Poll every 2 seconds
    
    # Timeout - notify both channels
    await send_discord_update({
        'task_id': task_id,
        'type': 'error',
        'message': f"❌ Task #{task_id} timed out waiting for confirmation"
    })
    
    if user_session:
        await session_manager.send_message_to_session(
            session_id=user_session.id,
            message=f"The background task #{task_id} timed out waiting for confirmation, sir."
        )
    
    return None


def is_destructive_command(command: str) -> bool:
    """Check if a command is potentially destructive and needs confirmation."""
    command_lower = command.lower()
    
    destructive_patterns = [
        'rm ', 'delete', 'drop ', 'truncate', '--force', '-f ',
        'reset --hard', 'chmod', 'chown', 'kill', 'pkill', 'sudo'
    ]
    
    for pattern in destructive_patterns:
        if pattern in command_lower:
            return True
    
    return False


async def _run_checkpoint_verification(
    claude_client,
    goal: str,
    context: Dict[str, Any],
    tracker
) -> Dict[str, Any]:
    """Run a checkpoint verification to assess task progress.
    
    Called every 50 iterations to decide whether to:
    - Mark as complete (all goals achieved)
    - Continue (making good progress)
    - Attempt recovery (stuck or failing)
    
    Args:
        claude_client: Anthropic client
        goal: Original task goal
        context: Current execution context
        tracker: Progress tracker for updates
        
    Returns:
        Dict with:
            - status: 'complete', 'in_progress', 'stuck', 'uncertain'
            - reason: Explanation
            - recovery_action: If stuck, what to try ('continue', 'reset', 'skip')
    """
    # Build summary of what's been done
    completed_summary = "\n".join(context.get('completed_actions', [])[-20:])
    error_summary = "\n".join(context.get('errors', [])[-5:])
    
    prompt = f"""You are evaluating whether a programming task has been completed successfully.

ORIGINAL GOAL:
{goal}

COMPLETED ACTIONS (last 20):
{completed_summary}

RECENT ERRORS (last 5):
{error_summary}

CURRENT PHASE: {context.get('current_phase', 'unknown')}
TOTAL ITERATIONS: {context.get('iteration', 0)}
STUCK COUNTER: {context.get('stuck_counter', 0)}

Analyze the progress and respond with a JSON object:
{{
    "status": "complete" | "in_progress" | "stuck" | "uncertain",
    "reason": "Brief explanation of your assessment",
    "progress_percentage": 0-100,
    "recovery_action": "continue" | "reset" | "skip" (if stuck)
}}

Consider:
- 'complete': Goal achieved, tests passing, ready for final verification
- 'in_progress': Making meaningful progress, should continue
- 'stuck': No progress being made, same errors repeating
- 'uncertain': Cannot determine status, need more information"""

    try:
        response = claude_client.messages.create(
            model=Config.CLAUDE_FAST_MODEL,  # Use faster model for checkpoints
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        import re
        text = response.content[0].text
        
        # Extract JSON from response
        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            logger.info(f"Checkpoint result: {result.get('status')} - {result.get('reason', '')[:50]}")
            return result
        
    except Exception as e:
        logger.error(f"Checkpoint verification failed: {e}")
    
    # Default to uncertain if we can't parse
    return {
        'status': 'uncertain',
        'reason': 'Failed to evaluate progress',
        'recovery_action': 'continue'
    }


async def run_autonomous_programming(
    task_id: str,
    goal: str,
    project_path: str,
    session_id: str,
    max_iterations: int = 50,
    max_minutes: int = 15
):
    """Run an autonomous programming session with phase-based execution.
    
    This is the main worker function called by RQ. It implements Claude Code-style
    workflow with distinct phases:
    1. DISCOVER - Map project structure (read-only)
    2. PLAN - Generate detailed plan with user approval
    3. EXECUTE - Implement with auto-git commits
    4. VERIFY - Run tests and fix failures
    5. PUBLISH - Push to GitHub
    
    Args:
        task_id: Unique task ID
        goal: What to build/fix
        project_path: Where to work
        session_id: TARS session that started this task
        max_iterations: Maximum total iterations across all phases
        max_minutes: Maximum runtime in minutes
    """
    # CRITICAL: Set fork safety FIRST, before any imports that might use Objective-C
    import os
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
    
    # NOW import the modules (after fork safety is set)
    from core.session_manager import SessionManager
    from core.database import Database
    from sub_agents_tars import ProgrammerAgent
    from core.phase_manager import PhaseManager, PHASES
    from core.context_manager import ContextManager
    from core.verification import VerificationEngine
    from core.user_interaction import ask_user_question, request_plan_approval, send_phase_completion_notification
    
    logger.info(f"Starting phase-based autonomous programming task {task_id}: {goal}")
    
    # Initialize
    tracker = TaskProgressTracker(task_id, discord_updates=True)
    start_time = time.time()
    
    # Send initial update
    await tracker.send_update(
        f"🚀 Started autonomous coding (Phase-Based)\n**Goal:** {goal}\n**Project:** {project_path}",
        phase="started"
    )
    
    try:
        # Initialize all managers and systems
        db = Database()
        session_manager = None  # Worker runs in separate process
        programmer = ProgrammerAgent(db=db, github_handler=None, session_manager=session_manager)
        claude_client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        
        # Initialize phase-based systems
        phase_manager = PhaseManager(project_path)
        context_mgr = ContextManager(max_tokens=180000)
        verifier = VerificationEngine(project_path)
        
        # Load project context (.tarsrules, owner preferences, etc.)
        await tracker.send_update("📚 Loading project context...")
        project_context = await load_project_context(project_path)
        
        # Ensure git repository exists
        await tracker.send_update("🔧 Ensuring git repository...")
        git_init_result = await programmer._git_ensure_repo(project_path)
        logger.info(f"Git repo status: {git_init_result}")
        
        # Initialize context
        context = {
            "goal": goal,
            "project_path": project_path,
            "project_context": project_context,
            "iteration": 0,
            "errors": [],
            "completed_actions": [],
            "recent_commands": [],
            "recent_file_edits": [],
            "stuck_counter": 0,
            "git_commits": []
        }
        
        # Start with DISCOVER phase
        current_phase = 'DISCOVER'
        await tracker.send_update(
            f"🔍 Entering DISCOVER phase\nMapping project structure...",
            phase="discover"
        )
        
        # MAIN PHASE LOOP
        total_iterations = 0
        while current_phase != 'COMPLETE' and total_iterations < max_iterations:
            # Get current phase configuration
            phase_config = phase_manager.get_phase_config(current_phase)
            
            # Phase iteration loop
            for phase_iteration in range(phase_config.get('max_iterations', 10)):
                total_iterations += 1
                
                # Check if stuck (no progress for 5 iterations)
                if context['stuck_counter'] >= 5:
                    await tracker.send_update(
                        f"⚠️ No progress for 5 iterations. Task may be stuck.\n"
                        f"Last actions: {context['completed_actions'][-3:]}\n"
                        f"Attempting to break out of loop...",
                        phase="stuck"
                    )
                    context['stuck_counter'] = 0  # Reset and try to recover
                
                # Check timeout
                elapsed = (time.time() - start_time) / 60
                if elapsed > max_minutes:
                    await tracker.send_update(
                        f"⏱️ Time limit reached ({max_minutes} min)",
                        phase="timeout"
                    )
                    break
                
                # Update context
                context["iteration"] = total_iterations
                
                # Compact context if needed
                context = await context_mgr.compact_if_needed(context, claude_client)
                
                # Get phase-specific system prompt
                system_prompt = phase_manager.get_phase_prompt(current_phase, context, project_context)
                
                # Build conversation messages with context
                # Include what Claude has done so far and file contents it has read
                conversation_context = f"Goal: {goal}\n\n"
                
                # Add completed actions
                if context.get('completed_actions'):
                    conversation_context += "Actions completed so far:\n"
                    for action in context['completed_actions'][-10:]:  # Last 10 actions
                        conversation_context += f"- {action}\n"
                    conversation_context += "\n"
                
                # Add file contents that were read
                if context.get('file_contents'):
                    conversation_context += "Files I have read:\n"
                    for filepath, content in list(context['file_contents'].items())[-5:]:  # Last 5 files
                        from pathlib import Path
                        filename = Path(filepath).name
                        # Truncate content for context
                        truncated = content[:3000] if len(content) > 3000 else content
                        conversation_context += f"\n--- {filename} ---\n{truncated}\n"
                    conversation_context += "\n"
                
                # Add recent errors
                if context.get('errors') and len(context['errors']) > 0:
                    conversation_context += "Recent errors:\n"
                    for err in context['errors'][-3:]:
                        conversation_context += f"- {err}\n"
                    conversation_context += "\n"
                
                conversation_context += "What action should I take next? Respond with a JSON object."
                
                # Ask Claude what to do next
                try:
                    response = claude_client.messages.create(
                        model=Config.CLAUDE_COMPLEX_MODEL,
                        max_tokens=4000,
                        temperature=0.7,
                        system=system_prompt,
                        messages=[{
                            "role": "user",
                            "content": conversation_context
                        }]
                    )
                    
                    # Parse Claude's decision
                    import json
                    import re
                    decision_text = response.content[0].text
                    
                    # Log raw response for debugging
                    logger.debug(f"Claude response (raw): {decision_text[:200]}")
                    
                    # Extract JSON from markdown code blocks if present
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', decision_text, re.DOTALL)
                    if json_match:
                        decision_text = json_match.group(1)
                    else:
                        # Try to find JSON object directly
                        json_match = re.search(r'\{.*\}', decision_text, re.DOTALL)
                        if json_match:
                            decision_text = json_match.group(0)
                    
                    decision = json.loads(decision_text)
                    
                    action = decision.get('action')
                    
                    # VALIDATE ACTION AGAINST PHASE CONSTRAINTS
                    if not phase_manager.validate_action(current_phase, action):
                        await tracker.send_update(
                            f"⚠️ Action '{action}' not allowed in {current_phase} phase"
                        )
                        context['stuck_counter'] += 1
                        continue
                    
                    # HANDLE PHASE COMPLETION
                    if action == 'complete_phase':
                        summary = decision.get('summary', 'Phase complete')
                        phase_manager.save_phase_artifact(current_phase, summary)
                        
                        next_phase = phase_manager.get_next_phase(current_phase)
                        await send_phase_completion_notification(task_id, current_phase, summary, next_phase)
                        
                        # Handle PLAN phase approval
                        if current_phase == 'PLAN':
                            approved = await request_plan_approval(task_id, summary, 600)
                            if approved:
                                current_phase = 'EXECUTE'
                            else:
                                continue  # Revise plan
                        elif phase_manager.should_auto_transition(current_phase):
                            current_phase = next_phase
                        
                        break  # Exit phase iteration loop
                    
                    # HANDLE ASK USER QUESTION (PLAN phase)
                    elif action == 'ask_user_question':
                        question = decision.get('question', '')
                        options = decision.get('options', [])
                        answer = await ask_user_question(task_id, question, options, 300)
                        context['completed_actions'].append(f"Asked: {question[:30]}")
                        context['stuck_counter'] = 0
                        continue
                    
                    # HANDLE READ FILE (for discovery/analysis)
                    elif action == 'read_file':
                        file_path = decision.get('file_path')
                        
                        if not file_path:
                            logger.error("No file_path provided in read_file action")
                            context['errors'].append("Missing file_path for read")
                            context['stuck_counter'] += 1
                            continue
                        
                        # Convert to absolute path if relative
                        from pathlib import Path
                        if not Path(file_path).is_absolute():
                            file_path = str(Path(project_path) / file_path)
                        
                        try:
                            file_path_obj = Path(file_path).expanduser()
                            if file_path_obj.exists():
                                content = file_path_obj.read_text()
                                # Truncate very long files
                                if len(content) > 10000:
                                    content = content[:10000] + f"\n\n... [truncated, {len(content)} total chars]"
                                
                                context['completed_actions'].append(f"Read {Path(file_path).name}")
                                context['stuck_counter'] = 0  # Made progress
                                
                                # Store file content in context for Claude to use
                                if 'file_contents' not in context:
                                    context['file_contents'] = {}
                                context['file_contents'][file_path] = content[:5000]  # Keep summary in context
                                
                                logger.info(f"Read file: {file_path} ({len(content)} chars)")
                                await tracker.send_update(f"📖 Read {Path(file_path).name} ({len(content)} chars)")
                            else:
                                context['errors'].append(f"File not found: {file_path}")
                                context['stuck_counter'] += 1
                                await tracker.send_update(f"❌ File not found: {file_path}")
                        except Exception as e:
                            logger.error(f"Error reading file {file_path}: {e}")
                            context['errors'].append(f"Read error: {str(e)[:100]}")
                            context['stuck_counter'] += 1
                        continue
                    
                    # HANDLE LIST FILES (for discovery)
                    elif action == 'list_files':
                        directory = decision.get('directory', project_path)
                        
                        from pathlib import Path
                        if not Path(directory).is_absolute():
                            directory = str(Path(project_path) / directory)
                        
                        try:
                            dir_path = Path(directory).expanduser()
                            if dir_path.exists() and dir_path.is_dir():
                                files = list(dir_path.iterdir())
                                file_list = []
                                for f in sorted(files)[:50]:  # Limit to 50 items
                                    prefix = "📁" if f.is_dir() else "📄"
                                    file_list.append(f"{prefix} {f.name}")
                                
                                context['completed_actions'].append(f"Listed {directory}")
                                context['stuck_counter'] = 0
                                
                                logger.info(f"Listed directory: {directory} ({len(files)} items)")
                                await tracker.send_update(f"📂 Listed {Path(directory).name} ({len(files)} items)")
                            else:
                                context['errors'].append(f"Directory not found: {directory}")
                                context['stuck_counter'] += 1
                        except Exception as e:
                            logger.error(f"Error listing directory {directory}: {e}")
                            context['errors'].append(f"List error: {str(e)[:100]}")
                            context['stuck_counter'] += 1
                        continue
                    
                    # EXISTING ACTIONS
                    elif action == 'edit_file':
                        # Edit or create a file
                        file_path = decision.get('file_path')
                        changes = decision.get('changes')
                        
                        if not file_path:
                            logger.error("No file_path provided in edit_file action")
                            context['errors'].append("Missing file_path")
                            context['stuck_counter'] += 1
                            continue
                        
                        # Convert to absolute path if relative
                        from pathlib import Path
                        if not Path(file_path).is_absolute():
                            file_path = str(Path(project_path) / file_path)
                        
                        # Normalize the path for comparison
                        normalized_path = str(Path(file_path).resolve())
                        
                        # Check for repetitive file edits (loop detection)
                        if normalized_path in context['recent_file_edits'][-2:]:
                            logger.warning(f"Detected repeated edit of same file: {file_path}")
                            await tracker.send_update(
                                f"⚠️ Already edited {file_path} recently!\n"
                                f"Please create or edit DIFFERENT files to make progress.\n"
                                f"Recent files: {[Path(p).name for p in context['recent_file_edits'][-3:]]}"
                            )
                            context['errors'].append(f"Repeated edit: {file_path}")
                            context['stuck_counter'] += 1
                            continue
                        
                        # Check if file exists - use create or edit accordingly
                        file_exists = Path(file_path).expanduser().exists()
                        
                        if file_exists:
                            await tracker.send_update(f"✏️ Editing {Path(file_path).name}")
                            result = await programmer._edit_file(
                                file_path=file_path,
                                changes_description=changes
                            )
                            action_verb = "Edited"
                        else:
                            await tracker.send_update(f"📝 Creating {file_path}")
                            result = await programmer._create_file(
                                file_path=file_path,
                                description=changes
                            )
                            action_verb = "Created"
                        
                        # Check if operation succeeded
                        if not result:
                            logger.error(f"File operation returned empty result")
                            await tracker.send_update(f"❌ Operation failed - no result")
                            context['errors'].append("Empty result from file operation")
                            context['stuck_counter'] += 1
                        elif "does not exist" in result or "error" in result.lower() or "failed" in result.lower():
                            logger.error(f"File operation failed: {result}")
                            await tracker.send_update(f"❌ Failed: {result[:200]}")
                            context['errors'].append(result[:200])
                            context['stuck_counter'] += 1
                        else:
                            logger.info(f"Successfully {action_verb.lower()} {file_path}")
                            context['completed_actions'].append(f"{action_verb} {Path(file_path).name}")
                            context['recent_file_edits'].append(normalized_path)  # Track this edit
                            context['stuck_counter'] = 0  # Reset - made progress!
                            await tracker.send_update(f"✅ {action_verb} {Path(file_path).name}")
                            
                            # AUTO-COMMIT in EXECUTE phase
                            if current_phase == 'EXECUTE' and phase_config.get('git_policy') == 'commit_per_step':
                                commit_msg = f"[{current_phase}] {decision.get('reason', 'Update')[:50]}"
                                git_result = await programmer._git_commit_smart(
                                    project_path=project_path,
                                    message=commit_msg,
                                    files=[file_path]
                                )
                                if "✓" in git_result:
                                    await tracker.send_update(f"📝 {git_result}")
                                    context['git_commits'].append(commit_msg)
                    
                    elif action == 'run_command':
                        # Run terminal command
                        command = decision.get('command')
                        reason = decision.get('reason', 'execute command')
                        
                        # Check for repetitive commands (loop detection)
                        if command in context['recent_commands'][-3:]:
                            logger.warning(f"Detected repeated command: {command}")
                            await tracker.send_update(
                                f"⚠️ Skipping repeated command: {command}\nPlease make progress by editing or creating files."
                            )
                            context['errors'].append(f"Repeated command: {command}")
                            context['stuck_counter'] += 1
                            continue
                        
                        # Track this command
                        context['recent_commands'].append(command)
                        
                        # Check if destructive
                        if is_destructive_command(command):
                            # PAUSE and request confirmation via Telegram
                            code = await request_confirmation_dual_channel(
                                task_id=task_id,
                                command=command,
                                reason=get_command_reason(command),
                                session_manager=session_manager
                            )
                            
                            if not code or not verify_confirmation_code(code):
                                await tracker.send_update(
                                    "❌ Invalid or missing confirmation code",
                                    phase="error"
                                )
                                break
                        
                        # Execute command
                        await tracker.send_update(
                            f"⚙️ Executing: `{command}`\nReason: {reason}",
                            command=command
                        )
                        
                        import subprocess
                        result = subprocess.run(
                            command,
                            shell=True,
                            cwd=project_path,
                            capture_output=True,
                            text=True,
                            timeout=120
                        )
                        
                        if result.returncode == 0:
                            await tracker.send_update(
                                f"✅ Command succeeded\n```\n{result.stdout[:200]}\n```"
                            )
                            context['completed_actions'].append(f"Ran: {command}")
                            
                            # Only reset stuck counter for productive commands (not just cat/ls)
                            if not any(cmd in command.lower() for cmd in ['cat', 'ls', 'find', 'grep', 'echo']):
                                context['stuck_counter'] = 0  # Made progress!
                            else:
                                context['stuck_counter'] += 1  # Just reading files
                        else:
                            await tracker.send_update(
                                f"❌ Command failed (exit {result.returncode})"
                            )
                            context['errors'].append(result.stderr[:500])
                            context['stuck_counter'] += 1
                    
                    elif action == 'run_tests':
                        # Run tests
                        await tracker.send_update("🧪 Running tests...", phase="testing")
                        
                        # Try common test commands
                        test_commands = ['npm test', 'pytest', 'python -m pytest', 'python -m unittest']
                        
                        for test_cmd in test_commands:
                            try:
                                result = subprocess.run(
                                    test_cmd,
                                    shell=True,
                                    cwd=project_path,
                                    capture_output=True,
                                    text=True,
                                    timeout=60
                                )
                                
                                if result.returncode == 0:
                                    await tracker.send_update(
                                        "✅ All tests passed!",
                                        phase="tests_passed"
                                    )
                                    break
                                else:
                                    context['errors'].append(result.stderr[:500])
                            except:
                                continue
                    
                    elif action == 'complete':
                        # Task complete
                        await tracker.send_update(
                            f"🎉 Task complete!\n{decision.get('reason', 'Goal achieved')}",
                            phase="complete"
                        )
                        context['stuck_counter'] = 0  # Success!
                        current_phase = 'COMPLETE'
                        break
                    
                    else:
                        logger.warning(f"Unknown action: {action}")
                        context['stuck_counter'] += 1
                    
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error in iteration {total_iterations}: {e}")
                    logger.error(f"Claude response was: {decision_text[:500]}")
                    context['errors'].append(f"JSON parse error: {e}")
                    context['stuck_counter'] += 1
                    await tracker.send_update(f"⚠️ Failed to parse AI response. Retrying...")
                except Exception as e:
                    logger.error(f"Error in iteration {total_iterations}: {e}")
                    context['errors'].append(str(e))
                    context['stuck_counter'] += 1
                    await tracker.send_update(f"⚠️ Error: {str(e)[:200]}")
            
            # End of phase iteration loop
            
            # SMART ITERATION CHECKPOINT - Every 50 iterations
            if total_iterations >= 50 and total_iterations % 50 == 0:
                await tracker.send_update(
                    f"📊 Checkpoint at iteration {total_iterations}...\nVerifying progress...",
                    phase="checkpoint"
                )
                
                # Run a checkpoint verification
                checkpoint_result = await _run_checkpoint_verification(
                    claude_client=claude_client,
                    goal=goal,
                    context=context,
                    tracker=tracker
                )
                
                if checkpoint_result['status'] == 'complete':
                    # All done
                    await tracker.send_update(
                        "✅ Checkpoint: Task appears complete. Moving to final verification.",
                        phase="checkpoint_complete"
                    )
                    current_phase = 'VERIFY'
                    
                elif checkpoint_result['status'] == 'stuck':
                    # Attempt self-healing
                    await tracker.send_update(
                        f"⚠️ Checkpoint: Task appears stuck.\n"
                        f"Reason: {checkpoint_result.get('reason', 'Unknown')}\n"
                        f"Attempting recovery...",
                        phase="checkpoint_stuck"
                    )
                    
                    # Try to recover
                    recovery_action = checkpoint_result.get('recovery_action', 'continue')
                    if recovery_action == 'reset':
                        # Reset to previous working state
                        context['errors'] = context['errors'][-3:]  # Keep last 3 errors
                        context['stuck_counter'] = 0
                    elif recovery_action == 'skip':
                        # Skip to next phase
                        current_phase = phase_manager.get_next_phase(current_phase)
                    # 'continue' - just keep going
                    
                elif checkpoint_result['status'] == 'in_progress':
                    # Still making progress, extend iterations
                    max_iterations += 25
                    await tracker.send_update(
                        f"📈 Checkpoint: Good progress! Extending by 25 iterations.\n"
                        f"New max: {max_iterations}",
                        phase="checkpoint_continue"
                    )
                else:
                    # Uncertain, continue cautiously
                    max_iterations += 10
                    await tracker.send_update(
                        f"🔄 Checkpoint: Status unclear. Extending by 10 iterations.",
                        phase="checkpoint_uncertain"
                    )
            
            # Handle VERIFY phase auto-testing
            if current_phase == 'VERIFY':
                await tracker.send_update("🧪 Running verification tests...", phase="testing")
                verification = await verifier.run_verification()
                
                if verification['all_passed']:
                    await tracker.send_update("✅ All tests passed!")
                    current_phase = 'PUBLISH'
                else:
                    await tracker.send_update(
                        f"❌ Tests failed:\n{verification['summary'][:300]}"
                    )
                    context['errors'].append(f"Tests failed: {verification['summary']}")
            
            # Check if we should exit main loop
            if current_phase == 'COMPLETE':
                break
        
        # Final update
        if current_phase == 'COMPLETE':
            await tracker.send_update("✅ All phases complete!", phase="complete")
        elif total_iterations >= max_iterations:
            await tracker.send_update(
                f"⚠️ Reached max iterations ({max_iterations})",
                phase="max_iterations"
            )
        
    except Exception as e:
        logger.error(f"Fatal error in task {task_id}: {e}")
        await tracker.send_update(
            f"❌ Fatal error: {str(e)}",
            phase="error"
        )
        raise
    
    finally:
        logger.info(f"Completed task {task_id}")


async def run_deep_research(
    task_id: str,
    goal: str,
    session_id: str,
    max_iterations: int = 5,
    output_format: str = "report"
):
    """Run a deep research task in the background.
    
    This is called by RQ when a research task is queued.
    Uses the DeepResearchAgent from sub_agents_tars.py.
    
    Args:
        task_id: Unique task identifier
        goal: Research topic/question
        session_id: TARS session that started this
        max_iterations: Max research iterations
        output_format: Output format (report, summary, bullet_points)
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from sub_agents_tars import DeepResearchAgent
    
    logger.info(f"Starting deep research task {task_id}: {goal}")
    
    # Create tracker for updates (using TaskProgressTracker)
    tracker = TaskProgressTracker(task_id, discord_updates=True)
    
    try:
        await tracker.send_update(
            f"🔬 Starting Deep Research\n**Topic:** {goal}",
            phase="research_start"
        )
        
        # Initialize research agent (db and session_manager are optional for background)
        research_agent = DeepResearchAgent(db=None, session_manager=None)
        
        # Run research synchronously (IMPORTANT: _run_in_foreground=True prevents re-queuing!)
        result = await research_agent.execute({
            "action": "research",
            "goal": goal,  # Fixed: was "research_goal"
            "output_format": output_format,
            "max_iterations": max_iterations,
            "_run_in_foreground": True,  # Run synchronously, don't re-queue!
            "_session_id": session_id
        })
        
        # Send completion update to Discord
        await tracker.send_update(
            f"✅ Research Complete\n\n**Summary:**\n{result[:1500]}...",
            phase="research_complete"
        )
        
        # Also send via Gmail (research agent already does this, but ensure it happens)
        await tracker.send_research_to_gmail(goal, result)
        
        logger.info(f"Completed research task {task_id}")
        return result
        
    except Exception as e:
        logger.error(f"Research task {task_id} failed: {e}")
        await tracker.send_update(
            f"❌ Research failed: {str(e)}",
            phase="research_error"
        )
        raise
