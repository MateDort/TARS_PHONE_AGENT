"""User interaction utilities for autonomous programming tasks."""
import asyncio
import logging
from typing import List, Optional
from redis import Redis

from core.config import Config

logger = logging.getLogger(__name__)


async def ask_user_question(
    task_id: str,
    question: str,
    options: List[str] = None,
    timeout_seconds: int = 300
) -> str:
    """Pause execution and ask user a question via Telegram.
    
    This is critical for Plan Mode where the AI needs clarification before
    proceeding with implementation. Telegram is used for questions that need
    a response, as it's easier to reply.
    
    Args:
        task_id: Background task ID
        question: Question to ask the user
        options: Optional list of predefined answers
        timeout_seconds: How long to wait for response (default: 5 minutes)
        
    Returns:
        User's answer, or "timeout" if no response
    """
    from core.background_worker import send_telegram_confirmation
    
    logger.info(f"Task {task_id} asking user: {question}")
    
    # Format options nicely if provided
    options_text = ""
    if options:
        options_text = "\n\nOptions:\n" + "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(options))
    
    # Send to Telegram via KIPP webhook (questions go to Telegram for easy reply)
    await send_telegram_confirmation({
        'task_id': task_id,
        'type': 'user_question',
        'question': question + options_text,
        'options': options,
        'message': f"❓ **Question from TARS (Task #{task_id})**\n\n{question}{options_text}\n\n_Reply to this message with your answer_"
    })
    
    # Poll Redis for answer
    try:
        redis_client = Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=True
        )
        
        answer_key = f"task:{task_id}:user_answer"
        
        # Poll every 2 seconds
        for attempt in range(timeout_seconds // 2):
            answer = redis_client.get(answer_key)
            if answer:
                # Clear the key
                redis_client.delete(answer_key)
                
                logger.info(f"Received answer for task {task_id}: {answer}")
                
                # Send acknowledgment
                await send_discord_update({
                    'task_id': task_id,
                    'type': 'progress',
                    'message': f"✅ Received your answer: {answer}\n\nContinuing with task..."
                })
                
                return answer
            
            await asyncio.sleep(2)
        
        # Timeout
        logger.warning(f"User question timed out for task {task_id}")
        await send_discord_update({
            'task_id': task_id,
            'type': 'error',
            'message': f"⏱️ Question timed out after {timeout_seconds}s. Continuing with default behavior..."
        })
        
        return "timeout"
        
    except Exception as e:
        logger.error(f"Error asking user question: {e}")
        return "error"


async def request_plan_approval(task_id: str, plan_content: str, timeout_seconds: int = 600) -> bool:
    """Request user approval for the generated plan before execution.
    
    Sent to Telegram for easy reply interaction.
    
    Args:
        task_id: Background task ID
        plan_content: The plan to approve
        timeout_seconds: How long to wait (default: 10 minutes)
        
    Returns:
        True if approved, False if rejected
    """
    from core.background_worker import send_telegram_confirmation, send_discord_update
    
    logger.info(f"Task {task_id} requesting plan approval")
    
    # Send plan to Telegram for approval (confirmations go to Telegram for easy reply)
    await send_telegram_confirmation({
        'task_id': task_id,
        'type': 'plan_approval_request',
        'plan': plan_content,
        'message': f"📋 **Plan Ready for Review (Task #{task_id})**\n\n{plan_content[:500]}...\n\n"
                   f"_Reply 'approve' or 'reject'_"
    })
    
    # Also log to Discord that plan is awaiting approval
    await send_discord_update({
        'task_id': task_id,
        'type': 'progress',
        'message': f"📋 Plan generated for Task #{task_id}. Awaiting approval via Telegram..."
    })
    
    try:
        redis_client = Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=True
        )
        
        approval_key = f"task:{task_id}:plan_approval"
        
        # Poll every 3 seconds
        for attempt in range(timeout_seconds // 3):
            response = redis_client.get(approval_key)
            if response:
                redis_client.delete(approval_key)
                
                approved = response.lower() in ['approve', 'approved', 'yes', 'y', 'ok']
                
                logger.info(f"Plan approval for task {task_id}: {approved}")
                
                if approved:
                    await send_discord_update({
                        'task_id': task_id,
                        'type': 'progress',
                        'message': "✅ Plan approved! Starting execution phase..."
                    })
                else:
                    await send_discord_update({
                        'task_id': task_id,
                        'type': 'progress',
                        'message': "❌ Plan rejected. Revising plan..."
                    })
                
                return approved
            
            await asyncio.sleep(3)
        
        # Timeout - default to approval for autonomous operation
        logger.warning(f"Plan approval timed out for task {task_id}, defaulting to approval")
        await send_discord_update({
            'task_id': task_id,
            'type': 'progress',
            'message': f"⏱️ Plan approval timed out. Proceeding with execution..."
        })
        
        return True  # Default to approval
        
    except Exception as e:
        logger.error(f"Error requesting plan approval: {e}")
        return True  # Default to approval on error


async def send_phase_completion_notification(
    task_id: str,
    phase: str,
    summary: str,
    next_phase: str
):
    """Notify user of phase completion.
    
    Args:
        task_id: Background task ID
        phase: Completed phase name
        summary: Phase summary
        next_phase: Next phase name
    """
    from core.background_worker import send_discord_update
    
    phase_emoji = {
        'DISCOVER': '🔍',
        'PLAN': '📋',
        'EXECUTE': '⚙️',
        'VERIFY': '✅',
        'PUBLISH': '🚀'
    }
    
    emoji = phase_emoji.get(phase, '✓')
    
    await send_discord_update({
        'task_id': task_id,
        'type': 'phase_complete',
        'phase': phase,
        'message': f"{emoji} **{phase} Phase Complete**\n\n{summary}\n\n➡️ Moving to {next_phase} phase..."
    })
