"""Main entry point for TARS - Máté's Personal Assistant with Gemini Live Audio."""
import asyncio
import logging
import signal
import sys
import threading
import time
from config import Config
from database import Database
from gemini_live_client import GeminiLiveClient
from twilio_media_streams import TwilioMediaStreamsHandler
from sub_agents_tars import get_all_agents, get_function_declarations
from reminder_checker import ReminderChecker
from translations import format_text
from session_manager import SessionManager
from message_router import MessageRouter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TARSPhoneAgent:
    """TARS - Máté's Personal Assistant with Gemini Live Audio and local database."""

    def __init__(self):
        """Initialize TARS phone agent."""
        # Validate configuration
        try:
            Config.validate()
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            sys.exit(1)

        if not Config.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY is required")
            sys.exit(1)

        logger.info("Initializing TARS - Máté's Personal Assistant...")

        # Initialize database
        self.db = Database("tars.db")
        logger.info("Database initialized")

        # Initialize Gemini Live client with TARS system instruction
        from datetime import datetime
        current_time = datetime.now().strftime("%I:%M %p")
        current_date = datetime.now().strftime("%A, %B %d, %Y")

        system_instruction = format_text(
            'tars_system_instruction',
            current_time=current_time,
            current_date=current_date,
            humor_percentage=Config.HUMOR_PERCENTAGE,
            honesty_percentage=Config.HONESTY_PERCENTAGE,
            personality=Config.PERSONALITY,
            nationality=Config.NATIONALITY
        )

        self.gemini_client = GeminiLiveClient(
            api_key=Config.GEMINI_API_KEY,
            system_instruction=system_instruction
        )

        # Initialize SessionManager for agent hub
        self.session_manager = SessionManager(self.db)
        logger.info("SessionManager initialized")

        # Initialize messaging handler for SMS/WhatsApp (needed for router)
        from messaging_handler import MessagingHandler
        self.messaging_handler = MessagingHandler(
            database=self.db,
            twilio_client=None,  # Will be set after twilio_handler created
            session_manager=self.session_manager,
            router=None,  # Will be set after router created
            twilio_handler=None  # Will be set after twilio_handler created
        )

        # Initialize MessageRouter for inter-session communication
        self.router = MessageRouter(
            self.session_manager,
            self.messaging_handler,
            self.db
        )
        logger.info("MessageRouter initialized")

        # Set router reference in session_manager (circular dependency workaround)
        self.session_manager.set_router(self.router)
        self.messaging_handler.router = self.router

        # Initialize reminder checker with multi-session awareness
        self.reminder_checker = ReminderChecker(
            db=self.db,
            twilio_handler=None,  # Will be set after twilio_handler created
            session_manager=self.session_manager,
            router=self.router
        )
        logger.info("ReminderChecker initialized with multi-session support")

        # Initialize Twilio handler with SessionManager and Router
        self.twilio_handler = TwilioMediaStreamsHandler(
            self.gemini_client,
            reminder_checker=self.reminder_checker,
            db=self.db,
            messaging_handler=self.messaging_handler,
            session_manager=self.session_manager,
            router=self.router
        )
        logger.info("TwilioMediaStreamsHandler initialized")

        # Set circular dependencies
        self.messaging_handler.twilio_client = self.twilio_handler.twilio_client
        self.messaging_handler.twilio_handler = self.twilio_handler
        self.reminder_checker.twilio_handler = self.twilio_handler
        self.reminder_checker.messaging_handler = self.messaging_handler

        # Register sub-agents (including config and message agents)
        self._register_sub_agents()

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.running = True
        self.websocket_task = None
        self.reminder_task = None

    async def _reload_system_instruction(self):
        """Reload system instruction with updated config values."""
        from datetime import datetime
        current_time = datetime.now().strftime("%I:%M %p")
        current_date = datetime.now().strftime("%A, %B %d, %Y")

        system_instruction = format_text(
            'tars_system_instruction',
            current_time=current_time,
            current_date=current_date,
            humor_percentage=Config.HUMOR_PERCENTAGE,
            honesty_percentage=Config.HONESTY_PERCENTAGE,
            personality=Config.PERSONALITY,
            nationality=Config.NATIONALITY
        )

        # Update the Gemini client's system instruction
        if hasattr(self.gemini_client, 'system_instruction'):
            self.gemini_client.system_instruction = system_instruction
            logger.info(
                "System instruction reloaded with updated configuration")

    def _register_sub_agents(self):
        """Register all sub-agents with the Gemini client."""
        logger.info("Registering sub-agents...")

        # Get all agents (including InterSessionAgent with session_manager and router)
        agents = get_all_agents(
            db=self.db,
            messaging_handler=self.messaging_handler,
            system_reloader_callback=self._reload_system_instruction,
            twilio_handler=self.twilio_handler,
            session_manager=self.session_manager,
            router=self.router
        )

        # Get function declarations
        declarations = get_function_declarations()

        # Register each function with its handler
        function_map = {
            "adjust_config": agents["config"],
            "manage_reminder": agents["reminder"],
            "lookup_contact": agents["contacts"],
            "send_notification": agents["notification"],
            # May be None if messaging not available
            "send_message": agents.get("message"),
            # May be None if twilio not available
            "make_goal_call": agents.get("outbound_call"),
            # InterSessionAgent functions
            "send_message_to_session": agents.get("inter_session"),
            "request_user_confirmation": agents.get("inter_session"),
            "broadcast_to_sessions": agents.get("inter_session"),
            "list_active_sessions": agents.get("inter_session"),
            "take_message_for_mate": agents.get("inter_session"),
            "schedule_callback": agents.get("inter_session"),
            "hangup_call": agents.get("inter_session"),
        }

        for declaration in declarations:
            fn_name = declaration["name"]
            if fn_name in function_map:
                agent = function_map[fn_name]

                # Skip if agent is None (e.g., message agent when messaging not available)
                if agent is None:
                    logger.warning(
                        f"Skipping function {fn_name} - agent not available")
                    continue

                # Create wrapper handler
                def make_handler(agent_instance):
                    async def handler(args):
                        return await agent_instance.execute(args)
                    return handler

                # Register with Gemini client
                handler = make_handler(agent)
                self.gemini_client.register_function(declaration, handler)
                logger.info(f"Registered function: {fn_name} -> {agent.name}")
            elif fn_name == "get_current_time":
                # Special handler for get_current_time
                async def get_time_handler(args):
                    from datetime import datetime
                    now = datetime.now()
                    current_time = now.strftime("%I:%M %p")
                    current_date = now.strftime("%A, %B %d, %Y")
                    return {
                        "time": current_time,
                        "date": current_date,
                        "message": f"The current time is {current_time} on {current_date}, sir."
                    }

                self.gemini_client.register_function(
                    declaration, get_time_handler)
                logger.info(f"Registered function: {fn_name} -> time utility")

        logger.info(f"Registered {len(function_map)} sub-agents")

        # Pass function handlers to SessionManager so session-specific clients can use them
        if self.session_manager:
            self.session_manager.set_function_handlers(
                self.gemini_client.function_handlers)
            logger.info("Function handlers registered with SessionManager")

    async def _trigger_reminder_call(self, reminder: dict):
        """Trigger an outbound call for a reminder.

        Args:
            reminder: Reminder dictionary from database
        """
        logger.info(f"Triggering reminder call for: {reminder['title']}")

        try:
            # Make outbound call via Twilio with reminder message
            reminder_message = f"Sir, you have a reminder: {reminder['title']}"
            call_sid = self.twilio_handler.make_call(
                reminder_message=reminder_message)
            logger.info(f"Reminder call initiated: {call_sid}")

        except Exception as e:
            logger.error(f"Error making reminder call: {e}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received, stopping TARS...")
        self.running = False
        self.reminder_checker.stop()

    async def start_async(self):
        """Start TARS phone agent (async)."""
        try:
            # Set main loop in twilio handler for thread-safe async execution from Flask
            self.twilio_handler.set_main_loop(asyncio.get_running_loop())

            # Start message router for inter-session communication
            await self.router.start()
            logger.info("Message router started")

            # Start reminder checker in background
            self.reminder_task = asyncio.create_task(
                self.reminder_checker.start())
            logger.info("Reminder checker started")

            # Start WebSocket server for Media Streams in background
            self.websocket_task = asyncio.create_task(
                self.twilio_handler.start_websocket_server(
                    host='0.0.0.0',
                    port=Config.WEBSOCKET_PORT
                )
            )

            # Give WebSocket server time to start
            await asyncio.sleep(2)

            logger.info("=" * 60)
            logger.info(
                "TARS - Máté's Personal Assistant Ready (Agent Hub Enabled)")
            logger.info("=" * 60)
            logger.info("Features:")
            logger.info("  ✓ Smart reminders (automatic calls)")
            logger.info("  ✓ Contact management")
            logger.info("  ✓ Dynamic personality adjustment")
            logger.info(
                f"  ✓ Humor: {Config.HUMOR_PERCENTAGE}% | Honesty: {Config.HONESTY_PERCENTAGE}%")
            logger.info("  ✓ Google Search for current info")
            logger.info("  ✓ Natural British voice conversations")
            logger.info(
                "  ✓ Multi-session agent hub (up to 10 concurrent calls)")
            logger.info("  ✓ Inter-agent communication & coordination")
            logger.info("=" * 60)
            logger.info("Waiting for calls...")

            # Keep running
            while self.running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error during operation: {e}")
        finally:
            await self.shutdown_async()

    async def shutdown_async(self):
        """Shutdown TARS and cleanup (async)."""
        logger.info("Shutting down TARS...")

        # Stop message router
        await self.router.stop()
        logger.info("Message router stopped")

        # Stop reminder checker
        self.reminder_checker.stop()

        # Cancel tasks
        if self.reminder_task:
            self.reminder_task.cancel()
            try:
                await self.reminder_task
            except asyncio.CancelledError:
                pass

        if self.websocket_task:
            self.websocket_task.cancel()
            try:
                await self.websocket_task
            except asyncio.CancelledError:
                pass

        # Disconnect Gemini
        if self.gemini_client.is_connected:
            await self.gemini_client.disconnect()

        # Close database
        self.db.close()

        logger.info("TARS stopped.")

    def start(self):
        """Start TARS phone agent (sync wrapper)."""
        logger.info("Starting TARS...")

        # Start Flask server in a separate thread
        server_thread = threading.Thread(
            target=self.twilio_handler.run_server,
            daemon=True
        )
        server_thread.start()

        # Wait for Flask server to start
        time.sleep(2)

        # Option to make outbound call
        if hasattr(Config, 'AUTO_CALL') and Config.AUTO_CALL:
            try:
                logger.info(
                    f"Making outbound call to {Config.TARGET_PHONE_NUMBER}...")
                call_sid = self.twilio_handler.make_call()
                logger.info(
                    f"Call initiated successfully. Call SID: {call_sid}")
            except Exception as e:
                logger.error(f"Error making call: {e}")

        # Run async event loop
        try:
            asyncio.run(self.start_async())
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error in event loop: {e}")


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("  TARS - MÁTÉ'S PERSONAL ASSISTANT")
    print("  Powered by Gemini Live Audio")
    print("=" * 60)
    print("\nFeatures:")
    print("  🤖 TARS - British, respectful, witty assistant")
    print("  🔔 Smart Reminders - Automatic calls for tasks & meetings")
    print("  👥 Contact Management - Quick access to friends & family")
    print("  ⚙️  Dynamic Personality - Adjustable humor & honesty levels")
    print("  🔍 Google Search - Current weather, news, and info")
    print("  🎤 Natural Voice - British accent, respectful conversations")
    print("=" * 60 + "\n")

    agent = TARSPhoneAgent()
    agent.start()


if __name__ == '__main__':
    main()
