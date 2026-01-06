"""Background service to check for due reminders and trigger phone calls."""
import asyncio
import logging
from datetime import datetime, timedelta
from database import Database
from typing import Optional, Callable
from config import Config

logger = logging.getLogger(__name__)


class ReminderChecker:
    """Checks for due reminders and triggers notifications/calls."""
    
    def __init__(self, db: Database, twilio_handler=None, session_manager=None, router=None):
        """Initialize reminder checker with multi-session awareness.

        Args:
            db: Database instance
            twilio_handler: TwilioMediaStreamsHandler for making calls
            session_manager: SessionManager for checking active sessions
            router: MessageRouter for routing reminders to active sessions
        """
        self.db = db
        self.twilio_handler = twilio_handler
        self.session_manager = session_manager
        self.router = router
        self.messaging_handler = None  # Will be set by main
        self.running = False
        self.check_interval = Config.REMINDER_CHECK_INTERVAL  # Check every N seconds (configurable)
    
    def update_check_interval(self):
        """Update check interval from config (called when config changes)."""
        self.check_interval = Config.REMINDER_CHECK_INTERVAL
        logger.info(f"Reminder check interval updated to {self.check_interval} seconds")

        # Track pending reminder for current call (deprecated - kept for compatibility)
        self.pending_reminder_id = None
        self.call_was_answered = False
    
    async def start(self):
        """Start the background reminder checking loop."""
        self.running = True
        logger.info("Reminder checker started")
        
        while self.running:
            try:
                await self._check_reminders()
                # Read interval from config each time (allows dynamic updates)
                interval = Config.REMINDER_CHECK_INTERVAL
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Error in reminder checker: {e}")
                interval = Config.REMINDER_CHECK_INTERVAL
                await asyncio.sleep(interval)
    
    def stop(self):
        """Stop the reminder checker."""
        self.running = False
        logger.info("Reminder checker stopped")
    
    # Deprecated methods - kept for backward compatibility
    def set_in_call(self, in_call: bool):
        """Deprecated: Set whether user is in a phone call (for backward compatibility)."""
        logger.debug(f"set_in_call called (deprecated): {in_call}")

    def set_call_answered(self, answered: bool):
        """Deprecated: Set whether call was answered (for backward compatibility)."""
        logger.debug(f"set_call_answered called (deprecated): {answered}")
    
    def _handle_call_ended(self):
        """Handle when a reminder call ends."""
        if not self.pending_reminder_id:
            return
        
        reminder_id = self.pending_reminder_id
        
        if self.call_was_answered:
            # User answered - mark reminder as complete
            logger.info(f"Reminder {reminder_id} was delivered - marking complete")
            
            # Check if it's recurring
            cursor = self.db.conn.execute(
                "SELECT recurrence FROM reminders WHERE id = ?",
                (reminder_id,)
            )
            row = cursor.fetchone()
            
            if row and row[0]:  # Recurring reminder
                # Just mark as triggered (already done in _handle_due_reminder)
                logger.info(f"Recurring reminder {reminder_id} will trigger again based on schedule")
            else:
                # Non-recurring - mark as complete (deactivate)
                self.db.mark_reminder_complete(reminder_id)
                logger.info(f"Non-recurring reminder {reminder_id} marked as complete")
        else:
            # User didn't answer - reschedule for 5 minutes
            logger.info(f"Reminder {reminder_id} not delivered - rescheduling in 5 minutes")
            new_time = datetime.now() + timedelta(minutes=5)
            self.db.reschedule_reminder(reminder_id, new_time)
        
        # Clear pending reminder
        self.pending_reminder_id = None
        self.call_was_answered = False
    
    async def _check_reminders(self):
        """Check for due reminders and handle them."""
        now = datetime.now()
        due_reminders = self.db.get_due_reminders(now)
        
        if not due_reminders:
            return
        
        logger.info(f"Found {len(due_reminders)} due reminder(s)")
        
        for reminder in due_reminders:
            await self._handle_due_reminder(reminder, now)
    
    async def _handle_due_reminder(self, reminder: dict, current_time: datetime):
        """Handle a due reminder with multi-session awareness.

        Args:
            reminder: Reminder dictionary
            current_time: Current datetime
        """
        reminder_id = reminder['id']
        title = reminder['title']

        logger.info(f"Processing due reminder: {title}")

        # Check if Máté has active main session
        mate_session = None
        if self.session_manager:
            mate_session = await self.session_manager.get_mate_main_session()

        if mate_session and mate_session.status.value == "active":
            # User is in active call - announce via router
            logger.info(f"Máté in active call - announcing reminder: {title}")

            if self.router:
                try:
                    await self.router.route_message(
                        from_session=None,  # System message
                        message=f"Reminder: {title}",
                        target="user",
                        message_type="reminder"
                    )
                    logger.info(f"Sent reminder to active session: {title}")
                except Exception as e:
                    logger.error(f"Error routing reminder to session: {e}")

            # Mark as complete since it's being announced
            if not reminder['recurrence']:
                self.db.mark_reminder_complete(reminder_id)
                logger.info(f"Marked non-recurring reminder {reminder_id} as complete after in-call announcement")

        else:
            # User not in call - use delivery method from config
            logger.info(f"Máté not in call - using fallback delivery for reminder: {title}")

            delivery_method = Config.REMINDER_DELIVERY.lower()

            # Send via call
            if delivery_method in ['call', 'both']:
                if self.twilio_handler:
                    try:
                        # Store reminder_id in twilio_handler so it can be marked complete when call is answered
                        if hasattr(self.twilio_handler, 'pending_reminder_id'):
                            self.twilio_handler.pending_reminder_id = reminder_id
                        self.twilio_handler.make_call(
                            to_number=Config.TARGET_PHONE_NUMBER,
                            reminder_message=title
                        )
                        logger.info(f"Initiated reminder call for: {title} (reminder_id: {reminder_id})")
                    except Exception as e:
                        logger.error(f"Error making reminder call: {e}")

            # Send via message (SMS)
            if delivery_method in ['message', 'both']:
                if self.messaging_handler:
                    try:
                        message_text = f"⏰ Reminder: {title}"
                        await self.messaging_handler.send_message(
                            to_number=Config.TARGET_PHONE_NUMBER,
                            message_body=message_text,
                            medium='sms'
                        )
                        logger.info(f"Sent reminder SMS for: {title}")
                    except Exception as e:
                        logger.error(f"Error sending reminder SMS: {e}")

            # Send via email
            if delivery_method in ['email', 'both']:
                # #region debug log
                try:
                    with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                        import json
                        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "E", "location": "reminder_checker.py:_handle_due_reminder:before_email", "message": "About to send reminder email", "data": {"delivery_method": delivery_method, "has_messaging_handler": self.messaging_handler is not None, "has_gmail_handler": self.messaging_handler.gmail_handler is not None if self.messaging_handler else False, "title": title, "target_email": Config.TARGET_EMAIL}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                except:
                    pass
                # #endregion
                if self.messaging_handler and self.messaging_handler.gmail_handler:
                    try:
                        message_text = f"⏰ Reminder: {title}"
                        result = self.messaging_handler.gmail_handler.send_email(
                            to_email=Config.TARGET_EMAIL,
                            subject=f"⏰ TARS Reminder: {title}",
                            body=message_text
                        )
                        # #region debug log
                        try:
                            with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                                import json
                                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "E", "location": "reminder_checker.py:_handle_due_reminder:after_email", "message": "Reminder email sent", "data": {"result": str(result), "title": title}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                        except:
                            pass
                        # #endregion
                        logger.info(f"Sent reminder email for: {title}")
                    except Exception as e:
                        # #region debug log
                        try:
                            with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                                import json
                                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "E", "location": "reminder_checker.py:_handle_due_reminder:email_error", "message": "Error sending reminder email", "data": {"error": str(e), "title": title}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                        except:
                            pass
                        # #endregion
                        logger.error(f"Error sending reminder email: {e}")

        # Mark as triggered
        self.db.mark_reminder_triggered(reminder_id)
        
        # If it's a recurring reminder, schedule next occurrence
        if reminder['recurrence']:
            await self._schedule_next_occurrence(reminder, current_time)
    
    async def _schedule_next_occurrence(self, reminder: dict, current_time: datetime):
        """Schedule next occurrence for recurring reminder.
        
        Args:
            reminder: Reminder dictionary
            current_time: Current datetime
        """
        reminder_time = datetime.fromisoformat(reminder['datetime'])
        next_time = None
        
        if reminder['recurrence'] == 'daily':
            # Schedule for same time tomorrow
            next_time = reminder_time.replace(
                year=current_time.year,
                month=current_time.month,
                day=current_time.day
            )
            # If that's in the past, move to tomorrow
            if next_time <= current_time:
                next_time = next_time.replace(day=next_time.day + 1)
        
        elif reminder['recurrence'] == 'weekly':
            # For weekly, the reminder will check days_of_week each day
            # Just move to tomorrow
            next_time = reminder_time.replace(day=reminder_time.day + 1)
        
        if next_time:
            self.db.update_reminder(
                reminder['id'],
                datetime=next_time.isoformat()
            )
            logger.info(f"Scheduled next occurrence for {reminder['title']} at {next_time}")
    
    def get_current_reminders_for_call(self) -> str:
        """Get formatted string of current due reminders for announcement.
        
        Returns:
            String describing due reminders
        """
        now = datetime.now()
        due_reminders = self.db.get_due_reminders(now)
        
        if not due_reminders:
            return None
        
        if len(due_reminders) == 1:
            return f"You have a reminder: {due_reminders[0]['title']}"
        else:
            titles = [r['title'] for r in due_reminders]
            return f"You have {len(due_reminders)} reminders: {', '.join(titles)}"

