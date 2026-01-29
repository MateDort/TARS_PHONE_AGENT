"""Manager Agent - The Orchestrator of TARS Autonomy."""
import asyncio
import logging
import signal
import sys
import os
from core.config import Config
from core.event_bus import event_bus
from communication.telegram_client import telegram_client
from communication.discord_client import discord_client
from core.database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ManagerAgent")

from core.session_manager import SessionManager

class ManagerAgent:
    """The central nervous system of TARS."""

    def __init__(self):
        self.running = False
        self.db = Database(Config.DATABASE_PATH)
        # Initialize local session manager for text sessions
        self.session_manager = SessionManager(self.db)

    async def start(self):
        """Start the manager and all connected services."""
        self.running = True
        logger.info("Manager Agent starting...")

        # 1. Subscribe to core events (Register handlers FIRST)
        event_bus.subscribe('task.create', self._handle_task_create)
        event_bus.subscribe('chat.message.received', self._handle_chat_message)
        event_bus.subscribe('chat.voice.received', self._handle_voice_message)
        event_bus.subscribe('chat.photo.received', self._handle_photo_message)
        
        # 2. Connect to Event Bus (Start listening AFTER registering)
        await event_bus.start_listening()
        
        # 3. Start Chat Clients
        self.client_tasks = []
        try:
            # Start Telegram (it has its own internal poller, but start() is async)
            telegram_task = asyncio.create_task(telegram_client.start())
            self.client_tasks.append(telegram_task)
            
            # Start Discord (blocking run loop)
            discord_task = asyncio.create_task(discord_client.start_client())
            self.client_tasks.append(discord_task)
            
            logger.info("Chat clients launched in background.")
        except Exception as e:
            logger.error(f"Failed to start chat clients: {e}")
            
        logger.info("Manager Agent running. Presiding over the Event Bus.")
        
        # Keep alive loop
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self):
        """Stop all services."""
        logger.info("Manager Agent stopping...")
        self.running = False
        await telegram_client.stop()
        # discord client stop if needed
        await event_bus.close()
        logger.info("Manager Agent stopped.")

    async def _handle_task_create(self, data: dict):
        """Handle new task creation request."""
        logger.info(f"New Task Requested: {data}")
        # Logic to spawn RQ job or Docker container would go here
        # For now, just acknowledge via notification
        await event_bus.publish('notification.send', {
            'message': f"Sir, I've received a request to: {data.get('description')}. (Manager Agent Acknowledged)"
        })

    async def _handle_chat_message(self, data: dict):
        """Handle incoming chat message."""
        user = data.get('username')
        text = data.get('text')
        platform = data.get('platform', 'unknown')
        chat_id = data.get('chat_id')
        user_id = data.get('user_id')
        
        # Use chat_id as primary identifier
        identifier = chat_id or user_id
        
        logger.info(f"Received {platform} message from {user}: {text}")
        
        try:
            # Create or retrieve session for this user
            session = await self.session_manager.create_message_session(
                identifier=str(identifier),
                platform=platform,
                user_name=user
            )
            
            # Send message to Gemini Live (Text)
            if session and session.gemini_client:
                 await session.gemini_client.send_text(text)
            else:
                 logger.error("Failed to create session or client is missing")
                 await event_bus.publish('notification.send', {
                    'chat_id': chat_id,
                    'message': "I'm currently rebooting my cognitive functions. Please try again in a moment."
                })

        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            await event_bus.publish('notification.send', {
                'chat_id': chat_id,
                'message': "My connection seems to be unstable. One moment."
            })

    async def _handle_voice_message(self, data: dict):
        """Handle incoming voice message event."""
        user = data.get('username')
        file_path = data.get('file_path')
        chat_id = data.get('chat_id')
        user_id = data.get('user_id')
        platform = data.get('platform')
        
        # Identifier logic same as chat message
        identifier = chat_id or user_id
        
        logger.info(f"Processing voice message from {user}: {file_path}")
        
        transcription = ""
        
        try:
            if not file_path or not os.path.exists(file_path):
                raise ValueError("File path missing or invalid")

            # Try OpenAI Whisper first if key is present
            if Config.OPENAI_API_KEY:
                try:
                    logger.info("Transcribing with OpenAI Whisper...")
                    from openai import OpenAI
                    client = OpenAI(api_key=Config.OPENAI_API_KEY)
                    
                    with open(file_path, "rb") as audio_file:
                        transcript = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file
                        )
                    transcription = transcript.text.strip()
                    logger.info(f"Whisper Transcription: {transcription}")
                except Exception as e:
                    logger.error(f"OpenAI Whisper failed: {e}. Falling back to Gemini.")
                    
            # Fallback to Gemini if OpenAI failed or no key
            if not transcription and Config.GEMINI_API_KEY:
                try:
                    # Configure Gemini
                    import google.generativeai as genai
                    genai.configure(api_key=Config.GEMINI_API_KEY)
                    
                    # 1. Upload file
                    logger.info("Uploading audio to Gemini...")
                    myfile = genai.upload_file(file_path, mime_type="audio/ogg")
                    
                    # 2. Transcribe
                    logger.info("Transcribing with Gemini...")
                    model = genai.GenerativeModel("gemini-2.0-flash-exp")
                    result = model.generate_content([
                        "Transcribe this audio file accurately. Return ONLY the transcription text. If it is empty or silence, say [Silence].", 
                        myfile
                    ])
                    transcription = result.text.strip()
                    logger.info(f"Gemini Transcription: {transcription}")
                    
                    # Cleanup Gemini file
                    try:
                        myfile.delete()
                    except:
                        pass
                except Exception as e:
                    logger.error(f"Gemini transcription failed: {e}")

            if not transcription:
                raise RuntimeError("All transcription methods failed.")
            
            # 3. Inject into Session
            session = await self.session_manager.create_message_session(
                identifier=str(identifier),
                platform=platform,
                user_name=user
            )
            
            if session and session.gemini_client:
                 # Send as if user typed it
                 # Prefix with [Voice Message] so AI knows context
                 await session.gemini_client.send_text(f"[Voice Message] {transcription}")
            else:
                 await event_bus.publish('notification.send', {
                    'chat_id': chat_id,
                    'message': "Voice received, but I couldn't connect to my brain to respond."
                })
            
            # Cleanup local file
            try:
                os.remove(file_path)
            except:
                pass

        except Exception as e:
            logger.error(f"Voice processing failed: {e}")
            await event_bus.publish('notification.send', {
                'chat_id': chat_id,
                'message': "I had trouble hearing that voice message."
            })

    async def _handle_photo_message(self, data: dict):
        """Handle incoming photo message event."""
        user = data.get('username')
        file_path = data.get('file_path')
        chat_id = data.get('chat_id')
        user_id = data.get('user_id')
        platform = data.get('platform')
        caption = data.get('caption', "")
        
        # Identifier logic same as chat message
        identifier = chat_id or user_id
        
        logger.info(f"Processing photo from {user}: {file_path}")
        
        try:
            if not file_path or not os.path.exists(file_path):
                 raise ValueError("File path missing or invalid")

            # Configure Gemini
            import google.generativeai as genai
            genai.configure(api_key=Config.GEMINI_API_KEY)
            
            # 1. Upload file
            logger.info("Uploading image to Gemini...")
            myfile = genai.upload_file(file_path, mime_type="image/jpeg")
            
            # 2. Analyze
            logger.info("Analyzing image...")
            model = genai.GenerativeModel("gemini-2.0-flash-exp")
            prompt = "Analyze this image in detail."
            if caption:
                prompt += f" The user provided this caption: '{caption}'."
            prompt += " If the user is asking a question, answer it. If not, describe what you see so I can respond to them."
            
            # We don't want the FINAL answer here, we want a description to feed to the MAIN agent
            # Actually, if we feed the description to the main agent, IT will generate the response.
            # So the prompt should be: "Describe this image in detail so an AI assistant can see it."
            
            prompt = f"Describe this image in detail. {f'User caption: {caption}' if caption else ''} Return a detailed description."
            
            result = model.generate_content([prompt, myfile])
            description = result.text.strip()
            logger.info(f"Image Analysis: {description}")
            
            # 3. Inject into Session
            session = await self.session_manager.create_message_session(
                identifier=str(identifier),
                platform=platform,
                user_name=user
            )
            
            if session and session.gemini_client:
                 # Send context to AI
                 context_msg = f"[User sent a photo]\nDescription: {description}"
                 if caption:
                     context_msg += f"\nUser Caption: {caption}"
                 
                 await session.gemini_client.send_text(context_msg)
            else:
                 await event_bus.publish('notification.send', {
                    'chat_id': chat_id,
                    'message': "I saw your photo, but my connection failed."
                })

            # Cleanup
            try:
                os.remove(file_path)
                myfile.delete()
            except:
                pass
                
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            await event_bus.publish('notification.send', {
                 'chat_id': chat_id,
                 'message': f"I couldn't analyze that photo. Error: {e}"
            })

def signal_handler(sig, frame):
    logger.info("Received exit signal")
    # In a real app we'd trigger a graceful shutdown here
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    manager = ManagerAgent()
    try:
        asyncio.run(manager.start())
    except KeyboardInterrupt:
        pass
