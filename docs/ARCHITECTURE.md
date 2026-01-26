# TARS Architecture & Organization Guide

**Last Updated**: 2026-01-26  
**Purpose**: Clear documentation for understanding and extending TARS

---

## 📁 File Structure Overview

```
TARS_PHONE_AGENT/
├── 🎯 CORE SYSTEM
│   ├── main_tars.py              # Application entry point, orchestrates everything
│   ├── config.py                 # Configuration management (env vars, settings)
│   ├── database.py               # SQLite operations (reminders, contacts, logs)
│   └── security.py               # Phone number authentication & permissions
│
├── 🧠 AI & COMMUNICATION
│   ├── gemini_live_client.py     # Gemini Live Audio API integration
│   ├── twilio_media_streams.py   # Twilio voice call handling & WebSocket
│   ├── translations.py           # Multi-language support
│   └── task_planner.py           # Function call ordering & prioritization
│
├── 🤖 AGENT SYSTEM
│   ├── sub_agents_tars.py        # ALL sub-agents (9 agents, 20 functions)
│   ├── agent_session.py          # Session state management per call
│   ├── session_manager.py        # Multi-session coordination
│   └── github_operations.py      # Git/GitHub operations for programmer agent
│
├── 💬 MESSAGING & ROUTING
│   ├── message_router.py         # Routes messages between sessions
│   ├── messaging_handler.py      # Twilio SMS/WhatsApp integration
│   └── reminder_checker.py       # Background reminder polling & calls
│
├── 📚 DOCUMENTATION
│   ├── README.md                 # Quick start guide
│   ├── ARCHITECTURE.md           # This file - system organization
│   ├── TARS.md                   # Core concept & features
│   ├── PROGRAMMER_SETUP.md       # Programmer agent guide
│   ├── BUGFIXES.md               # Recent bug fixes
│   └── IMPLEMENTATION_SUMMARY.md # Implementation details
│
└── 🔧 UTILITIES & TESTS
    ├── test_*.py                 # Test scripts
    ├── send_n8n_message.py       # N8N integration utility
    └── update_twilio_webhook.py  # Webhook configuration tool
```

---

## 🤖 Agent System Architecture

### Base Class: `SubAgent`

All agents inherit from `SubAgent` (defined at top of `sub_agents_tars.py`):

```python
class SubAgent:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    async def execute(self, args: Dict[str, Any]) -> str:
        # Each agent implements this
        pass
```

### Current Agents (9 Total)

| Agent | Line # | Functions | Purpose |
|-------|--------|-----------|---------|
| **ConfigAgent** | 17 | `adjust_config` | Adjust humor/honesty levels |
| **ReminderAgent** | 276 | `manage_reminder` | Create/list/delete reminders |
| **ContactsAgent** | 559 | `lookup_contact` | Find phone numbers |
| **NotificationAgent** | 803 | `send_notification` | Send SMS/WhatsApp |
| **OutboundCallAgent** | 834 | `make_goal_call` | Initiate outbound calls |
| **InterSessionAgent** | 1031 | 8 functions | Multi-session coordination |
| **ConversationSearchAgent** | 1527 | `search_conversations` | Search past conversations |
| **KIPPAgent** | 1614 | `send_to_n8n` | N8N workflow integration |
| **ProgrammerAgent** | 1822 | 4 functions | Terminal, file ops, GitHub |

### Total: 20 Functions Across 9 Agents

---

## 🔄 How Function Calls Work

### 1. Function Declaration (Gemini API Format)

Each function must be declared in `get_function_declarations()` at line ~2940:

```python
{
    "name": "function_name",
    "description": "What it does - Gemini reads this!",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "param1": {
                "type": "STRING",
                "description": "What this parameter is"
            }
        },
        "required": ["param1"]
    }
}
```

### 2. Registration (Mapping to Agents)

In `main_tars.py` `_register_sub_agents()` method:

```python
function_map = {
    "function_name": agents.get("agent_name"),
}
```

### 3. Execution Flow

```
User speaks → Gemini Live → Function call → 
main_tars.py routes to agent → Agent executes → 
Returns result → Gemini speaks response
```

---

## 🎯 Agent Details

### 1. ConfigAgent (Line 17)
**Purpose**: Adjust TARS's personality settings

**Functions**:
- `adjust_config(setting, value)` - Change humor or honesty levels

**Example**: "Make yourself more funny" → adjusts humor to 90%

---

### 2. ReminderAgent (Line 276)
**Purpose**: Time-based task management

**Functions**:
- `manage_reminder(action, ...)` - create/list/complete/delete reminders

**Database**: `reminders` table  
**Background**: `reminder_checker.py` polls every 30 seconds

**Example**: "Remind me to call mom at 3pm" → creates reminder → calls at 3pm

---

### 3. ContactsAgent (Line 559)
**Purpose**: Phone number lookup

**Functions**:
- `lookup_contact(name)` - Find phone numbers

**Database**: `contacts` table  
**Fuzzy matching**: Uses `difflib.get_close_matches()`

**Example**: "Call John" → looks up John's number

---

### 4. NotificationAgent (Line 803)
**Purpose**: Send text messages

**Functions**:
- `send_notification(contact, message, channel)` - SMS/WhatsApp

**Integration**: Twilio API via `messaging_handler.py`

**Example**: "Text mom I'll be late" → sends SMS

---

### 5. OutboundCallAgent (Line 834)
**Purpose**: Initiate phone calls

**Functions**:
- `make_goal_call(contact, goal)` - Start outbound call with goal

**Integration**: Twilio API, creates new session

**Example**: "Call dad to discuss dinner plans"

---

### 6. InterSessionAgent (Line 1031)
**Purpose**: Multi-session coordination (Agent Hub)

**Functions** (8 total):
1. `send_message_to_session` - Send message between sessions
2. `request_user_confirmation` - Ask user yes/no
3. `list_active_sessions` - Show all active calls
4. `schedule_callback` - Plan future action
5. `hangup_call` - End a session
6. `get_session_info` - Get session details
7. `suspend_session` - Pause session
8. `resume_session` - Resume session

**Architecture**: Up to 10 concurrent sessions, message routing

**Example**: "Tell the other call to hold on" → sends message to Session B

---

### 7. ConversationSearchAgent (Line 1527)
**Purpose**: Search past conversations

**Functions**:
- `search_conversations(query, limit)` - Search by keywords

**Database**: `conversations` table with FTS5 full-text search

**Example**: "What did we talk about last week?"

---

### 8. KIPPAgent (Line 1614)
**Purpose**: N8N workflow automation

**Functions**:
- `send_to_n8n(workflow_id, data)` - Trigger N8N workflows

**Integration**: HTTP POST to N8N webhook URLs

**Example**: "Add this to my CRM" → triggers N8N workflow

---

### 9. ProgrammerAgent (Line 1822) ⭐ NEW
**Purpose**: Code project management

**Functions** (4 total):
1. `manage_project` - list/create/open projects
2. `execute_terminal` - Run shell commands
3. `edit_code` - Create/edit/delete files with AI
4. `github_operation` - Git & GitHub operations

**Dependencies**: 
- `github_operations.py` - Git/GitHub wrapper
- `database.py` - `programming_operations` table

**Safety**: Destructive command detection, operation logging

**Example**: "Create a website and push to GitHub"

---

## ✨ How to Add a New Agent

### Step 1: Create Agent Class in `sub_agents_tars.py`

```python
class MyNewAgent(SubAgent):
    """Brief description of what it does."""
    
    def __init__(self, db: Database):
        super().__init__(
            name="my_agent",
            description="Handles XYZ tasks"
        )
        self.db = db
    
    async def execute(self, args: Dict[str, Any]) -> str:
        """Main execution method."""
        action = args.get('action', 'default')
        
        if action == 'do_something':
            return await self._do_something(args)
        else:
            return "Unknown action, sir."
    
    async def _do_something(self, args: Dict[str, Any]) -> str:
        """Internal helper method."""
        # Your logic here
        return "Success!"
```

**Location**: Add after line 3068 (end of ProgrammerAgent)

---

### Step 2: Register in `get_all_agents()` (Line ~3070)

```python
def get_all_agents(db: Database) -> Dict[str, SubAgent]:
    """Get all available sub-agents."""
    return {
        # ... existing agents ...
        "my_agent": MyNewAgent(db),  # ← Add this
    }
```

---

### Step 3: Add Function Declaration (Line ~2940)

```python
{
    "name": "my_function",
    "description": "Clear description for Gemini AI",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "What action to take"
            },
            "data": {
                "type": "STRING",
                "description": "Data for the action"
            }
        },
        "required": ["action"]
    }
}
```

---

### Step 4: Register Function in `main_tars.py`

In `_register_sub_agents()` method:

```python
function_map = {
    # ... existing mappings ...
    "my_function": agents.get("my_agent"),  # ← Add this
}
```

---

### Step 5: Add to Task Planner (Optional)

In `task_planner.py`, add category:

```python
self.function_categories = {
    # ... existing categories ...
    "my_category": ["my_function"],
}

self.priority_order = {
    # ... existing priorities ...
    "my_category": 7,
}
```

---

### Step 6: Add Database Tables (If Needed)

In `database.py` `init_database()`:

```python
cursor.execute('''
    CREATE TABLE IF NOT EXISTS my_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
''')
```

And add methods:

```python
def my_table_operation(self, data: str):
    """Do something with my_table."""
    pass
```

---

## 🔍 Key Integration Points

### Database (`database.py`)
- **SQLite** with tables for each feature
- Methods for CRUD operations
- Connection pooling handled automatically

### Config (`config.py`)
- Loads from `.env` file
- `Config` class with static properties
- `reload()` method for dynamic updates

### Gemini Client (`gemini_live_client.py`)
- Handles WebSocket connection
- Manages function call routing
- Audio streaming for voice

### Twilio (`twilio_media_streams.py`)
- Handles incoming calls
- Creates sessions
- Routes to Gemini

### Session Manager (`session_manager.py`)
- Tracks all active sessions
- Routes messages between sessions
- Manages session lifecycle

---

## 🎨 Code Style Guidelines

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `ProgrammerAgent`)
- **Functions**: `snake_case` (e.g., `manage_project`)
- **Constants**: `UPPER_CASE` (e.g., `MAX_TIMEOUT`)

### Return Format
Always return strings to Gemini:
```python
return "Success, sir."  # ✅ Good
return {"status": "ok"}  # ❌ Bad - Gemini expects string
```

### Async/Await
Use `async def` for all agent methods:
```python
async def execute(self, args: Dict[str, Any]) -> str:
    result = await self._helper()
    return result
```

### Error Handling
```python
try:
    # Your logic
    return "Success!"
except Exception as e:
    logger.error(f"Error: {e}")
    return f"Error: {str(e)}, sir."
```

### Logging
```python
import logging
logger = logging.getLogger(__name__)

logger.info("Operation started")
logger.error(f"Failed: {error}")
```

---

## 🧪 Testing New Agents

### 1. Unit Test (Python)
```python
# test_my_agent.py
import asyncio
from database import Database
from sub_agents_tars import MyNewAgent

async def test():
    db = Database("test.db")
    agent = MyNewAgent(db)
    result = await agent.execute({"action": "test"})
    print(result)

asyncio.run(test())
```

### 2. Integration Test (Call TARS)
1. Start TARS: `python3 main_tars.py`
2. Call your phone
3. Say: "Do my new thing"
4. Check logs for function call

### 3. Function Declaration Test
```python
# Check function is registered
from sub_agents_tars import get_function_declarations
funcs = get_function_declarations()
print([f['name'] for f in funcs])  # Should include 'my_function'
```

---

## 📊 Current System Metrics

- **Total Agents**: 9
- **Total Functions**: 20
- **Database Tables**: 8 (reminders, contacts, conversations, etc.)
- **Config Options**: ~30 environment variables
- **Max Concurrent Sessions**: 10
- **Function Call Timeout**: 30 seconds
- **Terminal Command Timeout**: 60 seconds

---

## 🚀 Common Extension Patterns

### Pattern 1: Simple Action Agent
```python
class CalculatorAgent(SubAgent):
    async def execute(self, args):
        operation = args.get('operation')
        if operation == 'add':
            result = args.get('a') + args.get('b')
            return f"Result: {result}, sir."
```

### Pattern 2: Database-backed Agent
```python
class NotesAgent(SubAgent):
    def __init__(self, db):
        super().__init__("notes", "Manage notes")
        self.db = db
    
    async def execute(self, args):
        if args.get('action') == 'save':
            self.db.save_note(args.get('content'))
            return "Note saved, sir."
```

### Pattern 3: External API Agent
```python
class WeatherAgent(SubAgent):
    async def execute(self, args):
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"api.weather.com/{args['city']}") as resp:
                data = await resp.json()
                return f"Temperature: {data['temp']}, sir."
```

---

## 📝 Quick Reference

### Find Agent Code
```bash
grep "class.*Agent" sub_agents_tars.py
```

### Find Function Declaration
```bash
grep -A 20 '"name": "function_name"' sub_agents_tars.py
```

### Check Function Registration
```bash
grep "function_name" main_tars.py
```

### View Database Schema
```bash
sqlite3 tars.db ".schema"
```

### Test Config Loading
```python
from config import Config
print(Config.GITHUB_TOKEN)
```

---

## 🎯 Next Steps After Reading This

1. ✅ Understand the 9 existing agents and their purposes
2. ✅ Know where to add new agent code
3. ✅ Know the 6 steps to add a new agent
4. ✅ Understand function declarations and routing
5. ✅ Ready to extend TARS with new capabilities!

---

**Questions? Check:**
- `PROGRAMMER_SETUP.md` - Programmer agent details
- `TARS.md` - Core concept
- `README.md` - Quick start

**Happy coding!** 🚀
