"""Session Manager - Central registry for all active agent sessions."""
import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from agent_session import (
    AgentSession,
    SessionStatus,
    SessionType,
    PermissionLevel,
    generate_session_id
)
from security import authenticate_phone_number, filter_functions_by_permission, get_limited_system_instruction
from config import Config

logger = logging.getLogger(__name__)


class SessionManager:
    """Central registry for all active Gemini Live sessions.

    Manages session lifecycle:
    - Creation with phone number authentication
    - Session naming (Máté main vs contacts vs unknown)
    - Permission filtering
    - Lookup by various keys (session_id, call_sid, phone_number)
    - Termination and cleanup
    """

    def __init__(self, db, router=None):
        """Initialize Session Manager.

        Args:
            db: Database instance for persistence
            router: Optional MessageRouter for inter-agent communication
        """
        self.db = db
        self.router = router  # Will be set after router is created

        # Session registries
        self.sessions: Dict[str, AgentSession] = {}  # session_id -> AgentSession
        self.call_sid_to_session: Dict[str, str] = {}  # call_sid -> session_id
        self.phone_to_sessions: Dict[str, List[str]] = {}  # phone -> [session_ids]

        # Thread-safe lock for concurrent access
        self._lock = asyncio.Lock()

        logger.info("SessionManager initialized")

    def set_router(self, router):
        """Set message router after initialization (circular dependency workaround)"""
        self.router = router
        logger.info("SessionManager connected to MessageRouter")

    async def create_session(
        self,
        call_sid: str,
        phone_number: str,
        websocket,
        stream_sid: str,
        purpose: Optional[str] = None,
        parent_session_id: Optional[str] = None
    ) -> AgentSession:
        """Create a new agent session for an incoming/outbound call.

        Handles:
        - Phone number authentication
        - Session naming
        - Permission filtering
        - GeminiLiveClient creation
        - Database persistence
        - Router registration

        Args:
            call_sid: Twilio Call SID
            phone_number: Caller's phone number
            websocket: Twilio Media Stream WebSocket
            stream_sid: Twilio Stream SID
            purpose: Optional goal description for outbound calls
            parent_session_id: Optional parent session ID (for spawned calls)

        Returns:
            Created AgentSession instance
        """
        async with self._lock:
            # Generate unique session ID
            session_id = generate_session_id()

            # Authenticate phone number
            permission_level = authenticate_phone_number(phone_number)

            # Determine session name and type
            session_name, session_type = await self._determine_session_identity(
                phone_number,
                permission_level,
                purpose
            )

            # Create dedicated GeminiLiveClient with filtered functions
            gemini_client = await self._create_gemini_client(permission_level)

            # Create session object
            session = AgentSession(
                session_id=session_id,
                call_sid=call_sid,
                session_name=session_name,
                phone_number=phone_number,
                permission_level=permission_level,
                session_type=session_type,
                gemini_client=gemini_client,
                websocket=websocket,
                stream_sid=stream_sid,
                purpose=purpose,
                parent_session_id=parent_session_id
            )

            # Register session
            self.sessions[session_id] = session
            self.call_sid_to_session[call_sid] = session_id

            # Track by phone number
            if phone_number not in self.phone_to_sessions:
                self.phone_to_sessions[phone_number] = []
            self.phone_to_sessions[phone_number].append(session_id)

            # Persist to database
            self.db.add_agent_session(session.to_dict())

            # Register with router (if available)
            if self.router:
                await self.router.register_session(session)

            logger.info(
                f"Created session {session_id[:8]}: {session_name} "
                f"({permission_level.value}, type={session_type.value})"
            )

            return session

    async def _determine_session_identity(
        self,
        phone_number: str,
        permission_level: PermissionLevel,
        purpose: Optional[str]
    ) -> tuple[str, SessionType]:
        """Determine session name and type based on caller information.

        Args:
            phone_number: Caller's phone number
            permission_level: FULL or LIMITED
            purpose: Optional goal description

        Returns:
            Tuple of (session_name, session_type)
        """
        if permission_level == PermissionLevel.FULL:
            # This is Máté - check if already has main session
            mate_main = await self.get_mate_main_session()

            if mate_main and mate_main.is_active():
                # Already has main session - this is a secondary one
                import uuid
                suffix = uuid.uuid4().hex[:4]
                session_name = f"Call with Máté ({suffix})"
            else:
                # First Máté session - this is the main one
                session_name = "Call with Máté (main)"

            if purpose:
                session_type = SessionType.OUTBOUND_GOAL
            else:
                session_type = SessionType.INBOUND_USER

        else:
            # Unknown caller - LIMITED access
            # Try to look up in contacts
            contact = self.db.search_contact_by_phone(phone_number)

            if contact:
                session_name = f"Call with {contact['name']}"
            else:
                session_name = f"Call with {phone_number}"

            session_type = SessionType.INBOUND_UNKNOWN

        return session_name, session_type

    async def _create_gemini_client(self, permission_level: PermissionLevel):
        """Create GeminiLiveClient with permission-filtered functions.

        Args:
            permission_level: FULL or LIMITED

        Returns:
            Configured GeminiLiveClient instance
        """
        from gemini_live_client import GeminiLiveClient
        from sub_agents_tars import get_function_declarations

        # Get all function declarations
        all_functions = get_function_declarations()

        # Filter based on permission
        filtered_functions = filter_functions_by_permission(
            permission_level,
            all_functions
        )

        # Get system instruction
        if permission_level == PermissionLevel.FULL:
            # Use standard system instruction from config
            from personality import get_personality_prompt
            system_instruction = get_personality_prompt()
        else:
            # Add LIMITED access constraints
            from personality import get_personality_prompt
            base_instruction = get_personality_prompt()
            security_instruction = get_limited_system_instruction()
            system_instruction = base_instruction + "\n\n" + security_instruction

        # Create client
        client = GeminiLiveClient(
            api_key=Config.GEMINI_API_KEY,
            system_instruction=system_instruction
        )

        # Set filtered function declarations
        client.function_declarations = filtered_functions

        # Note: function handlers will be set by the main initialization code
        # We only filter declarations here, not handlers

        return client

    async def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Get session by session ID.

        Args:
            session_id: Session UUID

        Returns:
            AgentSession if found, None otherwise
        """
        return self.sessions.get(session_id)

    async def get_session_by_call_sid(self, call_sid: str) -> Optional[AgentSession]:
        """Get session by Twilio Call SID.

        Args:
            call_sid: Twilio Call SID

        Returns:
            AgentSession if found, None otherwise
        """
        session_id = self.call_sid_to_session.get(call_sid)
        if session_id:
            return self.sessions.get(session_id)
        return None

    async def get_mate_main_session(self) -> Optional[AgentSession]:
        """Get Máté's active main session (if any).

        Returns:
            AgentSession for "Call with Máté (main)" if active, None otherwise
        """
        for session in self.sessions.values():
            if (
                session.session_name == "Call with Máté (main)"
                and session.is_active()
            ):
                return session
        return None

    async def get_sessions_for_phone(self, phone_number: str) -> List[AgentSession]:
        """Get all sessions (active or completed) for a phone number.

        Args:
            phone_number: Phone number to query

        Returns:
            List of AgentSession instances
        """
        session_ids = self.phone_to_sessions.get(phone_number, [])
        return [self.sessions[sid] for sid in session_ids if sid in self.sessions]

    async def get_active_sessions(self) -> List[AgentSession]:
        """Get all currently active sessions.

        Returns:
            List of active AgentSession instances
        """
        return [
            session for session in self.sessions.values()
            if session.is_active()
        ]

    async def get_active_session_count(self) -> int:
        """Get count of currently active sessions.

        Returns:
            Number of active sessions
        """
        active_sessions = await self.get_active_sessions()
        return len(active_sessions)

    async def get_session_by_name(self, session_name: str) -> Optional[AgentSession]:
        """Get session by name (for inter-agent messaging).

        Args:
            session_name: Session name to search for

        Returns:
            AgentSession if found and active, None otherwise
        """
        for session in self.sessions.values():
            if session.session_name == session_name and session.is_active():
                return session
        return None

    async def terminate_session(self, session_id: str, reason: str = "completed"):
        """Terminate a session and perform cleanup.

        Args:
            session_id: Session UUID to terminate
            reason: Reason for termination ("completed", "failed", "disconnected")
        """
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                logger.warning(f"Attempted to terminate unknown session {session_id[:8]}")
                return

            # Mark session as completed or failed
            if reason == "failed":
                session.fail(reason)
            else:
                session.complete()

            # Update database
            self.db.complete_session(session_id, completed_at=datetime.now())

            # Unregister from router
            if self.router:
                await self.router.unregister_session(session)

            # Cleanup Gemini client
            try:
                await session.gemini_client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting Gemini client: {e}")

            logger.info(
                f"Terminated session {session_id[:8]}: {session.session_name} "
                f"(reason: {reason})"
            )

    async def terminate_session_by_call_sid(self, call_sid: str, reason: str = "completed"):
        """Terminate session by Twilio Call SID.

        Args:
            call_sid: Twilio Call SID
            reason: Reason for termination
        """
        session_id = self.call_sid_to_session.get(call_sid)
        if session_id:
            await self.terminate_session(session_id, reason)
        else:
            logger.warning(f"Attempted to terminate session with unknown call_sid {call_sid}")

    async def broadcast_to_sessions(
        self,
        session_ids: List[str],
        message: Dict
    ):
        """Broadcast a message to multiple sessions (helper for router).

        Args:
            session_ids: List of session IDs to broadcast to
            message: Message dict to send
        """
        tasks = []
        for session_id in session_ids:
            session = await self.get_session(session_id)
            if session and session.is_active():
                tasks.append(self._send_to_session(session, message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_to_session(self, session: AgentSession, message: Dict):
        """Send message to a specific session's Gemini client.

        Args:
            session: Target session
            message: Message dict with 'text' key
        """
        try:
            await session.gemini_client.send_text(
                message.get('text', ''),
                end_of_turn=True
            )
        except Exception as e:
            logger.error(
                f"Error sending message to session {session.session_id[:8]}: {e}"
            )

    def get_session_stats(self) -> Dict:
        """Get statistics about current sessions.

        Returns:
            Dict with session counts and info
        """
        all_sessions = list(self.sessions.values())
        active = [s for s in all_sessions if s.is_active()]
        completed = [s for s in all_sessions if s.status == SessionStatus.COMPLETED]
        failed = [s for s in all_sessions if s.status == SessionStatus.FAILED]

        return {
            'total': len(all_sessions),
            'active': len(active),
            'completed': len(completed),
            'failed': len(failed),
            'active_sessions': [s.session_name for s in active]
        }
