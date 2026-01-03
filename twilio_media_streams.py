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

    def __init__(self, gemini_client: GeminiLiveClient, reminder_checker=None, database=None):
        """Initialize handler.

        Args:
            gemini_client: GeminiLiveClient instance
            reminder_checker: Optional ReminderChecker instance for call status updates
            database: Optional Database instance for conversation logging
        """
        self.gemini_client = gemini_client
        self.twilio_client = Client(
            Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
        self.app = Flask(__name__)
        self._setup_routes()
        self.reminder_checker = reminder_checker
        self.db = database

        # WebSocket state
        self.websocket_server = None
        self.active_connections = {}

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
                    websocket_url = Config.WEBSOCKET_URL.replace(
                        "wss://", "").replace("https://", "").replace("http://", "")
                    stream = Stream(url=f'wss://{websocket_url}/media-stream')
                else:
                    # Fallback: assume same domain (won't work with separate tunnels)
                    websocket_base = Config.WEBHOOK_BASE_URL.replace(
                        "https://", "").replace("http://", "")
                    stream = Stream(url=f'wss://{websocket_base}/media-stream')
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
                    self.db.complete_call_goal(goal['id'], result=f"Call completed ({call_duration}s)")
                    logger.info(f"Goal call {goal['id']} completed, will call Máté back")

                    # Schedule callback to Máté with summary
                    import threading
                    def call_back_mate():
                        import time
                        time.sleep(2)  # Brief delay before calling back
                        contact_name = goal['contact_name']
                        goal_desc = goal['goal_description']
                        callback_message = f"Report to Máté: You just completed a call with {contact_name} regarding '{goal_desc}'. The call lasted {call_duration} seconds. Provide a brief summary of what happened during the call and any important information or next steps."
                        try:
                            self.make_call(
                                to_number=Config.TARGET_PHONE_NUMBER,
                                reminder_message=callback_message
                            )
                            logger.info(f"Called Máté back after goal call completion")
                        except Exception as e:
                            logger.error(f"Error calling Máté back: {e}")

                    threading.Thread(target=call_back_mate, daemon=True).start()

            # Track if call was answered for reminder delivery
            if self.reminder_checker:
                if call_status == 'in-progress':
                    # Call was answered
                    self.reminder_checker.set_call_answered(True)
                elif call_status in ['failed', 'busy', 'no-answer', 'canceled']:
                    # Call was not answered
                    self.reminder_checker.set_call_answered(False)

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
        """Handle WebSocket connection from Twilio Media Streams.

        Args:
            websocket: WebSocket connection
        """
        # Note: 'path' parameter removed - websockets library no longer passes it in newer versions
        call_sid = None
        stream_sid = None

        try:
            print(f"\n🔌 WEBSOCKET CONNECTED")
            logger.info("Media stream connected")

            # Connect to Gemini Live
            print(f"   Connecting to Gemini Live...")
            await self.gemini_client.connect()
            print(f"   ✅ Gemini Live connected")

            # Send current time to Gemini for accurate time awareness (silently in system context)
            from datetime import datetime
            current_time = datetime.now().strftime("%I:%M %p")
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            time_msg = f"[System: Current time is {current_time} on {current_date}. Use this for any time-related questions or reminders.]"
            await self.gemini_client.send_text(time_msg, end_of_turn=True)
            print(f"   ⏰ Sent time context: {current_time} on {current_date}")
            logger.info(
                f"Sent current time context to Gemini: {current_time} on {current_date}")

            # If this is a reminder call, send the reminder message to Gemini
            if self.pending_reminder:
                # Check if this is a goal-based call (contains "CALL OBJECTIVE")
                if "CALL OBJECTIVE" in self.pending_reminder:
                    # This is an outbound goal call - TARS is speaking to the contact, not Máté
                    reminder_msg = f"[System: You are now on a call with the person mentioned in this objective. Speak to THEM directly. This is NOT a call with Máté.]\n\n{self.pending_reminder}"
                else:
                    # This is a reminder call to Máté
                    reminder_msg = f"You need to announce this reminder to the user: {self.pending_reminder}"
                await self.gemini_client.send_text(reminder_msg, end_of_turn=True)
                print(f"   🎯 Goal message sent to TARS")
                print(f"   {self.pending_reminder[:100]}...")
                logger.info(
                    f"Sent reminder to Gemini: {self.pending_reminder}")
                self.pending_reminder = None  # Clear after sending

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

            self.gemini_client.on_audio_response = send_audio_to_twilio

            # Set up conversation logging callbacks
            async def log_user_transcript(text: str):
                """Log user's spoken text to database."""
                try:
                    if hasattr(self, 'db') and self.db and text.strip():
                        self.db.add_conversation_message(
                            sender='user',
                            message=text,
                            medium='phone_call',
                            call_sid=call_sid,
                            direction='inbound'
                        )
                        logger.debug(f"Logged user transcript: {text[:50]}...")
                except Exception as e:
                    logger.error(f"Error logging user transcript: {e}")

            async def log_ai_response(text: str):
                """Log AI's spoken response to database."""
                try:
                    if hasattr(self, 'db') and self.db and text.strip():
                        self.db.add_conversation_message(
                            sender='assistant',
                            message=text,
                            medium='phone_call',
                            call_sid=call_sid,
                            direction='outbound'
                        )
                        logger.debug(f"Logged AI response: {text[:50]}...")
                except Exception as e:
                    logger.error(f"Error logging AI response: {e}")

            # Register conversation logging callbacks
            self.gemini_client.on_user_transcript = log_user_transcript
            self.gemini_client.on_text_response = log_ai_response

            # Process messages from Twilio
            async for message in websocket:
                try:
                    data = json.loads(message)
                    event = data.get('event')

                    if event == 'start':
                        # Stream started
                        call_sid = data['start']['callSid']
                        stream_sid = data['start']['streamSid']
                        self.active_connections[call_sid] = {
                            'stream_sid': stream_sid,
                            'websocket': websocket
                        }
                        logger.info(
                            f"Stream started: {stream_sid} for call {call_sid}")

                        # Update call status in reminder checker
                        if self.reminder_checker:
                            self.reminder_checker.set_in_call(True)

                    elif event == 'media':
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
                            if self.is_reconnecting or not self.gemini_client.is_connected:
                                # Buffer audio during reconnection
                                if len(self.audio_buffer) < self.max_buffer_size:
                                    self.audio_buffer.append(pcm_24k)
                                continue

                            # Send to Gemini with correct format
                            await self.gemini_client.send_audio(
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
            # Cleanup
            await self.gemini_client.disconnect()
            if call_sid and call_sid in self.active_connections:
                del self.active_connections[call_sid]

            # Update call status in reminder checker
            if self.reminder_checker:
                self.reminder_checker.set_in_call(False)

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
