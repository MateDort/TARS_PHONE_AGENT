# Getting Started with Background Tasks

**Follow these steps to enable autonomous programming**

---

## Prerequisites Check

Before starting, verify:
- ✅ TARS is working (you can make calls)
- ✅ Claude integration is working (ANTHROPIC_API_KEY in .env)
- ✅ You have terminal access to your Mac

---

## Step 1: Install Redis (5 minutes)

Open a terminal and run:

```bash
# Install Redis via Homebrew
brew install redis

# Start Redis as a background service
brew services start redis

# Test that it's running
redis-cli ping
```

**Expected output**: `PONG`

If you see `PONG`, Redis is ready! ✅

**If it fails**:
```bash
# Check Homebrew
brew doctor

# Try manual start
redis-server
```

---

## Step 2: Install Python Dependencies (1 minute)

```bash
cd /Users/matedort/TARS_PHONE_AGENT
pip install -r requirements.txt
```

This installs `rq` and `redis` packages.

**Expected output**: 
```
Successfully installed rq-1.x.x redis-5.x.x
```

---

## Step 3: Configure Environment (2 minutes)

Add these lines to your `.env` file:

```bash
# Open .env in your editor
nano .env

# Add these lines at the end:

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Background Task Settings
MAX_TASK_RUNTIME_MINUTES=15
ENABLE_DETAILED_UPDATES=true

# Discord Updates (you'll set up N8N later)
DISCORD_UPDATES_WEBHOOK=

# Save and exit (Ctrl+O, Enter, Ctrl+X for nano)
```

**Note**: Discord updates use the same `N8N_WEBHOOK_URL` as KIPP. No separate webhook needed!

---

## Step 4: Test Without Discord (5 minutes)

Let's verify the system works before adding Discord complexity.

### Terminal 1: Start Worker

```bash
cd /Users/matedort/TARS_PHONE_AGENT
python3 start_worker.py
```

**Expected output**:
```
============================================================
  TARS BACKGROUND WORKER
  Autonomous Programming Task Processor
============================================================

Configuration:
  Redis: localhost:6379 (DB 0)
  Max task runtime: 15 minutes
  Queue: tars_programming

🚀 Starting worker...
   Worker will process autonomous coding tasks
   Press CTRL+C to stop
============================================================

```

**If you see this**: Worker is ready! ✅

**If it fails**: Check that Redis is running (`redis-cli ping`)

### Terminal 2: Start TARS

```bash
cd /Users/matedort/TARS_PHONE_AGENT
python3 main_tars.py
```

Watch for this line in the startup:
```
2026-01-27 XX:XX:XX - core.session_manager - INFO - Background task manager initialized
```

If you see that, background tasks are enabled! ✅

### Terminal 3: Test Basic Task

Call TARS from your phone and say:

```
"Create a simple hello world Python script"
```

**Expected response**:
```
"Started autonomous coding task #abc123 in background, sir.
Goal: Create a simple hello world Python script
Project: /Users/matedort/[current_project]
I'll send updates to Discord and you can check progress anytime."
```

**Watch Terminal 1 (Worker)**:
```
2026-01-27 XX:XX:XX - INFO - Starting autonomous programming task abc123
2026-01-27 XX:XX:XX - INFO - Task abc123: Planning approach...
2026-01-27 XX:XX:XX - INFO - Task abc123: Editing hello.py
2026-01-27 XX:XX:XX - INFO - Completed task abc123
```

**Test TARS stays responsive**:

While the task is running, ask TARS:
```
"What's the time?"
```

TARS should respond immediately! This proves multitasking works. ✅

---

## Step 5: Set Up Discord Integration (15 minutes)

### 5.1 Create Discord Channel

1. Go to your Discord server
2. Create a new channel: `#tars-background-tasks`
3. Copy the channel ID (right-click channel → Copy ID)

### 5.2 Create N8N Workflow

Follow the detailed guide in [`N8N_BACKGROUND_TASKS_SETUP.md`](N8N_BACKGROUND_TASKS_SETUP.md)

**Quick version**:

1. **Create new workflow** in N8N: "TARS Background Tasks"

2. **Add Webhook trigger**:
   - Path: `discord-updates`
   - Method: POST
   - Response: `{"status": "ok"}`

3. **Add Discord Send Message**:
   - Channel ID: Your `#tars-background-tasks` channel
   - Message: `{{ $json.message }}`

4. **Activate workflow**

5. **Copy webhook URL** and add to TARS `.env`:
   ```env
   # Discord updates route through main N8N_WEBHOOK_URL (KIPP)
   ```

6. **Restart TARS** (Terminal 2: Ctrl+C, then `python3 main_tars.py`)

### 5.3 Test Discord Integration

Call TARS and say:

```
"Build a calculator script with add and subtract functions"
```

**You should see in Discord**:
```
🚀 Background Task Started

Task ID: xyz789
Goal: Build a calculator script with add and subtract functions
Project: /Users/matedort/[project]

Updates will be posted here.

---

📋 Planning approach...

---

✏️ Editing calculator.py

---

⚙️ Executing: `python calculator.py`

---

✅ Command succeeded
Result: Basic operations working

---

🎉 Task complete!
Calculator with add/subtract ready.
```

If you see these updates in Discord, **Discord integration works!** ✅

---

## Step 6: Test Confirmation Flow (5 minutes)

This tests the dual-channel confirmation system.

### Test A: Via Voice (While In Call)

Call TARS and say:

```
"Create a test file, run some tests, then delete the test file"
```

When the task tries to delete the file, you should see:

**Discord**:
```
⚠️ Background Task #abc123 Needs Confirmation

Command: `rm test_file.py`
Reason: delete files

Reply with your confirmation code to proceed.
```

**TARS (Voice)**:
```
"Sir, the background programming task needs your confirmation code.
I need to run: rm test_file.py.
This is needed to delete files.
Please provide your confirmation code."
```

**You respond (voice)**: "6283"

**TARS**: "Confirmation code received for task abc123, sir. The background task will continue."

**Worker continues** ✅

### Test B: Via Discord (Not In Call)

1. **Hang up** (end TARS call)

2. **In Terminal, simulate a task needing confirmation**:
   ```bash
   curl -X POST http://localhost:5002/webhook/background-confirmation \
     -H "Content-Type: application/json" \
     -d '{"task_id": "test456", "confirmation_code": "6283"}'
   ```

3. **Expected response**: `{"status": "ok", "message": "Confirmation received"}`

If you get this, **Discord confirmation endpoint works!** ✅

---

## Step 7: Advanced N8N (Optional - 10 minutes)

To complete the confirmation loop via Discord:

1. **Create second N8N workflow**: "TARS Confirmation Listener"

2. **Add Discord trigger**:
   - Event: Message Created
   - Channel: Your TARS channel
   - Ignore Bots: Yes

3. **Add IF node**:
   - Condition: Message contains 4-digit number
   - Regex: `^\d{4}$`

4. **Add HTTP Request node**:
   - Method: POST
   - URL: `http://localhost:5002/webhook/background-confirmation`
   - Body:
   ```json
   {
     "task_id": "{{ $json.task_id }}",
     "confirmation_code": "{{ $json.extracted_code }}"
   }
   ```
   
   **Note**: You'll need to extract task_id from recent messages. See [`N8N_BACKGROUND_TASKS_SETUP.md`](N8N_BACKGROUND_TASKS_SETUP.md) for detailed implementation.

5. **Activate workflow**

---

## ✅ Verification Checklist

After completing all steps, verify:

- [ ] Redis is running: `redis-cli ping` → PONG
- [ ] Worker starts: `python3 start_worker.py` → No errors
- [ ] TARS shows: "Background task manager initialized"
- [ ] Can start task via voice: "Create hello world"
- [ ] Worker terminal shows task execution
- [ ] TARS stays responsive during background task
- [ ] Discord receives task updates
- [ ] Confirmation request appears in Discord
- [ ] Can provide code via voice (if in call)
- [ ] Can provide code via Discord (N8N setup complete)

---

## 🆘 Troubleshooting

### "Background task system not available"

**Cause**: Redis not connected

**Fix**:
```bash
# Check Redis
redis-cli ping

# If no response
brew services restart redis
```

### Worker shows "Connection refused"

**Cause**: Redis not running

**Fix**:
```bash
brew services start redis
```

### No Discord messages appearing

**Cause**: Webhook not configured or N8N workflow not active

**Fix**:
1. Check `.env`: `N8N_WEBHOOK_URL` is set for KIPP/Discord routing
2. Check N8N: Workflow is **activated** (toggle in top-right)
3. Test webhook:
   ```bash
   curl -X POST your-webhook-url \
     -H "Content-Type: application/json" \
     -d '{"task_id": "test", "type": "progress", "message": "Test"}'
   ```

### Tasks not executing

**Cause**: Worker not started

**Fix**:
```bash
# Terminal 1
python3 start_worker.py
```

---

## 📞 Support

If you get stuck:

1. **Check logs**: Worker terminal shows detailed execution
2. **Read docs**: [`BACKGROUND_PROGRAMMING.md`](BACKGROUND_PROGRAMMING.md) has troubleshooting
3. **Test Redis**: `redis-cli` to inspect queue directly
4. **Simplify**: Start with basic task (hello world) before complex ones

---

## 🎯 Next Steps

Once basic setup works:

1. **Set up full N8N confirmation loop** - See [`N8N_BACKGROUND_TASKS_SETUP.md`](N8N_BACKGROUND_TASKS_SETUP.md)
2. **Try a complex task** - "Build a todo app with database and tests"
3. **Test multitasking** - Start task, then ask TARS about weather, reminders, etc.
4. **Optimize verbosity** - Set `ENABLE_DETAILED_UPDATES=false` if Discord is too noisy
5. **Deploy to cloud** - Follow main README for cloud deployment (24/7 availability)

---

**You're all set! Background programming is ready to use.** 🚀

Call TARS and say: **"Build me a calculator app with full test coverage"** and watch it work autonomously while you do other things!
