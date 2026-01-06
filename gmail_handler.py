"""Gmail handler for TARS - The Unified Console Interface."""
import smtplib
import imaplib
import email
import logging
import asyncio
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, List, Dict
from config import Config
from database import Database

logger = logging.getLogger(__name__)


class GmailHandler:
    """Handles sending and receiving emails via Gmail."""

    def __init__(self, database: Database, messaging_handler, session_manager=None):
        """Initialize Gmail handler.

        Args:
            database: Database instance
            messaging_handler: Reference to main MessagingHandler for AI processing
            session_manager: Optional SessionManager for call summaries
        """
        self.db = database
        self.messaging_handler = messaging_handler
        self.session_manager = session_manager
        self.email_user = Config.GMAIL_USER
        self.email_pass = Config.GMAIL_APP_PASSWORD
        self.running = False
        self.thread_id = None  # Main TARS console thread

        if not self.email_user or not self.email_pass:
            logger.warning(
                "Gmail credentials not set. Gmail Console disabled.")
            print("DEBUG: Gmail credentials missing in config.")
            return

        logger.info(
            f"GmailHandler initialized for {self.email_user} (Target: {Config.TARGET_EMAIL})")
        print(f"DEBUG: GmailHandler initialized for {self.email_user}")

    async def start_polling(self):
        """Start background polling for new emails."""
        if not self.email_user or not self.email_pass:
            return

        self.running = True
        logger.info("Started Gmail polling loop")

        # Capture the main event loop
        loop = asyncio.get_running_loop()

        while self.running:
            try:
                await self._check_new_emails(loop)
            except Exception as e:
                print(f"DEBUG: Error in polling loop: {e}")
                logger.error(f"Error polling Gmail: {e}")

            # Poll every N seconds (configurable via GMAIL_POLL_INTERVAL)
            poll_interval = Config.GMAIL_POLL_INTERVAL
            await asyncio.sleep(poll_interval)

    def stop(self):
        """Stop polling."""
        self.running = False

    async def _check_new_emails(self, loop):
        """Check for UNSEEN emails from the target user."""
        # Run blocking IMAP operations in a separate thread to avoid freezing the bot
        await asyncio.to_thread(self._check_new_emails_sync, loop)

    def _check_new_emails_sync(self, loop):
        """Synchronous implementation of email checking."""
        try:
            # print("DEBUG: Checking IMAP...") # Uncomment if you want to see every check
            # Connect to IMAP
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self.email_user, self.email_pass)
            mail.select("inbox")

            # Search for unread emails
            # We accept emails from anyone for now, but security logic will filter actions
            status, messages = mail.search(None, '(UNSEEN)')

            if status != "OK" or not messages[0]:
                mail.logout()
                return

            logger.info(f"Found {len(messages[0].split())} unread email(s)")
            print(f"DEBUG: Found {len(messages[0].split())} unread email(s)!")

            for num in messages[0].split():
                # Fetch email
                status, msg_data = mail.fetch(num, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Extract sender
                sender = email.utils.parseaddr(msg['From'])[1]
                subject = msg['Subject']

                # Extract body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            try:
                                body = part.get_payload(decode=True).decode(
                                    'utf-8', errors='ignore')
                            except:
                                body = part.get_payload(decode=True).decode(
                                    'latin-1', errors='ignore')
                            break
                else:
                    try:
                        body = msg.get_payload(decode=True).decode(
                            'utf-8', errors='ignore')
                    except:
                        body = msg.get_payload(decode=True).decode(
                            'latin-1', errors='ignore')

                logger.info(f"Received email from {sender}: {subject}")
                print(f"DEBUG: Processing email from {sender}: {subject}")

                # Process via MessagingHandler (reusing the AI logic)
                # We treat the email address as the "phone number" for ID purposes
                if self.messaging_handler:
                    # Run in background to not block polling
                    # Note: We use the main loop from the handler if available, or create a new task
                    # Since we are in a thread, we need to be careful.
                    # Ideally, we schedule this back on the main loop.
                    coro = self.messaging_handler.process_incoming_message(
                        from_number=sender,
                        message_body=body.strip(),
                        medium='gmail',
                        to_number=self.email_user
                    )
                    asyncio.run_coroutine_threadsafe(coro, loop)

            mail.logout()

        except Exception as e:
            print(f"DEBUG: IMAP Error: {e}")
            logger.error(f"IMAP Error: {e}")

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send an email via SMTP.

        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body text

        Returns:
            True if successful
        """
        # #region debug log
        try:
            with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                import json
                f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "gmail_handler.py:send_email:entry", "message": "send_email called", "data": {"to_email": to_email, "subject": subject[:50], "has_credentials": bool(self.email_user and self.email_pass)}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
        except:
            pass
        # #endregion
        
        if not self.email_user or not self.email_pass:
            logger.error("Cannot send email: Credentials missing")
            return False

        # Validate email address format
        from config import Config
        if not to_email or '@' not in to_email:
            # #region debug log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "gmail_handler.py:send_email:invalid_email", "message": "Invalid email address", "data": {"to_email": to_email, "target_email": Config.TARGET_EMAIL}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion
            logger.error(f"Invalid email address: {to_email}. Using TARGET_EMAIL instead.")
            to_email = Config.TARGET_EMAIL
            if not to_email or '@' not in to_email:
                logger.error(f"TARGET_EMAIL is also invalid: {to_email}")
                return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = f"TARS <{self.email_user}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.email_user, self.email_pass)
            text = msg.as_string()
            # #region debug log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "gmail_handler.py:send_email:before_sendmail", "message": "About to call sendmail", "data": {"from": self.email_user, "to": to_email}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion
            result = server.sendmail(self.email_user, to_email, text)
            # #region debug log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "gmail_handler.py:send_email:after_sendmail", "message": "sendmail result", "data": {"result": str(result) if result else "success"}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion
            server.quit()

            logger.info(f"Sent email to {to_email}: {subject}")

            # Log to database
            self.db.add_conversation_message(
                sender='assistant',
                message=f"Subject: {subject}\n\n{body}",
                medium='gmail',
                direction='outbound'
            )

            return True

        except Exception as e:
            # #region debug log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "gmail_handler.py:send_email:error", "message": "SMTP error", "data": {"error": str(e), "to_email": to_email}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion
            logger.error(f"SMTP Error: {e}")
            return False

    async def send_console_message(self, message: str, message_type: str = "notification"):
        """Send a formatted message to the user's console (Gmail).

        This formats TARS outputs (reminders, reports) into nice emails.
        """
        # Default to sending to the configured user if no specific target
        # In a real multi-user system, we'd look up the user
        target_email = Config.TARGET_EMAIL

        subject = "TARS Notification"
        if message_type == "reminder":
            subject = "⏰ TARS Reminder"
        elif message_type == "call_report":
            subject = "📞 Call Summary"
        elif message_type == "confirmation_request":
            subject = "❓ Action Required"
        elif message_type == "call_summary":
            subject = "📝 Conversation Summary"

        # Add timestamp to subject to thread properly/uniquely
        timestamp = datetime.now().strftime("%H:%M")
        subject = f"{subject} ({timestamp})"

        # Run in thread to avoid blocking async loop with SMTP
        await asyncio.to_thread(
            self.send_email,
            target_email,
            subject,
            message
        )

    async def send_call_summary(self, session, summary_text: str):
        """Send call summary to console after call ends.

        Args:
            session: AgentSession that just ended
            summary_text: AI-generated summary of the call
        """
        duration = (session.completed_at - session.created_at).total_seconds()
        duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"

        subject = f"📞 Call Summary ({datetime.now().strftime('%I:%M %p')})"
        body = f"""Call with {session.session_name} completed.

Duration: {duration_str}

Summary:
{summary_text}

---
Reply to this email to send a message to TARS.
        """

        # Send with threading
        await self._send_threaded_email(
            to_email=Config.TARGET_EMAIL,
            subject=subject,
            body=body,
            message_type='call_summary'
        )

        # Log to database
        self.db.add_console_message(
            session_id=session.session_id,
            direction='outbound',
            message_type='call_summary',
            subject=subject,
            body=body,
            thread_id=self.thread_id
        )

    async def send_approval_request(self, approval_id: str, question: str,
                                   options: List[str], context: str = ""):
        """Send interactive approval request.

        Args:
            approval_id: Unique approval ID
            question: Question to ask
            options: List of options (e.g., ["YES", "NO"])
            context: Optional context
        """
        subject = "❓ Approval Required"

        options_text = " / ".join([f"'{opt}'" for opt in options])

        body = f"""TARS needs your approval:

{question}

Options: {options_text}

{context if context else ''}

---
Reply with your choice to approve or deny.
This request will timeout in 5 minutes.
        """

        await self._send_threaded_email(
            to_email=Config.TARGET_EMAIL,
            subject=subject,
            body=body,
            message_type='approval_request'
        )

        # Store pending approval in database
        import json
        self.db.add_pending_approval(
            approval_id=approval_id,
            session_id=None,  # Could link to active session
            question=question,
            options=json.dumps(options),
            timeout_minutes=5
        )

    async def send_link_during_call(self, session_id: str, url: str, description: str = ""):
        """Send link/snapshot during active call.

        Args:
            session_id: Active session ID
            url: URL to send
            description: Optional description
        """
        subject = "🔗 Link from TARS"
        body = f"""{description if description else 'TARS sent you a link:'}

{url}

---
This was sent during your call. Continue the conversation on the call.
        """

        await self._send_threaded_email(
            to_email=Config.TARGET_EMAIL,
            subject=subject,
            body=body,
            message_type='link'
        )

    async def send_detailed_response(self, session_id: str, content: str,
                                    response_type: str = "detailed explanation"):
        """Send detailed/long response during active call.

        Args:
            session_id: Active session ID
            content: Full detailed content
            response_type: Type of response (for subject line)
        """
        subject = f"📄 {response_type.title()}"

        body = f"""TARS sent you detailed information during your call:

{content}

---
This was sent because the explanation was too long to speak comfortably.
Continue the conversation on your call.
        """

        await self._send_threaded_email(
            to_email=Config.TARGET_EMAIL,
            subject=subject,
            body=body,
            message_type='detailed_response'
        )

        logger.info(f"Sent detailed response to Gmail during session {session_id[:8]}")

    async def _send_threaded_email(self, to_email: str, subject: str, body: str,
                                   message_type: str):
        """Send email with threading support.

        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body
            message_type: Type of message (for tracking)
        """
        # Implement Gmail threading using In-Reply-To and References headers
        msg = MIMEMultipart()
        msg['From'] = f"TARS <{self.email_user}>"
        msg['To'] = to_email
        msg['Subject'] = subject

        # Add threading headers if thread exists
        if self.thread_id:
            msg['In-Reply-To'] = self.thread_id
            msg['References'] = self.thread_id

        msg.attach(MIMEText(body, 'plain'))

        # Send via SMTP
        await asyncio.to_thread(self._smtp_send, msg)

        # Store thread ID from first message
        if not self.thread_id and message_type == 'call_summary':
            # Extract Message-ID after sending
            self.thread_id = msg.get('Message-ID')

    def _smtp_send(self, msg):
        """Synchronous SMTP send.

        Args:
            msg: MIMEMultipart message to send
        """
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(self.email_user, self.email_pass)
        server.send_message(msg)
        server.quit()
