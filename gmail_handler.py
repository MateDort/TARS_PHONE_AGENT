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

                # Email filtering logic
                # Only process emails from TARGET_EMAIL (user's own email)
                if sender.lower() == Config.TARGET_EMAIL.lower():
                    # This is from the user - process normally
                    if self.messaging_handler:
                        coro = self.messaging_handler.process_incoming_message(
                            from_number=sender,
                            message_body=body.strip(),
                            medium='gmail',
                            to_number=self.email_user
                        )
                        asyncio.run_coroutine_threadsafe(coro, loop)
                elif any(term in sender.lower() for term in ['no-reply', 'noreply', 'donotreply', 'no_reply']):
                    # Skip no-reply emails - don't process
                    logger.info(f"Skipping no-reply email from {sender}")
                    continue
                else:
                    # Other emails - use AI to determine if needs reply
                    # Run async check in thread
                    message_id = num.decode('utf-8')
                    coro = self._process_other_email(sender, subject, body.strip(), message_id)
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

    async def _process_other_email(self, sender: str, subject: str, body: str, message_id: str):
        """Process emails that are not from TARGET_EMAIL and not no-reply.
        
        Args:
            sender: Sender email address
            subject: Email subject
            body: Email body
            message_id: IMAP message ID (string)
        """
        try:
            # Use AI to determine if email needs a reply
            needs_reply = await self._should_reply_to_email(sender, subject, body)
            
            if needs_reply:
                # Create draft and notify user
                await self._create_draft_and_notify(sender, subject, body)
            else:
                # Use smart processing to decide action
                await self._smart_process_email(sender, subject, body, message_id)
        except Exception as e:
            logger.error(f"Error processing other email: {e}")

    async def _should_reply_to_email(self, sender: str, subject: str, body: str) -> bool:
        """Use AI to determine if an email needs a reply.
        
        Args:
            sender: Sender email address
            subject: Email subject
            body: Email body
            
        Returns:
            True if email needs a reply, False otherwise
        """
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(
                http_options={"api_version": "v1beta"},
                api_key=Config.GEMINI_API_KEY
            )
            
            prompt = f"""Analyze this email and determine if it needs a reply from the user.

From: {sender}
Subject: {subject}
Body: {body[:500]}

Consider:
- Is it a personal message that requires a response?
- Is it a question or request?
- Is it a transactional email (receipts, confirmations) that doesn't need a reply?
- Is it promotional/marketing that can be ignored?

Respond with only "YES" if it needs a reply, or "NO" if it doesn't."""
            
            response = await client.aio.models.generate_content(
                model="models/gemini-2.0-flash-exp",
                contents=[types.Content(parts=[types.Part(text=prompt)], role="user")],
                config=types.GenerateContentConfig(temperature=0.3)
            )
            
            if response.candidates and response.candidates[0].content.parts:
                result = response.candidates[0].content.parts[0].text.strip().upper()
                return "YES" in result
            
            return False
        except Exception as e:
            logger.error(f"Error determining if email needs reply: {e}")
            return False
        finally:
            if 'client' in locals():
                client.close()

    async def _smart_process_email(self, sender: str, subject: str, body: str, message_id: str):
        """Intelligently process email using AI to decide action.
        
        Args:
            sender: Sender email address
            subject: Email subject
            body: Email body
            message_id: IMAP message ID (string)
        """
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(
                http_options={"api_version": "v1beta"},
                api_key=Config.GEMINI_API_KEY
            )
            
            prompt = f"""Analyze this email and decide the best action:

From: {sender}
Subject: {subject}
Body: {body[:500]}

Actions available:
- archive: For promotional emails, newsletters, non-urgent updates
- delete: For obvious spam, junk mail, unwanted advertisements
- notify: For important emails that need user attention but don't need immediate reply

Respond with only one word: "archive", "delete", or "notify"."""
            
            response = await client.aio.models.generate_content(
                model="models/gemini-2.0-flash-exp",
                contents=[types.Content(parts=[types.Part(text=prompt)], role="user")],
                config=types.GenerateContentConfig(temperature=0.3)
            )
            
            action = None
            if response.candidates and response.candidates[0].content.parts:
                result = response.candidates[0].content.parts[0].text.strip().lower()
                if "archive" in result:
                    action = "archive"
                elif "delete" in result:
                    action = "delete"
                else:
                    action = "notify"
            
            # Execute action
            if action == "archive":
                await asyncio.to_thread(self.archive_email, message_id)
                await self._notify_email_action(sender, subject, "archived")
            elif action == "delete":
                await asyncio.to_thread(self.delete_email, message_id)
                await self._notify_email_action(sender, subject, "deleted")
            else:
                # Notify user about the email
                await self._notify_email_action(sender, subject, "received")
                
        except Exception as e:
            logger.error(f"Error in smart email processing: {e}")
        finally:
            if 'client' in locals():
                client.close()

    async def _notify_email_action(self, sender: str, subject: str, action: str):
        """Notify user about email action taken.
        
        Args:
            sender: Sender email address
            subject: Email subject
            action: Action taken (archived, deleted, received)
        """
        try:
            if action == "archived":
                message = f"I archived an email from {sender} with subject '{subject}'"
            elif action == "deleted":
                message = f"I deleted an email from {sender} with subject '{subject}'"
            else:
                message = f"Received email from {sender}: {subject}"
            
            # Send notification via email
            if self.messaging_handler and self.messaging_handler.gmail_handler:
                await self.send_console_message(message, "notification")
        except Exception as e:
            logger.error(f"Error notifying email action: {e}")

    async def _create_draft_and_notify(self, sender: str, subject: str, body: str):
        """Create a draft email and notify user for approval.
        
        Args:
            sender: Sender email address
            subject: Original email subject
            body: Original email body
        """
        try:
            import uuid
            draft_id = str(uuid.uuid4())
            
            # Use AI to generate a reply
            reply_body = await self._generate_reply_draft(sender, subject, body)
            
            # Create draft using Gmail API (or store in database)
            gmail_draft_id = await self.create_draft(
                to_email=sender,
                subject=f"Re: {subject}",
                body=reply_body
            )
            
            # Store draft in database
            self.db.add_email_draft(
                draft_id=draft_id,
                gmail_draft_id=gmail_draft_id,
                recipient_email=sender,
                subject=f"Re: {subject}",
                body=reply_body
            )
            
            # Send notification via email and SMS
            notification_body = f"""I've created a draft email for you:

To: {sender}
Subject: Re: {subject}

{reply_body[:200]}...

Options:
- Reply "yes" or "send" to send the draft
- Reply "review" to see the full draft
- Reply "delete" to delete the draft"""
            
            # Send email notification
            await self.send_console_message(notification_body, "confirmation_request")
            
            # Send SMS notification if messaging handler available
            if self.messaging_handler:
                self.messaging_handler.send_message(
                    to_number=Config.TARGET_PHONE_NUMBER,
                    message_body=f"TARS created a draft reply to {sender}. Check your email for details.",
                    medium='sms'
                )
                
        except Exception as e:
            logger.error(f"Error creating draft and notifying: {e}")

    async def _generate_reply_draft(self, sender: str, subject: str, body: str) -> str:
        """Generate a draft reply using AI.
        
        Args:
            sender: Sender email address
            subject: Original email subject
            body: Original email body
            
        Returns:
            Draft reply text
        """
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(
                http_options={"api_version": "v1beta"},
                api_key=Config.GEMINI_API_KEY
            )
            
            prompt = f"""Write a professional email reply to this message:

From: {sender}
Subject: {subject}
Body: {body}

Write a concise, professional reply in the user's name. Keep it brief and appropriate."""
            
            response = await client.aio.models.generate_content(
                model="models/gemini-2.0-flash-exp",
                contents=[types.Content(parts=[types.Part(text=prompt)], role="user")],
                config=types.GenerateContentConfig(temperature=0.7)
            )
            
            if response.candidates and response.candidates[0].content.parts:
                return response.candidates[0].content.parts[0].text.strip()
            
            return "Thank you for your email. I will get back to you soon."
        except Exception as e:
            logger.error(f"Error generating reply draft: {e}")
            return "Thank you for your email. I will get back to you soon."
        finally:
            if 'client' in locals():
                client.close()

    def archive_email(self, message_id: str) -> bool:
        """Archive an email by message ID using IMAP.
        
        Args:
            message_id: IMAP message ID (sequence number)
            
        Returns:
            True if successful
        """
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self.email_user, self.email_pass)
            mail.select("inbox")
            
            # Move email to Archive folder
            mail.store(message_id, '+X-GM-LABELS', '\\Archived')
            mail.expunge()
            mail.logout()
            
            logger.info(f"Archived email {message_id}")
            return True
        except Exception as e:
            logger.error(f"Error archiving email: {e}")
            return False

    def delete_email(self, message_id: str) -> bool:
        """Delete an email by message ID using IMAP.
        
        Args:
            message_id: IMAP message ID (sequence number)
            
        Returns:
            True if successful
        """
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self.email_user, self.email_pass)
            mail.select("inbox")
            
            # Mark as deleted and expunge
            mail.store(message_id, '+FLAGS', '\\Deleted')
            mail.expunge()
            mail.logout()
            
            logger.info(f"Deleted email {message_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting email: {e}")
            return False

    async def create_draft(self, to_email: str, subject: str, body: str) -> Optional[str]:
        """Create a draft email using Gmail API.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body
            
        Returns:
            Gmail draft ID or None if failed
        """
        try:
            # For now, we'll use IMAP to create a draft
            # In the future, this could use Gmail API for better integration
            msg = MIMEMultipart()
            msg['From'] = f"TARS <{self.email_user}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            # Use IMAP to append as draft
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self.email_user, self.email_pass)
            mail.select("[Gmail]/Drafts")
            
            # Append message as draft
            mail.append("[Gmail]/Drafts", None, None, msg.as_bytes())
            mail.logout()
            
            logger.info(f"Created draft email to {to_email}")
            # Return a placeholder ID (in production, use Gmail API to get real draft ID)
            return f"draft_{datetime.now().timestamp()}"
        except Exception as e:
            logger.error(f"Error creating draft: {e}")
            return None

    def list_emails(self, folder: str = "inbox", query: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """List emails from specified folder with optional search query.
        
        Args:
            folder: Folder name ("inbox", "archived", "all")
            query: Optional IMAP search query
            limit: Maximum number of results
            
        Returns:
            List of email dicts with id, subject, sender, date
        """
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self.email_user, self.email_pass)
            
            # Map folder names to IMAP folder names
            folder_map = {
                "inbox": "inbox",
                "archived": "[Gmail]/All Mail",
                "all": "[Gmail]/All Mail"
            }
            imap_folder = folder_map.get(folder.lower(), "inbox")
            mail.select(imap_folder)
            
            # Build search query
            if query:
                # Support basic IMAP search syntax
                if query.startswith("from:"):
                    search_query = f'(FROM "{query[5:]}")'
                elif query.startswith("subject:"):
                    search_query = f'(SUBJECT "{query[8:]}")'
                else:
                    search_query = f'(TEXT "{query}")'
            else:
                search_query = 'ALL'
            
            status, messages = mail.search(None, search_query)
            
            if status != "OK" or not messages[0]:
                mail.logout()
                return []
            
            email_ids = messages[0].split()[-limit:]  # Get last N emails
            emails = []
            
            for num in reversed(email_ids):  # Most recent first
                try:
                    status, msg_data = mail.fetch(num, "(RFC822)")
                    if status != "OK":
                        continue
                    
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    sender = email.utils.parseaddr(msg['From'])[1]
                    subject = msg['Subject'] or "(No Subject)"
                    date = msg['Date']
                    
                    emails.append({
                        'id': num.decode('utf-8'),
                        'subject': subject,
                        'sender': sender,
                        'date': date
                    })
                except Exception as e:
                    logger.warning(f"Error fetching email {num}: {e}")
                    continue
            
            mail.logout()
            return emails
        except Exception as e:
            logger.error(f"Error listing emails: {e}")
            return []

    async def search_emails_by_criteria(self, folder: str, criteria: str, limit: int = 50) -> List[Dict]:
        """Search emails by AI-determined criteria.
        
        Args:
            folder: Folder name ("inbox", "archived", "all")
            criteria: Search criteria (e.g., "advertisement", "promotional")
            limit: Maximum number of results
            
        Returns:
            List of matching email dicts
        """
        # Get emails from folder
        emails = self.list_emails(folder, limit=limit * 2)
        
        # Categorize each email and filter by criteria
        categorized = []
        for email_data in emails:
            category = await self.categorize_email(
                email_data.get('subject', '') + " " + email_data.get('sender', '')
            )
            if category and criteria.lower() in category.lower():
                categorized.append(email_data)
                if len(categorized) >= limit:
                    break
        
        return categorized

    async def categorize_email(self, email_content: str) -> str:
        """Use AI to classify email category.
        
        Args:
            email_content: Email subject and/or body text
            
        Returns:
            Category: "advertisement", "promotional", "spam", "important", "newsletter", "notification"
        """
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(
                http_options={"api_version": "v1beta"},
                api_key=Config.GEMINI_API_KEY
            )
            
            prompt = f"""Categorize this email content into one of these categories:
- advertisement: Promotional emails, marketing
- promotional: Sales, deals, offers
- spam: Obvious spam/junk
- important: Personal, work-related, urgent
- newsletter: Subscriptions, updates
- notification: System notifications, receipts

Email content: {email_content[:300]}

Respond with only the category name."""
            
            response = await client.aio.models.generate_content(
                model="models/gemini-2.0-flash-exp",
                contents=[types.Content(parts=[types.Part(text=prompt)], role="user")],
                config=types.GenerateContentConfig(temperature=0.3)
            )
            
            if response.candidates and response.candidates[0].content.parts:
                category = response.candidates[0].content.parts[0].text.strip().lower()
                # Map to standard categories
                if "advertisement" in category or "ad" in category:
                    return "advertisement"
                elif "promotional" in category or "promo" in category:
                    return "promotional"
                elif "spam" in category:
                    return "spam"
                elif "important" in category or "urgent" in category:
                    return "important"
                elif "newsletter" in category:
                    return "newsletter"
                elif "notification" in category:
                    return "notification"
                return category
            
            return "unknown"
        except Exception as e:
            logger.error(f"Error categorizing email: {e}")
            return "unknown"
        finally:
            if 'client' in locals():
                client.close()

    def bulk_delete_emails(self, email_ids: List[str]) -> Dict[str, int]:
        """Delete multiple emails by their IDs.
        
        Args:
            email_ids: List of email message IDs
            
        Returns:
            Dict with 'deleted' count and 'failed' count
        """
        deleted = 0
        failed = 0
        
        for email_id in email_ids:
            if self.delete_email(email_id):
                deleted += 1
            else:
                failed += 1
        
        logger.info(f"Bulk deleted {deleted} emails, {failed} failed")
        return {'deleted': deleted, 'failed': failed}

    def bulk_archive_emails(self, email_ids: List[str]) -> Dict[str, int]:
        """Archive multiple emails by their IDs.
        
        Args:
            email_ids: List of email message IDs
            
        Returns:
            Dict with 'archived' count and 'failed' count
        """
        archived = 0
        failed = 0
        
        for email_id in email_ids:
            if self.archive_email(email_id):
                archived += 1
            else:
                failed += 1
        
        logger.info(f"Bulk archived {archived} emails, {failed} failed")
        return {'archived': archived, 'failed': failed}
