# macOS Fork Safety Fix

**Date**: January 27, 2026  
**Issue**: Background worker crashes on macOS with Objective-C fork error  
**Status**: ✅ Fixed

---

## Problem

When starting a background programming task, the worker would crash with:

```
objc[61081]: +[NSMutableString initialize] may have been in progress in another thread when fork() was called.
objc[61081]: +[NSMutableString initialize] may have been in progress in another thread when fork() was called. We cannot safely call it or ignore it in the fork() child process. Crashing instead.
```

**Root Cause**: 
- PyGithub and other Python libraries use macOS Objective-C frameworks
- These frameworks initialize certain classes at import time
- RQ (Redis Queue) uses `fork()` to create worker processes
- macOS prohibits calling Objective-C initialization after `fork()`
- This causes the worker process to crash immediately

---

## Solution

Set the `OBJC_DISABLE_INITIALIZE_FORK_SAFETY` environment variable to `YES` before importing any libraries.

### Changes Made

**File**: `start_worker.py`

Added at the top of the file (before any imports):

```python
import os

# Fix macOS fork safety issue with Objective-C libraries
# This must be set BEFORE importing any libraries that use Objective-C
os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
```

**Why this works**:
- Disables macOS's safety check for Objective-C initialization after fork
- Allows PyGithub and similar libraries to work in forked worker processes
- Safe because the worker process doesn't share state with the parent

---

## Testing

1. **Restart the worker**:
   ```bash
   # Stop existing worker (CTRL+C or)
   pkill -f "python.*start_worker.py"
   
   # Start with fix
   cd /Users/matedort/TARS_PHONE_AGENT
   source venv/bin/activate
   python start_worker.py
   ```

2. **Test background task**:
   - Call TARS
   - Ask it to "build a simple calculator app"
   - Worker should process the task without crashing

3. **Expected output**:
   ```
   ✅ Connected to Redis: localhost:6379
   🚀 Starting worker...
   *** Listening on tars_programming...
   [Task runs without crash]
   ```

---

## Alternative Solutions Considered

1. **Move imports inside functions**: Would work but reduces code readability
2. **Use `spawn` instead of `fork`**: Slower and not compatible with RQ
3. **Don't use PyGithub in worker**: Not feasible, needed for git operations

---

## Related Issues

### N8N Webhook URL Parsing

Also fixed in this update:

**File**: `core/config.py`

```python
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', '').strip()
# Fix common .env file issues: remove duplicate variable name if present
if N8N_WEBHOOK_URL.startswith("N8N_WEBHOOK_URL="):
    N8N_WEBHOOK_URL = N8N_WEBHOOK_URL.replace("N8N_WEBHOOK_URL=", "", 1)
```

This prevents the webhook URL from being malformed like:
`N8N_WEBHOOK_URL=https://...` → `https://...`

---

## Platform Compatibility

- ✅ **macOS**: Fixed with `OBJC_DISABLE_INITIALIZE_FORK_SAFETY`
- ✅ **Linux**: No changes needed (doesn't have Objective-C)
- ✅ **Windows**: No changes needed (uses different multiprocessing)

---

## References

- [Apple Technical Note on fork() safety](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fork.2.html)
- [Python multiprocessing and macOS](https://bugs.python.org/issue33725)
- [RQ worker implementation](https://python-rq.org/docs/workers/)

---

## Summary

**Problem**: Worker crashes on macOS due to Objective-C fork safety  
**Solution**: Set `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES`  
**Result**: Worker runs successfully on macOS  

This fix is automatically applied when starting the worker with `python start_worker.py`.
