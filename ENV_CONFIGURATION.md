# TARS Configuration Guide

## Complete .env File Template (Lines 45-55 and All Settings)

```bash
# ============================================================
# TARS - MÁTÉ'S PERSONAL ASSISTANT - CONFIGURATION
# ============================================================

# ============================================================
# REQUIRED API KEYS & CREDENTIALS
# ============================================================

# Twilio Configuration (Required for phone calls)
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_PHONE_NUMBER=+14452344131
TARGET_PHONE_NUMBER=+14049525557
WHATSAPP_ADMIN_NUMBER=+36202351624

# Gemini API Configuration (Required)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=models/gemini-2.5-flash-native-audio-preview-12-2025
GEMINI_VOICE=Puck

# TARGET_EMAIL is the user's email address (e.g., matedort1@gmail.com) - emails FROM this address are processed
TARGET_EMAIL=matedort1@gmail.com

# Important Email Notification Configuration
# Options: call, message, both
# Default: call (TARS will call you for important emails like flight changes, cancellations, etc.)
IMPORTANT_EMAIL_NOTIFICATION=call

# ============================================================
# NETWORK & WEBHOOK CONFIGURATION
# ============================================================

# Webhook Configuration (for Twilio callbacks)
WEBHOOK_BASE_URL=http://localhost:5002
WEBHOOK_PORT=5002

# WebSocket Configuration (for Media Streams)
WEBSOCKET_PORT=5001
WEBSOCKET_URL=

# ============================================================
# AUDIO & TECHNICAL SETTINGS - LINE 45
# ============================================================

# Audio Configuration
AUDIO_SAMPLE_RATE=8000

# ============================================================
# N8N INTEGRATION CONFIGURATION
# ============================================================

# N8N Webhook URL (for TARS to send tasks to N8N)
N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/tars

# N8N → TARS Webhook URL (for N8N to send tasks back to TARS)
N8N_TARS_WEBHOOK_URL=http://your-tars-instance.com/webhook/n8n

# Enable/disable messaging features (deprecated - handled by N8N)
ENABLE_SMS=true
ENABLE_WHATSAPP=true
WHATSAPP_NUMBER=whatsapp:+14155238886

# ============================================================
# TARS PERSONALITY & BEHAVIOR (Editable via commands)
# ============================================================

# Personality Configuration
HUMOR_PERCENTAGE=70
HONESTY_PERCENTAGE=95
PERSONALITY=normal
NATIONALITY=British

# Delivery Method Configuration
REMINDER_DELIVERY=call
CALLBACK_REPORT=call

# ============================================================
# AGENT HUB & PERFORMANCE SETTINGS
# ============================================================

# Maximum concurrent phone call sessions
MAX_CONCURRENT_SESSIONS=10

# Auto-make call on startup (for testing)
AUTO_CALL=false

# ============================================================
# POLLING & TIMING CONFIGURATION
# ============================================================

# Reminder checker interval (seconds) - how often to check for due reminders
REMINDER_CHECK_INTERVAL=60

# ============================================================
# USER INFORMATION
# ============================================================

# Your name (for greetings and authentication)
TARGET_NAME=Máté Dort
```

## All Current Configuration Options

### Required Settings
1. **TWILIO_ACCOUNT_SID** - Twilio account SID
2. **TWILIO_AUTH_TOKEN** - Twilio auth token
3. **TWILIO_PHONE_NUMBER** - Your Twilio phone number
4. **TARGET_PHONE_NUMBER** - Your personal phone number (for authentication)
5. **GEMINI_API_KEY** - Google Gemini API key
6. **TARGET_EMAIL** - User's email address (e.g., matedort1@gmail.com) - emails FROM this address are processed by TARS
7. **N8N_WEBHOOK_URL** - N8N webhook URL for TARS to send communication tasks
8. **N8N_TARS_WEBHOOK_URL** - TARS webhook URL for N8N to send tasks back to TARS

### Optional Settings (with defaults)
9. **GEMINI_MODEL** - Gemini model name (default: `models/gemini-2.5-flash-native-audio-preview-12-2025`)
10. **GEMINI_VOICE** - Voice name: `Puck`, `Kore`, or `Charon` (default: `Puck`)
11. **WEBHOOK_BASE_URL** - Base URL for Twilio webhooks (default: `http://localhost:5002`)
12. **WEBHOOK_PORT** - Port for webhook server (default: `5002`)
13. **WEBSOCKET_PORT** - Port for WebSocket server (default: `5001`)
14. **WEBSOCKET_URL** - ngrok URL for WebSocket (optional)
15. **AUDIO_SAMPLE_RATE** - Audio sample rate (default: `8000`)
16. **MESSAGING_PLATFORM** - Primary platform: `gmail`, `sms`, or `whatsapp` (default: `gmail`)
17. **ENABLE_SMS** - Enable SMS features (default: `true`)
18. **ENABLE_WHATSAPP** - Enable WhatsApp features (default: `true`)
19. **WHATSAPP_NUMBER** - WhatsApp number format (default: `whatsapp:+14155238886`)
20. **WHATSAPP_ADMIN_NUMBER** - Admin WhatsApp number
21. **TARGET_NAME** - Your name (default: `Máté Dort`)
22. **MAX_CONCURRENT_SESSIONS** - Max concurrent calls (default: `10`)
23. **AUTO_CALL** - Auto-call on startup (default: `false`)

### Editable via Commands (ConfigAgent)
24. **HUMOR_PERCENTAGE** - 0-100 (default: `70`)
25. **HONESTY_PERCENTAGE** - 0-100 (default: `95`)
26. **PERSONALITY** - `chatty`, `normal`, `brief` (default: `normal`)
27. **NATIONALITY** - Nationality string (default: `British`)
28. **REMINDER_DELIVERY** - `call`, `message`, `email`, `both` (default: `call`)
29. **CALLBACK_REPORT** - `call`, `message`, `email`, `both` (default: `call`)

## Commands to Change Settings

### Via Phone Call or Email:
- "Set humor to 75%"
- "Set honesty to 90%"
- "Set personality to brief"
- "Set nationality to American"
- "Set reminder delivery to email"
- "Set callback report to both"
- "What's my humor percentage?"
- "What's my personality setting?"

## Suggested Additional Configuration Options

### Performance & Timing
- **REMINDER_CHECK_INTERVAL** - How often to check reminders (seconds, default: 60)
- **SESSION_TIMEOUT** - Session timeout in minutes (default: 30)
- **FUNCTION_CALL_TIMEOUT** - Function call timeout in seconds (default: 30)

### Behavior & Features
- **ENABLE_GOOGLE_SEARCH** - Enable/disable Google Search (default: true)
- **ENABLE_FUNCTION_CALLING** - Enable/disable function calling (default: true)
- **CONVERSATION_HISTORY_LIMIT** - Number of messages to remember (default: 10)
- **MAX_FUNCTION_CALLS** - Max function calls per request (default: 5)

### Voice & Audio
- **VOICE_SPEED** - Speech speed multiplier (default: 1.0)
- **VOICE_PITCH** - Voice pitch adjustment (default: 1.0)
- **AUDIO_BUFFER_SIZE** - Audio buffer size in packets (default: 50)

### Security & Access
- **REQUIRE_PIN_FOR_UNKNOWN** - Require PIN for unknown callers (default: false)
- **ALLOW_UNKNOWN_CALLERS** - Allow unknown callers (default: true)
- **MAX_UNKNOWN_CALL_DURATION** - Max duration for unknown calls in minutes (default: 5)

### Logging & Debugging
- **LOG_LEVEL** - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
- **ENABLE_DEBUG_LOGGING** - Enable detailed debug logs (default: false)
- **SAVE_CONVERSATION_TRANSCRIPTS** - Save full transcripts (default: true)

### Database & Storage
- **DATABASE_PATH** - Path to database file (default: tars.db)
- **BACKUP_INTERVAL** - Database backup interval in hours (default: 24)
- **MAX_CONVERSATION_AGE** - Days to keep conversations (default: 90)

### Advanced Features
- **ENABLE_SESSION_PERSISTENCE** - Save sessions for resumption (default: true)
- **ENABLE_CALL_SUMMARIES** - Generate call summaries (default: true)
- **ENABLE_APPROVAL_REQUESTS** - Enable approval workflow (default: true)
- **APPROVAL_TIMEOUT_MINUTES** - Approval request timeout (default: 5)

