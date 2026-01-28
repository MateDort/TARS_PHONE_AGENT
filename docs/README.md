# TARS - Personal AI Assistant

<div align="center">

**A sophisticated AI personal assistant powered by Google Gemini Live Audio with intelligent task planning, multi-session management, and seamless N8N integration.**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Personal%20Use-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-success.svg)]()

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Documentation](#documentation)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

**TARS** is an intelligent personal assistant that combines:
- **Natural voice conversations** via Google Gemini Live Audio
- **Phone call management** through Twilio Media Streams
- **Task automation** with intelligent function call planning
- **Multi-session coordination** for concurrent conversations
- **External automation** via N8N for email, messaging, and calendar

TARS maintains a British, respectful personality that can be dynamically adjusted, manages your contacts and reminders locally, and delegates communication tasks to N8N for seamless integration with Gmail, Telegram, Discord, and Calendar services.

---

## 🚀 Quick Start

### For Users
1. **First Time**: Follow [Installation](#installation)
2. **Usage Guide**: See [Usage Examples](#usage-examples)
3. **Troubleshooting**: Check [Troubleshooting](#troubleshooting)

### For Developers
1. **Understanding the System**: Read [ARCHITECTURE.md](ARCHITECTURE.md) - Complete system organization
2. **Agent Reference**: See [AGENTS_REFERENCE.md](AGENTS_REFERENCE.md) - All 20 functions explained
3. **Adding Features**: Follow [ARCHITECTURE.md - How to Add a New Agent](ARCHITECTURE.md#-how-to-add-a-new-agent)
4. **Programmer Agent**: See [PROGRAMMER_SETUP.md](PROGRAMMER_SETUP.md) - Code management capabilities

---

## 📚 Documentation

### Core Documentation
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System organization, file structure, how agents work
- **[AGENTS_REFERENCE.md](AGENTS_REFERENCE.md)** - Quick reference for all 9 agents and 20 functions
- **[PROGRAMMER_SETUP.md](PROGRAMMER_SETUP.md)** - Terminal access, file operations, GitHub integration
- **[BUGFIXES.md](BUGFIXES.md)** - Recent bug fixes and solutions

### Setup Guides
- **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)** - Developer integration examples
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Implementation details

### Reference
- **[TARS.md](TARS.md)** - TARS personality definition
- **[Máté.md](Máté.md)** - User information reference

---

## ✨ Features

### Core Capabilities
- 🎤 **Natural Voice Conversations** - Real-time audio processing with Google Gemini 2.5 Flash Native Audio
- 📞 **Phone Call Management** - Inbound/outbound calls with goal-based task execution
- 🔔 **Smart Reminders** - Automatic phone calls, emails, or messages for scheduled tasks
- 👥 **Contact Management** - Local database for contacts with birthdays and relationship tracking
- ⚙️ **Dynamic Personality** - Adjustable humor (0-100%) and honesty (0-100%) levels on-the-fly
- 🔍 **Google Search Integration** - Real-time information retrieval for weather, news, and current events
- 🧠 **Intelligent Task Planning** - Automatic function call ordering based on dependencies
- 🔄 **Multi-Session Management** - Concurrent conversations with inter-session messaging
- 🔗 **N8N Integration** - Delegated communication tasks (email, SMS, Telegram, Discord, Calendar)

### Advanced Features
- **Session Persistence** - Resume conversations after disconnection
- **Permission-Based Access** - Full access for authenticated users, limited for unknown callers
- **Conversation Search** - Semantic and date-based conversation retrieval
- **Call Summaries** - AI-generated summaries of completed calls
- **Goal-Based Calling** - Make calls with specific objectives (appointments, inquiries, follow-ups)
- **🆕 Programmer Agent** - Terminal access, file operations, GitHub integration, project management

### Agent System (20 Functions)
TARS uses a modular agent system with 9 specialized agents:

| Agent | Functions | Purpose |
|-------|-----------|---------|
| **ConfigAgent** | 1 | Adjust personality settings |
| **ReminderAgent** | 1 | Time-based reminders |
| **ContactsAgent** | 1 | Phone number lookup |
| **NotificationAgent** | 1 | Send SMS/WhatsApp |
| **OutboundCallAgent** | 1 | Initiate calls |
| **InterSessionAgent** | 8 | Multi-session coordination |
| **ConversationSearchAgent** | 1 | Search past conversations |
| **KIPPAgent** | 1 | N8N workflow triggers |
| **ProgrammerAgent** ⭐ | 4 | Code & GitHub operations |

**[→ See all functions in AGENTS_REFERENCE.md](AGENTS_REFERENCE.md)**

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         TARS System                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐         ┌──────────────┐                    │
│  │   Twilio     │─────────▶│   Flask      │                    │
│  │   Phone      │         │   Webhooks   │                    │
│  │   Calls      │         │   (Port 5002) │                    │
│  └──────┬───────┘         └──────┬───────┘                    │
│         │                        │                             │
│         │ Media Streams          │                             │
│         ▼                        ▼                             │
│  ┌──────────────────────────────────────────┐                  │
│  │      TwilioMediaStreamsHandler           │                  │
│  │  - WebSocket connection management        │                  │
│  │  - Audio stream processing               │                  │
│  └──────────────┬───────────────────────────┘                  │
│                 │                                               │
│                 ▼                                               │
│  ┌──────────────────────────────────────────┐                  │
│  │         SessionManager                    │                  │
│  │  - Session lifecycle management           │                  │
│  │  - Permission-based access control       │                  │
│  │  - Session naming and routing             │                  │
│  └──────────────┬───────────────────────────┘                  │
│                 │                                               │
│                 ▼                                               │
│  ┌──────────────────────────────────────────┐                  │
│  │      GeminiLiveClient                     │                  │
│  │  - Voice conversation processing          │                  │
│  │  - Function call handling                 │                  │
│  │  - Task planning integration              │                  │
│  └──────────────┬───────────────────────────┘                  │
│                 │                                               │
│                 ▼                                               │
│  ┌──────────────────────────────────────────┐                  │
│  │         TaskPlanner                       │                  │
│  │  - Dependency analysis                   │                  │
│  │  - Function call ordering                │                  │
│  └──────────────┬───────────────────────────┘                  │
│                 │                                               │
│                 ▼                                               │
│  ┌──────────────────────────────────────────┐                  │
│  │         Sub-Agents                        │                  │
│  │  ┌──────────┐  ┌──────────┐  ┌────────┐ │                  │
│  │  │ Config   │  │ Reminder │  │Contact │ │                  │
│  │  │ Agent    │  │  Agent   │  │ Agent  │ │                  │
│  │  └──────────┘  └──────────┘  └────────┘ │                  │
│  │  ┌──────────┐  ┌──────────┐  ┌────────┐ │                  │
│  │  │  N8N     │  │Inter-Sess│  │Outbound│ │                  │
│  │  │  Agent   │  │  Agent   │  │  Call  │ │                  │
│  │  └────┬─────┘  └──────────┘  └────────┘ │                  │
│  └───────┼──────────────────────────────────┘                  │
│          │                                                      │
│          ▼                                                      │
│  ┌──────────────────────────────────────────┐                  │
│  │         MessageRouter                    │                  │
│  │  - Inter-session message routing         │                  │
│  │  - Fallback delivery (SMS/call/email)    │                  │
│  └──────────────┬───────────────────────────┘                  │
│                 │                                               │
│                 ▼                                               │
│  ┌──────────────────────────────────────────┐                  │
│  │         SQLite Database                   │                  │
│  │  - Contacts, Reminders, Conversations    │                  │
│  │  - Configuration persistence             │                  │
│  └──────────────────────────────────────────┘                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    External Services                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐         ┌──────────────┐                    │
│  │     N8N      │◀────────│   TARS       │                    │
│  │  Automation  │         │  (HTTP POST) │                    │
│  │              │────────▶│              │                    │
│  │  - Gmail     │         │  (Webhook)   │                    │
│  │  - Telegram  │         │              │                    │
│  │  - Discord   │         └──────────────┘                    │
│  │  - Calendar  │                                              │
│  └──────────────┘                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 User Flows

### Flow 1: Incoming Phone Call

```
User Calls TARS
      │
      ▼
┌─────────────────┐
│  Twilio Receives│
│  Incoming Call  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Flask Webhook  │
│  /webhook/voice │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  TwilioMedia    │
│  StreamsHandler │
│  Creates        │
│  WebSocket      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SessionManager │
│  - Authenticates│
│  - Creates      │
│    Session      │
│  - Sets         │
│    Permissions  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GeminiLive     │
│  Client         │
│  - Connects     │
│  - Processes    │
│    Audio        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  User Speaks     │
│  "Set reminder   │
│   for 3pm"      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Gemini         │
│  Generates      │
│  Function Call  │
│  manage_reminder│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  TaskPlanner    │
│  - Analyzes     │
│  - Orders       │
│    Functions    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ReminderAgent  │
│  Executes       │
│  - Creates      │
│    Reminder     │
│  - Saves to DB  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Response       │
│  "Reminder set  │
│   for 3pm, sir" │
└─────────────────┘
```

### Flow 2: Complex Task with Multiple Functions

```
User: "Call Helen and ask if she wants to meet for dinner, 
       then send me an email with the details"
      │
      ▼
┌─────────────────┐
│  Gemini         │
│  Identifies     │
│  Multiple       │
│  Functions:     │
│  1. lookup_     │
│     contact     │
│  2. make_goal_ │
│     call        │
│  3. send_to_n8n │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  TaskPlanner    │
│  Analyzes       │
│  Dependencies:  │
│  - lookup_      │
│    contact      │
│    (needed for  │
│    make_goal_    │
│    call)        │
│  - make_goal_   │
│    call         │
│    (must        │
│    complete     │
│    first)       │
│  - send_to_n8n  │
│    (depends on  │
│    call result) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Execution      │
│  Order:         │
│  1. lookup_     │
│     contact     │
│     → Gets      │
│     Helen's #   │
│  2. make_goal_  │
│     call        │
│     → Calls     │
│     Helen       │
│  3. send_to_n8n │
│     → Sends     │
│     email       │
└─────────────────┘
```

### Flow 3: N8N Communication Flow

```
TARS → N8N Communication
      │
      ▼
┌─────────────────┐
│  User: "Send    │
│  email to John │
│  about meeting" │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Gemini Calls   │
│  send_to_n8n()  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  N8NAgent       │
│  - Formats      │
│    message      │
│  - HTTP POST    │
│    to N8N       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  N8N Workflow   │
│  - Receives     │
│    webhook      │
│  - AI Agent     │
│    parses       │
│  - Selects      │
│    Gmail tool   │
│  - Sends email  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Response       │
│  "Email sent,   │
│   sir"          │
└─────────────────┘

N8N → TARS Communication
      │
      ▼
┌─────────────────┐
│  N8N Workflow   │
│  Determines     │
│  TARS needs to  │
│  do something   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  HTTP POST      │
│  to /webhook/   │
│  n8n            │
│  {"message":    │
│   "call helen"} │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Flask Webhook  │
│  Handler        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  SessionManager │
│  Creates        │
│  "Mate_n8n"     │
│  Session        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GeminiLive     │
│  Processes      │
│  Task           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Auto-closes    │
│  after 1 min    │
│  inactivity     │
└─────────────────┘
```

### Flow 4: Multi-Session Coordination

```
┌─────────────────────────────────────────────────────────────┐
│                    Active Sessions                           │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Call with Máté   │  │ Call with Helen  │                │
│  │ (main)           │  │                  │                │
│  │ [Full Access]    │  │ [Goal: Dinner]   │                │
│  └────────┬─────────┘  └────────┬─────────┘                │
│           │                      │                         │
│           │                      │                         │
│           │  "Does 7pm work?"    │                         │
│           │◀─────────────────────│                         │
│           │                      │                         │
│           │                      │                         │
│           │  MessageRouter       │                         │
│           │  Routes Message      │                         │
│           │                      │                         │
│           ▼                      │                         │
│  ┌──────────────────┐            │                         │
│  │ User Responds    │            │                         │
│  │ "Yes, perfect!"   │            │                         │
│  └────────┬─────────┘            │                         │
│           │                      │                         │
│           │  "7pm confirmed"     │                         │
│           │──────────────────────▶│                         │
│           │                      │                         │
│           │                      ▼                         │
│           │            ┌──────────────────┐                │
│           │            │ Helen Session    │                │
│           │            │ Confirms 7pm     │                │
│           │            │ with Restaurant  │                │
│           │            └──────────────────┘                │
│           │                                                 │
└───────────┼─────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────┐
│  Call Completes  │
│  Summary Sent    │
│  to Máté         │
└──────────────────┘
```

---

## 🚀 Installation

### Prerequisites

- **Python 3.9+**
- **Twilio Account** with phone number
- **Google Gemini API Key** ([Get one here](https://makersuite.google.com/app/apikey))
- **N8N Instance** (self-hosted or cloud)
- **ngrok** (for local development)

### Step-by-Step Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd TARS_PHONE_AGENT
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your credentials:
   ```env
   # Twilio Configuration
   TWILIO_ACCOUNT_SID=your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_PHONE_NUMBER=+1234567890
   TARGET_PHONE_NUMBER=+1987654321
   
   # Gemini Configuration
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_VOICE=Puck
   
   # N8N Integration
   N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/tars
   N8N_TARS_WEBHOOK_URL=http://your-tars-instance.com/webhook/n8n
   
   # Webhook Configuration
   WEBHOOK_BASE_URL=https://your-ngrok-url.ngrok.io
   WEBSOCKET_URL=wss://your-other-ngrok-url.ngrok.io
   ```

4. **Set up ngrok tunnels**
   ```bash
   # Terminal 1: Webhook server
   ngrok http 5002
   
   # Terminal 2: WebSocket server
   ngrok http 5001
   ```
   
   Update `.env` with the ngrok URLs.

5. **Configure Twilio webhooks**
   - Go to [Twilio Console](https://console.twilio.com) → Phone Numbers
   - Select your number
   - Set "A Call Comes In" → `https://your-ngrok-url.ngrok.io/webhook/voice`
   - Set "A Message Comes In" → `https://your-ngrok-url.ngrok.io/webhook/sms`

6. **Set up N8N integration**
   - See [N8N_SETUP.md](N8N_SETUP.md) for detailed instructions
   - Create workflow to receive tasks from TARS
   - Configure N8N → TARS webhook for task delegation

7. **Run TARS**
   ```bash
   python main_tars.py
   ```

### Background Workers (Optional - For Autonomous Programming)

For autonomous programming tasks that can run for 10-15 minutes in the background, you'll need Redis and a worker process:

1. **Install Redis**:
   ```bash
   # macOS
   brew install redis
   brew services start redis
   
   # Ubuntu/Debian
   sudo apt install redis-server
   sudo systemctl start redis
   
   # Verify Redis is running
   redis-cli ping  # Should respond with "PONG"
   ```

2. **Configure background tasks in `.env`**:
   ```env
   # Redis Configuration
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_DB=0
   
   # Background Task Settings
   MAX_TASK_RUNTIME_MINUTES=15
   ENABLE_DETAILED_UPDATES=true  # Send detailed updates for every action
   
   # Discord Updates (N8N webhook for background task progress)
   # Discord updates route through main N8N_WEBHOOK_URL (KIPP)
   ```

3. **Start the background worker** (in a separate terminal):
   ```bash
   python3 start_worker.py
   ```
   
   You should see:
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
   ```

4. **Run TARS** (in your main terminal):
   ```bash
   python3 main_tars.py
   ```

The worker will process autonomous coding tasks in the background while TARS remains responsive to other requests. See [BACKGROUND_PROGRAMMING.md](BACKGROUND_PROGRAMMING.md) for detailed usage.

**Note**: If you don't need autonomous programming features, you can skip the Redis/worker setup. All other TARS features work without it.

---

## ⚙️ Configuration

### Environment Variables

#### Required
- `TWILIO_ACCOUNT_SID` - Twilio account identifier
- `TWILIO_AUTH_TOKEN` - Twilio authentication token
- `TWILIO_PHONE_NUMBER` - Your Twilio phone number
- `TARGET_PHONE_NUMBER` - Your personal phone number (for authentication)
- `GEMINI_API_KEY` - Google Gemini API key
- `N8N_WEBHOOK_URL` - N8N webhook endpoint for TARS → N8N
- `N8N_TARS_WEBHOOK_URL` - TARS webhook endpoint for N8N → TARS

#### Optional (with defaults)
- `GEMINI_VOICE` - Voice selection: `Puck`, `Kore`, or `Charon` (default: `Puck`)
- `HUMOR_PERCENTAGE` - 0-100 (default: `70`)
- `HONESTY_PERCENTAGE` - 0-100 (default: `95`)
- `PERSONALITY` - `chatty`, `normal`, `brief` (default: `normal`)
- `NATIONALITY` - Nationality string (default: `British`)
- `REMINDER_DELIVERY` - `call`, `message`, `email`, `both` (default: `call`)
- `CALLBACK_REPORT` - `call`, `message`, `email`, `both` (default: `call`)

### Dynamic Configuration

TARS supports runtime configuration changes without restart:

**Via Voice Command:**
- "Set humor to 75%"
- "Set honesty to 90%"
- "Set personality to brief"
- "What's my humor percentage?"

**How it works:**
1. ConfigAgent updates `.env` file
2. Config class reloads values
3. System instruction regenerates
4. Changes take effect immediately

---

## 💡 Usage Examples

### Phone Call Interactions

**Basic Conversation:**
```
You: "What time is it?"
TARS: "It's currently 3:45 PM on Saturday, January 24th, 2026, sir."
```

**Reminder Management:**
```
You: "Remind me to call Helen tomorrow at 2pm"
TARS: "Reminder set for tomorrow at 2:00 PM to call Helen, sir."
```

**Contact Lookup:**
```
You: "What's Helen's phone number?"
TARS: "Helen's phone number is (404) 556-5930, sir."
```

**Goal-Based Calling:**
```
You: "Call the dentist to book an appointment for Wednesday at 2pm"
TARS: "Understood, sir. I'll ring the dentist now to book that appointment..."
```

### Communication via N8N

**Email:**
```
You: "Send email to john@example.com about the meeting"
TARS: "I've sent your request to N8N, sir. Email sent successfully."
```

**Telegram:**
```
You: "Send telegram message to Helen saying hello"
TARS: "I've sent your request to N8N, sir. Telegram message sent."
```

**Calendar:**
```
You: "Check my calendar for tomorrow"
TARS: "I've sent your request to N8N, sir. Calendar checked."
```

### Multi-Session Scenarios

**Concurrent Calls:**
```
Active Sessions:
- Call with Máté (main) [Full Access]
- Call with Helen [Goal: Dinner Plans]
- Call with Barber Shop [Goal: Appointment]

TARS can coordinate between sessions:
- Barber session asks Máté session: "Does 7pm work instead of 6pm?"
- Máté responds: "Yes, perfect!"
- Barber session confirms with barber
```

### Programmer Agent Examples 🆕

**Project Management:**
```
You: "List my projects"
TARS: "You have 31 projects: TARS_PHONE_AGENT, Simple Portfolio, ada_v2..."

You: "Create a portfolio website"
TARS: "Created vanilla-js project 'portfolio' at /Users/matedort/portfolio, sir."
```

**File Operations:**
```
You: "Create an index.html with Hello World"
TARS: "Created file index.html, sir."

You: "Run npm install in my website"
TARS: "Command executed successfully..."
```

**GitHub Integration:**
```
You: "Push to GitHub as my-portfolio-repo"
TARS: "Repository created and pushed to GitHub, sir."
```

**[→ See full programmer guide in PROGRAMMER_SETUP.md](PROGRAMMER_SETUP.md)**

---

## 🔗 N8N Integration

### What N8N Handles

N8N manages all communication tasks:
- **Gmail** - Send emails, check calendar, manage email operations
- **Telegram** - Send messages via Telegram
- **Discord** - Send messages to Discord channels
- **Calendar** - Check calendar events, schedule items

### How It Works

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│    TARS     │────────▶│     N8N     │────────▶│   Gmail/    │
│             │  HTTP   │  Workflow   │         │  Telegram/   │
│  send_to_n8n│  POST   │  - Parses   │         │  Discord/    │
│  ("send     │         │  - Routes   │         │  Calendar    │
│   email...")│         │  - Executes │         │              │
└─────────────┘         └─────────────┘         └─────────────┘
```

**TARS → N8N:**
- TARS sends natural language message: `"send email to john@example.com about meeting"`
- N8N's AI agent determines tool (Gmail) and extracts details
- N8N executes action and returns status

**N8N → TARS:**
- N8N sends task: `{"message": "call helen"}`
- TARS creates "Mate_n8n" session
- Processes task through Gemini Live
- Auto-closes after 1 minute of inactivity

See [N8N_SETUP.md](N8N_SETUP.md) for detailed setup instructions.

---

## 🛠️ Development

### Understanding the Codebase

**Start Here:**
1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete file organization and agent system explained
2. **[AGENTS_REFERENCE.md](AGENTS_REFERENCE.md)** - All 20 functions with examples
3. **[PROGRAMMER_SETUP.md](PROGRAMMER_SETUP.md)** - Newest agent features

### Quick File Guide

**Core System**
- `main_tars.py` - Entry point, orchestration
- `config.py` - Environment variable management
- `database.py` - SQLite operations (8 tables)
- `security.py` - Phone number authentication

**AI & Communication**
- `gemini_live_client.py` - Gemini Live Audio integration
- `twilio_media_streams.py` - Twilio voice call handling
- `task_planner.py` - Function call ordering

**Agent System**
- `sub_agents_tars.py` - ALL 9 agents (3,069 lines)
- `github_operations.py` - Git/GitHub operations for programmer agent
- `agent_session.py` - Session state per call
- `session_manager.py` - Multi-session coordination

**Messaging & Background**
- `message_router.py` - Inter-session message routing
- `messaging_handler.py` - Twilio SMS/WhatsApp
- `reminder_checker.py` - Background reminder polling

### Adding New Agents

**Complete 6-Step Guide:** See [ARCHITECTURE.md - How to Add a New Agent](ARCHITECTURE.md#-how-to-add-a-new-agent)

**Quick Summary:**
1. Create agent class in `sub_agents_tars.py`
2. Register in `get_all_agents()`
3. Add function declaration in `get_function_declarations()`
4. Map in `main_tars.py` `_register_sub_agents()`
5. (Optional) Add to `task_planner.py` categories
6. (Optional) Add database tables in `database.py`

**Example Code:** See [ARCHITECTURE.md - Extension Patterns](ARCHITECTURE.md#-common-extension-patterns)

---

## 🐛 Troubleshooting

### Common Issues

**TARS can't connect to Gemini:**
- Verify `GEMINI_API_KEY` is valid
- Check internet connection
- Review logs for API errors

**No phone calls received:**
- Verify Twilio webhooks are configured
- Ensure ngrok tunnels are running
- Check Flask server is running on port 5002
- Verify `WEBHOOK_BASE_URL` matches ngrok URL

**Reminders not triggering:**
- Check reminder is active in database
- Verify `REMINDER_CHECK_INTERVAL` is set correctly
- Review `reminder_checker.py` logs
- Ensure timezone settings are correct

**N8N integration not working:**
- Verify `N8N_WEBHOOK_URL` is correct and accessible
- Check N8N workflow is active
- Review N8N execution logs
- Ensure `N8N_TARS_WEBHOOK_URL` is publicly accessible

**Function calls not executing:**
- Check TaskPlanner logs for ordering issues
- Verify function is registered in `function_map`
- Review sub-agent implementation
- Check permission levels for function access

### Debug Mode

Enable detailed logging:
```env
LOG_LEVEL=DEBUG
ENABLE_DEBUG_LOGGING=true
```

---

## 📚 Full Documentation Index

### 📖 For Users
- **[README.md](README.md)** ← You are here
- **[PROGRAMMER_SETUP.md](PROGRAMMER_SETUP.md)** - Terminal, files, GitHub
- **[BUGFIXES.md](BUGFIXES.md)** - Recent fixes and solutions

### 🏗️ For Developers
- **[ARCHITECTURE.md](ARCHITECTURE.md)** ⭐ - System organization (START HERE)
- **[AGENTS_REFERENCE.md](AGENTS_REFERENCE.md)** ⭐ - All 20 functions explained
- **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)** - Integration examples
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Implementation details

### 📚 Reference
- **[TARS.md](TARS.md)** - Personality definition
- **[Máté.md](Máté.md)** - User information

---

## 🎭 About TARS

TARS is designed with a British, respectful personality that:
- Addresses you as "sir" or "Máté"
- Maintains wit while staying professional
- Adapts humor and honesty based on your preferences
- Supports your goals and disciplined lifestyle

Personality is defined in `TARS.md` and user information in `Máté.md`, both loaded into the system prompt at initialization.

---

## 🔧 Technology Stack

- **Google Gemini 2.5 Flash** - Native audio processing and AI
- **Twilio** - Phone calls and media streams
- **N8N** - Workflow automation for communications
- **Python 3.9+** - Core language
- **SQLite** - Local data storage
- **Flask** - Webhook server
- **WebSockets** - Real-time audio streaming

---

## 📝 License

Personal Use

---

**Version**: 0.4.0 (Programmer Agent Update)  
**Last Updated**: January 26, 2026

---

<div align="center">

**Built with ❤️ for intelligent personal assistance**

</div>
