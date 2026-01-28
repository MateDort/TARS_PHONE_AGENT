# N8N KIPP Routing - Quick Setup Guide

**For routing background task messages to Discord via KIPP**

---

## Overview

All background task updates now flow through your **existing KIPP N8N webhook**. You just need to add a router to detect Discord-bound messages and handle them appropriately.

---

## Message Flow

```
TARS Background Worker
  ↓
  POST to N8N_WEBHOOK_URL with:
  {
    "target": "discord",
    "source": "background_task",
    "task_id": "abc123",
    "type": "progress",
    "message": "✏️ Editing main.py"
  }
  ↓
N8N KIPP Webhook
  ↓
Router Node (IF: target === "discord")
  ↓
  TRUE: Format & Send to Discord
  FALSE: Existing KIPP logic
```

---

## N8N Workflow Modification

### Step 1: Open Existing KIPP Workflow

Navigate to your KIPP webhook workflow in N8N.

---

### Step 2: Add Router Node

After the webhook trigger, add an **IF node**:

**Name**: "Route by Target"

**Expression**:
```javascript
{{ $json.target === "discord" && $json.source === "background_task" }}
```

---

### Step 3: Format Discord Message (TRUE Branch)

Add a **Function node** on the TRUE branch:

**Name**: "Format Background Task Message"

**Code**:
```javascript
const data = $input.item.json;
const taskId = data.task_id;
const type = data.type;
const message = data.message;
const command = data.command;
const phase = data.phase;

// Format based on message type
let discordMessage = "";

if (type === 'task_started') {
  discordMessage = `🚀 **Background Task Started**\n\n` +
                  `**Task ID:** ${taskId}\n` +
                  `**Goal:** ${data.goal}\n` +
                  `**Project:** ${data.project}\n\n` +
                  `Updates will be posted here.`;
}
else if (type === 'confirmation_request') {
  discordMessage = `⚠️ **Task #${taskId} Needs Confirmation**\n\n` +
                  `**Command:** \`${command}\`\n` +
                  `**Reason:** ${data.reason}\n\n` +
                  `**Reply with your confirmation code to proceed.**`;
}
else if (type === 'phase_complete') {
  const phaseEmoji = {
    'started': '🚀',
    'planning': '📋',
    'coding': '✏️',
    'testing': '🧪',
    'complete': '🎉',
    'error': '❌',
    'timeout': '⏱️'
  };
  const emoji = phaseEmoji[phase] || '▶️';
  discordMessage = `${emoji} **${message}**`;
}
else if (type === 'progress') {
  discordMessage = message;
  if (command) {
    discordMessage += `\n\`\`\`bash\n${command}\n\`\`\``;
  }
}
else {
  discordMessage = `**Task #${taskId}:** ${message}`;
}

return [{
  json: {
    message: discordMessage,
    task_id: taskId,
    requires_confirmation: data.awaiting_confirmation || false
  }
}];
```

---

### Step 4: Send to Discord

Add a **Discord node** (or HTTP Request if using webhook):

**Method**: Send Message to Channel

**Channel**: Your background tasks channel ID

**Message**: `{{ $json.message }}`

---

### Step 5: Continue Existing Logic (FALSE Branch)

On the FALSE branch, connect to your existing KIPP logic (AI processing, etc.).

---

## Diagram

```
┌─────────────────────┐
│  Webhook Trigger    │
│  (N8N_WEBHOOK_URL)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────┐
│  IF Node: Route by Target           │
│  Condition:                          │
│  target === "discord" &&             │
│  source === "background_task"        │
└──────┬──────────────────────┬───────┘
       │                      │
    TRUE│                   FALSE│
       ▼                        ▼
┌─────────────────┐    ┌─────────────────┐
│  Format Discord │    │  Existing KIPP  │
│  Message        │    │  Logic (AI)     │
└────────┬────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐
│  Send to        │
│  Discord        │
└─────────────────┘
```

---

## Testing

### 1. Test Message from TARS

Send a test payload to your N8N webhook:

```bash
curl -X POST https://your-n8n-url.com/webhook/your-id \
  -H "Content-Type: application/json" \
  -d '{
    "target": "discord",
    "source": "background_task",
    "task_id": "test123",
    "type": "progress",
    "message": "🧪 Test message from TARS",
    "timestamp": "2026-01-27T10:00:00"
  }'
```

### 2. Verify Discord Receives Message

Check your Discord channel for:
```
🧪 Test message from TARS
```

### 3. Test Regular KIPP Message

Send a normal KIPP message (without `target: "discord"`):

```bash
curl -X POST https://your-n8n-url.com/webhook/your-id \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Send this to Discord: Hello from KIPP"
  }'
```

Should be handled by existing KIPP logic (AI processes it).

---

## Troubleshooting

### Messages Not Reaching Discord

1. **Check N8N execution log**:
   - Did the router detect `target: "discord"`?
   - Did it route to TRUE branch?

2. **Check Discord node**:
   - Is channel ID correct?
   - Does bot have permissions?

3. **Check TARS logs**:
   ```bash
   grep "Sent Discord update via KIPP" /path/to/tars.log
   ```

### Messages Going to Wrong Branch

1. **Verify IF condition**:
   ```javascript
   {{ $json.target === "discord" && $json.source === "background_task" }}
   ```
   
2. **Check incoming payload** has both fields:
   - `target: "discord"`
   - `source: "background_task"`

### Confirmation Codes Not Working

The confirmation handler is **separate** and unchanged:
- Still uses `/webhook/background-confirmation` endpoint
- Still stores codes in Redis
- Background worker still polls Redis

---

## Configuration Checklist

- [ ] N8N KIPP workflow updated with router
- [ ] Discord formatting node added
- [ ] Discord send node configured
- [ ] Test message routes correctly
- [ ] Regular KIPP messages still work
- [ ] TARS `.env` has `N8N_WEBHOOK_URL`
- [ ] No `DISCORD_UPDATES_WEBHOOK` in `.env`

---

## Summary

**What Changed**: Added a router to your existing KIPP workflow to detect Discord-bound messages.

**What Stayed the Same**: 
- Your existing KIPP logic
- Confirmation code endpoint
- Everything else

**Result**: All background task updates flow through one webhook, keeping architecture clean and maintainable.

---

## Need Help?

1. Check [DISCORD_VIA_KIPP_UPDATE.md](DISCORD_VIA_KIPP_UPDATE.md) for detailed explanation
2. Check [N8N_BACKGROUND_TASKS_SETUP.md](N8N_BACKGROUND_TASKS_SETUP.md) for full workflow setup
3. Check N8N execution logs for routing issues
4. Verify payload includes `target` and `source` fields
