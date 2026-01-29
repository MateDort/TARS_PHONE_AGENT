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
from core.event_bus import event_bus
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
            "to": "matedort1@gmail.com",
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


from core.event_bus import event_bus

async def send_programming_log(data: dict):
    """Send PROGRAMMING LOG to Discord via EventBus.
    
    Publishes to 'log.discord' channel which ManagerAgent/DiscordClient listens to.
    
    Args:
        data: {
            'task_id': str,
            'type': str (task_started|progress|phase_complete|task_complete|error),
            'message': str,
            'command': str (optional),
            'phase': str (optional)
        }
    """
    # Publish to Redis channel 'log.discord'
    # The DiscordClient in the main process will pick this up
    await event_bus.publish('log.discord', data)
    
    # Also log locally
    logger.debug(f"Published log to Discord: {data.get('message', '')[:50]}")


async def send_log_update(data: dict):
    """Send LOG/STATUS update via EventBus or KIPP.
    
    Uses Config.LOG_CHANNEL to determine where logs go.
    
    Args:
        data: {
            'task_id': str,
            'type': str,
            'message': str,
            'command': str (optional),
            'phase': str (optional)
        }
    """
    log_channel = Config.LOG_CHANNEL.lower()
    
    if log_channel == 'discord':
        # Use the efficient EventBus pathway for Discord
        await event_bus.publish('log.discord', data)
        # Also log locally
        logger.info(f"Published log to Discord via EventBus: {data.get('message', '')[:50]}")
    else:
        # For Telegram logging, we still fall back to KIPP for now
        # OR use notification.send if TelegramClient is listening?
        # TelegramClient doesn't listen to generic logs, so we'll use notification.send
        # But notification.send only takes 'message'.
        # We'll construct a formatted message.
        
        message = data.get('message', '')
        if data.get('command'):
            message += f"\nCommand: {data.get('command')}"
            
        await event_bus.publish('notification.send', {
            'platform': 'telegram', # Routing hint
            'message': f"📝 Log ({data.get('task_id')}): {message}"
        })


# Alias for backward compatibility
send_discord_update = send_log_update


async def send_confirmation_request(data: dict):
    """Send CONFIRMATION REQUEST via EventBus (Telegram)."""
    # Use configured confirmation channel (default: telegram)
    confirm_channel = Config.CONFIRMATION_CHANNEL.lower()
    
    message_text = data.get('message', '')
    if data.get('command'):
        message_text += f"\nCommand: {data.get('command')}"
    if data.get('reason'):
        message_text += f"\nReason: {data.get('reason')}"
        
    await event_bus.publish('notification.send', {
        'platform': confirm_channel,
        'channel_id': Config.TELEGRAM_MATE_CHAT_ID, # Ensure it goes to owner
        'message': message_text
    })

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


# NOTE: run_autonomous_programming was removed - TARS now uses Claude Code CLI
# for programming tasks via use_claude_code function in ProgrammerAgent


async def _placeholder_removed_autonomous_programming():
    """This function was removed. Use 'use_claude_code' instead."""
    pass


# Programming tasks should now be handled via:
#   - use_claude_code: For complex programming using Claude Code CLI
#   - edit_code: For simple file edits
#   - execute_terminal: For running commands


async def run_autonomous_programming(
    task_id: str,
    goal: str,
    project_path: str,
    session_id: str,
    max_iterations: int = 50,
    max_minutes: int = 15
):
    """DEPRECATED: This function has been removed.
    
    Use 'use_claude_code' instead for programming tasks.
    This stub exists only for backward compatibility with any lingering queue jobs.
    """
    tracker = TaskProgressTracker(task_id, discord_updates=True)
    await tracker.send_update(
        "⚠️ The autonomous coding system has been deprecated.\n"
        "Please use 'use_claude_code' for programming tasks instead.",
        phase="deprecated"
    )
    return {"status": "deprecated", "message": "Use 'use_claude_code' instead"}


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


async def run_claude_code(
    task_id: str,
    goal: str,
    project_path: str,
    session_id: str,
    timeout_minutes: int = 10
):
    """Run a Claude Code task in the background.
    
    This is called by RQ when a programming task is queued.
    Uses Claude Code CLI for autonomous programming.
    
    Args:
        task_id: Unique task identifier
        goal: Programming task description
        project_path: Project directory to work in
        session_id: TARS session that started this
        timeout_minutes: Timeout for the task
    """
    import shutil
    
    logger.info(f"Starting Claude Code task {task_id}: {goal[:50]}...")
    
    # Create tracker for updates
    tracker = TaskProgressTracker(task_id, discord_updates=True)
    
    try:
        # Notify Telegram of start
        await event_bus.publish('notification.send', {
            'platform': 'telegram',
            'channel_id': Config.TELEGRAM_MATE_CHAT_ID,
            'message': f"🤖 *Started Programming Task*\nGoal: {goal[:100]}...\nProject: `{project_path}`"
        })

        await tracker.send_update(
            f"🤖 Starting Claude Code Session\n**Project:** {project_path}\n**Goal:** {goal[:200]}",
            phase="claude_start"
        )
        
        # Find Claude Code CLI
        claude_code_path = shutil.which("claude")
        if not claude_code_path:
            home_path = Path.home() / ".npm-global" / "bin" / "claude"
            if home_path.exists():
                claude_code_path = str(home_path)
            else:
                raise RuntimeError("Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code")
        
        # Build command
        cmd = [
            claude_code_path,
            "--print",  # Non-interactive mode
            "--output-format", "text",
            goal
        ]
        
        logger.info(f"Running Claude Code in {project_path}: {' '.join(cmd)}")
        await tracker.send_update(f"🔧 Running Claude Code CLI...", phase="claude_running")
        
        # Run Claude Code
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_minutes * 60
            )
            
            if process.returncode == 0:
                output = stdout.decode().strip()
                if len(output) > 2000:
                    output = output[:2000] + "\n...[truncated]"
                
                await tracker.send_update(
                    f"✅ Claude Code Complete\n\n**Result:**\n```\n{output[:1500]}\n```",
                    phase="claude_complete"
                )
                
                # Notify Telegram of success
                await event_bus.publish('notification.send', {
                    'platform': 'telegram',
                    'channel_id': Config.TELEGRAM_MATE_CHAT_ID,
                    'message': f"✅ *Programming Task Complete*\n\nResult:\n{output[:500]}..."
                })
                
                logger.info(f"Claude Code task {task_id} completed successfully")
                return {"status": "completed", "output": output}
            else:
                error = stderr.decode().strip() or stdout.decode().strip()
                await tracker.send_update(
                    f"❌ Claude Code Failed\n\n**Error:**\n```\n{error[:1000]}\n```",
                    phase="claude_error"
                )
                
                # Notify Telegram of failure
                await event_bus.publish('notification.send', {
                    'platform': 'telegram',
                    'channel_id': Config.TELEGRAM_MATE_CHAT_ID,
                    'message': f"❌ *Programming Task Failed*\n\nError:\n{error[:500]}"
                })
                
                logger.error(f"Claude Code task {task_id} failed: {error[:200]}")
                return {"status": "failed", "error": error}
                
        except asyncio.TimeoutError:
            process.kill()
            await tracker.send_update(
                f"⏱️ Claude Code timed out after {timeout_minutes} minutes",
                phase="claude_timeout"
            )
            
            logger.warning(f"Claude Code task {task_id} timed out")
            return {"status": "timeout", "error": f"Timed out after {timeout_minutes} minutes"}
            
    except Exception as e:
        logger.error(f"Claude Code task {task_id} failed: {e}")
        await tracker.send_update(
            f"❌ Claude Code failed: {str(e)}",
            phase="claude_error"
        )
        raise


async def run_computer_control(
    task_id: str,
    goal: str,
    session_id: str,
    timeout_minutes: int = 15
):
    """Run a Computer Control task in the background.
    
    This is called by RQ when a computer control task is queued.
    Uses the DockerSandbox for safe execution.
    
    Args:
        task_id: Unique task identifier
        goal: Task description
        session_id: TARS session that started this
        timeout_minutes: Timeout for the task
    """
    from agents.programming.docker_sandbox import DockerSandbox
    
    logger.info(f"Starting Computer Control task {task_id}: {goal[:50]}...")
    
    # Create tracker for updates
    tracker = TaskProgressTracker(task_id, discord_updates=True)
    
    try:
        await tracker.send_update(
            f"🖥️ Starting Virtual Computer\\n**Goal:** {goal[:200]}",
            phase="docker_start"
        )
        
        # Initialize Sandbox
        sandbox = DockerSandbox()
        started = await sandbox.start()
        
        if not started:
            raise RuntimeError("Failed to start Docker Sandbox")
            
        await tracker.send_update("Sandbox Started. Executing task...", phase="docker_running")
        
        # Execute Code (This is a simplified version - normally we'd loop with LLM)
        # For now, we'll just run a simple python script that prints the goal to prove it works
        # In the future, we will integrate the full ComputerControlAgent loop here
        
        code = f"""
import sys
print("Virtual Computer Active.")
print("Processing Goal: {goal}")
# Mock work
import time
time.sleep(2)
print("Work Complete.")
"""
        result = await sandbox.execute_code(code)
        
        await sandbox.stop()
        
        if result.get("exit_code") == 0:
            output = result.get("stdout", "")
            await tracker.send_update(
                f"✅ Computer Control Complete\\n\\n**Output:**\\n```\\n{output}\\n```",
                phase="docker_complete"
            )
            logger.info(f"Computer Control task {task_id} completed successfully")
            return {"status": "completed", "output": output}
        else:
            error = result.get("stderr", "")
            await tracker.send_update(
                f"❌ Computer Control Failed\\n\\n**Error:**\\n```\\n{error}\\n```",
                phase="docker_error"
            )
            return {"status": "failed", "error": error}
            
    except Exception as e:
        logger.error(f"Computer Control task {task_id} failed: {e}")
        await tracker.send_update(
            f"❌ Computer Control failed: {str(e)}",
            phase="docker_error"
        )
        raise
