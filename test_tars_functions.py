#!/usr/bin/env python3
"""Test script for TARS function calling capabilities.

This script creates a Mate main Gemini session and tests all available functions.
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
from gemini_live_client import GeminiLiveClient
from translations import format_text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TARSTester:
    """Test harness for TARS function calling."""
    
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
                # Track that this function was called
                self.function_calls_tracked[func_name] = {
                    "called": True,
                    "args": args,
                    "timestamp": datetime.now().isoformat()
                }
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
            self.function_calls_tracked["get_current_time"] = {
                "called": True,
                "args": args,
                "timestamp": datetime.now().isoformat()
            }
            from datetime import datetime
            now = datetime.now()
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
        self.function_calls_tracked = {}  # Track which functions were called
        
    async def run_test(self):
        """Run the full test suite."""
        print("\n" + "="*80)
        print("TARS FUNCTION CALLING TEST SUITE")
        print("="*80 + "\n")
        
        # Get all function declarations
        all_functions = get_function_declarations()
        print(f"Found {len(all_functions)} function declarations\n")
        
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
        
        # Test 1: Ask TARS what it can do
        print("\n" + "-"*80)
        print("TEST 1: Asking TARS to list all capabilities")
        print("-"*80)
        
        test_prompt = """Please list all the functions and capabilities you have access to. 
For each function, tell me:
1. The function name
2. What it does
3. What parameters it requires

Be comprehensive and detailed."""
        
        response_buffer.clear()
        await session.gemini_client.send_text(test_prompt, end_of_turn=True)
        
        # Wait for response
        await asyncio.sleep(5)
        
        full_response = ''.join(response_buffer)
        self.responses.append(("capabilities_list", full_response))
        print(f"\n📋 Full Response:\n{full_response}\n")
        
        # Test 2: Test ALL functions systematically
        print("\n" + "-"*80)
        print("TEST 2: Testing ALL function calls")
        print("-"*80)
        
        # Get all function declarations and create tests
        all_functions = get_function_declarations()
        
        # Define test prompts for each function based on their descriptions
        function_tests = {
            "get_current_time": {
                "prompt": "What time is it right now?",
                "expected_keywords": ["time", "date", "current"]
            },
            "adjust_config": {
                "prompt": "Get the current humor percentage setting",
                "expected_keywords": ["humor", "percentage", "setting"]
            },
            "manage_reminder": {
                "prompt": "List all my reminders",
                "expected_keywords": ["reminder", "reminders"]
            },
            "lookup_contact": {
                "prompt": "List all contacts",
                "expected_keywords": ["contact", "contacts"]
            },
            "send_notification": {
                "prompt": "Send me a test notification saying 'Function test'",
                "expected_keywords": ["notification", "sent", "test"]
            },
            "search_conversations": {
                "prompt": "Search for conversations from today",
                "expected_keywords": ["conversation", "search"]
            },
            "send_message": {
                "prompt": "This is just a test - do not actually send any message",
                "expected_keywords": ["message", "send"]
            },
            "send_email": {
                "prompt": "This is just a test - do not actually send any email",
                "expected_keywords": ["email", "send"]
            },
            "archive_email": {
                "prompt": "This is just a test - do not actually archive any email",
                "expected_keywords": ["archive", "email"]
            },
            "delete_email": {
                "prompt": "This is just a test - do not actually delete any email",
                "expected_keywords": ["delete", "email"]
            },
            "make_draft": {
                "prompt": "This is just a test - do not actually create any draft",
                "expected_keywords": ["draft", "create"]
            },
            "search_emails": {
                "prompt": "Search for emails in the inbox, limit to 3",
                "expected_keywords": ["email", "search", "inbox"]
            },
            "list_drafts": {
                "prompt": "List all email drafts",
                "expected_keywords": ["draft", "drafts"]
            },
            "bulk_delete_emails": {
                "prompt": "This is just a test - do not actually delete any emails",
                "expected_keywords": ["delete", "bulk"]
            },
            "send_draft": {
                "prompt": "This is just a test - do not actually send any draft",
                "expected_keywords": ["draft", "send"]
            },
            "delete_draft": {
                "prompt": "This is just a test - do not actually delete any draft",
                "expected_keywords": ["draft", "delete"]
            },
            "make_goal_call": {
                "prompt": "This is just a test - do not actually make any call",
                "expected_keywords": ["call", "goal"]
            },
            "list_active_sessions": {
                "prompt": "List all active sessions",
                "expected_keywords": ["session", "sessions", "active"]
            },
            "get_session_info": {
                "prompt": "Get information about the current session",
                "expected_keywords": ["session", "info", "information"]
            },
            "send_message_to_session": {
                "prompt": "This is just a test - do not actually send any message to session",
                "expected_keywords": ["session", "message"]
            },
            "request_user_confirmation": {
                "prompt": "This is just a test - do not actually request confirmation",
                "expected_keywords": ["confirmation", "confirm"]
            },
            "schedule_callback": {
                "prompt": "This is just a test - do not actually schedule any callback",
                "expected_keywords": ["callback", "schedule"]
            },
            "hangup_call": {
                "prompt": "This is just a test - do not actually hang up any call",
                "expected_keywords": ["hangup", "call"]
            },
            "suspend_session": {
                "prompt": "This is just a test - do not actually suspend any session",
                "expected_keywords": ["suspend", "session"]
            },
            "resume_session": {
                "prompt": "This is just a test - do not actually resume any session",
                "expected_keywords": ["resume", "session"]
            },
            "suggest_phone_call": {
                "prompt": "This is just a test - do not actually suggest any call",
                "expected_keywords": ["call", "suggest"]
            }
        }
        
        # Test each function
        for func_decl in all_functions:
            func_name = func_decl.get("name")
            if func_name not in function_tests:
                print(f"\n⚠️  No test defined for: {func_name}")
                continue
            
            test = function_tests[func_name]
            print(f"\n🧪 Testing: {func_name}")
            print(f"   Prompt: {test['prompt']}")
            print(f"   Description: {func_decl.get('description', '')[:80]}...")
            
            response_buffer.clear()
            # Clear tracking for this function
            if func_name in self.function_calls_tracked:
                del self.function_calls_tracked[func_name]
            
            await session.gemini_client.send_text(test['prompt'], end_of_turn=True)
            await asyncio.sleep(4)  # Give more time for function calls
            
            response = ''.join(response_buffer)
            self.responses.append((func_name, response))
            
            # Check if function was called (from our tracking)
            if func_name in self.function_calls_tracked and self.function_calls_tracked[func_name].get("called"):
                print(f"   ✅ Function WAS CALLED")
                call_info = self.function_calls_tracked[func_name]
                print(f"      Args used: {call_info.get('args', {})}")
                # Check if response contains expected keywords
                response_lower = response.lower()
                keywords_found = [kw for kw in test['expected_keywords'] if kw in response_lower]
                if keywords_found:
                    print(f"   ✅ Response contains expected keywords: {keywords_found}")
                    self.results[func_name] = "PASS"
                else:
                    print(f"   ⚠️  Function called but response doesn't match expected keywords")
                    self.results[func_name] = "PARTIAL"
            else:
                print(f"   ❌ Function was NOT called")
                self.results[func_name] = "FAIL"
            
            print(f"   Response: {response[:150]}...")
        
        # Generate report
        await self.generate_report(session)
        
        # Cleanup
        await session.gemini_client.disconnect()
        await self.session_manager.terminate_session(session.session_id)
        
    async def generate_report(self, session):
        """Generate test report."""
        print("\n" + "="*80)
        print("TEST REPORT")
        print("="*80 + "\n")
        
        total_tests = len(self.results)
        passed = sum(1 for r in self.results.values() if r == "PASS")
        partial = sum(1 for r in self.results.values() if r == "PARTIAL")
        failed = sum(1 for r in self.results.values() if r == "FAIL")
        
        print(f"Total Functions Tested: {total_tests}")
        print(f"✅ Passed: {passed}")
        print(f"⚠️  Partial: {partial}")
        print(f"❌ Failed: {failed}")
        print(f"\nScore: {passed}/{total_tests} ({passed*100//total_tests if total_tests > 0 else 0}%)")
        print(f"Success Rate (Passed + Partial): {(passed + partial)*100//total_tests if total_tests > 0 else 0}%\n")
        
        print("Detailed Results:")
        print("-"*80)
        for func_name, result in sorted(self.results.items()):
            if result == "PASS":
                status_emoji = "✅"
            elif result == "PARTIAL":
                status_emoji = "⚠️"
            else:
                status_emoji = "❌"
            called_status = "CALLED" if func_name in self.function_calls_tracked else "NOT CALLED"
            print(f"{status_emoji} {func_name}: {result} ({called_status})")
        
        print("\n" + "-"*80)
        print("All Function Declarations:")
        print("-"*80)
        all_functions = get_function_declarations()
        for func in all_functions:
            print(f"  • {func.get('name', 'unknown')}: {func.get('description', 'no description')[:60]}...")
        
        print("\n" + "="*80)
        print("Test Complete!")
        print("="*80 + "\n")


async def main():
    """Main entry point."""
    if not Config.GEMINI_API_KEY:
        print("❌ Error: GEMINI_API_KEY not set in environment")
        sys.exit(1)
    
    if not Config.TARGET_EMAIL:
        print("❌ Error: TARGET_EMAIL not set in environment")
        sys.exit(1)
    
    tester = TARSTester()
    try:
        await tester.run_test()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
