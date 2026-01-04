#!/usr/bin/env python3
"""Test script for Agent Hub foundation components."""
import asyncio
from datetime import datetime

from agent_session import AgentSession, SessionType, PermissionLevel, generate_session_id
from security import authenticate_phone_number, filter_functions_by_permission, get_session_capabilities
from session_manager import SessionManager
from message_router import MessageRouter
from database import Database
from config import Config


async def test_authentication():
    """Test phone number authentication"""
    print("\n" + "="*60)
    print("TEST 1: Phone Number Authentication")
    print("="*60)

    # Test Máté's number
    mate_permission = authenticate_phone_number(Config.TARGET_PHONE_NUMBER)
    print(f"✓ {Config.TARGET_PHONE_NUMBER} → {mate_permission.value} access")
    assert mate_permission == PermissionLevel.FULL, "Máté should have FULL access"

    # Test unknown number
    unknown_permission = authenticate_phone_number("+15551234567")
    print(f"✓ +15551234567 → {unknown_permission.value} access")
    assert unknown_permission == PermissionLevel.LIMITED, "Unknown should have LIMITED access"

    print("\n✅ Authentication tests passed!")


async def test_permission_filtering():
    """Test function filtering by permission level"""
    print("\n" + "="*60)
    print("TEST 2: Permission-Based Function Filtering")
    print("="*60)

    # Mock function declarations
    mock_functions = [
        {"name": "get_current_time"},
        {"name": "add_reminder"},
        {"name": "make_call"},
        {"name": "take_message_for_mate"},
        {"name": "schedule_callback"},
        {"name": "search_contact"}
    ]

    # Test FULL access
    full_functions = filter_functions_by_permission(PermissionLevel.FULL, mock_functions)
    print(f"✓ FULL access: {len(full_functions)}/{len(mock_functions)} functions")
    assert len(full_functions) == len(mock_functions), "FULL should have all functions"

    # Test LIMITED access
    limited_functions = filter_functions_by_permission(PermissionLevel.LIMITED, mock_functions)
    print(f"✓ LIMITED access: {len(limited_functions)}/{len(mock_functions)} functions")
    limited_names = {f["name"] for f in limited_functions}
    print(f"  Allowed: {', '.join(limited_names)}")

    # Verify limited functions
    assert "add_reminder" not in limited_names, "LIMITED should not have add_reminder"
    assert "make_call" not in limited_names, "LIMITED should not have make_call"
    assert "take_message_for_mate" in limited_names, "LIMITED should have take_message_for_mate"

    print("\n✅ Permission filtering tests passed!")


async def test_database_tables():
    """Test new database tables"""
    print("\n" + "="*60)
    print("TEST 3: Database Tables & Methods")
    print("="*60)

    db = Database("test_agent_hub.db")

    # Test agent_sessions table
    session_dict = {
        'session_id': generate_session_id(),
        'call_sid': 'CA_test_123',
        'session_name': 'Call with Máté (main)',
        'phone_number': Config.TARGET_PHONE_NUMBER,
        'permission_level': 'full',
        'session_type': 'inbound_user',
        'purpose': None,
        'status': 'active',
        'parent_session_id': None,
        'created_at': datetime.now().isoformat()
    }

    session_id = db.add_agent_session(session_dict)
    print(f"✓ Created session: {session_dict['session_name']}")

    # Retrieve session
    retrieved = db.get_session_by_id(session_dict['session_id'])
    assert retrieved is not None, "Should retrieve session"
    print(f"✓ Retrieved session: {retrieved['session_name']}")

    # Test inter_session_messages table
    message_id = "msg_test_123"
    db.add_inter_session_message(
        message_id=message_id,
        from_session_id=session_dict['session_id'],
        to_session_id=None,
        to_session_name="user",
        message_type="direct",
        message_body="Test message",
        status="delivered"
    )
    print(f"✓ Created inter-session message")

    msg = db.get_inter_session_message(message_id)
    assert msg is not None, "Should retrieve message"
    print(f"✓ Retrieved message: {msg['message_body']}")

    # Test broadcast_approvals table
    approval_id = db.add_broadcast_approval("test_group", approved=1)
    print(f"✓ Created broadcast approval")

    approval = db.get_broadcast_approval("test_group")
    assert approval is not None, "Should retrieve approval"
    assert approval['approved'] == 1, "Should be approved"
    print(f"✓ Retrieved approval: group={approval['session_group']}, approved={approval['approved']}")

    # Cleanup
    import os
    db.close()
    os.remove("test_agent_hub.db")

    print("\n✅ Database tests passed!")


async def test_session_manager():
    """Test SessionManager (without actual Gemini clients)"""
    print("\n" + "="*60)
    print("TEST 4: SessionManager")
    print("="*60)

    db = Database("test_session_manager.db")
    session_manager = SessionManager(db)

    # Test session stats
    stats = session_manager.get_session_stats()
    print(f"✓ Session stats: {stats['total']} total, {stats['active']} active")

    # Test max concurrent sessions limit
    print(f"✓ Max concurrent sessions: {Config.MAX_CONCURRENT_SESSIONS}")

    # Cleanup
    db.close()
    import os
    os.remove("test_session_manager.db")

    print("\n✅ SessionManager tests passed!")


async def test_message_router():
    """Test MessageRouter (without actual sessions)"""
    print("\n" + "="*60)
    print("TEST 5: MessageRouter")
    print("="*60)

    db = Database("test_router.db")
    session_manager = SessionManager(db)

    # Mock messaging handler
    class MockMessagingHandler:
        async def send_message(self, to_number, message, medium='sms'):
            print(f"  [MOCK] Would send SMS to {to_number}: {message[:50]}...")

    messaging_handler = MockMessagingHandler()
    router = MessageRouter(session_manager, messaging_handler, db)

    # Start router
    await router.start()
    print("✓ Router started")

    # Check stats
    stats = router.get_stats()
    print(f"✓ Router stats: running={stats['running']}, queue_size={stats['queue_size']}")

    # Stop router
    await router.stop()
    print("✓ Router stopped")

    # Cleanup
    db.close()
    import os
    os.remove("test_router.db")

    print("\n✅ MessageRouter tests passed!")


async def test_config():
    """Test new config values"""
    print("\n" + "="*60)
    print("TEST 6: Configuration")
    print("="*60)

    print(f"✓ TARGET_NAME: {Config.TARGET_NAME}")
    print(f"✓ TARGET_PHONE_NUMBER: {Config.TARGET_PHONE_NUMBER}")
    print(f"✓ MAX_CONCURRENT_SESSIONS: {Config.MAX_CONCURRENT_SESSIONS}")
    print(f"✓ CALLBACK_REPORT: {Config.CALLBACK_REPORT}")

    print("\n✅ Config tests passed!")


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("AGENT HUB FOUNDATION TESTS")
    print("="*60)
    print("\nTesting foundation components before integration...\n")

    try:
        await test_authentication()
        await test_permission_filtering()
        await test_database_tables()
        await test_session_manager()
        await test_message_router()
        await test_config()

        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nFoundation is ready for integration.")
        print("\nNext steps:")
        print("  1. Update sub_agents_tars.py with InterSessionAgent")
        print("  2. Update twilio_media_streams.py to use SessionManager")
        print("  3. Update reminder_checker.py for multi-session awareness")
        print("  4. Update main_tars.py to wire everything together")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
