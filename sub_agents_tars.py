"""Sub-agents for TARS - Máté's Personal Assistant."""
import asyncio
import logging
import os
from typing import Dict, Any
from datetime import datetime, timedelta
from gemini_live_client import SubAgent
from database import Database
from translations import get_text, format_text
from config import Config
import re

logger = logging.getLogger(__name__)


class ConfigAgent(SubAgent):
    """Manages TARS configuration settings dynamically."""

    def __init__(self, db: Database, system_reloader_callback=None):
        super().__init__(
            name="config_agent",
            description="Adjusts TARS personality settings (humor and honesty percentages)"
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

        if setting not in ["humor", "honesty"]:
            return "Please specify either 'humor' or 'honesty' setting."

        if action == "set":
            return await self._set_config(setting, args.get("value"))
        elif action == "get":
            return await self._get_config(setting)
        else:
            return f"Unknown action: {action}"

    async def _set_config(self, setting: str, value: Any) -> str:
        """Set a configuration value."""
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

    async def _get_config(self, setting: str) -> str:
        """Get current configuration value."""
        if setting == "humor":
            value = Config.HUMOR_PERCENTAGE
        elif setting == "honesty":
            value = Config.HONESTY_PERCENTAGE
        else:
            return f"Unknown setting: {setting}"

        return format_text('config_current_value', setting=setting, value=value)

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
                "action": "create|list|delete|edit",
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

        logger.info(f"Created reminder {reminder_id}: {title} at {reminder_time}")

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

            target_time = target_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

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
                "birthday": str (optional, YYYY-MM-DD format),
                "notes": str (optional),
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
                if contact['birthday']:
                    info.append(f"Birthday: {self._format_birthday(contact['birthday'])}")
                return "\n".join(info)
            else:
                return f"{get_text('contact_not_found')}: {name}"

        elif action == "list":
            contacts = self.db.get_contacts()
            if not contacts:
                return "You have no contacts saved, sir."

            lines = ["Your contacts, sir:"]
            for c in contacts:
                lines.append(f"- {c['name']} ({c['relation']})")
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
                        upcoming.append(format_text('birthday_today', name=c['name']))

            return "\n".join(upcoming) if upcoming else get_text('no_birthdays_today')

        elif action == "add":
            return await self._add_contact(args)

        elif action == "edit":
            return await self._edit_contact(args)

        else:
            return f"Unknown contact action: {action}"

    async def _add_contact(self, args: Dict[str, Any]) -> str:
        """Add a new contact."""
        name = args.get("name", "")
        if not name:
            return "Please provide a name for the contact, sir."

        relation = args.get("relation")
        phone = args.get("phone")
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
        updated = next((c for c in updated_contact if c['id'] == contact['id']), None)

        if updated:
            info = [f"{get_text('contact_updated')}: {updated['name']}"]
            if updated['relation']:
                info.append(f"Relation: {updated['relation']}")
            if updated['phone']:
                info.append(f"Phone: {updated['phone']}")
            if updated['birthday']:
                info.append(f"Birthday: {self._format_birthday(updated['birthday'])}")
            return "\n".join(info)

        return f"{get_text('contact_updated')}: {old_name}"

    def _format_birthday(self, birthday_str: str) -> str:
        """Format birthday string nicely."""
        try:
            bday = datetime.fromisoformat(birthday_str)
            return bday.strftime("%B %d, %Y")
        except:
            return birthday_str


class MessageAgent(SubAgent):
    """Agent for sending SMS and WhatsApp messages to the user."""

    def __init__(self, messaging_handler):
        super().__init__(
            name="message_agent",
            description="Sends SMS/WhatsApp messages and links to the user"
        )
        self.messaging_handler = messaging_handler

    async def execute(self, args: Dict[str, Any]) -> str:
        """Handle message sending request.

        Args:
            args: {
                "action": "send" or "send_link",
                "message": str (message text or link description),
                "link": str (URL for send_link action),
                "medium": "sms" or "whatsapp"
            }
        """
        action = args.get("action", "send")
        message = args.get("message", "")
        link = args.get("link", "")
        medium = args.get("medium", "sms")

        logger.info(f"MessageAgent: {action} via {medium}")

        if action == "send_link":
            # Send a link with optional description
            self.messaging_handler.send_link(
                to_number=Config.TARGET_PHONE_NUMBER,
                url=link,
                description=message,
                medium=medium
            )
            return f"Link sent via {medium}, sir."
        else:
            # Send regular message
            self.messaging_handler.send_message(
                to_number=Config.TARGET_PHONE_NUMBER,
                message_body=message,
                medium=medium
            )
            return f"Message sent via {medium}, sir."


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

        logger.info(f"Created call goal {goal_id} for {contact_name} ({phone_number})")

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
                self.db.update_call_goal(goal_id, call_sid=call_sid, status='in_progress')
                logger.info(f"Initiated call for goal {goal_id}: {call_sid}")

                return f"Call initiated to {contact_name}, sir. Goal: {goal_description}"
            except Exception as e:
                logger.error(f"Error making call: {e}")
                self.db.fail_call_goal(goal_id, f"Failed to initiate call: {str(e)}")
                return f"Sorry sir, I couldn't initiate the call to {contact_name}. Error: {str(e)}"
        else:
            return f"Call goal saved, sir. Ready to call {contact_name} when you're ready."

    def _format_goal_message(self, contact_name: str, goal_type: str,
                             goal_description: str, preferred_date: str = None,
                             preferred_time: str = None, alternative_options: str = None) -> str:
        """Format goal information into a message for TARS."""
        message_parts = [
            f"CALL OBJECTIVE for {contact_name}:",
            f"Type: {goal_type}",
            f"Goal: {goal_description}"
        ]

        if preferred_date and preferred_time:
            message_parts.append(f"Preferred: {preferred_date} at {preferred_time}")
        elif preferred_date:
            message_parts.append(f"Preferred date: {preferred_date}")
        elif preferred_time:
            message_parts.append(f"Preferred time: {preferred_time}")

        if alternative_options:
            message_parts.append(f"Alternatives: {alternative_options}")

        message_parts.append(
            "\nIMPORTANT: If the preferred time is not available, "
            "gather alternative times and text them to Máté for approval."
        )

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
            match = next((g for g in goals if contact_name.lower() in g['contact_name'].lower()), None)

            if match:
                self.db.fail_call_goal(match['id'], "Cancelled by user")
                return f"Call to {match['contact_name']} cancelled, sir."
            else:
                return f"Couldn't find a pending call for {contact_name}, sir."
        else:
            return "Please provide goal_id or contact_name to cancel, sir."


# Agent registry
def get_all_agents(db: Database, messaging_handler=None, system_reloader_callback=None, twilio_handler=None) -> Dict[str, SubAgent]:
    """Get all available sub-agents for TARS.

    Args:
        db: Database instance
        messaging_handler: Optional MessagingHandler instance for MessageAgent
        system_reloader_callback: Optional callback to reload system instructions

    Returns:
        Dictionary of agent_name -> agent_instance
    """
    agents = {
        "config": ConfigAgent(db, system_reloader_callback),
        "reminder": ReminderAgent(db),
        "contacts": ContactsAgent(db),
        "notification": NotificationAgent(),
    }

    # Add message agent if messaging_handler is provided
    if messaging_handler:
        agents["message"] = MessageAgent(messaging_handler)

    # Add outbound call agent if twilio_handler is provided
    if twilio_handler:
        agents["outbound_call"] = OutboundCallAgent(db, twilio_handler)

    return agents


def get_function_declarations() -> list:
    """Get function declarations for all sub-agents.

    Returns:
        List of function declarations for Gemini
    """
    return [
        {
            "name": "adjust_config",
            "description": "Adjust TARS personality settings. Use this when Máté asks to change humor or honesty levels, or asks what they're currently set to. Examples: 'set humor to 65%', 'what's my humor percentage', 'make yourself more honest', 'set honesty to 90'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: 'set' (change value) or 'get' (check current value)"
                    },
                    "setting": {
                        "type": "STRING",
                        "description": "Setting to adjust: 'humor' or 'honesty'"
                    },
                    "value": {
                        "type": "STRING",
                        "description": "New value (0-100) for set action"
                    }
                },
                "required": ["action", "setting"]
            }
        },
        {
            "name": "manage_reminder",
            "description": "Create, list, delete, or edit reminders. Supports recurring reminders (daily, weekly). Examples: 'remind me to workout every day at 6am', 'what reminders do I have', 'delete my 8am reminder', 'change the 9am reminder to 10am'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: create, list, delete, or edit"
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
            "description": "Look up, add, edit, or manage family and friends contact information including phone numbers, birthdays, and relationships. Examples: 'what is Helen's phone number', 'add a new contact', 'edit contact information'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: lookup (find specific contact), list (all contacts), birthday_check (check today's birthdays), add (create new contact), or edit (update existing contact)"
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
                    "birthday": {
                        "type": "STRING",
                        "description": "Birthday in YYYY-MM-DD format (e.g., '2004-08-27'). For add/edit actions"
                    },
                    "notes": {
                        "type": "STRING",
                        "description": "Additional notes about the contact. For add/edit actions"
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
            "name": "send_message",
            "description": "Send a text message or link to Máté via SMS or WhatsApp. Use this when user requests links during phone calls or to send follow-up information.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: 'send' (text message) or 'send_link' (send URL)"
                    },
                    "message": {
                        "type": "STRING",
                        "description": "Message text or link description"
                    },
                    "link": {
                        "type": "STRING",
                        "description": "URL to send (for send_link action)"
                    },
                    "medium": {
                        "type": "STRING",
                        "description": "Communication medium: 'sms' or 'whatsapp' (default: sms)"
                    }
                },
                "required": ["action", "message"]
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
        }
    ]
