"""Local SQLite database for TARS - Máté's Personal Assistant."""
import sqlite3
import logging
import json
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
                    email TEXT,
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
                    parent_session_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                )
            """)

            # Create agent_sessions table (for agent hub)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    call_sid TEXT NOT NULL,
                    session_name TEXT NOT NULL,
                    phone_number TEXT NOT NULL,
                    permission_level TEXT NOT NULL,
                    session_type TEXT NOT NULL,
                    purpose TEXT,
                    status TEXT NOT NULL,
                    parent_session_id TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY (parent_session_id) REFERENCES agent_sessions(session_id)
                )
            """)

            # Create indexes for agent_sessions
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_call_sid
                ON agent_sessions(call_sid)
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_phone
                ON agent_sessions(phone_number)
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_status
                ON agent_sessions(status)
            """)

            # Create inter_session_messages table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS inter_session_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL UNIQUE,
                    from_session_id TEXT,
                    to_session_id TEXT,
                    to_session_name TEXT,
                    message_type TEXT NOT NULL,
                    message_body TEXT NOT NULL,
                    context TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    delivered_at TEXT,
                    FOREIGN KEY (from_session_id) REFERENCES agent_sessions(session_id)
                )
            """)

            # Create indexes for inter_session_messages
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_from
                ON inter_session_messages(from_session_id)
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_to
                ON inter_session_messages(to_session_id)
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_status
                ON inter_session_messages(status)
            """)

            # Create broadcast_approvals table (for hybrid broadcast mode)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS broadcast_approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_group TEXT NOT NULL,
                    approved INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)

            # Create session_snapshots table (for session persistence)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS session_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    snapshot_type TEXT NOT NULL,
                    conversation_history TEXT NOT NULL,
                    system_instruction TEXT,
                    gemini_state TEXT,
                    message_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id)
                )
            """)

            # Create pending_approvals table (for interactive approvals)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    approval_id TEXT NOT NULL UNIQUE,
                    session_id TEXT,
                    question TEXT NOT NULL,
                    context TEXT,
                    options TEXT,
                    status TEXT DEFAULT 'pending',
                    response TEXT,
                    timeout_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id)
                )
            """)

            # Create console_messages table (for unified Gmail thread)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS console_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL UNIQUE,
                    session_id TEXT,
                    direction TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    subject TEXT,
                    body TEXT NOT NULL,
                    email_message_id TEXT,
                    thread_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id)
                )
            """)

            # Create email_drafts table (for draft management)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS email_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draft_id TEXT NOT NULL UNIQUE,
                    gmail_draft_id TEXT,
                    recipient_email TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    sent_at TEXT,
                    deleted_at TEXT
                )
            """)

            # Create programming_operations table (for programmer agent)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS programming_operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    operation_type TEXT NOT NULL,
                    command TEXT,
                    working_directory TEXT,
                    status TEXT NOT NULL,
                    output TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    executed_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES agent_sessions(session_id)
                )
            """)

            # Create project_cache table (for tracking projects)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS project_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT UNIQUE NOT NULL,
                    project_path TEXT NOT NULL,
                    project_type TEXT,
                    git_status TEXT,
                    last_accessed TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for programming operations
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_prog_ops_session
                ON programming_operations(session_id)
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_prog_ops_status
                ON programming_operations(status)
            """)

            self.conn.commit()

            # Run migrations
            self._run_migrations()

            logger.info(f"TARS database initialized at {self.db_path}")

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def _run_migrations(self):
        """Run database migrations for schema updates."""
        try:
            # Check if email column exists in contacts table
            cursor = self.conn.execute("PRAGMA table_info(contacts)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'email' not in columns:
                logger.info("Adding email column to contacts table")
                self.conn.execute("ALTER TABLE contacts ADD COLUMN email TEXT")
                self.conn.commit()
                logger.info("Email column added successfully")

            # Extend agent_sessions table for session persistence
            cursor = self.conn.execute("PRAGMA table_info(agent_sessions)")
            session_columns = [row[1] for row in cursor.fetchall()]

            if 'session_state' not in session_columns:
                logger.info("Adding session persistence columns to agent_sessions")
                self.conn.execute("ALTER TABLE agent_sessions ADD COLUMN session_state TEXT DEFAULT 'active'")
                self.conn.execute("ALTER TABLE agent_sessions ADD COLUMN platform TEXT DEFAULT 'call'")
                self.conn.execute("ALTER TABLE agent_sessions ADD COLUMN last_activity_at TEXT")
                self.conn.execute("ALTER TABLE agent_sessions ADD COLUMN can_resume INTEGER DEFAULT 0")
                self.conn.commit()
                logger.info("Session persistence columns added successfully")

            # Extend conversations table to link to sessions
            cursor = self.conn.execute("PRAGMA table_info(conversations)")
            conv_columns = [row[1] for row in cursor.fetchall()]

            if 'session_id' not in conv_columns:
                logger.info("Adding session_id column to conversations table")
                self.conn.execute("ALTER TABLE conversations ADD COLUMN session_id TEXT")
                self.conn.execute("ALTER TABLE conversations ADD COLUMN context_snapshot_id INTEGER")
                self.conn.commit()
                logger.info("Session link columns added to conversations")

            # Add embedding column to conversations table
            if 'embedding' not in conv_columns:
                logger.info("Adding embedding column to conversations table")
                self.conn.execute("ALTER TABLE conversations ADD COLUMN embedding TEXT")
                self.conn.commit()
                logger.info("Embedding column added to conversations")

            # Add session_name_embedding column to agent_sessions table
            cursor = self.conn.execute("PRAGMA table_info(agent_sessions)")
            session_columns = [row[1] for row in cursor.fetchall()]
            if 'session_name_embedding' not in session_columns:
                logger.info("Adding session_name_embedding column to agent_sessions table")
                self.conn.execute("ALTER TABLE agent_sessions ADD COLUMN session_name_embedding TEXT")
                self.conn.commit()
                logger.info("Session name embedding column added")

        except Exception as e:
            logger.warning(f"Migration error (non-critical): {e}")

    # ==================== EMAIL DRAFTS ====================

    def add_email_draft(self, draft_id: str, gmail_draft_id: str = None, recipient_email: str = "", 
                       subject: str = "", body: str = "") -> bool:
        """Add a new email draft.
        
        Args:
            draft_id: Unique draft identifier
            gmail_draft_id: Gmail API draft ID (if created via Gmail API)
            recipient_email: Recipient email address
            subject: Email subject
            body: Email body
            
        Returns:
            True if successful
        """
        try:
            self.conn.execute("""
                INSERT INTO email_drafts (draft_id, gmail_draft_id, recipient_email, subject, body, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (draft_id, gmail_draft_id, recipient_email, subject, body, datetime.now().isoformat()))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding email draft: {e}")
            return False

    def get_email_draft(self, draft_id: str) -> Optional[Dict]:
        """Get email draft by ID.
        
        Args:
            draft_id: Draft identifier
            
        Returns:
            Draft dict or None if not found
        """
        cursor = self.conn.execute("""
            SELECT * FROM email_drafts WHERE draft_id = ? AND deleted_at IS NULL
        """, (draft_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_email_drafts(self, status: str = 'pending') -> List[Dict]:
        """List all email drafts.
        
        Args:
            status: Filter by status (pending, sent, deleted)
            
        Returns:
            List of draft dicts
        """
        cursor = self.conn.execute("""
            SELECT * FROM email_drafts 
            WHERE status = ? AND deleted_at IS NULL
            ORDER BY created_at DESC
        """, (status,))
        return [dict(row) for row in cursor.fetchall()]

    def update_email_draft_status(self, draft_id: str, status: str, sent_at: str = None) -> bool:
        """Update draft status.
        
        Args:
            draft_id: Draft identifier
            status: New status (pending, sent, deleted)
            sent_at: Optional timestamp when sent
            
        Returns:
            True if successful
        """
        try:
            if status == 'sent' and sent_at:
                self.conn.execute("""
                    UPDATE email_drafts 
                    SET status = ?, sent_at = ? 
                    WHERE draft_id = ?
                """, (status, sent_at, draft_id))
            elif status == 'deleted':
                self.conn.execute("""
                    UPDATE email_drafts 
                    SET status = ?, deleted_at = ? 
                    WHERE draft_id = ?
                """, (status, datetime.now().isoformat(), draft_id))
            else:
                self.conn.execute("""
                    UPDATE email_drafts 
                    SET status = ? 
                    WHERE draft_id = ?
                """, (status, draft_id))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating draft status: {e}")
            return False

    def delete_email_draft(self, draft_id: str) -> bool:
        """Delete an email draft.
        
        Args:
            draft_id: Draft identifier
            
        Returns:
            True if successful
        """
        return self.update_email_draft_status(draft_id, 'deleted')

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

    def delete_all_reminders(self) -> int:
        """Delete all reminders.

        Returns:
            Number of reminders deleted
        """
        cursor = self.conn.execute("SELECT COUNT(*) FROM reminders")
        count = cursor.fetchone()[0]
        self.conn.execute("DELETE FROM reminders")
        self.conn.commit()
        logger.info(f"Deleted all {count} reminders")
        return count

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
                   email: str = None, birthday: str = None, notes: str = None) -> int:
        """Add a new contact.

        Args:
            name: Contact name
            relation: Relationship (e.g., "Girlfriend", "Friend", "Doctor")
            phone: Phone number
            email: Email address
            birthday: Birthday in ISO format (YYYY-MM-DD)
            notes: Additional notes or bio

        Returns:
            Contact ID
        """
        cursor = self.conn.execute(
            "INSERT INTO contacts (name, relation, phone, email, birthday, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (name, relation, phone, email, birthday, notes)
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
        allowed_fields = ['name', 'relation', 'phone', 'email', 'birthday', 'notes']
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
                                 direction: str = None, embedding: str = None) -> int:
        """Add a conversation message to the database.

        Args:
            sender: 'user' or 'assistant'
            message: Message text
            medium: 'phone_call', 'sms', or 'whatsapp'
            call_sid: Twilio call SID (for phone calls)
            message_sid: Twilio message SID (for SMS/WhatsApp)
            direction: 'inbound' or 'outbound'
            embedding: Optional JSON string of embedding vector

        Returns:
            Conversation message ID
        """
        timestamp = datetime.now().isoformat()
        cursor = self.conn.execute(
            """INSERT INTO conversations
               (timestamp, sender, message, medium, call_sid, message_sid, direction, embedding)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (timestamp, sender, message, medium, call_sid, message_sid, direction, embedding)
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

    def search_conversations_by_date(self, date_str: str, limit: int = 50) -> List[Dict]:
        """Search conversations by date.

        Args:
            date_str: Date string in various formats:
                - "YYYY-MM-DD" (e.g., "2024-01-15")
                - "last monday", "last tuesday", etc.
                - "on the 12th of january", "january 12"
            limit: Maximum number of messages to retrieve

        Returns:
            List of conversation dictionaries matching the date
        """
        from dateutil import parser, relativedelta
        from datetime import datetime, timedelta

        try:
            # Parse date string
            today = datetime.now().date()

            # Handle relative dates
            date_str_lower = date_str.lower().strip()
            if "last monday" in date_str_lower:
                days_since_monday = (today.weekday()) % 7
                if days_since_monday == 0:
                    days_since_monday = 7  # If today is Monday, get last Monday
                target_date = today - timedelta(days=days_since_monday)
            elif "last tuesday" in date_str_lower:
                days_since_tuesday = (today.weekday() - 1) % 7
                if days_since_tuesday == 0:
                    days_since_tuesday = 7
                target_date = today - timedelta(days=days_since_tuesday)
            elif "last wednesday" in date_str_lower:
                days_since_wednesday = (today.weekday() - 2) % 7
                if days_since_wednesday == 0:
                    days_since_wednesday = 7
                target_date = today - timedelta(days=days_since_wednesday)
            elif "last thursday" in date_str_lower:
                days_since_thursday = (today.weekday() - 3) % 7
                if days_since_thursday == 0:
                    days_since_thursday = 7
                target_date = today - timedelta(days=days_since_thursday)
            elif "last friday" in date_str_lower:
                days_since_friday = (today.weekday() - 4) % 7
                if days_since_friday == 0:
                    days_since_friday = 7
                target_date = today - timedelta(days=days_since_friday)
            elif "last saturday" in date_str_lower:
                days_since_saturday = (today.weekday() - 5) % 7
                if days_since_saturday == 0:
                    days_since_saturday = 7
                target_date = today - timedelta(days=days_since_saturday)
            elif "last sunday" in date_str_lower:
                days_since_sunday = (today.weekday() - 6) % 7
                if days_since_sunday == 0:
                    days_since_sunday = 7
                target_date = today - timedelta(days=days_since_sunday)
            else:
                # Try to parse as date
                try:
                    parsed_date = parser.parse(date_str, fuzzy=True, default=datetime.now())
                    target_date = parsed_date.date()
                except:
                    # Fallback: try to extract date from string like "12th of january"
                    import re
                    # Try to find day and month
                    day_match = re.search(r'(\d+)(?:st|nd|rd|th)?', date_str_lower)
                    month_match = re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)', date_str_lower)
                    if day_match and month_match:
                        day = int(day_match.group(1))
                        month_names = ['january', 'february', 'march', 'april', 'may', 'june',
                                      'july', 'august', 'september', 'october', 'november', 'december']
                        month = month_names.index(month_match.group(1)) + 1
                        year = today.year
                        target_date = datetime(year, month, day).date()
                        if target_date > today:
                            target_date = datetime(year - 1, month, day).date()
                    else:
                        # Default to today if can't parse
                        target_date = today

            # Search for conversations on that date
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())

            cursor = self.conn.execute(
                """SELECT * FROM conversations
                   WHERE timestamp >= ? AND timestamp <= ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (start_datetime.isoformat(), end_datetime.isoformat(), limit)
            )
            messages = [dict(row) for row in cursor.fetchall()]
            return list(reversed(messages))

        except Exception as e:
            logger.error(f"Error searching conversations by date: {e}")
            return []

    def search_conversations_by_topic(self, topic: str, api_key: str, limit: int = 20, threshold: float = 0.7) -> List[Dict]:
        """Search conversations by topic using embeddings.

        Args:
            topic: Topic to search for (e.g., "AI glasses")
            api_key: Gemini API key for generating embeddings
            limit: Maximum number of results
            threshold: Minimum similarity threshold (0.0 to 1.0)

        Returns:
            List of conversation dictionaries sorted by relevance
        """
        try:
            # Generate embedding for topic
            topic_embedding_json = self.generate_embedding(topic, api_key)
            if not topic_embedding_json:
                logger.warning("Failed to generate embedding for topic")
                return []

            topic_embedding = json.loads(topic_embedding_json)
            if isinstance(topic_embedding, dict) and 'values' in topic_embedding:
                topic_embedding = topic_embedding['values']

            # Get all conversations with embeddings
            cursor = self.conn.execute(
                "SELECT * FROM conversations WHERE embedding IS NOT NULL"
            )
            conversations = [dict(row) for row in cursor.fetchall()]

            # Calculate similarity for each conversation
            results = []
            for conv in conversations:
                try:
                    conv_embedding_json = conv.get('embedding')
                    if not conv_embedding_json:
                        continue

                    conv_embedding = json.loads(conv_embedding_json)
                    if isinstance(conv_embedding, dict) and 'values' in conv_embedding:
                        conv_embedding = conv_embedding['values']

                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(topic_embedding, conv_embedding)
                    if similarity >= threshold:
                        conv_copy = conv.copy()
                        conv_copy['similarity'] = similarity
                        results.append(conv_copy)
                except Exception as e:
                    logger.warning(f"Error calculating similarity for conversation {conv.get('id')}: {e}")
                    continue

            # Sort by similarity (highest first)
            results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Error searching conversations by topic: {e}")
            return []

    def search_conversations_by_similarity(self, query_text: str, api_key: str, limit: int = 20, threshold: float = 0.7) -> List[Dict]:
        """Search conversations by semantic similarity using embeddings.

        Args:
            query_text: Query text to find similar conversations
            api_key: Gemini API key for generating embeddings
            limit: Maximum number of results
            threshold: Minimum similarity threshold (0.0 to 1.0)

        Returns:
            List of conversation dictionaries sorted by similarity
        """
        # This is essentially the same as search_conversations_by_topic
        return self.search_conversations_by_topic(query_text, api_key, limit, threshold)

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        try:
            import math

            if len(vec1) != len(vec2):
                logger.warning(f"Vector length mismatch: {len(vec1)} vs {len(vec2)}")
                return 0.0

            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            magnitude1 = math.sqrt(sum(a * a for a in vec1))
            magnitude2 = math.sqrt(sum(a * a for a in vec2))

            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0

            return dot_product / (magnitude1 * magnitude2)
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0

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

    # ==================== AGENT SESSIONS ====================

    def add_agent_session(self, session_dict: Dict) -> int:
        """Add a new agent session.

        Args:
            session_dict: Session data dictionary

        Returns:
            Session row ID
        """
        cursor = self.conn.execute(
            """INSERT INTO agent_sessions
               (session_id, call_sid, session_name, phone_number, permission_level,
                session_type, purpose, status, parent_session_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_dict['session_id'], session_dict['call_sid'],
             session_dict['session_name'], session_dict['phone_number'],
             session_dict['permission_level'], session_dict['session_type'],
             session_dict.get('purpose'), session_dict['status'],
             session_dict.get('parent_session_id'), session_dict['created_at'])
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_session_by_id(self, session_id: str) -> Optional[Dict]:
        """Get session by session ID.

        Args:
            session_id: Session UUID

        Returns:
            Session dictionary or None
        """
        cursor = self.conn.execute(
            "SELECT * FROM agent_sessions WHERE session_id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_active_sessions(self) -> List[Dict]:
        """Get all active sessions.

        Returns:
            List of active session dictionaries
        """
        cursor = self.conn.execute(
            "SELECT * FROM agent_sessions WHERE status = 'active' ORDER BY created_at"
        )
        return [dict(row) for row in cursor.fetchall()]

    def complete_session(self, session_id: str, completed_at: datetime):
        """Mark session as completed.

        Args:
            session_id: Session UUID
            completed_at: Completion timestamp
        """
        self.conn.execute(
            """UPDATE agent_sessions
               SET status = 'completed', completed_at = ?
               WHERE session_id = ?""",
            (completed_at.isoformat(), session_id)
        )
        self.conn.commit()

    def search_contact_by_phone(self, phone_number: str) -> Optional[Dict]:
        """Search for contact by phone number.

        Args:
            phone_number: Phone number to search

        Returns:
            Contact dictionary or None
        """
        # Normalize phone number for comparison
        normalized = phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')

        cursor = self.conn.execute(
            "SELECT * FROM contacts WHERE phone LIKE ?",
            (f'%{normalized[-10:]}%',)  # Match last 10 digits
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ==================== INTER-SESSION MESSAGES ====================

    def add_inter_session_message(
        self,
        message_id: str,
        from_session_id: Optional[str],
        to_session_id: Optional[str],
        to_session_name: str,
        message_type: str,
        message_body: str,
        context: str = "",
        status: str = "pending",
        error_message: str = None
    ) -> int:
        """Add an inter-session message.

        Args:
            message_id: Unique message ID
            from_session_id: Source session ID (None for system messages)
            to_session_id: Target session ID (None for broadcasts)
            to_session_name: Target session name
            message_type: Message type
            message_body: Message content
            context: Optional context JSON string
            status: Message status
            error_message: Optional error message

        Returns:
            Message row ID
        """
        now = datetime.now().isoformat()
        delivered_at = now if status == 'delivered' else None

        cursor = self.conn.execute(
            """INSERT INTO inter_session_messages
               (message_id, from_session_id, to_session_id, to_session_name,
                message_type, message_body, context, status, error_message,
                created_at, delivered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (message_id, from_session_id, to_session_id, to_session_name,
             message_type, message_body, context, status, error_message,
             now, delivered_at)
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_message_status(self, message_id: str, status: str):
        """Update message delivery status.

        Args:
            message_id: Message UUID
            status: New status
        """
        now = datetime.now().isoformat()
        self.conn.execute(
            """UPDATE inter_session_messages
               SET status = ?, delivered_at = ?
               WHERE message_id = ?""",
            (status, now, message_id)
        )
        self.conn.commit()

    def get_inter_session_message(self, message_id: str) -> Optional[Dict]:
        """Get inter-session message by ID.

        Args:
            message_id: Message UUID

        Returns:
            Message dictionary or None
        """
        cursor = self.conn.execute(
            "SELECT * FROM inter_session_messages WHERE message_id = ?",
            (message_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ==================== BROADCAST APPROVALS ====================

    def add_broadcast_approval(self, session_group: str, approved: int = 0) -> int:
        """Add a broadcast approval record.

        Args:
            session_group: Group identifier
            approved: Approval status (0=not asked, 1=approved, 2=denied)

        Returns:
            Approval row ID
        """
        now = datetime.now().isoformat()
        cursor = self.conn.execute(
            """INSERT INTO broadcast_approvals
               (session_group, approved, created_at)
               VALUES (?, ?, ?)""",
            (session_group, approved, now)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_broadcast_approval(self, session_group: str) -> Optional[Dict]:
        """Get broadcast approval for a session group.

        Args:
            session_group: Group identifier

        Returns:
            Approval dictionary or None
        """
        cursor = self.conn.execute(
            "SELECT * FROM broadcast_approvals WHERE session_group = ? ORDER BY created_at DESC LIMIT 1",
            (session_group,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_broadcast_approval(self, session_group: str, approved: int):
        """Update broadcast approval status.

        Args:
            session_group: Group identifier
            approved: Approval status (1=approved, 2=denied)
        """
        self.conn.execute(
            """UPDATE broadcast_approvals
               SET approved = ?
               WHERE session_group = ?""",
            (approved, session_group)
        )
        self.conn.commit()

    # ==================== SESSION SNAPSHOTS ====================

    def save_session_snapshot(self, session_id: str, conversation_history: str, snapshot_type: str = 'full') -> int:
        """Save session conversation snapshot for persistence.

        Args:
            session_id: Session UUID
            conversation_history: JSON string of conversation messages
            snapshot_type: Type of snapshot ('full', 'summary', 'recent')

        Returns:
            Snapshot row ID
        """
        import json
        history = json.loads(conversation_history) if isinstance(conversation_history, str) else conversation_history
        message_count = len(history)
        now = datetime.now().isoformat()

        cursor = self.conn.execute(
            """INSERT INTO session_snapshots
               (session_id, snapshot_type, conversation_history, message_count, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, snapshot_type, conversation_history, message_count, now)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_latest_session_snapshot(self, session_id: str) -> Optional[Dict]:
        """Get most recent snapshot for a session.

        Args:
            session_id: Session UUID

        Returns:
            Snapshot dictionary or None
        """
        cursor = self.conn.execute(
            "SELECT * FROM session_snapshots WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_session_conversation_history(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Get conversation history for a session.

        Args:
            session_id: Session UUID
            limit: Optional limit on number of messages

        Returns:
            List of message dictionaries
        """
        query = "SELECT * FROM conversations WHERE session_id = ? ORDER BY timestamp"
        if limit:
            query += f" LIMIT {limit}"

        cursor = self.conn.execute(query, (session_id,))
        return [dict(row) for row in cursor.fetchall()]

    # ==================== SESSION STATE MANAGEMENT ====================

    def suspend_session(self, session_id: str):
        """Mark session as suspended (paused for later resumption).

        Args:
            session_id: Session UUID
        """
        now = datetime.now().isoformat()
        self.conn.execute(
            """UPDATE agent_sessions
               SET status = 'suspended', session_state = 'suspended', last_activity_at = ?
               WHERE session_id = ?""",
            (now, session_id)
        )
        self.conn.commit()

    def mark_session_resumable(self, session_id: str, resumable: bool = True):
        """Mark session as resumable or not.

        Args:
            session_id: Session UUID
            resumable: True if session can be resumed
        """
        self.conn.execute(
            """UPDATE agent_sessions
               SET can_resume = ?
               WHERE session_id = ?""",
            (1 if resumable else 0, session_id)
        )
        self.conn.commit()

    def get_resumable_sessions(self, phone_number: str) -> List[Dict]:
        """Get all resumable sessions for a phone number.

        Args:
            phone_number: Phone number to query

        Returns:
            List of resumable session dictionaries (most recent first)
        """
        cursor = self.conn.execute(
            """SELECT * FROM agent_sessions
               WHERE phone_number = ? AND can_resume = 1 AND status = 'suspended'
               ORDER BY last_activity_at DESC""",
            (phone_number,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_session_activity(self, session_id: str):
        """Update last activity timestamp for a session.

        Args:
            session_id: Session UUID
        """
        now = datetime.now().isoformat()
        self.conn.execute(
            """UPDATE agent_sessions
               SET last_activity_at = ?
               WHERE session_id = ?""",
            (now, session_id)
        )
        self.conn.commit()

    # ==================== PENDING APPROVALS ====================

    def add_pending_approval(self, approval_id: str, session_id: Optional[str], question: str,
                           options: str, timeout_minutes: int = 5) -> int:
        """Add a pending approval request.

        Args:
            approval_id: Unique approval UUID
            session_id: Optional associated session UUID
            question: Question text
            options: JSON string of options
            timeout_minutes: Minutes until timeout

        Returns:
            Approval row ID
        """
        from datetime import timedelta
        now = datetime.now()
        timeout_at = (now + timedelta(minutes=timeout_minutes)).isoformat()
        created_at = now.isoformat()

        cursor = self.conn.execute(
            """INSERT INTO pending_approvals
               (approval_id, session_id, question, options, status, timeout_at, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
            (approval_id, session_id, question, options, timeout_at, created_at)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_pending_approval(self, approval_id: str) -> Optional[Dict]:
        """Get pending approval by ID.

        Args:
            approval_id: Approval UUID

        Returns:
            Approval dictionary or None
        """
        cursor = self.conn.execute(
            "SELECT * FROM pending_approvals WHERE approval_id = ?",
            (approval_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def resolve_approval(self, approval_id: str, response: str):
        """Resolve a pending approval.

        Args:
            approval_id: Approval UUID
            response: User's response ('approved', 'denied', etc.)
        """
        now = datetime.now().isoformat()
        status = 'approved' if 'approv' in response.lower() or 'yes' in response.lower() else 'denied'

        self.conn.execute(
            """UPDATE pending_approvals
               SET status = ?, response = ?, resolved_at = ?
               WHERE approval_id = ?""",
            (status, response, now, approval_id)
        )
        self.conn.commit()

    def expire_timeouts(self):
        """Mark timed-out approvals as expired."""
        now = datetime.now().isoformat()
        self.conn.execute(
            """UPDATE pending_approvals
               SET status = 'timeout'
               WHERE status = 'pending' AND timeout_at < ?""",
            (now,)
        )
        self.conn.commit()

    def get_pending_approvals_for_user(self, phone_number: str) -> List[Dict]:
        """Get all pending approvals for a user.

        Args:
            phone_number: User's phone number

        Returns:
            List of pending approval dictionaries
        """
        # Join with agent_sessions to get approvals for user's sessions
        cursor = self.conn.execute(
            """SELECT pa.* FROM pending_approvals pa
               LEFT JOIN agent_sessions s ON pa.session_id = s.session_id
               WHERE pa.status = 'pending'
               AND (s.phone_number = ? OR pa.session_id IS NULL)
               ORDER BY pa.created_at""",
            (phone_number,)
        )
        return [dict(row) for row in cursor.fetchall()]

    # ==================== CONSOLE MESSAGES ====================

    def add_console_message(self, session_id: Optional[str], direction: str, message_type: str,
                          subject: str, body: str, thread_id: Optional[str] = None) -> int:
        """Add a console message to unified thread.

        Args:
            session_id: Optional associated session UUID
            direction: 'inbound' or 'outbound'
            message_type: Message type ('command', 'summary', 'approval', etc.)
            subject: Message subject
            body: Message body
            thread_id: Optional Gmail thread ID

        Returns:
            Message row ID
        """
        import uuid
        message_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        cursor = self.conn.execute(
            """INSERT INTO console_messages
               (message_id, session_id, direction, message_type, subject, body, thread_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (message_id, session_id, direction, message_type, subject, body, thread_id, now)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_console_thread(self, limit: int = 50) -> List[Dict]:
        """Get console message thread.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of message dictionaries (most recent first)
        """
        cursor = self.conn.execute(
            "SELECT * FROM console_messages ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def link_message_to_session(self, message_id: str, session_id: str):
        """Link a console message to a session.

        Args:
            message_id: Message UUID
            session_id: Session UUID
        """
        self.conn.execute(
            """UPDATE console_messages
               SET session_id = ?
               WHERE message_id = ?""",
            (session_id, message_id)
        )
        self.conn.commit()

    # ==================== EMBEDDINGS ====================

    def generate_embedding(self, text: str, api_key: str) -> Optional[str]:
        """Generate embedding for text using Gemini embeddings API.

        Args:
            text: Text to generate embedding for
            api_key: Gemini API key

        Returns:
            JSON string of embedding vector, or None if generation fails
        """
        try:
            from google import genai
            import asyncio

            client = genai.Client(
                http_options={"api_version": "v1beta"},
                api_key=api_key
            )

            # Use Gemini embeddings model
            # Try to use async method if available, otherwise sync
            try:
                # Check if we're in an async context
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in async context, but this is a sync method
                    # We'll need to handle this differently
                    # For now, use sync approach
                    result = client.models.embed_content(
                        model="models/text-embedding-004",
                        contents=[text]
                    )
                else:
                    # No running loop, can use async
                    result = asyncio.run(client.aio.models.embed_content(
                        model="models/text-embedding-004",
                        contents=[text]
                    ))
            except RuntimeError:
                # No event loop, use sync
                result = client.models.embed_content(
                    model="models/text-embedding-004",
                    contents=[text]
                )

            # Extract embedding from result
            if result and hasattr(result, 'embeddings') and result.embeddings:
                # Result has embeddings list
                embedding = result.embeddings[0]
                if hasattr(embedding, 'values'):
                    return json.dumps(embedding.values)
                elif isinstance(embedding, (list, tuple)):
                    return json.dumps(list(embedding))
                else:
                    return json.dumps(embedding)
            elif result and hasattr(result, 'embedding'):
                embedding = result.embedding
                if hasattr(embedding, 'values'):
                    return json.dumps(embedding.values)
                else:
                    return json.dumps(embedding)
            elif result and isinstance(result, dict):
                if 'embeddings' in result and result['embeddings']:
                    embedding = result['embeddings'][0]
                    return json.dumps(embedding.get('values', embedding) if isinstance(embedding, dict) else embedding)
                elif 'embedding' in result:
                    embedding = result['embedding']
                    return json.dumps(embedding.get('values', embedding) if isinstance(embedding, dict) else embedding)
            else:
                logger.warning("Embedding generation returned unexpected format")
                return None

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    async def generate_embedding_async(self, text: str, api_key: str) -> Optional[str]:
        """Generate embedding for text using Gemini embeddings API (async version).

        Args:
            text: Text to generate embedding for
            api_key: Gemini API key

        Returns:
            JSON string of embedding vector, or None if generation fails
        """
        try:
            from google import genai

            client = genai.Client(
                http_options={"api_version": "v1beta"},
                api_key=api_key
            )

            # Use Gemini embeddings model
            result = await client.aio.models.embed_content(
                model="models/text-embedding-004",
                contents=[text]
            )

            # Extract embedding from result
            if result and hasattr(result, 'embeddings') and result.embeddings:
                # Result has embeddings list
                embedding = result.embeddings[0]
                if hasattr(embedding, 'values'):
                    return json.dumps(embedding.values)
                elif isinstance(embedding, (list, tuple)):
                    return json.dumps(list(embedding))
                else:
                    return json.dumps(embedding)
            elif result and hasattr(result, 'embedding'):
                embedding = result.embedding
                if hasattr(embedding, 'values'):
                    return json.dumps(embedding.values)
                else:
                    return json.dumps(embedding)
            elif result and isinstance(result, dict):
                if 'embeddings' in result and result['embeddings']:
                    embedding = result['embeddings'][0]
                    return json.dumps(embedding.get('values', embedding) if isinstance(embedding, dict) else embedding)
                elif 'embedding' in result:
                    embedding = result['embedding']
                    return json.dumps(embedding.get('values', embedding) if isinstance(embedding, dict) else embedding)
            else:
                logger.warning("Embedding generation returned unexpected format")
                return None

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    def update_conversation_embedding(self, message_id: int, embedding: str):
        """Update embedding for a conversation message.

        Args:
            message_id: Conversation message ID
            embedding: JSON string of embedding vector
        """
        self.conn.execute(
            "UPDATE conversations SET embedding = ? WHERE id = ?",
            (embedding, message_id)
        )
        self.conn.commit()

    # Programmer Agent Database Methods

    def log_programming_operation(
        self,
        session_id: str,
        operation_type: str,
        command: str,
        working_directory: str,
        status: str = 'pending'
    ) -> int:
        """Log a programming operation.

        Args:
            session_id: Session ID
            operation_type: Type of operation (terminal, file_edit, github)
            command: Command or operation description
            working_directory: Working directory
            status: Operation status

        Returns:
            Operation ID
        """
        cursor = self.conn.execute(
            """INSERT INTO programming_operations 
               (session_id, operation_type, command, working_directory, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, operation_type, command, working_directory, status, datetime.now().isoformat())
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_programming_operation(
        self,
        operation_id: int,
        status: str,
        output: str = None,
        error: str = None
    ):
        """Update a programming operation.

        Args:
            operation_id: Operation ID
            status: New status
            output: Operation output
            error: Error message if any
        """
        executed_at = datetime.now().isoformat() if status in ['executed', 'completed', 'failed'] else None
        self.conn.execute(
            """UPDATE programming_operations 
               SET status = ?, output = ?, error = ?, executed_at = ?
               WHERE id = ?""",
            (status, output, error, executed_at, operation_id)
        )
        self.conn.commit()

    def get_programming_operations(
        self,
        session_id: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get programming operations.

        Args:
            session_id: Filter by session ID (optional)
            limit: Maximum number of operations to return

        Returns:
            List of operation dictionaries
        """
        if session_id:
            cursor = self.conn.execute(
                """SELECT * FROM programming_operations 
                   WHERE session_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (session_id, limit)
            )
        else:
            cursor = self.conn.execute(
                """SELECT * FROM programming_operations 
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,)
            )
        return [dict(row) for row in cursor.fetchall()]

    def cache_project(
        self,
        project_name: str,
        project_path: str,
        project_type: str = None,
        git_status: str = 'none'
    ):
        """Cache project information.

        Args:
            project_name: Project name
            project_path: Full path to project
            project_type: Type of project (python, node, react, etc.)
            git_status: Git status (initialized, clean, modified, none)
        """
        try:
            self.conn.execute(
                """INSERT OR REPLACE INTO project_cache 
                   (project_name, project_path, project_type, git_status, last_accessed)
                   VALUES (?, ?, ?, ?, ?)""",
                (project_name, project_path, project_type, git_status, datetime.now().isoformat())
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error caching project: {e}")

    def get_cached_project(self, project_name: str) -> Optional[Dict]:
        """Get cached project information.

        Args:
            project_name: Project name

        Returns:
            Project dictionary or None
        """
        cursor = self.conn.execute(
            "SELECT * FROM project_cache WHERE project_name = ?",
            (project_name,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_cached_projects(self) -> List[Dict]:
        """Get all cached projects.

        Returns:
            List of project dictionaries
        """
        cursor = self.conn.execute(
            "SELECT * FROM project_cache ORDER BY last_accessed DESC"
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_project_git_status(self, project_name: str, git_status: str):
        """Update project git status.

        Args:
            project_name: Project name
            git_status: New git status
        """
        self.conn.execute(
            "UPDATE project_cache SET git_status = ?, last_accessed = ? WHERE project_name = ?",
            (git_status, datetime.now().isoformat(), project_name)
        )
        self.conn.commit()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
