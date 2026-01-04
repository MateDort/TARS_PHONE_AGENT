"""Local SQLite database for TARS - Máté's Personal Assistant."""
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """Manages local SQLite database for reminders, contacts, and configuration."""

    def __init__(self, db_path: str = "tars.db"):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self.init_database()

    def init_database(self):
        """Initialize database and create tables if they don't exist."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

            # Create reminders table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    datetime TEXT NOT NULL,
                    recurrence TEXT,
                    days_of_week TEXT,
                    active INTEGER DEFAULT 1,
                    last_triggered TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create contacts table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    relation TEXT,
                    phone TEXT,
                    birthday TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create conversations table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    message TEXT NOT NULL,
                    medium TEXT NOT NULL,
                    call_sid TEXT,
                    message_sid TEXT,
                    direction TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create configuration table (for runtime-editable config)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS configuration (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create call_goals table (for goal-based outbound calls)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS call_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number TEXT NOT NULL,
                    contact_name TEXT,
                    goal_type TEXT NOT NULL,
                    goal_description TEXT NOT NULL,
                    preferred_date TEXT,
                    preferred_time TEXT,
                    alternative_options TEXT,
                    status TEXT DEFAULT 'pending',
                    result TEXT,
                    call_sid TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                )
            """)

            self.conn.commit()
            logger.info(f"TARS database initialized at {self.db_path}")

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    # ==================== REMINDERS ====================

    def add_reminder(self, title: str, datetime_str: str, recurrence: str = None, days_of_week: str = None) -> int:
        """Add a new reminder.

        Args:
            title: Reminder title/description
            datetime_str: Datetime in ISO format
            recurrence: None, "daily", "weekly", "monthly"
            days_of_week: Comma-separated days (e.g., "monday,wednesday,friday")

        Returns:
            Reminder ID
        """
        cursor = self.conn.execute(
            "INSERT INTO reminders (title, datetime, recurrence, days_of_week) VALUES (?, ?, ?, ?)",
            (title, datetime_str, recurrence, days_of_week)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_reminders(self, active_only: bool = True) -> List[Dict]:
        """Get all reminders.

        Args:
            active_only: Only return active reminders

        Returns:
            List of reminder dictionaries
        """
        query = "SELECT * FROM reminders"
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY datetime"

        cursor = self.conn.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def get_reminder(self, reminder_id: int) -> Optional[Dict]:
        """Get a specific reminder by ID.

        Args:
            reminder_id: Reminder ID

        Returns:
            Reminder dictionary or None
        """
        cursor = self.conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_reminder(self, reminder_id: int, **kwargs) -> bool:
        """Update a reminder.

        Args:
            reminder_id: Reminder ID
            **kwargs: Fields to update (title, datetime, recurrence, etc.)

        Returns:
            True if updated, False otherwise
        """
        allowed_fields = ['title', 'datetime', 'recurrence', 'days_of_week', 'active']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [reminder_id]

        self.conn.execute(f"UPDATE reminders SET {set_clause} WHERE id = ?", values)
        self.conn.commit()
        return True

    def delete_reminder(self, reminder_id: int) -> bool:
        """Delete a reminder.

        Args:
            reminder_id: Reminder ID

        Returns:
            True if deleted, False otherwise
        """
        self.conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        self.conn.commit()
        return True

    def mark_reminder_triggered(self, reminder_id: int):
        """Mark reminder as triggered.

        Args:
            reminder_id: Reminder ID
        """
        now = datetime.now().isoformat()
        self.conn.execute(
            "UPDATE reminders SET last_triggered = ? WHERE id = ?",
            (now, reminder_id)
        )
        self.conn.commit()

    def mark_reminder_complete(self, reminder_id: int):
        """Mark a non-recurring reminder as complete.

        Args:
            reminder_id: Reminder ID
        """
        self.conn.execute(
            "UPDATE reminders SET active = 0 WHERE id = ?",
            (reminder_id,)
        )
        self.conn.commit()

    def reschedule_reminder(self, reminder_id: int, new_datetime: datetime):
        """Reschedule a reminder to a new time.

        Args:
            reminder_id: Reminder ID
            new_datetime: New datetime for the reminder
        """
        self.conn.execute(
            "UPDATE reminders SET datetime = ? WHERE id = ?",
            (new_datetime.isoformat(), reminder_id)
        )
        self.conn.commit()

    def get_due_reminders(self, current_time: datetime) -> List[Dict]:
        """Get reminders that are due.

        Args:
            current_time: Current datetime

        Returns:
            List of due reminders
        """
        reminders = self.get_reminders(active_only=True)
        due = []

        for reminder in reminders:
            reminder_time = datetime.fromisoformat(reminder['datetime'])

            # Check if reminder is due
            if reminder_time <= current_time:
                # For recurring reminders, check if already triggered today
                if reminder['recurrence']:
                    last_triggered = reminder.get('last_triggered')
                    if last_triggered:
                        last_triggered_dt = datetime.fromisoformat(last_triggered)
                        if last_triggered_dt.date() == current_time.date():
                            continue  # Already triggered today

                    # Check day of week for weekly recurrence
                    if reminder['recurrence'] == 'weekly' and reminder['days_of_week']:
                        current_day = current_time.strftime('%A').lower()
                        days = [d.strip().lower() for d in reminder['days_of_week'].split(',')]
                        if current_day not in days:
                            continue

                due.append(reminder)

        return due

    # ==================== CONTACTS ====================

    def add_contact(self, name: str, relation: str = None, phone: str = None,
                   birthday: str = None, notes: str = None) -> int:
        """Add a new contact.

        Args:
            name: Contact name
            relation: Relationship (e.g., "Girlfriend", "Friend", "Doctor")
            phone: Phone number
            birthday: Birthday in ISO format (YYYY-MM-DD)
            notes: Additional notes

        Returns:
            Contact ID
        """
        cursor = self.conn.execute(
            "INSERT INTO contacts (name, relation, phone, birthday, notes) VALUES (?, ?, ?, ?, ?)",
            (name, relation, phone, birthday, notes)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_contacts(self) -> List[Dict]:
        """Get all contacts.

        Returns:
            List of contact dictionaries
        """
        cursor = self.conn.execute("SELECT * FROM contacts ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    def search_contact(self, name: str) -> Optional[Dict]:
        """Search for a contact by name.

        Args:
            name: Contact name (case-insensitive partial match)

        Returns:
            Contact dictionary or None
        """
        cursor = self.conn.execute(
            "SELECT * FROM contacts WHERE LOWER(name) LIKE LOWER(?) LIMIT 1",
            (f"%{name}%",)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_contact(self, contact_id: int, **kwargs) -> bool:
        """Update a contact.

        Args:
            contact_id: Contact ID
            **kwargs: Fields to update

        Returns:
            True if updated, False otherwise
        """
        allowed_fields = ['name', 'relation', 'phone', 'birthday', 'notes']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [contact_id]

        self.conn.execute(f"UPDATE contacts SET {set_clause} WHERE id = ?", values)
        self.conn.commit()
        return True

    def delete_contact(self, contact_id: int) -> bool:
        """Delete a contact.

        Args:
            contact_id: Contact ID

        Returns:
            True if deleted, False otherwise
        """
        self.conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        self.conn.commit()
        return True

    # ==================== CONFIGURATION ====================

    def set_config(self, key: str, value: str):
        """Set a configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        timestamp = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO configuration (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, timestamp)
        )
        self.conn.commit()

    def get_config(self, key: str = None) -> Dict:
        """Get configuration values.

        Args:
            key: Specific key to retrieve, or None for all

        Returns:
            Dictionary of configuration data
        """
        if key:
            cursor = self.conn.execute("SELECT value FROM configuration WHERE key = ?", (key,))
            row = cursor.fetchone()
            return {key: row['value']} if row else {}
        else:
            cursor = self.conn.execute("SELECT * FROM configuration")
            return {row['key']: row['value'] for row in cursor.fetchall()}

    # ==================== CONVERSATIONS ====================

    def add_conversation_message(self, sender: str, message: str, medium: str,
                                 call_sid: str = None, message_sid: str = None,
                                 direction: str = None) -> int:
        """Add a conversation message to the database.

        Args:
            sender: 'user' or 'assistant'
            message: Message text
            medium: 'phone_call', 'sms', or 'whatsapp'
            call_sid: Twilio call SID (for phone calls)
            message_sid: Twilio message SID (for SMS/WhatsApp)
            direction: 'inbound' or 'outbound'

        Returns:
            Conversation message ID
        """
        timestamp = datetime.now().isoformat()
        cursor = self.conn.execute(
            """INSERT INTO conversations
               (timestamp, sender, message, medium, call_sid, message_sid, direction)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (timestamp, sender, message, medium, call_sid, message_sid, direction)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_recent_conversations(self, limit: int = 20) -> List[Dict]:
        """Get recent conversation messages.

        Args:
            limit: Maximum number of messages to retrieve

        Returns:
            List of conversation dictionaries
        """
        cursor = self.conn.execute(
            "SELECT * FROM conversations ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        messages = [dict(row) for row in cursor.fetchall()]
        return list(reversed(messages))  # Return oldest first

    def get_conversation_context(self, limit: int = 10) -> str:
        """Get recent conversation context as formatted text.

        Args:
            limit: Number of recent messages to include

        Returns:
            Formatted conversation context string
        """
        messages = self.get_recent_conversations(limit)
        if not messages:
            return ""

        context_lines = []
        for msg in messages:
            sender_label = "User" if msg['sender'] == 'user' else "Assistant"
            medium_label = msg['medium'].replace('_', ' ')
            context_lines.append(
                f"{sender_label}: {msg['message']} (via {medium_label})"
            )

        return "\n".join(context_lines)

    def get_conversations_by_medium(self, medium: str, limit: int = 50) -> List[Dict]:
        """Get conversations filtered by medium.

        Args:
            medium: 'phone_call', 'sms', or 'whatsapp'
            limit: Maximum number of messages to retrieve

        Returns:
            List of conversation dictionaries
        """
        cursor = self.conn.execute(
            """SELECT * FROM conversations
               WHERE medium = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (medium, limit)
        )
        messages = [dict(row) for row in cursor.fetchall()]
        return list(reversed(messages))

    def get_conversations_by_call_sid(self, call_sid: str) -> List[Dict]:
        """Get all conversations for a specific call.

        Args:
            call_sid: Twilio Call SID

        Returns:
            List of conversation dictionaries for this call, in chronological order
        """
        cursor = self.conn.execute(
            """SELECT * FROM conversations
               WHERE call_sid = ?
               ORDER BY timestamp ASC""",
            (call_sid,)
        )
        return [dict(row) for row in cursor.fetchall()]

    # ==================== CALL GOALS ====================

    def add_call_goal(self, phone_number: str, contact_name: str, goal_type: str,
                      goal_description: str, preferred_date: str = None,
                      preferred_time: str = None, alternative_options: str = None) -> int:
        """Add a new call goal for outbound calling.

        Args:
            phone_number: Phone number to call
            contact_name: Name of person/organization to call
            goal_type: Type of goal (appointment, inquiry, followup, etc.)
            goal_description: Detailed description of what to accomplish
            preferred_date: Preferred date (e.g., "Wednesday", "2026-01-08")
            preferred_time: Preferred time (e.g., "2pm", "afternoon")
            alternative_options: Alternative times/dates if preferred not available

        Returns:
            Call goal ID
        """
        cursor = self.conn.execute(
            """INSERT INTO call_goals
               (phone_number, contact_name, goal_type, goal_description,
                preferred_date, preferred_time, alternative_options)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (phone_number, contact_name, goal_type, goal_description,
             preferred_date, preferred_time, alternative_options)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_call_goal(self, goal_id: int) -> Optional[Dict]:
        """Get a specific call goal by ID.

        Args:
            goal_id: Call goal ID

        Returns:
            Call goal dictionary or None
        """
        cursor = self.conn.execute("SELECT * FROM call_goals WHERE id = ?", (goal_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_call_goal_by_sid(self, call_sid: str) -> Optional[Dict]:
        """Get a specific call goal by Twilio Call SID.

        Args:
            call_sid: Twilio Call SID

        Returns:
            Call goal dictionary or None
        """
        cursor = self.conn.execute("SELECT * FROM call_goals WHERE call_sid = ?", (call_sid,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_pending_call_goals(self) -> List[Dict]:
        """Get all pending call goals.

        Returns:
            List of pending call goal dictionaries
        """
        cursor = self.conn.execute(
            "SELECT * FROM call_goals WHERE status = 'pending' ORDER BY created_at"
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_call_goal(self, goal_id: int, **kwargs) -> bool:
        """Update a call goal.

        Args:
            goal_id: Call goal ID
            **kwargs: Fields to update (status, result, call_sid, etc.)

        Returns:
            True if updated, False otherwise
        """
        allowed_fields = ['status', 'result', 'call_sid', 'completed_at',
                          'phone_number', 'goal_description', 'preferred_date',
                          'preferred_time', 'alternative_options']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [goal_id]

        self.conn.execute(f"UPDATE call_goals SET {set_clause} WHERE id = ?", values)
        self.conn.commit()
        return True

    def complete_call_goal(self, goal_id: int, result: str):
        """Mark a call goal as completed.

        Args:
            goal_id: Call goal ID
            result: Result description
        """
        now = datetime.now().isoformat()
        self.conn.execute(
            """UPDATE call_goals
               SET status = 'completed', result = ?, completed_at = ?
               WHERE id = ?""",
            (result, now, goal_id)
        )
        self.conn.commit()

    def fail_call_goal(self, goal_id: int, reason: str):
        """Mark a call goal as failed.

        Args:
            goal_id: Call goal ID
            reason: Failure reason
        """
        now = datetime.now().isoformat()
        self.conn.execute(
            """UPDATE call_goals
               SET status = 'failed', result = ?, completed_at = ?
               WHERE id = ?""",
            (reason, now, goal_id)
        )
        self.conn.commit()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
