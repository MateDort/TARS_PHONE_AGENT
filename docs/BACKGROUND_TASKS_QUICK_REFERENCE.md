# Background Tasks Quick Reference

**One-page cheat sheet for TARS autonomous programming**

---

## Setup (One-Time)

```bash
# 1. Install Redis
brew install redis && brew services start redis

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure .env
# Discord updates route through main N8N webhook - no separate URL needed!
REDIS_HOST=localhost
MAX_TASK_RUNTIME_MINUTES=15
ENABLE_DETAILED_UPDATES=true

# 4. Start worker (Terminal 1)
python3 start_worker.py

# 5. Start TARS (Terminal 2)
python3 main_tars.py
```

---

## Voice Commands

| Command | What It Does |
|---------|--------------|
| "Build a calculator app with tests" | Starts background task |
| "How's the coding going?" | Check latest task progress |
| "Check progress on task abc123" | Check specific task |
| "Cancel the background task" | Cancel latest task |
| "Cancel task abc123" | Cancel specific task |
| "6283" (during confirmation) | Provide confirmation code |

---

## How It Works

```
You: "Build a calculator"
  ↓
TARS: "Started task #abc123, I'll update you on Discord"
  (TARS is now FREE to do other things)
  ↓
Background Worker:
  - Plans the approach
  - Creates calculator.py
  - Creates test_calculator.py  
  - Runs pytest
  - Tests fail → fixes bugs
  - Runs pytest again
  - Tests pass → done!
  ↓
Discord: "🎉 Task complete! All tests passing."
```

**Timeline**: You can talk to TARS about weather, reminders, etc. while this happens in parallel.

---

## Discord Messages You'll See

### Normal Flow

```
[Bot] 🚀 Started background task #abc123: Build a calculator

[Bot] 📋 Planning approach...

[Bot] ✏️ Editing calculator.py

[Bot] ✏️ Editing test_calculator.py

[Bot] ⚙️ Executing: `pytest`

[Bot] ✅ Command succeeded
      All 4 tests passed

[Bot] 🎉 Task complete!
```

### When Confirmation Needed

```
[Bot] ⚠️ Background Task #abc123 Needs Confirmation
      
      Command: `rm old_file.py`
      Reason: delete files
      
      Reply with your confirmation code to proceed.

[You] 6283

[Bot] ✅ Confirmation code received! Task #abc123 will continue.
```

---

## Functions Reference

### start_autonomous_coding
- **Purpose**: Start long-running coding task
- **Max time**: 15 minutes
- **Model**: Claude Sonnet 4.5
- **Updates**: Discord (real-time)

### check_coding_progress
- **Purpose**: Check task status
- **Shows**: Phase, progress, waiting for confirmation?

### cancel_coding_task
- **Purpose**: Stop running task
- **Effect**: Immediate cancellation

### submit_background_confirmation
- **Purpose**: Provide confirmation code
- **Triggered**: Automatically when you say a 4-digit code

---

## What Claude Does Autonomously

1. **Planning**: Analyzes the goal, decides approach
2. **File Operations**: Creates, edits, reads files
3. **Command Execution**: Runs npm, pip, pytest, git, etc.
4. **Testing**: Runs test suites, reads failures
5. **Debugging**: Fixes failing tests based on error output
6. **Iteration**: Repeats until tests pass or goal met
7. **Completion**: Reports results

**No human intervention needed** - unless a destructive command requires confirmation.

---

## Status Indicators

| Status | Meaning |
|--------|---------|
| `queued` | Waiting for worker to pick it up |
| `started` | Worker is working on it |
| `finished` | Successfully completed |
| `failed` | Error occurred |
| `timeout` | Exceeded 15-minute limit |

| Phase | What's Happening |
|-------|------------------|
| `init` | Starting up |
| `planning` | Claude analyzing goal |
| `coding` | Writing/editing code |
| `testing` | Running tests |
| `fixing` | Fixing failed tests |
| `complete` | Done! |
| `error` | Something went wrong |

---

## Confirmation Code Flow

### If You're In a Call:

1. **Discord message**: Shows command + reason
2. **TARS (voice)**: Interrupts to ask for code
3. **You**: Say "6283"
4. **TARS**: "Code received, task continues"
5. **Worker**: Resumes from where it paused

### If You're NOT In a Call:

1. **Discord message**: Shows command + reason
2. **You**: Reply in Discord: "6283"
3. **N8N**: Captures code, sends to TARS
4. **Worker**: Resumes

**Both channels work simultaneously** - whichever responds first unblocks the task.

---

## Configuration Options

### .env Settings

```env
# How long tasks can run
MAX_TASK_RUNTIME_MINUTES=15

# Show every action or just phases?
ENABLE_DETAILED_UPDATES=true  # false = phases only

# Where to send updates
# Background tasks use the same N8N_WEBHOOK_URL as KIPP

# Redis connection
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### Per-Task Override

```
"Build calculator with detailed updates"  # Verbose mode
"Build calculator with minimal updates"   # Quiet mode
```

---

## Limits & Constraints

| Limit | Value | Configurable |
|-------|-------|--------------|
| Max runtime | 15 minutes | Yes (.env) |
| Max iterations | 50 | No (hardcoded) |
| Confirmation timeout | 5 minutes | No (hardcoded) |
| Concurrent tasks | Unlimited | Limited by workers |
| Task result retention | 1 hour | No (hardcoded) |

---

## Cost Estimation

**Per 15-minute task**:
- Claude Sonnet 4.5 API calls: ~$0.50 - $2.00
- Depends on: iterations, file sizes, context length

**Tips to reduce costs**:
- Use shorter time limits for simple tasks
- Set `ENABLE_DETAILED_UPDATES=false` (slightly less API calls)
- Be specific with goals (fewer iterations needed)

---

## Troubleshooting Quick Fixes

| Problem | Solution |
|---------|----------|
| Worker not starting | `brew services restart redis` |
| Tasks stuck in queue | Restart worker: Ctrl+C then `python3 start_worker.py` |
| No Discord messages | Check webhook URL in `.env` |
| Confirmation timeout | Provide code within 5 minutes |
| Task taking too long | Normal for complex tasks, check progress periodically |

---

## Files Created by This Feature

```
/Users/matedort/TARS_PHONE_AGENT/
├── core/
│   ├── background_worker.py      # Task execution logic
│   ├── task_manager.py           # Queue management
│   └── config.py                 # Added Redis settings
├── start_worker.py               # Worker startup script
└── docs/
    ├── BACKGROUND_PROGRAMMING.md        # Full guide
    ├── N8N_BACKGROUND_TASKS_SETUP.md   # N8N setup
    └── BACKGROUND_TASKS_QUICK_REFERENCE.md  # This file
```

---

## Next Steps

1. ✅ Read this quick reference
2. 📖 Read [BACKGROUND_PROGRAMMING.md](BACKGROUND_PROGRAMMING.md) for detailed usage
3. 🔧 Read [N8N_BACKGROUND_TASKS_SETUP.md](N8N_BACKGROUND_TASKS_SETUP.md) for N8N setup
4. 🚀 Try a simple task: "Create a hello world script"
5. 🎯 Try a complex task: "Build a todo app with database and tests"

---

## Support & Debugging

**Check worker logs**:
```bash
# Worker shows real-time task execution
python3 start_worker.py
# Look for: "Task abc123: <current action>"
```

**Check TARS logs**:
```bash
# When starting task
2026-01-27 16:00:00 - sub_agents_tars - INFO - Started background task abc123

# When receiving confirmation
2026-01-27 16:05:00 - sub_agents_tars - INFO - Stored voice confirmation code for task abc123
```

**Check Redis directly**:
```bash
redis-cli

# List all tasks
KEYS task:*

# Check specific task confirmation
GET task:abc123:confirmation

# Check queue length
LLEN rq:queue:tars_programming
```

---

**Remember**: Background tasks let you multitask. Start a 15-minute coding job, then go about your day while Claude works autonomously!
