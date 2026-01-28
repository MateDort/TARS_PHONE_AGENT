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


class BackgroundTaskManager:
    """Manages background programming tasks using Redis Queue."""
    
    def __init__(self):
        """Initialize task manager with Redis connection."""
        try:
            self.redis_conn = Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                decode_responses=False  # We'll decode manually
            )
            
            self.queue = Queue('tars_programming', connection=self.redis_conn)
            self.tasks: Dict[str, Dict[str, Any]] = {}
            
            logger.info(f"BackgroundTaskManager initialized (Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT})")
            
        except Exception as e:
            logger.error(f"Failed to initialize BackgroundTaskManager: {e}")
            logger.warning("Background tasks will not be available")
            self.redis_conn = None
            self.queue = None
    
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
        """
        if not self.queue:
            raise RuntimeError("Task manager not initialized (Redis not available)")
        
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
                'status': 'queued'
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
