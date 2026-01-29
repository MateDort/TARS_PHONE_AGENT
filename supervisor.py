#!/usr/bin/env python3
"""
TARS Supervisor - Minimal watchdog for safe restarts.

IMPORTANT: This file should NEVER be modified by TARS itself.
It's the foundation that allows TARS to safely update and restart.

Usage:
    python supervisor.py

The supervisor:
1. Starts main_tars.py
2. Monitors for crashes (auto-restart after delay)
3. Monitors for restart requests (.tars_restart file)
4. Logs all events
"""
import subprocess
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - SUPERVISOR - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('supervisor.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
TARS_ROOT = Path(__file__).parent.absolute()
MAIN_SCRIPT = TARS_ROOT / "main_tars.py"
RESTART_FLAG = TARS_ROOT / ".tars_restart"
CRASH_DELAY = 5  # Seconds to wait before restarting after crash
MAX_RAPID_CRASHES = 5  # Max crashes within RAPID_CRASH_WINDOW before giving up
RAPID_CRASH_WINDOW = 60  # Seconds


def run_tars():
    """Run the main TARS process and return when it exits."""
    logger.info(f"Starting TARS: {MAIN_SCRIPT}")
    
    try:
        # Use the same Python interpreter
        process = subprocess.Popen(
            [sys.executable, str(MAIN_SCRIPT)],
            cwd=str(TARS_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Stream output to console and log
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(line.rstrip())
        
        exit_code = process.wait()
        return exit_code
        
    except Exception as e:
        logger.error(f"Failed to start TARS: {e}")
        return -1


def check_restart_request():
    """Check if a graceful restart was requested."""
    if RESTART_FLAG.exists():
        logger.info("Restart request detected (.tars_restart)")
        RESTART_FLAG.unlink()
        return True
    return False


def main():
    """Main supervisor loop."""
    logger.info("=" * 60)
    logger.info("TARS Supervisor starting")
    logger.info(f"TARS Root: {TARS_ROOT}")
    logger.info(f"Main Script: {MAIN_SCRIPT}")
    logger.info("=" * 60)
    
    # Track crashes for rapid crash detection
    crash_times = []
    
    while True:
        start_time = datetime.now()
        
        # Run TARS
        exit_code = run_tars()
        
        end_time = datetime.now()
        runtime = (end_time - start_time).total_seconds()
        
        # Check if this was a requested restart
        if check_restart_request():
            logger.info("Graceful restart - restarting immediately")
            continue
        
        # Handle exit codes
        if exit_code == 0:
            logger.info("TARS exited normally (code 0)")
            # Check if restart was requested
            if RESTART_FLAG.exists():
                logger.info("Restart flag found - restarting")
                RESTART_FLAG.unlink()
                continue
            else:
                logger.info("No restart requested - supervisor exiting")
                break
        else:
            logger.warning(f"TARS crashed (exit code: {exit_code}, runtime: {runtime:.1f}s)")
            
            # Track crash for rapid crash detection
            crash_times.append(datetime.now())
            
            # Remove old crashes outside the window
            cutoff = datetime.now().timestamp() - RAPID_CRASH_WINDOW
            crash_times = [t for t in crash_times if t.timestamp() > cutoff]
            
            # Check for rapid crash loop
            if len(crash_times) >= MAX_RAPID_CRASHES:
                logger.error(f"TARS crashed {len(crash_times)} times in {RAPID_CRASH_WINDOW}s - giving up")
                logger.error("Please fix the issue manually and restart the supervisor")
                break
            
            # Wait before restarting
            logger.info(f"Waiting {CRASH_DELAY}s before restart...")
            time.sleep(CRASH_DELAY)
            logger.info("Restarting TARS...")
    
    logger.info("Supervisor exiting")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Supervisor interrupted by user")
        sys.exit(0)
