# Discord Messaging via KIPP - Architecture Update

**Date**: January 27, 2026  
**Status**: ✅ Implemented

---

## Summary

Simplified the background task Discord integration by routing all messages through KIPP (the main N8N webhook) instead of using a separate Discord webhook.

---

## What Changed

### Before (More Complex)
```
Background Worker → DISCORD_UPDATES_WEBHOOK → N8N → Discord
                    (separate webhook)
```

### After (Simpler)
```
Background Worker → N8N_WEBHOOK_URL (KIPP) → N8N → Discord
                    (same webhook as everything else)
```

---

## Technical Changes

### 1. Code Changes

**File**: `core/background_worker.py`
- Modified `send_discord_update()` to use `Config.N8N_WEBHOOK_URL` instead of `Config.DISCORD_UPDATES_WEBHOOK`
- Added `target: "discord"` and `source: "background_task"` fields to payload
- Updated logging messages to reflect "via KIPP"

**File**: `sub_agents_tars.py`
- Modified `ProgrammerAgent._send_discord_update()` same as above
- Now routes through KIPP like all other messages

**File**: `core/config.py`
- Removed `DISCORD_UPDATES_WEBHOOK` environment variable
- Removed from `reload()` method

### 2. Message Format

Background task messages now include identification fields:

```json
{
  "target": "discord",           // NEW: Tells N8N to route to Discord
  "source": "background_task",   // NEW: Identifies as background task
  "task_id": "abc123",
  "type": "progress",
  "message": "✏️ Editing main.py",
  "timestamp": "2026-01-27T10:30:00"
}
```

N8N can use these fields to:
- Route to the correct channel (`target: "discord"`)
- Format messages appropriately (`source: "background_task"`)
- Apply special handling if needed

---

## Benefits

1. **Simpler Configuration**
   - One webhook URL instead of two
   - Easier to set up and maintain
   
2. **Consistent Architecture**
   - All TARS-to-Discord communication goes through KIPP
   - KIPP becomes the single integration point
   
3. **Intelligent Routing**
   - KIPP's AI can understand context
   - Can batch updates to avoid spam
   - Can route to different channels based on urgency
   
4. **Easier N8N Setup**
   - Extend existing KIPP workflow instead of creating new one
   - Add simple IF/Switch node to detect `target: "discord"`
   - Reuse existing Discord bot connection

---

## N8N Configuration

### Update Existing KIPP Workflow

1. **Add Router Node** (after webhook trigger):
   ```
   IF: {{ $json.target === "discord" && $json.source === "background_task" }}
   TRUE → Format for Discord → Send to Discord
   FALSE → Existing KIPP logic
   ```

2. **Format Discord Message** (same as before):
   ```javascript
   const data = $input.item.json;
   const taskId = data.task_id;
   const type = data.type;
   const message = data.message;
   
   // Format based on type...
   return { message: discordMessage };
   ```

3. **Send to Discord** (reuse existing Discord bot node)

### Confirmation Code Handler

The confirmation code webhook (`/webhook/background-confirmation`) remains unchanged. It still:
- Receives codes from Discord replies
- Stores in Redis for worker to poll
- Works exactly the same as before

---

## Migration Guide

If you already have the old setup:

1. **Update TARS**:
   ```bash
   git pull
   # Code already updated to use N8N_WEBHOOK_URL
   ```

2. **Update `.env`**:
   ```env
   # Remove this line (no longer needed):
   # DISCORD_UPDATES_WEBHOOK=https://...
   
   # Keep this (now used for everything):
   N8N_WEBHOOK_URL=https://n8n.srv1283735.hstgr.cloud/webhook-test/your-id
   ```

3. **Update N8N Workflow**:
   - Add router node to existing KIPP workflow
   - Detect `target: "discord"` messages
   - Route to Discord formatting logic

4. **Test**:
   ```bash
   # Start a background task
   # Should see updates in Discord
   # Routed through KIPP webhook
   ```

---

## Testing Checklist

- [x] Background tasks send updates to N8N_WEBHOOK_URL
- [x] Messages include `target: "discord"` field
- [x] Messages include `source: "background_task"` field
- [ ] N8N routes messages to Discord channel
- [ ] Confirmation codes still work
- [ ] All documentation updated

---

## Files Updated

### Code Files
- `core/background_worker.py` - Use N8N_WEBHOOK_URL
- `sub_agents_tars.py` - Use N8N_WEBHOOK_URL
- `core/config.py` - Remove DISCORD_UPDATES_WEBHOOK

### Documentation Files
- `docs/BACKGROUND_PROGRAMMING.md`
- `docs/N8N_BACKGROUND_TASKS_SETUP.md`
- `docs/BACKGROUND_TASKS_QUICK_REFERENCE.md`
- `docs/AUTONOMOUS_PROGRAMMING_SUMMARY.md`
- `docs/BACKGROUND_TASKS_IMPLEMENTATION.md`
- `docs/GETTING_STARTED_BACKGROUND_TASKS.md`
- `docs/README.md`

---

## Why This Is Better

### User's Original Insight

> "discord messaging can just go over kipp so tars can send a message to kipp to send this to me on discord it doesnt have to be direct"

This was **absolutely correct**. Having two separate webhooks:
1. Made configuration more complex
2. Created an inconsistent architecture
3. Missed the opportunity for KIPP's AI to intelligently handle messages

By routing everything through KIPP:
- ✅ Single point of integration
- ✅ KIPP can batch/prioritize messages
- ✅ Consistent with how all other messaging works
- ✅ Easier to maintain and debug

---

## Future Enhancements

Now that all messages route through KIPP, we can easily add:

1. **Intelligent Batching**
   - KIPP can combine multiple rapid updates into one message
   - Reduces Discord spam

2. **Smart Routing**
   - Different channels for different task types
   - "coding" → #dev-updates
   - "research" → #research-updates

3. **Priority Handling**
   - Urgent messages (confirmations) → immediate
   - Progress updates → batched every 30 seconds

4. **Multi-Platform**
   - Same infrastructure for Discord, Telegram, Slack
   - Just change `target` field

---

## Summary

**One webhook to rule them all!** 🎯

All TARS communication now flows through KIPP, creating a clean, maintainable architecture that's easier to configure and more powerful in capability.
