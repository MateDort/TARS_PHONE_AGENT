"""Sub-agents for TARS - Máté's Personal Assistant."""
import asyncio
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from communication.gemini_live_client import SubAgent
from core.database import Database
from utils.translations import get_text, format_text
from core.config import Config
import re

logger = logging.getLogger(__name__)


class ConfigAgent(SubAgent):
    """Manages TARS configuration settings dynamically."""

    def __init__(self, db: Database, system_reloader_callback=None):
        super().__init__(
            name="config_agent",
            description="Adjusts TARS settings (humor, honesty, personality, nationality, reminder delivery, callback reports)"
        )
        self.db = db
        self.system_reloader_callback = system_reloader_callback

    async def execute(self, args: Dict[str, Any]) -> str:
        """Execute configuration operation.

        Args:
            args: {
                "action": "set|get",
                "setting": "humor|honesty",
                "value": int (0-100, for set action)
            }
        """
        action = args.get("action", "get")
        setting = args.get("setting", "").lower()

        valid_settings = ["humor", "honesty", "personality", "nationality", "reminder_delivery", "callback_report", 
                         "voice", "reminder_check_interval", "conversation_history_limit"]
        if setting not in valid_settings:
            return f"Please specify one of: {', '.join(valid_settings)}."

        if action == "set":
            return await self._set_config(setting, args.get("value"))
        elif action == "get":
            return await self._get_config(setting)
        else:
            return f"Unknown action: {action}"

    async def _set_config(self, setting: str, value: Any) -> str:
        """Set a configuration value."""
        # Handle percentage-based settings (humor, honesty)
        if setting in ["humor", "honesty"]:
            try:
                value_int = int(value)
                if not 0 <= value_int <= 100:
                    return get_text('config_invalid_value')
            except (ValueError, TypeError):
                return get_text('config_invalid_value')

            # Update environment variable and save to .env file
            setting_key = f"{setting.upper()}_PERCENTAGE"
            os.environ[setting_key] = str(value_int)

            # Update .env file
            self._update_env_file(setting_key, str(value_int))

            # Reload config
            Config.reload()

            # Save to database for persistence
            self.db.set_config(setting_key, str(value_int))

            # Trigger system instruction reload if callback provided
            if self.system_reloader_callback:
                await self.system_reloader_callback()

            logger.info(f"Updated {setting} to {value_int}%")

            return format_text('config_updated', setting=setting, value=value_int)

        # Handle personality setting
        elif setting == "personality":
            valid_personalities = ['chatty', 'normal', 'brief']
            value_str = str(value).lower()
            if value_str not in valid_personalities:
                return f"Invalid personality. Please choose: {', '.join(valid_personalities)}"

            setting_key = "PERSONALITY"
            os.environ[setting_key] = value_str
            self._update_env_file(setting_key, value_str)
            Config.reload()
            self.db.set_config(setting_key, value_str)

            if self.system_reloader_callback:
                await self.system_reloader_callback()

            logger.info(f"Updated personality to {value_str}")
            return f"Personality updated to '{value_str}', sir."

        # Handle nationality setting
        elif setting == "nationality":
            value_str = str(value).capitalize()
            setting_key = "NATIONALITY"
            os.environ[setting_key] = value_str
            self._update_env_file(setting_key, value_str)
            Config.reload()
            self.db.set_config(setting_key, value_str)

            if self.system_reloader_callback:
                await self.system_reloader_callback()

            logger.info(f"Updated nationality to {value_str}")
            return f"Nationality updated to {value_str}, sir."

        # Handle reminder_delivery setting
        elif setting == "reminder_delivery":
            valid_methods = ['call', 'message', 'email', 'both']
            value_str = str(value).lower()
            if value_str not in valid_methods:
                return f"Invalid reminder delivery method. Please choose: {', '.join(valid_methods)}"

            setting_key = "REMINDER_DELIVERY"
            os.environ[setting_key] = value_str
            self._update_env_file(setting_key, value_str)
            Config.reload()
            self.db.set_config(setting_key, value_str)

            logger.info(f"Updated reminder delivery to {value_str}")
            return f"Reminder delivery method updated to '{value_str}', sir."

        # Handle callback_report setting
        elif setting == "callback_report":
            valid_methods = ['call', 'message', 'email', 'both']
            value_str = str(value).lower()
            if value_str not in valid_methods:
                return f"Invalid callback report method. Please choose: {', '.join(valid_methods)}"

            setting_key = "CALLBACK_REPORT"
            os.environ[setting_key] = value_str
            self._update_env_file(setting_key, value_str)
            Config.reload()
            self.db.set_config(setting_key, value_str)

            logger.info(f"Updated callback report to {value_str}")
            return f"Callback report method updated to '{value_str}', sir."

        # Handle voice setting
        elif setting == "voice":
            valid_voices = ['puck', 'kore', 'charon']
            value_str = str(value).lower()
            if value_str not in valid_voices:
                return f"Invalid voice. Please choose: {', '.join(valid_voices)}"

            setting_key = "GEMINI_VOICE"
            os.environ[setting_key] = value_str.capitalize()
            self._update_env_file(setting_key, value_str.capitalize())
            Config.reload()
            self.db.set_config(setting_key, value_str.capitalize())

            logger.info(f"Updated voice to {value_str.capitalize()}")
            return f"Voice updated to '{value_str.capitalize()}', sir."

        # Handle reminder_check_interval setting
        elif setting == "reminder_check_interval":
            try:
                value_int = int(value)
                if value_int < 10:
                    return "Reminder check interval must be at least 10 seconds, sir."
                if value_int > 3600:
                    return "Reminder check interval cannot exceed 3600 seconds (1 hour), sir."
            except (ValueError, TypeError):
                return "Invalid interval. Please provide a number in seconds, sir."

            setting_key = "REMINDER_CHECK_INTERVAL"
            os.environ[setting_key] = str(value_int)
            self._update_env_file(setting_key, str(value_int))
            Config.reload()
            self.db.set_config(setting_key, str(value_int))

            logger.info(f"Updated reminder check interval to {value_int} seconds")
            return f"Reminder check interval updated to {value_int} seconds, sir."


        # Handle conversation_history_limit setting
        elif setting == "conversation_history_limit":
            try:
                value_int = int(value)
                if value_int < 1:
                    return "Conversation history limit must be at least 1, sir."
                if value_int > 100:
                    return "Conversation history limit cannot exceed 100 messages, sir."
            except (ValueError, TypeError):
                return "Invalid limit. Please provide a number, sir."

            setting_key = "CONVERSATION_HISTORY_LIMIT"
            os.environ[setting_key] = str(value_int)
            self._update_env_file(setting_key, str(value_int))
            Config.reload()
            self.db.set_config(setting_key, str(value_int))

            logger.info(f"Updated conversation history limit to {value_int}")
            return f"Conversation history limit updated to {value_int} messages, sir."

        return f"Unknown setting: {setting}"

    def get_valid_settings(self) -> list:
        """Get list of all valid settings that can be adjusted."""
        return ["humor", "honesty", "personality", "nationality", "reminder_delivery", "callback_report", 
                "voice", "reminder_check_interval", "conversation_history_limit"]

    async def _get_config(self, setting: str) -> str:
        """Get current configuration value."""
        if setting == "humor":
            value = Config.HUMOR_PERCENTAGE
            return format_text('config_current_value', setting=setting, value=value)
        elif setting == "honesty":
            value = Config.HONESTY_PERCENTAGE
            return format_text('config_current_value', setting=setting, value=value)
        elif setting == "personality":
            value = Config.PERSONALITY
            return f"Current personality is '{value}', sir."
        elif setting == "nationality":
            value = Config.NATIONALITY
            return f"Current nationality is {value}, sir."
        elif setting == "reminder_delivery":
            value = Config.REMINDER_DELIVERY
            return f"Current reminder delivery method is '{value}', sir."
        elif setting == "callback_report":
            value = Config.CALLBACK_REPORT
            return f"Current callback report method is '{value}', sir."
        elif setting == "voice":
            value = Config.GEMINI_VOICE
            return f"Current voice is '{value}', sir."
        elif setting == "reminder_check_interval":
            value = Config.REMINDER_CHECK_INTERVAL
            return f"Current reminder check interval is {value} seconds, sir."
        elif setting == "conversation_history_limit":
            value = Config.CONVERSATION_HISTORY_LIMIT
            return f"Current conversation history limit is {value} messages, sir."
        else:
            return f"Unknown setting: {setting}"

    def _update_env_file(self, key: str, value: str):
        """Update .env file with new value."""
        env_path = ".env"
        if not os.path.exists(env_path):
            # Create .env file if it doesn't exist
            with open(env_path, 'w') as f:
                f.write(f"{key}={value}\n")
            return

        # Read existing .env file
        with open(env_path, 'r') as f:
            lines = f.readlines()

        # Update or add the key
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                found = True
                break

        if not found:
            lines.append(f"{key}={value}\n")

        # Write back to .env file
        with open(env_path, 'w') as f:
            f.writelines(lines)


class ReminderAgent(SubAgent):
    """Handles reminders with local storage and automatic phone call triggers."""

    def __init__(self, db: Database):
        super().__init__(
            name="reminder_agent",
            description="Manages reminders with recurring support and automatic notifications"
        )
        self.db = db

    async def execute(self, args: Dict[str, Any]) -> str:
        """Execute reminder operation.

        Args:
            args: {
                "action": "create|list|delete|delete_all|edit",
                "title": str,
                "time": str (e.g., "3pm", "tomorrow at 8am", "every day at 1pm"),
                "reminder_id": int (for delete/edit)
            }
        """
        action = args.get("action", "list")

        if action == "create":
            return await self._create_reminder(args)

        elif action == "list":
            return await self._list_reminders()

        elif action == "delete":
            return await self._delete_reminder(args)

        elif action == "delete_all":
            return await self._delete_all_reminders()

        elif action == "edit":
            return await self._edit_reminder(args)

        else:
            return f"Unknown action: {action}"

    async def _create_reminder(self, args: Dict[str, Any]) -> str:
        """Create a new reminder."""
        title = args.get("title", "Reminder")
        time_str = args.get("time", "")

        # Parse time and recurrence
        parsed = self._parse_time(time_str)
        if not parsed:
            return get_text('reminder_time_invalid')

        reminder_time = parsed['datetime']
        recurrence = parsed.get('recurrence')
        days_of_week = parsed.get('days_of_week')

        # Save to database
        reminder_id = self.db.add_reminder(
            title=title,
            datetime_str=reminder_time.isoformat(),
            recurrence=recurrence,
            days_of_week=days_of_week
        )

        logger.info(
            f"Created reminder {reminder_id}: {title} at {reminder_time}")

        # Build response
        recurrence_text = ""
        if recurrence == "daily":
            recurrence_text = " every day"
        elif recurrence == "weekly" and days_of_week:
            recurrence_text = f" every {days_of_week}"

        return f"{get_text('reminder_saved')}: {title} at {reminder_time.strftime('%I:%M %p on %B %d, %Y')}{recurrence_text}"

    async def _list_reminders(self) -> str:
        """List all active reminders."""
        reminders = self.db.get_reminders(active_only=True)

        if not reminders:
            return get_text('reminder_list_empty')

        lines = ["Your active reminders, sir:"]
        for r in reminders:
            reminder_time = datetime.fromisoformat(r['datetime'])
            time_str = reminder_time.strftime('%I:%M %p on %B %d')

            recurrence_text = ""
            if r['recurrence'] == 'daily':
                recurrence_text = " (every day)"
            elif r['recurrence'] == 'weekly' and r['days_of_week']:
                recurrence_text = f" (every {r['days_of_week']})"

            lines.append(f"- {r['title']} at {time_str}{recurrence_text}")

        return "\n".join(lines)

    async def _delete_reminder(self, args: Dict[str, Any]) -> str:
        """Delete a reminder."""
        # Try to find by time or title
        time_str = args.get("time", "")
        title = args.get("title", "")

        reminders = self.db.get_reminders(active_only=True)

        # Find matching reminder
        match = None
        for r in reminders:
            reminder_time = datetime.fromisoformat(r['datetime'])

            # Match by time
            if time_str and time_str in reminder_time.strftime('%I %p').lower():
                match = r
                break

            # Match by title
            if title and title.lower() in r['title'].lower():
                match = r
                break

        if match:
            self.db.delete_reminder(match['id'])
            return f"{get_text('reminder_deleted')}: {match['title']}"
        else:
            return get_text('reminder_not_found')

    async def _delete_all_reminders(self) -> str:
        """Delete all reminders."""
        count = self.db.delete_all_reminders()
        
        if count == 0:
            return "No reminders to delete, sir."
        elif count == 1:
            return "Deleted 1 reminder, sir."
        else:
            return f"Deleted all {count} reminders, sir."

    async def _edit_reminder(self, args: Dict[str, Any]) -> str:
        """Edit a reminder - can update title, time, or both."""
        # Find reminder by title or time
        reminders = self.db.get_reminders(active_only=True)
        match = None

        # Try to find by title first
        title = args.get("title", "")
        old_title = args.get("old_title", "")
        old_time = args.get("old_time", "")

        search_title = old_title or title

        for r in reminders:
            # Match by title
            if search_title and search_title.lower() in r['title'].lower():
                match = r
                break

            # Match by time
            if old_time:
                reminder_time = datetime.fromisoformat(r['datetime'])
                time_str = reminder_time.strftime('%I:%M %p').lower()
                if old_time.lower() in time_str or old_time.lower() in reminder_time.strftime('%I %p').lower():
                    match = r
                    break

        if not match:
            search_term = search_title or old_time or "reminder"
            return f"{get_text('reminder_not_found')}: {search_term}"

        # Prepare updates
        updates = {}

        # Update title if provided
        new_title = args.get("new_title", "")
        if new_title:
            updates["title"] = new_title
        elif "title" in args and args["title"] and args["title"] != match['title']:
            updates["title"] = args["title"]

        # Update time if provided
        new_time = args.get("new_time", "")
        time_str = args.get("time", "")
        if new_time or time_str:
            time_to_parse = new_time or time_str
            parsed = self._parse_time(time_to_parse)
            if not parsed:
                return get_text('reminder_time_invalid')

            updates["datetime"] = parsed['datetime'].isoformat()
            if parsed.get('recurrence'):
                updates["recurrence"] = parsed['recurrence']
            if parsed.get('days_of_week'):
                updates["days_of_week"] = parsed['days_of_week']

        if not updates:
            return "No changes specified for the reminder, sir."

        # Update reminder
        self.db.update_reminder(match['id'], **updates)

        logger.info(f"Updated reminder {match['id']}: {updates}")

        # Get updated reminder for response
        updated = self.db.get_reminder(match['id'])
        if updated:
            reminder_time = datetime.fromisoformat(updated['datetime'])
            time_str = reminder_time.strftime('%I:%M %p on %B %d, %Y')

            recurrence_text = ""
            if updated['recurrence'] == 'daily':
                recurrence_text = " every day"
            elif updated['recurrence'] == 'weekly' and updated['days_of_week']:
                recurrence_text = f" every {updated['days_of_week']}"

            return f"{get_text('reminder_updated')}: {updated['title']} at {time_str}{recurrence_text}"

        return get_text('reminder_updated')

    def _parse_time(self, time_str: str) -> Dict:
        """Parse time string into datetime and recurrence.

        Examples:
        - "3pm" -> today at 3pm
        - "tomorrow at 8am" -> tomorrow at 8am
        - "every day at 1pm" -> daily recurring at 1pm
        - "every monday at 2pm" -> weekly on monday at 2pm
        """
        time_str = time_str.lower().strip()

        # Check for recurrence
        recurrence = None
        days_of_week = None

        if "every day" in time_str or "daily" in time_str:
            recurrence = "daily"
            time_str = re.sub(r'every day|daily', '', time_str).strip()

        # Check for specific days
        days_pattern = r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)'
        if "every" in time_str and re.search(days_pattern, time_str):
            recurrence = "weekly"
            days_matches = re.findall(days_pattern, time_str)
            days_of_week = ",".join(days_matches)
            time_str = re.sub(r'every|' + days_pattern, '', time_str).strip()

        # Parse base time - ALWAYS use fresh current time
        now = datetime.now()
        target_time = now

        # Check for relative time expressions like "in X minutes/hours" (handle typos like "miute")
        relative_match = re.search(r'in\s+(\d+)\s+(minute|minutes|miute|miutes|hour|hours|second|seconds)', time_str, re.IGNORECASE)
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2).lower()
            
            if unit in ['minute', 'minutes']:
                target_time = now + timedelta(minutes=amount)
            elif unit in ['hour', 'hours']:
                target_time = now + timedelta(hours=amount)
            elif unit in ['second', 'seconds']:
                target_time = now + timedelta(seconds=amount)
            
            # Return early for relative times
            return {
                'datetime': target_time,
                'recurrence': recurrence,
                'days_of_week': days_of_week
            }

        # Extract time with optional minutes (3pm, 8:30am, 09:14 AM, etc.)
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', time_str)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3)

            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0

            target_time = target_time.replace(
                hour=hour, minute=minute, second=0, microsecond=0)

        # Check for relative days
        if "tomorrow" in time_str:
            target_time += timedelta(days=1)
        elif "today" not in time_str and target_time < now:
            # If time has passed today, set for tomorrow
            target_time += timedelta(days=1)

        return {
            'datetime': target_time,
            'recurrence': recurrence,
            'days_of_week': days_of_week
        }


class ContactsAgent(SubAgent):
    """Manages family and friends contact information."""

    def __init__(self, db: Database):
        super().__init__(
            name="contacts",
            description="Stores and retrieves family and friends information"
        )
        self.db = db
        self._init_contacts()

    def _init_contacts(self):
        """Initialize with Helen's contact information."""
        existing = self.db.search_contact("Helen")
        if not existing:
            self.db.add_contact(
                name="Helen Stadler",
                relation="Girlfriend",
                phone="404-953-5533",
                birthday="2004-08-27",
                notes="Birthday: August 27, 2004"
            )
            logger.info("Initial contacts added")

    async def execute(self, args: Dict[str, Any]) -> str:
        """Look up or manage contact information.

        Args:
            args: {
                "action": "lookup|list|birthday_check|add|edit",
                "name": str,
                "relation": str (optional),
                "phone": str (optional),
                "email": str (optional),
                "birthday": str (optional, YYYY-MM-DD format),
                "notes": str (optional - bio or additional info),
                "old_name": str (for edit - name to find),
                "new_name": str (for edit - new name)
            }
        """
        action = args.get("action", "lookup")
        name = args.get("name", "")

        if action == "lookup":
            contact = self.db.search_contact(name)
            if contact:
                info = [f"{contact['name']}"]
                if contact['relation']:
                    info.append(f"Relation: {contact['relation']}")
                if contact['phone']:
                    info.append(f"Phone: {contact['phone']}")
                if contact.get('email'):
                    info.append(f"Email: {contact['email']}")
                if contact['birthday']:
                    info.append(
                        f"Birthday: {self._format_birthday(contact['birthday'])}")
                if contact.get('notes'):
                    info.append(f"Bio: {contact['notes']}")
                return "\n".join(info)
            else:
                return f"{get_text('contact_not_found')}: {name}"

        elif action == "list":
            contacts = self.db.get_contacts()
            if not contacts:
                return "You have no contacts saved, sir."

            lines = ["Your contacts with all information, sir:"]
            for c in contacts:
                contact_parts = [f"**{c['name']}**"]
                if c.get('relation'):
                    contact_parts.append(f"Relationship: {c['relation']}")
                if c.get('phone'):
                    contact_parts.append(f"Phone number: {c['phone']}")
                if c.get('email'):
                    contact_parts.append(f"Email address: {c['email']}")
                if c.get('birthday'):
                    contact_parts.append(f"Birthday: {c['birthday']}")
                if c.get('notes'):
                    contact_parts.append(f"Notes: {c['notes']}")
                lines.append(f"*   {', '.join(contact_parts)}")
            return "\n".join(lines)

        elif action == "birthday_check":
            # Check for upcoming birthdays
            today = datetime.now().date()
            contacts = self.db.get_contacts()

            upcoming = []
            for c in contacts:
                if c['birthday']:
                    bday = datetime.fromisoformat(c['birthday']).date()
                    # Check if birthday is today
                    if bday.month == today.month and bday.day == today.day:
                        upcoming.append(format_text(
                            'birthday_today', name=c['name']))

            return "\n".join(upcoming) if upcoming else get_text('no_birthdays_today')

        elif action == "add":
            return await self._add_contact(args)

        elif action == "edit":
            return await self._edit_contact(args)

        elif action == "delete":
            return await self._delete_contact(args)

        else:
            return f"Unknown contact action: {action}"

    async def _add_contact(self, args: Dict[str, Any]) -> str:
        """Add a new contact."""
        name = args.get("name", "")
        if not name:
            return "Please provide a name for the contact, sir."

        relation = args.get("relation")
        phone = args.get("phone")
        email = args.get("email")
        birthday = args.get("birthday")
        notes = args.get("notes")

        # Check if contact already exists
        existing = self.db.search_contact(name)
        if existing:
            return f"A contact named {name} already exists, sir. Use edit to update it."

        # Add contact
        contact_id = self.db.add_contact(
            name=name,
            relation=relation,
            phone=phone,
            email=email,
            birthday=birthday,
            notes=notes
        )

        logger.info(f"Added contact {contact_id}: {name}")

        # Build response
        info = [f"{get_text('contact_added')}: {name}"]
        if relation:
            info.append(f"Relation: {relation}")
        if phone:
            info.append(f"Phone: {phone}")
        if email:
            info.append(f"Email: {email}")
        if birthday:
            info.append(f"Birthday: {self._format_birthday(birthday)}")

        return "\n".join(info)

    async def _edit_contact(self, args: Dict[str, Any]) -> str:
        """Edit an existing contact."""
        # Find contact by name (old_name or name)
        old_name = args.get("old_name") or args.get("name", "")
        if not old_name:
            return get_text('contact_not_found')

        contact = self.db.search_contact(old_name)
        if not contact:
            return f"{get_text('contact_not_found')}: {old_name}"

        # Prepare update fields
        updates = {}
        if "new_name" in args and args["new_name"]:
            updates["name"] = args["new_name"]
        elif "name" in args and args["name"] and args["name"] != old_name:
            updates["name"] = args["name"]

        if "relation" in args:
            updates["relation"] = args["relation"]
        if "phone" in args:
            updates["phone"] = args["phone"]
        if "email" in args:
            updates["email"] = args["email"]
        if "birthday" in args:
            updates["birthday"] = args["birthday"]
        if "notes" in args:
            updates["notes"] = args["notes"]

        if not updates:
            return "No changes specified, sir."

        # Update contact
        self.db.update_contact(contact['id'], **updates)

        logger.info(f"Updated contact {contact['id']}: {updates}")

        # Return updated contact info
        updated_contact = self.db.get_contacts()
        updated = next(
            (c for c in updated_contact if c['id'] == contact['id']), None)

        if updated:
            info = [f"{get_text('contact_updated')}: {updated['name']}"]
            if updated['relation']:
                info.append(f"Relation: {updated['relation']}")
            if updated['phone']:
                info.append(f"Phone: {updated['phone']}")
            if updated.get('email'):
                info.append(f"Email: {updated['email']}")
            if updated['birthday']:
                info.append(
                    f"Birthday: {self._format_birthday(updated['birthday'])}")
            return "\n".join(info)

        return f"{get_text('contact_updated')}: {old_name}"

    async def _delete_contact(self, args: Dict[str, Any]) -> str:
        """Delete a contact."""
        name = args.get("name", "")
        if not name:
            return "Please provide a contact name to delete, sir."

        # Find contact by name
        contact = self.db.search_contact(name)
        if not contact:
            return f"{get_text('contact_not_found')}: {name}"

        # Delete contact
        success = self.db.delete_contact(contact['id'])
        if success:
            logger.info(f"Deleted contact {contact['id']}: {name}")
            return f"Contact '{name}' has been deleted, sir."
        else:
            return f"Failed to delete contact '{name}', sir."

    def _format_birthday(self, birthday_str: str) -> str:
        """Format birthday string nicely."""
        try:
            bday = datetime.fromisoformat(birthday_str)
            return bday.strftime("%B %d, %Y")
        except:
            return birthday_str








class NotificationAgent(SubAgent):
    """Handles notifications and can trigger phone calls."""

    def __init__(self):
        super().__init__(
            name="notification",
            description="Sends notifications and can trigger phone calls for important reminders"
        )

    async def execute(self, args: Dict[str, Any]) -> str:
        """Handle notification request.

        Args:
            args: {
                "message": str,
                "type": "call|message",
                "urgency": "normal|urgent"
            }
        """
        message = args.get("message", "")
        notification_type = args.get("type", "message")

        logger.info(f"Notification: {message} (type: {notification_type})")

        if notification_type == "call":
            # This would trigger a phone call in production
            return f"Phone call scheduled, sir: {message}"
        else:
            return f"{get_text('notification_sent')}: {message}"


class OutboundCallAgent(SubAgent):
    """Handles goal-based outbound calls with specific objectives."""

    def __init__(self, db: Database, twilio_handler):
        super().__init__(
            name="outbound_call",
            description="Makes goal-based outbound calls to accomplish specific tasks"
        )
        self.db = db
        self.twilio_handler = twilio_handler

    async def execute(self, args: Dict[str, Any]) -> str:
        """Handle outbound call request.

        Args:
            args: {
                "action": "schedule|list|cancel",
                "phone_number": str,
                "contact_name": str,
                "goal_type": str (appointment, inquiry, followup, etc.),
                "goal_description": str,
                "preferred_date": str (optional, e.g., "Wednesday", "2026-01-08"),
                "preferred_time": str (optional, e.g., "2pm", "afternoon"),
                "alternative_options": str (optional, e.g., "Thursday or Friday afternoon"),
                "call_now": bool (optional, default: True)
            }
        """
        action = args.get("action", "schedule")

        if action == "schedule":
            return await self._schedule_call(args)
        elif action == "list":
            return await self._list_call_goals()
        elif action == "cancel":
            return await self._cancel_call(args)
        else:
            return f"Unknown action: {action}"

    async def _schedule_call(self, args: Dict[str, Any]) -> str:
        """Schedule a goal-based outbound call."""
        phone_number = args.get("phone_number")
        contact_name = args.get("contact_name", "Unknown")
        goal_type = args.get("goal_type", "general")
        goal_description = args.get("goal_description", "")
        preferred_date = args.get("preferred_date")
        preferred_time = args.get("preferred_time")
        alternative_options = args.get("alternative_options")
        call_now = args.get("call_now", True)

        # If no phone number provided, try to look it up from contact_name
        if not phone_number and contact_name and contact_name != "Unknown":
            contact = self.db.search_contact(contact_name)
            if contact and contact.get('phone'):
                phone_number = contact['phone']
                logger.info(
                    f"Looked up phone number for {contact_name}: {phone_number}")
            else:
                return f"I couldn't find a phone number for {contact_name}, sir. Please provide a phone number or save their contact information first."

        if not phone_number or not goal_description:
            return "Please provide both phone_number and goal_description, sir."

        # Save the call goal to database
        goal_id = self.db.add_call_goal(
            phone_number=phone_number,
            contact_name=contact_name,
            goal_type=goal_type,
            goal_description=goal_description,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            alternative_options=alternative_options
        )

        logger.info(
            f"Created call goal {goal_id} for {contact_name} ({phone_number})")

        # Prepare goal message for TARS to use during the call
        goal_message = self._format_goal_message(
            contact_name, goal_type, goal_description,
            preferred_date, preferred_time, alternative_options
        )

        # Make the call immediately if requested
        if call_now:
            try:
                call_sid = self.twilio_handler.make_call(
                    to_number=phone_number,
                    reminder_message=goal_message
                )
                self.db.update_call_goal(
                    goal_id, call_sid=call_sid, status='in_progress')
                logger.info(f"Initiated call for goal {goal_id}: {call_sid}")

                return f"Understood, sir. I'll ring {contact_name} now to {goal_description}. I'll hang up with you and call you back once I've spoken with them. Goodbye for now."
            except Exception as e:
                logger.error(f"Error making call: {e}")
                self.db.fail_call_goal(
                    goal_id, f"Failed to initiate call: {str(e)}")
                return f"Sorry sir, I couldn't initiate the call to {contact_name}. Error: {str(e)}"
        else:
            return f"Call goal saved, sir. Ready to call {contact_name} when you're ready."

    def _format_goal_message(self, contact_name: str, goal_type: str,
                             goal_description: str, preferred_date: str = None,
                             preferred_time: str = None, alternative_options: str = None) -> str:
        """Format goal information into a message for TARS."""
        message_parts = [
            f"=== OUTBOUND CALL TO {contact_name.upper()} ===",
            "",
            f"YOUR TASK: {goal_description}",
            ""
        ]

        if preferred_date and preferred_time:
            message_parts.append(
                f"Preferred time: {preferred_date} at {preferred_time}")
        elif preferred_date:
            message_parts.append(f"Preferred date: {preferred_date}")
        elif preferred_time:
            message_parts.append(f"Preferred time: {preferred_time}")

        if alternative_options:
            message_parts.append(f"Backup options: {alternative_options}")

        message_parts.extend([
            "",
            "CRITICAL INSTRUCTIONS:",
            f"1. You are NOW speaking with {contact_name} - NOT with Máté",
            f"2. Start by greeting {contact_name} warmly: 'Hello!' or 'Hi there!'",
            "3. Introduce yourself: 'This is TARS, Máté's assistant'",
            f"4. Have a REAL, BACK-AND-FORTH conversation with {contact_name}",
            "5. LISTEN to what they say and RESPOND naturally to their questions",
            "6. Answer ANY questions they ask you - engage in the conversation",
            "7. Gently guide the conversation toward accomplishing your task",
            "8. Be friendly, British, personable - like chatting with a friend",
            "9. If booking appointment and time unavailable, get alternatives",
            "10. When task is done, say a warm goodbye",
            "",
            "CONVERSATION FLOW:",
            "- YOU speak first to greet them",
            "- THEN listen to their response",
            "- THEN respond to what they said",
            "- Continue this natural back-and-forth until task is complete",
            "",
            "AFTER THIS CALL ENDS:",
            "- DO NOT send a text message to Máté",
            "- The system will automatically handle notifying Máté",
            "",
            "Remember: This is a REAL conversation - listen, respond, engage naturally!"
        ])

        return "\n".join(message_parts)

    async def _list_call_goals(self) -> str:
        """List pending call goals."""
        goals = self.db.get_pending_call_goals()

        if not goals:
            return "No pending call goals, sir."

        lines = ["Your pending call goals, sir:"]
        for g in goals:
            pref = ""
            if g['preferred_date'] and g['preferred_time']:
                pref = f" (preferred: {g['preferred_date']} at {g['preferred_time']})"
            elif g['preferred_date']:
                pref = f" (preferred: {g['preferred_date']})"

            lines.append(
                f"- {g['contact_name']}: {g['goal_description']}{pref}"
            )

        return "\n".join(lines)

    async def _cancel_call(self, args: Dict[str, Any]) -> str:
        """Cancel a pending call goal."""
        goal_id = args.get("goal_id")
        contact_name = args.get("contact_name")

        if goal_id:
            self.db.fail_call_goal(goal_id, "Cancelled by user")
            return f"Call goal {goal_id} cancelled, sir."
        elif contact_name:
            # Find by contact name
            goals = self.db.get_pending_call_goals()
            match = next((g for g in goals if contact_name.lower()
                         in g['contact_name'].lower()), None)

            if match:
                self.db.fail_call_goal(match['id'], "Cancelled by user")
                return f"Call to {match['contact_name']} cancelled, sir."
            else:
                return f"Couldn't find a pending call for {contact_name}, sir."
        else:
            return "Please provide goal_id or contact_name to cancel, sir."


class InterSessionAgent(SubAgent):
    """Handles inter-session communication and coordination for agent hub."""

    def __init__(self, session_manager=None, router=None, db=None, twilio_handler=None):
        super().__init__(
            name="inter_session",
            description="Inter-agent communication and coordination"
        )
        self.session_manager = session_manager
        self.router = router
        self.db = db
        self.twilio_handler = twilio_handler

    async def execute(self, args: Dict[str, Any]) -> str:
        """Execute inter-session operation.

        Args:
            args: {
                "action": "send_message|request_confirmation|broadcast|list_sessions|take_message|schedule_callback",
                ... (action-specific parameters)
            }
        """
        action = args.get("action", "send_message")

        if action == "send_message":
            return await self._send_message(args)
        elif action == "request_confirmation":
            return await self._request_confirmation(args)
        elif action == "broadcast":
            # Broadcast is now handled by _send_message
            return await self._send_message(args)
        elif action == "list_sessions":
            return await self._list_sessions(args)
        elif action == "take_message":
            # Take message is now handled by _send_message
            return await self._send_message(args)
        elif action == "schedule_callback":
            return await self._schedule_callback(args)
        elif action == "hangup":
            return await self._hangup_call(args)
        elif action == "get_session_info":
            return await self._get_session_info(args)
        elif action == "suspend_session":
            return await self._suspend_session(args)
        elif action == "resume_session":
            return await self._resume_session(args)
        else:
            return f"Unknown action: {action}"

    async def _send_message(self, args: Dict[str, Any]) -> str:
        """Send message to specific session, user, or broadcast to multiple sessions.
        
        Unified function that handles:
        - Direct messages to specific sessions (target_session_name)
        - Taking messages for Máté (target="user" or take_message action)
        - Broadcasting to multiple sessions (target_sessions as list or comma-separated)
        """
        if not self.router or not self.session_manager:
            return "Inter-session communication not available, sir."

        # Support multiple ways to specify target
        target = args.get("target_session_name") or args.get("target")
        target_sessions = args.get("target_sessions", "")
        message = args.get("message")
        message_type = args.get("message_type", "direct")
        context = args.get("context", "")
        action = args.get("action", "send_message")
        
        # Handle take_message action - route to user
        if action == "take_message" or args.get("take_message", False):
            caller_name = args.get("caller_name", "Unknown caller")
            callback_requested = args.get("callback_requested", False)
            
            if not message:
                return "Please provide a message."
            
            source_session = args.get('_source_session')
            formatted_msg = f"Message from {caller_name}: {message}"
            if callback_requested:
                formatted_msg += f"\n(Caller requested a callback)"
            
            await self.router.route_message(
                from_session=source_session,
                message=formatted_msg,
                target="user",
                message_type="notification"
            )
            return f"I've relayed your message to {Config.TARGET_NAME}. He'll get back to you soon."

        # Handle broadcast action
        if action == "broadcast" or target_sessions:
            if not message:
                return "Please provide a message to broadcast, sir."
            
            source_session = args.get('_source_session')
            session_group = args.get("session_group", "default")
            
            # Check if this group already approved
            approval = self.db.get_broadcast_approval(session_group) if self.db else None
            
            if not approval or approval['approved'] == 0:
                # First time - ask user for permission
                question = f"I'd like to share this information with all {session_group} sessions: '{message}'. Should I broadcast this?"
                
                await self.router.route_message(
                    from_session=source_session,
                    message=question,
                    target="user",
                    message_type="broadcast_approval_request",
                    context={"session_group": session_group, "message": message}
                )
                
                # Store pending approval
                if self.db and not approval:
                    self.db.add_broadcast_approval(session_group, approved=0)
                
                return f"Requesting permission from Máté to broadcast to {session_group} sessions, sir..."
            
            elif approval['approved'] == 1:
                # Already approved - go ahead
                if isinstance(target_sessions, str):
                    session_list = [s.strip() for s in target_sessions.split(",") if s.strip()]
                elif isinstance(target_sessions, list):
                    session_list = target_sessions
                else:
                    session_list = []
                
                await self.router.route_message(
                    from_session=source_session,
                    message=message,
                    target=session_list if session_list else "user",
                    message_type="broadcast",
                    context={"session_group": session_group}
                )
                
                return f"Message broadcasted to {len(session_list)} sessions, sir."
            
            else:
                return "Broadcast permission was denied by Máté, sir."

        # Default: send to specific session or user
        if not target:
            # If no target specified, default to user (take_message behavior)
            target = "user"
            message_type = "notification"
        
        if not message:
            return "Please provide a message, sir."

        # Get source session (injected by SessionManager wrapper)
        source_session = args.get('_source_session')

        await self.router.route_message(
            from_session=source_session,
            message=message,
            target=target,
            message_type=message_type,
            context={"detail": context}
        )

        return f"Message sent to {target}, sir."

    async def _request_confirmation(self, args: Dict[str, Any]) -> str:
        """Request user confirmation/decision"""
        if not self.router:
            return "Inter-session communication not available, sir."

        question = args.get("question")
        context = args.get("context", "")
        options = args.get("options", "yes/no")

        if not question:
            return "Please provide a question, sir."

        source_session = args.get('_source_session')

        # Format confirmation request
        formatted_message = f"{question} Options: {options}. Context: {context}"

        await self.router.route_message(
            from_session=source_session,
            message=formatted_message,
            target="user",
            message_type="confirmation_request",
            context={"question": question,
                     "options": options, "detail": context}
        )

        return "Confirmation request sent to Máté, sir. Awaiting response."


    async def _list_sessions(self, args: Dict[str, Any]) -> str:
        """List active sessions"""
        if not self.session_manager:
            return "Session management not available, sir."

        filter_type = args.get("filter", "all").lower()

        active_sessions = await self.session_manager.get_active_sessions()

        if not active_sessions:
            return "No active sessions at the moment, sir."

        # Filter sessions
        if filter_type == "outbound":
            sessions = [
                s for s in active_sessions if s.session_type.value == "outbound_goal"]
        elif filter_type == "inbound":
            sessions = [
                s for s in active_sessions if "inbound" in s.session_type.value]
        elif filter_type == "mate_only":
            sessions = [s for s in active_sessions if s.has_full_access()]
        else:  # all
            sessions = active_sessions

        if not sessions:
            return f"No {filter_type} sessions active, sir."

        # Format list
        session_list = []
        for s in sessions:
            session_list.append(
                f"- {s.session_name} ({s.permission_level.value} access, {s.session_type.value})")

        return f"Active sessions ({len(sessions)}):\n" + "\n".join(session_list)


    def _parse_vague_callback_time(self, time_str: str) -> Optional[datetime]:
        """Parse vague callback time expressions into specific datetime.
        
        Handles:
        - "in the morning" → 8am today (or tomorrow if morning has passed)
        - "as soon as you see it" → 5 minutes from now
        - "this afternoon" → 2pm today
        - "this evening" → 6pm today
        - "tonight" → 7pm today
        - Regular times like "3pm", "tomorrow at 8am", etc.
        
        Returns:
            Parsed datetime or None if parsing fails
        """
        time_str_lower = time_str.lower().strip()
        now = datetime.now()
        
        # Handle vague time expressions
        if "as soon as you see it" in time_str_lower or "as soon as possible" in time_str_lower or "asap" in time_str_lower:
            # 5 minutes from now
            return now + timedelta(minutes=5)
        
        if "in the morning" in time_str_lower or "this morning" in time_str_lower:
            # 8am today or tomorrow
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if target < now:
                target += timedelta(days=1)
            return target
        
        if "this afternoon" in time_str_lower or "in the afternoon" in time_str_lower:
            # 2pm today
            target = now.replace(hour=14, minute=0, second=0, microsecond=0)
            if target < now:
                target += timedelta(days=1)
            return target
        
        if "this evening" in time_str_lower or "in the evening" in time_str_lower or "tonight" in time_str_lower:
            # 6pm today (or 7pm for tonight)
            hour = 19 if "tonight" in time_str_lower else 18
            target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if target < now:
                target += timedelta(days=1)
            return target
        
        # Try to use ReminderAgent's _parse_time logic for regular times
        # Create a temporary ReminderAgent instance to use its parsing
        try:
            from sub_agents_tars import ReminderAgent
            temp_reminder = ReminderAgent(self.db)
            parsed = temp_reminder._parse_time(time_str)
            if parsed and 'datetime' in parsed:
                return parsed['datetime']
        except:
            pass
        
        # Fallback: try dateutil parser
        try:
            from dateutil import parser
            parsed_dt = parser.parse(time_str, fuzzy=True, default=now)
            if parsed_dt < now:
                parsed_dt += timedelta(days=1)
            return parsed_dt
        except:
            pass
        
        return None

    async def _schedule_callback(self, args: Dict[str, Any]) -> str:
        """Schedule callback for limited access caller"""
        caller_name = args.get("caller_name", "Unknown caller")
        callback_time = args.get("callback_time")
        reason = args.get("reason")

        if not callback_time or not reason:
            return "Please provide callback time and reason."

        # Create a reminder for Máté to call back
        if self.db:
            try:
                # Try to parse vague times first
                callback_dt = self._parse_vague_callback_time(callback_time)
                
                if not callback_dt:
                    # Fallback to dateutil if vague parsing fails
                    try:
                        from dateutil import parser
                        callback_dt = parser.parse(
                            callback_time, fuzzy=True, default=datetime.now())
                        # If parsed date is in the past, assume it's for tomorrow
                        if callback_dt < datetime.now():
                            callback_dt += timedelta(days=1)
                    except ImportError:
                        logger.error(
                            "CRITICAL: 'python-dateutil' is not installed. Please run 'pip install python-dateutil'. Falling back to a simple reminder.")
                        # Fallback if dateutil is not installed
                        reminder_title = f"Call back {caller_name} ({callback_time}) about: {reason}"
                        # Schedule for 1 hour from now as a simple fallback
                        callback_dt = datetime.now() + timedelta(hours=1)
                        self.db.add_reminder(
                            title=reminder_title,
                            datetime_str=callback_dt.isoformat()
                        )
                        return f"I've noted your callback request for {callback_time}. {Config.TARGET_NAME} will get back to you."
                    except Exception as e:
                        logger.error(f"Error parsing callback time: {e}")
                        return f"I've noted your callback request for {callback_time}. {Config.TARGET_NAME} will get back to you."

                reminder_title = f"Call back {caller_name}: {reason}"

                self.db.add_reminder(
                    title=reminder_title,
                    datetime_str=callback_dt.isoformat()
                )
                return f"I've scheduled a callback reminder for {Config.TARGET_NAME} at {callback_dt.strftime('%I:%M %p on %B %d')}. He'll call you back then."
            except Exception as e:
                logger.error(
                    f"Error parsing callback time or scheduling reminder: {e}")
                return f"I've noted your callback request for {callback_time}. {Config.TARGET_NAME} will get back to you."
        else:
            return f"I've noted your callback request. {Config.TARGET_NAME} will get back to you."

    async def _hangup_call(self, args: Dict[str, Any]) -> str:
        """Hang up a specific call session."""
        if not self.session_manager or not self.twilio_handler:
            return "Call management is not available, sir."

        target_name = args.get("target_session_name")
        if not target_name:
            return "Please specify which call to hang up using 'target_session_name'."

        source_session = args.get('_source_session')

        # #region debug log
        try:
            with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                import json
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "sub_agents_tars.py:_hangup_call:entry", "message": "Hangup call requested", "data": {"target_name": target_name, "has_source_session": source_session is not None}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
        except:
            pass
        # #endregion

        if target_name.lower() == 'current':
            if source_session:
                target_session = source_session
            else:
                return "I cannot determine the 'current' call to hang up."
        else:
            # Try exact match first
            target_session = await self.session_manager.get_session_by_name(target_name)
            
            # If not found, try fuzzy matching - extract name from "Call with {name}"
            if not target_session and "call with" in target_name.lower():
                # Extract the name part (e.g., "John" from "Call with John")
                name_part = target_name.lower().replace("call with", "").strip()
                # Try to find session by contact name
                all_sessions = await self.session_manager.get_active_sessions()
                for session in all_sessions:
                    session_name_lower = session.session_name.lower()
                    if name_part in session_name_lower or session_name_lower.endswith(name_part):
                        target_session = session
                        break
            
            # #region debug log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "sub_agents_tars.py:_hangup_call:after_lookup", "message": "After session lookup", "data": {"found": target_session is not None, "session_name": target_session.session_name if target_session else None}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion

        if not target_session:
            # List available sessions for debugging
            all_sessions = await self.session_manager.get_active_sessions()
            session_names = [s.session_name for s in all_sessions]
            return f"I could not find an active session named '{target_name}' to hang up. Active sessions: {', '.join(session_names) if session_names else 'none'}."

        if not target_session.is_active():
            return f"The session '{target_name}' is not currently active."

        # Use the twilio_handler to hang up the call
        success = self.twilio_handler.hangup_call(target_session.call_sid)

        if success:
            return f"The call with '{target_session.session_name}' has been terminated, sir."
        else:
            return f"I was unable to terminate the call with '{target_session.session_name}' due to an error."

    async def _get_session_info(self, args: Dict[str, Any]) -> str:
        """Get detailed information about a session."""
        if not self.session_manager:
            return "Session management not available, sir."

        session_id = args.get("session_id")
        session_name = args.get("session_name")

        if not session_id and not session_name:
            return "Please provide session_id or session_name, sir."

        info = await self.session_manager.get_session_info(
            session_id=session_id,
            session_name=session_name
        )

        if not info:
            return f"Session not found: {session_id or session_name}, sir."

        # Format response
        lines = [f"Session Information for '{info['session_name']}':"]
        lines.append(f"  Status: {info['status']} ({'Active' if info['is_active'] else 'Inactive'})")
        lines.append(f"  Type: {info['session_type']}")
        lines.append(f"  Permission: {info['permission_level']}")
        lines.append(f"  Phone: {info['phone_number']}")
        lines.append(f"  Messages: {info['message_count']}")
        if info.get('purpose'):
            lines.append(f"  Purpose: {info['purpose']}")
        if info.get('created_at'):
            lines.append(f"  Created: {info['created_at']}")

        return "\n".join(lines)

    async def _suspend_session(self, args: Dict[str, Any]) -> str:
        """Suspend a session for later resumption."""
        if not self.session_manager:
            return "Session management not available, sir."

        session_id = args.get("session_id")
        session_name = args.get("session_name")
        reason = args.get("reason", "user_request")

        if not session_id and not session_name:
            return "Please provide session_id or session_name, sir."

        success = await self.session_manager.suspend_session(
            session_id=session_id,
            session_name=session_name,
            reason=reason
        )

        if success:
            target = session_id or session_name
            return f"Session '{target}' has been suspended, sir."
        else:
            return f"Failed to suspend session '{session_id or session_name}', sir. It may not be active or may not exist."

    async def _resume_session(self, args: Dict[str, Any]) -> str:
        """Resume a suspended session."""
        if not self.session_manager:
            return "Session management not available, sir."

        session_id = args.get("session_id")
        session_name = args.get("session_name")

        if not session_id and not session_name:
            return "Please provide session_id or session_name, sir."

        # Note: For full resumption with new connection, call_sid, websocket, and stream_sid would be needed
        # This is a simplified version that just marks the session as active
        session = await self.session_manager.resume_session(
            session_id=session_id,
            session_name=session_name
        )

        if session:
            return f"Session '{session.session_name}' has been resumed, sir."
        else:
            return f"Failed to resume session '{session_id or session_name}', sir. It may not be suspended or may not exist."


class ConversationSearchAgent(SubAgent):
    """Handles conversation search by date, topic, and similarity."""

    def __init__(self, db: Database):
        super().__init__(
            name="conversation_search",
            description="Search conversations by date, topic, or similarity"
        )
        self.db = db

    async def execute(self, args: Dict[str, Any]) -> str:
        """Execute conversation search operation.

        Args:
            args: {
                "action": "search_by_date|search_by_topic|search_by_similarity",
                "query": str (date string, topic, or search query),
                "limit": int (optional, default: 20)
            }
        """
        action = args.get("action", "search_by_date")
        query = args.get("query", "")
        limit = args.get("limit", 20)

        if not query:
            return "Please provide a search query, sir."

        from core.config import Config

        if action == "search_by_date":
            results = self.db.search_conversations_by_date(query, limit=limit)
            if not results:
                return f"No conversations found for date: {query}, sir."
            
            lines = [f"Found {len(results)} conversations for {query}:"]
            for conv in results[:10]:  # Show first 10
                timestamp = conv.get('timestamp', '')
                sender = conv.get('sender', 'unknown')
                message_preview = conv.get('message', '')[:100]
                lines.append(f"  [{timestamp}] {sender}: {message_preview}...")
            return "\n".join(lines)

        elif action == "search_by_topic":
            if not Config.GEMINI_API_KEY:
                return "Conversation search by topic requires Gemini API key, sir."
            
            results = self.db.search_conversations_by_topic(
                query, Config.GEMINI_API_KEY, limit=limit
            )
            if not results:
                return f"No conversations found for topic: {query}, sir."
            
            lines = [f"Found {len(results)} conversations about '{query}':"]
            for conv in results[:10]:  # Show first 10
                similarity = conv.get('similarity', 0)
                timestamp = conv.get('timestamp', '')
                sender = conv.get('sender', 'unknown')
                message_preview = conv.get('message', '')[:100]
                lines.append(f"  [{timestamp}] {sender}: {message_preview}... (similarity: {similarity:.2f})")
            return "\n".join(lines)

        elif action == "search_by_similarity":
            if not Config.GEMINI_API_KEY:
                return "Conversation search by similarity requires Gemini API key, sir."
            
            results = self.db.search_conversations_by_similarity(
                query, Config.GEMINI_API_KEY, limit=limit
            )
            if not results:
                return f"No similar conversations found for: {query}, sir."
            
            lines = [f"Found {len(results)} similar conversations to '{query}':"]
            for conv in results[:10]:  # Show first 10
                similarity = conv.get('similarity', 0)
                timestamp = conv.get('timestamp', '')
                sender = conv.get('sender', 'unknown')
                message_preview = conv.get('message', '')[:100]
                lines.append(f"  [{timestamp}] {sender}: {message_preview}... (similarity: {similarity:.2f})")
            return "\n".join(lines)

        else:
            return f"Unknown search action: {action}"


# MessagingAgent removed - all messaging moved to KIPP via send_to_n8n function


class KIPPAgent(SubAgent):
    """Handles all communication tasks via KIPP (Gmail, Calendar, Telegram, Discord)."""

    def __init__(self):
        super().__init__(
            name="kipp",
            description="Send messages and tasks to KIPP. KIPP handles Gmail, Calendar, Telegram, and Discord automatically."
        )

    async def execute(self, args: Dict[str, Any]) -> str:
        """Execute KIPP operation.

        Args:
            args: {
                "message": str - the user's request/task description
            }
        """
        message = args.get("message", "")
        
        if not message:
            return "Please provide a message or task description, sir."
        
        return await self._send_to_kipp(message)

    async def _send_to_kipp(self, message: str) -> str:
        """Send message/task to KIPP via HTTP POST.

        Args:
            message: User's request/task description

        Returns:
            Response message
        """
        import aiohttp
        import json
        
        n8n_webhook_url = Config.N8N_WEBHOOK_URL
        
        if not n8n_webhook_url:
            logger.error("KIPP webhook URL not configured")
            return "KIPP webhook URL is not configured, sir. Please set N8N_WEBHOOK_URL in your .env file."
        
        # Fix common .env file issues: remove duplicate variable name if present
        if n8n_webhook_url.startswith("N8N_WEBHOOK_URL="):
            n8n_webhook_url = n8n_webhook_url.replace("N8N_WEBHOOK_URL=", "", 1)
            logger.warning("Fixed KIPP webhook URL: removed duplicate variable name prefix")
        
        # #region agent log
        try:
            with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                import time
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"sub_agents_tars.py:_send_to_kipp","message":"Attempting KIPP connection","data":{"url_length":len(n8n_webhook_url),"url_starts_with_http":n8n_webhook_url.startswith("http"),"message_preview":message[:50]},"timestamp":int(time.time()*1000)})+"\n")
        except:
            pass
        # #endregion
        
        # Enhance message for email requests - replace "Máté" with actual email
        # This helps KIPP's AI agent know the recipient email address
        enhanced_message = message
        try:
            if Config.TARGET_EMAIL and ("email" in message.lower() or "send" in message.lower()):
                # If message mentions "Máté" or user's name, replace with email for clarity
                target_name = Config.TARGET_NAME or "Máté"
                if target_name.lower() in message.lower() or "me" in message.lower() or "my" in message.lower():
                    # Replace name references with email address
                    # Replace "to Máté" or "to me" with "to {email}"
                    enhanced_message = re.sub(
                        rf'\bto\s+({re.escape(target_name)}|me|my)\b',
                        f'to {Config.TARGET_EMAIL}',
                        message,
                        flags=re.IGNORECASE
                    )
                    # Also handle "send email Máté" format (but be careful not to replace in the middle of words)
                    if enhanced_message == message:  # Only if first replacement didn't work
                        enhanced_message = re.sub(
                            rf'\b({re.escape(target_name)}|me|my)\b',
                            Config.TARGET_EMAIL,
                            message,
                            flags=re.IGNORECASE
                        )
                    if enhanced_message != message:
                        logger.info(f"Enhanced KIPP message: '{message}' -> '{enhanced_message}'")
        except Exception as e:
            logger.warning(f"Error enhancing KIPP message, using original: {e}")
            enhanced_message = message  # Fallback to original message
        
        try:
            payload = {
                "message": enhanced_message
            }
            
            # #region agent log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import time
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"sub_agents_tars.py:_send_to_kipp","message":"Creating HTTP session","data":{"timeout":10},"timestamp":int(time.time()*1000)})+"\n")
            except:
                pass
            # #endregion
            
            async with aiohttp.ClientSession() as session:
                # #region agent log
                try:
                    with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                        import time
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"sub_agents_tars.py:_send_to_kipp","message":"Sending POST request","data":{"url":n8n_webhook_url},"timestamp":int(time.time()*1000)})+"\n")
                except:
                    pass
                # #endregion
                
                async with session.post(
                    n8n_webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    # #region agent log
                    try:
                        with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                            import time
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"sub_agents_tars.py:_send_to_kipp","message":"Received HTTP response","data":{"status":response.status,"headers":dict(response.headers)},"timestamp":int(time.time()*1000)})+"\n")
                    except:
                        pass
                    # #endregion
                    
                    if response.status == 200:
                        try:
                            result = await response.json()
                            # #region agent log
                            try:
                                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                                    import time
                                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"sub_agents_tars.py:_send_to_kipp","message":"KIPP response received","data":{"payload_sent":payload,"response_body":result},"timestamp":int(time.time()*1000)})+"\n")
                            except:
                                pass
                            # #endregion
                            logger.info(f"Successfully sent message to KIPP: {message[:50]}... Response: {result}")
                            return f"I've sent your request to KIPP, sir. {result.get('message', 'Task received.')}"
                        except:
                            text_result = await response.text()
                            # #region agent log
                            try:
                                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                                    import time
                                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"sub_agents_tars.py:_send_to_kipp","message":"KIPP text response received","data":{"payload_sent":payload,"response_text":text_result},"timestamp":int(time.time()*1000)})+"\n")
                            except:
                                pass
                            # #endregion
                            logger.info(f"Successfully sent message to KIPP: {message[:50]}... Response: {text_result}")
                            return f"I've sent your request to KIPP, sir. {text_result if text_result else 'Task received.'}"
                    else:
                        error_text = await response.text()
                        logger.error(f"KIPP webhook error {response.status}: {error_text}")
                        # #region agent log
                        try:
                            with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                                import time
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"sub_agents_tars.py:_send_to_kipp","message":"KIPP returned non-200 status","data":{"status":response.status,"error_text":error_text[:200]},"timestamp":int(time.time()*1000)})+"\n")
                        except:
                            pass
                        # #endregion
                        return f"I encountered an error sending to KIPP (status {response.status}), sir. Please try again."
        
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Error connecting to KIPP (connection failed): {type(e).__name__}: {e}")
            # #region agent log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import time
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"sub_agents_tars.py:_send_to_kipp","message":"Connection error","data":{"error_type":type(e).__name__,"error_message":str(e),"url":n8n_webhook_url},"timestamp":int(time.time()*1000)})+"\n")
            except:
                pass
            # #endregion
            return f"I couldn't connect to KIPP, sir. Please check the webhook URL and try again."
        except aiohttp.ClientError as e:
            logger.error(f"Error connecting to KIPP (client error): {type(e).__name__}: {e}")
            # #region agent log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import time
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"sub_agents_tars.py:_send_to_kipp","message":"Client error","data":{"error_type":type(e).__name__,"error_message":str(e),"url":n8n_webhook_url},"timestamp":int(time.time()*1000)})+"\n")
            except:
                pass
            # #endregion
            return f"I couldn't connect to KIPP, sir. Please check the webhook URL and try again."
        except asyncio.TimeoutError as e:
            logger.error(f"Error connecting to KIPP (timeout): {e}")
            # #region agent log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import time
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"sub_agents_tars.py:_send_to_kipp","message":"Timeout error","data":{"error_type":type(e).__name__,"url":n8n_webhook_url},"timestamp":int(time.time()*1000)})+"\n")
            except:
                pass
            # #endregion
            return f"Connection to KIPP timed out, sir. Please check the webhook URL and try again."
        except Exception as e:
            logger.error(f"Unexpected error sending to KIPP: {type(e).__name__}: {e}")
            # #region agent log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import time
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ALL","location":"sub_agents_tars.py:_send_to_kipp","message":"Unexpected error","data":{"error_type":type(e).__name__,"error_message":str(e),"url":n8n_webhook_url},"timestamp":int(time.time()*1000)})+"\n")
            except:
                pass
            # #endregion
            return f"An unexpected error occurred while sending to KIPP, sir: {str(e)}"


class ProgrammerAgent(SubAgent):
    """Handles programming tasks: file operations, terminal commands, code editing, and GitHub operations."""

    def __init__(self, db: Database):
        super().__init__(
            name="programmer",
            description="Manages programming projects, executes terminal commands, edits code, and handles GitHub operations"
        )
        self.db = db
        from utils.github_operations import GitHubOperations
        self.github = GitHubOperations()
        
        # Safe commands that don't need confirmation
        self.safe_commands = {
            'ls', 'pwd', 'cd', 'cat', 'echo', 'git status', 'git log', 
            'git diff', 'git branch', 'npm install', 'pip install', 
            'pip list', 'npm list', 'node --version', 'python --version',
            'python3 --version', 'which', 'whereis'
        }
        
        # Destructive commands that require confirmation
        self.destructive_patterns = [
            'rm ', 'rmdir', 'git push', 'git push --force', 'git reset --hard',
            'dd ', 'mkfs', 'sudo', 'chmod', 'chown'
        ]
        # Note: Removed '>' and '>>' to allow file redirection for normal operations

    async def execute(self, args: Dict[str, Any]) -> str:
        """Execute programmer operation.

        Args:
            args: Operation arguments with 'action' field
        """
        action = args.get('action', '')
        
        # Route based on action type first, then parameters
        # Check file operations first (most specific)
        if 'file_path' in args and action in ['read', 'edit', 'create', 'delete']:
            return await self.edit_code(args)
        # Check GitHub operations
        elif action in ['clone', 'push', 'pull', 'create_repo', 'list_repos', 'init'] or 'repo_url' in args:
            return await self.github_operation(args)
        # Check project management
        elif action in ['list', 'create', 'open', 'info'] or ('project_name' in args and 'file_path' not in args):
            return await self.manage_project(args)
        # Check terminal commands
        elif 'command' in args:
            return await self.execute_terminal(args)
        else:
            return "Invalid programmer operation, sir."

    async def manage_project(self, args: Dict[str, Any]) -> str:
        """Manage programming projects.

        Args:
            args: {
                "action": "list|create|open|info",
                "project_name": str,
                "project_type": str (optional),
                "path": str (optional)
            }
        """
        action = args.get('action', 'list')
        
        if action == 'list':
            return await self._list_projects(args.get('path', Config.PROJECTS_ROOT))
        elif action == 'create':
            return await self._create_project(args)
        elif action == 'open':
            return await self._open_project(args.get('project_name'))
        elif action == 'info':
            return await self._get_project_info(args.get('project_name'))
        else:
            return f"Unknown project action: {action}, sir."

    async def _list_projects(self, base_path: str) -> str:
        """List all projects in a directory."""
        try:
            import os
            from pathlib import Path
            
            base = Path(base_path).expanduser()
            if not base.exists():
                return f"Directory {base_path} does not exist, sir."
            
            # Find directories that look like projects
            projects = []
            for item in base.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    # Check for common project indicators
                    is_project = any([
                        (item / '.git').exists(),
                        (item / 'package.json').exists(),
                        (item / 'requirements.txt').exists(),
                        (item / 'setup.py').exists(),
                        (item / 'Cargo.toml').exists(),
                        (item / 'go.mod').exists()
                    ])
                    
                    if is_project:
                        project_type = self._detect_project_type(item)
                        git_status = 'initialized' if (item / '.git').exists() else 'none'
                        projects.append({
                            'name': item.name,
                            'path': str(item),
                            'type': project_type,
                            'git': git_status
                        })
                        # Cache this project
                        self.db.cache_project(item.name, str(item), project_type, git_status)
            
            if not projects:
                return f"No projects found in {base_path}, sir."
            
            result = f"Found {len(projects)} project(s) in {base_path}:\n"
            for p in projects:
                result += f"\n- {p['name']}: {p['type']} (Git: {p['git']})"
            
            return result
            
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return f"Error listing projects: {str(e)}, sir."

    def _detect_project_type(self, project_path: Path) -> str:
        """Detect project type from files."""
        if (project_path / 'package.json').exists():
            package_json = project_path / 'package.json'
            try:
                import json
                with open(package_json) as f:
                    data = json.load(f)
                    if 'react' in str(data.get('dependencies', {})):
                        return 'react'
                    elif 'next' in str(data.get('dependencies', {})):
                        return 'next'
                    else:
                        return 'node'
            except:
                return 'node'
        elif (project_path / 'requirements.txt').exists() or (project_path / 'setup.py').exists():
            return 'python'
        elif (project_path / 'Cargo.toml').exists():
            return 'rust'
        elif (project_path / 'go.mod').exists():
            return 'go'
        else:
            return 'unknown'

    async def _create_project(self, args: Dict[str, Any]) -> str:
        """Create a new project."""
        try:
            import os
            from pathlib import Path
            
            project_name = args.get('project_name')
            project_type = args.get('project_type', 'python')
            base_path = args.get('path', Config.PROJECTS_ROOT)
            
            if not project_name:
                return "Please provide a project name, sir."
            
            project_path = Path(base_path).expanduser() / project_name
            
            if project_path.exists():
                return f"Project {project_name} already exists at {project_path}, sir."
            
            # Create project directory
            project_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize based on project type
            if project_type == 'python':
                # Create basic Python project structure
                (project_path / 'main.py').write_text('#!/usr/bin/env python3\n"""Main module."""\n\nif __name__ == "__main__":\n    print("Hello, World!")\n')
                (project_path / 'requirements.txt').write_text('# Python dependencies\n')
                (project_path / 'README.md').write_text(f'# {project_name}\n\nA Python project.\n')
            elif project_type in ['node', 'react', 'next']:
                # Create package.json
                import json
                package_data = {
                    'name': project_name,
                    'version': '1.0.0',
                    'description': f'A {project_type} project',
                    'main': 'index.js',
                    'scripts': {'start': 'node index.js'},
                    'author': '',
                    'license': 'ISC'
                }
                (project_path / 'package.json').write_text(json.dumps(package_data, indent=2))
                (project_path / 'index.js').write_text('console.log("Hello, World!");\n')
                (project_path / 'README.md').write_text(f'# {project_name}\n\nA {project_type} project.\n')
            else:
                # Generic project
                (project_path / 'README.md').write_text(f'# {project_name}\n\nA new project.\n')
            
            # Cache the project
            self.db.cache_project(project_name, str(project_path), project_type, 'none')
            
            logger.info(f"Created project: {project_name} at {project_path}")
            return f"Created {project_type} project '{project_name}' at {project_path}, sir."
            
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            return f"Error creating project: {str(e)}, sir."

    async def _open_project(self, project_name: str) -> str:
        """Open a project and return its structure."""
        try:
            from pathlib import Path
            
            if not project_name:
                return "Please provide a project name, sir."
            
            # Check cache first
            cached = self.db.get_cached_project(project_name)
            if cached:
                project_path = Path(cached['project_path'])
            else:
                # Try to find it
                project_path = Path(Config.PROJECTS_ROOT).expanduser() / project_name
            
            if not project_path.exists():
                return f"Project {project_name} not found, sir."
            
            # Get project structure
            structure = self._get_directory_structure(project_path, max_depth=2)
            
            # Update cache
            project_type = self._detect_project_type(project_path)
            git_status = 'initialized' if (project_path / '.git').exists() else 'none'
            self.db.cache_project(project_name, str(project_path), project_type, git_status)
            
            return f"Opened project '{project_name}':\nPath: {project_path}\nType: {project_type}\n\nStructure:\n{structure}"
            
        except Exception as e:
            logger.error(f"Error opening project: {e}")
            return f"Error opening project: {str(e)}, sir."

    def _get_directory_structure(self, path: Path, prefix: str = "", max_depth: int = 3, current_depth: int = 0) -> str:
        """Get a tree structure of a directory."""
        if current_depth >= max_depth:
            return ""
        
        try:
            items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            structure = ""
            
            for i, item in enumerate(items):
                # Skip hidden files and common exclusions
                if item.name.startswith('.') or item.name in ['node_modules', '__pycache__', 'venv', 'env']:
                    continue
                
                is_last = i == len(items) - 1
                connector = "└── " if is_last else "├── "
                
                if item.is_dir():
                    structure += f"{prefix}{connector}{item.name}/\n"
                    extension = "    " if is_last else "│   "
                    structure += self._get_directory_structure(item, prefix + extension, max_depth, current_depth + 1)
                else:
                    structure += f"{prefix}{connector}{item.name}\n"
            
            return structure
        except PermissionError:
            return f"{prefix}[Permission Denied]\n"

    async def _get_project_info(self, project_name: str) -> str:
        """Get detailed information about a project."""
        try:
            from pathlib import Path
            
            cached = self.db.get_cached_project(project_name)
            if not cached:
                return f"Project {project_name} not found in cache. Try listing projects first, sir."
            
            project_path = Path(cached['project_path'])
            
            if not project_path.exists():
                return f"Project path {project_path} no longer exists, sir."
            
            info = f"Project: {project_name}\n"
            info += f"Path: {project_path}\n"
            info += f"Type: {cached.get('project_type', 'unknown')}\n"
            info += f"Git Status: {cached.get('git_status', 'none')}\n"
            info += f"Last Accessed: {cached.get('last_accessed', 'never')}\n"
            
            # Check for git repo
            if (project_path / '.git').exists():
                branch = await self.github.get_current_branch(str(project_path))
                if branch:
                    info += f"Git Branch: {branch}\n"
                
                git_status_result = await self.github.git_status(str(project_path))
                if git_status_result.get('success'):
                    if git_status_result.get('clean'):
                        info += "Working tree: clean\n"
                    else:
                        info += "Working tree: has changes\n"
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting project info: {e}")
            return f"Error getting project info: {str(e)}, sir."

    async def execute_terminal(self, args: Dict[str, Any]) -> str:
        """Execute terminal command with safety checks.

        Args:
            args: {
                "command": str,
                "working_directory": str (optional),
                "timeout": int (optional)
            }
        """
        try:
            import subprocess
            from pathlib import Path
            
            command = args.get('command', '').strip()
            working_dir = args.get('working_directory', Config.PROJECTS_ROOT)
            timeout = args.get('timeout', Config.MAX_COMMAND_TIMEOUT)
            
            if not command:
                return "Please provide a command to execute, sir."
            
            # Check if command is safe and verify confirmation code
            needs_confirmation = self._is_destructive_command(command)
            
            if needs_confirmation:
                from core.security import verify_confirmation_code
                confirmation_code = args.get('confirmation_code', '')
                
                if not verify_confirmation_code(confirmation_code):
                    return f"This command requires confirmation code: {command}\nPlease provide your confirmation code to proceed, sir."
            
            # Log operation
            session_id = args.get('session_id', 'unknown')
            op_id = self.db.log_programming_operation(
                session_id=session_id,
                operation_type='terminal',
                command=command,
                working_directory=working_dir,
                status='pending'
            )
            
            # Execute command
            try:
                # Expand working directory
                work_path = Path(working_dir).expanduser()
                if not work_path.exists():
                    self.db.update_programming_operation(op_id, 'failed', error=f"Directory {working_dir} does not exist")
                    return f"Directory {working_dir} does not exist, sir."
                
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(work_path),
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                output = result.stdout if result.stdout else result.stderr
                
                if result.returncode == 0:
                    self.db.update_programming_operation(op_id, 'executed', output=output)
                    logger.info(f"Executed command: {command}")
                    return f"Command executed successfully:\n\n{output}" if output else "Command executed successfully, sir."
                else:
                    self.db.update_programming_operation(op_id, 'failed', output=output, error=result.stderr)
                    return f"Command failed with exit code {result.returncode}:\n\n{result.stderr or output}"
                    
            except subprocess.TimeoutExpired:
                self.db.update_programming_operation(op_id, 'failed', error='Command timed out')
                return f"Command timed out after {timeout} seconds, sir."
                
        except Exception as e:
            logger.error(f"Error executing terminal command: {e}")
            return f"Error executing command: {str(e)}, sir."

    def _is_destructive_command(self, command: str) -> bool:
        """Check if a command is potentially destructive."""
        command_lower = command.lower()
        
        # Check for destructive patterns
        for pattern in self.destructive_patterns:
            if pattern in command_lower:
                return True
        
        return False

    async def edit_code(self, args: Dict[str, Any]) -> str:
        """Edit code files with AI assistance.

        Args:
            args: {
                "action": "read|edit|create|delete",
                "file_path": str,
                "changes_description": str,
                "content": str (for create action)
            }
        """
        action = args.get('action', 'read')
        file_path = args.get('file_path', '')
        
        if not file_path:
            return "Please provide a file path, sir."
        
        if action == 'read':
            return await self._read_file(file_path)
        elif action == 'create':
            return await self._create_file(file_path, args.get('content', ''))
        elif action == 'edit':
            return await self._edit_file(file_path, args.get('changes_description', ''))
        elif action == 'delete':
            return await self._delete_file(file_path, args.get('confirmation_code', ''))
        else:
            return f"Unknown file action: {action}, sir."

    async def _read_file(self, file_path: str) -> str:
        """Read a file."""
        try:
            from pathlib import Path
            
            path = Path(file_path).expanduser()
            if not path.exists():
                return f"File {file_path} does not exist, sir."
            
            if path.stat().st_size > 100000:  # 100KB limit
                return f"File {file_path} is too large to read (>100KB), sir."
            
            content = path.read_text()
            return f"File: {file_path}\n\n{content}"
            
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return f"Error reading file: {str(e)}, sir."

    async def _create_file(self, file_path: str, content: str) -> str:
        """Create a new file."""
        try:
            from pathlib import Path
            
            path = Path(file_path).expanduser()
            
            if path.exists():
                return f"File {file_path} already exists. Use edit action to modify it, sir."
            
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            path.write_text(content)
            
            logger.info(f"Created file: {file_path}")
            return f"Created file {file_path}, sir."
            
        except Exception as e:
            logger.error(f"Error creating file: {e}")
            return f"Error creating file: {str(e)}, sir."

    async def _edit_file(self, file_path: str, changes_description: str) -> str:
        """Edit a file using AI."""
        try:
            from pathlib import Path
            import difflib
            
            path = Path(file_path).expanduser()
            
            if not path.exists():
                return f"File {file_path} does not exist, sir."
            
            # Read current content
            original_content = path.read_text()
            
            # Backup file if enabled
            if Config.ENABLE_CODE_BACKUPS:
                backup_dir = path.parent / '.tars_backups'
                backup_dir.mkdir(exist_ok=True)
                from datetime import datetime
                backup_name = f"{path.name}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                (backup_dir / backup_name).write_text(original_content)
            
            # Use Gemini to generate changes
            from google import genai
            client = genai.Client(
                http_options={"api_version": "v1beta"},
                api_key=Config.GEMINI_API_KEY
            )
            
            prompt = f"""Analyze this code and apply these changes: {changes_description}

Current code in {path.name}:
```
{original_content}
```

Respond with ONLY the complete modified file content, no explanations."""
            
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt
            )
            
            modified_content = response.text.strip()
            
            # Remove markdown code blocks if present
            if modified_content.startswith('```'):
                lines = modified_content.split('\n')
                modified_content = '\n'.join(lines[1:-1]) if len(lines) > 2 else modified_content
            
            # Generate diff
            diff = difflib.unified_diff(
                original_content.splitlines(keepends=True),
                modified_content.splitlines(keepends=True),
                fromfile=f'{path.name} (original)',
                tofile=f'{path.name} (modified)',
                lineterm=''
            )
            diff_text = ''.join(diff)
            
            # Write modified content
            path.write_text(modified_content)
            
            logger.info(f"Edited file: {file_path}")
            return f"Edited file {file_path}. Changes:\n\n{diff_text[:1000]}"  # Limit diff output
            
        except Exception as e:
            logger.error(f"Error editing file: {e}")
            return f"Error editing file: {str(e)}, sir."

    async def _delete_file(self, file_path: str, confirmation_code: str = '') -> str:
        """Delete a file (requires confirmation code)."""
        from core.security import verify_confirmation_code
        
        if not verify_confirmation_code(confirmation_code):
            return f"Deleting {file_path} requires confirmation code. Please provide your confirmation code to proceed, sir."
        
        # Proceed with deletion
        try:
            file_path_obj = Path(file_path).expanduser()
            if not file_path_obj.exists():
                return f"File {file_path} does not exist, sir."
            
            file_path_obj.unlink()
            logger.info(f"Deleted file: {file_path}")
            return f"Deleted file {file_path}, sir."
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return f"Error deleting file: {str(e)}, sir."

    async def github_operation(self, args: Dict[str, Any]) -> str:
        """Handle GitHub operations.

        Args:
            args: {
                "action": "clone|push|pull|create_repo|list_repos|init",
                "repo_name": str,
                "repo_url": str,
                "commit_message": str,
                "branch": str
            }
        """
        action = args.get('action', '')
        
        if action == 'init':
            return await self._git_init(args.get('working_directory', '.'))
        elif action == 'list_repos':
            return await self._list_repos()
        elif action == 'create_repo':
            return await self._create_repo(args)
        elif action == 'clone':
            return await self._clone_repo(args)
        elif action == 'push':
            return await self._git_push(args)
        elif action == 'pull':
            return await self._git_pull(args)
        else:
            return f"Unknown GitHub action: {action}, sir."

    async def _git_init(self, directory: str) -> str:
        """Initialize git repository."""
        result = await self.github.git_init(directory)
        if result.get('success'):
            return f"Initialized git repository in {directory}, sir."
        return f"Failed to initialize git: {result.get('error')}, sir."

    async def _list_repos(self) -> str:
        """List GitHub repositories."""
        if not self.github.is_authenticated():
            return "GitHub authentication not configured. Please set GITHUB_TOKEN in .env, sir."
        
        repos = await self.github.list_repositories()
        if not repos:
            return "No repositories found or error accessing GitHub, sir."
        
        result = f"Found {len(repos)} repositories:\n"
        for repo in repos[:10]:  # Limit to 10
            result += f"\n- {repo['name']}: {repo['url']}"
        
        return result

    async def _create_repo(self, args: Dict[str, Any]) -> str:
        """Create GitHub repository."""
        repo_name = args.get('repo_name', '')
        description = args.get('description', '')
        private = args.get('private', False)
        
        if not repo_name:
            return "Please provide a repository name, sir."
        
        if not self.github.is_authenticated():
            return "GitHub authentication not configured. Please set GITHUB_TOKEN in .env file, sir."
        
        result = await self.github.create_repository(repo_name, description, private)
        if result.get('success'):
            return f"Created GitHub repository '{repo_name}' at {result.get('url')}, sir."
        return f"Failed to create repository: {result.get('error')}, sir."

    async def _clone_repo(self, args: Dict[str, Any]) -> str:
        """Clone a repository."""
        repo_url = args.get('repo_url', '')
        target_dir = args.get('target_dir', '')
        
        if not repo_url:
            return "Please provide a repository URL, sir."
        
        if not target_dir:
            # Extract repo name from URL
            repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
            target_dir = str(Path(Config.PROJECTS_ROOT).expanduser() / repo_name)
        
        result = await self.github.clone_repository(repo_url, target_dir)
        if result.get('success'):
            return f"Cloned repository to {target_dir}, sir."
        return f"Failed to clone repository: {result.get('error')}, sir."

    async def _git_push(self, args: Dict[str, Any]) -> str:
        """Push to GitHub."""
        working_dir = args.get('working_directory', '.')
        branch = args.get('branch', 'main')
        commit_message = args.get('commit_message', 'Update files')
        
        # First, add and commit changes
        commit_result = await self.github.git_add_commit(working_dir, commit_message)
        if not commit_result.get('success'):
            return f"Failed to commit: {commit_result.get('error')}, sir."
        
        # Then push
        push_result = await self.github.git_push(working_dir, branch)
        if push_result.get('success'):
            return f"Pushed to {branch}: {push_result.get('message')}, sir."
        return f"Failed to push: {push_result.get('error')}, sir."

    async def _git_pull(self, args: Dict[str, Any]) -> str:
        """Pull from GitHub."""
        working_dir = args.get('working_directory', '.')
        branch = args.get('branch', 'main')
        
        result = await self.github.git_pull(working_dir, branch)
        if result.get('success'):
            return f"Pulled from {branch}: {result.get('message')}, sir."
        return f"Failed to pull: {result.get('error')}, sir."


# Agent registry


def get_all_agents(db: Database, messaging_handler=None, system_reloader_callback=None, twilio_handler=None, session_manager=None, router=None) -> Dict[str, SubAgent]:
    """Get all available sub-agents for TARS.

    Args:
        db: Database instance
        messaging_handler: Optional MessagingHandler instance for messaging operations
        system_reloader_callback: Optional callback to reload system instructions

    Returns:
        Dictionary of agent_name -> agent_instance
    """
    agents = {
        "config": ConfigAgent(db, system_reloader_callback),
        "reminder": ReminderAgent(db),
        "contacts": ContactsAgent(db),
        "notification": NotificationAgent(),
        "conversation_search": ConversationSearchAgent(db),
    }

    # Add outbound call agent if twilio_handler is provided
    if twilio_handler:
        agents["outbound_call"] = OutboundCallAgent(db, twilio_handler)

    # Add inter-session agent if session_manager and router are provided
    if session_manager and router:
        agents["inter_session"] = InterSessionAgent(
            session_manager, router, db, twilio_handler)

    # MessagingAgent removed - all messaging moved to KIPP

    # Add KIPP agent for all communication tasks
    agents["kipp"] = KIPPAgent()

    # Add programmer agent
    agents["programmer"] = ProgrammerAgent(db)

    return agents


def get_function_declarations() -> list:
    """Get function declarations for all sub-agents.

    Returns:
        List of function declarations for Gemini
    """
    return [
        {
            "name": "adjust_config",
            "description": "Adjust TARS settings. Available settings: humor (0-100%), honesty (0-100%), personality (chatty/normal/brief), nationality, reminder_delivery (call/message/email/both), callback_report (call/message/email/both), voice (Puck/Kore/Charon), reminder_check_interval (seconds), conversation_history_limit (messages). Examples: 'set humor to 65%', 'make yourself more chatty', 'set personality to brief', 'become American', 'send reminders via email', 'set callback report to both', 'set voice to Kore', 'set reminder check interval to 30 seconds'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: 'set' (change value) or 'get' (check current value)"
                    },
                    "setting": {
                        "type": "STRING",
                        "description": "Setting to adjust: 'humor', 'honesty', 'personality', 'nationality', 'reminder_delivery', 'callback_report', 'voice', 'reminder_check_interval', or 'conversation_history_limit'"
                    },
                    "value": {
                        "type": "STRING",
                        "description": "New value. For humor/honesty: 0-100. For personality: 'chatty', 'normal', or 'brief'. For nationality: any nationality. For reminder_delivery/callback_report: 'call', 'message', 'email', or 'both'. For voice: 'Puck', 'Kore', or 'Charon'. For intervals: number in seconds. For conversation_history_limit: number of messages."
                    }
                },
                "required": ["action", "setting"]
            }
        },
        {
            "name": "manage_reminder",
            "description": "Create, list, delete, delete all, or edit reminders. Supports recurring reminders (daily, weekly). Examples: 'remind me to workout every day at 6am', 'what reminders do I have', 'delete my 8am reminder', 'delete all reminders', 'change the 9am reminder to 10am'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: create, list, delete, delete_all, or edit"
                    },
                    "title": {
                        "type": "STRING",
                        "description": "Reminder description. For edit: can be used to find reminder or set new title"
                    },
                    "time": {
                        "type": "STRING",
                        "description": "When to remind: '3pm', 'tomorrow at 8am', 'every day at 1pm', 'every monday at 2pm'. For edit: new time for the reminder"
                    },
                    "old_title": {
                        "type": "STRING",
                        "description": "For edit: the current title/name of the reminder to find"
                    },
                    "old_time": {
                        "type": "STRING",
                        "description": "For edit: the current time of the reminder to find (e.g., '9am', '3pm')"
                    },
                    "new_title": {
                        "type": "STRING",
                        "description": "For edit: the new title/name for the reminder"
                    },
                    "new_time": {
                        "type": "STRING",
                        "description": "For edit: the new time for the reminder (e.g., '10am', 'tomorrow at 2pm')"
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "lookup_contact",
            "description": "CRITICAL: You MUST call this function to look up, add, edit, delete, or list contacts. NEVER rely on conversation history for contact information - always call this function to get current data from the database. Examples: 'what is Helen's email' → call with action='lookup', 'list all contacts' → call with action='list', 'add a new contact' → call with action='add'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: lookup (find specific contact), list (all contacts - ALWAYS call this, never use conversation history), birthday_check (check today's birthdays), add (create new contact), edit (update existing contact), or delete (remove contact)"
                    },
                    "name": {
                        "type": "STRING",
                        "description": "Contact name. For lookup/add: the name. For edit: can be used to find contact or set new name"
                    },
                    "relation": {
                        "type": "STRING",
                        "description": "Relationship (e.g., 'girlfriend', 'friend', 'family'). For add/edit actions"
                    },
                    "phone": {
                        "type": "STRING",
                        "description": "Phone number. For add/edit actions"
                    },
                    "email": {
                        "type": "STRING",
                        "description": "Email address. For add/edit actions"
                    },
                    "birthday": {
                        "type": "STRING",
                        "description": "Birthday in YYYY-MM-DD format (e.g., '2004-08-27'). For add/edit actions"
                    },
                    "notes": {
                        "type": "STRING",
                        "description": "Additional notes or bio about the contact (e.g., 'Loves hiking and photography', 'Works as software engineer at Google'). For add/edit actions"
                    },
                    "old_name": {
                        "type": "STRING",
                        "description": "For edit: the current name of the contact to find"
                    },
                    "new_name": {
                        "type": "STRING",
                        "description": "For edit: the new name for the contact"
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "send_notification",
            "description": "Send a notification or trigger a phone call",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "message": {
                        "type": "STRING",
                        "description": "Notification message"
                    },
                    "type": {
                        "type": "STRING",
                        "description": "Type: 'call' (phone call) or 'message' (notification)"
                    }
                },
                "required": ["message"]
            }
        },
        {
            "name": "get_current_time",
            "description": "Get the current date and time. Use this whenever you need to know what time it is right now.",
            "parameters": {
                "type": "OBJECT",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "search_conversations",
            "description": "Search past conversations by date, topic, or similarity. Examples: 'find conversations from last monday', 'search for conversations about AI glasses', 'find similar conversations to this topic'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: 'search_by_date' (e.g., 'last monday', 'january 12'), 'search_by_topic' (e.g., 'AI glasses'), or 'search_by_similarity' (semantic similarity search)"
                    },
                    "query": {
                        "type": "STRING",
                        "description": "Search query: date string (for search_by_date), topic (for search_by_topic), or search text (for search_by_similarity)"
                    },
                    "limit": {
                        "type": "STRING",
                        "description": "Maximum number of results (optional, default: 20)"
                    }
                },
                "required": ["action", "query"]
            }
        },

        {
            "name": "make_goal_call",
            "description": "Make an outbound phone call with a specific goal/objective. Use this when Máté asks you to call someone to accomplish something (book appointment, make inquiry, follow up, etc.). Examples: 'call my dentist to book an appointment for Wednesday at 2pm', 'call the DMV to ask about my license renewal', 'call Helen to see if she wants to meet for dinner'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: 'schedule' (make call), 'list' (show pending calls), or 'cancel' (cancel scheduled call)"
                    },
                    "phone_number": {
                        "type": "STRING",
                        "description": "Phone number to call (for schedule action). Can look up from contacts if contact_name is provided instead."
                    },
                    "contact_name": {
                        "type": "STRING",
                        "description": "Name of person/organization to call (e.g., 'Dr. Smith', 'Dentist Office', 'Helen')"
                    },
                    "goal_type": {
                        "type": "STRING",
                        "description": "Type of goal: 'appointment', 'inquiry', 'followup', 'reservation', 'support', or 'general'"
                    },
                    "goal_description": {
                        "type": "STRING",
                        "description": "Detailed description of what to accomplish on the call (e.g., 'Book a dental cleaning appointment')"
                    },
                    "preferred_date": {
                        "type": "STRING",
                        "description": "Preferred date for appointment/meeting (e.g., 'Wednesday', 'January 8th', 'next Monday')"
                    },
                    "preferred_time": {
                        "type": "STRING",
                        "description": "Preferred time (e.g., '2pm', 'afternoon', 'morning')"
                    },
                    "alternative_options": {
                        "type": "STRING",
                        "description": "Alternative times/dates if preferred not available (e.g., 'Thursday or Friday afternoon', 'any time next week')"
                    },
                    "call_now": {
                        "type": "STRING",
                        "description": "Whether to make the call immediately. Default: 'true'"
                    }
                },
                "required": ["action"]
            }
        },
        # Inter-session communication functions
        {
            "name": "send_message_to_session",
            "description": "Send a message to another active agent session, take a message for Máté, or broadcast to multiple sessions (unified inter-session communication). Use when you need to communicate with another ongoing call, relay a message from a caller to Máté, or broadcast to multiple sessions. Examples: 'Tell the Barber Shop call that 7pm works', 'Take a message for Máté from John', 'Broadcast to all hotel calls that we got $60/night quote'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: 'send_message' (to specific session), 'take_message' (relay to Máté), or 'broadcast' (to multiple sessions)"
                    },
                    "target_session_name": {
                        "type": "STRING",
                        "description": "Name of the target session (e.g., 'Máté (main)', 'Call with Barber Shop'). For take_message, use 'user' or omit. For broadcast, use target_sessions instead."
                    },
                    "target": {
                        "type": "STRING",
                        "description": "Alternative to target_session_name. Use 'user' to send to Máté (take_message behavior)."
                    },
                    "target_sessions": {
                        "type": "STRING",
                        "description": "For broadcast: comma-separated list of session names, or 'all' for all active sessions"
                    },
                    "message": {
                        "type": "STRING",
                        "description": "Message to send"
                    },
                    "caller_name": {
                        "type": "STRING",
                        "description": "For take_message: caller's name"
                    },
                    "callback_requested": {
                        "type": "STRING",
                        "description": "For take_message: 'true' if caller requested callback"
                    },
                    "session_group": {
                        "type": "STRING",
                        "description": "For broadcast: group identifier for approval tracking (e.g., 'hotel_negotiations')"
                    },
                    "message_type": {
                        "type": "STRING",
                        "description": "Type: 'direct' (simple message), 'confirmation_request' (awaiting yes/no), 'update' (FYI), 'notification' (for take_message)"
                    },
                    "context": {
                        "type": "STRING",
                        "description": "Additional context about why you're sending this message"
                    }
                },
                "required": ["action", "message"]
            }
        },
        {
            "name": "request_user_confirmation",
            "description": "Request a yes/no decision from Máté. Use when you need user approval for an action. This will route to Máté's active call if in one, or send SMS/call if not. Examples: 'Does 7pm work instead of 6pm?', 'Suite Inn quoted $60/night, should I accept?'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: always 'request_confirmation'"
                    },
                    "question": {
                        "type": "STRING",
                        "description": "The yes/no question to ask Máté"
                    },
                    "context": {
                        "type": "STRING",
                        "description": "Context about what you're doing (e.g., 'negotiating with barber', 'comparing hotel prices')"
                    },
                    "options": {
                        "type": "STRING",
                        "description": "Available options (e.g., 'yes/no', '7pm or 8pm', 'Drury at $100 or Suite Inn at $60')"
                    }
                },
                "required": ["action", "question", "context"]
            }
        },
        {
            "name": "list_active_sessions",
            "description": "List all currently active agent sessions. Use to see what other calls are ongoing. Useful for coordination.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: always 'list_sessions'"
                    },
                    "filter": {
                        "type": "STRING",
                        "description": "Optional filter: 'all', 'outbound', 'inbound', 'mate_only'"
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "schedule_callback",
            "description": "Schedule a callback for unknown caller. For limited-access sessions only. Creates a reminder for Máté to call them back.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: always 'schedule_callback'"
                    },
                    "caller_name": {
                        "type": "STRING",
                        "description": "Caller's name"
                    },
                    "callback_time": {
                        "type": "STRING",
                        "description": "When to callback (e.g., 'tomorrow 2pm', 'next Monday morning')"
                    },
                    "reason": {
                        "type": "STRING",
                        "description": "Reason for callback"
                    }
                },
                "required": ["action", "callback_time", "reason"]
            }
        },
        {
            "name": "hangup_call",
            "description": "Hang up or terminate an active phone call session. Use this when you need to end a specific call, including your own. Examples: 'hang up this call', 'terminate the call with the barber shop'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: always 'hangup'"
                    },
                    "target_session_name": {
                        "type": "STRING",
                        "description": "The name of the session to hang up (e.g., 'Call with +14045565930', 'Call with Barber Shop'). Use 'current' to hang up the call you are on."
                    }
                },
                "required": ["action", "target_session_name"]
            }
        },
        {
            "name": "get_session_info",
            "description": "Get detailed information about a session including status, type, message count, and other metadata.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: always 'get_session_info'"
                    },
                    "session_id": {
                        "type": "STRING",
                        "description": "Session UUID (optional if session_name provided)"
                    },
                    "session_name": {
                        "type": "STRING",
                        "description": "Session name (e.g., 'Call with Helen', 'Call with Máté (main)') - optional if session_id provided"
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "suspend_session",
            "description": "Suspend a session for later resumption. Saves conversation state so it can be resumed later.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: always 'suspend_session'"
                    },
                    "session_id": {
                        "type": "STRING",
                        "description": "Session UUID (optional if session_name provided)"
                    },
                    "session_name": {
                        "type": "STRING",
                        "description": "Session name (e.g., 'Call with Helen') - optional if session_id provided"
                    },
                    "reason": {
                        "type": "STRING",
                        "description": "Reason for suspension (optional, default: 'user_request')"
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "resume_session",
            "description": "Resume a previously suspended session. Restores conversation history and reactivates the session.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: always 'resume_session'"
                    },
                    "session_id": {
                        "type": "STRING",
                        "description": "Session UUID (optional if session_name provided)"
                    },
                    "session_name": {
                        "type": "STRING",
                        "description": "Session name (e.g., 'Call with Helen') - optional if session_id provided"
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "suggest_phone_call",
            "description": "Suggest to Máté that a call would be better for discussing the topic. Use when conversation via message is getting complex or would benefit from voice discussion.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: always 'suggest_call'"
                    },
                    "reason": {
                        "type": "STRING",
                        "description": "Why a call would be better (e.g., 'This topic has many details that would be easier to discuss verbally')"
                    }
                },
                "required": ["action", "reason"]
            }
        },
        {
            "name": "send_to_n8n",
            "description": "Send a message or task to KIPP. KIPP handles Gmail, Calendar, Telegram, and Discord. Just describe what you want to do (e.g., 'send email to John about meeting', 'send telegram message to Helen', 'check calendar for tomorrow', 'send discord message to team'). KIPP will automatically figure out which tool to use based on your request.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "message": {
                        "type": "STRING",
                        "description": "The user's request or task description. Describe what you want to do with Gmail, Calendar, Telegram, or Discord. Examples: 'send email to john@example.com about the meeting', 'send telegram message to Helen saying hello', 'check my calendar for tomorrow', 'send discord message to the team channel'"
                    }
                },
                "required": ["message"]
            }
        },
        {
            "name": "manage_project",
            "description": "Manage coding projects in /Users/matedort/: list all projects, create new project, open existing project, or get project info. Use this to navigate and manage Máté's programming projects.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action to perform: 'list' (show all projects), 'create' (new project), 'open' (open existing project), 'info' (get project details)"
                    },
                    "project_name": {
                        "type": "STRING",
                        "description": "Name of the project (required for create, open, info actions)"
                    },
                    "project_type": {
                        "type": "STRING",
                        "description": "Type of project for create action: 'python', 'node', 'react', 'next', or 'vanilla-js'"
                    },
                    "path": {
                        "type": "STRING",
                        "description": "Optional: custom path to search for projects (default: /Users/matedort/)"
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "execute_terminal",
            "description": "Execute terminal commands in a project directory. Safe commands (ls, pwd, git status, npm install, pip install) execute immediately. Destructive commands (rm, git push, sudo) require confirmation_code parameter.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "command": {
                        "type": "STRING",
                        "description": "Shell command to execute (e.g., 'npm install', 'python main.py', 'git status')"
                    },
                    "working_directory": {
                        "type": "STRING",
                        "description": "Directory to run command in (default: /Users/matedort/)"
                    },
                    "timeout": {
                        "type": "INTEGER",
                        "description": "Maximum seconds to wait for command (default: 60, max: 600)"
                    },
                    "confirmation_code": {
                        "type": "STRING",
                        "description": "Confirmation code required for destructive commands (rm, sudo, etc.). Ask user for their confirmation code if needed."
                    }
                },
                "required": ["command"]
            }
        },
        {
            "name": "edit_code",
            "description": "Read, create, edit, or delete code files using AI. For edit action, describe the changes you want (e.g., 'change background color to blue', 'fix the bug in login function', 'add error handling'). AI will analyze the code, generate changes, and show a diff before applying. Delete action requires confirmation_code.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: 'read' (view file), 'create' (new file), 'edit' (modify with AI), 'delete' (remove file - requires confirmation_code)"
                    },
                    "file_path": {
                        "type": "STRING",
                        "description": "Full path to the file (e.g., '/Users/matedort/simple-portfolio/style.css')"
                    },
                    "changes_description": {
                        "type": "STRING",
                        "description": "For edit action: describe what to change (e.g., 'change background to blue', 'add login validation')"
                    },
                    "content": {
                        "type": "STRING",
                        "description": "For create action: the file content to write"
                    },
                    "confirmation_code": {
                        "type": "STRING",
                        "description": "Confirmation code required for delete action. Ask user for their confirmation code when deleting files."
                    }
                },
                "required": ["action", "file_path"]
            }
        },
        {
            "name": "github_operation",
            "description": "GitHub operations: initialize git repo, clone repository, push changes, pull changes, create new repository, list repositories. Handles git workflow including commits. Note: Push and create_repo actions can be performed without confirmation_code since you're authorized.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: 'init' (git init), 'clone' (clone repo), 'push' (push changes with commit), 'pull' (pull changes), 'create_repo' (new GitHub repo), 'list_repos' (show repositories)"
                    },
                    "repo_name": {
                        "type": "STRING",
                        "description": "Repository name (for create_repo action)"
                    },
                    "repo_url": {
                        "type": "STRING",
                        "description": "Repository URL for clone action (e.g., 'https://github.com/user/repo.git')"
                    },
                    "commit_message": {
                        "type": "STRING",
                        "description": "Commit message for push action (e.g., 'Update background color')"
                    },
                    "branch": {
                        "type": "STRING",
                        "description": "Branch name (default: 'main')"
                    },
                    "working_directory": {
                        "type": "STRING",
                        "description": "Directory for git operations (default: current project)"
                    },
                    "confirmation_code": {
                        "type": "STRING",
                        "description": "Optional confirmation code for sensitive operations (not required for you)"
                    }
                },
                "required": ["action"]
            }
        }
    ]
