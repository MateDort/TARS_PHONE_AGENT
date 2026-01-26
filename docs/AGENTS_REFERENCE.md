# TARS Agents Quick Reference

**Quick lookup for all agents and their functions**

---

## 📋 All 20 Functions at a Glance

| # | Function | Agent | What It Does | Example |
|---|----------|-------|--------------|---------|
| 1 | `adjust_config` | Config | Change humor/honesty | "Be more serious" |
| 2 | `manage_reminder` | Reminder | Create/list reminders | "Remind me at 3pm" |
| 3 | `lookup_contact` | Contacts | Find phone numbers | "What's mom's number?" |
| 4 | `send_notification` | Notification | Send SMS/WhatsApp | "Text John I'm late" |
| 5 | `make_goal_call` | OutboundCall | Initiate calls | "Call dad" |
| 6 | `send_message_to_session` | InterSession | Message other calls | "Tell other call to wait" |
| 7 | `request_user_confirmation` | InterSession | Ask yes/no | "Should I proceed?" |
| 8 | `list_active_sessions` | InterSession | Show all calls | "Who am I talking to?" |
| 9 | `schedule_callback` | InterSession | Plan future action | "Call me back in 10 min" |
| 10 | `hangup_call` | InterSession | End session | "Hang up on the other call" |
| 11 | `get_session_info` | InterSession | Get call details | "Info on session 2" |
| 12 | `suspend_session` | InterSession | Pause session | "Put session 2 on hold" |
| 13 | `resume_session` | InterSession | Resume session | "Resume session 2" |
| 14 | `search_conversations` | ConversationSearch | Search past talks | "What did we discuss?" |
| 15 | `send_to_n8n` | KIPP | Trigger workflows | "Add to CRM" |
| 16 | `manage_project` | Programmer | List/create projects | "Create a website" |
| 17 | `execute_terminal` | Programmer | Run commands | "Run npm install" |
| 18 | `edit_code` | Programmer | Create/edit files | "Add index.html" |
| 19 | `github_operation` | Programmer | Git operations | "Push to GitHub" |
| 20 | `get_current_time` | Utility | Get time/date | "What time is it?" |

---

## 🎯 Agent 1: ConfigAgent

**Purpose**: Adjust TARS's personality  
**Line**: 17 in `sub_agents_tars.py`

### Functions

#### `adjust_config(setting, value)`
**Parameters**:
- `setting`: "humor" or "honesty"  
- `value`: 0-100 (percentage)

**Examples**:
```
"Make yourself funnier" → humor: 90
"Be more honest" → honesty: 100
"Dial down the jokes" → humor: 30
```

**Database**: Updates `config` table and `Config` class

---

## 🎯 Agent 2: ReminderAgent

**Purpose**: Time-based reminders  
**Line**: 276 in `sub_agents_tars.py`

### Functions

#### `manage_reminder(action, ...)`
**Parameters**:
- `action`: "create" | "list" | "complete" | "delete"
- `task`: What to remind about
- `reminder_time`: When to remind (natural language)
- `reminder_id`: For complete/delete

**Examples**:
```
"Remind me to call mom at 3pm"
"Show my reminders"
"Mark reminder 5 as done"
"Delete the 3pm reminder"
```

**Database**: `reminders` table  
**Background**: `reminder_checker.py` polls every 30 seconds

---

## 🎯 Agent 3: ContactsAgent

**Purpose**: Phone number lookup  
**Line**: 559 in `sub_agents_tars.py`

### Functions

#### `lookup_contact(name)`
**Parameters**:
- `name`: Contact name (fuzzy matched)

**Examples**:
```
"What's mom's number?" → +36202351624
"Call John" → looks up John's number
"Text Sarah" → finds Sarah's contact
```

**Database**: `contacts` table  
**Matching**: Uses `difflib` for fuzzy name matching

---

## 🎯 Agent 4: NotificationAgent

**Purpose**: Send text messages  
**Line**: 803 in `sub_agents_tars.py`

### Functions

#### `send_notification(contact, message, channel)`
**Parameters**:
- `contact`: Contact name or phone number
- `message`: Text to send
- `channel`: "sms" or "whatsapp" (default: sms)

**Examples**:
```
"Text mom I'll be late"
"WhatsApp John the meeting is at 3"
"Send SMS to dad: arrived safely"
```

**Integration**: Twilio via `messaging_handler.py`

---

## 🎯 Agent 5: OutboundCallAgent

**Purpose**: Initiate phone calls  
**Line**: 834 in `sub_agents_tars.py`

### Functions

#### `make_goal_call(contact, goal)`
**Parameters**:
- `contact`: Who to call
- `goal`: Purpose of the call

**Examples**:
```
"Call dad to discuss dinner plans"
"Ring mom to check in"
"Phone John about the project"
```

**Integration**: Twilio, creates new session

---

## 🎯 Agent 6: InterSessionAgent

**Purpose**: Multi-session coordination (Agent Hub)  
**Line**: 1031 in `sub_agents_tars.py`  
**Complexity**: Highest - manages multiple concurrent calls

### Functions (8 total)

#### 1. `send_message_to_session(session_id, message, sender_id)`
Send message between sessions

**Examples**:
```
"Tell the other call I'll be right there"
"Send 'hold on' to session 2"
```

#### 2. `request_user_confirmation(question, session_id, timeout)`
Ask yes/no question

**Examples**:
```
"Ask if they want to proceed"
"Confirm with user"
```

#### 3. `list_active_sessions()`
Show all active calls

**Examples**:
```
"Who am I talking to?"
"Show active calls"
"List sessions"
```

#### 4. `schedule_callback(contact, when, goal)`
Plan future call

**Examples**:
```
"Call me back in 10 minutes"
"Schedule follow-up tomorrow"
```

#### 5. `hangup_call(session_id)`
End a session

**Examples**:
```
"Hang up on the other call"
"End session 2"
```

#### 6. `get_session_info(session_id)`
Get call details

**Examples**:
```
"Info on session 2"
"Who's in the other call?"
```

#### 7. `suspend_session(session_id)`
Pause session

**Examples**:
```
"Put session 2 on hold"
"Pause the other call"
```

#### 8. `resume_session(session_id)`
Resume session

**Examples**:
```
"Resume session 2"
"Continue with the other call"
```

---

## 🎯 Agent 7: ConversationSearchAgent

**Purpose**: Search past conversations  
**Line**: 1527 in `sub_agents_tars.py`

### Functions

#### `search_conversations(query, limit)`
**Parameters**:
- `query`: Keywords to search
- `limit`: Max results (default: 5)

**Examples**:
```
"What did we talk about last week?"
"Search for pizza in our chats"
"Find conversations about meetings"
```

**Database**: `conversations` with FTS5 full-text search

---

## 🎯 Agent 8: KIPPAgent

**Purpose**: N8N workflow automation  
**Line**: 1614 in `sub_agents_tars.py`

### Functions

#### `send_to_n8n(workflow_id, data, action)`
**Parameters**:
- `workflow_id`: Which N8N workflow
- `data`: Data to send
- `action`: Optional action type

**Examples**:
```
"Add this to my CRM"
"Log this expense"
"Create a task in my project"
```

**Integration**: HTTP POST to N8N webhooks  
**Config**: `N8N_WEBHOOK_URL` in `.env`

---

## 🎯 Agent 9: ProgrammerAgent ⭐

**Purpose**: Code project management  
**Line**: 1822 in `sub_agents_tars.py`  
**Newest**: Added 2026-01-25

### Functions (4 total)

#### 1. `manage_project(action, project_name, project_type)`
Manage coding projects

**Actions**: list | create | open | info

**Examples**:
```
"List my projects" → shows 31 projects
"Create a website called my-portfolio"
"Open the test-project"
"Info on TARS_PHONE_AGENT"
```

**Database**: `project_cache` table

#### 2. `execute_terminal(command, working_directory, timeout)`
Run shell commands

**Safety**: Blocks destructive patterns (rm, sudo, git push)

**Examples**:
```
"Run npm install in my-website"
"Check Python version"
"List files in test-project"
```

**Database**: `programming_operations` table  
**Timeout**: 60 seconds default

#### 3. `edit_code(action, file_path, content, changes_description)`
Create/edit/delete files

**Actions**: read | create | edit | delete

**Examples**:
```
"Create index.html with Hello World"
"Read the main.py file"
"Edit login.js to fix the bug"
"Delete old-file.txt"
```

**AI**: Uses Gemini for code analysis and editing

#### 4. `github_operation(action, repo_name, working_directory)`
Git and GitHub operations

**Actions**: init | clone | push | pull | create_repo | list_repos

**Examples**:
```
"Initialize git in my project"
"Push to GitHub"
"Create repository my-app"
"Clone github.com/user/repo"
```

**Dependencies**: `github_operations.py`, PyGithub  
**Auth**: Requires `GITHUB_TOKEN` in `.env`

---

## 🔧 Utility Functions

### `get_current_time()`
**Purpose**: Get current time/date  
**Not a SubAgent**: Standalone utility function

**Examples**:
```
"What time is it?"
"What's today's date?"
"Tell me the current time"
```

---

## 📊 Agent Statistics

| Agent | Functions | Complexity | Database Tables |
|-------|-----------|------------|-----------------|
| ConfigAgent | 1 | Low | 1 |
| ReminderAgent | 1 | Medium | 1 |
| ContactsAgent | 1 | Low | 1 |
| NotificationAgent | 1 | Low | 0 |
| OutboundCallAgent | 1 | Medium | 1 |
| InterSessionAgent | 8 | High | 1 |
| ConversationSearchAgent | 1 | Medium | 1 |
| KIPPAgent | 1 | Low | 0 |
| ProgrammerAgent | 4 | High | 2 |
| **Total** | **20** | - | **8** |

---

## 🎨 Function Call Examples by Category

### Time Management
```
"Remind me to take medicine at 8pm"
"Schedule callback tomorrow at noon"
"What time is it?"
```

### Communication
```
"Call mom"
"Text dad I'm running late"
"WhatsApp Sarah about dinner"
```

### Multi-Tasking
```
"List active sessions"
"Tell the other call to hold on"
"Put session 2 on hold"
```

### Programming
```
"Create a portfolio website"
"Run npm install"
"Push to GitHub"
```

### Search & Info
```
"What did we talk about yesterday?"
"Info on session 2"
"Lookup John's number"
```

### Personality
```
"Be funnier"
"More honest please"
"Dial down the humor"
```

---

## 🚀 Most Commonly Used Functions

1. `manage_reminder` - Core feature
2. `lookup_contact` - Used before calls/texts
3. `send_notification` - Frequent user request
4. `make_goal_call` - Outbound automation
5. `list_active_sessions` - Multi-call management
6. `manage_project` - New, growing usage
7. `execute_terminal` - Developer favorite

---

## 📝 Adding Your Own Function

See `ARCHITECTURE.md` for the full guide. Quick summary:

1. Add agent class in `sub_agents_tars.py`
2. Implement `async def execute()` method
3. Register in `get_all_agents()`
4. Add function declaration in `get_function_declarations()`
5. Map in `main_tars.py` `_register_sub_agents()`
6. Test with a call!

---

**For detailed implementation**: See `ARCHITECTURE.md`  
**For setup**: See `README.md`  
**For programmer agent**: See `PROGRAMMER_SETUP.md`
