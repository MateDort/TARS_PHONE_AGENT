#!/bin/bash
# TARS 2.0 Startup Script
# Starts:
# 1. Redis (if locally available via brew)
# 2. Redis Workers (for background tasks)
# 3. Manager Agent (Telelegram/Discord/Orchestrator)
# 4. TARS Phone Agent (Flask/Twilio/Gemini)

# PREVENT MACOS FORK CRASHES
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

echo "=================================================="
echo "   STARTING TARS 2.0 - AUTONOMOUS SYSTEM"
echo "=================================================="

# 1. Check/Start Redis
if ! pgrep redis-server > /dev/null; then
    echo "[SYSTEM] Starting Redis..."
    if command -v brew >/dev/null; then
        brew services start redis
    else
        echo "[ERROR] Redis not found. Please start Redis manually."
        exit 1
    fi
else
    echo "[SYSTEM] Redis is running."
fi

# Activate venv
source ./venv/bin/activate

# 2. Start Manager Agent (Background) with module syntax (fixes imports)
echo "[AGENT] Starting Manager Agent (Telegram/Discord/EventBus)..."
# Using -m agents.manager_agent to ensure 'core' package is found
python -m agents.manager_agent > manager.log 2>&1 &
MANAGER_PID=$!
echo "[AGENT] Manager Agent started (PID: $MANAGER_PID)"

# 3. Start Workers (Background)
echo "[WORKER] Starting Background Workers..."
# Using -m to also help with path issues, though start_workers is in root
python start_workers.py --workers 3 > workers.log 2>&1 &
WORKER_PID=$!
echo "[WORKER] Workers started (PID: $WORKER_PID)"

# 4. Start Phone Agent (Foreground)
echo "[PHONE] Starting TARS Phone Agent..."
echo "Press Ctrl+C to stop all services."
python main_tars.py

# Cleanup function
cleanup() {
    echo ""
    echo "[SYSTEM] Shutting down..."
    kill $MANAGER_PID
    kill $WORKER_PID
    # Python script handles its own cleanup signal, but we kill background procs here
    echo "[SYSTEM] TARS Shutdown Complete."
}

# Trap exit signals
trap cleanup EXIT INT TERM
