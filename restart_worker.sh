#!/bin/bash
# Script to restart the TARS background worker

# Kill existing worker if running
pkill -f "python.*start_worker.py"

# Wait a moment
sleep 1

# Start worker with fork safety fix
cd "$(dirname "$0")"
source venv/bin/activate
python start_worker.py
