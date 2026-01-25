# Agent Hub Integration Guide

## Remaining Integration Steps

We've completed **8 out of 11** tasks (73% done). The foundation is solid and tested. Three critical files remain to be integrated:

1. **twilio_media_streams.py** - Connect SessionManager to call handling
2. **reminder_checker.py** - Multi-session awareness for reminders
3. **main_tars.py** - Wire everything together

This guide provides detailed instructions for completing the integration.

---

## Progress Summary

### ✅ Completed (Phase 1 & 2.1-2.3)

- `agent_session.py` - Session data structures
- `security.py` - Phone authentication & permissions
- `session_manager.py` - Session registry
- `message_router.py` - Message routing logic
- `database.py` - 3 new tables + 15 new methods
- `config.py` - TARGET_NAME, MAX_CONCURRENT_SESSIONS
- `gemini_live_client.py` - Permission-based config
- `sub_agents_tars.py` - InterSessionAgent + 6 functions

### 🔄 Remaining (Phase 2.4-2.6)

- `twilio_media_streams.py` - Integration (~300 lines)
- `reminder_checker.py` - Multi-session (~100 lines)
- `main_tars.py` - Wiring (~80 lines)

---

## File 1: twilio_media_streams.py

### Overview
This file handles incoming/outbound calls via Twilio WebSocket. It needs to:
1. Create sessions via SessionManager instead of bare GeminiLiveClient
2. Get caller phone number and authenticate
3. Handle different greetings (Máté vs unknown)
4. Integrate with MessageRouter for callbacks

### Key Changes

#### 1. Update `__init__` (lines 38-44)

**Add new dependencies:**
```python
def __init__(self, gemini_client: GeminiLiveClient, reminder_checker, db: Database,
             messaging_handler, session_manager, router):
    # ... existing code ...
    self.session_manager = session_manager
    self.router = router

    # REMOVE: self.active_connections = {} (replaced by SessionManager)
```

#### 2. Add `_get_caller_phone` method (NEW)

**Add after line ~635:**
```python
async def _get_caller_phone(self, call_sid: str) -> str:
    """Fetch caller's phone number from Twilio Call API"""
    try:
        call = self.twilio_client.calls(call_sid).fetch()
        return call.from_  # Caller's phone number
    except Exception as e:
        logger.error(f"Error fetching call details: {e}")
        return "unknown"
```

#### 3. Update `handle_media_stream()` (lines 349-448)

**MAJOR REFACTOR - Replace session creation logic:**

```python
async def handle_media_stream(self, websocket):
    """Handle WebSocket - now creates session via SessionManager"""

    call_sid = None
    stream_sid = None
    session = None

    try:
        # Wait for 'start' event to get call_sid
        async for message in websocket:
            data = json.loads(message)
            event = data.get('event')

            if event == 'start':
                call_sid = data['start']['callSid']
                stream_sid = data['start']['streamSid']

                # Get caller's phone number from Twilio
                from_number = await self._get_caller_phone(call_sid)

                # CREATE SESSION via SessionManager
                session = await self.session_manager.create_session(
                    call_sid=call_sid,
                    phone_number=from_number,
                    websocket=websocket,
                    stream_sid=stream_sid,
                    purpose=self.pending_reminder if "CALL OBJECTIVE" in (self.pending_reminder or "") else None
                )

                # Use session's dedicated Gemini client (already configured with permissions)
                call_gemini_client = session.gemini_client

                # Connect to Gemini with permission level
                await call_gemini_client.connect(permission_level=session.permission_level.value)

                # Send initial context based on session type
                if self.pending_reminder:
                    # Outbound goal call
                    if "CALL OBJECTIVE" in self.pending_reminder or "=== OUTBOUND CALL" in self.pending_reminder:
                        reminder_msg = f"[System: You are now speaking with {session.session_name}. This is NOT Máté.]\n\n{self.pending_reminder}"
                        await call_gemini_client.send_text(reminder_msg, end_of_turn=True)
                    else:
                        # Reminder call to Máté
                        await call_gemini_client.send_text(f"Announce reminder: {self.pending_reminder}", end_of_turn=True)
                    self.pending_reminder = None

                elif session.permission_level.value == "full":
                    # Máté's session - regular greeting
                    from translations import get_text
                    greeting = get_text('greeting')
                    await call_gemini_client.send_text(f"[System: Greet Máté with: '{greeting}']", end_of_turn=True)

                else:
                    # Unknown caller - limited access greeting
                    greeting = f"Hey, this is {Config.TARGET_NAME}'s assistant TARS, how can I help you?"
                    await call_gemini_client.send_text(
                        f"[System: Greet caller with: '{greeting}'. You have limited access - can only take messages and schedule callbacks.]",
                        end_of_turn=True
                    )

                    # Notify Máté of incoming unknown call (non-blocking)
                    asyncio.create_task(self._notify_mate_of_unknown_caller(session))

                # Mark session as active
                session.activate()

                # Continue with existing audio setup...
                # (rest of the code continues as before)
                break
```

#### 4. Add `_notify_mate_of_unknown_caller` method (NEW)

**Add after `_get_caller_phone`:**
```python
async def _notify_mate_of_unknown_caller(self, caller_session):
    """Notify Máté when unknown caller rings"""
    notification = f"Incoming call from {caller_session.session_name}"

    await self.router.route_message(
        from_session=caller_session,
        message=notification,
        target="user",
        message_type="notification"
    )
```

#### 5. Update `status_webhook()` (lines 96-212)

**Replace callback logic:**

Find the section that handles completed calls (around line 124-196) and update:

```python
# When call completes with goal:
if goal and goal['status'] == 'in_progress':
    self.db.complete_call_goal(goal['id'])

    # Get parent session (Máté's original session that requested this call)
    parent_session_id = goal.get('parent_session_id')

    def send_callback():
        # Build BRIEF summary (not full transcript)
        transcript = self.db.get_conversation_for_call(call_sid)

        # Generate AI summary using Gemini text model
        summary = await self._generate_call_summary(transcript, goal)

        callback_message = f"Report from call with {goal['contact_name']}:\n\n{summary}"

        # Route via message router (smart routing)
        await self.router.route_message(
            from_session=None,  # System message
            message=callback_message,
            target="user",
            message_type="call_completion_report"
        )

    # Run in background
    asyncio.create_task(send_callback())

# Terminate session in SessionManager
await self.session_manager.terminate_session_by_call_sid(call_sid)
```

#### 6. Add `_generate_call_summary` method (NEW)

**Add before status_webhook:**
```python
async def _generate_call_summary(self, transcript: List[Dict], goal: Dict) -> str:
    """Generate brief AI summary of call outcome (2-3 sentences)"""
    import google.generativeai as genai

    # Format transcript
    conversation = "\n".join([f"{msg['sender']}: {msg['message']}" for msg in transcript])

    prompt = f"""Summarize this phone call in 2-3 sentences. Focus on: (1) was the goal achieved? (2) what was decided? (3) any next steps?

Goal: {goal['goal_description']}

Conversation:
{conversation}

Brief summary:"""

    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    response = await model.generate_content_async(prompt)
    return response.text.strip()
```

---

## File 2: reminder_checker.py

### Overview
Currently uses single boolean `in_phone_call` - needs multi-session awareness via SessionManager.

### Key Changes

#### 1. Update `__init__` (lines 30-36)

```python
def __init__(self, db: Database, twilio_handler, session_manager, router):
    # REMOVE: self.in_phone_call = False (single boolean)
    # ADD:
    self.session_manager = session_manager
    self.router = router
```

#### 2. Remove old methods

**DELETE these methods:**
- `set_phone_call_status(in_call: bool)`
- `mark_call_answered()`

#### 3. Update `_handle_due_reminder()` (lines 126-195)

**Replace with multi-session logic:**

```python
async def _handle_due_reminder(self, reminder: dict):
    """Handle due reminder - check if Máté in active call"""

    # Check if Máté has active main session
    mate_session = await self.session_manager.get_mate_main_session()

    if mate_session and mate_session.status.value == "active":
        # User is in call - announce via router
        await self.router.route_message(
            from_session=None,  # System message
            message=f"Reminder: {reminder['title']}",
            target="user",
            message_type="reminder"
        )
        logger.info(f"Announced reminder in active call: {reminder['title']}")

    else:
        # User not in call - use delivery method from config
        delivery_method = Config.REMINDER_DELIVERY.lower()

        if delivery_method in ['call', 'both']:
            # Make outbound reminder call
            self.twilio_handler.make_call(
                to_number=Config.TARGET_PHONE_NUMBER,
                reminder_message=reminder['title']
            )

        if delivery_method in ['message', 'both']:
            # Send SMS reminder via N8N
            from sub_agents_tars import N8NAgent
            n8n_agent = N8NAgent()
            await n8n_agent.execute({
                "message": f"Send SMS to {Config.TARGET_PHONE_NUMBER}: ⏰ Reminder: {reminder['title']}"
            })
```

---

## File 3: main_tars.py

### Overview
Wire everything together - initialize SessionManager, Router, and update agent registrations.

### Key Changes

#### 1. Update imports (top of file)

**Add after existing imports:**
```python
from session_manager import SessionManager
from message_router import MessageRouter
```

#### 2. Update `main()` function initialization (lines 40-187)

**Replace agent initialization section:**

```python
async def main():
    # ... existing initialization ...

    db = Database()
    messaging_handler = MessagingHandler(db, Config.TWILIO_PHONE_NUMBER)

    # NEW: Initialize SessionManager and Router
    session_manager = SessionManager(db)
    router = MessageRouter(session_manager, messaging_handler, db)

    # Set router reference in session_manager (circular dependency workaround)
    session_manager.set_router(router)

    # Start router background processing
    await router.start()
    logger.info("Message router started")

    # Update ReminderChecker with new dependencies
    reminder_checker = ReminderChecker(
        db=db,
        twilio_handler=None,  # Will be set after twilio_handler created
        session_manager=session_manager,
        router=router
    )

    # Update TwilioMediaStreamsHandler with new dependencies
    twilio_handler = TwilioMediaStreamsHandler(
        gemini_client=gemini_client,
        reminder_checker=reminder_checker,
        db=db,
        messaging_handler=messaging_handler,
        session_manager=session_manager,
        router=router
    )

    # Set twilio_handler in reminder_checker
    reminder_checker.twilio_handler = twilio_handler
    reminder_checker.messaging_handler = messaging_handler

    # Get all agents with new dependencies
    agents = get_all_agents(
        db=db,
        messaging_handler=messaging_handler,
        system_reloader_callback=reload_system,
        twilio_handler=twilio_handler,
        session_manager=session_manager,
        router=router
    )

    # Register all function handlers
    for agent_name, agent in agents.items():
        for func_name, handler in agent.function_handlers.items():
            gemini_client.register_function_handler(func_name, handler)

    # ... rest of main() ...
```

---

## Testing After Integration

### 1. Basic Functionality Test

```bash
python main_tars.py
```

Should see:
```
🤖 TARS - Máté's Personal Assistant
════════════════════════════════════════════════════════════
Message router started
SessionManager initialized
... (rest of startup)
✅ TARS is ready!
```

### 2. Single Call Test

Call TARS from your number (404-952-5557):
- Should create "Call with Máté (main)" session
- Should work identically to before
- Check database: `SELECT * FROM agent_sessions;`

### 3. Unknown Caller Test

Call TARS from different number:
- Should hear: "Hey, this is Máté Dort's assistant TARS..."
- Should have limited functions
- Check logs for permission filtering

### 4. Database Check

```bash
sqlite3 tars.db
.tables
# Should see: agent_sessions, inter_session_messages, broadcast_approvals
SELECT * FROM agent_sessions;
```

---

## Rollback Plan

If issues arise:

```bash
# Revert to foundation only (before integration)
git checkout 522d14f  # Foundation + tests

# Or revert specific file:
git checkout HEAD~1 -- twilio_media_streams.py
```

---

## Next Steps

After completing integration:

1. **Test with single call** - Verify basic functionality
2. **Test with unknown caller** - Verify limited access
3. **Test reminders** - Verify in-call announcements
4. **Test outbound calls** - Verify goal callbacks work

Once all tests pass, the agent hub will be fully functional! 🚀

---

## Need Help?

- Run foundation tests: `python test_agent_hub.py`
- Check logs: Look for "SessionManager", "MessageRouter" messages
- Database inspection: `sqlite3 tars.db` then `.schema agent_sessions`
