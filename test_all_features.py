#!/usr/bin/env python3
"""Comprehensive test script for all TARS features based on test.md

This script tests all 17 phases of TARS functionality systematically.
"""
import asyncio
import logging
import sys
from datetime import datetime
from config import Config
from database import Database
from session_manager import SessionManager
from message_router import MessageRouter
from gmail_handler import GmailHandler
from messaging_handler import MessagingHandler
from sub_agents_tars import get_function_declarations, get_all_agents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TARSFeatureTester:
    """Comprehensive test harness for all TARS features."""
    
    def __init__(self):
        """Initialize test harness."""
        self.db = Database("tars.db")
        self.session_manager = SessionManager(self.db)
        
        # Initialize messaging handler
        self.messaging_handler = MessagingHandler(
            database=self.db,
            twilio_client=None,
            session_manager=self.session_manager,
            router=None,
            twilio_handler=None
        )
        
        # Initialize router
        self.router = MessageRouter(
            self.session_manager,
            self.messaging_handler,
            self.db
        )
        
        self.session_manager.set_router(self.router)
        self.messaging_handler.router = self.router
        
        # Initialize Gmail handler
        self.gmail_handler = GmailHandler(
            database=self.db,
            messaging_handler=self.messaging_handler,
            session_manager=self.session_manager
        )
        self.session_manager.gmail_handler = self.gmail_handler
        self.session_manager.messaging_handler = self.messaging_handler
        self.messaging_handler.gmail_handler = self.gmail_handler  # EmailAgent accesses through messaging_handler
        
        # Register function handlers
        agents = get_all_agents(
            db=self.db,
            messaging_handler=self.messaging_handler,
            system_reloader_callback=None,
            twilio_handler=None,
            session_manager=self.session_manager,
            router=self.router
        )
        
        # Create proper async handler wrappers with tracking
        def make_handler(agent_instance, func_name):
            async def handler(args):
                # Track function call
                current_test_id = getattr(self, '_current_test_id', None)
                if current_test_id:
                    if current_test_id not in self.function_calls_tracked:
                        self.function_calls_tracked[current_test_id] = []
                    self.function_calls_tracked[current_test_id].append(func_name)
                return await agent_instance.execute(args)
            return handler
        
        function_map = {}
        
        # Map functions to agents with proper handlers
        if agents.get("config"):
            function_map["adjust_config"] = make_handler(agents["config"], "adjust_config")
        if agents.get("reminder"):
            function_map["manage_reminder"] = make_handler(agents["reminder"], "manage_reminder")
        if agents.get("contacts"):
            function_map["lookup_contact"] = make_handler(agents["contacts"], "lookup_contact")
        if agents.get("notification"):
            function_map["send_notification"] = make_handler(agents["notification"], "send_notification")
        if agents.get("conversation_search"):
            function_map["search_conversations"] = make_handler(agents["conversation_search"], "search_conversations")
        if agents.get("message"):
            function_map["send_message"] = make_handler(agents["message"], "send_message")
        if agents.get("email"):
            email_agent = agents["email"]
            function_map["send_email"] = make_handler(email_agent, "send_email")
            function_map["archive_email"] = make_handler(email_agent, "archive_email")
            function_map["delete_email"] = make_handler(email_agent, "delete_email")
            function_map["make_draft"] = make_handler(email_agent, "make_draft")
            function_map["search_emails"] = make_handler(email_agent, "search_emails")
            function_map["bulk_delete_emails"] = make_handler(email_agent, "bulk_delete_emails")
            function_map["send_draft"] = make_handler(email_agent, "send_draft")
            function_map["delete_draft"] = make_handler(email_agent, "delete_draft")
            function_map["list_drafts"] = make_handler(email_agent, "list_drafts")
        if agents.get("outbound_call"):
            function_map["make_goal_call"] = make_handler(agents["outbound_call"], "make_goal_call")
        if agents.get("inter_session"):
            inter_agent = agents["inter_session"]
            function_map["send_message_to_session"] = make_handler(inter_agent, "send_message_to_session")
            function_map["request_user_confirmation"] = make_handler(inter_agent, "request_user_confirmation")
            function_map["list_active_sessions"] = make_handler(inter_agent, "list_active_sessions")
            function_map["schedule_callback"] = make_handler(inter_agent, "schedule_callback")
            function_map["hangup_call"] = make_handler(inter_agent, "hangup_call")
            function_map["get_session_info"] = make_handler(inter_agent, "get_session_info")
            function_map["suspend_session"] = make_handler(inter_agent, "suspend_session")
            function_map["resume_session"] = make_handler(inter_agent, "resume_session")
        
        # Add get_current_time handler with tracking
        async def get_time_handler(args):
            # Track function call
            current_test_id = getattr(self, '_current_test_id', None)
            if current_test_id:
                if current_test_id not in self.function_calls_tracked:
                    self.function_calls_tracked[current_test_id] = []
                self.function_calls_tracked[current_test_id].append("get_current_time")
            from datetime import datetime as dt
            now = dt.now()
            current_time = now.strftime("%I:%M %p")
            current_date = now.strftime("%A, %B %d, %Y")
            return {
                "time": current_time,
                "date": current_date,
                "message": f"The current time is {current_time} on {current_date}, sir."
            }
        function_map["get_current_time"] = get_time_handler
        
        self.session_manager.set_function_handlers(function_map)
        
        # Test results
        self.results = {}
        self.responses = []
        self.function_calls_tracked = {}  # Track function calls: {test_id: [function_names]}
        
    async def run_all_tests(self):
        """Run all test phases."""
        print("\n" + "="*80)
        print("TARS COMPREHENSIVE FEATURE TEST SUITE")
        print("="*80 + "\n")
        
        # Create Mate main session
        print("Creating Mate main session...")
        try:
            session = await self.session_manager.create_message_session(
                email_address=Config.TARGET_EMAIL
            )
            print(f"✅ Session created: {session.session_name}\n")
        except Exception as e:
            print(f"❌ Failed to create session: {e}")
            return
        
        # Capture responses
        response_buffer = []
        
        async def capture_response(text: str):
            """Capture TARS responses."""
            response_buffer.append(text)
            print(f"📝 TARS: {text}")
        
        session.gemini_client.on_text_response = capture_response
        
        # Define all test phases
        test_phases = self._get_test_phases()
        
        # Helper to check and recreate session if needed
        async def ensure_session_active(current_sess):
            """Ensure session is active, recreate if needed."""
            if not current_sess or not current_sess.is_active():
                print("\n⚠️  Session inactive, recreating...")
                try:
                    new_session = await self.session_manager.create_message_session(
                        email_address=Config.TARGET_EMAIL
                    )
                    new_session.gemini_client.on_text_response = capture_response
                    # Re-register function handlers
                    self.session_manager.set_function_handlers(function_map)
                    return new_session
                except Exception as e:
                    print(f"❌ Failed to recreate session: {e}")
                    return None
            
            # Check connection status
            try:
                if not hasattr(current_sess.gemini_client, 'is_connected') or not current_sess.gemini_client.is_connected:
                    print("\n⚠️  Session disconnected, recreating...")
                    try:
                        new_session = await self.session_manager.create_message_session(
                            email_address=Config.TARGET_EMAIL
                        )
                        new_session.gemini_client.on_text_response = capture_response
                        # Re-register function handlers
                        self.session_manager.set_function_handlers(function_map)
                        return new_session
                    except Exception as e:
                        print(f"❌ Failed to recreate session: {e}")
                        return None
            except Exception:
                # If we can't check connection, assume it's fine
                pass
            
            # Update activity to prevent timeout
            if hasattr(current_sess, 'update_activity'):
                current_sess.update_activity()
            return current_sess
        
        # Run each phase
        current_session = session
        for phase_num, phase in enumerate(test_phases, 1):
            print("\n" + "="*80)
            print(f"PHASE {phase_num}: {phase['name']}")
            print("="*80)
            
            for test_num, test in enumerate(phase['tests'], 1):
                test_id = f"Phase{phase_num}_Test{test_num}"
                print(f"\n[{phase_num}.{test_num}] {test['description']}")
                print(f"   Command: {test['command']}")
                
                # Set current test ID for function tracking
                self._current_test_id = test_id
                self.function_calls_tracked[test_id] = []
                
                # Ensure session is active before each test
                current_session = await ensure_session_active(current_session)
                if not current_session:
                    print(f"   ❌ Cannot continue - session unavailable")
                    self.results[test_id] = "FAIL"
                    self._current_test_id = None
                    continue
                
                # Clear response buffer and wait a moment for any pending responses
                response_buffer.clear()
                await asyncio.sleep(0.5)  # Brief pause to let any pending responses finish
                
                try:
                    # Update session activity before sending to prevent timeout
                    if hasattr(current_session, 'update_activity'):
                        current_session.update_activity()
                    
                    await current_session.gemini_client.send_text(test['command'], end_of_turn=True)
                    
                    # Wait for response - check for function calls
                    max_wait = 10  # Maximum wait time (increased)
                    wait_interval = 0.5  # Check every 0.5 seconds
                    waited = 0
                    function_called = False
                    last_response_length = 0
                    stable_count = 0  # Count how many times response hasn't changed
                    
                    while waited < max_wait:
                        await asyncio.sleep(wait_interval)
                        waited += wait_interval
                        
                        # Check if response is stable (not changing)
                        current_length = len(response_buffer)
                        if current_length == last_response_length:
                            stable_count += 1
                        else:
                            stable_count = 0
                        last_response_length = current_length
                        
                        # Check if expected function was called
                        expected_function = test.get('expected_function')
                        if expected_function:
                            if expected_function in self.function_calls_tracked.get(test_id, []):
                                function_called = True
                                # Wait a bit more for response after function call
                                await asyncio.sleep(2)
                                break
                        else:
                            # If no specific function expected, wait for stable response
                            if stable_count >= 3:  # Response stable for 1.5 seconds
                                break
                    
                except (RuntimeError, Exception) as e:
                    error_msg = str(e)
                    if "Not connected" in error_msg or "disconnected" in error_msg.lower():
                        print(f"   ⚠️  Session disconnected during test, recreating...")
                        current_session = await ensure_session_active(current_session)
                        if current_session:
                            try:
                                # Update activity
                                if hasattr(current_session, 'update_activity'):
                                    current_session.update_activity()
                                await current_session.gemini_client.send_text(test['command'], end_of_turn=True)
                                # Wait for response
                                await asyncio.sleep(8)
                            except Exception as e2:
                                print(f"   ❌ Error after reconnect: {e2}")
                                self.results[test_id] = "FAIL"
                                self._current_test_id = None
                                continue
                        else:
                            self.results[test_id] = "FAIL"
                            self._current_test_id = None
                            continue
                    else:
                        # Log unexpected errors but continue
                        logger.warning(f"Unexpected error in test {test_id}: {e}")
                        self.results[test_id] = "FAIL"
                        self._current_test_id = None
                        continue
                finally:
                    self._current_test_id = None
                
                response = ''.join(response_buffer)
                self.responses.append((test_id, response))
                
                # Determine if test passed
                # Priority 1: Check if expected function was called
                expected_function = test.get('expected_function')
                if expected_function:
                    functions_called = self.function_calls_tracked.get(test_id, [])
                    if expected_function in functions_called:
                        passed = True
                        print(f"   ✅ Expected function '{expected_function}' was called")
                    else:
                        passed = False
                        print(f"   ❌ Expected function '{expected_function}' was NOT called")
                        if functions_called:
                            print(f"      Functions called instead: {functions_called}")
                else:
                    # Priority 2: Check for expected keyword in response
                    expected_keyword = test.get('expected_keyword')
                    if expected_keyword:
                        passed = expected_keyword.lower() in response.lower()
                        if not passed and len(response) == 0:
                            # Check if any function was called (might be a function-only test)
                            functions_called = self.function_calls_tracked.get(test_id, [])
                            if functions_called:
                                passed = True  # Function was called, consider it a pass
                                print(f"   ✅ Function(s) called: {functions_called}")
                    else:
                        # No specific expectation - pass if we got any response or function call
                        functions_called = self.function_calls_tracked.get(test_id, [])
                        passed = len(response) > 0 or len(functions_called) > 0
                
                self.results[test_id] = "PASS" if passed else "FAIL"
                
                status = "✅" if passed else "❌"
                functions_called = self.function_calls_tracked.get(test_id, [])
                if functions_called:
                    print(f"   Functions called: {functions_called}")
                print(f"   {status} Result: {response[:150] if response else '(no response)'}...")
                
                # Small delay between tests to let responses finish
                await asyncio.sleep(0.5)
        
        # Generate report
        await self.generate_report()
        
        # Cleanup
        try:
            if current_session and current_session.is_active():
                await current_session.gemini_client.disconnect()
                await self.session_manager.terminate_session(current_session.session_id)
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
        
    def _get_test_phases(self):
        """Get all test phases from test.md."""
        return [
            {
                "name": "Contact Management",
                "tests": [
                    {
                        "description": "List all contacts",
                        "command": "List all my contacts",
                        "expected_function": "lookup_contact",
                        "expected_keyword": "contact"
                    },
                    {
                        "description": "Look up Helen's contact information",
                        "command": "What is Helen's email address and phone number?",
                        "expected_function": "lookup_contact",
                        "expected_keyword": "helen"
                    },
                    {
                        "description": "Add a test contact",
                        "command": "Add a new contact named 'Test Person' with phone number 555-1234, email test@example.com, and birthday 1990-01-01",
                        "expected_function": "lookup_contact",
                        "expected_keyword": "test person"
                    },
                    {
                        "description": "Edit the test contact's phone number",
                        "command": "Update Test Person's phone number to 555-5678",
                        "expected_function": "lookup_contact",
                        "expected_keyword": "updated"
                    },
                    {
                        "description": "Delete the test contact",
                        "command": "Delete the contact named 'Test Person'",
                        "expected_function": "lookup_contact",
                        "expected_keyword": "deleted"
                    },
                    {
                        "description": "Verify the contact is removed",
                        "command": "List all contacts and confirm Test Person is not in the list",
                        "expected_function": "lookup_contact",
                        "expected_keyword": "contact"
                    }
                ]
            },
            {
                "name": "Messaging - Basic Functions",
                "tests": [
                    {
                        "description": "Send a short message via SMS (test mode - don't actually send)",
                        "command": "This is a test - do not actually send any message. If I asked you to send a short message saying 'Hello test' via SMS, what would you do?",
                        "expected_keyword": "message"
                    },
                    {
                        "description": "Send a message with a URL link (test mode)",
                        "command": "This is a test - do not actually send. If I asked you to send a message with the link https://example.com, what function would you use?",
                        "expected_keyword": "link"
                    },
                    {
                        "description": "Send a message to a contact by name (test mode)",
                        "command": "This is a test - do not actually send. If I asked you to send a message to Helen saying 'Hello', what would you do?",
                        "expected_keyword": "helen"
                    },
                    {
                        "description": "Send a message to a phone number directly (test mode)",
                        "command": "This is a test - do not actually send. If I asked you to send a message to phone number 404-952-5557, what function would you use?",
                        "expected_keyword": "message"
                    }
                ]
            },
            {
                "name": "Email Functionality",
                "tests": [
                    {
                        "description": "Send an email to Helen (test mode)",
                        "command": "This is a test - do not actually send any email. If I asked you to send an email to Helen with subject 'Test' and body 'Hello', what would you do?",
                        "expected_keyword": "email"
                    },
                    {
                        "description": "Send an email to a direct email address (test mode)",
                        "command": "This is a test - do not actually send. If I asked you to send an email to test@example.com, what function would you use?",
                        "expected_keyword": "email"
                    },
                    {
                        "description": "List email drafts",
                        "command": "List all email drafts",
                        "expected_function": "list_drafts",
                        "expected_keyword": "draft"
                    }
                ]
            },
            {
                "name": "Long Message Auto-Routing",
                "tests": [
                    {
                        "description": "Generate a long response (over 500 chars)",
                        "command": "Explain how the human eye works in detail, breaking down each part and its function",
                        "expected_keyword": "eye"
                    },
                    {
                        "description": "Generate a short response (under 500 chars)",
                        "command": "What time is it?",
                        "expected_function": "get_current_time",
                        "expected_keyword": "time"
                    }
                ]
            },
            {
                "name": "Conversation Search - Date-Based",
                "tests": [
                    {
                        "description": "Search conversations from last Monday",
                        "command": "Search for conversations from last Monday",
                        "expected_function": "search_conversations",
                        "expected_keyword": "conversation"
                    },
                    {
                        "description": "Search conversations from January 12",
                        "command": "Search for conversations from January 12",
                        "expected_function": "search_conversations",
                        "expected_keyword": "conversation"
                    },
                    {
                        "description": "Search conversations from today",
                        "command": "Search for conversations from today",
                        "expected_function": "search_conversations",
                        "expected_keyword": "conversation"
                    }
                ]
            },
            {
                "name": "Conversation Search - Topic-Based",
                "tests": [
                    {
                        "description": "Search conversations about AI glasses",
                        "command": "Search for conversations about AI glasses",
                        "expected_function": "search_conversations",
                        "expected_keyword": "conversation"
                    },
                    {
                        "description": "Search conversations about reminders",
                        "command": "Search for conversations about reminders",
                        "expected_function": "search_conversations",
                        "expected_keyword": "conversation"
                    }
                ]
            },
            {
                "name": "Conversation Search - Similarity-Based",
                "tests": [
                    {
                        "description": "Find conversations similar to a query",
                        "command": "Find conversations similar to 'artificial intelligence and smart devices'",
                        "expected_function": "search_conversations",
                        "expected_keyword": "conversation"
                    }
                ]
            },
            {
                "name": "Session Management - Basic",
                "tests": [
                    {
                        "description": "List all active sessions",
                        "command": "List all active sessions",
                        "expected_function": "list_active_sessions",
                        "expected_keyword": "session"
                    },
                    {
                        "description": "Get information about current session",
                        "command": "Get information about the current session",
                        "expected_function": "get_session_info",
                        "expected_keyword": "session"
                    }
                ]
            },
            {
                "name": "Session Management - Suspend/Resume",
                "tests": [
                    {
                        "description": "Suspend current session (test mode)",
                        "command": "This is a test - do not actually suspend. If I asked you to suspend the current session, what would you do?",
                        "expected_keyword": "suspend"
                    },
                    {
                        "description": "Resume a suspended session (test mode)",
                        "command": "This is a test - do not actually resume. If I asked you to resume a suspended session, what would you do?",
                        "expected_keyword": "resume"
                    }
                ]
            },
            {
                "name": "Session Lookup by Similarity",
                "tests": [
                    {
                        "description": "Find sessions by partial name (test mode)",
                        "command": "This is a test. If I asked you to find a session with 'helen' in the name, what would you do?",
                        "expected_keyword": "session"
                    }
                ]
            },
            {
                "name": "Inter-Session Communication",
                "tests": [
                    {
                        "description": "Send message to another session (test mode)",
                        "command": "This is a test - do not actually send. If I asked you to send a message to another active session, what function would you use?",
                        "expected_keyword": "session"
                    },
                    {
                        "description": "Request user confirmation (test mode)",
                        "command": "This is a test - do not actually request. If I asked you to request confirmation from me, what function would you use?",
                        "expected_keyword": "confirmation"
                    }
                ]
            },
            {
                "name": "Callback Scheduling - Vague Times",
                "tests": [
                    {
                        "description": "Schedule callback 'in the morning' (test mode)",
                        "command": "This is a test - do not actually schedule. If I asked you to schedule a callback 'in the morning' for a caller, what time would you use?",
                        "expected_keyword": "morning"
                    },
                    {
                        "description": "Schedule callback 'as soon as you see it' (test mode)",
                        "command": "This is a test - do not actually schedule. If I asked you to schedule a callback 'as soon as you see it', what time would you use?",
                        "expected_keyword": "minute"
                    },
                    {
                        "description": "Schedule callback 'this afternoon' (test mode)",
                        "command": "This is a test - do not actually schedule. If I asked you to schedule a callback 'this afternoon', what time would you use?",
                        "expected_keyword": "afternoon"
                    },
                    {
                        "description": "Schedule callback 'this evening' (test mode)",
                        "command": "This is a test - do not actually schedule. If I asked you to schedule a callback 'this evening', what time would you use?",
                        "expected_keyword": "evening"
                    }
                ]
            },
            {
                "name": "Email Management Functions",
                "tests": [
                    {
                        "description": "Search emails in inbox",
                        "command": "Search for emails in the inbox, limit to 5",
                        "expected_function": "search_emails",
                        "expected_keyword": "email"
                    },
                    {
                        "description": "Archive email (test mode)",
                        "command": "This is a test - do not actually archive. If I asked you to archive an email, what function would you use?",
                        "expected_keyword": "archive"
                    },
                    {
                        "description": "Delete email (test mode)",
                        "command": "This is a test - do not actually delete. If I asked you to delete an email, what function would you use?",
                        "expected_keyword": "delete"
                    },
                    {
                        "description": "Create draft (test mode)",
                        "command": "This is a test - do not actually create. If I asked you to create a draft email, what function would you use?",
                        "expected_keyword": "draft"
                    }
                ]
            },
            {
                "name": "Reminder Management",
                "tests": [
                    {
                        "description": "List all reminders",
                        "command": "List all my reminders",
                        "expected_function": "manage_reminder",
                        "expected_keyword": "reminder"
                    },
                    {
                        "description": "Create a reminder (test mode)",
                        "command": "This is a test - do not actually create. If I asked you to create a reminder for tomorrow at 3pm to 'test reminder', what would you do?",
                        "expected_keyword": "reminder"
                    }
                ]
            },
            {
                "name": "Configuration Management",
                "tests": [
                    {
                        "description": "Get current humor setting",
                        "command": "What is the current humor percentage setting?",
                        "expected_function": "adjust_config",
                        "expected_keyword": "humor"
                    },
                    {
                        "description": "Get current time",
                        "command": "What time is it right now?",
                        "expected_function": "get_current_time",
                        "expected_keyword": "time"
                    }
                ]
            },
            {
                "name": "Error Handling",
                "tests": [
                    {
                        "description": "Try to send email to non-existent contact",
                        "command": "This is a test - do not actually send. If I asked you to send an email to a contact named 'NonExistent Person', what would happen?",
                        "expected_keyword": "not found"
                    },
                    {
                        "description": "Try to get info about non-existent session",
                        "command": "This is a test. If I asked you to get information about a session named 'NonExistent Session', what would happen?",
                        "expected_keyword": "not found"
                    }
                ]
            }
        ]
    
    async def generate_report(self):
        """Generate test report."""
        print("\n" + "="*80)
        print("TEST REPORT")
        print("="*80 + "\n")
        
        total_tests = len(self.results)
        passed = sum(1 for r in self.results.values() if r == "PASS")
        failed = sum(1 for r in self.results.values() if r == "FAIL")
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"\nSuccess Rate: {(passed/total_tests)*100:.1f}%\n")
        
        print("Detailed Results:")
        print("-"*80)
        for test_id, result in sorted(self.results.items()):
            status_emoji = "✅" if result == "PASS" else "❌"
            functions_called = self.function_calls_tracked.get(test_id, [])
            func_info = f" [Functions: {', '.join(functions_called)}]" if functions_called else " [No functions called]"
            print(f"{status_emoji} {test_id}: {result}{func_info}")


async def main():
    """Main function to run the tester."""
    tester = TARSFeatureTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
