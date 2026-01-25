# TARS Configuration Commands Guide

## All Available Configuration Commands

You can change these settings via phone call or email using natural language commands.

### Personality Settings

**Humor Percentage (0-100)**
- "Set humor to 75%"
- "What's my humor percentage?"
- Default: 70%

**Honesty Percentage (0-100)**
- "Set honesty to 90%"
- "What's my honesty percentage?"
- Default: 95%

**Personality Style**
- "Set personality to brief"
- "Set personality to chatty"
- "Set personality to normal"
- "What's my personality?"
- Options: `chatty`, `normal`, `brief`
- Default: `normal`

**Nationality**
- "Set nationality to American"
- "Set nationality to British"
- "What's my nationality?"
- Default: `British`

### Voice Settings

**Voice Selection**
- "Set voice to Puck"
- "Set voice to Kore"
- "Set voice to Charon"
- "What voice are you using?"
- Options: `Puck`, `Kore`, `Charon`
- Default: `Puck`

### Delivery Method Settings

**Reminder Delivery**
- "Set reminder delivery to email"
- "Set reminder delivery to call"
- "Set reminder delivery to message"
- "Set reminder delivery to both"
- "How do you deliver reminders?"
- Options: `call`, `message`, `email`, `both`
- Default: `call`

**Callback Report**
- "Set callback report to email"
- "Set callback report to both"
- "How do you send callback reports?"
- Options: `call`, `message`, `email`, `both`
- Default: `call`

### Performance & Timing Settings

**Reminder Check Interval**
- "Set reminder check interval to 30 seconds"
- "Set reminder check interval to 120 seconds"
- "How often do you check reminders?"
- Range: 10-3600 seconds
- Default: 60 seconds


**Conversation History Limit**
- "Set conversation history limit to 20"
- "How many messages do you remember?"
- Range: 1-100 messages
- Default: 10 messages

## Complete Configuration Reference

### Current Configs (29 total)

#### Required API Keys (8)
1. `TWILIO_ACCOUNT_SID` - Twilio account SID
2. `TWILIO_AUTH_TOKEN` - Twilio auth token
3. `TWILIO_PHONE_NUMBER` - Your Twilio phone number
4. `TARGET_PHONE_NUMBER` - Your personal phone number
5. `GEMINI_API_KEY` - Google Gemini API key
6. `GMAIL_USER` - Gmail account for sending
7. `GMAIL_APP_PASSWORD` - Gmail app password
8. `TARGET_EMAIL` - Your email address

#### Network & Webhooks (4)
9. `WEBHOOK_BASE_URL` - Base URL for webhooks
10. `WEBHOOK_PORT` - Webhook server port (default: 5002)
11. `WEBSOCKET_PORT` - WebSocket server port (default: 5001)
12. `WEBSOCKET_URL` - ngrok URL for WebSocket (optional)

#### Audio & Technical (1)
13. `AUDIO_SAMPLE_RATE` - Audio sample rate (default: 8000)

#### N8N Integration (2)
14. `N8N_WEBHOOK_URL` - N8N webhook URL for communication tasks (required)
15. `N8N_TARS_WEBHOOK_URL` - TARS webhook URL for N8N to send tasks back (required)

#### Messaging Features (deprecated - handled by N8N)
16. `ENABLE_SMS` - Enable SMS (default: `true`, deprecated)
17. `ENABLE_WHATSAPP` - Enable WhatsApp (default: `true`, deprecated)
18. `WHATSAPP_NUMBER` - WhatsApp number format
19. `WHATSAPP_ADMIN_NUMBER` - Admin WhatsApp number

#### Personality & Behavior (6) - **Editable via Commands**
19. `HUMOR_PERCENTAGE` - 0-100 (default: 70)
20. `HONESTY_PERCENTAGE` - 0-100 (default: 95)
21. `PERSONALITY` - `chatty`, `normal`, `brief` (default: `normal`)
22. `NATIONALITY` - Nationality string (default: `British`)
23. `REMINDER_DELIVERY` - `call`, `message`, `email`, `both` (default: `call`)
24. `CALLBACK_REPORT` - `call`, `message`, `email`, `both` (default: `call`)

#### Performance & Timing (3) - **Editable via Commands**
25. `REMINDER_CHECK_INTERVAL` - Seconds between reminder checks (default: 60)
26. `GMAIL_POLL_INTERVAL` - Seconds between Gmail checks (default: 2)
27. `CONVERSATION_HISTORY_LIMIT` - Messages to remember (default: 10)

#### Agent Hub (2)
28. `MAX_CONCURRENT_SESSIONS` - Max concurrent calls (default: 10)
29. `AUTO_CALL` - Auto-call on startup (default: `false`)

#### Feature Flags (5) - **New**
30. `ENABLE_GOOGLE_SEARCH` - Enable Google Search (default: `true`)
31. `ENABLE_FUNCTION_CALLING` - Enable function calling (default: `true`)
32. `ENABLE_SESSION_PERSISTENCE` - Save sessions for resumption (default: `true`)
33. `ENABLE_CALL_SUMMARIES` - Generate call summaries (default: `true`)
34. `SAVE_CONVERSATION_TRANSCRIPTS` - Save full transcripts (default: `true`)

#### Logging (2) - **New**
35. `LOG_LEVEL` - `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`)
36. `ENABLE_DEBUG_LOGGING` - Enable detailed debug logs (default: `false`)

#### Database (3) - **New**
37. `DATABASE_PATH` - Path to database file (default: `tars.db`)
38. `BACKUP_INTERVAL` - Backup interval in hours (default: 24)
39. `MAX_CONVERSATION_AGE` - Days to keep conversations (default: 90)

#### Security (3) - **New**
40. `REQUIRE_PIN_FOR_UNKNOWN` - Require PIN for unknown callers (default: `false`)
41. `ALLOW_UNKNOWN_CALLERS` - Allow unknown callers (default: `true`)
42. `MAX_UNKNOWN_CALL_DURATION` - Max duration in minutes (default: 5)

#### Approval & Workflow (2) - **New**
43. `ENABLE_APPROVAL_REQUESTS` - Enable approval workflow (default: `true`)
44. `APPROVAL_TIMEOUT_MINUTES` - Approval timeout (default: 5)

## Example .env File (Lines 45-55 Section)

```bash
# Audio Configuration - LINE 45
AUDIO_SAMPLE_RATE=8000

# N8N Integration Configuration
N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/tars
N8N_TARS_WEBHOOK_URL=http://your-tars-instance.com/webhook/n8n

# Messaging Features (deprecated - handled by N8N)
ENABLE_SMS=true
ENABLE_WHATSAPP=true
WHATSAPP_NUMBER=whatsapp:+14155238886

# User Email
TARGET_EMAIL=your_target_email@gmail.com
```

## Suggested Additional Configs for Future

### Voice & Audio Enhancement
- `VOICE_SPEED` - Speech speed multiplier (0.5-2.0)
- `VOICE_PITCH` - Voice pitch adjustment (0.5-2.0)
- `AUDIO_BUFFER_SIZE` - Buffer size in packets

### Advanced Behavior
- `MAX_FUNCTION_CALLS` - Max function calls per request (already added)
- `FUNCTION_CALL_TIMEOUT` - Function timeout in seconds
- `SESSION_TIMEOUT` - Session timeout in minutes

### Smart Features
- `ENABLE_SMART_REMINDERS` - AI-powered reminder suggestions
- `ENABLE_CONTACT_SUGGESTIONS` - Suggest contacts based on context
- `ENABLE_AUTO_CATEGORIZATION` - Auto-categorize conversations

### Integration Settings
- `ENABLE_CALENDAR_SYNC` - Sync with Google Calendar
- `ENABLE_NOTES_SYNC` - Sync with note-taking apps
- `ENABLE_TASK_MANAGEMENT` - Task management integration

