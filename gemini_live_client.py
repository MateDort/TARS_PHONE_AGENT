"""Gemini Live Audio client with native voice, Google Search, and function calling."""
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from google import genai
from google.genai import types

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
        
        # Audio callbacks
        self.on_audio_response: Optional[Callable] = None
        self.on_text_response: Optional[Callable] = None
        self.on_user_transcript: Optional[Callable] = None
        
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
    
    def _build_config(self) -> types.LiveConnectConfig:
        """Build configuration for Gemini Live session.
        
        Returns:
            LiveConnectConfig with voice, tools, and function calling
        """
        # Build tools list
        tools = [
            {'google_search': {}},  # Enable Google Search
        ]
        
        # Add custom function declarations if any
        if self.function_declarations:
            tools.append({
                "function_declarations": self.function_declarations
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
            
            # Tools (Google Search + custom functions)
            tools=tools
        )
        
        return config
    
    async def connect(self):
        """Connect to Gemini Live session."""
        try:
            config = self._build_config()
            
            # Store the context manager and enter it
            self._session_context = self.client.aio.live.connect(
                model=self.model,
                config=config
            )
            self.session = await self._session_context.__aenter__()
            
            self.is_connected = True
            logger.info("Connected to Gemini Live Audio")
            
            # Start receiving responses
            asyncio.create_task(self._receive_loop())
            
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
                                logger.info(f"AI: {text}")
                                if self.on_text_response:
                                    await self.on_text_response(text)
                            
                            # User's spoken text
                            if hasattr(response.server_content, 'input_transcription') and response.server_content.input_transcription:
                                user_text = response.server_content.input_transcription.text
                                logger.info(f"User: {user_text}")
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
            
            # Only attempt reconnection if this wasn't a clean shutdown
            should_reconnect = self.is_connected and self._session_context and "1008" in str(e)
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
                except Exception as reconnect_error:
                    logger.error(f"Failed to reconnect: {reconnect_error}")
    
    async def _handle_function_calls(self, tool_call):
        """Handle function calls from Gemini.
        
        Args:
            tool_call: Tool call from Gemini response
        """
        for fc in tool_call.function_calls:
            fn_name = fc.name
            args = fc.args
            
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
                    logger.info(f"Function {fn_name} completed: {result}")
                    
                except Exception as e:
                    logger.error(f"Error executing function {fn_name}: {e}")
                    
                    # Send error response
                    error_response = types.FunctionResponse(
                        id=fc.id,
                        name=fn_name,
                        response={"error": str(e)}
                    )
                    await self.session.send(input=error_response)
            else:
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

