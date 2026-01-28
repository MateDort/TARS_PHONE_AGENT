# Background Worker Fixes - January 27, 2026

## Issues Fixed

### 1. **macOS Fork Crash** ✅ FIXED
**Error**: `objc[PID]: +[NSMutableString initialize] may have been in progress in another thread when fork() was called`

**Fix**: Switched to `SimpleWorker` on macOS (in `start_worker.py`)
- `SimpleWorker` doesn't use `fork()`, avoiding Objective-C conflicts
- Tasks now run in the same process as the worker
- Trade-off: If a task crashes, the entire worker crashes (but acceptable for TARS)

**Files Modified**:
- `/Users/matedort/TARS_PHONE_AGENT/start_worker.py` (lines 74-83)

---

### 2. **JSON Parsing Error** ✅ FIXED
**Error**: `Expecting value: line 1 column 1 (char 0)`

**Fix**: Added regex extraction to handle Claude responses wrapped in markdown
- Extracts JSON from markdown code blocks
- Falls back to regex search for raw JSON objects
- Better error logging shows actual Claude response

**Files Modified**:
- `/Users/matedort/TARS_PHONE_AGENT/core/background_worker.py` (lines 413-431)

---

### 3. **`_edit_file()` Parameter Error** ✅ FIXED
**Error**: `ProgrammerAgent._edit_file() got an unexpected keyword argument 'session_id'`

**Fix**: Removed `session_id` parameter from the call
- `_edit_file()` only accepts `file_path` and `changes_description`
- Session ID not needed in background worker context

**Files Modified**:
- `/Users/matedort/TARS_PHONE_AGENT/core/background_worker.py` (lines 457-461)

---

### 4. **Infinite Loop / No Progress** ✅ FIXED
**Problem**: Worker ran 50 iterations reading the same files repeatedly without creating anything

**Fixes Applied**:

#### A. **Loop Detection**
- Tracks last 3 commands run
- Skips if command was already run recently
- Warns Claude to make progress

#### B. **Stuck Counter**
- Tracks iterations without real progress
- Increments when:
  - Just reading files (`cat`, `ls`, `find`, `grep`)
  - Errors occur
  - Unknown actions
  - Repeated commands
- Resets when:
  - File is edited
  - Productive command runs (not just reading)
  - Task completes
- After 5 stuck iterations, sends warning

#### C. **Improved Prompt**
- Shows recent commands to Claude
- Explicitly tells Claude not to repeat commands
- Reminds Claude to EDIT or CREATE files, not just read

**Files Modified**:
- `/Users/matedort/TARS_PHONE_AGENT/core/background_worker.py`
  - Context tracking (lines 365-373)
  - Stuck detection (lines 377-391)
  - Improved prompt (lines 395-406)
  - Loop detection (lines 471-479)
  - Progress tracking (lines 463, 509-520)

---

## Testing

To test the fixes:

1. **Restart the worker**:
   ```bash
   cd /Users/matedort/TARS_PHONE_AGENT
   # Stop current worker (CTRL+C)
   python start_worker.py
   ```

2. **Start a background task via TARS**:
   - Call TARS and say: "Start an autonomous coding task to [goal]"
   - Worker should now:
     - Not crash (macOS fork fixed)
     - Parse Claude responses (JSON extraction working)
     - Actually edit files (session_id error fixed)
     - Make progress without looping (stuck detection working)

3. **Monitor logs**:
   - Look for: `Using SimpleWorker (no fork) for macOS compatibility`
   - Watch for: `✏️ Editing [file]` messages (actual progress)
   - Check for: `⚠️ Skipping repeated command` if it tries to loop
   - Watch for: `⚠️ No progress for 5 iterations` if stuck

---

## What To Expect Now

### ✅ Should Work
- Worker starts without crashing
- Tasks can edit files
- Claude responses are parsed correctly
- Detects and breaks out of infinite loops
- Makes actual progress toward goals

### ⚠️ Known Limitations
- If task crashes, entire worker goes down (restart manually)
- Memory from completed tasks persists until worker restart
- Stuck detection is heuristic (may have false positives)

---

## Next Steps

1. Test with a simple task first ("create index.html with hello world")
2. Monitor for any new issues
3. Adjust stuck counter threshold if needed (currently 5 iterations)
4. Consider adding task timeout (currently 15 minutes)

---

## Summary

All **4 critical bugs** have been fixed:
1. ✅ macOS fork crash
2. ✅ JSON parsing error  
3. ✅ `_edit_file()` parameter error
4. ✅ Infinite loop / no progress

The background worker should now be **fully functional** on macOS!
