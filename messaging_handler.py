"""Messaging handler for SMS and WhatsApp via Twilio."""
import asyncio
import logging
from typing import Optional
from datetime import datetime
from twilio.rest import Client
from config import Config
from database import Database

logger = logging.getLogger(__name__)


class MessagingHandler:
    """Handles bidirectional SMS and WhatsApp messaging via Twilio."""
    
    def __init__(self, gemini_client, database: Database, twilio_client: Client):
        """Initialize messaging handler.
        
        Args:
            gemini_client: GeminiLiveClient instance for AI responses
            database: Database instance for conversation logging
            twilio_client: Twilio Client instance
        """
        self.gemini_client = gemini_client
        self.db = database
        self.twilio_client = twilio_client
        
        logger.info("MessagingHandler initialized")
    
    async def process_incoming_message(self, from_number: str, message_body: str, 
                                      medium: str = 'sms', message_sid: str = None):
        """Process incoming SMS/WhatsApp message and generate AI response.
        
        Args:
            from_number: Sender's phone number
            message_body: Message text
            medium: 'sms' or 'whatsapp'
            message_sid: Twilio message SID
        """
        try:
            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"messaging_handler.py:process_incoming_message:entry","message":"Processing incoming message","data":{"from_number":from_number,"message_body":message_body,"medium":medium},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            
            logger.info(f"Processing incoming {medium} from {from_number}: {message_body}")
            
            # Log incoming message to database
            self.db.add_conversation_message(
                sender='user',
                message=message_body,
                medium=medium,
                message_sid=message_sid,
                direction='inbound'
            )
            
            # Get conversation context for better AI responses
            context = self.db.get_conversation_context(limit=10)
            
            # Prepare system instruction with context
            from translations import format_text
            current_time = datetime.now().strftime("%I:%M %p")
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            
            system_instruction = format_text(
                'elderly_system_instruction',
                Config.LANGUAGE,
                current_time=current_time,
                current_date=current_date
            )
            
            # IMPORTANT: For SMS/WhatsApp, the AI should NOT call send_message function
            # It should just return text. The send_message function is only for phone calls.
            system_instruction += "\n\nIMPORTANT: You are responding via SMS/WhatsApp. Do NOT call the send_message function. Just return your response as text. The send_message function is only for sending links during phone calls."
            
            # Add context if available
            if context:
                system_instruction += f"\n\nRecent conversation history:\n{context}"
            
            # Generate AI response using Gemini
            # Note: For text-only messaging, we'll use the gemini client's text generation
            # This is a simplified version - in production you might want to use a separate
            # text-only Gemini client for better performance
            response_text = await self._generate_text_response(
                message_body, 
                system_instruction
            )
            
            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"messaging_handler.py:process_incoming_message:before_send","message":"About to send reply","data":{"to_number":from_number,"response_length":len(response_text),"response_preview":response_text[:100]},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            
            # Send reply via Twilio
            self.send_message(
                to_number=from_number,
                message_body=response_text,
                medium=medium
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
    
    async def _generate_text_response(self, message: str, system_instruction: str) -> str:
        """Generate text response using Gemini AI (same approach as phone calls).
        
        Args:
            message: User's message
            system_instruction: System instruction with context
            
        Returns:
            AI response text
        """
        try:
            # Use the same Gemini client as phone calls (google.genai, not deprecated google.generativeai)
            from google import genai
            from google.genai import types
            
            # Create client (same as GeminiLiveClient)
            client = genai.Client(
                http_options={"api_version": "v1beta"},
                api_key=Config.GEMINI_API_KEY
            )
            
            # Use text model (not audio model)
            model = "models/gemini-2.5-flash"
            
            # Get function declarations from sub_agents (same as phone calls)
            from sub_agents_elderly import get_function_declarations
            declarations = get_function_declarations()
            
            # For SMS/WhatsApp, remove send_message function - AI should just return text
            # send_message is only for phone calls when user requests links
            if declarations:
                declarations = [d for d in declarations if d.get('name') != 'send_message']
            
            # Build tools list
            # NOTE: generate_content API doesn't support google_search + function_declarations together
            # So we'll use only function_declarations for now (function calling still works)
            # Google Search can be added via a function if needed
            tools = []
            
            # Add custom function declarations if any (same as phone calls)
            if declarations:
                tools.append({
                    "function_declarations": declarations
                })
            
            # If no function declarations, use empty tools (model will still work)
            if not tools:
                tools = None
            
            # Generate response using generate_content (text-only, not audio)
            # Format contents properly
            contents = types.Content(parts=[types.Part(text=message)])
            
            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run2","hypothesisId":"F","location":"messaging_handler.py:_generate_text_response:before_api","message":"About to call Gemini API","data":{"model":model,"has_tools":bool(tools),"tools_count":len(tools)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=types.Content(
                        parts=[types.Part(text=system_instruction)]
                    ) if system_instruction else None,
                    tools=tools if tools else None,
                    temperature=0.7,
                )
            )
            
            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    has_candidates = bool(response.candidates) if hasattr(response, 'candidates') else False
                    parts_count = len(response.candidates[0].content.parts) if (has_candidates and response.candidates[0].content.parts) else 0
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run2","hypothesisId":"F","location":"messaging_handler.py:_generate_text_response:after_api","message":"Gemini API response received","data":{"has_candidates":has_candidates,"parts_count":parts_count},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            
            # Handle function calls if present (same logic as phone calls)
            # Check for function calls in response
            function_calls_handled = False
            if response.candidates and response.candidates[0].content.parts:
                function_responses = []
                
                for part in response.candidates[0].content.parts:
                    # Check for function_call attribute
                    if hasattr(part, 'function_call') and part.function_call:
                        function_calls_handled = True
                        function_call = part.function_call
                        function_name = function_call.name if hasattr(function_call, 'name') else None
                        
                        # Extract args - could be dict or object
                        if hasattr(function_call, 'args'):
                            if isinstance(function_call.args, dict):
                                function_args = function_call.args
                            else:
                                function_args = dict(function_call.args) if hasattr(function_call.args, '__dict__') else {}
                        else:
                            function_args = {}
                        
                        if function_name:
                            logger.info(f"Function call in message: {function_name}")
                            
                            # Execute the function through registered handlers
                            result = await self._execute_function(function_name, function_args)
                            
                            # Build function response
                            function_response = types.FunctionResponse(
                                name=function_name,
                                response={'result': str(result)}
                            )
                            
                            # Add ID if present
                            if hasattr(function_call, 'id'):
                                function_response.id = function_call.id
                            
                            function_responses.append(function_response)
                
                # If we handled function calls, send responses back
                if function_calls_handled and function_responses:
                    # Build conversation history
                    conversation = [
                        types.Content(parts=[types.Part(text=message)])
                    ]
                    
                    # Add function responses
                    for fr in function_responses:
                        conversation.append(
                            types.Content(parts=[types.Part(function_response=fr)])
                        )
                    
                    # Get final response with function results
                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model,
                        contents=conversation,
                        config=types.GenerateContentConfig(
                            system_instruction=types.Content(
                                parts=[types.Part(text=system_instruction)]
                            ) if system_instruction else None,
                            tools=tools if tools else None,
                            temperature=0.7,
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
    
    async def _execute_function(self, function_name: str, args: dict) -> str:
        """Execute a function call from the AI.
        
        Args:
            function_name: Name of the function to call
            args: Function arguments
            
        Returns:
            Function result as string
        """
        try:
            from sub_agents_elderly import get_all_agents
            
            # Get agents
            agents = get_all_agents(self.db)
            
            # Map function names to agents
            function_map = {
                "manage_reminder": agents["reminder"],
                "lookup_user_info": agents["user_bio"],
                "lookup_contact": agents["contacts"],
                "send_notification": agents["notification"],
            }
            
            if function_name in function_map:
                agent = function_map[function_name]
                result = await agent.execute(args)
                return str(result)
            elif function_name == "get_current_time":
                now = datetime.now()
                current_time = now.strftime("%I:%M %p")
                current_date = now.strftime("%A, %B %d, %Y")
                return f"The current time is {current_time} on {current_date}"
            elif function_name == "send_message":
                # Handle send_message function
                # NOTE: This should NOT be called during normal message processing
                # It's only for sending links/messages during phone calls
                # For SMS responses, we should just return text, not call this function
                action = args.get("action", "send")
                message = args.get("message", "")
                link = args.get("link", "")
                medium = args.get("medium", "sms")
                
                # #region debug log
                try:
                    with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                        import json
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"messaging_handler.py:_execute_function:send_message","message":"send_message function called","data":{"action":action,"has_link":bool(link),"medium":medium},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                except: pass
                # #endregion
                
                if action == "send_link":
                    self.send_link(
                        to_number=Config.TARGET_PHONE_NUMBER,
                        url=link,
                        description=message,
                        medium=medium
                    )
                    return f"Link sent via {medium}"
                else:
                    self.send_message(
                        to_number=Config.TARGET_PHONE_NUMBER,
                        message_body=message,
                        medium=medium
                    )
                    return f"Message sent via {medium}"
            else:
                return f"Unknown function: {function_name}"
                
        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}")
            return f"Error executing function: {e}"
    
    def send_message(self, to_number: str, message_body: str, medium: str = 'sms') -> Optional[str]:
        """Send outbound SMS or WhatsApp message.
        
        Args:
            to_number: Recipient's phone number
            message_body: Message text
            medium: 'sms' or 'whatsapp'
            
        Returns:
            Message SID or None if failed
        """
        try:
            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"messaging_handler.py:send_message:entry","message":"send_message called","data":{"to_number":to_number,"medium":medium,"message_length":len(message_body),"message_preview":message_body[:50]},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            
            # Format phone numbers for Twilio
            from_number = Config.TWILIO_PHONE_NUMBER
            
            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"messaging_handler.py:send_message:before_format","message":"Before number formatting","data":{"from_number":from_number,"to_number":to_number,"medium":medium},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            
            if medium == 'whatsapp':
                # WhatsApp requires 'whatsapp:' prefix
                if not from_number.startswith('whatsapp:'):
                    from_number = f'whatsapp:{from_number}'
                if not to_number.startswith('whatsapp:'):
                    to_number = f'whatsapp:{to_number}'
            
            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"messaging_handler.py:send_message:after_format","message":"After number formatting","data":{"from_number":from_number,"to_number":to_number,"medium":medium},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            
            # #region debug log
            try:
                with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"messaging_handler.py:send_message:before_twilio","message":"Before Twilio API call","data":{"from_number":from_number,"to_number":to_number,"body":message_body},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
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
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"messaging_handler.py:send_message:after_twilio","message":"After Twilio API call with full details","data":error_data,"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except Exception as e:
                logger.error(f"Error logging debug info: {e}")
            # #endregion
            
            # Check message status and log warnings with detailed error info
            if message.status == 'queued' or message.status == 'undelivered':
                logger.warning(f"⚠️  Message {message.sid} status: {message.status}")
                
                # Get detailed error information
                error_code = getattr(message, 'error_code', None)
                error_message = getattr(message, 'error_message', None)
                
                # #region debug log
                try:
                    with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                        import json
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"G","location":"messaging_handler.py:send_message:undelivered_status","message":"Message undelivered - checking error details","data":{"status":message.status,"error_code":error_code,"error_message":error_message,"to":to_number,"from":from_number},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                except: pass
                # #endregion
                
                if error_code:
                    logger.error(f"   Error Code: {error_code}")
                    
                    # Specific handling for common error codes
                    if error_code == 30034:
                        logger.error("   Error 30034: Message blocked by carrier or recipient opt-out")
                        logger.error("   Possible causes:")
                        logger.error("     - A2P 10DLC registration required (MOST LIKELY - even with paid account)")
                        logger.error("     - Recipient has opted out/unsubscribed")
                        logger.error("     - Carrier blocking")
                        logger.error("     - Number on Do Not Call list")
                        logger.error("   Solutions (in order):")
                        logger.error("     1. Complete A2P 10DLC Registration (REQUIRED for US SMS):")
                        logger.error("        a. Go to: https://console.twilio.com/us1/develop/sms/a2p-messaging")
                        logger.error("        b. Register your Brand (company/organization)")
                        logger.error("        c. Create a Campaign (use case for messaging)")
                        logger.error("        d. Wait for approval (can take 1-3 business days)")
                        logger.error("     2. Check if recipient opted out:")
                        logger.error("        - Go to Twilio Console → Messaging → Opt-outs")
                        logger.error("        - Check if +14049525557 is listed")
                        logger.error("     3. Contact Twilio Support with Message SID:")
                        logger.error(f"        {message.sid}")
                        logger.error("     4. Try sending from a different Twilio number")
                        
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
                    is_verified = any(v.phone_number == to_number or v.phone_number == to_number.replace('+', '') for v in verified_numbers)
                    
                    # #region debug log
                    try:
                        with open('/Users/matedort/phone-call-agent/.cursor/debug.log', 'a') as f:
                            import json
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"G","location":"messaging_handler.py:send_message:check_verified","message":"Checking if number is verified","data":{"to_number":to_number,"is_verified":is_verified,"verified_count":len(verified_numbers)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                    except: pass
                    # #endregion
                    
                    if not is_verified:
                        logger.warning(f"   ⚠️  Number {to_number} is NOT verified in Twilio")
                        logger.warning(f"   Verify at: https://console.twilio.com/us1/develop/phone-numbers/manage/verified")
                    else:
                        logger.warning(f"   ✓ Number {to_number} IS verified, but message still undelivered")
                        logger.warning(f"   This may be a carrier blocking issue or account restriction")
                except Exception as e:
                    logger.warning(f"   Could not check verification status: {e}")
                
                logger.warning(f"   Check Twilio Console → Messaging → Logs → Click 'Troubleshoot' for details")
            elif message.status == 'failed':
                logger.error(f"❌ Message {message.sid} failed to send")
                if hasattr(message, 'error_message') and message.error_message:
                    logger.error(f"   Error: {message.error_message}")
                if hasattr(message, 'error_code') and message.error_code:
                    logger.error(f"   Error Code: {message.error_code}")
            elif message.status in ['sent', 'delivered']:
                logger.info(f"✅ Message {message.sid} {message.status} successfully")
            
            logger.info(f"Sent {medium} message to {to_number}: {message.sid} (status: {message.status})")
            
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

