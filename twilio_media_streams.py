"""Twilio Media Streams integration for real-time audio with Gemini Live."""
import asyncio
import json
import base64
import logging
import websockets
import sys
import audioop  # audioop-lts package provides the 'audioop' module for Python 3.13+
from typing import Optional
from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from twilio.rest import Client
from config import Config
from gemini_live_client import GeminiLiveClient

logger = logging.getLogger(__name__)


class TwilioMediaStreamsHandler:
    """Handles Twilio Media Streams WebSocket connection with Gemini Live."""

    def __init__(self, gemini_client: GeminiLiveClient, reminder_checker=None, db=None, messaging_handler=None, session_manager=None, router=None):
        """Initialize handler with agent hub support.

        Args:
            gemini_client: GeminiLiveClient instance (main client, not used per-session)
            reminder_checker: Optional ReminderChecker instance
            db: Optional Database instance for conversation logging
            messaging_handler: Optional MessagingHandler instance
            session_manager: Optional SessionManager for agent hub
            router: Optional MessageRouter for inter-session communication
        """
        self.gemini_client = gemini_client
        self.twilio_client = Client(
            Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
        self.app = Flask(__name__)
        self._setup_routes()
        self.reminder_checker = reminder_checker
        self.db = db
        self.messaging_handler = messaging_handler
        self.session_manager = session_manager
        self.router = router
        self.main_loop = None

        # WebSocket state (deprecated - sessions now managed by SessionManager)
        self.websocket_server = None
        self.active_connections = {}  # Kept for backward compatibility

        # Pending reminder message for auto-calls
        self.pending_reminder = None
        self.pending_reminder_id = None  # Track reminder_id to mark complete when answered

        # Audio buffer for seamless reconnection
        self.audio_buffer = []
        self.is_reconnecting = False
        # Buffer up to 50 packets (~1 second of audio)
        self.max_buffer_size = 50
        # Store active call client for reconnection checks
        self._active_call_client = None

    def set_main_loop(self, loop):
        """Set the main event loop for thread-safe scheduling from Flask threads."""
        self.main_loop = loop

    def _setup_routes(self):
        """Set up Flask routes for Twilio webhooks."""

        @self.app.route('/', methods=['GET'])
        def root():
            """Handle root requests (ngrok browser verification)."""
            return Response('TARS Webhook Server', mimetype='text/plain')

        @self.app.route('/webhook/voice', methods=['POST', 'GET'])
        def voice_webhook():
            """Handle incoming call - start media stream."""
            try:
                call_sid = request.form.get('CallSid')
                from_number = request.form.get('From')
                to_number = request.form.get('To')

                print(f"\n📞 INCOMING CALL")
                print(f"   From: {from_number}")
                print(f"   To: {to_number}")
                print(f"   Call SID: {call_sid}")
                logger.info(f"Voice webhook called: CallSid={call_sid}, From={from_number}, To={to_number}")

                response = VoiceResponse()

                # Connect to Media Streams WebSocket immediately
                # Note: Say removed - it was causing calls to hang up before WebSocket connection
                # WebSocket runs on port 5001 with its own ngrok URL
                connect = Connect()
                if Config.WEBSOCKET_URL:
                    # Use configured WebSocket URL (from separate ngrok tunnel)
                    # Don't add path - WebSocket server listens on root
                    websocket_url = Config.WEBSOCKET_URL.replace(
                        "wss://", "").replace("https://", "").replace("http://", "")
                    stream = Stream(url=f'wss://{websocket_url}')
                else:
                    # Fallback: assume same domain (won't work with separate tunnels)
                    websocket_base = Config.WEBHOOK_BASE_URL.replace(
                        "https://", "").replace("http://", "")
                    stream = Stream(url=f'wss://{websocket_base}')
                connect.append(stream)
                response.append(connect)

                return Response(str(response), mimetype='text/xml')

            except Exception as e:
                logger.error(f"Error in voice_webhook: {e}")
                response = VoiceResponse()
                response.say("Sorry, an error occurred")
                return Response(str(response), mimetype='text/xml')

        @self.app.route('/webhook/status', methods=['POST'])
        def status_webhook():
            """Handle call status updates."""
            call_sid = request.form.get('CallSid')
            call_status = request.form.get('CallStatus')
            call_duration = request.form.get('CallDuration', '0')

            # Visual call status logging
            status_emoji = {
                'queued': '📞',
                'ringing': '📱',
                'in-progress': '✅',
                'completed': '✔️',
                'failed': '❌',
                'busy': '📵',
                'no-answer': '🔇',
                'canceled': '🚫'
            }
            emoji = status_emoji.get(call_status, '📞')

            print(f"\n{emoji} CALL STATUS: {call_status.upper()}")
            print(f"   Call SID: {call_sid}")
            if call_status == 'completed':
                print(f"   Duration: {call_duration} seconds")

            logger.info(
                f"Call {call_sid} status: {call_status} (duration: {call_duration}s)")

            # Check if this was a completed goal-based outbound call
            if call_status == 'completed' and self.db:
                goal = self.db.get_call_goal_by_sid(call_sid)
                if goal and goal['status'] == 'in_progress':
                    # Mark as completed
                    self.db.complete_call_goal(
                        goal['id'], result=f"Call completed ({call_duration}s)")
                    logger.info(
                        f"Goal call {goal['id']} completed, generating summary...")

                    # Get parent session ID (Máté's original session that requested this call)
                    parent_session_id = goal.get('parent_session_id')

                    # Generate and route callback via MessageRouter (async, non-blocking)
                    async def send_callback():
                        try:
                            # Get conversation transcript
                            transcript = self.db.get_conversations_by_call_sid(
                                call_sid)

                            # Generate brief AI summary (2-3 sentences)
                            summary = await self._generate_call_summary(transcript, goal)

                            callback_message = f"Report from call with {goal['contact_name']}:\n\n{summary}"

                            # Route via message router (smart routing - in-call or SMS/call)
                            await self.router.route_message(
                                from_session=None,  # System message
                                message=callback_message,
                                target="user",
                                message_type="call_completion_report"
                            )
                            logger.info(
                                f"Routed callback for goal call {goal['id']}")
                        except Exception as e:
                            logger.error(f"Error sending callback: {e}")

                    # Run in background
                    if self.main_loop and self.main_loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            send_callback(), self.main_loop)
                    else:
                        logger.error(
                            "Cannot send callback: Main event loop not available")

                    # Terminate session in SessionManager (if not already done in finally block)
                    async def terminate_session():
                        try:
                            await self.session_manager.terminate_session_by_call_sid(call_sid)
                        except Exception as e:
                            logger.debug(
                                f"Session already terminated or not found: {e}")

                    if self.session_manager:
                        if self.main_loop and self.main_loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                terminate_session(), self.main_loop)
                        else:
                            logger.error(
                                "Cannot terminate session: Main event loop not available")

            if call_status in ['completed', 'failed', 'busy', 'no-answer']:
                # Cleanup connection
                if call_sid in self.active_connections:
                    del self.active_connections[call_sid]

            return Response('', mimetype='text/xml')

        @self.app.route('/webhook/sms', methods=['POST'])
        def sms_webhook():
            """Handle incoming SMS messages."""
            from_number = request.form.get('From')
            to_number = request.form.get('To')
            message_body = request.form.get('Body')
            message_sid = request.form.get('MessageSid')

            logger.info(f"Received SMS from {from_number}: {message_body}")

            # Process message asynchronously if messaging handler is available
            if hasattr(self, 'messaging_handler') and self.messaging_handler:
                coro = self.messaging_handler.process_incoming_message(
                    from_number=from_number,
                    message_body=message_body,
                    medium='sms',
                    message_sid=message_sid,
                    to_number=to_number
                )
                if self.main_loop and self.main_loop.is_running():
                    asyncio.run_coroutine_threadsafe(coro, self.main_loop)
                else:
                    logger.error(
                        "Cannot process SMS: Main event loop not available. Running in new thread.")
                    # Fallback for environments where loop isn't passed (e.g. tests)
                    import threading
                    thread = threading.Thread(
                        target=lambda: asyncio.run(coro), daemon=True)
                    thread.start()
            else:
                logger.warning(
                    "MessagingHandler not initialized - cannot process SMS")

            # Return empty response (Twilio will receive reply separately)
            return Response('', status=200)

        @self.app.route('/webhook/n8n', methods=['POST'])
        def n8n_webhook():
            """Handle incoming tasks from N8N - creates 'Mate_n8n' live session."""
            import json
            try:
                data = request.get_json() or request.form.to_dict()
                task_message = data.get('message') or data.get('task') or data.get('text', '')
                
                if not task_message:
                    logger.warning("N8N webhook received empty message")
                    return Response(json.dumps({"error": "No message provided"}), status=400, mimetype='application/json')
                
                logger.info(f"Received task from N8N: {task_message[:100]}")
                
                # Create N8N session asynchronously
                async def create_n8n_session():
                    try:
                        # Create a special session for N8N tasks
                        session = await self.session_manager.create_n8n_session(
                            task_message=task_message
                        )
                        logger.info(f"Created N8N session: {session.session_name}")
                    except Exception as e:
                        logger.error(f"Error creating N8N session: {e}")
                
                # Run in background
                if self.main_loop and self.main_loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        create_n8n_session(), self.main_loop)
                else:
                    logger.error("Cannot create N8N session: Main event loop not available")
                    return Response(json.dumps({"error": "System not ready"}), status=503, mimetype='application/json')
                
                return Response(json.dumps({"status": "accepted", "message": "Task received"}), status=200, mimetype='application/json')
                
            except Exception as e:
                logger.error(f"Error in N8N webhook: {e}")
                return Response(json.dumps({"error": str(e)}), status=500, mimetype='application/json')

        @self.app.route('/webhook/whatsapp', methods=['POST'])
        def whatsapp_webhook():
            """Handle incoming WhatsApp messages."""
            from_number = request.form.get('From')
            to_number = request.form.get('To')
            message_body = request.form.get('Body')
            message_sid = request.form.get('MessageSid')

            logger.info(
                f"Received WhatsApp from {from_number}: {message_body}")

            # Process message asynchronously if messaging handler is available
            if hasattr(self, 'messaging_handler') and self.messaging_handler:
                coro = self.messaging_handler.process_incoming_message(
                    from_number=from_number,
                    message_body=message_body,
                    medium='whatsapp',
                    message_sid=message_sid,
                    to_number=to_number
                )
                if self.main_loop and self.main_loop.is_running():
                    asyncio.run_coroutine_threadsafe(coro, self.main_loop)
                else:
                    logger.error(
                        "Cannot process WhatsApp: Main event loop not available. Running in new thread.")
                    # Fallback for environments where loop isn't passed
                    import threading
                    thread = threading.Thread(
                        target=lambda: asyncio.run(coro), daemon=True)
                    thread.start()
            else:
                logger.warning(
                    "MessagingHandler not initialized - cannot process WhatsApp")

            # Return empty response
            return Response('', status=200)

    async def handle_media_stream(self, websocket):
        """Handle WebSocket connection from Twilio Media Streams - now creates session via SessionManager.

        Args:
            websocket: WebSocket connection
        """
        # Note: 'path' parameter removed - websockets library no longer passes it in newer versions
        call_sid = None
        stream_sid = None
        session = None
        call_gemini_client = None

        try:
            print(f"\n🔌 WEBSOCKET CONNECTED")
            logger.info("Media stream connected - waiting for start event...")

            # Wait for 'start' event to get call_sid before creating session
            async for message in websocket:
                try:
                    data = json.loads(message)
                    event = data.get('event')

                    if event == 'start':
                        # Extract call details
                        call_sid = data['start']['callSid']
                        stream_sid = data['start']['streamSid']

                        print(f"   📞 Call SID: {call_sid}")
                        logger.info(
                            f"Stream started: {stream_sid} for call {call_sid}")

                        # Get call details from Twilio Call API
                        from_number = await self._get_caller_phone(call_sid)

                        # Determine authentication phone number based on call direction
                        # For outbound reminder calls to Máté, authenticate based on TO number
                        # For inbound calls or outbound goal calls, authenticate based on FROM number
                        if self.pending_reminder and "CALL OBJECTIVE" not in (self.pending_reminder or ""):
                            # This is an outbound reminder call to Máté - use TO number
                            try:
                                call = self.twilio_client.calls(
                                    call_sid).fetch()
                                to_number = getattr(call, 'to', None) or getattr(
                                    call, 'to_formatted', None) or call._properties.get('to', from_number)
                                auth_phone = to_number
                                print(
                                    f"   📱 Calling: {to_number} (outbound reminder)")
                            except Exception as e:
                                logger.error(f"Error fetching TO number: {e}")
                                auth_phone = from_number
                        else:
                            # Inbound call or outbound goal call - use FROM number
                            auth_phone = from_number
                            print(f"   📱 Caller: {from_number}")

                        # CREATE SESSION via SessionManager
                        # This handles authentication, naming, and permission-filtered function declarations
                        # #region agent log
                        with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                            import json, time
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"twilio_media_streams.py:376","message":"Creating session - before","data":{"call_sid":call_sid,"auth_phone":auth_phone},"timestamp":int(time.time()*1000)})+"\n")
                        # #endregion
                        session = await self.session_manager.create_session(
                            call_sid=call_sid,
                            phone_number=auth_phone,
                            websocket=websocket,
                            stream_sid=stream_sid,
                            purpose=self.pending_reminder if "CALL OBJECTIVE" in (
                                self.pending_reminder or "") else None
                        )
                        # #region agent log
                        with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                            import json, time
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"twilio_media_streams.py:388","message":"Session created - after","data":{"session_name":session.session_name,"permission_level":session.permission_level.value},"timestamp":int(time.time()*1000)})+"\n")
                        # #endregion

                        print(
                            f"   👤 Session: {session.session_name} ({session.permission_level.value} access)")
                        logger.info(
                            f"Created session: {session.session_name} with {session.permission_level.value} permissions")

                        # Use session's dedicated Gemini client (already configured with permissions)
                        call_gemini_client = session.gemini_client
                        self._active_call_client = call_gemini_client  # Store for reconnection

                        # Connect to Gemini with permission level
                        print(f"   Connecting to Gemini Live...")
                        # #region agent log
                        with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                            import json, time
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"twilio_media_streams.py:396","message":"Connecting to Gemini - before","data":{"permission_level":session.permission_level.value},"timestamp":int(time.time()*1000)})+"\n")
                        # #endregion
                        await call_gemini_client.connect(permission_level=session.permission_level.value)
                        # #region agent log
                        with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                            import json, time
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"twilio_media_streams.py:399","message":"Gemini connected - after","data":{"permission_level":session.permission_level.value},"timestamp":int(time.time()*1000)})+"\n")
                        # #endregion
                        print(
                            f"   ✅ Gemini Live connected (permission: {session.permission_level.value})")

                        # Send initial context based on session type and permissions
                        if self.pending_reminder:
                            # Outbound call with a goal
                            if "CALL OBJECTIVE" in self.pending_reminder or "=== OUTBOUND CALL" in self.pending_reminder:
                                # Goal-based call - TARS speaks to contact, not Máté
                                reminder_msg = f"[System: You are now speaking with {session.session_name}. This is NOT Máté.]\n\n{self.pending_reminder}"
                                await call_gemini_client.send_text(reminder_msg, end_of_turn=True)
                                print(f"   🎯 Goal message sent to TARS")
                                print(f"   {self.pending_reminder[:100]}...")
                            else:
                                # Reminder call to Máté
                                await call_gemini_client.send_text(f"Announce reminder: {self.pending_reminder}", end_of_turn=True)
                                print(f"   ⏰ Reminder message sent")
                                # Mark reminder as complete since call was answered
                                if self.pending_reminder_id and self.db:
                                    reminder = self.db.get_reminder(self.pending_reminder_id)
                                    if reminder and not reminder.get('recurrence'):
                                        self.db.mark_reminder_complete(self.pending_reminder_id)
                                        logger.info(f"Marked reminder {self.pending_reminder_id} as complete after call answered")
                            self.pending_reminder = None
                            self.pending_reminder_id = None

                        elif session.permission_level.value == "full":
                            # Máté's session - regular greeting
                            from translations import get_text
                            greeting = get_text('greeting')
                            await call_gemini_client.send_text(f"[System: Greet Máté with: '{greeting}']", end_of_turn=True)
                            print(f"   👋 Greeting sent to TARS")
                            logger.info(
                                "Sent greeting trigger to Gemini for Máté")

                        else:
                            # Unknown caller - limited access greeting
                            greeting = f"Hey, this is {Config.TARGET_NAME}'s assistant TARS, how can I help you?"
                            await call_gemini_client.send_text(
                                f"[System: Greet caller with: '{greeting}'. You have limited access - can only take messages and schedule callbacks.]",
                                end_of_turn=True
                            )
                            print(f"   🔒 Limited access greeting sent")
                            logger.info(
                                f"Sent limited access greeting for unknown caller: {from_number}")

                            # Notify Máté of incoming unknown call (non-blocking)
                            asyncio.create_task(
                                self._notify_mate_of_unknown_caller(session))

                        # Mark session as active
                        session.activate()

                        # Set up conversation logging callbacks with the call_sid
                        # Buffer for accumulating sentence fragments
                        user_buffer = []
                        ai_buffer = []
                        
                        # Full response buffer for length checking
                        full_response_buffer = []
                        response_check_task = None

                        async def log_user_transcript(text: str):
                            """Log user's spoken text to database, batching into sentences."""
                            try:
                                if not text.strip():
                                    return

                                user_buffer.append(text)

                                # Check if this completes a sentence (ends with punctuation or is long enough)
                                combined = ''.join(user_buffer)
                                if any(combined.rstrip().endswith(p) for p in ['.', '!', '?', '。']) or len(user_buffer) > 15:
                                    if hasattr(self, 'db') and self.db:
                                        self.db.add_conversation_message(
                                            sender='user',
                                            message=combined.strip(),
                                            medium='phone_call',
                                            call_sid=call_sid,
                                            direction='inbound'
                                        )
                                        logger.debug(
                                            f"Logged user sentence for call {call_sid}: {combined[:50]}...")
                                        
                                        # Check if user confirmed sending full response via email
                                        user_text_lower = combined.strip().lower()
                                        affirmative_responses = ['yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'send it', 'send', 'please', 'go ahead']
                                        
                                        if any(response in user_text_lower for response in affirmative_responses):
                                            # Get session to check for pending long response
                                            session = await self.session_manager.get_session_by_call_sid(call_sid)
                                            if session and hasattr(session, '_pending_long_response') and session._pending_long_response:
                                                full_response = session._pending_long_response
                                                response_chars = getattr(session, '_pending_response_chars', len(full_response))
                                                
                                                logger.info(f"User confirmed sending full response ({response_chars} chars) via email")
                                                
                                                # Send full response via email
                                                # Detailed responses now handled by N8N
                                                # Deprecated code path - removed
                                                
                                                # Clear pending response
                                                session._pending_long_response = None
                                                session._pending_response_chars = None
                                                
                                                # Confirm to user via audio
                                                if session.gemini_client:
                                                    await session.gemini_client.send_text(
                                                        "I've sent the full detailed response to your email.",
                                                        end_of_turn=True
                                                    )
                                                
                                        user_buffer.clear()
                            except Exception as e:
                                logger.error(
                                    f"Error logging user transcript: {e}")

                        async def log_ai_response(text: str):
                            """Log AI's spoken response to database, batching into sentences."""
                            nonlocal full_response_buffer, response_check_task
                            
                            try:
                                if not text.strip():
                                    return

                                # Existing sentence logging
                                ai_buffer.append(text)
                                combined = ''.join(ai_buffer)
                                if any(combined.rstrip().endswith(p) for p in ['.', '!', '?', '。']) or len(ai_buffer) > 15:
                                    if hasattr(self, 'db') and self.db:
                                        self.db.add_conversation_message(
                                            sender='assistant',
                                            message=combined.strip(),
                                            medium='phone_call',
                                            call_sid=call_sid,
                                            direction='outbound'
                                        )
                                        logger.debug(
                                            f"Logged AI sentence for call {call_sid}: {combined[:50]}...")
                                        ai_buffer.clear()
                                
                                # Add to full response buffer
                                full_response_buffer.append(text)
                                
                                # Cancel existing check task
                                if response_check_task and not response_check_task.done():
                                    response_check_task.cancel()
                                
                                # Set timeout to check response when complete
                                async def check_and_handle_long_response():
                                    try:
                                        await asyncio.sleep(2.0)  # Wait 2 seconds for response to complete
                                        if full_response_buffer:
                                            full_response = ''.join(full_response_buffer)
                                            total_chars = len(full_response)
                                            full_response_buffer.clear()
                                            
                                            # Check if response is long (>= 500 chars)
                                            if total_chars >= Config.LONG_MESSAGE_THRESHOLD:
                                                logger.info(f"Long response detected during call ({total_chars} chars, threshold: {Config.LONG_MESSAGE_THRESHOLD})")
                                                
                                                # Get session to send follow-up
                                                session = await self.session_manager.get_session_by_call_sid(call_sid)
                                                if session and session.gemini_client:
                                                    # Generate brief summary using Gemini
                                                    # Include character count in the spoken response
                                                    summary_prompt = f"""I just gave a response that was {total_chars} characters long (the threshold is {Config.LONG_MESSAGE_THRESHOLD} characters). 

Please say: "That response was {total_chars} characters. Here's a brief summary: [2-3 sentence summary of the key points]. Would you like me to send you the full detailed response via email?"

Keep it concise and natural for speaking."""
                                                    
                                                    # Send summary request (this will generate audio)
                                                    await session.gemini_client.send_text(summary_prompt, end_of_turn=True)
                                                    
                                                    # Store full response for potential email sending
                                                    session._pending_long_response = full_response
                                                    session._pending_response_chars = total_chars
                                                    logger.info(f"Stored long response ({total_chars} chars) for potential email sending")
                                            
                                    except asyncio.CancelledError:
                                        pass
                                    except Exception as e:
                                        logger.error(f"Error checking long response: {e}")
                                
                                response_check_task = asyncio.create_task(check_and_handle_long_response())
                                
                            except Exception as e:
                                logger.error(f"Error logging AI response: {e}")

                        # Register conversation logging callbacks
                        call_gemini_client.on_user_transcript = log_user_transcript
                        call_gemini_client.on_text_response = log_ai_response
                        logger.info(
                            f"Registered conversation logging callbacks for call {call_sid}")

                        # Register in active_connections (deprecated but kept for compatibility)
                        self.active_connections[call_sid] = {
                            'stream_sid': stream_sid,
                            'websocket': websocket
                        }

                        # Break out to process media events
                        break

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from Twilio during start: {e}")
                except Exception as e:
                    logger.error(f"Error processing start event: {e}")
                    raise

            # Set up audio callback to send Gemini's audio back to Twilio
            async def send_audio_to_twilio(audio_data: bytes):
                """Send Gemini's audio response back to caller."""
                try:
                    # Gemini outputs audio/pcm at 24kHz by default, Twilio expects μ-law at 8kHz
                    # Step 1: Resample from 24kHz to 8kHz
                    pcm_8k, _ = audioop.ratecv(
                        audio_data,
                        2,      # sample width (16-bit = 2 bytes)
                        1,      # channels (mono)
                        24000,  # input rate (24kHz from Gemini)
                        8000,   # output rate (8kHz for Twilio)
                        None    # state
                    )

                    # Step 2: Convert Linear PCM to μ-law
                    ulaw_audio = audioop.lin2ulaw(pcm_8k, 2)

                    # Encode audio as base64
                    audio_base64 = base64.b64encode(ulaw_audio).decode('utf-8')

                    # Send to Twilio
                    media_message = {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {
                            "payload": audio_base64
                        }
                    }
                    await websocket.send(json.dumps(media_message))

                except Exception as e:
                    logger.error(f"Error sending audio to Twilio: {e}")

            call_gemini_client.on_audio_response = send_audio_to_twilio

            # Process media messages from Twilio
            async for message in websocket:
                try:
                    data = json.loads(message)
                    event = data.get('event')

                    if event == 'media':
                        # Audio from caller
                        payload = data['media']['payload']

                        # Decode from base64
                        audio_data = base64.b64decode(payload)

                        # Convert μ-law (8kHz) to Linear PCM 24kHz
                        # Twilio sends μ-law at 8kHz, Gemini expects PCM at 24kHz
                        try:
                            # Step 1: Convert μ-law to linear PCM (still 8kHz)
                            pcm_8k = audioop.ulaw2lin(
                                audio_data, 2)  # 2 = 16-bit samples

                            # Step 2: Resample from 8kHz to 24kHz
                            pcm_24k, _ = audioop.ratecv(
                                pcm_8k,
                                2,      # sample width (16-bit = 2 bytes)
                                1,      # channels (mono)
                                8000,   # input rate (8kHz from Twilio)
                                24000,  # output rate (24kHz for Gemini)
                                None    # state
                            )

                            # Check if we're reconnecting
                            if self.is_reconnecting or not call_gemini_client.is_connected:
                                # Buffer audio during reconnection
                                if len(self.audio_buffer) < self.max_buffer_size:
                                    self.audio_buffer.append(pcm_24k)
                                continue

                            # Send to Gemini with correct format
                            await call_gemini_client.send_audio(
                                pcm_24k,
                                mime_type="audio/pcm;rate=24000"
                            )

                        except Exception as e:
                            # #region debug log
                            try:
                                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "D", "location": "twilio_media_streams.py:handle_media_stream:audio_error", "message": "Error processing audio", "data": {"error": str(e), "error_type": type(e).__name__, "is_reconnecting": self.is_reconnecting, "is_connected": call_gemini_client.is_connected if call_gemini_client else None, "contains_1008": "1008" in str(e), "contains_1011": "1011" in str(e)}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                            except:
                                pass
                            # #endregion
                            # If connection error, trigger reconnection
                            if "Not connected" in str(e) or "1008" in str(e) or "1011" in str(e):
                                if not self.is_reconnecting:
                                    self.is_reconnecting = True
                                    # #region debug log
                                    try:
                                        with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                                            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "twilio_media_streams.py:handle_media_stream:start_reconnect", "message": "Starting reconnection", "data": {"is_reconnecting": self.is_reconnecting, "buffer_size": len(self.audio_buffer)}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                                    except:
                                        pass
                                    # #endregion
                                    asyncio.create_task(
                                        self._reconnect_gemini())
                                # Buffer this audio
                                if len(self.audio_buffer) < self.max_buffer_size:
                                    pcm_8k = audioop.ulaw2lin(audio_data, 2)
                                    pcm_24k, _ = audioop.ratecv(
                                        pcm_8k, 2, 1, 8000, 24000, None)
                                    self.audio_buffer.append(pcm_24k)
                            else:
                                logger.error(f"Error converting audio: {e}")
                                raise

                    elif event == 'stop':
                        # Stream ended
                        logger.info(f"Stream stopped: {stream_sid}")
                        # Clear active client reference
                        self._active_call_client = None

                        # Flush any remaining buffered transcripts
                        try:
                            if user_buffer and hasattr(self, 'db') and self.db:
                                combined = ''.join(user_buffer).strip()
                                if combined:
                                    self.db.add_conversation_message(
                                        sender='user',
                                        message=combined,
                                        medium='phone_call',
                                        call_sid=call_sid,
                                        direction='inbound'
                                    )
                                    logger.debug(
                                        f"Flushed remaining user text: {combined[:50]}...")
                                    user_buffer.clear()

                            if ai_buffer and hasattr(self, 'db') and self.db:
                                combined = ''.join(ai_buffer).strip()
                                if combined:
                                    self.db.add_conversation_message(
                                        sender='assistant',
                                        message=combined,
                                        medium='phone_call',
                                        call_sid=call_sid,
                                        direction='outbound'
                                    )
                                    logger.debug(
                                        f"Flushed remaining AI text: {combined[:50]}...")
                                    ai_buffer.clear()
                        except Exception as e:
                            logger.error(
                                f"Error flushing transcript buffers: {e}")

                        # Update call status in reminder checker
                        if self.reminder_checker:
                            self.reminder_checker.set_in_call(False)

                        break

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from Twilio: {e}")
                    # #region agent log
                    with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                        import json, time
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"twilio_media_streams.py:793","message":"JSON decode error","data":{"error":str(e)},"timestamp":int(time.time()*1000)})+"\n")
                    # #endregion
                except Exception as e:
                    logger.error(f"Error processing Twilio message: {e}")
                    # #region agent log
                    with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                        import json, time
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ALL","location":"twilio_media_streams.py:796","message":"Error processing message","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
                    # #endregion

        except websockets.exceptions.ConnectionClosed:
            logger.info("Media stream connection closed")
            # #region agent log
            with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                import json, time
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"twilio_media_streams.py:818","message":"WebSocket connection closed","data":{"call_sid":call_sid},"timestamp":int(time.time()*1000)})+"\n")
            # #endregion
        except Exception as e:
            logger.error(f"Error in media stream handler: {e}")
            # #region agent log
            with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                import json, time
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ALL","location":"twilio_media_streams.py:820","message":"Exception in handle_media_stream","data":{"error":str(e),"error_type":type(e).__name__,"call_sid":call_sid},"timestamp":int(time.time()*1000)})+"\n")
            # #endregion
        finally:
            # Cleanup - disconnect Gemini client and terminate session
            if call_gemini_client:
                await call_gemini_client.disconnect()

            # Terminate session in SessionManager
            if session:
                await self.session_manager.terminate_session(session.session_id)
                logger.info(f"Terminated session: {session.session_name}")

            # Clean up active_connections (deprecated but kept for compatibility)
            if call_sid and call_sid in self.active_connections:
                del self.active_connections[call_sid]

    async def _reconnect_gemini(self):
        """Handle Gemini reconnection with buffered audio playback."""
        try:
            logger.warning(
                f"Starting reconnection... (buffer size: {len(self.audio_buffer)})")
            # #region debug log
            try:
                active_client = self._active_call_client or self.gemini_client
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "B", "location": "twilio_media_streams.py:_reconnect_gemini:start", "message": "Reconnection started", "data": {"buffer_size": len(self.audio_buffer), "is_connected": active_client.is_connected if active_client else None}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion

            # Wait a brief moment for connection to stabilize and reconnection to start
            await asyncio.sleep(1.0)  # Increased from 0.5 to give reconnection more time to start

            # The gemini_client handles reconnection in its receive_loop
            # Wait for it to complete - increased timeout to handle slower reconnections
            # Use the active call client, not the main client
            active_client = self._active_call_client or self.gemini_client
            max_wait = 10  # Max 10 seconds (increased from 5)
            waited = 0
            while not active_client.is_connected and waited < max_wait:
                await asyncio.sleep(0.1)
                waited += 0.1
                # #region debug log
                if waited % 1.0 < 0.1:  # Log every second
                    try:
                        with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "B", "location": "twilio_media_streams.py:_reconnect_gemini:waiting", "message": "Waiting for reconnection", "data": {"waited": round(waited, 1), "max_wait": max_wait, "is_connected": active_client.is_connected if active_client else None}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                    except:
                        pass
                # #endregion

            if active_client.is_connected:
                logger.info(
                    f"Reconnection complete, flushing {len(self.audio_buffer)} buffered packets")

                # Flush buffered audio
                buffer_copy = self.audio_buffer.copy()
                self.audio_buffer.clear()

                for audio_chunk in buffer_copy:
                    try:
                        await active_client.send_audio(
                            audio_chunk,
                            mime_type="audio/pcm;rate=24000"
                        )
                        # Small delay between packets
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.error(f"Error flushing buffered audio: {e}")
                        break

                logger.info("Buffer flushed successfully")
                # #region debug log
                try:
                    with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "B", "location": "twilio_media_streams.py:_reconnect_gemini:success", "message": "Reconnection successful", "data": {"is_connected": active_client.is_connected, "buffer_flushed": True}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                except:
                    pass
                # #endregion
            else:
                logger.error("Reconnection timed out")
                # #region debug log
                try:
                    with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "B", "location": "twilio_media_streams.py:_reconnect_gemini:timeout", "message": "Reconnection timed out", "data": {"waited": round(waited, 1), "max_wait": max_wait, "is_connected": active_client.is_connected if active_client else None}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                except:
                    pass
                # #endregion
                self.audio_buffer.clear()  # Clear buffer on timeout

        except Exception as e:
            logger.error(f"Error in reconnection handler: {e}")
            # #region debug log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "twilio_media_streams.py:_reconnect_gemini:error", "message": "Reconnection handler error", "data": {"error": str(e), "is_reconnecting": self.is_reconnecting}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion
            self.audio_buffer.clear()
        finally:
            self.is_reconnecting = False
            # #region debug log
            try:
                active_client = self._active_call_client or self.gemini_client
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "twilio_media_streams.py:_reconnect_gemini:finally", "message": "Reconnection handler finished", "data": {"is_reconnecting": self.is_reconnecting, "is_connected": active_client.is_connected if active_client else None}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion

    async def start_websocket_server(self, host: str = '0.0.0.0', port: int = 5001):
        """Start WebSocket server for Media Streams.

        Args:
            host: Host to bind to
            port: Port for WebSocket server
        """
        logger.info(
            f"Starting Media Streams WebSocket server on {host}:{port}")

        async def websocket_handler(websocket, path=None):
            """Wrapper to log connection attempts."""
            # #region agent log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import json, time
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"twilio_media_streams.py:websocket_handler","message":"WebSocket connection attempt","data":{"remote_addr":websocket.remote_address if hasattr(websocket, 'remote_address') else None,"path":path},"timestamp":int(time.time()*1000)})+"\n")
            except:
                pass
            # #endregion
            logger.info(f"WebSocket connection attempt from {websocket.remote_address if hasattr(websocket, 'remote_address') else 'unknown'}")
            await self.handle_media_stream(websocket)

        self.websocket_server = await websockets.serve(
            websocket_handler,
            host,
            port
        )

        logger.info(f"WebSocket server running on ws://{host}:{port}")

        # Keep server running
        await asyncio.Future()  # Run forever

    async def _get_caller_phone(self, call_sid: str) -> str:
        """Fetch caller's phone number from Twilio Call API.

        Args:
            call_sid: Twilio Call SID

        Returns:
            Caller's phone number or "unknown" if fetch fails
        """
        try:
            call = self.twilio_client.calls(call_sid).fetch()
            # Try different attribute names for the from number
            return getattr(call, 'from_', None) or getattr(call, 'from_formatted', None) or call._properties.get('from', 'unknown')
        except Exception as e:
            logger.error(f"Error fetching call details: {e}")
            return "unknown"

    async def _notify_mate_of_unknown_caller(self, caller_session):
        """Notify Máté when unknown caller rings.

        Args:
            caller_session: AgentSession for the unknown caller
        """
        notification = f"Incoming call from {caller_session.session_name}"

        try:
            await self.router.route_message(
                from_session=caller_session,
                message=notification,
                target="user",
                message_type="notification"
            )
            logger.info(
                f"Notified Máté of unknown caller: {caller_session.session_name}")
        except Exception as e:
            logger.error(f"Error notifying Máté of unknown caller: {e}")

    async def _generate_call_summary(self, transcript: list, goal: dict) -> str:
        """Generate brief AI summary of call outcome (2-3 sentences).

        Args:
            transcript: List of conversation message dicts
            goal: Call goal dictionary

        Returns:
            Brief summary text
        """
        try:
            from google import genai
            from google.genai import types

            # Format transcript
            conversation = "\n".join(
                [f"{msg['sender']}: {msg['message']}" for msg in transcript])

            prompt = f"""Summarize this phone call in 2-3 sentences. Focus on: (1) was the goal achieved? (2) what was decided? (3) any next steps?

Goal: {goal['goal_description']}

Conversation:
{conversation}

Brief summary:"""

            client = genai.Client(
                http_options={"api_version": "v1beta"},
                api_key=Config.GEMINI_API_KEY
            )
            response = await client.aio.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error generating call summary: {e}")
            # Fallback to simple format if AI summary fails
            return f"Call completed. Goal was: {goal['goal_description']}"

    def hangup_call(self, call_sid: str) -> bool:
        """Hang up an active call by its SID.

        Args:
            call_sid: The SID of the call to hang up.

        Returns:
            True if successful, False otherwise.
        """
        try:
            logger.info(f"Attempting to hang up call: {call_sid}")
            self.twilio_client.calls(call_sid).update(status='completed')
            logger.info(f"Successfully hung up call: {call_sid}")
            return True
        except Exception as e:
            # Log error but don't crash. The call might already be over.
            logger.error(f"Error hanging up call {call_sid}: {e}")
            return False

    def make_call(self, to_number: str = None, from_number: str = None, reminder_message: str = None) -> str:
        """Make an outbound call.

        Args:
            to_number: Phone number to call (defaults to config)
            from_number: Twilio phone number to call from (defaults to config)
            reminder_message: Optional reminder message to announce when call connects

        Returns:
            Call SID
        """
        to_number = to_number or Config.TARGET_PHONE_NUMBER
        from_number = from_number or Config.TWILIO_PHONE_NUMBER

        print(f"\n📲 INITIATING OUTBOUND CALL")
        print(f"   From: {from_number}")
        print(f"   To: {to_number}")

        # Store reminder for this call
        if reminder_message:
            self.pending_reminder = reminder_message
            print(f"   🎯 Goal: {reminder_message[:80]}...")
            logger.info(
                f"Storing reminder message for call: {reminder_message}")

        webhook_url = f"{Config.WEBHOOK_BASE_URL}/webhook/voice"
        status_callback = f"{Config.WEBHOOK_BASE_URL}/webhook/status"

        try:
            call = self.twilio_client.calls.create(
                to=to_number,
                from_=from_number,
                url=webhook_url,
                status_callback=status_callback,
                status_callback_event=['initiated',
                                       'ringing', 'answered', 'completed'],
                method='POST'
            )

            logger.info(f"Call initiated: {call.sid} to {to_number}")
            return call.sid

        except Exception as e:
            logger.error(f"Error making call: {e}")
            raise

    def run_server(self, port: int = None, debug: bool = False):
        """Run Flask webhook server.

        Args:
            port: Port to run server on (defaults to config)
            debug: Enable debug mode
        """
        port = port or Config.WEBHOOK_PORT
        logger.info(f"Starting webhook server on port {port}")
        try:
            self.app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)
        except Exception as e:
            raise


class AudioConverter:
    """Utilities for audio format conversion between Twilio and Gemini."""

    @staticmethod
    def mulaw_to_pcm(mulaw_data: bytes) -> bytes:
        """Convert μ-law audio to PCM.

        Args:
            mulaw_data: μ-law encoded audio

        Returns:
            PCM audio data
        """
        # TODO: Implement μ-law to PCM conversion
        # For now, returning as-is
        # May need audioop library: audioop.ulaw2lin(mulaw_data, 2)
        return mulaw_data

    @staticmethod
    def pcm_to_mulaw(pcm_data: bytes) -> bytes:
        """Convert PCM audio to μ-law.

        Args:
            pcm_data: PCM audio data

        Returns:
            μ-law encoded audio
        """
        # TODO: Implement PCM to μ-law conversion
        # For now, returning as-is
        # May need audioop library: audioop.lin2ulaw(pcm_data, 2)
        return pcm_data

    @staticmethod
    def resample_audio(audio_data: bytes, from_rate: int, to_rate: int) -> bytes:
        """Resample audio between different sample rates.

        Args:
            audio_data: Input audio
            from_rate: Source sample rate
            to_rate: Target sample rate

        Returns:
            Resampled audio
        """
        # TODO: Implement resampling using scipy or librosa
        # For now, returning as-is
        return audio_data
