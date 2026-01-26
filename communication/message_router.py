"""Message Router - Central hub for routing messages between agent sessions."""
import logging
import asyncio
import uuid
from typing import Dict, List, Optional, Union
from datetime import datetime

from core.agent_session import AgentSession
from core.config import Config

logger = logging.getLogger(__name__)


class MessageRouter:
    """Central hub for routing messages between sessions.

    Handles:
    - Direct messages to specific sessions
    - Broadcast messages to multiple sessions
    - Routing to user (Máté) with fallback to SMS/call
    - Message delivery tracking and failure handling
    - Background message processing queue
    """

    def __init__(self, session_manager, messaging_handler, db):
        """Initialize Message Router.

        Args:
            session_manager: SessionManager instance
            messaging_handler: MessagingHandler for SMS/WhatsApp
            db: Database instance for message logging
        """
        self.session_manager = session_manager
        self.messaging_handler = messaging_handler
        self.db = db

        # Message queue for async processing
        self.message_queue = asyncio.Queue()
        self.running = False

        # Delivery tracking
        self._delivery_tasks: Dict[str, asyncio.Task] = {}

        # Registered sessions
        self._registered_sessions: Dict[str, AgentSession] = {}

        logger.info("MessageRouter initialized")

    async def start(self):
        """Start router background processing loop"""
        if self.running:
            logger.warning("MessageRouter already running")
            return

        self.running = True
        asyncio.create_task(self._process_messages())
        logger.info("MessageRouter started")

    async def stop(self):
        """Stop router background processing"""
        self.running = False
        logger.info("MessageRouter stopped")

    async def register_session(self, session: AgentSession):
        """Register a new session with the router.

        Args:
            session: AgentSession to register
        """
        self._registered_sessions[session.session_id] = session
        logger.info(
            f"Registered session {session.session_id[:8]}: {session.session_name}"
        )

    async def unregister_session(self, session: AgentSession):
        """Unregister a session (when call ends).

        Args:
            session: AgentSession to unregister
        """
        if session.session_id in self._registered_sessions:
            del self._registered_sessions[session.session_id]
            logger.info(
                f"Unregistered session {session.session_id[:8]}: {session.session_name}"
            )

    async def route_message(
        self,
        from_session: Optional[AgentSession],
        message: str,
        target: Union[str, List[str]],
        message_type: str = "direct",
        context: Optional[Dict] = None
    ) -> str:
        """Route a message from one session to another or to user.

        Args:
            from_session: Source session (None for system messages)
            message: Message text to send
            target: Target session name, "user", or list of session names
            message_type: "direct", "confirmation_request", "update", "reminder", "notification"
            context: Optional context dict

        Returns:
            Message ID for tracking
        """
        message_id = str(uuid.uuid4())

        # Build message dict
        msg = {
            'message_id': message_id,
            'from_session': from_session,
            'from_session_id': from_session.session_id if from_session else None,
            'from_name': from_session.session_name if from_session else "System",
            'message': message,
            'target': target,
            'message_type': message_type,
            'context': context or {},
            'timestamp': datetime.now()
        }

        # Add to queue for async processing
        await self.message_queue.put(msg)

        logger.info(
            f"Queued message {message_id[:8]} from {msg['from_name']} to {target}"
        )

        return message_id

    async def _process_messages(self):
        """Background loop to process message queue"""
        logger.info("Message processing loop started")

        while self.running:
            try:
                # Get message from queue (wait up to 1 second)
                try:
                    msg = await asyncio.wait_for(
                        self.message_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Process message
                await self._route_message_internal(msg)

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)

        logger.info("Message processing loop stopped")

    async def _route_message_internal(self, msg: Dict):
        """Internal routing implementation.

        Args:
            msg: Message dict from queue
        """
        target = msg['target']
        message_id = msg['message_id']

        try:
            # Case 1: Direct to user (Máté)
            if target == "user":
                await self._route_to_user(msg)

            # Case 2: Named session (e.g., "Máté (main)", "Call with Barber Shop")
            elif isinstance(target, str):
                await self._route_to_named_session(msg)

            # Case 3: Broadcast to multiple sessions
            elif isinstance(target, list):
                await self._broadcast_to_sessions(msg)

            else:
                logger.error(f"Invalid target type: {type(target)}")

        except Exception as e:
            logger.error(
                f"Error routing message {message_id[:8]}: {e}", exc_info=True)
            await self._handle_delivery_failure(msg, e)

    async def _route_to_user(self, msg: Dict):
        """Route message to user (Máté).

        Tries to deliver to active main session first, falls back to SMS/call.

        Args:
            msg: Message dict
        """
        # Try to find Máté's active main session
        mate_session = await self.session_manager.get_mate_main_session()

        if mate_session and mate_session.is_active():
            # User is in active call - announce in call
            logger.info(
                f"Delivering message {msg['message_id'][:8]} to active Máté session"
            )
            await self._deliver_to_session(mate_session, msg)
        else:
            # User not in call - use fallback (SMS/call)
            logger.info(
                f"Máté not in active call, using fallback for message {msg['message_id'][:8]}"
            )
            await self._fallback_to_user(msg)

    async def _route_to_named_session(self, msg: Dict):
        """Route message to a specific named session.

        Args:
            msg: Message dict
        """
        target_name = msg['target']

        # Try to find target session by name
        target_session = await self.session_manager.get_session_by_name(target_name)

        if target_session and target_session.is_active():
            # Session found and active - deliver
            await self._deliver_to_session(target_session, msg)
        else:
            # Session not found or not active
            logger.warning(
                f"Target session '{target_name}' not found or not active for "
                f"message {msg['message_id'][:8]}"
            )
            await self._fallback_session_not_found(msg)

    async def _broadcast_to_sessions(self, msg: Dict):
        """Broadcast message to multiple sessions.

        Args:
            msg: Message dict with target as list of session names
        """
        target_sessions = msg['target']
        delivery_tasks = []

        for session_name in target_sessions:
            session = await self.session_manager.get_session_by_name(session_name)
            if session and session.is_active():
                delivery_tasks.append(self._deliver_to_session(session, msg))
            else:
                logger.warning(
                    f"Broadcast target '{session_name}' not found or not active")

        if delivery_tasks:
            # Deliver to all targets concurrently
            results = await asyncio.gather(*delivery_tasks, return_exceptions=True)

            # Log any failures
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Broadcast delivery failed to {target_sessions[i]}: {result}"
                    )

    async def _deliver_to_session(self, target_session: AgentSession, msg: Dict):
        """Deliver message to a specific session's Gemini client.

        Args:
            target_session: Target session
            msg: Message dict
        """
        from_name = msg['from_name']
        message_body = msg['message']
        message_type = msg['message_type']

        # Format message for AI announcement based on type
        if message_type == "confirmation_request":
            announcement = (
                f"[INTER-AGENT MESSAGE] {from_name} is asking: {message_body}. "
                f"Please respond yes/no or provide guidance."
            )
        elif message_type == "reminder":
            announcement = f"[REMINDER] {message_body}"
        elif message_type == "notification":
            announcement = f"[NOTIFICATION] {message_body}"
        elif message_type == "update":
            announcement = f"[UPDATE] {from_name}: {message_body}"
        elif message_type == "broadcast":
            announcement = f"[BROADCAST] {from_name}: {message_body}"
        elif message_type == "call_completion_report":
            announcement = f"[CALL REPORT] {message_body}"
        elif message_type == "broadcast_approval_request":
            announcement = f"[APPROVAL NEEDED] {message_body}"
        else:  # direct
            announcement = f"[INTER-AGENT MESSAGE] {from_name} says: {message_body}"

        try:
            # Send to Gemini client with timeout
            await asyncio.wait_for(
                target_session.gemini_client.send_text(
                    announcement, end_of_turn=True),
                timeout=10.0
            )

            # Log successful delivery to database
            self.db.add_inter_session_message(
                message_id=msg['message_id'],
                from_session_id=msg['from_session_id'],
                to_session_id=target_session.session_id,
                to_session_name=target_session.session_name,
                message_type=message_type,
                message_body=message_body,
                context=str(msg['context']),
                status='delivered'
            )

            logger.info(
                f"Delivered message {msg['message_id'][:8]} to "
                f"{target_session.session_name}"
            )

        except asyncio.TimeoutError:
            logger.error(
                f"Timeout delivering message {msg['message_id'][:8]} to "
                f"{target_session.session_name}"
            )
            raise

        except Exception as e:
            logger.error(
                f"Error delivering message {msg['message_id'][:8]} to "
                f"{target_session.session_name}: {e}"
            )
            raise

    async def _fallback_to_user(self, msg: Dict):
        """Fallback when user not in active call - send via SMS or make call.

        Args:
            msg: Message dict
        """
        from_name = msg['from_name']
        message_body = msg['message']
        message_type = msg['message_type']

        # Get callback method from config
        callback_method = getattr(Config, 'CALLBACK_REPORT', 'message').lower()

        # Send via message (SMS) or email - route through KIPP
        if callback_method in ['message', 'email', 'both']:
            try:
                from sub_agents_tars import KIPPAgent
                n8n_agent = KIPPAgent()
                
                # Format message based on type
                if message_type == "reminder":
                    formatted_message = f"⏰ Reminder: {message_body}"
                elif message_type == "notification":
                    formatted_message = f"📢 {message_body}"
                elif message_type == "call_completion_report":
                    formatted_message = f"📞 Call Report:\n\n{message_body}"
                else:
                    formatted_message = f"Message from {from_name}:\n\n{message_body}"
                
                # Build KIPP request based on delivery method
                if callback_method == 'message':
                    n8n_message = f"Send SMS to {Config.TARGET_PHONE_NUMBER}: {formatted_message}"
                elif callback_method == 'email':
                    subject = f"TARS {message_type.title()}" if message_type != "direct" else f"Message from {from_name}"
                    n8n_message = f"Send email to {Config.TARGET_EMAIL} with subject '{subject}' and body '{formatted_message}'"
                else:  # both
                    subject = f"TARS {message_type.title()}" if message_type != "direct" else f"Message from {from_name}"
                    n8n_message = f"Send SMS to {Config.TARGET_PHONE_NUMBER} and email to {Config.TARGET_EMAIL} with subject '{subject}': {formatted_message}"
                
                await n8n_agent.execute({"message": n8n_message})
                logger.info(
                    f"Sent fallback via KIPP for message {msg['message_id'][:8]} (method: {callback_method})"
                )

            except Exception as e:
                logger.error(f"Failed to send fallback via KIPP: {e}")

        # Send via call
        if callback_method in ['call', 'both']:
            try:
                # This will be implemented when we integrate with twilio_handler
                # For now, just log
                logger.info(
                    f"Would make callback call for message {msg['message_id'][:8]}: "
                    f"{message_body[:50]}..."
                )
            except Exception as e:
                logger.error(f"Failed to make fallback call: {e}")

        # Log fallback delivery
        self.db.add_inter_session_message(
            message_id=msg['message_id'],
            from_session_id=msg['from_session_id'],
            to_session_id=None,
            to_session_name="user_fallback",
            message_type=message_type,
            message_body=message_body,
            context=str(msg['context']),
            status='delivered_via_fallback'
        )

    async def _fallback_session_not_found(self, msg: Dict):
        """Handle case where target session doesn't exist.

        Args:
            msg: Message dict
        """
        target_name = msg['target']
        from_session = msg['from_session']

        # Notify sender session that target not found
        if from_session and from_session.is_active():
            error_msg = (
                f"[DELIVERY FAILED] Could not deliver your message to '{target_name}' - "
                f"that session is not currently active. I'll notify Máté via SMS instead."
            )
            try:
                await from_session.gemini_client.send_text(error_msg, end_of_turn=True)
            except Exception as e:
                logger.error(
                    f"Failed to notify sender of delivery failure: {e}")

        # Fallback: notify user via SMS
        notification = (
            f"Message from {msg['from_name']} could not be delivered to "
            f"'{target_name}' (session not active):\n\n{msg['message']}"
        )

        # Create a new message dict for the notification to avoid ID collision
        notification_msg = msg.copy()
        notification_msg['message_id'] = str(uuid.uuid4())
        notification_msg['message'] = notification
        notification_msg['message_type'] = 'notification'

        await self._fallback_to_user(notification_msg)

        # Log failed delivery
        self.db.add_inter_session_message(
            message_id=msg['message_id'],
            from_session_id=msg['from_session_id'],
            to_session_id=None,
            to_session_name=target_name,
            message_type=msg['message_type'],
            message_body=msg['message'],
            context=str(msg['context']),
            status='failed_target_not_found'
        )

    async def _handle_delivery_failure(self, msg: Dict, error: Exception):
        """Handle message delivery failure.

        Args:
            msg: Message dict
            error: Exception that occurred
        """
        logger.error(
            f"Failed to deliver message {msg['message_id'][:8]}: {error}",
            exc_info=True
        )

        # Notify sender session
        from_session = msg['from_session']
        if from_session and from_session.is_active():
            error_msg = (
                f"[SYSTEM ERROR] Failed to deliver your message to {msg['target']}: "
                f"{str(error)}"
            )
            try:
                await from_session.gemini_client.send_text(error_msg, end_of_turn=True)
            except Exception as e:
                logger.error(f"Failed to notify sender of delivery error: {e}")

        # Log failure to database
        self.db.add_inter_session_message(
            message_id=msg['message_id'],
            from_session_id=msg['from_session_id'],
            to_session_id=None,
            to_session_name=str(msg['target']),
            message_type=msg['message_type'],
            message_body=msg['message'],
            context=str(msg['context']),
            status='failed',
            error_message=str(error)
        )

    async def get_message_status(self, message_id: str) -> Optional[Dict]:
        """Get delivery status of a message.

        Args:
            message_id: Message ID to query

        Returns:
            Message status dict from database, or None if not found
        """
        return self.db.get_inter_session_message(message_id)

    def get_stats(self) -> Dict:
        """Get router statistics.

        Returns:
            Dict with message counts and queue info
        """
        return {
            'running': self.running,
            'queue_size': self.message_queue.qsize(),
            'registered_sessions': len(self._registered_sessions),
            'active_delivery_tasks': len(self._delivery_tasks)
        }
