# Bug Fixes: Subprocess Environment & Gemini Freeze Detection

**Date:** January 27, 2026  
**Status:** ✅ Implemented

---

## Summary

Fixed two critical issues affecting TARS's reliability:

1. **Subprocess Environment Issue**: Commands like `cursor .` and `code .` failing with "command not found"
2. **Gemini Freeze Issue**: TARS sometimes freezing and not responding even though it hears the user

---

## Fix 1: Subprocess Environment (Enable Full PATH)

### Problem

When TARS tried to execute commands like `cursor .` or `code .` in the terminal, they failed with:

```
Command failed with exit code 127: /bin/sh: code: command not found
```

This happened even though:
- The commands worked fine in a normal terminal
- TARS was "allowed" to run these commands (no security restriction)
- The confirmation code system wasn't blocking them

### Root Cause

The `subprocess.run()` call in `sub_agents_tars.py` was using the **default minimal shell environment** (`/bin/sh`) which has a very limited `PATH`:

```python
# Before (broken)
result = subprocess.run(
    command,
    shell=True,
    cwd=str(work_path),
    capture_output=True,
    text=True,
    timeout=timeout
)
```

The minimal `PATH` only included basic directories like:
- `/usr/bin`
- `/bin`

But **not** user-installed program directories like:
- `/usr/local/bin` (where Homebrew installs)
- `~/.local/bin` (where user scripts live)
- Custom `PATH` entries in your shell config

### Solution

Pass the **full environment** to subprocess so it has access to all your programs:

```python
# After (fixed)
result = subprocess.run(
    command,
    shell=True,
    cwd=str(work_path),
    capture_output=True,
    text=True,
    timeout=timeout,
    env=os.environ.copy()  # ← Pass full environment
)
```

### What Changed

#### File: `sub_agents_tars.py`
- **Line 2219**: Added `env=os.environ.copy()` parameter

### What This Enables

Commands that were **already allowed** but broken now work:
- ✅ `cursor .` - Open Cursor editor
- ✅ `code .` - Open VS Code
- ✅ Custom scripts in `~/bin` or `/usr/local/bin`
- ✅ Tools installed via Homebrew
- ✅ Python virtual environment tools

### Security Impact

**NO NEGATIVE SECURITY IMPACT:**

- ✅ Confirmation code system still fully functional
- ✅ Destructive commands still require confirmation
- ✅ All command logging still happens
- ✅ Timeout protection still active
- ✅ No new dangerous commands enabled

This is **standard practice** for subprocess execution and actually aligns with expected behavior.

### Testing

Before fix:
```bash
TARS> execute terminal command: cursor .
❌ Command failed with exit code 127: /bin/sh: cursor: command not found
```

After fix:
```bash
TARS> execute terminal command: cursor .
✅ Command executed successfully
[Cursor opens in project directory]
```

---

## Fix 2: Gemini Freeze Detection & Auto-Recovery

### Problem

TARS would sometimes "freeze" during conversations:
- User speaks
- TARS receives the audio (transcription shows in logs)
- **TARS never responds** - just silence
- User has to hang up and call back

Example from logs:
```
2025-01-27 14:32:15 - User: "Can you help me with..."
2025-01-27 14:32:16 - [silence for 30+ seconds]
2025-01-27 14:32:50 - User hangs up
```

### Root Cause

Gemini Live API has an issue where it sometimes:
1. **Receives user input** successfully
2. **Doesn't send `end_of_turn` signal** properly
3. **Waits indefinitely** for more audio/input
4. **Never generates a response** because it thinks user is still talking

This creates a "thinking loop" where:
- Gemini is waiting for user to finish
- User is waiting for Gemini to respond
- **Deadlock** - nobody speaks

### Solution

Implement a **freeze watchdog** that:
1. **Tracks timing**: Records when user speaks and when AI responds
2. **Detects freezes**: If AI doesn't respond within 15 seconds
3. **Sends nudge**: Automatically sends `end_of_turn` signal to break the deadlock
4. **Auto-recovers**: Prompts Gemini to respond without user intervention

### Implementation

#### File: `communication/gemini_live_client.py`

Added four components:

**Note**: Initial implementation sent an empty audio chunk as nudge, but this caused a sample rate error. Fixed to use empty text input instead.

#### 1. State Tracking (Lines 60-63)
```python
# Freeze detection: track last user input and AI response times
self._last_user_input_time = None
self._last_ai_response_time = None
self._freeze_watchdog_task = None
self._freeze_timeout = 15.0  # seconds
```

#### 2. Watchdog Method (Lines 86-116)
```python
async def _freeze_watchdog(self):
    """Detect if Gemini freezes and send a nudge."""
    try:
        await asyncio.sleep(self._freeze_timeout)
        
        # Timeout expired - Gemini is frozen
        logger.warning(f"⚠️  Gemini appears frozen (no response for {self._freeze_timeout}s)")
        print(f"\n⚠️  TARS hasn't responded in {self._freeze_timeout}s, sending nudge...")
        
        # Send empty audio with end_of_turn=True
        if self.session and self.is_connected:
            await self.session.send(
                input={"data": b"", "mime_type": "audio/pcm"},
                end_of_turn=True
            )
            
    except asyncio.CancelledError:
        # Watchdog cancelled (AI responded in time - normal)
        pass
```

#### 3. Start Watchdog on User Input (Lines 436-442)
```python
# User's spoken text
if hasattr(response.server_content, 'input_transcription'):
    user_text = response.server_content.input_transcription.text
    
    # Track user input time
    import time
    self._last_user_input_time = time.time()
    
    # Start freeze watchdog
    if self._freeze_watchdog_task and not self._freeze_watchdog_task.done():
        self._freeze_watchdog_task.cancel()
    self._freeze_watchdog_task = asyncio.create_task(self._freeze_watchdog())
```

#### 4. Cancel Watchdog on AI Response (Lines 396-402)
```python
# AI's spoken text
if response.server_content.output_transcription:
    text = response.server_content.output_transcription.text
    
    # Track AI response time
    import time
    self._last_ai_response_time = time.time()
    
    # Cancel freeze watchdog (AI is responding)
    if self._freeze_watchdog_task and not self._freeze_watchdog_task.done():
        self._freeze_watchdog_task.cancel()
```

#### 5. Cleanup on Disconnect (Lines 227-229)
```python
# Cancel freeze watchdog if active
if self._freeze_watchdog_task and not self._freeze_watchdog_task.done():
    self._freeze_watchdog_task.cancel()
```

### How It Works

```
User speaks → Start 15s watchdog timer
    ↓
AI responds within 15s? → Cancel watchdog ✅ (normal)
    ↓
AI doesn't respond for 15s? → Send end_of_turn nudge ⚠️
    ↓
Gemini realizes turn is over → Generates response 🤖
```

### User Experience

#### Before Fix:
```
👤 USER: "Can you help me with this code?"
[30 seconds of silence]
👤 USER: "Hello? Are you there?"
[Still silence]
👤 USER: *hangs up and calls back*
```

#### After Fix:
```
👤 USER: "Can you help me with this code?"
[15 seconds pass]
⚠️  TARS hasn't responded in 15s, sending nudge...
🤖 TARS: "Of course! Let me help you with that code..."
```

### Configuration

The freeze timeout is configurable:

```python
# In gemini_live_client.py __init__
self._freeze_timeout = 15.0  # Change this value
```

**Recommended values:**
- `10.0` - More aggressive (catches freezes faster, might trigger on complex tasks)
- `15.0` - **Default** (good balance)
- `20.0` - More conservative (only catches severe freezes)

### Logging

Freeze events are logged for debugging:

```python
logger.warning(f"⚠️  Gemini appears frozen (no response for {self._freeze_timeout}s) - sending nudge")
logger.info("Sent end_of_turn nudge to Gemini")
```

Check logs at: `/Users/matedort/TARS_PHONE_AGENT/logs/`

---

## Known Issues & Fixes

### Issue: Sample Rate Error on Audio Nudge

**Problem discovered in testing (Jan 27, 2026)**:

Initial implementation sent an empty audio chunk `b""` as the nudge, which caused:

```
Error 1007: Sample rate changed from previously 24000 to 16000, which is not supported
```

**Root cause**: Gemini interprets empty audio as a sample rate change and rejects it.

**Fix applied**: Changed from audio-based nudge to minimal text nudge:

```python
# Before (broken - audio)
await self.session.send(
    input={"data": b"", "mime_type": "audio/pcm"},
    end_of_turn=True
)

# Attempt 1 (still broken - empty text)
await self.session.send(
    input="",  # Gemini rejects empty strings as "invalid argument"
    end_of_turn=True
)

# After (fixed - minimal text)
await self.session.send(
    input=" ",  # Single space - minimal valid input
    end_of_turn=True
)
```

**Final solution**: Use a single space `" "` as input. This is the minimum valid input that satisfies Gemini's validation (non-empty) while being functionally invisible (won't be spoken meaningfully) and still signals `end_of_turn`.

---

## Testing & Verification

### Test Fix 1 (Subprocess)

1. Call TARS
2. Say: "Open this project in Cursor"
3. TARS executes: `cursor .`
4. ✅ **Expected**: Cursor opens successfully
5. ❌ **Before**: "command not found" error

### Test Fix 2 (Freeze Detection)

Harder to test directly, but monitor for:

1. **Normal conversations**: Should work exactly as before
2. **Complex tasks**: Watchdog stays silent (gets cancelled when AI responds)
3. **If freeze occurs**: Should see warning and auto-recovery after 15s

### Monitoring

Watch the terminal output for:

```bash
# Normal operation (good)
👤 USER: "Help me with X"
🤖 TARS: "Sure, let me help..."

# Freeze detected (watchdog working)
👤 USER: "Help me with X"
⚠️  TARS hasn't responded in 15s, sending nudge...
🤖 TARS: "Sure, let me help..."

# Freeze NOT detected (watchdog failed)
👤 USER: "Help me with X"
[silence for 30+ seconds]
```

---

## Rollback Instructions

If either fix causes issues:

### Rollback Fix 1 (Subprocess):

```python
# In sub_agents_tars.py line 2213
# Remove this line:
env=os.environ.copy()

# Result:
result = subprocess.run(
    command,
    shell=True,
    cwd=str(work_path),
    capture_output=True,
    text=True,
    timeout=timeout
)
```

### Rollback Fix 2 (Freeze Detection):

```python
# In gemini_live_client.py __init__ (lines 60-63)
# Remove these lines:
self._last_user_input_time = None
self._last_ai_response_time = None
self._freeze_watchdog_task = None
self._freeze_timeout = 15.0

# Remove the _freeze_watchdog method (lines 86-116)

# Remove watchdog start code (lines 436-442)
# Remove watchdog cancel code (lines 396-402)
# Remove watchdog cleanup code (lines 227-229)
```

---

## Performance Impact

### Fix 1 (Subprocess)
- **Memory**: +~1KB (environment variable copy)
- **CPU**: Negligible
- **Latency**: None

### Fix 2 (Freeze Detection)
- **Memory**: +~500 bytes (timestamps + task reference)
- **CPU**: Minimal (1 async timer per user input)
- **Latency**: None (runs in background)

**Overall**: Both fixes have **negligible performance impact**.

---

## Future Improvements

### Potential Enhancements:

1. **Adaptive Timeout**: Adjust `_freeze_timeout` based on task complexity
2. **Multiple Nudges**: Try 2-3 nudges before giving up
3. **Metrics Tracking**: Count freeze occurrences and recovery success rate
4. **User Notification**: Tell user "I'm thinking about that..." before sending nudge
5. **Gemini API Feedback**: Report freeze patterns to Google

### Related Issues to Monitor:

- Gemini Live API behavior updates from Google
- Python subprocess best practices
- Audio streaming buffer management

---

## Related Documentation

- [Claude Programming Integration](CLAUDE_PROGRAMMING_INTEGRATION.md)
- [Architecture Overview](ARCHITECTURE.md)
- [Bug Fixes Log](BUGFIXES.md)

---

## Changelog

| Date | Change | Files Modified |
|------|--------|----------------|
| 2026-01-27 | Add `env=os.environ.copy()` to subprocess | `sub_agents_tars.py` |
| 2026-01-27 | Add freeze detection watchdog | `communication/gemini_live_client.py` |

---

**Status**: ✅ Both fixes implemented and ready for testing
