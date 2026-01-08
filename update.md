 Missing features

Contact deletion function
Long message auto-routing to email
Conversation similarity search
Date-based conversation lookup
Topic-based conversation search (e.g., "AI glasses")
Automatic email routing for long responses (needs detection logic)

Combine send_message and send_link_to_user into one function
Create separate send_email function should support contacts and email addresses
send_message should support contacts and phone numbers
Combine send_message_to_session and take_message_for_mate broadcast_to_session (router already handles this)
Enhance schedule_callback for vague times - in the morning can be 8am and as soon as you see it can be 5min from now 

C. list_active_sessions could be part of a unified session management function
Could add: get_session_info, suspend_session (which where we have hang_up_call() so we can use that), resume_session
Recommendation: Keep list_active_sessions separate; it's informational, not an action.


Recommendation: Option C (messages enter live sessions)
Implementation approach:
# In messaging_handler.py:async def process_incoming_message(...):    # Try to find active Máté session    mate_session = await self.session_manager.get_mate_main_session()        if mate_session and mate_session.is_active():        # Inject message into live session        await mate_session.gemini_client.session.send(            input=message_body,            end_of_turn=True        )        # Response will come through normal session flow    else:        # No active session - use current generate_content approach        # But use same function handlers        response = await self._generate_text_response(...)
Benefits:
Same conversation context
Same function calling mechanism
Seamless transition between phone and email
Messages appear in the same session

live session naming:
session should be named after the name in the session or a goal like call with helen or call with druty hotel. I should be able to look up sessions with live_sessions function based on those names or similarites so it is easier

Naming the session after the contact for outbound goal calls is fine. Permission is determined by phone number authentication, not session name, so security stays correct.
Here's the fix to extract the contact name from the goal message and use it for the session name:
# In session_manager.py, modify _determine_session_identity():async def _determine_session_identity(    self,    phone_number: str,    permission_level: PermissionLevel,    purpose: Optional[str]) -> tuple[str, SessionType]:    """Determine session name and type based on caller information.    Args:        phone_number: Caller's phone number        permission_level: FULL or LIMITED        purpose: Optional goal description    Returns:        Tuple of (session_name, session_type)    """    if permission_level == PermissionLevel.FULL:        # Check if this is an outbound goal call (has purpose with contact name)        if purpose and ("OUTBOUND CALL TO" in purpose or "=== OUTBOUND CALL" in purpose):            # Extract contact name from goal message            # Format: "=== OUTBOUND CALL TO {NAME} ==="            import re            match = re.search(r'OUTBOUND CALL TO (\w+)', purpose, re.IGNORECASE)            if match:                contact_name = match.group(1)                session_name = f"Call with {contact_name}"                session_type = SessionType.OUTBOUND_GOAL                return session_name, session_type                # Regular Máté session - check if already has main session        mate_main = await self.get_mate_main_session()        if mate_main and mate_main.is_active():            # Already has main session - this is a secondary one            import uuid            suffix = uuid.uuid4().hex[:4]            session_name = f"Call with Máté ({suffix})"        else:            # First Máté session - this is the main one            session_name = "Call with Máté (main)"        if purpose:            session_type = SessionType.OUTBOUND_GOAL        else:            session_type = SessionType.INBOUND_USER    else:        # Unknown caller - LIMITED access        # Try to look up in contacts        contact = self.db.search_contact_by_phone(phone_number)        if contact:            session_name = f"Call with {contact['name']}"        else:            session_name = f"Call with {phone_number}"        session_type = SessionType.INBOUND_UNKNOWN    return session_name, session_type
Why this works:
Security: Permission stays FULL based on phone number authentication.
Clarity: Session name reflects who TARS is talking to.
Hangup: Works because the session is named "Call with John".
No confusion: Permission is separate from session name.
Benefits:
Hangup commands work correctly ("hang up the call with John")
Session names are meaningful
Security remains correct (FULL access based on phone number)
System logic remains clear (session name is for display/organization, permission is for security)