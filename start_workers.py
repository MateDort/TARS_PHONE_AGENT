#!/usr/bin/env python3
"""
Start multiple RQ workers for TARS background tasks.

This creates a worker pool that can handle multiple concurrent background tasks
(programming, research, outbound calls) up to MAX_BACKGROUND_TASKS.

Usage:
    python start_workers.py              # Start default number of workers
    python start_workers.py --workers 5  # Start 5 workers
    python start_workers.py --single     # Start single worker (legacy mode)
"""
import argparse
import logging
import signal
import sys
import os
from multiprocessing import Process
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from redis import Redis
from rq import Worker, Queue
from core.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Track worker processes for cleanup
worker_processes = []


def create_redis_connection():
    """Create Redis connection with config settings."""
    return Redis(
        host=Config.REDIS_HOST,
        port=Config.REDIS_PORT,
        db=Config.REDIS_DB
    )


def start_single_worker(worker_id: int = 0):
    """Start a single RQ worker.
    
    This is run in a subprocess.
    Workers listen on ALL task queues (programming, research, calls).
    
    Args:
        worker_id: Unique identifier for this worker
    """
    # Set up worker-specific logging
    worker_logger = logging.getLogger(f"worker-{worker_id}")
    worker_logger.info(f"Worker {worker_id} starting...")
    
    try:
        # macOS fork safety - set environment variable
        os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
        
        redis_conn = create_redis_connection()
        
        # Workers listen on ALL queues defined in TaskManager
        programming_queue = Queue('tars_programming', connection=redis_conn)
        research_queue = Queue('tars_research', connection=redis_conn)
        computer_queue = Queue('tars_computer_control', connection=redis_conn)
        calls_queue = Queue('tars_calls', connection=redis_conn)
        
        worker = Worker(
            [programming_queue, research_queue, computer_queue, calls_queue],  # Listen on all queues
            connection=redis_conn,
            name=f'tars-worker-{worker_id}'
        )
        
        worker_logger.info(f"Worker {worker_id} connected to queues: tars_programming, tars_research, tars_calls")
        worker.work(with_scheduler=False)
        
    except Exception as e:
        worker_logger.error(f"Worker {worker_id} error: {e}")
        sys.exit(1)


def start_worker_pool(num_workers: int):
    """Start a pool of workers.
    
    Args:
        num_workers: Number of workers to start
    """
    global worker_processes
    
    logger.info(f"Starting worker pool with {num_workers} workers")
    logger.info(f"Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
    logger.info(f"Max concurrent tasks: {Config.MAX_BACKGROUND_TASKS}")
    
    # Create worker processes
    for i in range(num_workers):
        p = Process(target=start_single_worker, args=(i,))
        p.start()
        worker_processes.append(p)
        logger.info(f"Started worker {i} (PID: {p.pid})")
    
    logger.info(f"All {num_workers} workers started")
    
    # Wait for all workers
    try:
        for p in worker_processes:
            p.join()
    except KeyboardInterrupt:
        logger.info("Interrupt received, shutting down workers...")
        shutdown_workers()


def shutdown_workers():
    """Gracefully shutdown all worker processes."""
    global worker_processes
    
    for p in worker_processes:
        if p.is_alive():
            logger.info(f"Terminating worker (PID: {p.pid})")
            p.terminate()
    
    # Wait for processes to terminate
    for p in worker_processes:
        p.join(timeout=5)
        if p.is_alive():
            logger.warning(f"Force killing worker (PID: {p.pid})")
            p.kill()
    
    worker_processes = []
    logger.info("All workers stopped")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}")
    shutdown_workers()
    sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Start TARS background workers')
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=Config.WORKER_POOL_SIZE,
        help=f'Number of workers to start (default: {Config.WORKER_POOL_SIZE})'
    )
    parser.add_argument(
        '--single', '-s',
        action='store_true',
        help='Start a single worker (legacy mode)'
    )
    
    args = parser.parse_args()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Validate Redis connection
    try:
        redis_conn = create_redis_connection()
        redis_conn.ping()
        logger.info("Redis connection successful")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        logger.error("Make sure Redis is running: brew services start redis")
        sys.exit(1)
    
    # Start workers
    if args.single:
        logger.info("Starting single worker (legacy mode)")
        start_single_worker(0)
    else:
        num_workers = min(args.workers, Config.MAX_BACKGROUND_TASKS)
        start_worker_pool(num_workers)


if __name__ == '__main__':
    main()
