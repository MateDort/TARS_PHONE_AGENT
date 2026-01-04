"""Security module for agent session authentication and permission filtering."""
import logging
from typing import List, Dict
from config import Config

logger = logging.getLogger(__name__)


# Import PermissionLevel from agent_session to avoid circular import issues
from agent_session import PermissionLevel


def authenticate_phone_number(phone: str) -> PermissionLevel:
    """Determine permission level based on phone number.

    Args:
        phone: Caller's phone number

    Returns:
        PermissionLevel.FULL for Máté's number, LIMITED for others
    """
    # Normalize phone numbers for comparison (remove spaces, dashes, etc.)
    normalized_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    normalized_target = Config.TARGET_PHONE_NUMBER.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')

    if normalized_phone.endswith(normalized_target[-10:]):  # Match last 10 digits
        logger.info(f"Phone {phone} authenticated as Máté (FULL access)")
        return PermissionLevel.FULL
    else:
        logger.info(f"Phone {phone} authenticated as unknown caller (LIMITED access)")
        return PermissionLevel.LIMITED


def filter_functions_by_permission(
    permission: PermissionLevel,
    all_functions: List[Dict]
) -> List[Dict]:
    """Filter function declarations based on permission level.

    FULL access: All functions available
    LIMITED access: Only safe, restricted functions

    Args:
        permission: PermissionLevel (FULL or LIMITED)
        all_functions: List of function declaration dicts

    Returns:
        Filtered list of function declarations
    """
    if permission == PermissionLevel.FULL:
        logger.debug(f"FULL access: {len(all_functions)} functions available")
        return all_functions

    # LIMITED access - only allow safe functions
    allowed_function_names = {
        # Time and information
        "get_current_time",

        # Message taking (for unknown callers)
        "take_message_for_mate",
        "schedule_callback",

        # Inter-agent communication (allow limited sessions to send messages)
        "send_message_to_session",
        "request_user_confirmation",
        "list_active_sessions"

        # NOT ALLOWED for LIMITED:
        # - outbound_call_agent (make_call, cancel_call)
        # - reminder_agent (add_reminder, delete_reminder, list_reminders)
        # - contact_agent (add_contact, search_contact, etc.)
        # - config_agent (edit_config)
        # - broadcast_to_sessions (can only send direct messages)
    }

    filtered = [f for f in all_functions if f.get("name") in allowed_function_names]

    logger.info(
        f"LIMITED access: {len(filtered)}/{len(all_functions)} functions available - "
        f"allowed: {', '.join(allowed_function_names)}"
    )

    return filtered


def get_limited_system_instruction() -> str:
    """Get modified system instruction for limited-access sessions.

    Returns:
        Additional instructions for limited access behavior
    """
    return """
[IMPORTANT SECURITY CONSTRAINTS]
You have LIMITED ACCESS because this caller is not Máté. You can ONLY:
1. Have conversations and answer general questions
2. Take messages for Máté using take_message_for_mate()
3. Schedule callbacks using schedule_callback()
4. Send messages to other active sessions (if needed)

You CANNOT:
- Make outbound calls to other people
- Access or modify Máté's reminders
- Access or modify contacts
- Access confidential information
- Change any configuration settings
- Broadcast messages to multiple sessions

Be polite and helpful, but maintain these security boundaries at all times.
If the caller asks for something you cannot do, explain that you have limited
access and offer to take a message for Máté instead.
"""


def validate_session_permission(
    session_permission: PermissionLevel,
    required_permission: PermissionLevel
) -> bool:
    """Validate if a session has required permission level.

    Args:
        session_permission: Session's actual permission level
        required_permission: Required permission level for operation

    Returns:
        True if session has sufficient permission, False otherwise
    """
    if required_permission == PermissionLevel.LIMITED:
        # Any permission level satisfies LIMITED requirement
        return True

    if required_permission == PermissionLevel.FULL:
        # Only FULL permission satisfies FULL requirement
        return session_permission == PermissionLevel.FULL

    return False


def get_session_capabilities(permission: PermissionLevel) -> List[str]:
    """Get list of capabilities available to a permission level.

    Args:
        permission: PermissionLevel to query

    Returns:
        List of capability descriptions
    """
    if permission == PermissionLevel.FULL:
        return [
            "Make outbound calls to contacts",
            "Create, view, and delete reminders",
            "Access and modify contact information",
            "Change configuration settings",
            "Send messages (SMS/WhatsApp)",
            "Inter-agent communication (send/broadcast messages)",
            "View conversation history",
            "Full access to all TARS functions"
        ]
    else:  # LIMITED
        return [
            "Have general conversations",
            "Take messages for Máté",
            "Schedule callbacks",
            "Send messages to other active sessions",
            "Check current time"
        ]


# Security audit logging
def log_permission_violation(
    session_id: str,
    session_name: str,
    attempted_function: str,
    permission_level: PermissionLevel
):
    """Log security violation when a session attempts unauthorized action.

    Args:
        session_id: Session ID attempting the action
        session_name: Human-readable session name
        attempted_function: Function that was attempted
        permission_level: Session's permission level
    """
    logger.warning(
        f"SECURITY VIOLATION: Session {session_id[:8]} ({session_name}) with "
        f"{permission_level.value} access attempted to call {attempted_function}. "
        f"This function requires FULL access."
    )
