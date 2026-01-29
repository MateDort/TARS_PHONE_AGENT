"""Background task manager using Redis Queue."""
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from redis import Redis
from rq import Queue
from rq.job import Job

from core.config import Config

logger = logging.getLogger(__name__)


class TaskType:
    """Types of background tasks."""
    PROGRAMMING = "programming"
    RESEARCH = "research"
    CALL = "call"


class BackgroundTaskManager:
    """Manages background tasks using Redis Queue.
    
    Supports up to MAX_BACKGROUND_TASKS concurrent tasks across:
    - Programming tasks (code editing, debugging)
    - Research tasks (deep research with Gemini/Claude)
    - Call tasks (outbound phone calls)
    """
    
    def __init__(self):
        """Initialize task manager with Redis connection."""
        try:
            self.redis_conn = Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                decode_responses=False  # We'll decode manually
            )
            
            # Create queues for different task types
            self.queues = {
                TaskType.PROGRAMMING: Queue('tars_programming', connection=self.redis_conn),
                TaskType.RESEARCH: Queue('tars_research', connection=self.redis_conn),
                TaskType.CALL: Queue('tars_calls', connection=self.redis_conn),
            }
            self.queue = self.queues[TaskType.PROGRAMMING]  # Default queue for backward compatibility
            
            self.tasks: Dict[str, Dict[str, Any]] = {}
            self.max_concurrent = Config.MAX_BACKGROUND_TASKS
            
            logger.info(f"BackgroundTaskManager initialized (Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT})")
            logger.info(f"Max concurrent tasks: {self.max_concurrent}")
            
        except Exception as e:
            logger.error(f"Failed to initialize BackgroundTaskManager: {e}")
            logger.warning("Background tasks will not be available")
            self.redis_conn = None
            self.queue = None
            self.queues = {}
    
    def get_active_task_count(self) -> int:
        """Get count of currently active (running) tasks.
        
        Returns:
            Number of active tasks across all queues
        """
        count = 0
        for task_id, task_info in self.tasks.items():
            try:
                job = task_info.get('job')
                if job and job.get_status() in ['queued', 'started']:
                    count += 1
            except:
                pass
        return count
    
    def can_start_new_task(self) -> bool:
        """Check if we can start a new background task.
        
        Returns:
            True if under max concurrent task limit
        """
        return self.get_active_task_count() < self.max_concurrent
    
    def get_task_count_by_type(self) -> Dict[str, int]:
        """Get count of tasks by type.
        
        Returns:
            Dict mapping task type to count
        """
        counts = {
            TaskType.PROGRAMMING: 0,
            TaskType.RESEARCH: 0,
            TaskType.CALL: 0
        }
        
        for task_id, task_info in self.tasks.items():
            task_type = task_info.get('task_type', TaskType.PROGRAMMING)
            try:
                job = task_info.get('job')
                if job and job.get_status() in ['queued', 'started']:
                    counts[task_type] = counts.get(task_type, 0) + 1
            except:
                pass
        
        return counts
    
    def start_programming_task(
        self,
        goal: str,
        project_path: str,
        session_id: str,
        verbose_updates: Optional[bool] = None
    ) -> str:
        """Start a new background programming task.
        
        Args:
            goal: What to build/fix
            project_path: Where to work
            session_id: TARS session that started this
            verbose_updates: Send detailed updates (optional, uses config default)
        
        Returns:
            Task ID
            
        Raises:
            RuntimeError: If Redis not available or max concurrent tasks reached
        """
        if not self.queue:
            raise RuntimeError("Task manager not initialized (Redis not available)")
        
        # Check concurrent task limit
        if not self.can_start_new_task():
            active = self.get_active_task_count()
            raise RuntimeError(
                f"Maximum concurrent tasks ({self.max_concurrent}) reached. "
                f"Currently {active} tasks running. Please wait for some to complete."
            )
        
        # Generate short task ID
        task_id = str(uuid.uuid4())[:8]
        
        # Set verbosity
        if verbose_updates is not None:
            # Temporarily override config for this task
            import os
            original_verbose = os.getenv('ENABLE_DETAILED_UPDATES')
            os.environ['ENABLE_DETAILED_UPDATES'] = 'true' if verbose_updates else 'false'
        
        try:
            # Enqueue the task
            job = self.queue.enqueue(
                'core.background_worker.run_autonomous_programming',
                task_id=task_id,
                goal=goal,
                project_path=project_path,
                session_id=session_id,
                max_iterations=50,
                max_minutes=Config.MAX_TASK_RUNTIME_MINUTES,
                job_timeout=f'{Config.MAX_TASK_RUNTIME_MINUTES + 2}m',  # +2 min buffer
                result_ttl=3600,  # Keep results for 1 hour
                job_id=task_id  # Use our task_id as job ID
            )
            
            # Store task info
            self.tasks[task_id] = {
                'job': job,
                'goal': goal,
                'project_path': project_path,
                'session_id': session_id,
                'started_at': datetime.now(),
                'status': 'queued',
                'task_type': TaskType.PROGRAMMING
            }
            
            logger.info(f"Started background task {task_id}: {goal}")
            return task_id
            
        finally:
            # Restore original verbosity setting
            if verbose_updates is not None and original_verbose is not None:
                import os
                os.environ['ENABLE_DETAILED_UPDATES'] = original_verbose
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get current status of a background task.
        
        Args:
            task_id: Task ID
        
        Returns:
            Status dictionary with:
                - task_id
                - status (queued, started, finished, failed)
                - goal
                - started_at
                - progress
                - current_phase
                - awaiting_confirmation
        """
        # Try to get from memory first
        if task_id in self.tasks:
            task_info = self.tasks[task_id]
            job = task_info['job']
        else:
            # Try to fetch from Redis by job ID
            try:
                job = Job.fetch(task_id, connection=self.redis_conn)
                # Reconstruct task info
                task_info = {
                    'goal': job.meta.get('goal', 'Unknown'),
                    'started_at': job.created_at,
                    'session_id': job.meta.get('session_id', 'unknown')
                }
                # Cache it
                self.tasks[task_id] = {
                    **task_info,
                    'job': job
                }
            except Exception as e:
                logger.error(f"Failed to fetch task {task_id}: {e}")
                return {'error': 'Task not found'}
        
        # Get job status
        try:
            job_status = job.get_status()
            job_meta = job.meta
            
            return {
                'task_id': task_id,
                'status': job_status,
                'goal': task_info['goal'],
                'project_path': task_info.get('project_path', 'Unknown'),
                'started_at': task_info['started_at'].isoformat() if isinstance(task_info['started_at'], datetime) else str(task_info['started_at']),
                'progress': job_meta.get('progress', 'Initializing...'),
                'current_phase': job_meta.get('phase', 'init'),
                'awaiting_confirmation': job_meta.get('awaiting_confirmation', False),
                'confirmation_command': job_meta.get('confirmation_command', None)
            }
        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {e}")
            return {
                'task_id': task_id,
                'status': 'unknown',
                'error': str(e)
            }
    
    def get_tasks_awaiting_confirmation(self) -> List[str]:
        """Get list of task IDs currently waiting for confirmation codes.
        
        Used to update system instructions so Gemini knows to watch for codes.
        
        Returns:
            List of task IDs
        """
        awaiting = []
        
        for task_id, task_info in self.tasks.items():
            try:
                job = task_info['job']
                if job.meta.get('awaiting_confirmation', False):
                    awaiting.append(task_id)
            except Exception as e:
                logger.error(f"Error checking task {task_id}: {e}")
        
        return awaiting
    
    def cancel_task(self, task_id: str) -> str:
        """Cancel a running background task.
        
        Args:
            task_id: Task ID to cancel
        
        Returns:
            Status message
        """
        if task_id not in self.tasks:
            # Try to fetch from Redis
            try:
                job = Job.fetch(task_id, connection=self.redis_conn)
            except:
                return "Task not found, sir."
        else:
            job = self.tasks[task_id]['job']
        
        try:
            # Cancel the job
            job.cancel()
            job.delete()
            
            # Remove from memory
            if task_id in self.tasks:
                del self.tasks[task_id]
            
            logger.info(f"Cancelled task {task_id}")
            return f"Task {task_id} cancelled, sir."
            
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")
            return f"Error cancelling task: {str(e)}"
    
    def list_all_tasks(self) -> List[Dict[str, Any]]:
        """List all tracked background tasks.
        
        Returns:
            List of task summaries
        """
        tasks = []
        
        for task_id in self.tasks.keys():
            try:
                status = self.get_task_status(task_id)
                tasks.append(status)
            except Exception as e:
                logger.error(f"Error listing task {task_id}: {e}")
        
        return tasks
    
    def start_research_task(
        self,
        goal: str,
        session_id: str,
        max_iterations: int = 5,
        output_format: str = "report"
    ) -> str:
        """Start a background research task.
        
        Args:
            goal: Research topic/question
            session_id: TARS session that started this
            max_iterations: Max research iterations
            output_format: Output format (report, summary, bullet_points)
        
        Returns:
            Task ID
        """
        if not self.queues.get(TaskType.RESEARCH):
            raise RuntimeError("Research queue not available")
        
        if not self.can_start_new_task():
            active = self.get_active_task_count()
            raise RuntimeError(f"Max tasks ({self.max_concurrent}) reached. {active} running.")
        
        task_id = str(uuid.uuid4())[:8]
        
        try:
            job = self.queues[TaskType.RESEARCH].enqueue(
                'core.background_worker.run_deep_research',
                task_id=task_id,
                goal=goal,
                session_id=session_id,
                max_iterations=max_iterations,
                output_format=output_format,
                job_timeout=f'{Config.RESEARCH_TIMEOUT_MINUTES}m',
                result_ttl=3600,
                job_id=f"research-{task_id}"
            )
            
            self.tasks[task_id] = {
                'job': job,
                'goal': goal,
                'session_id': session_id,
                'started_at': datetime.now(),
                'status': 'queued',
                'task_type': TaskType.RESEARCH
            }
            
            logger.info(f"Started research task {task_id}: {goal}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to start research task: {e}")
            raise
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about task queues.
        
        Returns:
            Dict with queue statistics
        """
        stats = {
            'active_tasks': self.get_active_task_count(),
            'max_concurrent': self.max_concurrent,
            'available_slots': self.max_concurrent - self.get_active_task_count(),
            'by_type': self.get_task_count_by_type()
        }
        
        # Add queue lengths
        for task_type, queue in self.queues.items():
            try:
                stats[f'{task_type}_queue_length'] = len(queue)
            except:
                stats[f'{task_type}_queue_length'] = 0
        
        return stats
