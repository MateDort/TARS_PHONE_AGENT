# 🚀 START HERE - TARS Guide

**Welcome to TARS!** This guide will get you oriented quickly.

---

## 👋 First Time Here?

### I want to USE TARS
1. Read [README.md](README.md) - Installation & Setup
2. Configure `.env` with your API keys
3. Run `python3 main_tars.py`
4. Call your Twilio number!

### I want to UNDERSTAND TARS
1. Read [ARCHITECTURE.md](ARCHITECTURE.md) - How everything works
2. Browse [AGENTS_REFERENCE.md](AGENTS_REFERENCE.md) - What TARS can do
3. Check [PROGRAMMER_SETUP.md](PROGRAMMER_SETUP.md) - Newest features

### I want to EXTEND TARS
1. Study [ARCHITECTURE.md - How to Add a New Agent](ARCHITECTURE.md#-how-to-add-a-new-agent)
2. Look at existing agents in `sub_agents_tars.py`
3. Follow the 6-step guide to add your agent
4. Test and iterate!

---

## 📚 Documentation Map

```
START_HERE.md (you are here)
    │
    ├─── For Users ──────────────────┐
    │    ├── README.md               │ Setup & usage
    │    ├── PROGRAMMER_SETUP.md     │ Code features
    │    └── BUGFIXES.md             │ Known issues
    │
    ├─── For Developers ─────────────┐
    │    ├── ARCHITECTURE.md         │ System design ⭐
    │    ├── AGENTS_REFERENCE.md     │ All functions ⭐
    │    ├── INTEGRATION_GUIDE.md    │ Examples
    │    └── IMPLEMENTATION_SUMMARY.md │ Details
    │
    └─── Reference ──────────────────┐
         ├── ORGANIZATION_SUMMARY.md │ What was organized
         ├── TARS.md                 │ Personality
         └── Máté.md                 │ User info
```

---

## 🗺️ Quick Navigation

### Find a Function
```
AGENTS_REFERENCE.md
→ Table at top lists all 20 functions
→ Find your function
→ See line number and examples
```

### Understand Agent System
```
ARCHITECTURE.md
→ Section: "Agent System Architecture"
→ See all 9 agents with purposes
→ Line numbers for code location
```

### Add a New Feature
```
ARCHITECTURE.md
→ Section: "How to Add a New Agent"
→ Follow 6 steps
→ See code examples
→ Test and deploy!
```

### Debug an Issue
```
BUGFIXES.md
→ Recent fixes and solutions
→ Common problems
→ GitHub authentication
```

---

## 🤖 TARS Capabilities (20 Functions)

### 📞 Communication (5)
- Call people with goals
- Send SMS/WhatsApp
- Look up contacts
- Search past conversations
- Get current time

### ⏰ Task Management (2)
- Set reminders
- Schedule callbacks

### 🔧 Configuration (1)
- Adjust personality

### 🤝 Multi-Session (8)
- Message between calls
- Manage active sessions
- Suspend/resume calls
- Request confirmations
- And more...

### 💻 Programming (4) ⭐ NEW
- Manage projects
- Run terminal commands
- Edit code files
- GitHub operations

---

## 📂 File Organization

### Core System Files
```
main_tars.py           - Application entry point
config.py              - Configuration management
database.py            - SQLite operations
security.py            - Authentication
```

### AI & Communication
```
gemini_live_client.py  - Gemini API
twilio_media_streams.py - Twilio integration
task_planner.py        - Function ordering
translations.py        - System prompts
```

### Agent System
```
sub_agents_tars.py     - ALL 9 agents (3,069 lines)
agent_session.py       - Session state
session_manager.py     - Multi-session coordination
github_operations.py   - Git/GitHub wrapper
```

### Messaging & Background
```
message_router.py      - Inter-session messaging
messaging_handler.py   - Twilio SMS
reminder_checker.py    - Background reminders
```

---

## 🎯 Common Tasks

### Test GitHub Integration
```bash
python3 test_github_complete.py
```

### Check Database
```bash
sqlite3 tars.db ".schema"
sqlite3 tars.db "SELECT * FROM reminders;"
```

### View Configuration
```python
from config import Config
print(f"Humor: {Config.HUMOR_PERCENTAGE}%")
print(f"Token: {len(Config.GITHUB_TOKEN)} chars")
```

### Find Agent Code
```bash
grep "^class \w*Agent" sub_agents_tars.py
```

---

## 💡 Examples

### Using TARS (Voice)
```
You: "Remind me to call mom at 3pm"
TARS: "Reminder set for 3:00 PM, sir."

You: "Create a portfolio website"
TARS: "Created project 'portfolio', sir."

You: "Push to GitHub"
TARS: "Pushed to GitHub successfully, sir."
```

### Adding an Agent (Code)
```python
# 1. Create agent in sub_agents_tars.py
class WeatherAgent(SubAgent):
    def __init__(self, db):
        super().__init__("weather", "Get weather info")
        self.db = db
    
    async def execute(self, args):
        city = args.get('city')
        # Get weather API data...
        return f"Weather in {city}: Sunny, 75°F"

# 2. Register in get_all_agents()
"weather": WeatherAgent(db),

# 3. Add function declaration
{
    "name": "get_weather",
    "description": "Get current weather",
    "parameters": {...}
}

# 4. Map in main_tars.py
"get_weather": agents.get("weather"),

# Done! Now TARS can get weather!
```

---

## 🔥 What's New

### Version 0.4.0 (January 2026)
- ✨ **Programmer Agent** - Terminal, files, GitHub
- 📚 **Complete Documentation** - Architecture & reference guides
- 🏗️ **Organized Structure** - Clear file organization
- 🐛 **Bug Fixes** - File creation, GitHub auth, confirmations

---

## ❓ FAQ

**Q: Where do I start?**  
A: User? → README.md. Developer? → ARCHITECTURE.md

**Q: How do I add a function?**  
A: See ARCHITECTURE.md section "How to Add a New Agent"

**Q: Where are all the agents?**  
A: In `sub_agents_tars.py` - line numbers in ARCHITECTURE.md

**Q: How do I test changes?**  
A: Run `python3 main_tars.py` and call your phone

**Q: What's the newest feature?**  
A: Programmer Agent! See PROGRAMMER_SETUP.md

**Q: How do I find a function?**  
A: Check AGENTS_REFERENCE.md - all 20 functions listed

---

## 🎓 Learning Path

### Day 1: Overview
- Read README.md
- Try using TARS
- Explore basic features

### Day 2: Deep Dive
- Read ARCHITECTURE.md
- Browse AGENTS_REFERENCE.md
- Understand the agent system

### Day 3: Hands-On
- Read existing agent code
- Follow "Add Agent" guide
- Create a simple test agent

### Day 4+: Build!
- Design your feature
- Implement your agent
- Test and iterate
- Share with the world!

---

## 🚀 Ready to Go!

You now know:
- ✅ Where all documentation is
- ✅ How to navigate the codebase
- ✅ What TARS can do (20 functions)
- ✅ How to add new features
- ✅ Where to find help

**Pick your path:**
- 👤 **User**: Go to [README.md](README.md)
- 👨‍💻 **Developer**: Go to [ARCHITECTURE.md](ARCHITECTURE.md)
- 🔍 **Explorer**: Go to [AGENTS_REFERENCE.md](AGENTS_REFERENCE.md)

---

**Need help?** Check the relevant documentation file or search the code!

**Happy TARS-ing!** 🎉
