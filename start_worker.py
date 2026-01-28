#!/usr/bin/env python3
"""Start RQ worker for background programming tasks.

This worker processes autonomous coding tasks in the background,
allowing TARS to remain responsive to other requests during long-running
programming operations.

Usage:
    python3 start_worker.py

Requirements:
    - Redis must be running (brew install redis && brew services start redis)
    - All dependencies installed (pip install -r requirements.txt)
"""
import os

# Fix macOS fork safety issue with Objective-C libraries
# This must be set BEFORE importing any libraries that use Objective-C
os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'

from redis import Redis
from rq import Worker, Queue
from core.config import Config
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Start the background worker."""
    print("\n" + "=" * 60)
    print("  TARS BACKGROUND WORKER")
    print("  Autonomous Programming Task Processor")
    print("=" * 60)
    print()
    
    # Test Redis connection
    try:
        redis_conn = Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB
        )
        redis_conn.ping()
        logger.info(f"✅ Connected to Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        logger.error(f"   Make sure Redis is running:")
        logger.error(f"   macOS: brew install redis && brew services start redis")
        logger.error(f"   Ubuntu: sudo apt install redis-server && sudo systemctl start redis")
        sys.exit(1)
    
    # Create queue
    queue = Queue('tars_programming', connection=redis_conn)
    
    print("Configuration:")
    print(f"  Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT} (DB {Config.REDIS_DB})")
    print(f"  Max task runtime: {Config.MAX_TASK_RUNTIME_MINUTES} minutes")
    print(f"  Detailed updates: {'enabled' if Config.ENABLE_DETAILED_UPDATES else 'disabled'}")
    print(f"  Queue: tars_programming")
    print()
    print("🚀 Starting worker...")
    print("   Worker will process autonomous coding tasks")
    print("   Press CTRL+C to stop")
    print("=" * 60)
    print()
    
    # Create and start worker
    try:
        # Use SimpleWorker on macOS to avoid fork() issues with Objective-C
        # SimpleWorker doesn't fork, it runs tasks in the same process
        from rq.worker import SimpleWorker
        import platform
        
        if platform.system() == 'Darwin':  # macOS
            logger.info("Using SimpleWorker (no fork) for macOS compatibility")
            worker = SimpleWorker([queue], connection=redis_conn)
        else:
            worker = Worker([queue], connection=redis_conn)
        
        # Start working (blocks until interrupted)
        logger.info("Worker started successfully")
        worker.work()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Worker stopped by user")
        logger.info("Worker stopped by user interrupt")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Worker error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
