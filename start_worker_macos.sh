#!/bin/bash
# macOS-safe wrapper to start the background worker
# This sets the fork safety environment variable BEFORE Python starts

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Set macOS fork safety flag BEFORE Python starts
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Start the worker
python start_worker.py
