"""Configuration management for TARS - Máté's Personal Assistant."""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for TARS phone assistant."""

    # Twilio Configuration
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '+14452344131')
    TARGET_PHONE_NUMBER = os.getenv('TARGET_PHONE_NUMBER', '+14049525557')
    WHATSAPP_ADMIN_NUMBER = os.getenv('WHATSAPP_ADMIN_NUMBER', '+36202351624')
    # For unknown caller greeting
    TARGET_NAME = os.getenv('TARGET_NAME', 'Máté Dort')
    # Your personal email for authentication
    TARGET_EMAIL = os.getenv('TARGET_EMAIL', '').strip()

    # Webhook Configuration
    WEBHOOK_BASE_URL = os.getenv('WEBHOOK_BASE_URL', 'http://localhost:5002')
    WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '5002'))

    # Gemini Configuration (primary for voice + LLM)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.getenv(
        'GEMINI_MODEL', 'models/gemini-2.5-flash-native-audio-preview-12-2025')
    # Voice name: Kore, Puck, or Charon
    GEMINI_VOICE = os.getenv('GEMINI_VOICE', 'Puck')

    # Agent Configuration
    AUTO_CALL = os.getenv('AUTO_CALL', 'false').lower(
    ) == 'true'  # Auto-make call on startup

    # WebSocket Configuration for Media Streams
    WEBSOCKET_PORT = int(os.getenv('WEBSOCKET_PORT', '5001'))
    # Separate ngrok URL for WebSocket
    WEBSOCKET_URL = os.getenv('WEBSOCKET_URL', '')

    # Audio Configuration
    # Twilio uses 8kHz μ-law
    AUDIO_SAMPLE_RATE = int(os.getenv('AUDIO_SAMPLE_RATE', '8000'))

    # Messaging Configuration
    ENABLE_SMS = os.getenv('ENABLE_SMS', 'true').lower() == 'true'
    ENABLE_WHATSAPP = os.getenv('ENABLE_WHATSAPP', 'true').lower() == 'true'
    # Format: whatsapp:+1234567890
    WHATSAPP_NUMBER = os.getenv('WHATSAPP_NUMBER', 'whatsapp:+14155238886')

    # Gmail Configuration (for console interface)
    GMAIL_USER = os.getenv('GMAIL_USER', '')
    GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', '')

    # Messaging Platform Selection
    # Options: gmail, sms, whatsapp
    MESSAGING_PLATFORM = os.getenv('MESSAGING_PLATFORM', 'gmail')

    # TARS Personality Configuration (Dynamically Editable)
    HUMOR_PERCENTAGE = int(os.getenv('HUMOR_PERCENTAGE', '70'))  # Default 70%
    HONESTY_PERCENTAGE = int(
        os.getenv('HONESTY_PERCENTAGE', '95'))  # Default 95%
    # Options: chatty, normal, brief
    PERSONALITY = os.getenv('PERSONALITY', 'normal')
    NATIONALITY = os.getenv('NATIONALITY', 'British')  # Default: British

    # Delivery Method Configuration
    # Options: call, message, email, both
    REMINDER_DELIVERY = os.getenv('REMINDER_DELIVERY', 'call')
    # Options: call, message, email, both
    CALLBACK_REPORT = os.getenv('CALLBACK_REPORT', 'call')

    # Agent Hub Configuration
    # Hard limit for concurrent calls
    MAX_CONCURRENT_SESSIONS = int(os.getenv('MAX_CONCURRENT_SESSIONS', '10'))

    # Polling & Timing Configuration
    REMINDER_CHECK_INTERVAL = int(os.getenv('REMINDER_CHECK_INTERVAL', '60'))  # Check reminders every N seconds
    GMAIL_POLL_INTERVAL = int(os.getenv('GMAIL_POLL_INTERVAL', '2'))  # Check Gmail every N seconds

    # Conversation & Memory Configuration
    CONVERSATION_HISTORY_LIMIT = int(os.getenv('CONVERSATION_HISTORY_LIMIT', '10'))  # Messages to remember
    MAX_FUNCTION_CALLS = int(os.getenv('MAX_FUNCTION_CALLS', '5'))  # Max function calls per request

    # Feature Flags
    ENABLE_GOOGLE_SEARCH = os.getenv('ENABLE_GOOGLE_SEARCH', 'true').lower() == 'true'
    ENABLE_FUNCTION_CALLING = os.getenv('ENABLE_FUNCTION_CALLING', 'true').lower() == 'true'
    ENABLE_SESSION_PERSISTENCE = os.getenv('ENABLE_SESSION_PERSISTENCE', 'true').lower() == 'true'
    ENABLE_CALL_SUMMARIES = os.getenv('ENABLE_CALL_SUMMARIES', 'true').lower() == 'true'
    SAVE_CONVERSATION_TRANSCRIPTS = os.getenv('SAVE_CONVERSATION_TRANSCRIPTS', 'true').lower() == 'true'

    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()  # DEBUG, INFO, WARNING, ERROR
    ENABLE_DEBUG_LOGGING = os.getenv('ENABLE_DEBUG_LOGGING', 'false').lower() == 'true'

    # Database Configuration
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'tars.db')
    BACKUP_INTERVAL = int(os.getenv('BACKUP_INTERVAL', '24'))  # Backup every N hours
    MAX_CONVERSATION_AGE = int(os.getenv('MAX_CONVERSATION_AGE', '90'))  # Days to keep conversations

    # Security Configuration
    REQUIRE_PIN_FOR_UNKNOWN = os.getenv('REQUIRE_PIN_FOR_UNKNOWN', 'false').lower() == 'true'
    ALLOW_UNKNOWN_CALLERS = os.getenv('ALLOW_UNKNOWN_CALLERS', 'true').lower() == 'true'
    MAX_UNKNOWN_CALL_DURATION = int(os.getenv('MAX_UNKNOWN_CALL_DURATION', '5'))  # Minutes

    # Approval & Workflow Configuration
    ENABLE_APPROVAL_REQUESTS = os.getenv('ENABLE_APPROVAL_REQUESTS', 'true').lower() == 'true'
    APPROVAL_TIMEOUT_MINUTES = int(os.getenv('APPROVAL_TIMEOUT_MINUTES', '5'))  # Minutes until timeout

    # Long Message Auto-Routing Configuration
    LONG_MESSAGE_THRESHOLD = int(os.getenv('LONG_MESSAGE_THRESHOLD', '500'))  # Characters threshold for auto-email routing
    AUTO_EMAIL_ROUTING = os.getenv('AUTO_EMAIL_ROUTING', 'true').lower() == 'true'  # Enable auto-routing long messages to email

    # Conversation Search Configuration
    CONVERSATION_SEARCH_ENABLED = os.getenv('CONVERSATION_SEARCH_ENABLED', 'true').lower() == 'true'  # Enable conversation search features

    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        errors = []

        if not cls.TWILIO_ACCOUNT_SID:
            errors.append("TWILIO_ACCOUNT_SID is required")
        if not cls.TWILIO_AUTH_TOKEN:
            errors.append("TWILIO_AUTH_TOKEN is required")
        if not cls.TWILIO_PHONE_NUMBER:
            errors.append("TWILIO_PHONE_NUMBER is required")
        if not cls.TARGET_PHONE_NUMBER:
            errors.append("TARGET_PHONE_NUMBER is required")
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required")

        # Validate personality percentages
        if not 0 <= cls.HUMOR_PERCENTAGE <= 100:
            errors.append("HUMOR_PERCENTAGE must be between 0 and 100")
        if not 0 <= cls.HONESTY_PERCENTAGE <= 100:
            errors.append("HONESTY_PERCENTAGE must be between 0 and 100")

        # Validate personality setting
        valid_personalities = ['chatty', 'normal', 'brief']
        if cls.PERSONALITY.lower() not in valid_personalities:
            errors.append(
                f"PERSONALITY must be one of: {', '.join(valid_personalities)}")

        # Validate delivery method settings
        valid_delivery_methods = ['call', 'message', 'email', 'both']
        if cls.REMINDER_DELIVERY.lower() not in valid_delivery_methods:
            errors.append(
                f"REMINDER_DELIVERY must be one of: {', '.join(valid_delivery_methods)}")
        if cls.CALLBACK_REPORT.lower() not in valid_delivery_methods:
            errors.append(
                f"CALLBACK_REPORT must be one of: {', '.join(valid_delivery_methods)}")

        if errors:
            raise ValueError("Configuration errors:\n" +
                             "\n".join(f"  - {e}" for e in errors))

        return True

    @classmethod
    def reload(cls):
        """Reload configuration from environment variables and .env file."""
        load_dotenv(override=True)

        # Reload all configuration values
        cls.HUMOR_PERCENTAGE = int(os.getenv('HUMOR_PERCENTAGE', '70'))
        cls.HONESTY_PERCENTAGE = int(os.getenv('HONESTY_PERCENTAGE', '95'))
        cls.PERSONALITY = os.getenv('PERSONALITY', 'normal')
        cls.NATIONALITY = os.getenv('NATIONALITY', 'British')
        cls.REMINDER_DELIVERY = os.getenv('REMINDER_DELIVERY', 'call')
        cls.CALLBACK_REPORT = os.getenv('CALLBACK_REPORT', 'call')
        cls.GEMINI_VOICE = os.getenv('GEMINI_VOICE', 'Puck')
        cls.AUTO_CALL = os.getenv('AUTO_CALL', 'false').lower() == 'true'
        cls.ENABLE_SMS = os.getenv('ENABLE_SMS', 'true').lower() == 'true'
        cls.ENABLE_WHATSAPP = os.getenv('ENABLE_WHATSAPP', 'true').lower() == 'true'
        cls.REMINDER_CHECK_INTERVAL = int(os.getenv('REMINDER_CHECK_INTERVAL', '60'))
        cls.GMAIL_POLL_INTERVAL = int(os.getenv('GMAIL_POLL_INTERVAL', '2'))
        cls.CONVERSATION_HISTORY_LIMIT = int(os.getenv('CONVERSATION_HISTORY_LIMIT', '10'))
        cls.MAX_FUNCTION_CALLS = int(os.getenv('MAX_FUNCTION_CALLS', '5'))
        cls.ENABLE_GOOGLE_SEARCH = os.getenv('ENABLE_GOOGLE_SEARCH', 'true').lower() == 'true'
        cls.ENABLE_FUNCTION_CALLING = os.getenv('ENABLE_FUNCTION_CALLING', 'true').lower() == 'true'
        cls.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
        cls.LONG_MESSAGE_THRESHOLD = int(os.getenv('LONG_MESSAGE_THRESHOLD', '500'))
        cls.AUTO_EMAIL_ROUTING = os.getenv('AUTO_EMAIL_ROUTING', 'true').lower() == 'true'
        cls.CONVERSATION_SEARCH_ENABLED = os.getenv('CONVERSATION_SEARCH_ENABLED', 'true').lower() == 'true'

        return True
