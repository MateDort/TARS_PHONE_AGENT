# Bug Fix: System Freezing During Long User Speech

## Problem
The TARS phone agent would freeze and send a "nudge" to Gemini when the user spoke continuously for more than 15 seconds. This interrupted natural conversations where users needed to provide detailed instructions or lengthy explanations.

## Root Cause
The freeze detection watchdog was triggering prematurely during extended user speech:
- **Old timeout**: 15 seconds
- **Issue**: Watchdog timer started on FIRST speech fragment, not the last
- **Result**: If user spoke for 20+ seconds continuously, the system would "nudge" Gemini after 15s even though the user was still talking

## Solution
Implemented three improvements to fix the freeze detection:

### 1. Increased Freeze Timeout
```python
self._freeze_timeout = 15.0  # Increased from 15.0 seconds
```
- Gives Gemini 15 seconds to respond instead of 15
- More appropriate for complex tasks or when processing long user input

### 2. Added Speech State Tracking
```python
self._user_speaking = False  # Track if user is currently speaking
```
- System now knows when user is actively speaking vs. waiting for response

### 3. Implemented Speech-End Detection
```python
async def _detect_speech_end(self):
    """Detect when user has stopped speaking (pause in transcription)."""
    await asyncio.sleep(2.0)  # Wait for 2-second pause
    self._user_speaking = False
    # Only then start the freeze watchdog
```

**New Flow:**
1. User starts speaking → `_user_speaking = True`
2. Each new speech fragment resets the speech-end detection timer
3. After 2 seconds of silence → `_user_speaking = False`
4. Only then does the 45-second freeze watchdog start
5. Watchdog only triggers if user is NOT speaking

## Benefits
- ✅ Users can speak for as long as they need without interruption
- ✅ System still detects genuine freezes (45s timeout)
- ✅ More natural conversation flow
- ✅ Better handling of complex, multi-sentence instructions

## Testing
Test scenarios that previously failed:
- Speaking continuously for 20+ seconds (complex task descriptions)
- Providing multi-step instructions with natural pauses
- Dictating long messages or commands

## Files Changed
- `communication/gemini_live_client.py`
  - Increased `_freeze_timeout` from 15.0 to 45.0 seconds
  - Added `_user_speaking` flag
  - Added `_detect_speech_end()` method
  - Updated speech detection logic in `_receive_loop()`
  - Modified `_freeze_watchdog()` to check `_user_speaking` flag

## Date
January 28, 2026
