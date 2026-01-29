# TARS Autonomous Coding V2 - Phase-Based System

## Overview

TARS now uses a sophisticated phase-based autonomous coding system inspired by Claude Code and Cursor. Instead of diving straight into coding, TARS follows a structured workflow with clear phases, each with specific constraints and goals.

## Model Configuration

- **Complex Tasks (Programming)**: Claude Opus 4 (`claude-opus-4-20250514`)
- **Fast Tasks (Summaries)**: Claude Sonnet 4 (`claude-sonnet-4-20250514`)

## Message Routing

TARS uses KIPP (N8N) for message routing with clear channel separation:

| Message Type | Channel | KIPP Instruction |
|-------------|---------|------------------|
| Logs/Progress | Discord | `target: "discord"`, `routing_instruction: "send_via_discord"` |
| Confirmations/Questions | Telegram | `target: "telegram"`, `routing_instruction: "send_via_telegram"` |

## Architecture

```
DISCOVER → PLAN → [User Approval via Telegram] → EXECUTE → VERIFY → PUBLISH
```

### Phase Flow

1. **DISCOVER** (Read-Only)
   - Maps project structure
   - Understands existing code
   - Identifies key files and patterns
   - **Output:** `discovery.md`

2. **PLAN** (Strategy)
   - Generates detailed implementation plan
   - Can ask clarifying questions via **Telegram**
   - Requires user approval via **Telegram** before proceeding
   - **Output:** `PLAN.md`

3. **EXECUTE** (Implementation)
   - Follows the approved plan
   - Creates/edits files incrementally
   - Auto-commits after each logical step
   - Logs progress to **Discord**
   - **Git Policy:** Commit per step

4. **VERIFY** (Testing)
   - Auto-runs detected tests
   - Fixes failures automatically
   - **Output:** `test_results.md`

5. **PUBLISH** (Deployment)
   - Pushes to GitHub
   - Generates deployment summary
   - **Output:** `deployment.md`

---

## Key Features

### 1. Project Memory (.tarsrules)

Every project has a `.tarsrules` file that stores:
- Language & style preferences
- Architecture patterns
- Git commit message format
- Testing requirements
- Custom project-specific instructions

### 2. Dual-Channel Communication

**Discord (Logs):**
- Progress updates
- Phase completions
- Status notifications
- Error reports

**Telegram (Confirmations):**
- User questions during PLAN phase
- Plan approval requests
- Destructive command confirmations

### 3. Auto Git Integration

- Ensures git repo exists before starting
- Auto-commits after each file edit in EXECUTE phase
- Commit format: `[PHASE] Brief description`
- Push to GitHub in PUBLISH phase

### 4. Context Management

- Uses Claude Sonnet 4 for summarization (cost-effective)
- Compacts old actions when approaching token limits
- Keeps recent actions and errors in full detail

---

## Usage

### Starting a Task

Via voice or Discord:
```
"Hey TARS, start autonomous coding on /Users/me/my-project 
with goal: Add user authentication system"
```

### Message Flow Example

```
[DISCORD] 🔍 Entering DISCOVER phase
[DISCORD] 📝 Discovered: Next.js app with 15 components
[TELEGRAM] ❓ Question: Should I use JWT or session-based auth?
[User replies on Telegram]
[TELEGRAM] 📋 Plan Ready - Reply 'approve' or 'reject'
[User replies 'approve' on Telegram]
[DISCORD] ✅ Plan approved! Starting execution...
[DISCORD] ⚙️ Entering EXECUTE phase
[DISCORD] 📝 Created middleware/auth.ts
[DISCORD] 📝 Git commit: [EXECUTE] Add auth middleware
[DISCORD] 🧪 Running verification...
[DISCORD] ✅ All tests passed!
[DISCORD] 🚀 Pushed to GitHub!
```

---

## Configuration

### Environment Variables

```bash
# Model Configuration
CLAUDE_COMPLEX_MODEL=claude-opus-4-20250514  # For programming
CLAUDE_FAST_MODEL=claude-sonnet-4-20250514   # For summaries

# Phase system
MAX_PHASE_ITERATIONS_DISCOVER=10
MAX_PHASE_ITERATIONS_PLAN=5
MAX_PHASE_ITERATIONS_EXECUTE=30
MAX_PHASE_ITERATIONS_VERIFY=10
MAX_PHASE_ITERATIONS_PUBLISH=3

# Context management
MAX_CONTEXT_TOKENS=180000
ENABLE_AUTO_CONTEXT_COMPACTION=true

# Git integration
AUTO_COMMIT_PER_STEP=true
AUTO_PUSH_ON_COMPLETE=true
COMMIT_MESSAGE_PREFIX="[TARS]"
```

---

## KIPP/N8N Routing

### Discord Messages (Logs)
```json
{
  "target": "discord",
  "routing_instruction": "send_via_discord",
  "message_type": "log",
  "source": "background_task",
  "task_id": "abc123",
  "type": "progress",
  "message": "✅ Created package.json"
}
```

### Telegram Messages (Confirmations)
```json
{
  "target": "telegram",
  "routing_instruction": "send_via_telegram",
  "message_type": "confirmation",
  "source": "background_task",
  "task_id": "abc123",
  "type": "user_question",
  "message": "❓ Should I use TypeScript?",
  "awaiting_response": true
}
```

---

## Technical Implementation

- `core/phase_manager.py` - Phase definitions and validation
- `core/user_interaction.py` - Telegram questions and approvals
- `core/verification.py` - Test framework detection
- `core/context_manager.py` - Token management with Sonnet 4
- `core/background_worker.py` - Main execution loop with Opus 4
- `sub_agents_tars.py` - ProgrammerAgent with git helpers

---

Generated: 2026-01-28
Version: 2.0.0
