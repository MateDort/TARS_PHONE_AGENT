"""Gemini Live Audio client with native voice, Google Search, and function calling."""
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from google import genai
from google.genai import types
from config import Config

logger = logging.getLogger(__name__)


class GeminiLiveClient:
    """Client for Gemini 2.5 Flash Native Audio with agentic capabilities."""
    
    def __init__(self, api_key: str, system_instruction: str = None):
        """Initialize Gemini Live Audio client.
        
        Args:
            api_key: Gemini API key
            system_instruction: System prompt for the agent
        """
        self.api_key = api_key
        self.client = genai.Client(
            http_options={"api_version": "v1beta"},
            api_key=api_key
        )
        
        # Model with native audio support
        self.model = "models/gemini-2.5-flash-native-audio-preview-12-2025"
        
        # Default system instruction
        self.system_instruction = system_instruction or """You are a helpful AI assistant on a phone call. 
Keep responses concise and natural for phone conversations. 
You have access to Google Search for real-time information and can call specialized functions when needed.
Be conversational, friendly, and helpful."""
        
        # Function registry for sub-agents
        self.function_handlers: Dict[str, Callable] = {}
        self.function_declarations: List[Dict] = []
        
        # Session state
        self.session = None
        self._session_context = None  # Store the context manager
        self.is_connected = False
        self._receive_task = None  # Track receive loop task to avoid duplicates
        
        # Audio callbacks
        self.on_audio_response: Optional[Callable] = None
        self.on_text_response: Optional[Callable] = None
        self.on_user_transcript: Optional[Callable] = None

        # Sentence buffering for cleaner console output
        self._ai_console_buffer = []
        self._user_console_buffer = []
        
        # Full response buffering for complete response printing
        self._full_response_buffer = []
        self._response_timeout_task = None
        
    def register_function(self, declaration: Dict, handler: Callable):
        """Register a function for the agent to call.
        
        Args:
            declaration: Function declaration in Gemini format
            handler: Async function to handle the call
            
        Example declaration:
        {
            "name": "search_database",
            "description": "Search the customer database",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
        """
        self.function_declarations.append(declaration)
        self.function_handlers[declaration["name"]] = handler
        logger.info(f"Registered function: {declaration['name']}")
    
    def _build_config(self, permission_level: str = "full") -> types.LiveConnectConfig:
        """Build configuration for Gemini Live session with permission filtering.

        Args:
            permission_level: "full" for all functions, "limited" for restricted access

        Returns:
            LiveConnectConfig with voice, tools, and filtered function calling
        """
        # Filter function declarations based on permission level
        filtered_declarations = self.function_declarations

        if permission_level == "limited":
            # Import security module for filtering
            try:
                from security import filter_functions_by_permission, PermissionLevel
                filtered_declarations = filter_functions_by_permission(
                    PermissionLevel.LIMITED,
                    self.function_declarations
                )
                logger.info(f"Filtered functions for LIMITED access: {len(filtered_declarations)}/{len(self.function_declarations)}")
            except ImportError:
                # Security module not available, use all functions
                logger.warning("Security module not available, using all functions")

        # Build tools list
        tools = [
            {'google_search': {}},  # Enable Google Search
        ]

        # Add filtered function declarations if any
        if filtered_declarations:
            tools.append({
                "function_declarations": filtered_declarations
            })

        # Build config with proper format for newer Gemini API
        config = types.LiveConnectConfig(
            # Enable audio response
            response_modalities=["AUDIO"],

            # System instructions - API now expects this format
            system_instruction=types.Content(
                parts=[types.Part(text=self.system_instruction)]
            ) if self.system_instruction else None,

            # Voice and audio settings - explicitly configure sample rate
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Puck"  # Female voice
                    )
                )
            ),

            # Enable transcription for both input (user) and output (AI) audio
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),

            # Tools (Google Search + custom functions)
            tools=tools
        )

        return config

    async def connect(self, permission_level: str = "full"):
        """Connect to Gemini Live session with permission filtering.

        Args:
            permission_level: "full" for all functions, "limited" for restricted access
        """
        try:
            config = self._build_config(permission_level)
            
            # Store the context manager and enter it
            self._session_context = self.client.aio.live.connect(
                model=self.model,
                config=config
            )
            self.session = await self._session_context.__aenter__()
            
            self.is_connected = True
            logger.info("Connected to Gemini Live Audio")
            # #region debug log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "E", "location": "gemini_live_client.py:connect:success", "message": "Connection established", "data": {"is_connected": self.is_connected, "has_session": self.session is not None}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion
            
            # Start receiving responses (only if not already running)
            if self._receive_task is None or self._receive_task.done():
                self._receive_task = asyncio.create_task(self._receive_loop())
                logger.debug("Started new receive loop task")
            else:
                logger.debug("Receive loop already running, not starting new one")
            
        except Exception as e:
            logger.error(f"Failed to connect to Gemini Live: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Gemini Live session."""
        if self._session_context and self.is_connected:
            try:
                # Exit the context manager properly
                await self._session_context.__aexit__(None, None, None)
                self.is_connected = False
                self.session = None
                self._session_context = None
                # Flush any remaining buffered console output
                if self._ai_console_buffer:
                    combined = ''.join(self._ai_console_buffer).strip()
                    if combined:
                        print(f"\n🤖 TARS: {combined}")
                        logger.info(f"AI: {combined}")
                    self._ai_console_buffer.clear()

                if self._user_console_buffer:
                    combined = ''.join(self._user_console_buffer).strip()
                    if combined:
                        print(f"\n👤 USER: {combined}")
                        logger.info(f"User: {combined}")
                    self._user_console_buffer.clear()

                logger.info("Disconnected from Gemini Live")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
    
    async def send_audio(self, audio_data: bytes, mime_type: str = "audio/pcm"):
        """Send audio data to Gemini.
        
        Args:
            audio_data: Raw audio bytes
            mime_type: Audio format (default: audio/pcm for μ-law)
        """
        if not self.session or not self.is_connected:
            raise RuntimeError("Not connected to Gemini Live")
        
        try:
            await self.session.send(
                input={"data": audio_data, "mime_type": mime_type},
                end_of_turn=False
            )
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            # #region debug log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "D", "location": "gemini_live_client.py:send_audio:error", "message": "Error sending audio", "data": {"error": str(e), "error_type": type(e).__name__, "is_connected": self.is_connected, "has_session": self.session is not None, "contains_1008": "1008" in str(e), "contains_1011": "1011" in str(e)}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion
            raise
    
    async def send_text(self, text: str, end_of_turn: bool = True):
        """Send text input to Gemini.

        Args:
            text: Text message
            end_of_turn: Whether this ends the user's turn
        """
        if not self.session or not self.is_connected:
            raise RuntimeError("Not connected to Gemini Live")

        try:
            await self.session.send(
                input=text,
                end_of_turn=end_of_turn
            )
        except Exception as e:
            logger.error(f"Error sending text: {e}")
            raise

    async def send_text_or_message(self, text: str, end_of_turn: bool = True):
        """Decide whether to speak text or send as message based on length/complexity.

        Args:
            text: Response text to deliver
            end_of_turn: Whether this ends the turn

        Returns:
            True if sent via message, False if spoken
        """
        # Estimate speaking time (rough: 150 words per minute)
        word_count = len(text.split())
        estimated_seconds = (word_count / 150) * 60

        # Thresholds
        MAX_SPEAKING_SECONDS = 30  # Don't speak for more than 30 seconds
        LONG_RESPONSE_INDICATOR_WORDS = ['breakdown', 'details', 'list', 'steps', 'explanation']

        should_message = False
        reason = ""

        # Check if response is too long
        if estimated_seconds > MAX_SPEAKING_SECONDS:
            should_message = True
            reason = "detailed explanation"

        # Check if response contains structured content (lists, breakdowns)
        if any(word in text.lower() for word in LONG_RESPONSE_INDICATOR_WORDS):
            if word_count > 50:  # Only if substantial
                should_message = True
                reason = "structured breakdown"

        # Check for multiple line breaks (formatted content)
        if text.count('\n') > 5:
            should_message = True
            reason = "formatted content"

        if should_message:
            # Send brief summary via voice + full content via message
            brief_summary = self._generate_brief_summary(text)

            # Speak brief version
            await self.send_text(
                f"{brief_summary} I've sent you the full {reason} in a message, sir.",
                end_of_turn=False
            )

            # Send full content via KIPP
            if self._session_context and hasattr(self._session_context, 'session_id'):
                try:
                    from sub_agents_tars import KIPPAgent
                    n8n_agent = KIPPAgent()
                    n8n_message = f"Send email to {Config.TARGET_EMAIL} with subject 'TARS {reason.title()}' and body '{text}'"
                    await n8n_agent.execute({"message": n8n_message})
                except Exception as e:
                    logger.error(f"Error sending detailed response via KIPP: {e}")

            return True  # Handled via message

        else:
            # Short enough to speak
            await self.send_text(text, end_of_turn=end_of_turn)
            return False

    def _generate_brief_summary(self, long_text: str) -> str:
        """Extract or generate brief summary of long content.

        Args:
            long_text: Full text to summarize

        Returns:
            Brief summary (first sentence or 100 chars)
        """
        # Take first sentence or first 100 characters
        sentences = long_text.split('. ')
        if sentences:
            brief = sentences[0]
            if len(brief) > 100:
                brief = brief[:100] + "..."
            return brief
        else:
            return long_text[:100] + "..."
    
    async def _receive_loop(self):
        """Main loop for receiving responses from Gemini."""
        try:
            while self.is_connected:
                try:
                    async for response in self.session.receive():
                        # Handle audio output
                        if response.data:
                            if self.on_audio_response:
                                await self.on_audio_response(response.data)
                        
                        # Handle transcriptions
                        if response.server_content:
                            # AI's spoken text
                            if response.server_content.output_transcription:
                                text = response.server_content.output_transcription.text

                                # Add to full response buffer
                                self._full_response_buffer.append(text)
                                
                                # Cancel existing timeout task
                                if self._response_timeout_task and not self._response_timeout_task.done():
                                    self._response_timeout_task.cancel()
                                
                                # Set timeout to print full response when complete
                                async def print_full_response():
                                    try:
                                        await asyncio.sleep(2.0)  # Wait 2 seconds for more text
                                        if self._full_response_buffer:
                                            full_response = ''.join(self._full_response_buffer)
                                            total_chars = len(full_response)
                                            
                                            # Print full response with character count
                                            print(f"\n🤖 TARS ({total_chars} chars): {full_response}")
                                            logger.info(f"AI (full response, {total_chars} chars): {full_response}")
                                            
                                            self._full_response_buffer.clear()
                                    except asyncio.CancelledError:
                                        pass
                                
                                self._response_timeout_task = asyncio.create_task(print_full_response())
                                
                                # Keep sentence buffer for real-time feedback (optional, just for debug)
                                self._ai_console_buffer.append(text)
                                combined = ''.join(self._ai_console_buffer)
                                if any(combined.rstrip().endswith(p) for p in ['.', '!', '?', '。']) or len(self._ai_console_buffer) > 15:
                                    # Just log for debugging, don't print (full response will be printed)
                                    logger.debug(f"AI sentence: {combined}")
                                    self._ai_console_buffer.clear()

                                # Always call the callback (it has its own buffering)
                                if self.on_text_response:
                                    await self.on_text_response(text)

                            # User's spoken text
                            if hasattr(response.server_content, 'input_transcription') and response.server_content.input_transcription:
                                user_text = response.server_content.input_transcription.text

                                # Buffer for console output
                                self._user_console_buffer.append(user_text)
                                combined = ''.join(self._user_console_buffer)

                                # Print complete sentences only
                                if any(combined.rstrip().endswith(p) for p in ['.', '!', '?', '。']) or len(self._user_console_buffer) > 15:
                                    print(f"\n👤 USER: {combined}")
                                    logger.info(f"User: {combined}")
                                    self._user_console_buffer.clear()

                                # Always call the callback (it has its own buffering)
                                if self.on_user_transcript:
                                    await self.on_user_transcript(user_text)
                        
                        # Handle function calls from the model
                        if response.tool_call:
                            await self._handle_function_calls(response.tool_call)
                    
                    # If we reach here, the async for loop completed naturally (iterator exhausted)
                    # This happens when Gemini finishes a turn. Continue the while loop to keep listening.
                    await asyncio.sleep(0.1)  # Brief pause before continuing
                    
                except StopAsyncIteration:
                    # Iterator explicitly stopped, continue
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
            # #region debug log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "gemini_live_client.py:_receive_loop:error", "message": "Error in receive loop", "data": {"error": str(e), "error_type": type(e).__name__, "is_connected": self.is_connected, "has_session_context": self._session_context is not None, "contains_1008": "1008" in str(e), "contains_1011": "1011" in str(e)}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion
            
            # Only attempt reconnection if this wasn't a clean shutdown
            should_reconnect = self.is_connected and self._session_context and ("1008" in str(e) or "1011" in str(e))
            # #region debug log
            try:
                with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "gemini_live_client.py:_receive_loop:should_reconnect", "message": "Reconnection decision", "data": {"should_reconnect": should_reconnect, "is_connected": self.is_connected, "has_session_context": self._session_context is not None}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion
            self.is_connected = False
            
            if should_reconnect:
                logger.warning("Connection lost unexpectedly, attempting quick reconnect...")
                try:
                    # Clean up old session
                    try:
                        await self._session_context.__aexit__(None, None, None)
                    except:
                        pass
                    self.session = None
                    self._session_context = None
                    
                    # Quick reconnect without long delay
                    await asyncio.sleep(0.3)
                    
                    # Reconnect
                    await self.connect()
                    logger.info("Successfully reconnected to Gemini Live")
                    # #region debug log
                    try:
                        with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                            import json
                            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "E", "location": "gemini_live_client.py:_receive_loop:reconnect_success", "message": "Reconnection successful", "data": {"is_connected": self.is_connected, "has_session": self.session is not None}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                    except:
                        pass
                    # #endregion
                    # After reconnection, exit this loop - the new receive loop started by connect() will handle responses
                    # This prevents duplicate receive loops
                    return
                except Exception as reconnect_error:
                    logger.error(f"Failed to reconnect: {reconnect_error}")
                    # #region debug log
                    try:
                        with open('/Users/matedort/TARS_PHONE_AGENT/.cursor/debug.log', 'a') as f:
                            import json
                            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "E", "location": "gemini_live_client.py:_receive_loop:reconnect_failed", "message": "Reconnection failed", "data": {"error": str(reconnect_error), "is_connected": self.is_connected}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                    except:
                        pass
                    # #endregion
    
    async def _handle_function_calls(self, tool_call):
        """Handle function calls from Gemini with task planning.
        
        Args:
            tool_call: Tool call from Gemini response
        """
        # Collect all function calls
        function_calls = []
        for fc in tool_call.function_calls:
            function_calls.append({
                "name": fc.name,
                "args": fc.args,
                "id": fc.id,
                "fc": fc  # Keep reference to original
            })
        
        # Plan and order function calls
        if len(function_calls) > 1:
            try:
                from task_planner import TaskPlanner
                planner = TaskPlanner()
                planned_calls = planner.plan_tasks(function_calls)
                logger.info(f"Planned {len(function_calls)} function calls, reordered to {len(planned_calls)}")
                function_calls = planned_calls
            except Exception as e:
                logger.warning(f"Task planning failed, executing in original order: {e}")
        
        # Execute planned function calls in order
        for call_data in function_calls:
            fn_name = call_data["name"]
            args = call_data["args"]
            fc = call_data["fc"]

            print(f"\n⚙️  FUNCTION CALL: {fn_name}")
            print(f"   Args: {args}")
            logger.info(f"Function call: {fn_name}({args})")

            # Check if we have a handler for this function
            if fn_name in self.function_handlers:
                try:
                    # Call the handler
                    handler = self.function_handlers[fn_name]

                    # Execute handler (could be sync or async)
                    if asyncio.iscoroutinefunction(handler):
                        result = await handler(args)
                    else:
                        result = handler(args)

                    # Send response back to Gemini
                    function_response = types.FunctionResponse(
                        id=fc.id,
                        name=fn_name,
                        response={"result": str(result)}
                    )

                    await self.session.send(input=function_response)
                    print(f"   ✅ Result: {result}")
                    logger.info(f"Function {fn_name} completed: {result}")
                    
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    logger.error(f"Error executing function {fn_name}: {e}")

                    # Send error response
                    error_response = types.FunctionResponse(
                        id=fc.id,
                        name=fn_name,
                        response={"error": str(e)}
                    )
                    await self.session.send(input=error_response)
            else:
                print(f"   ⚠️  No handler registered for function: {fn_name}")
                logger.warning(f"No handler registered for function: {fn_name}")
                
                # Send error response
                error_response = types.FunctionResponse(
                    id=fc.id,
                    name=fn_name,
                    response={"error": f"No handler for {fn_name}"}
                )
                await self.session.send(input=error_response)
    
    async def send_notification(self, message: str):
        """Send a system notification to the agent.
        
        Useful for background tasks to inform the agent of completion.
        
        Args:
            message: Notification message
        """
        if self.session and self.is_connected:
            await self.session.send(
                input=f"System Notification: {message}",
                end_of_turn=True
            )


class SubAgent:
    """Base class for sub-agents."""
    
    def __init__(self, name: str, description: str):
        """Initialize sub-agent.
        
        Args:
            name: Agent name
            description: What this agent does
        """
        self.name = name
        self.description = description
    
    async def execute(self, args: Dict[str, Any]) -> Any:
        """Execute the agent's task.
        
        Args:
            args: Arguments from function call
            
        Returns:
            Result to send back to main agent
        """
        raise NotImplementedError("Subclasses must implement execute()")

