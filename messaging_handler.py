"""Messaging handler for SMS and WhatsApp via Twilio."""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from twilio.rest import Client
from config import Config
from database import Database
from security import authenticate_phone_number, filter_functions_by_permission, get_limited_system_instruction
from agent_session import PermissionLevel

logger = logging.getLogger(__name__)


class MessagingHandler:
    """Handles bidirectional SMS and WhatsApp messaging via Twilio."""

    def __init__(self, database: Database, twilio_client: Client, session_manager=None, router=None, twilio_handler=None, gmail_handler=None):
        """Initialize messaging handler.

        Args:
            database: Database instance for conversation logging
            twilio_client: Twilio Client instance
            session_manager: SessionManager instance
            router: MessageRouter instance
            twilio_handler: TwilioMediaStreamsHandler instance
            gmail_handler: GmailHandler instance
        """
        self.db = database
        self.twilio_client = twilio_client
        self.session_manager = session_manager
        self.router = router
        self.twilio_handler = twilio_handler
        self.gmail_handler = gmail_handler

        logger.info("MessagingHandler initialized")

    async def process_incoming_message(self, from_number: str, message_body: str,
                                       medium: str = 'sms', message_sid: str = None, to_number: str = None):
        """Process incoming SMS/WhatsApp message and generate AI response.

        Args:
            from_number: Sender's phone number
            message_body: Message text
            medium: 'sms' or 'whatsapp'
            message_sid: Twilio message SID
            to_number: The number the message was sent to (bot's number)
        """
        try:
            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "messaging_handler.py:process_incoming_message:entry",
                            "message": "Processing incoming message", "data": {"from_number": from_number, "message_body": message_body, "medium": medium}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion

            logger.info(
                f"Processing incoming {medium} from {from_number}: {message_body}")

            # Log incoming message to database
            self.db.add_conversation_message(
                sender='user',
                message=message_body,
                medium=medium,
                message_sid=message_sid,
                direction='inbound'
            )

            # Authenticate sender to determine permission level
            permission_level = authenticate_phone_number(from_number)

            # Get conversation context for better AI responses
            context = self.db.get_conversation_context(limit=10)

            # Prepare system instruction with context
            from translations import format_text
            current_time = datetime.now().strftime("%I:%M %p")
            current_date = datetime.now().strftime("%A, %B %d, %Y")

            if permission_level == PermissionLevel.FULL:
                system_instruction = format_text(
                    'tars_system_instruction',
                    current_time=current_time,
                    current_date=current_date,
                    humor_percentage=Config.HUMOR_PERCENTAGE,
                    honesty_percentage=Config.HONESTY_PERCENTAGE,
                    personality=Config.PERSONALITY,
                    nationality=Config.NATIONALITY
                )
            else:
                # For limited access, start with the base instruction and add constraints
                system_instruction = format_text('tars_system_instruction', current_time=current_time, current_date=current_date, humor_percentage=Config.HUMOR_PERCENTAGE,
                                                 honesty_percentage=Config.HONESTY_PERCENTAGE, personality=Config.PERSONALITY, nationality=Config.NATIONALITY)
                system_instruction += "\n\n" + get_limited_system_instruction()

            # IMPORTANT: For SMS/WhatsApp, the AI should NOT call send_message function
            # It should just return text. The send_message function is only for sending links.
            system_instruction += "\n\nIMPORTANT: You are responding via text message. Do NOT call the send_message function unless you are sending a link. Just return your response as text."
            
            # Add Google Search availability notice
            system_instruction += "\n\nYou have access to Google Search for real-time information. Use it automatically for queries about current weather, news, stock prices, or any information that requires up-to-date data. Google Search is enabled and will be used automatically when needed."

            # Add context if available
            if context:
                system_instruction += f"\n\nRecent conversation history:\n{context}"

            # Generate AI response using Gemini
            # Note: For text-only messaging, we'll use the gemini client's text generation
            # This is a simplified version - in production you might want to use a separate
            # text-only Gemini client for better performance
            response_text = await self._generate_text_response(
                message_body,
                system_instruction,
                permission_level
            )

            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "messaging_handler.py:process_incoming_message:before_send", "message": "About to send reply", "data": {
                            "to_number": from_number, "response_length": len(response_text), "response_preview": response_text[:100]}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion

            # Send reply via Twilio
            self.send_message(
                to_number=from_number,
                message_body=response_text,
                medium=medium,
                from_number=to_number  # Reply from the same number that received the message
            )

            logger.info(f"Sent {medium} reply to {from_number}")

        except Exception as e:
            logger.error(f"Error processing incoming message: {e}")
            # Send error message to user
            try:
                self.send_message(
                    to_number=from_number,
                    message_body="Sorry, I encountered an error. Please try again.",
                    medium=medium
                )
            except:
                pass

    async def _generate_text_response(self, message: str, system_instruction: str, permission_level: PermissionLevel) -> str:
        """Generate text response using Gemini AI (same approach as phone calls).

        Args:
            message: User's message
            system_instruction: System instruction with context
            permission_level: The permission level of the user.

        Returns:
            AI response text
        """
        client = None
        try:
            # Use the same Gemini client as phone calls (google.genai, not deprecated google.generativeai)
            from google import genai
            from google.genai import types

            # Create client (same as GeminiLiveClient)
            client = genai.Client(
                http_options={"api_version": "v1beta"},
                api_key=Config.GEMINI_API_KEY
            )

            model = "models/gemini-2.0-flash-exp"  # Use same model family as call system

            # Get function declarations from sub_agents (same as phone calls)
            from sub_agents_tars import get_function_declarations
            all_declarations = get_function_declarations()

            # Filter declarations based on permission level
            declarations = filter_functions_by_permission(
                permission_level, all_declarations)

            # Build tools list
            # For generate_content API, tools should be a single object combining all tools
            # or an array with a single combined object
            tools = None
            if declarations:
                # Combine google_search and function_declarations into single tool object
                tool_obj = {}
                # Enable Google Search Grounding
                tool_obj["google_search"] = {}
                tool_obj["function_declarations"] = declarations
                tools = [tool_obj]
            elif True:  # Always enable google_search even without functions
                # Just google_search
                tools = [{"google_search": {}}]

            # Build conversation history for the API call
            conversation_history = [
                types.Content(parts=[types.Part(text=message)], role="user")
            ]

            response = await client.aio.models.generate_content(
                model=model,
                contents=conversation_history,
                config=types.GenerateContentConfig(
                    system_instruction=types.Content(
                        parts=[types.Part(text=system_instruction)]
                    ) if system_instruction else None,
                    tools=tools if tools else None,
                    temperature=0.8,
                )
            )

            # Handle function calls if present (same logic as phone calls)
            if response.candidates and response.candidates[0].content.parts:
                first_part = response.candidates[0].content.parts[0]
                if hasattr(first_part, 'function_call') and first_part.function_call:
                    function_call = first_part.function_call
                    function_name = function_call.name
                    function_args = dict(function_call.args)

                    logger.info(
                        f"Function call in message: {function_name}({function_args})")

                    # Execute the function
                    result = await self._execute_function(function_name, function_args)

                    # Append the AI's function call and the result to the conversation
                    conversation_history.append(response.candidates[0].content)
                    conversation_history.append(
                        types.Content(
                            parts=[
                                types.Part(
                                    function_response=types.FunctionResponse(
                                        name=function_name,
                                        response={'result': str(result)}
                                    )
                                )
                            ]
                        )
                    )

                    # Get final response with function results
                    response = await client.aio.models.generate_content(
                        model=model,
                        contents=conversation_history,
                        config=types.GenerateContentConfig(
                            system_instruction=types.Content(
                                parts=[types.Part(text=system_instruction)]
                            ) if system_instruction else None,
                            tools=tools if tools else None,
                            temperature=0.8,
                        )
                    )

            # Extract text from response
            if response.candidates and response.candidates[0].content.parts:
                text_parts = []
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                return ' '.join(text_parts) if text_parts else "I'm processing your request."

            return "I'm processing your request."

        except Exception as e:
            logger.error(f"Error generating text response: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return "I'm having trouble processing your request right now. Please try again."
        finally:
            if client:
                client.close()

    async def _execute_function(self, function_name: str, args: Dict[str, Any]) -> str:
        """Execute a function call from the AI.

        Args:
            function_name: Name of the function to call
            args: Function arguments

        Returns:
            Function result as string
        """
        try:
            from sub_agents_tars import get_all_agents

            # Get agents
            agents = get_all_agents(
                db=self.db,
                messaging_handler=self,
                session_manager=self.session_manager,
                router=self.router,
                twilio_handler=self.twilio_handler
            )

            # Map function names to agents
            function_map = {
                "adjust_config": agents.get("config"),
                "manage_reminder": agents["reminder"],
                "lookup_contact": agents["contacts"],
                "send_notification": agents["notification"],
                "send_message": agents.get("message"),
                "make_goal_call": agents.get("outbound_call"),
                "send_message_to_session": agents.get("inter_session"),
                "request_user_confirmation": agents.get("inter_session"),
                "broadcast_to_sessions": agents.get("inter_session"),
                "list_active_sessions": agents.get("inter_session"),
                "take_message_for_mate": agents.get("inter_session"),
                "schedule_callback": agents.get("inter_session"),
                "hangup_call": agents.get("inter_session"),
            }

            if function_name in function_map:
                agent = function_map[function_name]
                if agent:
                    return await agent.execute(args)
                return f"Error: Agent for {function_name} not available."
            elif function_name == "get_current_time":
                now = datetime.now()
                return f"The current time is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')}."
            else:
                return f"Unknown function: {function_name}"

        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}")
            return f"Error executing function: {e}"

    def send_message(self, to_number: str, message_body: str, medium: str = 'sms', from_number: str = None) -> Optional[str]:
        """Send outbound SMS or WhatsApp message.

        Args:
            to_number: Recipient's phone number
            message_body: Message text
            medium: 'sms' or 'whatsapp'
            medium: 'sms', 'whatsapp', or 'gmail'
            from_number: Optional sender number override

        Returns:
            Message SID or None if failed
        """
        try:
            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "B", "location": "messaging_handler.py:send_message:entry", "message": "send_message called", "data": {
                            "to_number": to_number, "medium": medium, "message_length": len(message_body), "message_preview": message_body[:50]}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion

            # Handle Gmail medium
            if medium == 'gmail':
                if self.gmail_handler:
                    # For Gmail, to_number is the email address
                    subject = "TARS Reply"
                    return str(self.gmail_handler.send_email(to_number, subject, message_body))
                return None

            # Format phone numbers for Twilio
            if not from_number:
                from_number = Config.TWILIO_PHONE_NUMBER

            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "messaging_handler.py:send_message:before_format",
                            "message": "Before number formatting", "data": {"from_number": from_number, "to_number": to_number, "medium": medium}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion

            if medium == 'whatsapp':
                # Use dedicated WhatsApp number if available
                if Config.WHATSAPP_NUMBER and from_number == Config.TWILIO_PHONE_NUMBER:
                    from_number = Config.WHATSAPP_NUMBER

                # WhatsApp requires 'whatsapp:' prefix
                if not from_number.startswith('whatsapp:'):
                    from_number = f'whatsapp:{from_number}'
                if not to_number.startswith('whatsapp:'):
                    to_number = f'whatsapp:{to_number}'

            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "messaging_handler.py:send_message:after_format",
                            "message": "After number formatting", "data": {"from_number": from_number, "to_number": to_number, "medium": medium}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion

            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "D", "location": "messaging_handler.py:send_message:before_twilio",
                            "message": "Before Twilio API call", "data": {"from_number": from_number, "to_number": to_number, "body": message_body}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except:
                pass
            # #endregion

            # Send message via Twilio
            message = self.twilio_client.messages.create(
                body=message_body,
                from_=from_number,
                to=to_number
            )

            # Fetch full message details to get error information
            # Wait a moment for status to update
            import time
            time.sleep(0.5)

            # Fetch updated message status
            try:
                message = self.twilio_client.messages(message.sid).fetch()
            except:
                pass  # If fetch fails, use original message object

            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    error_data = {
                        "message_sid": message.sid,
                        "status": message.status,
                        "to": message.to,
                        "from": message.from_,
                        "body_length": len(message.body) if hasattr(message, 'body') else None,
                        "error_code": getattr(message, 'error_code', None),
                        "error_message": getattr(message, 'error_message', None),
                        "price": getattr(message, 'price', None),
                        "price_unit": getattr(message, 'price_unit', None),
                    }
                    # Check for additional error info
                    if hasattr(message, 'uri'):
                        error_data["uri"] = message.uri
                    f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "D", "location": "messaging_handler.py:send_message:after_twilio",
                            "message": "After Twilio API call with full details", "data": error_data, "timestamp": int(__import__('time').time()*1000)}) + '\n')
            except Exception as e:
                logger.error(f"Error logging debug info: {e}")
            # #endregion

            # Check message status and log warnings with detailed error info
            if message.status == 'queued' or message.status == 'undelivered':
                logger.warning(
                    f"⚠️  Message {message.sid} status: {message.status}")

                # Get detailed error information
                error_code = getattr(message, 'error_code', None)
                error_message = getattr(message, 'error_message', None)

                # #region debug log
                try:
                    with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                        import json
                        f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "G", "location": "messaging_handler.py:send_message:undelivered_status", "message": "Message undelivered - checking error details", "data": {
                                "status": message.status, "error_code": error_code, "error_message": error_message, "to": to_number, "from": from_number}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                except:
                    pass
                # #endregion

                if error_code:
                    logger.error(f"   Error Code: {error_code}")

                    # Specific handling for common error codes
                    if error_code == 30034:
                        logger.error(
                            "   Error 30034: Message blocked by carrier or recipient opt-out")
                        logger.error("   Possible causes:")
                        logger.error(
                            "     - A2P 10DLC registration required (MOST LIKELY - even with paid account)")
                        logger.error(
                            "     - Recipient has opted out/unsubscribed")
                        logger.error("     - Carrier blocking")
                        logger.error("     - Number on Do Not Call list")
                        logger.error("   Solutions (in order):")
                        logger.error(
                            "     1. Complete A2P 10DLC Registration (REQUIRED for US SMS):")
                        logger.error(
                            "        a. Go to: https://console.twilio.com/us1/develop/sms/a2p-messaging")
                        logger.error(
                            "        b. Register your Brand (company/organization)")
                        logger.error(
                            "        c. Create a Campaign (use case for messaging)")
                        logger.error(
                            "        d. Wait for approval (can take 1-3 business days)")
                        logger.error("     2. Check if recipient opted out:")
                        logger.error(
                            "        - Go to Twilio Console → Messaging → Opt-outs")
                        logger.error(
                            "        - Check if +14049525557 is listed")
                        logger.error(
                            "     3. Contact Twilio Support with Message SID:")
                        logger.error(f"        {message.sid}")
                        logger.error(
                            "     4. Try sending from a different Twilio number")

                        # Check if number is opted out
                        try:
                            opt_outs = self.twilio_client.messaging.v1.services.list()
                            # Check for opt-outs (this requires a Messaging Service, but we can try)
                            logger.warning("   Checking opt-out status...")
                        except:
                            pass

                if error_message:
                    logger.error(f"   Error Message: {error_message}")

                # Check if number is verified
                try:
                    verified_numbers = self.twilio_client.outgoing_caller_ids.list()
                    is_verified = any(v.phone_number == to_number or v.phone_number == to_number.replace(
                        '+', '') for v in verified_numbers)

                    # #region debug log
                    try:
                        with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                            import json
                            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "G", "location": "messaging_handler.py:send_message:check_verified", "message": "Checking if number is verified", "data": {
                                    "to_number": to_number, "is_verified": is_verified, "verified_count": len(verified_numbers)}, "timestamp": int(__import__('time').time()*1000)}) + '\n')
                    except:
                        pass
                    # #endregion

                    if not is_verified:
                        logger.warning(
                            f"   ⚠️  Number {to_number} is NOT verified in Twilio")
                        logger.warning(
                            f"   Verify at: https://console.twilio.com/us1/develop/phone-numbers/manage/verified")
                    else:
                        logger.warning(
                            f"   ✓ Number {to_number} IS verified, but message still undelivered")
                        logger.warning(
                            f"   This may be a carrier blocking issue or account restriction")
                except Exception as e:
                    logger.warning(
                        f"   Could not check verification status: {e}")

                logger.warning(
                    f"   Check Twilio Console → Messaging → Logs → Click 'Troubleshoot' for details")
            elif message.status == 'failed':
                logger.error(f"❌ Message {message.sid} failed to send")
                if hasattr(message, 'error_message') and message.error_message:
                    logger.error(f"   Error: {message.error_message}")
                if hasattr(message, 'error_code') and message.error_code:
                    logger.error(f"   Error Code: {message.error_code}")
            elif message.status in ['sent', 'delivered']:
                logger.info(
                    f"✅ Message {message.sid} {message.status} successfully")

            logger.info(
                f"Sent {medium} message to {to_number}: {message.sid} (status: {message.status})")

            # Log outgoing message to database
            self.db.add_conversation_message(
                sender='assistant',
                message=message_body,
                medium=medium,
                message_sid=message.sid,
                direction='outbound'
            )

            return message.sid

        except Exception as e:
            logger.error(f"Error sending {medium} message: {e}")
            return None

    def send_link(self, to_number: str, url: str, description: str = '', medium: str = 'sms') -> Optional[str]:
        """Send a link to the user via SMS/WhatsApp.

        Args:
            to_number: Recipient's phone number
            url: URL to send
            description: Optional description of the link
            medium: 'sms' or 'whatsapp'

        Returns:
            Message SID or None if failed
        """
        # Format message with link
        if description:
            message_body = f"{description}\n\n{url}"
        else:
            message_body = url

        return self.send_message(to_number, message_body, medium)
