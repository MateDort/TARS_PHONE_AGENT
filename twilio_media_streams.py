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

        # WebSocket state (deprecated - sessions now managed by SessionManager)
        self.websocket_server = None
        self.active_connections = {}  # Kept for backward compatibility

        # Pending reminder message for auto-calls
        self.pending_reminder = None

        # Audio buffer for seamless reconnection
        self.audio_buffer = []
        self.is_reconnecting = False
        # Buffer up to 50 packets (~1 second of audio)
        self.max_buffer_size = 50

    def _setup_routes(self):
        """Set up Flask routes for Twilio webhooks."""

        @self.app.route('/webhook/voice', methods=['POST'])
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

                response = VoiceResponse()

                # Optional: Play a brief greeting
                response.say("Hello, connecting you now", voice='Polly.Joanna')

                # Connect to Media Streams WebSocket
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
                    asyncio.create_task(send_callback())

                    # Terminate session in SessionManager (if not already done in finally block)
                    async def terminate_session():
                        try:
                            await self.session_manager.terminate_session_by_call_sid(call_sid)
                        except Exception as e:
                            logger.debug(
                                f"Session already terminated or not found: {e}")

                    if self.session_manager:
                        asyncio.create_task(terminate_session())

            if call_status in ['completed', 'failed', 'busy', 'no-answer']:
                # Cleanup connection
                if call_sid in self.active_connections:
                    del self.active_connections[call_sid]

            return Response('', mimetype='text/xml')

        @self.app.route('/webhook/sms', methods=['POST'])
        def sms_webhook():
            """Handle incoming SMS messages."""
            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "twilio_media_streams.py:sms_webhook:entry", "message": "SMS webhook called", "data": {
                            "has_messaging_handler": hasattr(self, 'messaging_handler'), "event_loop_running": asyncio.get_running_loop() if asyncio._get_running_loop() else None}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion

            from_number = request.form.get('From')
            message_body = request.form.get('Body')
            message_sid = request.form.get('MessageSid')

            logger.info(f"Received SMS from {from_number}: {message_body}")

            # Process message asynchronously if messaging handler is available
            if hasattr(self, 'messaging_handler') and self.messaging_handler:
                # #region debug log
                try:
                    with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                        import json
                        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "twilio_media_streams.py:sms_webhook:before_create_task",
                                "message": "Attempting create_task", "data": {"has_loop": asyncio._get_running_loop() is not None}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                except:
                    pass
                # #endregion

                # Create async task to process message
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # No running loop - need to run in new event loop
                    # #region debug log
                    try:
                        with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                            import json
                            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "twilio_media_streams.py:sms_webhook:no_loop",
                                    "message": "No running event loop detected", "data": {}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                    except:
                        pass
                    # #endregion

                    # Run async function in new event loop using thread pool
                    import threading

                    def run_async():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            new_loop.run_until_complete(
                                self.messaging_handler.process_incoming_message(
                                    from_number=from_number,
                                    message_body=message_body,
                                    medium='sms',
                                    message_sid=message_sid
                                )
                            )
                        finally:
                            new_loop.close()

                    thread = threading.Thread(target=run_async, daemon=True)
                    thread.start()
                else:
                    # Running loop exists - can use create_task
                    asyncio.create_task(
                        self.messaging_handler.process_incoming_message(
                            from_number=from_number,
                            message_body=message_body,
                            medium='sms',
                            message_sid=message_sid
                        )
                    )
            else:
                logger.warning(
                    "MessagingHandler not initialized - cannot process SMS")

            # Return empty response (Twilio will receive reply separately)
            return Response('', status=200)

        @self.app.route('/webhook/whatsapp', methods=['POST'])
        def whatsapp_webhook():
            """Handle incoming WhatsApp messages."""
            from_number = request.form.get('From')
            message_body = request.form.get('Body')
            message_sid = request.form.get('MessageSid')

            logger.info(
                f"Received WhatsApp from {from_number}: {message_body}")

            # Process message asynchronously if messaging handler is available
            if hasattr(self, 'messaging_handler') and self.messaging_handler:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # No running loop - need to run in new event loop
                    import threading

                    def run_async():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            new_loop.run_until_complete(
                                self.messaging_handler.process_incoming_message(
                                    from_number=from_number,
                                    message_body=message_body,
                                    medium='whatsapp',
                                    message_sid=message_sid
                                )
                            )
                        finally:
                            new_loop.close()

                    thread = threading.Thread(target=run_async, daemon=True)
                    thread.start()
                else:
                    # Running loop exists - can use create_task
                    asyncio.create_task(
                        self.messaging_handler.process_incoming_message(
                            from_number=from_number,
                            message_body=message_body,
                            medium='whatsapp',
                            message_sid=message_sid
                        )
                    )
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
                                call = self.twilio_client.calls(call_sid).fetch()
                                to_number = getattr(call, 'to', None) or getattr(call, 'to_formatted', None) or call._properties.get('to', from_number)
                                auth_phone = to_number
                                print(f"   📱 Calling: {to_number} (outbound reminder)")
                            except Exception as e:
                                logger.error(f"Error fetching TO number: {e}")
                                auth_phone = from_number
                        else:
                            # Inbound call or outbound goal call - use FROM number
                            auth_phone = from_number
                            print(f"   📱 Caller: {from_number}")

                        # CREATE SESSION via SessionManager
                        # This handles authentication, naming, and permission-filtered function declarations
                        session = await self.session_manager.create_session(
                            call_sid=call_sid,
                            phone_number=auth_phone,
                            websocket=websocket,
                            stream_sid=stream_sid,
                            purpose=self.pending_reminder if "CALL OBJECTIVE" in (
                                self.pending_reminder or "") else None
                        )

                        print(
                            f"   👤 Session: {session.session_name} ({session.permission_level.value} access)")
                        logger.info(
                            f"Created session: {session.session_name} with {session.permission_level.value} permissions")

                        # Use session's dedicated Gemini client (already configured with permissions)
                        call_gemini_client = session.gemini_client

                        # Connect to Gemini with permission level
                        print(f"   Connecting to Gemini Live...")
                        await call_gemini_client.connect(permission_level=session.permission_level.value)
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
                            self.pending_reminder = None

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
                                        user_buffer.clear()
                            except Exception as e:
                                logger.error(
                                    f"Error logging user transcript: {e}")

                        async def log_ai_response(text: str):
                            """Log AI's spoken response to database, batching into sentences."""
                            try:
                                if not text.strip():
                                    return

                                ai_buffer.append(text)

                                # Check if this completes a sentence (ends with punctuation or is long enough)
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
                            # If connection error, trigger reconnection
                            if "Not connected" in str(e) or "1008" in str(e):
                                if not self.is_reconnecting:
                                    self.is_reconnecting = True
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
                except Exception as e:
                    logger.error(f"Error processing Twilio message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("Media stream connection closed")
        except Exception as e:
            logger.error(f"Error in media stream handler: {e}")
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

            # Wait a brief moment for connection to stabilize
            await asyncio.sleep(0.5)

            # The gemini_client handles reconnection in its receive_loop
            # Wait for it to complete
            max_wait = 5  # Max 5 seconds
            waited = 0
            while not self.gemini_client.is_connected and waited < max_wait:
                await asyncio.sleep(0.1)
                waited += 0.1

            if self.gemini_client.is_connected:
                logger.info(
                    f"Reconnection complete, flushing {len(self.audio_buffer)} buffered packets")

                # Flush buffered audio
                buffer_copy = self.audio_buffer.copy()
                self.audio_buffer.clear()

                for audio_chunk in buffer_copy:
                    try:
                        await self.gemini_client.send_audio(
                            audio_chunk,
                            mime_type="audio/pcm;rate=24000"
                        )
                        # Small delay between packets
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        logger.error(f"Error flushing buffered audio: {e}")
                        break

                logger.info("Buffer flushed successfully")
            else:
                logger.error("Reconnection timed out")
                self.audio_buffer.clear()  # Clear buffer on timeout

        except Exception as e:
            logger.error(f"Error in reconnection handler: {e}")
            self.audio_buffer.clear()
        finally:
            self.is_reconnecting = False

    async def start_websocket_server(self, host: str = '0.0.0.0', port: int = 5001):
        """Start WebSocket server for Media Streams.

        Args:
            host: Host to bind to
            port: Port for WebSocket server
        """
        logger.info(
            f"Starting Media Streams WebSocket server on {host}:{port}")

        self.websocket_server = await websockets.serve(
            self.handle_media_stream,
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
            import google.generativeai as genai

            # Format transcript
            conversation = "\n".join(
                [f"{msg['sender']}: {msg['message']}" for msg in transcript])

            prompt = f"""Summarize this phone call in 2-3 sentences. Focus on: (1) was the goal achieved? (2) what was decided? (3) any next steps?

Goal: {goal['goal_description']}

Conversation:
{conversation}

Brief summary:"""

            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = await model.generate_content_async(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error generating call summary: {e}")
            # Fallback to simple format if AI summary fails
            return f"Call completed. Goal was: {goal['goal_description']}"

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
