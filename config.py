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

    # Webhook Configuration
    WEBHOOK_BASE_URL = os.getenv('WEBHOOK_BASE_URL', 'http://localhost:5002')
    WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '5002'))

    # Gemini Configuration (primary for voice + LLM)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'models/gemini-2.5-flash-native-audio-preview-12-2025')
    GEMINI_VOICE = os.getenv('GEMINI_VOICE', 'Puck')  # Voice name: Kore, Puck, or Charon

    # Agent Configuration
    AUTO_CALL = os.getenv('AUTO_CALL', 'false').lower() == 'true'  # Auto-make call on startup

    # WebSocket Configuration for Media Streams
    WEBSOCKET_PORT = int(os.getenv('WEBSOCKET_PORT', '5001'))
    WEBSOCKET_URL = os.getenv('WEBSOCKET_URL', '')  # Separate ngrok URL for WebSocket

    # Audio Configuration
    AUDIO_SAMPLE_RATE = int(os.getenv('AUDIO_SAMPLE_RATE', '8000'))  # Twilio uses 8kHz μ-law

    # Messaging Configuration
    ENABLE_SMS = os.getenv('ENABLE_SMS', 'true').lower() == 'true'
    ENABLE_WHATSAPP = os.getenv('ENABLE_WHATSAPP', 'true').lower() == 'true'
    WHATSAPP_NUMBER = os.getenv('WHATSAPP_NUMBER', '')  # Format: whatsapp:+1234567890

    # TARS Personality Configuration (Dynamically Editable)
    HUMOR_PERCENTAGE = int(os.getenv('HUMOR_PERCENTAGE', '70'))  # Default 70%
    HONESTY_PERCENTAGE = int(os.getenv('HONESTY_PERCENTAGE', '95'))  # Default 95%
    PERSONALITY = os.getenv('PERSONALITY', 'normal')  # Options: chatty, normal, brief
    NATIONALITY = os.getenv('NATIONALITY', 'British')  # Default: British

    # Delivery Method Configuration
    REMINDER_DELIVERY = os.getenv('REMINDER_DELIVERY', 'call')  # Options: call, message, both
    CALLBACK_REPORT = os.getenv('CALLBACK_REPORT', 'call')  # Options: call, message, both

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
            errors.append(f"PERSONALITY must be one of: {', '.join(valid_personalities)}")

        # Validate delivery method settings
        valid_delivery_methods = ['call', 'message', 'both']
        if cls.REMINDER_DELIVERY.lower() not in valid_delivery_methods:
            errors.append(f"REMINDER_DELIVERY must be one of: {', '.join(valid_delivery_methods)}")
        if cls.CALLBACK_REPORT.lower() not in valid_delivery_methods:
            errors.append(f"CALLBACK_REPORT must be one of: {', '.join(valid_delivery_methods)}")

        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

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

        return True
