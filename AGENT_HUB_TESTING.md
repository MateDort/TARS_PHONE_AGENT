# Agent Hub Testing Guide

## 🎉 System Ready for Testing!

All 11 integration tasks complete. The Agent Hub system is now fully operational with:
- ✅ Named sessions with phone authentication
- ✅ Inter-agent communication via MessageRouter
- ✅ Permission-based access control (FULL/LIMITED)
- ✅ Multi-session coordination (up to 10 concurrent)
- ✅ Smart callback routing (in-call vs SMS/call fallback)
- ✅ Unknown caller handling with notifications
- ✅ AI-generated call summaries

---

## 🚀 Quick Start

### 1. Start TARS
```bash
python main_tars.py
```

**Expected Terminal Output:**
```
🤖 TARS Phone Agent Starting...
📞 Twilio handler initialized
💬 Messaging handler initialized
✅ SessionManager initialized
✅ MessageRouter started
🔔 Reminder checker started
🌐 WebSocket server running on ws://0.0.0.0:8081
📱 Flask webhook server running on http://0.0.0.0:8080

🎯 TARS is ready! Agent Hub Enabled (max 10 sessions)
   - Phone: +1234567890
   - WebSocket: ws://your-ngrok-url.ngrok.io
```

---

## 🧪 Test Scenarios

### Test 1: Máté's Main Session (Full Access)
**Setup:** Call TARS from 404-952-5557

**Expected Behavior:**
1. Terminal shows:
   ```
   🔌 WEBSOCKET CONNECTED
      📞 Call SID: CAxxxx
      📱 Caller: +14049525557
      👤 Session: Call with Máté (main) (full access)
      Connecting to Gemini Live...
      ✅ Gemini Live connected (permission: full)
      👋 Greeting sent to TARS
   ```

2. TARS greets you in Hungarian/your language
3. All functions available (reminders, calls, contacts, messages, etc.)
4. Database shows:
   ```sql
   SELECT session_name, permission_level, status FROM agent_sessions;
   -- Result: "Call with Máté (main)", "full", "active"
   ```

**Test Commands:**
- "What's the weather?" (should work - full access)
- "Add a reminder for tomorrow at 3pm" (should work)
- "Call my mom" (should work)

---

### Test 2: Unknown Caller (Limited Access)
**Setup:** Call TARS from any number except 404-952-5557

**Expected Behavior:**
1. Terminal shows:
   ```
   🔌 WEBSOCKET CONNECTED
      📞 Call SID: CAxxxx
      📱 Caller: +19876543210
      👤 Session: Call with +19876543210 (limited access)
      Connecting to Gemini Live...
      ✅ Gemini Live connected (permission: limited)
      🔒 Limited access greeting sent
   ```

2. TARS says: "Hey, this is Máté Dort's assistant TARS, how can I help you?"
3. Máté receives notification (if in another call, it's announced; otherwise SMS/call)
4. Caller can ONLY:
   - Take messages: "Can you tell Máté that John called about the meeting?"
   - Schedule callbacks: "Ask Máté to call me back at 5pm"
   - Send messages to sessions: "Tell Máté's other session that..."

**Test Commands:**
- "What's the weather?" → ❌ "I don't have access to that function"
- "Can you take a message for Máté?" → ✅ Works
- "Schedule a callback for 3pm tomorrow" → ✅ Works

---

### Test 3: Inter-Session Communication
**Setup:** Have 2 active calls (Máté + one other)

**Scenario:** In Máté's call, say:
> "Send a message to [other session name] saying 'What's your favorite color?'"

**Expected Behavior:**
1. Terminal shows:
   ```
   [MessageRouter] Routing message to: Call with +19876543210
   [MessageRouter] Delivered to session: Call with +19876543210
   ```

2. Other call hears:
   > "[INTER-AGENT MESSAGE] Call with Máté (main) says: What's your favorite color?"

3. Database shows:
   ```sql
   SELECT * FROM inter_session_messages;
   -- Shows: from_session_id, to_session_id, message_body, status='delivered'
   ```

---

### Test 4: Multi-Session Scenario (Hotel Negotiation)
**Setup:** Test the classic scenario from requirements

**Steps:**
1. In Máté's call, say:
   > "Call Drury Hotel and ask for their best rate for March 15th"

2. TARS creates outbound session to hotel
3. Hotel quotes a price
4. In hotel call, TARS says:
   > "Let me check with Máté about that price. Can you hold on?"

5. TARS sends message to Máté's session:
   > "[INTER-AGENT MESSAGE] Call with Drury Hotel says: They're offering $120/night. Should I accept?"

6. Máté responds "Yes, book it"
7. TARS routes response back to hotel session
8. Hotel confirms booking
9. TARS generates AI summary and reports back to Máté

**Expected Terminal:**
```
👤 Session: Call with Máté (main) (full access)
👤 Session: Call with Drury Hotel (full access, parent: Máté-main)
[MessageRouter] Routing message from 'Call with Drury Hotel' to 'user'
[MessageRouter] Máté is in active call - announcing message
```

---

### Test 5: Session Limit (10 Concurrent Sessions)
**Setup:** Have 10 active calls, then try an 11th

**Expected Behavior:**
1. First 10 calls succeed normally
2. 11th call receives:
   > "I'm sorry, I'm currently at maximum capacity with 10 active calls. Please try again later."

3. Terminal shows:
   ```
   ❌ Maximum concurrent sessions (10) reached - rejecting call
   ```

---

### Test 6: Callback Routing (Goal-Based Call)
**Setup:** Máté requests outbound call to barber shop

**Steps:**
1. In Máté's call: "Call the barber shop and ask if they have availability at 6pm today"
2. TARS calls barber shop (creates session with parent_session_id)
3. Barber says "We're full at 6pm, but we have 7pm available"
4. Call ends
5. **Smart routing logic:**
   - If Máté is still in his call → Announce in call: "Report from call with Barber Shop: They don't have 6pm available but offered 7pm instead."
   - If Máté ended his call → Send via SMS/call based on Config.CALLBACK_REPORT

**Expected Terminal:**
```
🎯 Goal call completed, generating summary...
[MessageRouter] Routing callback to user
[MessageRouter] Máté is in active call - announcing in call
   OR
[MessageRouter] Máté not in call - fallback to SMS/call
```

---

## 🔍 Debugging Commands

### Check Active Sessions
```sql
sqlite3 tars.db "SELECT session_id, session_name, phone_number, permission_level, status FROM agent_sessions WHERE status='active';"
```

### Check Inter-Session Messages
```sql
sqlite3 tars.db "SELECT from_session_id, to_session_name, message_body, status FROM inter_session_messages ORDER BY created_at DESC LIMIT 10;"
```

### Check Broadcast Approvals
```sql
sqlite3 tars.db "SELECT * FROM broadcast_approvals;"
```

### Monitor Logs
```bash
tail -f tars.log | grep -E 'Session|Router|Permission'
```

---

## 🐛 Common Issues & Fixes

### Issue: "SessionManager not initialized"
**Fix:** Check [main_tars.py:69-71](main_tars.py#L69-L71) - SessionManager should be created before TwilioMediaStreamsHandler

### Issue: "Router not receiving messages"
**Fix:**
1. Check router is started: `self.router.start()` in [main_tars.py:261](main_tars.py#L261)
2. Check circular dependency is resolved: `session_manager.set_router(router)` in [main_tars.py:73](main_tars.py#L73)

### Issue: "Unknown caller has full access"
**Fix:** Check authentication logic in [security.py:33-42](security.py#L33-L42) - should return FULL only for 404-952-5557

### Issue: "Inter-session messages not delivered"
**Fix:**
1. Check target session is active: `SELECT * FROM agent_sessions WHERE status='active';`
2. Check router queue: `logger.info` messages should show routing attempts

---

## 📊 Success Metrics

After testing, you should see:
- ✅ Multiple sessions in database with correct permission levels
- ✅ Inter-session messages with status='delivered'
- ✅ Unknown callers get limited access greeting
- ✅ Máté gets notifications for unknown callers
- ✅ Callback routing works (in-call vs SMS/call)
- ✅ Session termination on call end (status='completed')
- ✅ AI summaries generated for goal calls

---

## 🎯 Next Steps

After successful testing:
1. **Production Config:**
   - Set `MAX_CONCURRENT_SESSIONS` in .env (default: 10)
   - Set `TARGET_NAME` in .env (default: "Máté Dort")
   - Set `CALLBACK_REPORT` (call/message/both)

2. **Monitor Performance:**
   - Watch memory usage with multiple sessions
   - Check database growth (agent_sessions, inter_session_messages)
   - Monitor Gemini API usage (each session = separate connection)

3. **Advanced Scenarios:**
   - Test hybrid broadcast approval mode
   - Test session recovery on network issues
   - Test parent-child session relationships

---

## 📞 Emergency Rollback

If issues arise:
```bash
# Revert to previous commit (before agent hub)
git revert HEAD~6..HEAD

# Or checkout last stable version
git checkout b213dd0  # Before Phase 2.6

# Restart TARS
python main_tars.py
```

---

## 🎊 Congratulations!

Your TARS system now has a fully operational Agent Hub with:
- Multi-session management
- Permission-based security
- Inter-agent communication
- Smart callback routing
- Unknown caller handling

**Start testing and enjoy the enhanced capabilities!** 🚀
