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


class TaskProgressTracker:
    """Tracks and reports progress of background tasks."""
    
    def __init__(self, task_id: str, discord_updates: bool = True):
        self.task_id = task_id
        self.discord_updates = discord_updates
        self.phase = "init"
        self.iteration = 0
    
    async def send_update(self, message: str, phase: Optional[str] = None, command: Optional[str] = None):
        """Send progress update to Discord.
        
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
        
        # Send to Discord
        if self.discord_updates:
            await send_discord_update({
                'task_id': self.task_id,
                'type': 'progress' if not phase else 'phase_complete',
                'message': message,
                'phase': phase,
                'command': command
            })
        
        logger.info(f"Task {self.task_id}: {message}")


async def send_discord_update(data: dict):
    """Send update to Discord via KIPP (N8N webhook).
    
    Args:
        data: {
            'task_id': str,
            'type': str (task_started|progress|phase_complete|confirmation_request|task_complete|error),
            'message': str,
            'command': str (optional),
            'phase': str (optional),
            'code_request': bool (optional)
        }
    """
    webhook_url = Config.N8N_WEBHOOK_URL
    
    if not webhook_url:
        logger.warning("N8N webhook not configured for Discord updates")
        return
    
    # Format payload for KIPP/N8N to route to Discord
    payload = {
        "target": "discord",  # Tell KIPP to route to Discord
        "source": "background_task",  # Identify as background task update
        "task_id": data.get('task_id'),
        "type": data.get('type'),
        "message": data.get('message'),
        "timestamp": datetime.now().isoformat()
    }
    
    if 'command' in data:
        payload['command'] = data['command']
    if 'phase' in data:
        payload['phase'] = data['phase']
    if 'code_request' in data:
        payload['awaiting_confirmation'] = True
    if 'goal' in data:
        payload['goal'] = data['goal']
    if 'project' in data:
        payload['project'] = data['project']
    if 'reason' in data:
        payload['reason'] = data['reason']
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    logger.info(f"Sent Discord update via KIPP: {data.get('message', '')[:50]}")
                else:
                    logger.warning(f"KIPP webhook returned {response.status}")
    except Exception as e:
        logger.error(f"Failed to send Discord update via KIPP: {e}")


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
    discord_message = (
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
    
    # 1. Send Discord notification
    await send_discord_update({
        'task_id': task_id,
        'type': 'confirmation_request',
        'command': command,
        'reason': reason,
        'message': discord_message,
        'code_request': True
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


async def run_autonomous_programming(
    task_id: str,
    goal: str,
    project_path: str,
    session_id: str,
    max_iterations: int = 50,
    max_minutes: int = 15
):
    """Run an autonomous programming session in background.
    
    This is the main worker function called by RQ. It:
    1. Uses Claude Sonnet 4.5 to plan and execute coding tasks
    2. Iterates through code/test/fix loops
    3. Sends progress updates to Discord
    4. Requests confirmation for destructive commands
    5. Runs until task complete or timeout
    
    Args:
        task_id: Unique task ID
        goal: What to build/fix
        project_path: Where to work
        session_id: TARS session that started this task
        max_iterations: Maximum number of iterations
        max_minutes: Maximum runtime in minutes
    """
    # CRITICAL: Set fork safety FIRST, before any imports that might use Objective-C
    # This is the first thing the child process should do
    import os
    os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
    
    # NOW import the modules (after fork safety is set)
    from core.session_manager import SessionManager
    from core.database import Database
    from sub_agents_tars import ProgrammerAgent
    
    logger.info(f"Starting autonomous programming task {task_id}: {goal}")
    
    # Initialize
    tracker = TaskProgressTracker(task_id, discord_updates=True)
    start_time = time.time()
    
    # Send initial update
    await tracker.send_update(
        f"🚀 Started autonomous coding\n**Goal:** {goal}\n**Project:** {project_path}",
        phase="started"
    )
    
    try:
        # Initialize dependencies AFTER setting fork safety
        # Note: SessionManager needs to be accessible for confirmation requests
        # We get it through a global reference or import
        db = Database()
        
        # Import here to avoid circular dependency at module level
        from core.session_manager import SessionManager
        
        # Try to get existing SessionManager instance
        # For now, we'll pass None and handle confirmation without voice
        # TODO: Implement proper SessionManager singleton pattern
        session_manager = None
        
        programmer = ProgrammerAgent(db=db, github_handler=None, session_manager=session_manager)
        
        # Initialize Claude client
        claude_client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        
        # Build initial context
        context = {
            "goal": goal,
            "project_path": project_path,
            "iteration": 0,
            "errors": [],
            "completed_actions": [],
            "recent_commands": [],  # Track recent commands to detect loops
            "recent_file_edits": [],  # Track recent file edits to detect loops
            "stuck_counter": 0  # Count iterations without progress
        }
        
        await tracker.send_update("📋 Planning approach...", phase="planning")
        
        for iteration in range(max_iterations):
            # Check if stuck (no progress for 5 iterations)
            if context['stuck_counter'] >= 5:
                await tracker.send_update(
                    f"⚠️  No progress for 5 iterations. Task may be stuck.\n"
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
            context["iteration"] = iteration
            
            # Ask Claude what to do next
            try:
                response = claude_client.messages.create(
                    model=Config.CLAUDE_COMPLEX_MODEL,
                    max_tokens=4000,
                    temperature=0.7,
                    system=(
                        f"You are an expert programmer working autonomously. "
                        f"Goal: {goal}\n"
                        f"Project: {project_path}\n"
                        f"Iteration: {iteration}/{max_iterations}\n"
                        f"Previous actions: {context['completed_actions'][-5:]}\n"
                        f"Recent commands: {context['recent_commands'][-3:]}\n"
                        f"Recent file edits: {context['recent_file_edits'][-3:]}\n"
                        f"Recent errors: {context['errors'][-3:]}\n\n"
                        f"IMPORTANT: Don't repeat commands or file edits!\n"
                        f"- Already worked on these files: {context['recent_file_edits'][-3:]}\n"
                        f"- Work on DIFFERENT files to make progress\n"
                        f"- Use 'edit_file' for both creating NEW files and editing existing ones\n"
                        f"- For a Next.js app, you need: package.json, tsconfig.json, next.config.js, "
                        f"pages/index.tsx, components/, styles/, etc.\n\n"
                        f"Decide the next action. Respond with JSON:\n"
                        f'{{"action": "edit_file|run_command|run_tests|complete", '
                        f'"file_path": "path/to/file", "changes": "what to create/change", "command": "shell command", '
                        f'"reason": "why this action"}}\n\n'
                        f"NOTE: edit_file works for BOTH creating new files and editing existing ones."
                    ),
                    messages=[{
                        "role": "user",
                        "content": f"What should I do next to achieve: {goal}?"
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
                
                if action == 'edit_file':
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
                            f"⚠️  Already edited {file_path} recently!\n"
                            f"Please create or edit DIFFERENT files to make progress.\n"
                            f"Recent files: {[Path(p).name for p in context['recent_file_edits'][-3:]]}"
                        )
                        context['errors'].append(f"Repeated edit: {file_path}")
                        context['stuck_counter'] += 1
                        continue
                    
                    # Check if file exists - use create or edit accordingly
                    file_exists = Path(file_path).expanduser().exists()
                    
                    if file_exists:
                        await tracker.send_update(f"✏️  Editing {Path(file_path).name}")
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
                    
                elif action == 'run_command':
                    # Run terminal command
                    command = decision.get('command')
                    reason = decision.get('reason', 'execute command')
                    
                    # Check for repetitive commands (loop detection)
                    if command in context['recent_commands'][-3:]:
                        logger.warning(f"Detected repeated command: {command}")
                        await tracker.send_update(
                            f"⚠️  Skipping repeated command: {command}\nPlease make progress by editing or creating files."
                        )
                        context['errors'].append(f"Repeated command: {command}")
                        context['stuck_counter'] += 1
                        continue
                    
                    # Track this command
                    context['recent_commands'].append(command)
                    
                    # Check if destructive
                    if is_destructive_command(command):
                        # PAUSE and request confirmation via BOTH Discord and voice
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
                        f"⚙️  Executing: `{command}`\nReason: {reason}",
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
                    break
                
                else:
                    logger.warning(f"Unknown action: {action}")
                    context['stuck_counter'] += 1
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error in iteration {iteration}: {e}")
                logger.error(f"Claude response was: {decision_text[:500]}")
                context['errors'].append(f"JSON parse error: {e}")
                context['stuck_counter'] += 1
                await tracker.send_update(f"⚠️  Failed to parse AI response. Retrying...")
            except Exception as e:
                logger.error(f"Error in iteration {iteration}: {e}")
                context['errors'].append(str(e))
                context['stuck_counter'] += 1
                await tracker.send_update(f"⚠️  Error: {str(e)[:200]}")
        
        # Final update
        if iteration >= max_iterations - 1:
            await tracker.send_update(
                f"⚠️  Reached max iterations ({max_iterations})",
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
