"""Messaging platform abstraction layer for easy SMS/Gmail/WhatsApp switching."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class MessagingPlatform(ABC):
    """Abstract base class for messaging platforms"""

    @abstractmethod
    async def send_message(self, to: str, body: str, subject: str = None,
                          thread_id: str = None) -> Optional[str]:
        """Send a message. Returns message ID or None if failed."""
        pass

    @abstractmethod
    async def poll_messages(self) -> List[Dict]:
        """Check for new messages. Returns list of message dicts."""
        pass

    @abstractmethod
    async def start_polling(self):
        """Start background polling loop."""
        pass

    @abstractmethod
    def stop_polling(self):
        """Stop polling loop."""
        pass

    @abstractmethod
    def get_platform_name(self) -> str:
        """Return platform name (gmail, sms, whatsapp)."""
        pass


class GmailPlatform(MessagingPlatform):
    """Gmail implementation of messaging platform"""

    def __init__(self, gmail_handler):
        self.handler = gmail_handler

    async def send_message(self, to: str, body: str, subject: str = None,
                          thread_id: str = None) -> Optional[str]:
        """Send email"""
        result = await self.handler._send_threaded_email(
            to_email=to,
            subject=subject or "Message from TARS",
            body=body,
            message_type='notification'
        )
        return str(result) if result else None

    async def poll_messages(self) -> List[Dict]:
        """Check Gmail for new messages"""
        # Delegate to GmailHandler
        return await self.handler.check_messages()

    async def start_polling(self):
        await self.handler.start_polling()

    def stop_polling(self):
        self.handler.stop()

    def get_platform_name(self) -> str:
        return "gmail"


class SMSPlatform(MessagingPlatform):
    """SMS implementation (via Twilio) - FUTURE"""

    def __init__(self, twilio_client, from_number):
        self.client = twilio_client
        self.from_number = from_number

    async def send_message(self, to: str, body: str, subject: str = None,
                          thread_id: str = None) -> Optional[str]:
        """Send SMS (subject ignored for SMS)"""
        message = self.client.messages.create(
            body=body,
            from_=self.from_number,
            to=to
        )
        return message.sid

    async def poll_messages(self) -> List[Dict]:
        """SMS uses webhooks, not polling"""
        return []

    async def start_polling(self):
        """SMS doesn't need polling (webhook-based)"""
        logger.info("SMS platform uses webhooks, no polling needed")

    def stop_polling(self):
        pass

    def get_platform_name(self) -> str:
        return "sms"


def create_messaging_platform(platform_type: str, **kwargs) -> MessagingPlatform:
    """Factory function to create messaging platform"""
    if platform_type == "gmail":
        return GmailPlatform(kwargs['gmail_handler'])
    elif platform_type == "sms":
        return SMSPlatform(kwargs['twilio_client'], kwargs['from_number'])
    elif platform_type == "whatsapp":
        # Future: WhatsAppPlatform
        raise NotImplementedError("WhatsApp platform not yet implemented")
    else:
        raise ValueError(f"Unknown platform type: {platform_type}")
