# TARS - Máté's Personal Assistant

**TARS** is your British, respectful, and witty AI personal assistant powered by Google's Gemini Live Audio. TARS can handle phone calls, manage your reminders, keep track of your contacts, and dynamically adjust his personality based on your preferences.

## Features

- 🤖 **British Personality**: Respectful, witty, and intelligent assistant
- 🔔 **Smart Reminders**: Automatic phone calls for tasks, meetings, and deadlines
- 👥 **Contact Management**: Quick access to friends, family, and professional contacts
- ⚙️ **Dynamic Personality**: Adjustable humor and honesty levels on the fly
- 🔍 **Google Search**: Real-time information about weather, news, and current events
- 🎤 **Natural Voice**: British accent with natural conversational flow
- 📱 **SMS/WhatsApp**: Send messages and links during phone calls
- 💾 **Local Storage**: All data stored securely in SQLite database

## Quick Start

### Prerequisites

- Python 3.9+
- Twilio account with phone number
- Google Gemini API key
- ngrok (for local development)

### Installation

1. **Clone the repository** (if not already done)
   ```bash
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

   Edit `.env` and fill in your credentials:
   - `TWILIO_ACCOUNT_SID`: From Twilio Console
   - `TWILIO_AUTH_TOKEN`: From Twilio Console
   - `TWILIO_PHONE_NUMBER`: Your Twilio phone number
   - `TARGET_PHONE_NUMBER`: Your personal phone number
   - `GEMINI_API_KEY`: From Google AI Studio
   - `HUMOR_PERCENTAGE`: 0-100 (default: 70)
   - `HONESTY_PERCENTAGE`: 0-100 (default: 95)

4. **Set up ngrok**
   ```bash
   # Terminal 1: Webhook server (port 5002)
   ngrok http 5002

   # Terminal 2: WebSocket server (port 5001)
   ngrok http 5001
   ```

   Update your `.env` file:
   ```
   WEBHOOK_BASE_URL=https://your-ngrok-url.ngrok.io
   WEBSOCKET_URL=wss://your-other-ngrok-url.ngrok.io
   ```

5. **Configure Twilio webhooks**
   - Go to your Twilio phone number settings
   - Set "A Call Comes In" to: `https://your-ngrok-url.ngrok.io/webhook/voice`
   - Set "A Message Comes In" to: `https://your-ngrok-url.ngrok.io/webhook/sms`

6. **Run TARS**
   ```bash
   python main_tars.py
   ```

## Usage

### Making Calls

TARS can:
- Answer incoming calls to your Twilio number
- Make outbound calls for reminders (automatic)
- Handle natural voice conversations with British accent

### Managing Reminders

**Create reminders:**
- "Remind me to work out every day at 6am"
- "Set a reminder for tomorrow at 3pm to call Helen"
- "Remind me to take my medication every Monday at 9am"

**List reminders:**
- "What reminders do I have?"
- "Show me my reminders"

**Edit reminders:**
- "Change my 9am reminder to 10am"
- "Edit the workout reminder to 7am"

**Delete reminders:**
- "Delete my 3pm reminder"
- "Remove the medication reminder"

### Managing Contacts

**Look up contacts:**
- "What's Helen's phone number?"
- "When is Helen's birthday?"

**Add contacts:**
- "Add a new contact named Sarah, she's a friend, phone number 555-1234"

**Edit contacts:**
- "Update Helen's phone number to 555-9999"

### Adjusting TARS Personality

**Set humor level:**
- "Set humor to 65%"
- "Make yourself more funny" (TARS will ask for specific value)
- "Set humor to 90"

**Set honesty level:**
- "Set honesty to 100%"
- "Make yourself more diplomatic" (TARS will ask for specific value)

**Check current settings:**
- "What's my humor percentage?"
- "What percentage is honesty at now?"

**How it works:**
- Changes are saved to the database
- `.env` file is automatically updated
- TARS reloads his personality without restarting
- Settings persist across sessions

### Getting Current Time

- "What time is it?"
- "What's today's date?"

### Sending Messages

- "Send me a text message with [content]"
- "Send me a link to [URL]"

## Architecture

### Core Components

- **main_tars.py**: Entry point and orchestration
- **config.py**: Configuration management with dynamic reloading
- **database.py**: SQLite database for reminders, contacts, and config
- **translations.py**: TARS personality and system prompts
- **sub_agents_tars.py**: Specialized agents for different tasks
- **gemini_live_client.py**: Google Gemini Live Audio client
- **twilio_media_streams.py**: Twilio webhook and WebSocket handler
- **reminder_checker.py**: Background service for reminder notifications
- **messaging_handler.py**: SMS/WhatsApp message processing

### Sub-Agents

1. **ConfigAgent**: Manages personality settings dynamically
2. **ReminderAgent**: Creates, lists, edits, and deletes reminders
3. **ContactsAgent**: Manages contact information and birthdays
4. **MessageAgent**: Sends SMS/WhatsApp messages and links
5. **NotificationAgent**: Handles system notifications

### Database Schema

**reminders**
- title, datetime, recurrence, days_of_week, active, last_triggered

**contacts**
- name, relation, phone, birthday, notes

**conversations**
- timestamp, sender, message, medium, call_sid, message_sid

**configuration**
- key, value, updated_at

## Configuration

### Personality Settings

**HUMOR_PERCENTAGE** (0-100)
- 0: Very serious and formal
- 50: Balanced professional with occasional wit
- 70: Default - Respectfully witty
- 100: Maximum humor (still respectful)

**HONESTY_PERCENTAGE** (0-100)
- 0: Extremely diplomatic and gentle
- 50: Balanced honesty with tact
- 95: Default - Direct and honest
- 100: Brutally honest (no sugar-coating)

### Voice Options

TARS uses Google Gemini's native audio voices:
- **Puck** (default): British male voice
- **Kore**: Alternative voice option
- **Charon**: Alternative voice option

Change in `.env`: `GEMINI_VOICE=Puck`

## Troubleshooting

### TARS can't connect
- Check your internet connection
- Verify Gemini API key is valid
- Ensure ngrok tunnels are running

### No phone calls received
- Verify Twilio webhooks are configured correctly
- Check ngrok URLs are up-to-date in Twilio console
- Ensure Flask server is running on port 5002

### Reminders not triggering
- Check reminder is active in database
- Verify reminder_checker is running in logs
- Ensure time zone settings are correct

### Config changes not working
- Verify `.env` file is in the same directory as main_tars.py
- Check file permissions (must be writable)
- Review logs for any errors

## Development

### Project Structure
```
TARS_PHONE_AGENT/
├── main_tars.py              # Entry point
├── config.py                 # Configuration management
├── database.py               # Database operations
├── translations.py           # System prompts and text
├── sub_agents_tars.py        # Sub-agent implementations
├── gemini_live_client.py     # Gemini Live Audio client
├── twilio_media_streams.py   # Twilio integration
├── reminder_checker.py       # Background reminder service
├── messaging_handler.py      # SMS/WhatsApp handler
├── requirements.txt          # Python dependencies
├── .env.example              # Configuration template
├── TARS.md                   # TARS personality reference
├── Máté.md                   # User information reference
└── README.md                 # This file
```

### Adding New Features

1. Create a new SubAgent class in `sub_agents_tars.py`
2. Add function declaration in `get_function_declarations()`
3. Register the agent in `get_all_agents()`
4. Update translations if needed in `translations.py`

## About TARS

TARS knows everything about Máté through the information embedded in his system prompt:
- Your background, achievements, and goals
- Your values and interests
- Your daily routine and preferences
- Your girlfriend Helen's contact information

TARS is designed to:
- Always address you as "sir" or "Máté"
- Be respectful even when joking
- Provide concise, clear responses
- Support your ambitious goals and disciplined lifestyle

## Credits

Based on the GrannyAI elderly care system, adapted for personal assistant use with enhanced personality customization and dynamic configuration.

**Powered by:**
- Google Gemini 2.5 Flash with Native Audio
- Twilio Voice & Messaging APIs
- Python AsyncIO
- SQLite Database

---

**Version**: 1.0
**Created**: 2026-01-03
**License**: Personal Use

For questions or issues, check the logs or review the code documentation.
