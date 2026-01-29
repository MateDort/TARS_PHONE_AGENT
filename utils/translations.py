"""Translation and system instruction management for TARS."""
import os

def _load_markdown_file(filename: str) -> str:
    """Load content from a markdown file.

    Args:
        filename: Name of the markdown file to load

    Returns:
        Content of the file, or empty string if not found
    """
    try:
        # Look in project root (parent of utils/)
        project_root = os.path.dirname(os.path.dirname(__file__))
        filepath = os.path.join(project_root, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Warning: {filename} not found, using default content")
        return ""

# Load markdown files
MATE_INFO = _load_markdown_file('Máté.md')
TARS_INFO = _load_markdown_file('TARS.md')

# System instruction templates
TARS_SYSTEM_INSTRUCTION = f"""You are TARS, Máté Dort's personal assistant. You are respectful, calling him either "sir" or "Máté". You are {{nationality}} in style and tone. You like to joke, but always respectfully.

## About Máté Dort
{MATE_INFO}

{TARS_INFO}

## Personality Settings
Current time: {{current_time}}
Current date: {{current_date}}
Humor level: {{humor_percentage}}%
Honesty level: {{honesty_percentage}}%
Communication style: {{personality}}
Nationality: {{nationality}}
"""

# All text strings for TARS (English only)
TRANSLATIONS = {
    # Conversation strings
    'greeting': "I am all set sir! How can I help you today?",
    'goodbye': "Goodbye sir, until next time.",
    'error_general': "I apologize sir, I've encountered an error. Could you please try again?",
    'connection_issue': "It seems we're having a connection issue. Please try again in a moment.",

    # Reminder strings
    'reminder_saved': "Reminder saved, sir.",
    'reminder_deleted': "Reminder deleted, sir.",
    'reminder_not_found': "I couldn't find that reminder, sir.",
    'reminder_list_empty': "You have no active reminders at the moment, sir.",
    'reminder_updated': "Reminder updated, sir.",
    'reminder_time_invalid': "I couldn't understand that time format, sir. Could you please try again?",

    # Contact strings
    'contact_found': "I found the contact information, sir.",
    'contact_not_found': "I couldn't find that contact, sir.",
    'contact_added': "Contact added, sir.",
    'contact_updated': "Contact updated, sir.",
    'no_birthdays_today': "No birthdays today, sir.",
    'birthday_today': "Today is {name}'s birthday, sir.",

    # Notification strings
    'notification_sent': "Notification sent, sir.",
    'notification_failed': "I couldn't send that notification, sir.",

    # Message strings
    'message_sent': "Message sent, sir.",
    'message_failed': "I couldn't send that message, sir. Please check the recipient details.",
    'link_sent': "Link sent, sir.",
    'sms_disabled': "SMS is currently disabled, sir.",
    'whatsapp_disabled': "WhatsApp is currently disabled, sir.",

    # Configuration strings
    'config_updated': "Configuration updated, sir. {setting} is now at {value}%.",
    'config_invalid_value': "That value is invalid, sir. Please use a number between 0 and 100.",
    'config_current_value': "Current {setting} is at {value}%, sir.",
    'config_reloaded': "Configuration reloaded, sir.",

    # Time strings
    'current_time': "The current time is {time} on {date}, sir.",

    # System strings
    'tars_system_instruction': TARS_SYSTEM_INSTRUCTION,
}


def get_text(key: str) -> str:
    """
    Get translated text for a given key.

    Args:
        key: The translation key

    Returns:
        The translated text, or the key itself if not found
    """
    return TRANSLATIONS.get(key, key)


def format_text(key: str, **kwargs) -> str:
    """
    Get translated text and format it with provided arguments.

    Args:
        key: The translation key
        **kwargs: Arguments to format the text with

    Returns:
        The formatted translated text
    """
    text = get_text(key)
    try:
        return text.format(**kwargs)
    except KeyError as e:
        print(f"Warning: Missing format argument {e} for key '{key}'")
        return text
