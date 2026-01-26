"""Agent Session - Represents a single active Gemini Live call session."""
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Session lifecycle states"""
    CONNECTING = "connecting"
    ACTIVE = "active"
    SUSPENDED = "suspended"  # NEW: Session paused, can resume
    COMPLETED = "completed"
    FAILED = "failed"


class SessionType(Enum):
    """Types of sessions based on origin"""
    INBOUND_USER = "inbound_user"          # Máté calling in
    INBOUND_UNKNOWN = "inbound_unknown"    # Unknown caller
    OUTBOUND_GOAL = "outbound_goal"        # Goal-based outbound call


class PermissionLevel(Enum):
    """Permission levels for session access control"""
    FULL = "full"          # Máté's sessions - all tools available
    LIMITED = "limited"    # Unknown callers - restricted access


class AgentSession:
    """Represents a single active Gemini Live session with metadata.

    Each phone call gets its own AgentSession instance that tracks:
    - Session identity (ID, name, phone number)
    - Permission level (full vs limited access)
    - Associated Gemini Live client and websocket
    - Session lifecycle status
    - Parent/child relationships for spawned calls
    """

    def __init__(
        self,
        session_id: str,
        call_sid: str,
        session_name: str,
        phone_number: str,
        permission_level: PermissionLevel,
        session_type: SessionType,
        gemini_client,  # GeminiLiveClient
        websocket,      # WebSocket
        stream_sid: str,
        purpose: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        created_at: Optional[datetime] = None
    ):
        """Initialize a new agent session.

        Args:
            session_id: Unique UUID for this session
            call_sid: Twilio Call SID
            session_name: Human-readable name (e.g., "Call with Máté (main)")
            phone_number: Caller's phone number
            permission_level: FULL or LIMITED access
            session_type: INBOUND_USER, INBOUND_UNKNOWN, or OUTBOUND_GOAL
            gemini_client: Dedicated GeminiLiveClient for this session
            websocket: Twilio Media Stream WebSocket connection
            stream_sid: Twilio Stream SID
            purpose: Optional goal description for outbound calls
            parent_session_id: Optional ID of parent session (for spawned calls)
            created_at: Session creation timestamp
        """
        self.session_id = session_id
        self.call_sid = call_sid
        self.session_name = session_name
        self.phone_number = phone_number
        self.permission_level = permission_level
        self.session_type = session_type
        self.purpose = purpose
        self.gemini_client = gemini_client
        self.websocket = websocket
        self.stream_sid = stream_sid
        self.parent_session_id = parent_session_id
        self.created_at = created_at or datetime.now()

        # Session state
        self.status = SessionStatus.CONNECTING
        self.completed_at: Optional[datetime] = None

        # NEW: Session persistence fields
        self.platform = "call"  # call, gmail, sms, whatsapp
        self.last_activity_at = datetime.now()
        self.can_resume = False

        # Inter-agent communication
        self.pending_user_confirmations: List[Dict] = []

        logger.info(
            f"Created session {self.session_id[:8]}: {self.session_name} "
            f"({self.permission_level.value} access)"
        )

    def activate(self):
        """Mark session as active (call connected)"""
        self.status = SessionStatus.ACTIVE
        logger.info(f"Session {self.session_id[:8]} activated: {self.session_name}")

    def complete(self):
        """Mark session as completed (call ended successfully)"""
        self.status = SessionStatus.COMPLETED
        self.completed_at = datetime.now()
        duration = (self.completed_at - self.created_at).total_seconds()
        logger.info(
            f"Session {self.session_id[:8]} completed: {self.session_name} "
            f"(duration: {duration:.1f}s)"
        )

    def fail(self, reason: str):
        """Mark session as failed with reason"""
        self.status = SessionStatus.FAILED
        self.completed_at = datetime.now()
        logger.error(
            f"Session {self.session_id[:8]} failed: {self.session_name} - {reason}"
        )

    def add_pending_confirmation(self, confirmation: Dict):
        """Add a pending user confirmation request.

        Args:
            confirmation: Dict with keys: message_id, question, context, timestamp
        """
        self.pending_user_confirmations.append(confirmation)
        logger.debug(
            f"Session {self.session_id[:8]} has pending confirmation: "
            f"{confirmation.get('question', 'unknown')}"
        )

    def resolve_confirmation(self, message_id: str, response: str):
        """Resolve a pending confirmation with user's response.

        Args:
            message_id: ID of the confirmation message
            response: User's response

        Returns:
            The resolved confirmation dict, or None if not found
        """
        for i, conf in enumerate(self.pending_user_confirmations):
            if conf.get('message_id') == message_id:
                conf['response'] = response
                conf['resolved_at'] = datetime.now()
                resolved = self.pending_user_confirmations.pop(i)
                logger.info(
                    f"Session {self.session_id[:8]} resolved confirmation: "
                    f"{resolved.get('question', 'unknown')} -> {response}"
                )
                return resolved
        return None

    def has_full_access(self) -> bool:
        """Check if this session has full access permissions"""
        return self.permission_level == PermissionLevel.FULL

    def is_active(self) -> bool:
        """Check if session is currently active"""
        return self.status == SessionStatus.ACTIVE

    def is_mate_session(self) -> bool:
        """Check if this is a Máté session (full access)"""
        return self.has_full_access()

    def suspend(self):
        """Suspend session for later resumption"""
        self.status = SessionStatus.SUSPENDED
        self.last_activity_at = datetime.now()
        self.can_resume = True
        logger.info(f"Session {self.session_id[:8]} suspended")

    def resume(self, new_call_sid: str, new_websocket, new_stream_sid: str):
        """Resume suspended session with new connection"""
        self.call_sid = new_call_sid
        self.websocket = new_websocket
        self.stream_sid = new_stream_sid
        self.status = SessionStatus.ACTIVE
        self.last_activity_at = datetime.now()
        logger.info(f"Session {self.session_id[:8]} resumed")

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity_at = datetime.now()

    def switch_platform(self, new_platform: str):
        """Transfer session to different platform"""
        old_platform = self.platform
        self.platform = new_platform
        self.last_activity_at = datetime.now()
        logger.info(f"Session {self.session_id[:8]} switched: {old_platform} → {new_platform}")

    def to_dict(self) -> Dict:
        """Convert session to dictionary for database storage"""
        return {
            'session_id': self.session_id,
            'call_sid': self.call_sid,
            'session_name': self.session_name,
            'phone_number': self.phone_number,
            'permission_level': self.permission_level.value,
            'session_type': self.session_type.value,
            'purpose': self.purpose,
            'status': self.status.value,
            'parent_session_id': self.parent_session_id,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

    def __repr__(self) -> str:
        return (
            f"AgentSession(id={self.session_id[:8]}, "
            f"name='{self.session_name}', "
            f"status={self.status.value}, "
            f"permission={self.permission_level.value})"
        )


def generate_session_id() -> str:
    """Generate a unique session ID (UUID4)"""
    return str(uuid.uuid4())
