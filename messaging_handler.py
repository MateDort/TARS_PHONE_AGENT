"""Messaging handler for Twilio (phone calls only - all messaging moved to N8N)."""
import logging
from typing import Optional
from twilio.rest import Client
from config import Config
from database import Database

logger = logging.getLogger(__name__)


class MessagingHandler:
    """Handles Twilio client for phone calls (messaging moved to N8N)."""

    def __init__(self, database: Database, twilio_client: Client, session_manager=None, router=None, twilio_handler=None):
        """Initialize messaging handler (Twilio-only, for phone calls).

        Args:
            database: Database instance for conversation logging
            twilio_client: Twilio Client instance
            session_manager: SessionManager instance
            router: MessageRouter instance
            twilio_handler: TwilioMediaStreamsHandler instance
        """
        self.db = database
        self.twilio_client = twilio_client
        self.session_manager = session_manager
        self.router = router
        self.twilio_handler = twilio_handler

        logger.info("MessagingHandler initialized (Twilio-only)")

    async def process_incoming_message(self, from_number: str, message_body: str,
                                       medium: str = 'sms', message_sid: str = None, to_number: str = None):
        """Process incoming SMS/WhatsApp message (deprecated - all messaging moved to N8N).

        This method is kept for compatibility but routes to N8N.
        Args:
            from_number: Sender's phone number
            message_body: Message text
            medium: 'sms' or 'whatsapp'
            message_sid: Twilio message SID
            to_number: The number the message was sent to (bot's number)
        """
        logger.warning(f"process_incoming_message called but messaging moved to N8N. Message from {from_number}: {message_body[:50]}")
        # Route to N8N via send_to_n8n
        from sub_agents_tars import N8NAgent
        n8n_agent = N8NAgent()
        message = f"Received {medium} from {from_number}: {message_body}"
        return await n8n_agent.execute({"message": message})

    def send_message(self, to_number: str, message_body: str, medium: str = 'sms', from_number: str = None, url: str = None) -> Optional[str]:
        """Send message (deprecated - use send_to_n8n instead).
        
        This method is kept for compatibility but should not be used.
        All messaging has been moved to N8N.
        """
        logger.warning("send_message called but messaging moved to N8N. Use send_to_n8n instead.")
        return None

    def send_email(self, to_email: str, subject: str, body: str) -> Optional[str]:
        """Send email (deprecated - use send_to_n8n instead).
        
        This method is kept for compatibility but should not be used.
        All email has been moved to N8N.
        """
        logger.warning("send_email called but email moved to N8N. Use send_to_n8n instead.")
        return None

    def send_link(self, to_number: str, url: str, description: str = '', medium: str = 'sms') -> Optional[str]:
        """Send link (deprecated - use send_to_n8n instead).
        
        This method is kept for compatibility but should not be used.
        All messaging has been moved to N8N.
        """
        logger.warning("send_link called but messaging moved to N8N. Use send_to_n8n instead.")
        return None
