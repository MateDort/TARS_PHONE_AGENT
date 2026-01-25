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
- [System Architecture](#system-architecture)
- [User Flows](#user-flows)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [N8N Integration](#n8n-integration)
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

## 📖 Usage

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

### Project Structure

```
TARS_PHONE_AGENT/
├── main_tars.py              # Entry point and orchestration
├── config.py                 # Configuration management
├── database.py               # SQLite database operations
├── translations.py           # System prompts and personality
├── sub_agents_tars.py        # Sub-agent implementations
├── gemini_live_client.py     # Gemini Live Audio client
├── twilio_media_streams.py   # Twilio integration
├── session_manager.py        # Session lifecycle management
├── message_router.py         # Inter-session message routing
├── reminder_checker.py       # Background reminder service
├── messaging_handler.py      # Twilio-only messaging (deprecated)
├── task_planner.py          # Function call ordering
├── security.py              # Authentication and permissions
├── agent_session.py         # Session data models
├── requirements.txt          # Python dependencies
├── .env.example              # Configuration template
├── TARS.md                   # TARS personality reference
├── Máté.md                   # User information reference
├── N8N_SETUP.md             # N8N integration guide
└── README.md                # This file
```

### Core Components

#### SessionManager
- Manages all active Gemini Live sessions
- Handles session creation, termination, and resumption
- Implements permission-based access control
- Tracks sessions by phone number, call SID, and session name

#### MessageRouter
- Routes messages between active sessions
- Handles fallback delivery (SMS/call/email via N8N)
- Manages message queues and delivery tracking
- Supports broadcast and direct messaging

#### TaskPlanner
- Analyzes function call dependencies
- Orders functions for optimal execution
- Uses topological sorting for dependency resolution
- Categorizes functions by type (query, lookup, action, communication)

#### Sub-Agents
- **ConfigAgent** - Dynamic configuration management
- **ReminderAgent** - Reminder CRUD operations
- **ContactsAgent** - Contact management
- **N8NAgent** - N8N communication delegation
- **InterSessionAgent** - Multi-session coordination
- **OutboundCallAgent** - Goal-based calling

### Adding New Features

1. **Create SubAgent class** in `sub_agents_tars.py`:
   ```python
   class MyAgent(SubAgent):
       def __init__(self):
           super().__init__(
               name="my_agent",
               description="What this agent does"
           )
       
       async def execute(self, args: Dict[str, Any]) -> str:
           # Implementation
           return "Result"
   ```

2. **Add function declaration** in `get_function_declarations()`:
   ```python
   {
       "name": "my_function",
       "description": "Function description",
       "parameters": {
           "type": "OBJECT",
           "properties": {
               "param": {"type": "STRING", "description": "..."}
           },
           "required": ["param"]
       }
   }
   ```

3. **Register agent** in `get_all_agents()`:
   ```python
   agents["my_agent"] = MyAgent()
   ```

4. **Map function** in `main_tars.py`:
   ```python
   function_map = {
       "my_function": agents.get("my_agent"),
       # ...
   }
   ```

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

## 📚 Additional Documentation

- [N8N Setup Guide](N8N_SETUP.md) - Detailed N8N integration instructions
- [Environment Configuration](ENV_CONFIGURATION.md) - Complete configuration reference
- [Config Commands](CONFIG_COMMANDS.md) - Runtime configuration commands
- [Integration Guide](INTEGRATION_GUIDE.md) - Developer integration examples
- [Goal Calling Guide](GOAL_CALLING_GUIDE.md) - Goal-based calling examples

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

**Version**: 2.0  
**Last Updated**: January 2026

---

<div align="center">

**Built with ❤️ for intelligent personal assistance**

</div>
