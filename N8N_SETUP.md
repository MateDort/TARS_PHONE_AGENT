# N8N Integration Setup Guide

## What N8N Can Do

N8N handles all communication tasks for TARS:

### **Communication Tools:**
1. **Gmail** - Send emails, check calendar, manage email operations
2. **Telegram** - Send messages via Telegram
3. **Discord** - Send messages to Discord channels
4. **Calendar** - Check calendar events, schedule items

### **How It Works:**

TARS sends a natural language message to N8N, and N8N's internal agent automatically:
- Determines which tool to use (Gmail, Telegram, Discord, Calendar)
- Extracts necessary information (recipient, subject, message content)
- Executes the appropriate action
- Returns a status message to TARS

**Example Messages TARS Sends:**
- `"send email to john@example.com about the meeting"`
- `"send telegram message to Helen saying hello"`
- `"check my calendar for tomorrow"`
- `"send discord message to the team channel about the update"`

## Setup Instructions

### 1. Configure TARS → N8N Connection

Add to your `.env` file:

```env
# N8N Webhook URL (for TARS to send tasks to N8N)
N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/tars

# N8N → TARS Webhook URL (for N8N to send tasks back to TARS)
N8N_TARS_WEBHOOK_URL=http://your-tars-instance.com/webhook/n8n
```

**Important:** 
- `N8N_WEBHOOK_URL` should point to your N8N webhook endpoint
- `N8N_TARS_WEBHOOK_URL` should be the publicly accessible URL where TARS is running (use ngrok if running locally)

### 2. Create N8N Workflow

In your N8N instance, create a workflow that:

1. **Receives webhook from TARS:**
   - Use a "Webhook" node
   - Method: POST
   - Path: `/webhook/tars` (or your chosen path)
   - This receives: `{"message": "user's request"}`

2. **Processes the message:**
   - Use an AI agent node (e.g., OpenAI, Anthropic, or N8N's built-in AI)
   - The agent should:
     - Parse the message to determine intent
     - Extract recipient, subject, content, etc.
     - Select the appropriate tool (Gmail, Telegram, Discord, Calendar)

3. **Executes the action:**
   - Use the appropriate node:
     - **Gmail** node for email operations
     - **Telegram** node for Telegram messages
     - **Discord** node for Discord messages
     - **Google Calendar** node for calendar operations

4. **Returns response:**
   - Return a JSON response: `{"message": "Task completed successfully"}`

### 3. Create N8N → TARS Workflow

When N8N needs TARS to perform an action (e.g., "call helen"):

1. **Trigger:** Your N8N workflow determines TARS needs to do something
2. **HTTP Request Node:**
   - Method: POST
   - URL: `{{N8N_TARS_WEBHOOK_URL}}/webhook/n8n`
   - Body: `{"message": "call helen"}` or `{"task": "call helen"}` or `{"text": "call helen"}`

### 4. TARS Webhook Endpoint

TARS automatically creates the webhook endpoint at:
- **Path:** `/webhook/n8n`
- **Method:** POST
- **Accepts:** JSON with `message`, `task`, or `text` field
- **Response:** `{"status": "accepted", "message": "Task received"}`

When N8N sends a task:
1. TARS creates a live session named "Mate_n8n"
2. Processes the task through Gemini Live
3. Session auto-closes after 1 minute of inactivity

## Example N8N Workflow Structure

```
[Webhook] → [AI Agent/Function] → [Gmail/Telegram/Discord/Calendar] → [Respond to Webhook]
     ↓
  Receives: {"message": "send email to john about meeting"}
     ↓
  AI determines: Use Gmail, to=john@example.com, subject="meeting", body="..."
     ↓
  Gmail node sends email
     ↓
  Returns: {"message": "Email sent successfully"}
```

## Testing

1. **Test TARS → N8N:**
   - Ask TARS: "send email to test@example.com saying hello"
   - Check N8N workflow execution logs
   - Verify email was sent

2. **Test N8N → TARS:**
   - In N8N, trigger a workflow that sends: `{"message": "call helen"}`
   - Check TARS logs for "Mate_n8n" session creation
   - Verify TARS processes the task

## Troubleshooting

- **N8N_WEBHOOK_URL not configured:** TARS will return an error message
- **N8N not receiving requests:** Check webhook URL is correct and N8N is accessible
- **TARS not receiving from N8N:** Ensure `N8N_TARS_WEBHOOK_URL` is publicly accessible (use ngrok for local testing)
- **Session timeout:** N8N sessions close after 1 minute of inactivity - this is expected behavior
