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
import anthropic

logger = logging.getLogger(__name__)


class ConfigAgent(SubAgent):
    """Manages TARS configuration settings dynamically."""

    def __init__(self, db: Database, system_reloader_callback=None):
        super().__init__(
            name="config_agent",
            description="Adjusts TARS settings (humor, honesty, personality, voice, delivery channels, programming model, etc.)"
        )
        self.db = db
        self.system_reloader_callback = system_reloader_callback

    async def execute(self, args: Dict[str, Any]) -> str:
        """Execute configuration operation.

        Args:
            args: {
                "action": "set|get|list",
                "setting": setting name,
                "value": value to set
            }
        """
        action = args.get("action", "get")
        setting = args.get("setting", "").lower()

        valid_settings = [
            # Personality
            "humor", "honesty", "personality", "nationality", "voice",
            # Delivery channels (via KIPP)
            "reminder_delivery", "callback_report", "log_channel", "confirmation_channel",
            # Programming
            "programming_model", "auto_commit", "auto_push", "detailed_updates",
            # Timing
            "reminder_check_interval", "conversation_history_limit", "max_task_runtime", "approval_timeout",
            # Features
            "google_search", "call_summaries", "code_backups", "debug_mode"
        ]
        
        if action == "list":
            return await self._list_settings()
        
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

        # Handle reminder_delivery setting (call, discord, telegram)
        elif setting == "reminder_delivery":
            valid_methods = ['call', 'discord', 'telegram']
            value_str = str(value).lower()
            if value_str not in valid_methods:
                return f"Invalid reminder delivery method. Please choose: {', '.join(valid_methods)}"

            setting_key = "REMINDER_DELIVERY"
            os.environ[setting_key] = value_str
            self._update_env_file(setting_key, value_str)
            Config.reload()
            self.db.set_config(setting_key, value_str)

            logger.info(f"Updated reminder delivery to {value_str}")
            channel_note = " (via KIPP)" if value_str in ['discord', 'telegram'] else ""
            return f"Reminder delivery updated to '{value_str}'{channel_note}, sir."

        # Handle callback_report setting (call, discord, telegram)
        elif setting == "callback_report":
            valid_methods = ['call', 'discord', 'telegram']
            value_str = str(value).lower()
            if value_str not in valid_methods:
                return f"Invalid callback report method. Please choose: {', '.join(valid_methods)}"

            setting_key = "CALLBACK_REPORT"
            os.environ[setting_key] = value_str
            self._update_env_file(setting_key, value_str)
            Config.reload()
            self.db.set_config(setting_key, value_str)

            logger.info(f"Updated callback report to {value_str}")
            channel_note = " (via KIPP)" if value_str in ['discord', 'telegram'] else ""
            return f"Callback report method updated to '{value_str}'{channel_note}, sir."
        
        # Handle log_channel setting (discord, telegram)
        elif setting == "log_channel":
            valid_channels = ['discord', 'telegram']
            value_str = str(value).lower()
            if value_str not in valid_channels:
                return f"Invalid log channel. Please choose: {', '.join(valid_channels)}"

            setting_key = "LOG_CHANNEL"
            os.environ[setting_key] = value_str
            self._update_env_file(setting_key, value_str)
            Config.reload()
            self.db.set_config(setting_key, value_str)

            logger.info(f"Updated log channel to {value_str}")
            return f"Log channel updated to '{value_str}' via KIPP, sir. Status updates will go there."
        
        # Handle confirmation_channel setting (discord, telegram)
        elif setting == "confirmation_channel":
            valid_channels = ['discord', 'telegram']
            value_str = str(value).lower()
            if value_str not in valid_channels:
                return f"Invalid confirmation channel. Please choose: {', '.join(valid_channels)}"

            setting_key = "CONFIRMATION_CHANNEL"
            os.environ[setting_key] = value_str
            self._update_env_file(setting_key, value_str)
            Config.reload()
            self.db.set_config(setting_key, value_str)

            logger.info(f"Updated confirmation channel to {value_str}")
            return f"Confirmation channel updated to '{value_str}' via KIPP, sir. Approval requests will go there."
        
        # Handle programming_model setting (opus, sonnet)
        elif setting == "programming_model":
            valid_models = ['opus', 'sonnet']
            value_str = str(value).lower()
            if value_str not in valid_models:
                return f"Invalid programming model. Please choose: {', '.join(valid_models)}"

            setting_key = "PROGRAMMING_MODEL"
            os.environ[setting_key] = value_str
            self._update_env_file(setting_key, value_str)
            Config.reload()
            self.db.set_config(setting_key, value_str)

            logger.info(f"Updated programming model to {value_str}")
            model_desc = "Opus 4 (most capable)" if value_str == "opus" else "Sonnet 4 (faster)"
            return f"Programming model updated to {model_desc}, sir."
        
        # Handle auto_commit setting (on/off)
        elif setting == "auto_commit":
            value_str = str(value).lower()
            enabled = value_str in ['on', 'true', 'yes', '1', 'enabled']
            
            setting_key = "AUTO_GIT_COMMIT"
            os.environ[setting_key] = str(enabled).lower()
            self._update_env_file(setting_key, str(enabled).lower())
            Config.reload()
            self.db.set_config(setting_key, str(enabled).lower())

            logger.info(f"Updated auto commit to {enabled}")
            return f"Auto git commit {'enabled' if enabled else 'disabled'}, sir."
        
        # Handle auto_push setting (on/off)
        elif setting == "auto_push":
            value_str = str(value).lower()
            enabled = value_str in ['on', 'true', 'yes', '1', 'enabled']
            
            setting_key = "AUTO_GIT_PUSH"
            os.environ[setting_key] = str(enabled).lower()
            self._update_env_file(setting_key, str(enabled).lower())
            Config.reload()
            self.db.set_config(setting_key, str(enabled).lower())

            logger.info(f"Updated auto push to {enabled}")
            return f"Auto git push {'enabled' if enabled else 'disabled'}, sir."
        
        # Handle detailed_updates setting (on/off)
        elif setting == "detailed_updates":
            value_str = str(value).lower()
            enabled = value_str in ['on', 'true', 'yes', '1', 'enabled']
            
            setting_key = "ENABLE_DETAILED_UPDATES"
            os.environ[setting_key] = str(enabled).lower()
            self._update_env_file(setting_key, str(enabled).lower())
            Config.reload()
            self.db.set_config(setting_key, str(enabled).lower())

            logger.info(f"Updated detailed updates to {enabled}")
            return f"Detailed progress updates {'enabled' if enabled else 'disabled'}, sir."
        
        # Handle max_task_runtime setting (minutes)
        elif setting == "max_task_runtime":
            try:
                value_int = int(value)
                if value_int < 5:
                    return "Max task runtime must be at least 5 minutes, sir."
                if value_int > 60:
                    return "Max task runtime cannot exceed 60 minutes, sir."
            except (ValueError, TypeError):
                return "Invalid runtime. Please provide a number in minutes, sir."

            setting_key = "MAX_TASK_RUNTIME_MINUTES"
            os.environ[setting_key] = str(value_int)
            self._update_env_file(setting_key, str(value_int))
            Config.reload()
            self.db.set_config(setting_key, str(value_int))

            logger.info(f"Updated max task runtime to {value_int} minutes")
            return f"Max task runtime updated to {value_int} minutes, sir."
        
        # Handle approval_timeout setting (minutes)
        elif setting == "approval_timeout":
            try:
                value_int = int(value)
                if value_int < 1:
                    return "Approval timeout must be at least 1 minute, sir."
                if value_int > 30:
                    return "Approval timeout cannot exceed 30 minutes, sir."
            except (ValueError, TypeError):
                return "Invalid timeout. Please provide a number in minutes, sir."

            setting_key = "APPROVAL_TIMEOUT_MINUTES"
            os.environ[setting_key] = str(value_int)
            self._update_env_file(setting_key, str(value_int))
            Config.reload()
            self.db.set_config(setting_key, str(value_int))

            logger.info(f"Updated approval timeout to {value_int} minutes")
            return f"Approval timeout updated to {value_int} minutes, sir."
        
        # Handle google_search setting (on/off)
        elif setting == "google_search":
            value_str = str(value).lower()
            enabled = value_str in ['on', 'true', 'yes', '1', 'enabled']
            
            setting_key = "ENABLE_GOOGLE_SEARCH"
            os.environ[setting_key] = str(enabled).lower()
            self._update_env_file(setting_key, str(enabled).lower())
            Config.reload()
            self.db.set_config(setting_key, str(enabled).lower())

            logger.info(f"Updated google search to {enabled}")
            return f"Google search {'enabled' if enabled else 'disabled'}, sir."
        
        # Handle call_summaries setting (on/off)
        elif setting == "call_summaries":
            value_str = str(value).lower()
            enabled = value_str in ['on', 'true', 'yes', '1', 'enabled']
            
            setting_key = "ENABLE_CALL_SUMMARIES"
            os.environ[setting_key] = str(enabled).lower()
            self._update_env_file(setting_key, str(enabled).lower())
            Config.reload()
            self.db.set_config(setting_key, str(enabled).lower())

            logger.info(f"Updated call summaries to {enabled}")
            return f"Call summaries {'enabled' if enabled else 'disabled'}, sir."
        
        # Handle code_backups setting (on/off)
        elif setting == "code_backups":
            value_str = str(value).lower()
            enabled = value_str in ['on', 'true', 'yes', '1', 'enabled']
            
            setting_key = "ENABLE_CODE_BACKUPS"
            os.environ[setting_key] = str(enabled).lower()
            self._update_env_file(setting_key, str(enabled).lower())
            Config.reload()
            self.db.set_config(setting_key, str(enabled).lower())

            logger.info(f"Updated code backups to {enabled}")
            return f"Code backups {'enabled' if enabled else 'disabled'}, sir."
        
        # Handle debug_mode setting (on/off)
        elif setting == "debug_mode":
            value_str = str(value).lower()
            enabled = value_str in ['on', 'true', 'yes', '1', 'enabled']
            
            setting_key = "ENABLE_DEBUG_LOGGING"
            os.environ[setting_key] = str(enabled).lower()
            self._update_env_file(setting_key, str(enabled).lower())
            Config.reload()
            self.db.set_config(setting_key, str(enabled).lower())

            logger.info(f"Updated debug mode to {enabled}")
            return f"Debug logging {'enabled' if enabled else 'disabled'}, sir."

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
        return [
            # Personality
            "humor", "honesty", "personality", "nationality", "voice",
            # Delivery channels
            "reminder_delivery", "callback_report", "log_channel", "confirmation_channel",
            # Programming
            "programming_model", "auto_commit", "auto_push", "detailed_updates",
            # Timing
            "reminder_check_interval", "conversation_history_limit", "max_task_runtime", "approval_timeout",
            # Features
            "google_search", "call_summaries", "code_backups", "debug_mode"
        ]

    async def _list_settings(self) -> str:
        """List all current settings grouped by category."""
        settings = [
            "**Personality Settings:**",
            f"  - humor: {Config.HUMOR_PERCENTAGE}%",
            f"  - honesty: {Config.HONESTY_PERCENTAGE}%",
            f"  - personality: {Config.PERSONALITY}",
            f"  - nationality: {Config.NATIONALITY}",
            f"  - voice: {Config.GEMINI_VOICE}",
            "",
            "**Delivery Channels (via KIPP):**",
            f"  - reminder_delivery: {Config.REMINDER_DELIVERY}",
            f"  - callback_report: {Config.CALLBACK_REPORT}",
            f"  - log_channel: {Config.LOG_CHANNEL}",
            f"  - confirmation_channel: {Config.CONFIRMATION_CHANNEL}",
            "",
            "**Programming Settings:**",
            f"  - programming_model: {Config.PROGRAMMING_MODEL}",
            f"  - auto_commit: {'on' if Config.AUTO_GIT_COMMIT else 'off'}",
            f"  - auto_push: {'on' if Config.AUTO_GIT_PUSH else 'off'}",
            f"  - detailed_updates: {'on' if Config.ENABLE_DETAILED_UPDATES else 'off'}",
            f"  - code_backups: {'on' if Config.ENABLE_CODE_BACKUPS else 'off'}",
            "",
            "**Timing Settings:**",
            f"  - reminder_check_interval: {Config.REMINDER_CHECK_INTERVAL}s",
            f"  - conversation_history_limit: {Config.CONVERSATION_HISTORY_LIMIT}",
            f"  - max_task_runtime: {Config.MAX_TASK_RUNTIME_MINUTES} min",
            f"  - approval_timeout: {Config.APPROVAL_TIMEOUT_MINUTES} min",
            "",
            "**Feature Toggles:**",
            f"  - google_search: {'on' if Config.ENABLE_GOOGLE_SEARCH else 'off'}",
            f"  - call_summaries: {'on' if Config.ENABLE_CALL_SUMMARIES else 'off'}",
            f"  - debug_mode: {'on' if Config.ENABLE_DEBUG_LOGGING else 'off'}",
        ]
        return "Here are all current settings, sir:\n\n" + "\n".join(settings)

    async def _get_config(self, setting: str) -> str:
        """Get current configuration value."""
        if setting == "humor":
            return format_text('config_current_value', setting=setting, value=Config.HUMOR_PERCENTAGE)
        elif setting == "honesty":
            return format_text('config_current_value', setting=setting, value=Config.HONESTY_PERCENTAGE)
        elif setting == "personality":
            return f"Current personality is '{Config.PERSONALITY}', sir."
        elif setting == "nationality":
            return f"Current nationality is {Config.NATIONALITY}, sir."
        elif setting == "voice":
            return f"Current voice is '{Config.GEMINI_VOICE}', sir."
        # Delivery channels
        elif setting == "reminder_delivery":
            return f"Reminder delivery is '{Config.REMINDER_DELIVERY}', sir."
        elif setting == "callback_report":
            return f"Callback report method is '{Config.CALLBACK_REPORT}', sir."
        elif setting == "log_channel":
            return f"Log channel is '{Config.LOG_CHANNEL}' (via KIPP), sir."
        elif setting == "confirmation_channel":
            return f"Confirmation channel is '{Config.CONFIRMATION_CHANNEL}' (via KIPP), sir."
        # Programming
        elif setting == "programming_model":
            model_name = "Opus 4" if Config.PROGRAMMING_MODEL == "opus" else "Sonnet 4"
            return f"Programming model is {model_name}, sir."
        elif setting == "auto_commit":
            return f"Auto git commit is {'enabled' if Config.AUTO_GIT_COMMIT else 'disabled'}, sir."
        elif setting == "auto_push":
            return f"Auto git push is {'enabled' if Config.AUTO_GIT_PUSH else 'disabled'}, sir."
        elif setting == "detailed_updates":
            return f"Detailed updates are {'enabled' if Config.ENABLE_DETAILED_UPDATES else 'disabled'}, sir."
        # Timing
        elif setting == "reminder_check_interval":
            return f"Reminder check interval is {Config.REMINDER_CHECK_INTERVAL} seconds, sir."
        elif setting == "conversation_history_limit":
            return f"Conversation history limit is {Config.CONVERSATION_HISTORY_LIMIT} messages, sir."
        elif setting == "max_task_runtime":
            return f"Max task runtime is {Config.MAX_TASK_RUNTIME_MINUTES} minutes, sir."
        elif setting == "approval_timeout":
            return f"Approval timeout is {Config.APPROVAL_TIMEOUT_MINUTES} minutes, sir."
        # Features
        elif setting == "google_search":
            return f"Google search is {'enabled' if Config.ENABLE_GOOGLE_SEARCH else 'disabled'}, sir."
        elif setting == "call_summaries":
            return f"Call summaries are {'enabled' if Config.ENABLE_CALL_SUMMARIES else 'disabled'}, sir."
        elif setting == "code_backups":
            return f"Code backups are {'enabled' if Config.ENABLE_CODE_BACKUPS else 'disabled'}, sir."
        elif setting == "debug_mode":
            return f"Debug mode is {'enabled' if Config.ENABLE_DEBUG_LOGGING else 'disabled'}, sir."
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
    
    async def submit_background_confirmation(self, args: Dict[str, Any]) -> str:
        """Submit confirmation code for a background task (called from voice).
        
        This is automatically called when user provides a confirmation code
        during a background task confirmation request.
        
        Args:
            args: {
                "task_id": str - Background task ID
                "confirmation_code": str - The code provided by user
            }
        """
        task_id = args.get('task_id')
        code = args.get('confirmation_code')
        
        if not task_id or not code:
            return "Please provide both task ID and confirmation code, sir."
        
        try:
            # Store confirmation in Redis for background worker to pick up
            from redis import Redis
            redis_conn = Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB
            )
            
            redis_conn.setex(
                f"task:{task_id}:confirmation",
                300,  # 5 minute expiry
                code
            )
            
            logger.info(f"Stored voice confirmation code for task {task_id}")
            return f"Confirmation code received for task {task_id}, sir. The background task will continue."
            
        except Exception as e:
            logger.error(f"Error storing voice confirmation: {e}")
            return f"Error processing confirmation code: {str(e)}"


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


class WebBrowserAgent(SubAgent):
    """Headless browser agent using Playwright for web automation and scraping."""

    def __init__(self):
        super().__init__(
            name="web_browser",
            description="Browse websites, extract content, fill forms, take screenshots using headless browser"
        )
        self._browser = None
        self._context = None
        self._page = None

    async def execute(self, args: Dict[str, Any]) -> str:
        """Execute web browser operation.

        Args:
            args: {
                "action": "navigate|search|extract|extract_products|screenshot|click|fill|scroll|get_links|get_text|close",
                "url": str (for navigate, search, extract_products),
                "search_query": str (for search, extract_products),
                "selector": str (for click/fill/extract),
                "value": str (for fill),
                "max_price": float (for extract_products),
                "send_to_discord": bool (for extract_products),
                "wait_for": str (optional selector to wait for),
                "timeout": int (optional, milliseconds)
            }
        """
        action = args.get("action", "navigate")
        
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return "Playwright not installed. Run: pip install playwright && playwright install chromium"

        try:
            if action == "navigate":
                return await self._navigate(args)
            elif action == "search":
                # Search is now handled by extract_products
                return await self.extract_products(args)
            elif action == "extract":
                return await self._extract_content(args)
            elif action == "screenshot":
                return await self._take_screenshot(args)
            elif action == "click":
                return await self._click_element(args)
            elif action == "fill":
                return await self._fill_form(args)
            elif action == "scroll":
                return await self._scroll_page(args)
            elif action == "get_links":
                return await self._get_links(args)
            elif action == "get_text":
                return await self._get_page_text(args)
            elif action == "close":
                return await self._close_browser()
            elif action == "extract_products":
                return await self.extract_products(args)
            elif action == "send_links":
                # Convenience action: get links and send to Discord
                args["send_to_discord"] = True
                return await self._get_links(args)
            else:
                return f"Unknown browser action: {action}"
        except Exception as e:
            logger.error(f"Browser error: {e}")
            return f"Browser error: {str(e)}"

    async def _ensure_browser(self):
        """Ensure browser is initialized."""
        if self._browser is None:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            self._page = await self._context.new_page()
            logger.info("Headless browser initialized")

    async def _navigate(self, args: Dict[str, Any]) -> str:
        """Navigate to a URL."""
        url = args.get("url")
        if not url:
            return "Please provide a URL to navigate to."
        
        await self._ensure_browser()
        
        wait_for = args.get("wait_for")
        timeout = args.get("timeout", 30000)
        
        try:
            await self._page.goto(url, timeout=timeout)
            
            if wait_for:
                await self._page.wait_for_selector(wait_for, timeout=timeout)
            
            title = await self._page.title()
            return f"Navigated to: {url}\nPage title: {title}"
        except Exception as e:
            return f"Navigation error: {str(e)}"

    async def _extract_content(self, args: Dict[str, Any]) -> str:
        """Extract content from page using selector."""
        selector = args.get("selector")
        if not selector:
            return "Please provide a CSS selector to extract content from."
        
        await self._ensure_browser()
        
        try:
            elements = await self._page.query_selector_all(selector)
            if not elements:
                return f"No elements found matching selector: {selector}"
            
            contents = []
            for el in elements[:20]:  # Limit to 20 elements
                text = await el.text_content()
                if text and text.strip():
                    contents.append(text.strip())
            
            return f"Found {len(contents)} elements:\n" + "\n".join(contents[:10])
        except Exception as e:
            return f"Extraction error: {str(e)}"

    async def _take_screenshot(self, args: Dict[str, Any]) -> str:
        """Take screenshot of page or element and optionally send to Discord."""
        await self._ensure_browser()
        
        from pathlib import Path
        from datetime import datetime
        import base64
        
        selector = args.get("selector")
        filename = args.get("filename") or f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        send_to_discord = args.get("send_to_discord", True)  # Default: send to Discord
        caption = args.get("caption", "")
        
        # Save to .tars_docs folder
        screenshot_path = Path(Config.TARS_ROOT if hasattr(Config, 'TARS_ROOT') else '.') / ".tars_docs" / filename
        screenshot_path.parent.mkdir(exist_ok=True)
        
        try:
            if selector:
                element = await self._page.query_selector(selector)
                if element:
                    await element.screenshot(path=str(screenshot_path))
                else:
                    return f"Element not found: {selector}"
            else:
                await self._page.screenshot(path=str(screenshot_path), full_page=args.get("full_page", False))
            
            result = f"Screenshot saved: {screenshot_path}"
            
            # Send to Discord via KIPP
            if send_to_discord:
                current_url = self._page.url if self._page else "Unknown"
                title = await self._page.title() if self._page else "Unknown"
                
                # Read and encode image as base64
                with open(screenshot_path, "rb") as img_file:
                    image_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                
                await self._send_screenshot_to_discord(
                    image_base64=image_base64,
                    filename=filename,
                    caption=caption or f"Screenshot of: {title}",
                    url=current_url
                )
                result += "\n📸 Screenshot sent to Discord!"
            
            return result
        except Exception as e:
            return f"Screenshot error: {str(e)}"

    async def _send_screenshot_to_discord(
        self,
        image_base64: str,
        filename: str,
        caption: str = "",
        url: str = ""
    ):
        """Send screenshot to Discord via KIPP webhook.
        
        Args:
            image_base64: Base64-encoded image data
            filename: Image filename
            caption: Caption for the image
            url: URL the screenshot is from
        """
        import aiohttp
        from datetime import datetime
        
        webhook_url = Config.N8N_WEBHOOK_URL
        if not webhook_url:
            logger.warning("N8N webhook not configured - cannot send screenshot")
            return
        
        # Format message with image data
        payload = {
            "target": "discord",
            "routing_instruction": "send_via_discord",
            "message_type": "screenshot",
            "source": "web_browser",
            "message": f"📸 **Browser Screenshot**\n\n{caption}\n\n🔗 URL: {url}",
            "image_base64": image_base64,
            "image_filename": filename,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Screenshot sent to Discord: {filename}")
                    else:
                        logger.warning(f"Failed to send screenshot to Discord: {response.status}")
        except Exception as e:
            logger.error(f"Error sending screenshot to Discord: {e}")

    async def _click_element(self, args: Dict[str, Any]) -> str:
        """Click an element on the page."""
        selector = args.get("selector")
        if not selector:
            return "Please provide a selector to click."
        
        await self._ensure_browser()
        
        try:
            # Try normal click first, then force click if timeout
            try:
                await self._page.click(selector, timeout=5000)
            except Exception:
                logger.warning(f"Normal click failed for {selector}, trying force click")
                await self._page.click(selector, timeout=args.get("timeout", 10000), force=True)
                
            return f"Clicked element: {selector}"
        except Exception as e:
            return f"Click error: {str(e)}"

    async def _fill_form(self, args: Dict[str, Any]) -> str:
        """Fill a form field."""
        selector = args.get("selector")
        value = args.get("value", "")
        
        if not selector:
            return "Please provide a selector for the form field."
        
        await self._ensure_browser()
        
        try:
            await self._page.fill(selector, value, timeout=args.get("timeout", 10000))
            return f"Filled '{selector}' with value"
        except Exception as e:
            return f"Fill error: {str(e)}"

    async def _scroll_page(self, args: Dict[str, Any]) -> str:
        """Scroll the page."""
        await self._ensure_browser()
        
        direction = args.get("direction", "down")
        amount = args.get("amount", 500)
        
        try:
            if direction == "down":
                await self._page.evaluate(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                await self._page.evaluate(f"window.scrollBy(0, -{amount})")
            elif direction == "bottom":
                await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif direction == "top":
                await self._page.evaluate("window.scrollTo(0, 0)")
            
            return f"Scrolled {direction}"
        except Exception as e:
            return f"Scroll error: {str(e)}"

    async def _get_links(self, args: Dict[str, Any]) -> str:
        """Get all links from the page and optionally send to Discord."""
        await self._ensure_browser()
        
        send_to_discord = args.get("send_to_discord", False)
        filter_text = args.get("filter", "")  # Optional filter for link text
        max_links = args.get("max_links", 20)
        
        try:
            links = await self._page.evaluate("""
                () => Array.from(document.querySelectorAll('a[href]'))
                    .map(a => ({text: a.textContent?.trim(), href: a.href}))
                    .filter(l => l.href && !l.href.startsWith('javascript:'))
                    .slice(0, 50)
            """)
            
            if not links:
                return "No links found on page."
            
            # Apply filter if provided
            if filter_text:
                filter_lower = filter_text.lower()
                links = [l for l in links if filter_lower in l.get('text', '').lower()]
            
            result = f"Found {len(links)} links:\n"
            formatted_links = []
            for link in links[:max_links]:
                text = link.get('text', '')[:50] or '[no text]'
                href = link.get('href', '')
                result += f"  - {text}: {href}\n"
                formatted_links.append({"text": text, "href": href})
            
            # Send to Discord if requested
            if send_to_discord and formatted_links:
                current_url = self._page.url if self._page else "Unknown"
                title = await self._page.title() if self._page else "Unknown"
                await self._send_links_to_discord(
                    links=formatted_links,
                    page_title=title,
                    page_url=current_url
                )
                result += "\n🔗 Links sent to Discord!"
            
            return result
        except Exception as e:
            return f"Error getting links: {str(e)}"

    async def _send_links_to_discord(
        self,
        links: list,
        page_title: str = "",
        page_url: str = "",
        caption: str = ""
    ):
        """Send extracted links to Discord via KIPP webhook.
        
        Args:
            links: List of {text, href} dicts
            page_title: Title of the source page
            page_url: URL of the source page
            caption: Optional caption
        """
        import aiohttp
        from datetime import datetime
        
        webhook_url = Config.N8N_WEBHOOK_URL
        if not webhook_url:
            logger.warning("N8N webhook not configured - cannot send links")
            return
        
        # Format links as markdown
        links_text = "\n".join([
            f"• [{link['text'][:60]}]({link['href']})" 
            for link in links[:15]
        ])
        
        message = f"🔗 **Links Found**\n\n"
        if caption:
            message += f"{caption}\n\n"
        message += f"**Source:** [{page_title}]({page_url})\n\n"
        message += f"**Links ({len(links)}):**\n{links_text}"
        
        payload = {
            "target": "discord",
            "routing_instruction": "send_via_discord",
            "message_type": "links",
            "source": "web_browser",
            "message": message,
            "links_count": len(links),
            "page_url": page_url,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Sent {len(links)} links to Discord")
                    else:
                        logger.warning(f"Failed to send links to Discord: {response.status}")
        except Exception as e:
            logger.error(f"Error sending links to Discord: {e}")

    async def _get_page_text(self, args: Dict[str, Any]) -> str:
        """Get full text content of the page."""
        await self._ensure_browser()
        
        selector = args.get("selector", "body")
        max_length = args.get("max_length", 10000)
        
        try:
            element = await self._page.query_selector(selector)
            if not element:
                return f"Element not found: {selector}"
            
            text = await element.text_content()
            if text:
                # Clean up whitespace
                import re
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) > max_length:
                    text = text[:max_length] + "... [truncated]"
                return text
            return "No text content found."
        except Exception as e:
            return f"Error getting text: {str(e)}"

    async def _close_browser(self) -> str:
        """Close the browser."""
        if self._browser:
            await self._browser.close()
            await self._playwright.stop()
            self._browser = None
            self._context = None
            self._page = None
            return "Browser closed."
        return "No browser was open."

    async def send_completion_screenshot(self, success: bool = True, task_description: str = ""):
        """Take and send a completion/failure screenshot to Discord.
        
        Call this at the end of a browser task to show the final state.
        
        Args:
            success: Whether the task completed successfully
            task_description: Description of what was being done
        """
        if not self._page:
            return
        
        status_emoji = "✅" if success else "❌"
        status_text = "COMPLETED" if success else "FAILED"
        caption = f"{status_emoji} **Browser Task {status_text}**\n\n{task_description}"
        
        await self._take_screenshot({
            "send_to_discord": True,
            "caption": caption,
            "filename": f"task_{'complete' if success else 'failed'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        })

    async def send_products_to_discord(
        self,
        products: list,
        search_query: str = "",
        source_url: str = ""
    ):
        """Send product search results to Discord via KIPP.
        
        Args:
            products: List of {name, price, url, ...} dicts
            search_query: What was searched for
            source_url: URL of the search results page
        """
        import aiohttp
        from datetime import datetime
        
        webhook_url = Config.N8N_WEBHOOK_URL
        if not webhook_url:
            logger.warning("N8N webhook not configured - cannot send products")
            return
        
        # Format products as markdown
        products_text = ""
        for i, product in enumerate(products[:10], 1):
            name = product.get('name', 'Unknown')[:60]
            price = product.get('price', 'N/A')
            url = product.get('url', '')
            
            if url:
                products_text += f"{i}. [{name}]({url}) - **{price}**\n"
            else:
                products_text += f"{i}. {name} - **{price}**\n"
        
        message = f"🛒 **Product Search Results**\n\n"
        message += f"**Search:** {search_query}\n\n"
        message += f"**Found {len(products)} products:**\n{products_text}"
        if source_url:
            message += f"\n\n🔗 [View on site]({source_url})"
        
        payload = {
            "target": "discord",
            "routing_instruction": "send_via_discord",
            "message_type": "products",
            "source": "web_browser",
            "message": message,
            "products_count": len(products),
            "search_query": search_query,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Sent {len(products)} products to Discord")
                    else:
                        logger.warning(f"Failed to send products to Discord: {response.status}")
        except Exception as e:
            logger.error(f"Error sending products to Discord: {e}")

    async def extract_products(self, args: Dict[str, Any]) -> str:
        """Extract product listings from a shopping page (Amazon, eBay, etc.).
        
        This method handles the full flow:
        1. Navigate to the URL (if provided)
        2. Search for the product (if search_query provided)
        3. Extract product listings
        4. Send to Discord via KIPP (if send_to_discord)
        
        Args:
            args: {
                "url": URL to navigate to (e.g., "https://www.amazon.com"),
                "search_query": What to search for (e.g., "Raspberry Pi 5"),
                "max_price": Optional maximum price filter,
                "send_to_discord": Whether to send results to Discord (default True)
            }
        """
        await self._ensure_browser()
        
        url = args.get("url", "")
        search_query = args.get("search_query", "")
        
        # Build direct search URL when possible (more reliable than filling search box)
        if search_query:
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(search_query)
            
            if url and "amazon" in url.lower():
                # Amazon direct search URL
                url = f"https://www.amazon.com/s?k={encoded_query}"
                logger.info(f"Using Amazon direct search URL: {url}")
            elif url and "ebay" in url.lower():
                # eBay direct search URL
                url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}"
                logger.info(f"Using eBay direct search URL: {url}")
            elif url and "google" in url.lower():
                # Google Shopping search
                url = f"https://www.google.com/search?q={encoded_query}&tbm=shop"
                logger.info(f"Using Google Shopping search URL: {url}")
        
        # Navigate to URL (either direct search URL or provided URL)
        if url:
            try:
                await self._page.goto(url, timeout=30000)
                await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
                # Give page a moment to render dynamic content
                await self._page.wait_for_timeout(2000)
                logger.info(f"Navigated to {url}")
            except Exception as e:
                logger.warning(f"Navigation timeout/error: {e}, continuing anyway")
        
        # Common selectors for popular sites
        site_selectors = {
            "amazon": {
                "container": "[data-component-type='s-search-result']",
                "name": "h2 span, .a-text-normal",
                "price": ".a-price .a-offscreen, .a-price-whole",
                "link": "h2 a"
            },
            "ebay": {
                "container": ".s-item",
                "name": ".s-item__title",
                "price": ".s-item__price",
                "link": ".s-item__link"
            },
            "google_shopping": {
                "container": "[data-docid]",
                "name": ".EI11Pd, .sh-np__product-title, h3",
                "price": ".a8Pemb, .OFFNJ",
                "link": "a"
            }
        }
        
        # Detect site from current URL
        current_url = self._page.url.lower()
        selectors = {}
        if "amazon" in current_url:
            selectors = site_selectors["amazon"]
        elif "ebay" in current_url:
            selectors = site_selectors["ebay"]
        elif "google.com" in current_url and "tbm=shop" in current_url:
            selectors = site_selectors["google_shopping"]
        else:
            selectors = {
                "container": "[class*='product'], [class*='item'], article",
                "name": "[class*='title'], [class*='name'], h2, h3",
                "price": "[class*='price']",
                "link": "a[href]"
            }
        
        max_price = args.get("max_price")
        send_to_discord = args.get("send_to_discord", True)
        
        container_selector = selectors.get("container", "")
        name_selector = selectors.get("name", "")
        price_selector = selectors.get("price", "")
        link_selector = selectors.get("link", "")
        
        try:
            # Extract products using container-based approach
            if container_selector:
                products = await self._page.evaluate(f"""
                    () => {{
                        const containers = document.querySelectorAll("{container_selector}");
                        const products = [];
                        
                        containers.forEach((container, idx) => {{
                            if (idx >= 15) return; // Limit to 15 products
                            
                            const nameEl = container.querySelector("{name_selector}");
                            const priceEl = container.querySelector("{price_selector}");
                            const linkEl = container.querySelector("{link_selector}");
                            
                            const name = nameEl?.textContent?.trim() || '';
                            const price = priceEl?.textContent?.trim() || 'N/A';
                            const url = linkEl?.href || '';
                            
                            if (name.length > 10 && !name.includes('results for')) {{
                                products.push({{ name, price, url }});
                            }}
                        }});
                        
                        return products;
                    }}
                """)
            else:
                # Fallback: extract from parallel arrays
                products = await self._page.evaluate(f"""
                    () => {{
                        const names = Array.from(document.querySelectorAll("{name_selector}")).map(el => el.textContent?.trim());
                        const prices = Array.from(document.querySelectorAll("{price_selector}")).map(el => el.textContent?.trim());
                        const links = Array.from(document.querySelectorAll("{link_selector}")).map(el => el.href);
                        
                        const products = [];
                        for (let i = 0; i < Math.min(names.length, 15); i++) {{
                            if (names[i] && names[i].length > 10) {{
                                products.push({{
                                    name: names[i],
                                    price: prices[i] || 'N/A',
                                    url: links[i] || ''
                                }});
                            }}
                        }}
                        return products;
                    }}
                """)
            
            if not products:
                # Debugging: Check if we hit a captcha or anti-bot page
                title = await self._page.title()
                content = await self._page.content()
                
                if "captcha" in title.lower() or "robot check" in title.lower():
                    logger.warning(f"Amazon Captcha detected! Title: {title}")
                    return f"Amazon blocked the search with a Captcha check. Title: {title}"
                
                # If title is empty or weird, log it
                if not title:
                    logger.warning("Empty page title - possible block or load failure")
                    return "Page loaded but has no title. Possibly blocked."
                    
                return f"No products found on this page. Title: {title}"
            
            # Filter by max price if provided
            if max_price:
                import re
                filtered = []
                for p in products:
                    price_str = p.get('price', '')
                    # Extract numeric price
                    match = re.search(r'[\d,]+\.?\d*', price_str.replace(',', ''))
                    if match:
                        try:
                            price_val = float(match.group())
                            if price_val <= max_price:
                                filtered.append(p)
                        except:
                            pass
                products = filtered
            
            # Format result
            result = f"Found {len(products)} products:\n\n"
            for i, p in enumerate(products[:10], 1):
                result += f"{i}. {p['name'][:50]} - {p['price']}\n"
            
            # Send to Discord
            if send_to_discord and products:
                search_query = args.get("search_query", "")
                await self.send_products_to_discord(
                    products=products,
                    search_query=search_query,
                    source_url=self._page.url
                )
                result += "\n🛒 Products sent to Discord!"
            
            return result
            
        except Exception as e:
            logger.error(f"Product extraction error: {e}")
            return f"Error extracting products: {str(e)}"



class DeepResearchAgent(SubAgent):
    """
    Deep Research Agent - Uses Google's Deep Research API for comprehensive research.
    
    This leverages Google's official Deep Research Agent via the Interactions API,
    which provides:
    - 1M token context window
    - 40% less hallucination than custom implementations
    - Native Google Search integration
    - Multi-step research with automatic planning
    
    Research runs in background workers via Redis for true async execution.
    """

    def __init__(self, db: Database, session_manager=None):
        super().__init__(
            name="deep_research",
            description="Conduct deep multi-step research on any topic using Google's Deep Research Agent. Returns comprehensive, well-sourced reports."
        )
        self.db = db
        self.session_manager = session_manager
        
        # Initialize Gemini client for Deep Research
        self.genai_client = None
        if Config.GEMINI_API_KEY:
            try:
                from google import genai
                self.genai_client = genai.Client(api_key=Config.GEMINI_API_KEY)
                logger.info("DeepResearchAgent: Google Deep Research API initialized")
            except Exception as e:
                logger.error(f"DeepResearchAgent: Failed to initialize Google genai: {e}")

    async def execute(self, args: Dict[str, Any]) -> str:
        """Execute deep research operation.

        Args:
            args: {
                "action": "research|status|cancel",
                "goal": str - Research question/topic,
                "task_id": str - For status/cancel actions,
                "_run_in_foreground": bool - Force synchronous execution (default: False)
            }
        """
        action = args.get("action", "research")
        
        if action == "research":
            # Check routing flags
            run_in_foreground = args.get("_run_in_foreground", False)
            route_to_background = args.get("_route_to_background", True)  # Default to background
            
            if run_in_foreground:
                # Run synchronously (used by background workers internally)
                return await self._run_google_deep_research(args)
            elif route_to_background:
                # Queue to background workers (default behavior)
                return await self._queue_deep_research(args)
            else:
                return await self._run_google_deep_research(args)
        elif action == "status":
            return await self._get_research_status(args)
        elif action == "cancel":
            return await self._cancel_research(args)
        else:
            return f"Unknown action: {action}"

    async def _queue_deep_research(self, args: Dict[str, Any]) -> str:
        """Queue deep research to background workers."""
        goal = args.get("goal")
        if not goal:
            return "Please provide a research goal, sir."
        
        session_id = args.get("_session_id", "unknown")
        
        # Check if task manager is available
        if not self.session_manager or not hasattr(self.session_manager, 'task_manager'):
            logger.warning("Task manager not available, running research in foreground")
            return await self._run_google_deep_research(args)
        
        task_manager = self.session_manager.task_manager
        if not task_manager:
            logger.warning("Task manager is None, running research in foreground")
            return await self._run_google_deep_research(args)
        
        try:
            # Queue research to background workers
            task_id = task_manager.start_research_task(
                goal=goal,
                session_id=session_id,
                max_iterations=5,  # Not used by Google Deep Research, but kept for compatibility
                output_format="report"
            )
            
            logger.info(f"Google Deep Research queued: task_id={task_id}, goal={goal[:50]}...")
            
            return (
                f"Deep research started in the background, sir. Task ID: {task_id}. "
                f"Google's Deep Research agent is now working on this. "
                f"I'll send the results to your email when complete."
            )
            
        except Exception as e:
            logger.error(f"Failed to queue research task: {e}")
            logger.warning("Falling back to foreground research")
            return await self._run_google_deep_research(args)

    async def _run_google_deep_research(self, args: Dict[str, Any]) -> str:
        """Run Google Deep Research synchronously.
        
        Uses Google's Interactions API with the deep-research-pro-preview agent.
        """
        goal = args.get("goal")
        if not goal:
            return "Please provide a research goal, sir."
        
        if not self.genai_client:
            return "Google Deep Research API not configured. Please set GEMINI_API_KEY."
        
        logger.info(f"Starting Google Deep Research: {goal[:100]}...")
        
        try:
            # Start the research using Google's Deep Research agent
            interaction = self.genai_client.interactions.create(
                input=goal,
                agent='deep-research-pro-preview-12-2025',
                background=True  # Required for long-running research
            )
            
            interaction_id = interaction.id
            logger.info(f"Google Deep Research started: interaction_id={interaction_id}")
            
            # Poll for results (max 15 minutes)
            import time
            max_wait = 15 * 60  # 15 minutes
            poll_interval = 10  # seconds
            elapsed = 0
            
            while elapsed < max_wait:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                
                # Check status
                result = self.genai_client.interactions.get(interaction_id)
                
                if result.status == "completed":
                    # Extract the research report
                    report = result.outputs[-1].text if result.outputs else "No output generated"
                    
                    logger.info(f"Google Deep Research completed: {len(report)} chars")
                    
                    # Send to email via KIPP
                    await self._send_research_results(goal, report)
                    
                    # Return truncated result for voice
                    if len(report) > 2000:
                        return f"Research complete, sir! Here's a summary:\n\n{report[:2000]}\n\n[Full report sent to your email]"
                    return f"Research complete, sir!\n\n{report}"
                    
                elif result.status == "failed":
                    error_msg = result.error if hasattr(result, 'error') else "Unknown error"
                    logger.error(f"Google Deep Research failed: {error_msg}")
                    return f"Research failed, sir: {error_msg}"
                
                # Still in progress
                logger.debug(f"Research in progress... ({elapsed}s elapsed)")
            
            return "Research timed out after 15 minutes, sir. Please try again with a more specific query."
            
        except Exception as e:
            logger.error(f"Google Deep Research error: {e}")
            return f"Research error: {str(e)}"

    async def _send_research_results(self, goal: str, report: str):
        """Send research results via KIPP to email."""
        import aiohttp
        
        webhook_url = Config.N8N_WEBHOOK_URL
        if not webhook_url:
            logger.warning("N8N webhook not configured - cannot send research to email")
            return
        
        email_subject = f"TARS Research: {goal[:50]}"
        email_body = f"""
<h2>Deep Research Report</h2>
<p><strong>Topic:</strong> {goal}</p>
<p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<p><em>Powered by Google Deep Research</em></p>
<hr>

<div style="white-space: pre-wrap; font-family: sans-serif;">
{report}
</div>

<hr>
<p><em>Generated by TARS using Google Deep Research Agent</em></p>
"""
        
        payload = {
            "target": "gmail",
            "source": "deep_research",
            "message_type": "research_report",
            "routing_instruction": "send_via_gmail",
            "to": "matedort1@gmail.com",
            "subject": email_subject,
            "body": email_body,
            "message": f"Research report for: {goal}"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Research report sent to email via KIPP")
                    else:
                        logger.warning(f"KIPP webhook returned {response.status}")
        except Exception as e:
            logger.error(f"Failed to send research to email: {e}")

    async def _get_research_status(self, args: Dict[str, Any]) -> str:
        """Get status of ongoing research."""
        task_id = args.get("task_id")
        if not task_id:
            return "Please provide a task ID to check status, sir."
        
        if not self.session_manager or not hasattr(self.session_manager, 'task_manager'):
            return "Task manager not available, sir."
        
        task_manager = self.session_manager.task_manager
        if not task_manager:
            return "Task manager not available, sir."
        
        try:
            status = task_manager.get_task_status(task_id)
            return f"Research task {task_id}: {status.get('status', 'unknown')}"
        except Exception as e:
            return f"Could not get status: {str(e)}"

    async def _cancel_research(self, args: Dict[str, Any]) -> str:
        """Cancel ongoing research."""
        task_id = args.get("task_id")
        if not task_id:
            return "Please provide a task ID to cancel, sir."
        
        if not self.session_manager or not hasattr(self.session_manager, 'task_manager'):
            return "Task manager not available, sir."
        
        task_manager = self.session_manager.task_manager
        if not task_manager:
            return "Task manager not available, sir."
        
        try:
            result = task_manager.cancel_task(task_id)
            return result
        except Exception as e:
            return f"Could not cancel research: {str(e)}"



class ComputerControlAgent(SubAgent):
    """
    Computer Control Agent - Controls mouse/keyboard to perform UI tasks.
    
    Architecture (Agent-S style):
    1. Screenshot -> Vision LLM
    2. Reasoning -> Action (Click, Type, Scroll)
    3. Execution -> PyAutoGUI
    4. Loop
    """

    def __init__(self, db: Database, session_manager=None):
        super().__init__(
            name="computer_control",
            description="Controls the computer's mouse and keyboard to perform UI tasks (e.g., 'open Spotify', 'find file'). Uses vision to navigate."
        )
        self.db = db
        self.session_manager = session_manager
        
        # Initialize Gemini client for vision
        self.genai_client = None
        if Config.GEMINI_API_KEY:
            try:
                from google import genai
                from google.genai import types
                self.genai_client = genai.Client(api_key=Config.GEMINI_API_KEY)
                self.genai_types = types
                logger.info("ComputerControlAgent: Gemini client initialized for vision")
            except Exception as e:
                logger.error(f"ComputerControlAgent: Failed to initialize Gemini: {e}")
                
        # PyAutoGUI settings
        try:
            import pyautogui
            pyautogui.FAILSAFE = True  # Move mouse to corner to abort
            pyautogui.PAUSE = 0.5  # Add delay between actions
            self.pyautogui = pyautogui
            logger.info("ComputerControlAgent: PyAutoGUI initialized")
        except ImportError:
            logger.error("ComputerControlAgent: PyAutoGUI not found")
            self.pyautogui = None

    async def execute(self, args: Dict[str, Any]) -> str:
        """Execute computer control operation.

        Args:
            args: {
                "action": "control",
                "goal": str - Task description
            }
        """
        action = args.get("action", "control")
        goal = args.get("goal")
        
        if not goal:
            return "Please provide a task goal, sir."
            
        if not self.pyautogui:
            return "Computer control tools (PyAutoGUI) not installed, sir."
            
        # Check permissions (simple check)
        # Note: True permission check requires trying to take a screenshot or move mouse
        
        # Check if TaskRouter wants this in background workers
        route_to_background = args.get('_route_to_background', False)
        
        if route_to_background and self.session_manager and getattr(self.session_manager, 'task_manager', None):
            try:
                task_manager = self.session_manager.task_manager
                session_id = args.get('_session_id', 'unknown')
                
                # Queue to Redis workers
                task_id = task_manager.start_computer_control_task(
                    goal=goal,
                    session_id=session_id,
                    timeout_minutes=15
                )
                
                logger.info(f"Computer Control queued to background workers: task_id={task_id}, goal={goal[:50]}...")
                
                return (
                    f"I'll handle that on the computer in the background, sir. Task ID: {task_id}. "
                    f"You can continue with other things while I work on '{goal}'."
                )
            except Exception as e:
                logger.error(f"Failed to queue computer control task: {e}")
                # Fall back to foreground execution
                logger.warning("Falling back to foreground execution")
        
        try:
            return await self._run_control_loop(goal)
        except Exception as e:
            logger.error(f"Computer control error: {e}")
            return f"I encountered an error trying to control the computer: {str(e)}"

    async def _run_control_loop(self, goal: str) -> str:
        """Main control loop: Screenshot -> Analyze -> Act."""
        import json
        
        MAX_STEPS = 15
        history = []
        
        logger.info(f"Starting computer control task: {goal}")
        
        for step in range(MAX_STEPS):
            # 1. Take screenshot
            screenshot_path = self._take_screenshot()
            if not screenshot_path:
                return "Failed to capture screen, sir. Please check permissions."
                
            # 2. Analyze with Gemini Vision
            try:
                action_plan = await self._analyze_screen(screenshot_path, goal, history)
            except Exception as e:
                logger.error(f"Vision analysis failed: {e}")
                return f"I'm having trouble seeing the screen, sir. Error: {e}"
                
            # 3. Execute action
            logger.info(f"Step {step+1}: {action_plan.get('reasoning')} -> {action_plan.get('action')}")
            
            action_type = action_plan.get('action')
            params = action_plan.get('params', {})
            
            history.append({
                "step": step + 1,
                "action": action_type,
                "reasoning": action_plan.get('reasoning'),
                "result": "executed"
            })
            
            if action_type == 'done':
                return f"Task completed: {action_plan.get('reasoning')}"
                
            elif action_type == 'fail':
                return f"I couldn't complete the task, sir. {action_plan.get('reasoning')}"
                
            elif action_type == 'click':
                # Convert coordinates (0-1000 scale to pixels)
                screen_w, screen_h = self.pyautogui.size()
                x = int(params.get('x', 0) * screen_w / 1000)
                y = int(params.get('y', 0) * screen_h / 1000)
                
                # Move smoothly
                self.pyautogui.moveTo(x, y, duration=0.5)
                self.pyautogui.click()
                
            elif action_type == 'double_click':
                screen_w, screen_h = self.pyautogui.size()
                x = int(params.get('x', 0) * screen_w / 1000)
                y = int(params.get('y', 0) * screen_h / 1000)
                
                self.pyautogui.moveTo(x, y, duration=0.5)
                self.pyautogui.doubleClick()
                
            elif action_type == 'type':
                text = params.get('text', '')
                self.pyautogui.write(text, interval=0.05)
                if params.get('submit', False):
                    self.pyautogui.press('enter')
                    
            elif action_type == 'press':
                keys = params.get('keys', [])
                if isinstance(keys, str):
                    keys = [keys]
                # Handle hotkeys like ['command', 'space']
                self.pyautogui.hotkey(*keys)
                
            elif action_type == 'wait':
                await asyncio.sleep(params.get('seconds', 2))
                
            # Cleanup screenshot
            if os.path.exists(screenshot_path):
                os.unlink(screenshot_path)
                
            # Wait for UI to update
            await asyncio.sleep(2)
            
        return "I reached the maximum number of steps without confirming completion, sir."

    def _take_screenshot(self) -> Optional[str]:
        """Capture full screen to a temporary file."""
        import subprocess
        import tempfile
        
        path = os.path.join(tempfile.gettempdir(), "tars_vision.png")
        
        # Native macOS screencapture is fastest and most reliable
        try:
            # -x: mute sound, -r: do not add shadow
            subprocess.run(["screencapture", "-x", "-r", path], check=True)
            return path
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    async def _analyze_screen(self, screenshot_path: str, goal: str, history: list) -> Dict[str, Any]:
        """Send screenshot to Gemini for analysis and action planning."""
        import base64
        import json
        
        with open(screenshot_path, "rb") as f:
            image_data = f.read()
            
        # Format history for context
        history_str = json.dumps(history[-5:], indent=2) if history else "None"
        
        prompt = f"""
        You are a computer control agent. Your goal is: "{goal}"
        
        Current history of actions:
        {history_str}
        
        Analyze the screenshot and determine the NEXT SINGLE ACTION to take.
        
        Coordinate system: 0,0 is top-left, 1000,1000 is bottom-right.
        
        Allowed actions:
        - click(x, y): Click a UI element
        - double_click(x, y): Open file/app
        - type(text, submit=True/False): Type text
        - press(keys=["command", "space"]): Press key combo
        - wait(seconds): Wait for loading
        - done(reason): Task completed
        - fail(reason): Cannot complete task
        
        Return JSON ONLY:
        {{
            "reasoning": "I see the Spotlight search bar...",
            "action": "type",
            "params": {{ "text": "Spotify", "submit": true }}
        }}
        """
        
        from google.genai import types
        
        response = self.genai_client.models.generate_content(
            model="gemini-2.0-flash", # Use stable flash model
            contents=[
                self.genai_types.Part(text=prompt),
                self.genai_types.Part(inline_data=self.genai_types.Blob(data=image_data, mime_type="image/png"))
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        
        return json.loads(response.text)
class ProgrammerAgent(SubAgent):
    """Handles programming tasks: file operations, terminal commands, code editing, and GitHub operations."""

    def __init__(self, db: Database, github_handler=None, session_manager=None):
        super().__init__(
            name="programmer",
            description="Manages programming projects, executes terminal commands, edits code, and handles GitHub operations"
        )
        self.db = db
        self.session_manager = session_manager  # For background task access
        
        # Initialize GitHub handler
        if github_handler:
            self.github = github_handler
        else:
            from utils.github_operations import GitHubOperations
            self.github = GitHubOperations()
        
        self.current_project_path = None  # Track current project for relative path resolution
        
        # Initialize Claude client for code generation and editing
        self.anthropic_client = None
        if Config.ANTHROPIC_API_KEY:
            try:
                self.anthropic_client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
                self.complex_model = Config.CLAUDE_COMPLEX_MODEL  # claude-opus-4 for complex programming tasks
                self.fast_model = Config.CLAUDE_FAST_MODEL  # claude-sonnet-4 for faster tasks
                logger.info(f"Claude client initialized with complex model: {self.complex_model}, fast model: {self.fast_model}")
            except Exception as e:
                logger.error(f"Failed to initialize Claude client: {e}")
                self.anthropic_client = None
        else:
            logger.warning("ANTHROPIC_API_KEY not set - Claude features disabled")
        
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
        
        # Claude Code CLI path
        self.claude_code_path = "/Users/matedort/.local/bin/claude"
        self.claude_code_available = Path(self.claude_code_path).exists()
        if self.claude_code_available:
            logger.info("Claude Code CLI available for complex programming tasks")
        
        # Track running Claude Code sessions for monitoring and cancellation
        # Key: session_id, Value: session metadata dict
        self.claude_sessions: Dict[str, Dict[str, Any]] = {}
        self.claude_projects_dir = Path.home() / ".claude" / "projects"

    async def execute_with_claude_code(
        self,
        goal: str,
        project_path: Optional[str] = None,
        timeout_minutes: int = 10,
        background: bool = False
    ) -> str:
        """Execute complex programming task using Claude Code CLI.
        
        This delegates real programming work to Claude Code, which has:
        - Extended thinking capabilities
        - Better code understanding
        - Built-in file editing and terminal access
        
        Args:
            goal: What to build/fix/code
            project_path: Directory to work in (optional)
            timeout_minutes: Max execution time
            background: If True, run in background and return immediately
            
        Returns:
            Result summary from Claude Code (or session ID if background=True)
        """
        if not self.claude_code_available:
            return "Claude Code CLI not available. Please install: npm install -g @anthropic-ai/claude-code"
        
        import uuid
        from datetime import datetime
        
        # Determine working directory
        work_dir = project_path or self.current_project_path or Config.TARS_ROOT
        
        # Generate session ID (short for display, full UUID stored internally)
        full_uuid = str(uuid.uuid4())
        session_id = full_uuid[:8]  # Short ID for display/voice
        
        # Build Claude Code command
        # Note: Claude CLI doesn't accept --session-id, it auto-generates session IDs
        cmd = [
            self.claude_code_path,
            "--print",  # Non-interactive mode
            "--output-format", "text",  # Use text format for simpler parsing
            goal  # The prompt/goal
        ]
        
        logger.info(f"Starting Claude Code session {session_id}: {goal[:100]}...")
        logger.info(f"Working directory: {work_dir}")
        
        try:
            # Create async subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Track the session
            self.claude_sessions[session_id] = {
                "pid": process.pid,
                "process": process,
                "goal": goal,
                "project_path": str(work_dir),
                "started_at": datetime.now(),
                "status": "running",
                "session_id": session_id,
                "timeout_minutes": timeout_minutes
            }
            
            logger.info(f"Claude Code session {session_id} started (PID: {process.pid})")
            
            if background:
                # Return immediately with session ID
                return f"Claude Code session started in background, sir.\n\nSession ID: {session_id}\nGoal: {goal[:100]}...\n\nYou can check progress with 'list claude sessions' or 'what is Claude working on?'"
            
            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_minutes * 60
                )
                
                # Update session status
                if process.returncode == 0:
                    self.claude_sessions[session_id]["status"] = "completed"
                    output = stdout.decode().strip()
                    # Text format is already readable
                    if len(output) > 2000:
                        output = output[:2000] + "\n...[truncated]"
                    logger.info(f"Claude Code session {session_id} completed successfully")
                    return f"Claude Code completed:\n\n{output}"
                else:
                    self.claude_sessions[session_id]["status"] = "failed"
                    error = stderr.decode().strip() or stdout.decode().strip()
                    logger.error(f"Claude Code session {session_id} failed: {error[:500]}")
                    return f"Claude Code error: {error[:500]}"
                    
            except asyncio.TimeoutError:
                # Timeout - kill the process
                process.kill()
                await process.wait()
                self.claude_sessions[session_id]["status"] = "timeout"
                logger.error(f"Claude Code session {session_id} timed out after {timeout_minutes} minutes")
                return f"Claude Code timed out after {timeout_minutes} minutes, sir."
                
        except Exception as e:
            if session_id in self.claude_sessions:
                self.claude_sessions[session_id]["status"] = "error"
            logger.error(f"Claude Code execution error: {e}")
            return f"Error running Claude Code: {str(e)}"

    async def _queue_claude_code_task(
        self,
        goal: str,
        project_path: str,
        session_id: str,
        timeout_minutes: int = 10
    ) -> str:
        """Queue Claude Code task to background workers via Redis.
        
        This enables true background execution in a separate worker process.
        
        Args:
            goal: Programming task description
            project_path: Project directory to work in
            session_id: TARS session that started this
            timeout_minutes: Timeout for the task
            
        Returns:
            Status message with task ID
        """
        # Check if task manager is available
        if not self.session_manager or not hasattr(self.session_manager, 'task_manager'):
            logger.warning("Task manager not available, running Claude Code in foreground")
            return await self.execute_with_claude_code(
                goal=goal,
                project_path=project_path,
                timeout_minutes=timeout_minutes,
                background=True  # Still use async subprocess
            )
        
        task_manager = self.session_manager.task_manager
        if not task_manager:
            logger.warning("Task manager is None, running Claude Code in foreground")
            return await self.execute_with_claude_code(
                goal=goal,
                project_path=project_path,
                timeout_minutes=timeout_minutes,
                background=True
            )
        
        try:
            # Queue to Redis workers
            task_id = task_manager.start_programming_task(
                goal=goal,
                project_path=project_path,
                session_id=session_id,
                timeout_minutes=timeout_minutes
            )
            
            logger.info(f"Claude Code queued to background workers: task_id={task_id}, goal={goal[:50]}...")
            
            return (
                f"Claude Code task queued to background workers, sir. Task ID: {task_id}. "
                f"I'll work on this in the background while you continue with other things. "
                f"You can ask 'what's the status of task {task_id}' to check progress."
            )
            
        except Exception as e:
            logger.error(f"Failed to queue Claude Code task: {e}")
            # Fall back to in-process execution
            logger.warning("Falling back to in-process Claude Code execution")
            return await self.execute_with_claude_code(
                goal=goal,
                project_path=project_path,
                timeout_minutes=timeout_minutes,
                background=True
            )

    def _parse_stream_json_output(self, output: str) -> str:
        """Parse stream-json output from Claude Code to extract readable result."""
        import json
        
        lines = output.strip().split('\n')
        result_parts = []
        
        for line in lines:
            try:
                data = json.loads(line)
                # Extract assistant messages and tool results
                if data.get("type") == "assistant" and data.get("message"):
                    msg = data["message"]
                    if isinstance(msg, dict) and msg.get("content"):
                        for block in msg.get("content", []):
                            if isinstance(block, dict) and block.get("type") == "text":
                                result_parts.append(block.get("text", ""))
                elif data.get("type") == "result":
                    if data.get("result"):
                        result_parts.append(str(data["result"]))
            except json.JSONDecodeError:
                # Plain text line
                if line.strip():
                    result_parts.append(line)
        
        return "\n".join(result_parts) if result_parts else output

    async def list_claude_sessions(self, include_completed: bool = True) -> str:
        """List all Claude Code sessions with their status.
        
        Args:
            include_completed: Whether to include completed/cancelled sessions
            
        Returns:
            Formatted list of sessions
        """
        from datetime import datetime
        
        # First, update status of all tracked sessions
        for session_id, session in list(self.claude_sessions.items()):
            process = session.get("process")
            if process and session["status"] == "running":
                # Check if still running
                if process.returncode is not None:
                    session["status"] = "completed" if process.returncode == 0 else "failed"
        
        # Also scan for recent sessions from Claude's project directory
        recent_sessions = self._scan_recent_claude_sessions()
        
        # Merge with tracked sessions
        all_sessions = {}
        for session_id, session in self.claude_sessions.items():
            all_sessions[session_id] = session
        for session_id, session in recent_sessions.items():
            if session_id not in all_sessions:
                all_sessions[session_id] = session
        
        if not all_sessions:
            return "No Claude Code sessions found, sir."
        
        # Filter if needed
        if not include_completed:
            all_sessions = {k: v for k, v in all_sessions.items() if v["status"] == "running"}
        
        if not all_sessions:
            return "No running Claude Code sessions at the moment, sir."
        
        # Format output
        result = f"**Claude Code Sessions ({len(all_sessions)}):**\n\n"
        
        for session_id, session in sorted(all_sessions.items(), 
                                           key=lambda x: x[1].get("started_at", datetime.min), 
                                           reverse=True):
            status = session.get("status", "unknown")
            status_emoji = {
                "running": "🔄",
                "completed": "✅",
                "failed": "❌",
                "cancelled": "⏹️",
                "timeout": "⏰",
                "error": "⚠️"
            }.get(status, "❓")
            
            goal = session.get("goal", "Unknown")[:80]
            started = session.get("started_at")
            if isinstance(started, datetime):
                started_str = started.strftime("%H:%M:%S")
            else:
                started_str = str(started) if started else "Unknown"
            
            project = Path(session.get("project_path", "")).name or "Unknown"
            
            result += f"{status_emoji} **{session_id}** - {status.upper()}\n"
            result += f"   Goal: {goal}...\n"
            result += f"   Project: {project} | Started: {started_str}\n\n"
        
        return result

    def _scan_recent_claude_sessions(self, max_age_hours: int = 24) -> Dict[str, Dict[str, Any]]:
        """Scan Claude's project directory for recent sessions.
        
        Returns:
            Dictionary of session_id -> session info
        """
        from datetime import datetime, timedelta
        import json
        
        sessions = {}
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        if not self.claude_projects_dir.exists():
            return sessions
        
        try:
            for project_dir in self.claude_projects_dir.iterdir():
                if not project_dir.is_dir():
                    continue
                    
                for jsonl_file in project_dir.glob("*.jsonl"):
                    # Check modification time
                    try:
                        mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
                        if mtime < cutoff:
                            continue
                        
                        session_id = jsonl_file.stem
                        if session_id.startswith("agent-"):
                            continue  # Skip subagent files
                        
                        # Get first line to extract goal
                        goal = "Unknown goal"
                        with open(jsonl_file, 'r') as f:
                            first_line = f.readline()
                            try:
                                data = json.loads(first_line)
                                if data.get("type") == "user" and data.get("message"):
                                    msg = data["message"]
                                    if isinstance(msg, dict) and msg.get("content"):
                                        goal = str(msg["content"])[:200]
                                    elif isinstance(msg, str):
                                        goal = msg[:200]
                            except:
                                pass
                        
                        # Derive project path from directory name
                        project_path = project_dir.name.replace("-", "/")
                        if project_path.startswith("/"):
                            project_path = project_path[1:]
                        
                        sessions[session_id] = {
                            "session_id": session_id,
                            "goal": goal,
                            "project_path": project_path,
                            "started_at": mtime,
                            "status": "completed",  # Assume completed if we find the file
                            "jsonl_path": str(jsonl_file)
                        }
                    except Exception as e:
                        logger.debug(f"Error reading session file {jsonl_file}: {e}")
                        continue
        except Exception as e:
            logger.warning(f"Error scanning Claude sessions: {e}")
        
        return sessions

    async def get_claude_session_status(self, session_id: str) -> str:
        """Get detailed status of a specific Claude Code session.
        
        Args:
            session_id: The session ID to check
            
        Returns:
            Detailed status information
        """
        from datetime import datetime
        import json
        
        # Check tracked sessions first
        session = self.claude_sessions.get(session_id)
        
        if not session:
            # Try to find in recent sessions
            recent = self._scan_recent_claude_sessions()
            session = recent.get(session_id)
        
        if not session:
            return f"Session {session_id} not found, sir. Try 'list claude sessions' to see available sessions."
        
        status = session.get("status", "unknown")
        goal = session.get("goal", "Unknown")
        project_path = session.get("project_path", "Unknown")
        started = session.get("started_at")
        
        if isinstance(started, datetime):
            elapsed = datetime.now() - started
            elapsed_str = f"{int(elapsed.total_seconds() / 60)} minutes {int(elapsed.total_seconds() % 60)} seconds"
        else:
            elapsed_str = "Unknown"
        
        result = f"**Claude Code Session: {session_id}**\n\n"
        result += f"**Status:** {status.upper()}\n"
        result += f"**Goal:** {goal}\n"
        result += f"**Project:** {project_path}\n"
        result += f"**Elapsed:** {elapsed_str}\n\n"
        
        # Try to get recent activity from JSONL
        jsonl_path = session.get("jsonl_path")
        if not jsonl_path:
            # Try to find it
            project_encoded = str(project_path).replace("/", "-")
            potential_path = self.claude_projects_dir / project_encoded / f"{session_id}.jsonl"
            if potential_path.exists():
                jsonl_path = str(potential_path)
        
        if jsonl_path and Path(jsonl_path).exists():
            recent_activity = self._get_recent_session_activity(jsonl_path)
            if recent_activity:
                result += f"**Recent Activity:**\n{recent_activity}\n"
        
        return result

    def _get_recent_session_activity(self, jsonl_path: str, max_lines: int = 10) -> str:
        """Get recent activity from a Claude session JSONL file."""
        import json
        from collections import deque
        
        try:
            recent_lines = deque(maxlen=max_lines)
            
            with open(jsonl_path, 'r') as f:
                for line in f:
                    recent_lines.append(line)
            
            activities = []
            for line in recent_lines:
                try:
                    data = json.loads(line)
                    msg_type = data.get("type", "")
                    
                    if msg_type == "tool_use":
                        tool_name = data.get("name", "unknown_tool")
                        activities.append(f"🔧 Used tool: {tool_name}")
                    elif msg_type == "assistant":
                        msg = data.get("message", {})
                        if isinstance(msg, dict):
                            for block in msg.get("content", []):
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text = block.get("text", "")[:100]
                                    if text:
                                        activities.append(f"💬 {text}...")
                    elif msg_type == "result":
                        activities.append(f"✅ Task completed")
                        
                except json.JSONDecodeError:
                    continue
            
            return "\n".join(activities[-5:]) if activities else "No recent activity found."
            
        except Exception as e:
            logger.debug(f"Error reading session activity: {e}")
            return "Could not read session activity."

    async def cancel_claude_session(self, session_id: str) -> str:
        """Cancel a running Claude Code session.
        
        Args:
            session_id: The session ID to cancel
            
        Returns:
            Confirmation message
        """
        session = self.claude_sessions.get(session_id)
        
        if not session:
            return f"Session {session_id} not found in active sessions, sir. It may have already completed."
        
        if session["status"] != "running":
            return f"Session {session_id} is not running (status: {session['status']}), sir."
        
        process = session.get("process")
        if not process:
            return f"No process found for session {session_id}, sir."
        
        try:
            # Terminate the process
            process.terminate()
            
            # Give it a moment to clean up
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Force kill if it doesn't terminate
                process.kill()
                await process.wait()
            
            session["status"] = "cancelled"
            logger.info(f"Cancelled Claude Code session {session_id}")
            
            return f"Claude Code session {session_id} has been cancelled, sir.\n\nGoal was: {session['goal'][:100]}..."
            
        except Exception as e:
            logger.error(f"Error cancelling session {session_id}: {e}")
            return f"Error cancelling session: {str(e)}"

    def is_complex_task(self, goal: str) -> bool:
        """Determine if a task should use Claude Code (complex) vs light commands.
        
        Args:
            goal: The task description
            
        Returns:
            True if task should use Claude Code
        """
        # Keywords that indicate complex tasks needing Claude Code
        complex_keywords = [
            "build", "create", "implement", "develop", "code",
            "fix", "debug", "refactor", "optimize", "rewrite",
            "add feature", "new feature", "update", "modify",
            "test", "write tests", "unit test",
            "setup", "configure", "deploy"
        ]
        
        goal_lower = goal.lower()
        
        # Check for complex keywords
        for keyword in complex_keywords:
            if keyword in goal_lower:
                return True
        
        # Long goals are usually complex
        if len(goal) > 100:
            return True
        
        return False

    async def execute(self, args: Dict[str, Any]) -> str:
        """Execute programmer operation.

        Args:
            args: Operation arguments with 'action' field
        """
        action = args.get('action', '')
        
        # Check for function name routing (from Gemini function calls)
        function_name = args.get('_function_name', '')
        
        # Route based on function name first
        if function_name == 'update_self' or action == 'update_self':
            return await self._handle_update_self(args)
        elif function_name == 'use_claude_code' or action == 'use_claude_code':
            goal = args.get('goal', args.get('task', ''))
            if not goal:
                return "Please provide a goal for Claude Code, sir."
            
            # Check if TaskRouter wants this in background workers
            route_to_background = args.get('_route_to_background', False)
            background = args.get('background', False)
            project_path = args.get('project_path') or self.current_project_path or Config.TARS_ROOT
            timeout_minutes = args.get('timeout', 10)
            
            if route_to_background:
                # Queue to Redis workers for true background execution
                return await self._queue_claude_code_task(
                    goal=goal,
                    project_path=project_path,
                    session_id=args.get('_session_id', 'unknown'),
                    timeout_minutes=timeout_minutes
                )
            else:
                # Run directly (with optional async background mode)
                return await self.execute_with_claude_code(
                    goal=goal,
                    project_path=project_path,
                    timeout_minutes=timeout_minutes,
                    background=background
                )
        
        # Route based on action type first, then parameters
        # Claude Code for complex programming tasks
        elif action == 'claude_code' or args.get('use_claude_code'):
            goal = args.get('goal', args.get('task', ''))
            if not goal:
                return "Please provide a goal for Claude Code, sir."
            return await self.execute_with_claude_code(
                goal=goal,
                project_path=args.get('project_path'),
                timeout_minutes=args.get('timeout', 10),
                background=args.get('background', False)
            )
        # Claude Code session management functions
        elif function_name == 'list_claude_sessions' or action == 'list_claude_sessions':
            include_completed = args.get('include_completed', True)
            return await self.list_claude_sessions(include_completed)
        elif function_name == 'get_claude_session_status' or action == 'get_claude_session_status':
            session_id = args.get('session_id', '')
            if not session_id:
                return "Please provide a session ID, sir."
            return await self.get_claude_session_status(session_id)
        elif function_name == 'cancel_claude_session' or action == 'cancel_claude_session':
            session_id = args.get('session_id', '')
            if not session_id:
                return "Please provide a session ID to cancel, sir."
            return await self.cancel_claude_session(session_id)
        # Check file operations first (most specific)
        elif 'file_path' in args and action in ['read', 'edit', 'create', 'delete']:
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

    async def _handle_update_self(self, args: Dict[str, Any]) -> str:
        """Handle self-update requests (TARS modifying itself).
        
        This uses the SelfUpdater to safely modify TARS's own code.
        
        Args:
            args: {
                "change_description": str - What to add/change
                "target_file": str (optional) - Which file to modify
                "run_tests": bool (optional) - Whether to run tests (default: True)
                "auto_push": bool (optional) - Whether to push to GitHub
            }
        """
        from core.self_updater import get_self_updater
        
        change_description = args.get('change_description', '')
        if not change_description:
            return "Please describe what you want me to change about myself, sir."
        
        target_file = args.get('target_file')
        run_tests = args.get('run_tests', True)
        auto_push = args.get('auto_push', Config.AUTO_GIT_PUSH)
        
        logger.info(f"Self-update requested: {change_description}")
        
        try:
            updater = get_self_updater()
            result = await updater.apply_feature_request(
                feature_description=change_description,
                target_file=target_file
            )
            
            if result.success:
                response = (
                    f"✅ Successfully updated myself, sir!\n\n"
                    f"**Changes:** {change_description}\n"
                    f"**Files modified:** {', '.join(result.changes_made)}\n"
                    f"**Tests passed:** {'Yes' if result.tests_passed else 'Skipped'}\n"
                    f"**Commit:** {result.commit_hash or 'N/A'}\n\n"
                    f"A restart has been requested to load the new code."
                )
            else:
                response = (
                    f"❌ Self-update failed, sir.\n\n"
                    f"**Error:** {result.error_message}\n"
                    f"**Rollback:** {'Applied' if result.rollback_needed else 'Not needed'}\n\n"
                    f"The original code has been preserved."
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Self-update error: {e}")
            return f"Error during self-update: {str(e)}"

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
            
            # Set as current project for relative path resolution
            self.current_project_path = project_path
            
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
            # Use current project path if set and no explicit working_directory provided
            if 'working_directory' not in args and self.current_project_path:
                working_dir = str(self.current_project_path)
            else:
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
                    timeout=timeout,
                    env=os.environ.copy()  # Pass full environment to find all programs (cursor, code, etc.)
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

    def _resolve_file_path(self, file_path: str) -> str:
        """Resolve file path, handling relative paths against current project.
        
        Args:
            file_path: File path (absolute or relative)
            
        Returns:
            Resolved absolute file path
        """
        from pathlib import Path
        
        path = Path(file_path).expanduser()
        
        # If path is already absolute, return as-is
        if path.is_absolute():
            return str(path)
        
        # If relative path and we have a current project, resolve against it
        if self.current_project_path:
            resolved = self.current_project_path / file_path
            return str(resolved.resolve())
        
        # Otherwise, resolve relative to current working directory
        return str(path.resolve())

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
        
        # Resolve relative paths against current project if set
        file_path = self._resolve_file_path(file_path)
        
        if action == 'read':
            return await self._read_file(file_path)
        elif action == 'create':
            # Support both direct content and AI-generated content via description
            return await self._create_file(
                file_path, 
                content=args.get('content'),
                description=args.get('changes_description')
            )
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

    async def _create_file(self, file_path: str, content: str = None, description: str = None) -> str:
        """Create a new file, optionally using Claude to generate content.
        
        Args:
            file_path: Path to create the file
            content: Direct content to write (optional)
            description: Description of what to create (used with Claude if content not provided)
        """
        try:
            from pathlib import Path
            from datetime import datetime
            
            path = Path(file_path).expanduser()
            
            if path.exists():
                return f"File {file_path} already exists. Use edit action to modify it, sir."
            
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            model_used = None
            complexity = 0
            
            # If content not provided, use Claude to generate it
            if not content and description and self.anthropic_client:
                logger.info(f"Using Claude to generate content for new file: {file_path}")
                result = await self._generate_code_with_claude(
                    task_description=description,
                    file_path=file_path,
                    existing_content=None
                )
                content = result['code']
                model_used = result['model_used']
                complexity = result['complexity']
                logger.info(f"Content generated using {model_used}")
            elif not content:
                # No content and no description provided
                content = ""  # Create empty file
            
            # Write content
            path.write_text(content)
            
            logger.info(f"Created file: {file_path}")
            
            # Generate documentation if enabled and Claude was used
            if Config.ENABLE_PROGRAMMING_DOCS and model_used:
                doc_content = await self._generate_documentation(
                    operation_type='create',
                    file_path=file_path,
                    model_used=model_used,
                    complexity=complexity,
                    logic_explanation=description or "File created with provided content"
                )
                
                # Save documentation
                docs_dir = Path(self.current_project_path or Path.cwd()) / Config.PROGRAMMING_DOCS_DIR
                docs_dir.mkdir(exist_ok=True)
                doc_file = docs_dir / f"create_{path.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                doc_file.write_text(doc_content)
                logger.info(f"Documentation saved to: {doc_file}")
                
                # Send to Discord
                await self._send_docs_to_discord(doc_content, file_path)
            
            result_msg = f"Created file {file_path}"
            if model_used:
                result_msg += f" using {model_used}"
            return f"{result_msg}, sir."
            
        except Exception as e:
            logger.error(f"Error creating file: {e}")
            return f"Error creating file: {str(e)}, sir."

    async def _edit_file(self, file_path: str, changes_description: str) -> str:
        """Edit a file using Claude AI."""
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
            
            # Use Claude to generate changes
            logger.info(f"Using Claude to edit file: {file_path}")
            result = await self._generate_code_with_claude(
                task_description=changes_description,
                file_path=file_path,
                existing_content=original_content
            )
            
            modified_content = result['code']
            model_used = result['model_used']
            complexity = result['complexity']
            
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
            
            logger.info(f"Edited file: {file_path} using {model_used}")
            
            # Generate documentation if enabled
            if Config.ENABLE_PROGRAMMING_DOCS:
                doc_content = await self._generate_documentation(
                    operation_type='edit',
                    file_path=file_path,
                    model_used=model_used,
                    complexity=complexity,
                    changes=diff_text[:2000],  # Limit diff in docs
                    logic_explanation=changes_description
                )
                
                # Save documentation
                docs_dir = Path(self.current_project_path or Path.cwd()) / Config.PROGRAMMING_DOCS_DIR
                docs_dir.mkdir(exist_ok=True)
                doc_file = docs_dir / f"edit_{path.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                doc_file.write_text(doc_content)
                logger.info(f"Documentation saved to: {doc_file}")
                
                # Send to Discord
                await self._send_docs_to_discord(doc_content, file_path)
            
            return f"Edited file {file_path} using {model_used}. Changes:\n\n{diff_text[:1000]}"
            
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

    async def _analyze_task_complexity(self, task_description: str, file_path: str = None, existing_content: str = None) -> int:
        """Analyze task complexity on a scale of 0-10.
        
        Args:
            task_description: Description of the task
            file_path: Optional file path being worked on
            existing_content: Optional existing file content
            
        Returns:
            Complexity score (0-10)
        """
        complexity = 0
        
        # Check task description for complexity keywords
        complex_keywords = [
            'refactor', 'architecture', 'debug', 'design', 'optimize', 
            'complex', 'algorithm', 'performance', 'restructure', 'migrate'
        ]
        simple_keywords = ['add comment', 'fix typo', 'rename', 'format', 'style']
        
        task_lower = task_description.lower()
        
        # Check for complex keywords (+2 per keyword, max +6)
        for keyword in complex_keywords:
            if keyword in task_lower:
                complexity += 2
        
        # Check for simple keywords (-2 per keyword)
        for keyword in simple_keywords:
            if keyword in task_lower:
                complexity -= 2
        
        # File size complexity
        if existing_content:
            lines = len(existing_content.split('\n'))
            if lines > 500:
                complexity += 3
            elif lines > 200:
                complexity += 2
            elif lines > 100:
                complexity += 1
        
        # Multi-file operations
        if 'multiple files' in task_lower or 'all files' in task_lower:
            complexity += 3
        
        # Clamp between 0 and 10
        complexity = max(0, min(10, complexity))
        
        logger.info(f"Task complexity analysis: {complexity}/10 for '{task_description[:50]}...'")
        return complexity
    
    async def _should_use_complex_model(self, task_description: str, file_path: str = None, existing_content: str = None) -> bool:
        """Determine if we should use the complex model (Claude Sonnet 4.5) or fast model (Claude 3.5 Haiku).
        
        Args:
            task_description: Description of the task
            file_path: Optional file path being worked on
            existing_content: Optional existing file content
            
        Returns:
            True if complex model should be used, False for fast model
        """
        complexity = await self._analyze_task_complexity(task_description, file_path, existing_content)
        
        # Use complex model for complexity >= 5
        use_complex = complexity >= 5
        
        model_name = "Claude Sonnet 4.5 (complex)" if use_complex else "Claude 3.5 Haiku (fast)"
        logger.info(f"Selected {model_name} for complexity {complexity}/10")
        
        return use_complex
    
    async def _call_claude(self, prompt: str, model: str, system_prompt: str = None) -> str:
        """Call Claude API with the given prompt.
        
        Args:
            prompt: The prompt to send to Claude
            model: Model identifier (complex or fast)
            system_prompt: Optional system prompt
            
        Returns:
            Claude's response text
        """
        if not self.anthropic_client:
            raise Exception("Claude client not initialized. Please set ANTHROPIC_API_KEY in your .env file.")
        
        try:
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            kwargs = {
                "model": model,
                "max_tokens": 8192,
                "messages": messages
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            response = self.anthropic_client.messages.create(**kwargs)
            
            # Extract text from response
            result_text = ""
            for content_block in response.content:
                if hasattr(content_block, 'text'):
                    result_text += content_block.text
            
            return result_text.strip()
            
        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            raise
    
    async def _generate_code_with_claude(self, task_description: str, file_path: str, existing_content: str = None) -> dict:
        """Generate or modify code using Claude.
        
        Args:
            task_description: Description of what code to generate/modify
            file_path: Path to the file
            existing_content: Existing file content (for edits)
            
        Returns:
            dict with 'code', 'model_used', 'complexity', 'explanation'
        """
        # Determine which model to use
        use_complex = await self._should_use_complex_model(task_description, file_path, existing_content)
        model = self.complex_model if use_complex else self.fast_model
        model_name = "Claude Sonnet 4.5" if use_complex else "Claude 3.5 Haiku"
        
        # Build prompt
        if existing_content:
            # Editing existing file
            prompt = f"""Analyze this code and apply these changes: {task_description}

Current code in {Path(file_path).name}:
```
{existing_content}
```

Respond with ONLY the complete modified file content, no explanations or markdown code blocks."""
        else:
            # Creating new file
            prompt = f"""Create a new file: {task_description}

File: {Path(file_path).name}

Respond with ONLY the complete file content, no explanations or markdown code blocks."""
        
        system_prompt = "You are an expert programmer. Generate clean, well-documented, production-ready code. Return ONLY the code, no markdown formatting or explanations."
        
        # Call Claude
        logger.info(f"Calling {model_name} for code generation/modification")
        response_text = await self._call_claude(prompt, model, system_prompt)
        
        # Clean up response (remove markdown code blocks if present)
        code = response_text
        if code.startswith('```'):
            lines = code.split('\n')
            # Remove first line (```language) and last line (```)
            if len(lines) > 2 and lines[-1].strip() == '```':
                code = '\n'.join(lines[1:-1])
        
        # Get complexity score
        complexity = await self._analyze_task_complexity(task_description, file_path, existing_content)
        
        return {
            'code': code,
            'model_used': model_name,
            'complexity': complexity,
            'explanation': task_description
        }
    
    async def _generate_documentation(self, operation_type: str, file_path: str, model_used: str, 
                                      complexity: int, changes: str = None, test_results: str = None,
                                      logic_explanation: str = None) -> str:
        """Generate markdown documentation for a file operation.
        
        Args:
            operation_type: 'create' or 'edit'
            file_path: Path to the file
            model_used: Which Claude model was used
            complexity: Complexity score (0-10)
            changes: Optional changes/diff summary
            test_results: Optional test results
            logic_explanation: Optional explanation of logic used
            
        Returns:
            Markdown documentation content
        """
        from datetime import datetime
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        filename = Path(file_path).name
        
        if operation_type == 'create':
            doc = f"""# File Creation Report: {filename}

**Operation**: File Creation
**Timestamp**: {timestamp}
**File Path**: {file_path}
**Model Used**: {model_used}
**Complexity Score**: {complexity}/10

## Logic Used
{logic_explanation or 'No detailed explanation provided'}

## Test Results
{test_results or 'No tests run'}

---
*Generated by TARS Programming Agent*
"""
        else:  # edit
            doc = f"""# File Edit Report: {filename}

**Operation**: File Edit
**Timestamp**: {timestamp}
**File Path**: {file_path}
**Model Used**: {model_used}
**Complexity Score**: {complexity}/10

## Changes Made
{changes or 'No detailed change summary available'}

## Logic Used
{logic_explanation or 'No detailed explanation provided'}

## Test Results
{test_results or 'No tests run'}

---
*Generated by TARS Programming Agent*
"""
        
        return doc
    
    async def _send_docs_to_discord(self, doc_content: str, file_path: str) -> str:
        """Send documentation to Discord via N8N webhook.
        
        Args:
            doc_content: Markdown documentation content
            file_path: Path to the file (for title)
            
        Returns:
            Status message
        """
        if not Config.N8N_WEBHOOK_URL:
            logger.warning("N8N webhook not configured, skipping Discord notification")
            return "Documentation generated but Discord notification skipped (webhook not configured)"
        
        try:
            # Use KIPPAgent's send method by constructing similar message
            filename = Path(file_path).name
            message = f"send discord message: Programming documentation for {filename}\n\n{doc_content}"
            
            # Import and use KIPPAgent's send method
            import aiohttp
            import json
            
            n8n_webhook_url = Config.N8N_WEBHOOK_URL
            
            payload = {
                "message": message
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    n8n_webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Successfully sent programming documentation for {filename} to Discord")
                        return "Documentation sent to Discord"
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to send to Discord: {response.status} - {error_text}")
                        return f"Documentation generated but Discord notification failed (status {response.status})"
        
        except Exception as e:
            logger.error(f"Error sending documentation to Discord: {e}")
            return f"Documentation generated but Discord notification failed: {str(e)}"

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
            # Use current project path if set and no explicit working_directory provided
            if 'working_directory' not in args and self.current_project_path:
                working_dir = str(self.current_project_path)
            else:
                working_dir = args.get('working_directory', '.')
            return await self._git_init(working_dir)
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
        # Use current project path if set and no explicit working_directory provided
        if 'working_directory' not in args and self.current_project_path:
            working_dir = str(self.current_project_path)
        else:
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
        # Use current project path if set and no explicit working_directory provided
        if 'working_directory' not in args and self.current_project_path:
            working_dir = str(self.current_project_path)
        else:
            working_dir = args.get('working_directory', '.')
        branch = args.get('branch', 'main')
        
        result = await self.github.git_pull(working_dir, branch)
        if result.get('success'):
            return f"Pulled from {branch}: {result.get('message')}, sir."
        return f"Failed to pull: {result.get('error')}, sir."
    
    async def _git_ensure_repo(self, project_path: str) -> str:
        """Ensure git repository exists, create if needed.
        
        Args:
            project_path: Path to project directory
            
        Returns:
            Status message
        """
        try:
            from pathlib import Path
            import subprocess
            
            git_dir = Path(project_path) / ".git"
            
            if git_dir.exists():
                logger.info(f"Git repo already exists at {project_path}")
                return "Git repo exists"
            
            # Initialize new repo
            result = subprocess.run(
                ['git', 'init'],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f"Initialized git repo at {project_path}")
                
                # Configure user if not set
                subprocess.run(
                    ['git', 'config', 'user.name', 'TARS'],
                    cwd=project_path,
                    capture_output=True
                )
                subprocess.run(
                    ['git', 'config', 'user.email', 'tars@autonomous.ai'],
                    cwd=project_path,
                    capture_output=True
                )
                
                # Create initial commit
                subprocess.run(
                    ['git', 'add', '.gitignore', '.tarsrules'],
                    cwd=project_path,
                    capture_output=True
                )
                subprocess.run(
                    ['git', 'commit', '-m', '[INIT] Initial commit by TARS', '--allow-empty'],
                    cwd=project_path,
                    capture_output=True
                )
                
                return f"Initialized git repo: {result.stdout}"
            else:
                logger.error(f"Git init failed: {result.stderr}")
                return f"Failed to initialize git: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return "Git init timed out"
        except Exception as e:
            logger.error(f"Error ensuring git repo: {e}")
            return f"Error: {e}"
    
    async def _git_commit_smart(
        self,
        project_path: str,
        message: str,
        files: List[str] = None
    ) -> str:
        """Intelligent git commit with automatic staging.
        
        Args:
            project_path: Path to project directory
            message: Commit message
            files: List of specific files to commit (None = commit all changes)
            
        Returns:
            Commit status message
        """
        try:
            import subprocess
            from pathlib import Path
            
            # Ensure message is properly formatted
            if not message:
                message = "[AUTO] Automated commit by TARS"
            
            # Stage files
            if files:
                for file in files:
                    # Convert to relative path if needed
                    file_path = Path(file)
                    if file_path.is_absolute():
                        try:
                            file_path = file_path.relative_to(Path(project_path))
                        except ValueError:
                            pass  # File is outside project, use as-is
                    
                    result = subprocess.run(
                        ['git', 'add', str(file_path)],
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode != 0:
                        logger.warning(f"Could not stage {file_path}: {result.stderr}")
            else:
                # Stage all changes
                result = subprocess.run(
                    ['git', 'add', '-A'],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    logger.warning(f"Git add failed: {result.stderr}")
            
            # Check if there's anything to commit
            status = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if not status.stdout.strip():
                logger.info("No changes to commit")
                return "Nothing to commit"
            
            # Commit
            result = subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Get short hash
                hash_result = subprocess.run(
                    ['git', 'rev-parse', '--short', 'HEAD'],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else "unknown"
                
                logger.info(f"Committed {commit_hash}: {message}")
                return f"✓ Committed [{commit_hash}]: {message}"
            else:
                logger.error(f"Commit failed: {result.stderr}")
                return f"⚠️ Commit failed: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return "Git commit timed out"
        except Exception as e:
            logger.error(f"Error in git commit: {e}")
            return f"Error: {e}"
    
    async def _send_discord_update(self, data: dict):
        """Send update to Discord via KIPP (N8N webhook).
        
        Args:
            data: {
                'task_id': str,
                'type': str (task_started|progress|phase_complete|confirmation_request|task_complete|error),
                'message': str,
                'command': str (optional - for terminal commands),
                'phase': str (optional - for phase completions),
                'code_request': bool (optional - if confirmation needed)
            }
        """
        webhook_url = Config.N8N_WEBHOOK_URL
        
        if not webhook_url:
            logger.warning("N8N webhook not configured for Discord updates")
            return
        
        # Format payload for KIPP/N8N to route to Discord
        payload = {
            "target": "discord",  # Tell KIPP to route to Discord
            "source": "background_task",  # Identify as background task update
            "task_id": data.get('task_id'),
            "type": data.get('type'),
            "message": data.get('message'),
            "timestamp": datetime.now().isoformat()
        }
        
        # Add optional fields
        if 'command' in data:
            payload['command'] = data['command']
        if 'phase' in data:
            payload['phase'] = data['phase']
        if 'code_request' in data:
            payload['awaiting_confirmation'] = True
        if 'goal' in data:
            payload['goal'] = data['goal']
        if 'project' in data:
            payload['project'] = data['project']
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Sent Discord update via KIPP: {data.get('message', '')[:50]}")
                    else:
                        logger.warning(f"KIPP webhook returned {response.status}")
        except Exception as e:
            logger.error(f"Failed to send Discord update via KIPP: {e}")


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

    # Add web browser agent for headless browsing
    agents["web_browser"] = WebBrowserAgent()

    # Add deep research agent
    agents["deep_research"] = DeepResearchAgent(db=db, session_manager=session_manager)
    agents["skill_creator"] = SkillCreatorAgent()

    # Add programmer agent (with session_manager for background tasks)
    agents["programmer"] = ProgrammerAgent(db=db, github_handler=None, session_manager=session_manager)

    # Add computer control agent
    agents["computer_control"] = ComputerControlAgent(db=db, session_manager=session_manager)

    return agents


def get_function_declarations() -> list:
    """Get function declarations for all sub-agents.

    Returns:
        List of function declarations for Gemini
    """
    return [
        {
            "name": "adjust_config",
            "description": "Adjust TARS settings. PERSONALITY: humor (0-100%), honesty (0-100%), personality (chatty/normal/brief), nationality, voice (Puck/Kore/Charon). DELIVERY CHANNELS: reminder_delivery (call/discord/telegram), callback_report (call/discord/telegram), log_channel (discord/telegram), confirmation_channel (discord/telegram). PROGRAMMING: programming_model (opus/sonnet), auto_commit (on/off), auto_push (on/off), detailed_updates (on/off), code_backups (on/off). TIMING: reminder_check_interval (seconds), conversation_history_limit, max_task_runtime (minutes), approval_timeout (minutes). FEATURES: google_search (on/off), call_summaries (on/off), debug_mode (on/off). Use action='list' to see all settings.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: 'set' (change value), 'get' (check current value), or 'list' (show all settings)"
                    },
                    "setting": {
                        "type": "STRING",
                        "description": "Setting to adjust. Personality: humor, honesty, personality, nationality, voice. Channels: reminder_delivery, callback_report, log_channel, confirmation_channel. Programming: programming_model, auto_commit, auto_push, detailed_updates, code_backups. Timing: reminder_check_interval, conversation_history_limit, max_task_runtime, approval_timeout. Features: google_search, call_summaries, debug_mode"
                    },
                    "value": {
                        "type": "STRING",
                        "description": "New value. humor/honesty: 0-100. personality: chatty/normal/brief. voice: Puck/Kore/Charon. Delivery channels: call/discord/telegram. log/confirmation channels: discord/telegram. programming_model: opus/sonnet. Toggle settings: on/off. Intervals: number in seconds/minutes."
                    }
                },
                "required": ["action"]
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
            "name": "computer_control",
            "description": "Control the computer's mouse and keyboard to perform UI tasks. Use this when the user asks to manipulate desktop apps (e.g., 'open Spotify', 'find file in Notes', 'send message on Slack'). The agent sees the screen and navigates naturally.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: always 'control'"
                    },
                    "goal": {
                        "type": "STRING",
                        "description": "Description of the task to perform (e.g., 'Open Notes and find the song list', 'Play Bohemian Rhapsody on Spotify')"
                    }
                },
                "required": ["action", "goal"]
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
        },
        # Web Browser Agent functions
        {
            "name": "browse_web",
            "description": "Use headless browser to navigate websites, extract content, take screenshots, fill forms, click elements, or extract products. Screenshots and links can be sent to Discord. For shopping: use extract_products to find items with prices. Examples: 'go to Amazon and search for water bottles under $10', 'take a screenshot of this page and send it to me'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Browser action: navigate, extract, screenshot, click, fill, scroll, get_links, send_links (get + send to Discord), get_text, extract_products (for shopping sites), close"
                    },
                    "url": {
                        "type": "STRING",
                        "description": "URL to navigate to (for navigate action)"
                    },
                    "selector": {
                        "type": "STRING",
                        "description": "CSS selector for element interaction (for extract, click, fill, screenshot)"
                    },
                    "value": {
                        "type": "STRING",
                        "description": "Value to fill in form field (for fill action)"
                    },
                    "wait_for": {
                        "type": "STRING",
                        "description": "CSS selector to wait for after navigation"
                    },
                    "send_to_discord": {
                        "type": "BOOLEAN",
                        "description": "Send results (screenshot, links, products) to Discord (default: true for screenshots)"
                    },
                    "max_price": {
                        "type": "NUMBER",
                        "description": "For extract_products: filter products under this price"
                    },
                    "search_query": {
                        "type": "STRING",
                        "description": "For extract_products: what was searched for (for context in Discord message)"
                    },
                    "caption": {
                        "type": "STRING",
                        "description": "For screenshot: caption to include in Discord message"
                    }
                },
                "required": ["action"]
            }
        },
        # Deep Research Agent functions
        {
            "name": "deep_research",
            "description": "Conduct deep multi-step research on any topic (like Gemini/Perplexity Deep Research). Automatically searches the web, browses pages, identifies knowledge gaps, iterates, and synthesizes findings into a comprehensive report. Runs in background. Examples: 'research how quantum computing works', 'deep dive into the history of AI', 'analyze the market for electric vehicles'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {
                        "type": "STRING",
                        "description": "Action: research, status, cancel"
                    },
                    "goal": {
                        "type": "STRING",
                        "description": "Research question or topic to investigate"
                    },
                    "max_iterations": {
                        "type": "INTEGER",
                        "description": "Maximum research iterations (default: 5, max: 10)"
                    },
                    "max_sources": {
                        "type": "INTEGER",
                        "description": "Maximum sources to consult (default: 10, max: 20)"
                    },
                    "output_format": {
                        "type": "STRING",
                        "description": "Output format: report (detailed), summary (concise), bullet_points"
                    },
                    "follow_up_action": {
                        "type": "STRING",
                        "description": "What to do after research: none, build_project, create_visualization"
                    }
                },
                "required": ["goal"]
            }
        },
        # Self-Update (TARS modifying itself)
        {
            "name": "update_self",
            "description": "Add a feature or fix to TARS itself. Runs safely with automatic backup and restore if tests fail. TARS can edit its own code and restart to load new features. Examples: 'add a new sub-agent for X', 'fix the bug in reminder system', 'add telegram integration'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "change_description": {
                        "type": "STRING",
                        "description": "What to add or change (feature description or bug fix)"
                    },
                    "target_file": {
                        "type": "STRING",
                        "description": "Which file to modify (optional - defaults to sub_agents_tars.py)"
                    },
                    "run_tests": {
                        "type": "BOOLEAN",
                        "description": "Whether to run tests before applying (default: true)"
                    },
                    "auto_push": {
                        "type": "BOOLEAN",
                        "description": "Whether to push to GitHub after success (default: from config)"
                    }
                },
                "required": ["change_description"]
            }
        },
        # Claude Code for complex programming
        {
            "name": "use_claude_code",
            "description": "Delegate complex programming tasks to Claude Code CLI. Best for multi-file changes, debugging, refactoring, and complex implementations. Lighter tasks use built-in terminal. Examples: 'build a REST API with authentication', 'refactor the database layer', 'debug and fix all failing tests'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "goal": {
                        "type": "STRING",
                        "description": "Programming task to accomplish"
                    },
                    "project_path": {
                        "type": "STRING",
                        "description": "Project directory to work in (optional)"
                    },
                    "timeout": {
                        "type": "INTEGER",
                        "description": "Timeout in minutes (default: 10, max: 30)"
                    },
                    "background": {
                        "type": "BOOLEAN",
                        "description": "If true, run in background and return immediately with session ID (default: false)"
                    }
                },
                "required": ["goal"]
            }
        },
        # Claude Code Session Management
        {
            "name": "list_claude_sessions",
            "description": "List all Claude Code programming sessions - both running and recently completed. Shows session ID, status, goal, project, and start time. Use this when the user asks 'what is Claude working on?', 'list coding sessions', or 'show running tasks'.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "include_completed": {
                        "type": "BOOLEAN",
                        "description": "Whether to include completed/cancelled sessions (default: true)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_claude_session_status",
            "description": "Get detailed status of a specific Claude Code session including progress, files modified, and recent activity. Use when user asks for details about a particular session.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "session_id": {
                        "type": "STRING",
                        "description": "The session ID to check (8 character ID)"
                    }
                },
                "required": ["session_id"]
            }
        },
        {
            "name": "cancel_claude_session",
            "description": "Cancel a running Claude Code session. Stops the programming task immediately. Use when user says 'stop Claude', 'cancel the coding task', or 'kill that session'.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "session_id": {
                        "type": "STRING",
                        "description": "The session ID to cancel (8 character ID)"
                    }
                },
                "required": ["session_id"]
            }
        },
        # Skill Creator (Moltbot capability)
        {
            "name": "create_skill",
            "description": "Create a new permanent skill/tool for TARS. Use when you identify a gap in your capabilities and write code to fix it. This creates a new 'skill' directory with code and metadata. Example: 'create a skill to resize images', 'create a tool to check stock prices'",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "skill_name": {
                        "type": "STRING",
                        "description": "Short, unique name for the skill (e.g., 'image_resizer')"
                    },
                    "instruction": {
                        "type": "STRING",
                        "description": "Description of what the skill does and how to use it"
                    },
                    "code_content": {
                        "type": "STRING",
                        "description": "The Python code for the tool (optional - if provided)"
                    }
                },
                "required": ["skill_name", "instruction"]
            }
        }
    ]
