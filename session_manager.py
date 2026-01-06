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

    def __init__(self, db, router=None, function_handlers=None):
        """Initialize Session Manager.

        Args:
            db: Database instance for persistence
            router: Optional MessageRouter for inter-agent communication
            function_handlers: Optional dict of function_name -> handler for GeminiLiveClient
        """
        self.db = db
        self.router = router  # Will be set after router is created
        # Will be set after handlers are registered
        self.function_handlers = function_handlers or {}

        # Session registries
        # session_id -> AgentSession
        self.sessions: Dict[str, AgentSession] = {}
        self.call_sid_to_session: Dict[str, str] = {}  # call_sid -> session_id
        # phone -> [session_ids]
        self.phone_to_sessions: Dict[str, List[str]] = {}

        # Thread-safe lock for concurrent access
        self._lock = asyncio.Lock()

        logger.info("SessionManager initialized")

    def set_function_handlers(self, handlers: Dict):
        """Set function handlers after initialization (circular dependency workaround)"""
        self.function_handlers = handlers
        logger.info(
            f"SessionManager registered {len(handlers)} function handlers")

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
            # Authenticate phone number
            permission_level = authenticate_phone_number(phone_number)

            # If this is Máté with FULL access, check for resumable session
            if permission_level == PermissionLevel.FULL:
                resumed_session = await self.resume_mate_main_session(
                    phone_number, call_sid, websocket, stream_sid
                )

                if resumed_session:
                    logger.info(f"Resumed existing Máté main session")
                    # Register with router
                    if self.router:
                        await self.router.register_session(resumed_session)
                    return resumed_session

            # Generate unique session ID for new session
            session_id = generate_session_id()

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

            # Inject session context into handlers so agents know who they are
            self._inject_session_context(session)

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
            # Check if this is an outbound goal call (has purpose with contact name)
            if purpose and ("OUTBOUND CALL TO" in purpose or "=== OUTBOUND CALL" in purpose):
                # Extract contact name from goal message
                # Format: "=== OUTBOUND CALL TO {NAME} ==="
                import re
                # Match "OUTBOUND CALL TO" followed by name (stops at === or newline)
                # Contact names are uppercase in the message, but we'll convert to title case
                match = re.search(r'OUTBOUND CALL TO ([A-Z\s\-]+?)(?:\s*===|\n|$)', purpose, re.IGNORECASE)
                if match:
                    contact_name = match.group(1).strip().title()  # Title case for proper formatting
                    session_name = f"Call with {contact_name}"
                    session_type = SessionType.OUTBOUND_GOAL
                    logger.info(f"Outbound goal call detected - naming session: {session_name}")
                    return session_name, session_type
            
            # Regular Máté session - check if already has main session
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
        from translations import format_text
        from datetime import datetime

        current_time = datetime.now().strftime("%I:%M %p")
        current_date = datetime.now().strftime("%A, %B %d, %Y")

        if permission_level == PermissionLevel.FULL:
            # Use standard system instruction from config
            system_instruction = format_text(
                'tars_system_instruction',
                current_time=current_time,
                current_date=current_date,
                humor_percentage=Config.HUMOR_PERCENTAGE,
                honesty_percentage=Config.HONESTY_PERCENTAGE,
                personality=Config.PERSONALITY,
                nationality=Config.NATIONALITY
            )
            
            # Add conversation history context for phone calls
            context = self.db.get_conversation_context(limit=Config.CONVERSATION_HISTORY_LIMIT)
            if context:
                system_instruction += f"\n\nRecent conversation history:\n{context}"
        else:
            # Add LIMITED access constraints
            base_instruction = format_text(
                'tars_system_instruction',
                current_time=current_time,
                current_date=current_date,
                humor_percentage=Config.HUMOR_PERCENTAGE,
                honesty_percentage=Config.HONESTY_PERCENTAGE,
                personality=Config.PERSONALITY,
                nationality=Config.NATIONALITY
            )
            security_instruction = get_limited_system_instruction()
            system_instruction = base_instruction + "\n\n" + security_instruction

        # Create client
        client = GeminiLiveClient(
            api_key=Config.GEMINI_API_KEY,
            system_instruction=system_instruction
        )

        # Set filtered function declarations
        client.function_declarations = filtered_functions

        # Copy function handlers from SessionManager (already registered in main)
        if self.function_handlers:
            client.function_handlers = self.function_handlers.copy()
            logger.debug(
                f"Copied {len(self.function_handlers)} function handlers to session client")

        return client

    def _inject_session_context(self, session: AgentSession):
        """Wrap inter-session handlers to inject the source session object.

        This allows the InterSessionAgent to know which session is calling it,
        so messages are correctly attributed (e.g. "From Call with Helen" instead of "System").
        """
        client = session.gemini_client

        # Functions that need session context
        context_fns = [
            "send_message_to_session",
            "request_user_confirmation",
            "broadcast_to_sessions",
            "take_message_for_mate",
            "schedule_callback"
        ]

        for name in context_fns:
            if name in client.function_handlers:
                original = client.function_handlers[name]

                # Create wrapper that injects session into args
                async def wrapper(args, orig=original, sess=session):
                    if isinstance(args, dict):
                        args['_source_session'] = sess
                    return await orig(args)

                client.function_handlers[name] = wrapper

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
        target = session_name.lower().strip()
        candidates = []

        for session in self.sessions.values():
            if not session.is_active():
                continue

            name = session.session_name.lower()

            # 1. Exact match
            if name == target:
                return session

            # 2. Fuzzy match: target in name (e.g. "Máté (main)" in "Call with Máté (main)")
            if target in name:
                candidates.append(session)

        # If we found exactly one candidate, return it
        if len(candidates) == 1:
            return candidates[0]

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
                logger.warning(
                    f"Attempted to terminate unknown session {session_id[:8]}")
                return

            # Mark session as completed or failed
            if reason == "failed":
                session.fail(reason)
            else:
                session.complete()

            # Update database
            self.db.complete_session(session_id, completed_at=datetime.now())

            # Generate and send call summary for Máté (main) sessions
            if session.is_mate_session() and session.session_name == "Call with Máté (main)":
                asyncio.create_task(self._generate_and_send_call_summary(session))

            # Send conversation summary to Máté if this was a limited-access session
            if session.permission_level == PermissionLevel.LIMITED and self.router:
                asyncio.create_task(self._send_conversation_summary(session))

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
            logger.warning(
                f"Attempted to terminate session with unknown call_sid {call_sid}")

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

    async def _send_conversation_summary(self, session: AgentSession):
        """Send conversation summary to Máté after a limited-access session ends.

        Args:
            session: The completed session to summarize
        """
        try:
            # Get conversation from this call
            conversations = self.db.get_conversations_by_call_sid(
                session.call_sid)

            if not conversations or len(conversations) == 0:
                logger.debug(
                    f"No conversation to summarize for {session.session_name}")
                return

            # Build summary from conversation
            caller_messages = []
            for conv in conversations:
                if conv['sender'] == 'user':  # Messages from the caller
                    caller_messages.append(conv['message'])

            if not caller_messages:
                logger.debug(
                    f"No caller messages to summarize for {session.session_name}")
                return

            # Create concise summary
            summary_text = "; ".join(caller_messages[:3])  # First 3 messages
            if len(caller_messages) > 3:
                summary_text += f" (and {len(caller_messages) - 3} more messages)"

            message = f"Call ended with {session.session_name}. They said: {summary_text}"

            # Route to Máté via message router
            await self.router.route_message(
                from_session=session,
                message=message,
                target="user",
                message_type="conversation_summary"
            )
            logger.info(
                f"Sent conversation summary for {session.session_name} to Máté")

        except Exception as e:
            logger.error(f"Error sending conversation summary: {e}")

    def get_session_stats(self) -> Dict:
        """Get statistics about current sessions.

        Returns:
            Dict with session counts and info
        """
        all_sessions = list(self.sessions.values())
        active = [s for s in all_sessions if s.is_active()]
        completed = [s for s in all_sessions if s.status ==
                     SessionStatus.COMPLETED]
        failed = [s for s in all_sessions if s.status == SessionStatus.FAILED]

        return {
            'total': len(all_sessions),
            'active': len(active),
            'completed': len(completed),
            'failed': len(failed),
            'active_sessions': [s.session_name for s in active]
        }

    # ==================== SESSION PERSISTENCE ====================

    async def suspend_mate_main_session(self, reason: str = "user_disconnect") -> bool:
        """Suspend Máté's main session for later resumption.

        Args:
            reason: Reason for suspension

        Returns:
            True if session was suspended, False otherwise
        """
        mate_main = await self.get_mate_main_session()
        if not mate_main:
            return False

        import json

        # Save conversation snapshot
        conversations = self.db.get_conversations_by_call_sid(mate_main.call_sid)
        conversation_history = [
            {"sender": c['sender'], "message": c['message'], "timestamp": c['timestamp']}
            for c in conversations
        ]

        self.db.save_session_snapshot(
            mate_main.session_id,
            json.dumps(conversation_history),
            snapshot_type='full'
        )

        # Suspend session
        mate_main.suspend()
        self.db.suspend_session(mate_main.session_id)
        self.db.mark_session_resumable(mate_main.session_id, True)

        logger.info(f"Suspended Máté main session {mate_main.session_id[:8]} - {len(conversation_history)} messages saved")
        return True

    async def resume_mate_main_session(self, phone_number: str, call_sid: str, websocket, stream_sid: str):
        """Resume Máté's suspended session with conversation history.

        Args:
            phone_number: Phone number (for verification)
            call_sid: New Twilio call SID
            websocket: New WebSocket connection
            stream_sid: New Twilio stream SID

        Returns:
            Resumed AgentSession or None if no session to resume
        """
        # Check for resumable session
        resumable_sessions = self.db.get_resumable_sessions(phone_number)

        if not resumable_sessions:
            return None  # No session to resume, create new

        # Get most recent suspended session
        session_data = resumable_sessions[0]
        session_id = session_data['session_id']

        # Retrieve session object (might be in memory or need reconstruction)
        session = await self.get_session(session_id)

        if not session:
            # Reconstruct session from database
            session = await self._reconstruct_session_from_db(session_data)
            self.sessions[session_id] = session

        # Resume with new connection details
        session.resume(call_sid, websocket, stream_sid)
        self.call_sid_to_session[call_sid] = session_id

        # Restore conversation history to Gemini
        await self._restore_conversation_history(session)

        logger.info(f"Resumed Máté main session {session_id[:8]}")
        return session

    async def _restore_conversation_history(self, session: AgentSession):
        """Inject conversation history into Gemini Live session.

        Args:
            session: Session to restore context to
        """
        import json

        # Get snapshot
        snapshot = self.db.get_latest_session_snapshot(session.session_id)
        if not snapshot:
            logger.warning(f"No snapshot found for session {session.session_id[:8]}")
            return

        conversation_history = json.loads(snapshot['conversation_history'])

        # Send conversation replay to Gemini
        # Format: "Previous conversation context: [messages]"
        context_text = "Resuming previous conversation. Here's what we discussed:\n\n"

        for msg in conversation_history[-20:]:  # Last 20 messages for context
            sender_label = "You" if msg['sender'] == 'assistant' else "Máté"
            context_text += f"{sender_label}: {msg['message']}\n"

        context_text += "\nLet's continue from where we left off."

        # Send to Gemini as system message
        await session.gemini_client.send_text(context_text, end_of_turn=True)

        logger.info(f"Restored {len(conversation_history)} messages to session {session.session_id[:8]}")

    async def _reconstruct_session_from_db(self, session_data: Dict) -> AgentSession:
        """Recreate AgentSession from database data.

        Args:
            session_data: Session data from database

        Returns:
            Reconstructed AgentSession
        """
        # This is for when session object was lost from memory
        # Create new GeminiLiveClient
        permission_level = PermissionLevel(session_data['permission_level'])
        gemini_client = await self._create_gemini_client(permission_level)

        # Create session object (websocket/stream_sid will be None, updated on resume)
        session = AgentSession(
            session_id=session_data['session_id'],
            call_sid=session_data['call_sid'],
            session_name=session_data['session_name'],
            phone_number=session_data['phone_number'],
            permission_level=permission_level,
            session_type=SessionType(session_data['session_type']),
            gemini_client=gemini_client,
            websocket=None,  # Will be set on resume
            stream_sid=None,  # Will be set on resume
            purpose=session_data.get('purpose'),
            parent_session_id=session_data.get('parent_session_id'),
            created_at=datetime.fromisoformat(session_data['created_at'])
        )

        session.status = SessionStatus(session_data['status'])
        return session

    async def _generate_and_send_call_summary(self, session: AgentSession):
        """Generate AI-powered call summary and send to Gmail."""
        try:
            # Get conversation from call
            conversations = self.db.get_conversations_by_call_sid(session.call_sid)

            if not conversations or len(conversations) == 0:
                logger.debug(f"No conversation to summarize for {session.session_name}")
                return

            # Build conversation text for summarization
            conversation_text = ""
            for conv in conversations:
                sender_label = "TARS" if conv['sender'] == 'assistant' else "Máté"
                conversation_text += f"{sender_label}: {conv['message']}\n"

            # Use Gemini to generate summary
            summary = await self._generate_summary_with_ai(conversation_text, session)

            # Send to Gmail console
            if hasattr(self, 'gmail_handler') and self.gmail_handler:
                await self.gmail_handler.send_call_summary(session, summary)
                logger.info(f"Sent call summary for {session.session_name}")

        except Exception as e:
            logger.error(f"Error generating call summary: {e}")

    async def _generate_summary_with_ai(self, conversation_text: str, session: AgentSession) -> str:
        """Use Gemini to generate concise call summary."""
        from google import genai
        from google.genai import types

        client = genai.Client(
            http_options={"api_version": "v1beta"},
            api_key=Config.GEMINI_API_KEY
        )

        prompt = f"""Analyze this phone call between Máté and TARS and create a concise summary.

Conversation:
{conversation_text}

Generate a summary with:
1. Main topics discussed (bullet points)
2. Decisions made
3. Action items or next steps
4. Key information shared

Keep it brief and actionable (3-5 sentences max)."""

        try:
            response = await client.aio.models.generate_content(
                model="models/gemini-2.0-flash-exp",
                contents=[types.Content(parts=[types.Part(text=prompt)], role="user")],
                config=types.GenerateContentConfig(temperature=0.3)
            )

            if response.candidates and response.candidates[0].content.parts:
                summary = response.candidates[0].content.parts[0].text
                return summary.strip()
            else:
                return "Summary generation failed."

        except Exception as e:
            logger.error(f"AI summary generation error: {e}")
            return "Summary not available."
        finally:
            client.close()
