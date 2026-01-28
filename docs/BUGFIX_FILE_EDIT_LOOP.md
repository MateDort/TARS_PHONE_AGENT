# Fix: Repeated File Edit Loop - January 27, 2026

## Problem

The background worker was **editing the same file repeatedly** instead of creating new files:

```
✏️ Editing /Users/matedort/test/build.md
✅ Edited file: /Users/matedort/test/build.md
✏️ Editing /Users/matedort/test/build.md  ← AGAIN!
✅ Edited file: /Users/matedort/test/build.md
✏️ Editing /Users/matedort/test/build.md  ← AGAIN!
✅ Edited file: /Users/matedort/test/build.md
✏️ Editing /Users/matedort/test/build.md  ← AGAIN!
```

Edited `build.md` **7+ times** in a row without creating any other files!

## Root Cause

The loop detection only tracked **repeated commands**, not **repeated file edits**. The stuck counter reset on ANY edit, so the worker thought it was making progress even though it was just modifying the same file over and over.

---

## Solution

### 1. Track Recent File Edits

Added `recent_file_edits` array to context (like `recent_commands`):

```python
context = {
    # ... existing fields ...
    "recent_commands": [],
    "recent_file_edits": [],  # NEW: Track which files are being edited
    "stuck_counter": 0
}
```

### 2. Detect Repeated File Edits

Before editing a file, check if it was edited in the last 2 iterations:

```python
if file_path in context['recent_file_edits'][-2:]:
    logger.warning(f"Detected repeated edit of same file: {file_path}")
    await tracker.send_update(
        f"⚠️  Already edited {file_path} recently!\n"
        f"Please create or edit DIFFERENT files to make progress.\n"
        f"Recent files: {context['recent_file_edits'][-3:]}"
    )
    context['stuck_counter'] += 1
    continue  # Skip this edit and try next action
```

### 3. Improved Prompt

Tell Claude explicitly which files were already edited:

```python
system=(
    f"You are an expert programmer working autonomously. "
    # ...
    f"Recent file edits: {context['recent_file_edits'][-3:]}\n"
    f"Recent errors: {context['errors'][-3:]}\n\n"
    f"IMPORTANT: Don't repeat commands or file edits!\n"
    f"- Already edited these files: {context['recent_file_edits'][-3:]}\n"
    f"- Edit DIFFERENT files or create NEW files to make progress\n"
    f"- For a Next.js app, you need: package.json, tsconfig.json, next.config.js, "
    f"pages/index.tsx, components/, styles/, etc.\n\n"
    # ...
)
```

### 4. Track Each Edit

After successfully editing a file, add it to the tracking list:

```python
context['completed_actions'].append(f"Edited {file_path}")
context['recent_file_edits'].append(file_path)  # NEW: Track this edit
context['stuck_counter'] = 0
```

---

## Expected Behavior Now

### Before (Broken)
```
Iteration 1: Edit build.md
Iteration 2: Edit build.md  ← REPEAT!
Iteration 3: Edit build.md  ← REPEAT!
Iteration 4: Edit build.md  ← REPEAT!
...
```

### After (Fixed)
```
Iteration 1: Edit build.md
Iteration 2: Edit build.md  ← Last time allowed
Iteration 3: Try to edit build.md → ⚠️ BLOCKED! "Already edited recently"
Iteration 4: Create package.json instead
Iteration 5: Create pages/index.tsx
Iteration 6: Create next.config.js
...
```

---

## Testing

**Restart the worker** and try the same task:

```bash
# Stop worker (CTRL+C)
python start_worker.py
```

You should see:
- ✅ Files edited **once or twice max**
- ✅ Warning message if it tries a 3rd time: `⚠️ Already edited [file] recently!`
- ✅ Worker creates **different files** to make progress
- ✅ Actually builds the full Next.js app structure

---

## Files Modified

- `/Users/matedort/TARS_PHONE_AGENT/core/background_worker.py`
  - Line 373: Added `recent_file_edits` tracking
  - Lines 408-423: Updated prompt with file edit history
  - Lines 451-478: Added repeated file edit detection

---

## Summary

The worker will now:
1. ✅ Track which files it has edited
2. ✅ Block editing the same file more than twice in a row
3. ✅ Tell Claude which files were already edited
4. ✅ Force progress by creating different files
5. ✅ Build complete project structures instead of looping
