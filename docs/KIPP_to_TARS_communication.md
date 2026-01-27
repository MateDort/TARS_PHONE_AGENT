Bidirectional Agent Bridge Implementation
Architecture Overview
Telegram → n8n (KIPP) → TARS HTTP API → Phone Call
                                    ↓
                            (optional callback)
                                    ↓
                              n8n → Telegram
Implementation Plan
1. Add HTTP API Endpoint in TARS
File: communication/twilio_media_streams.py

Add a new route /call that accepts POST requests from n8n:

@self.app.route('/call', methods=['POST'])
def call_endpoint():
    """Handle action requests from n8n/KIPP."""
    # Accept JSON payload:
    # {
    #   "action": "call_user",
    #   "phone": "+1XXXXXXXXXX",
    #   "source": "kipp",
    #   "chat_id": 8326230132,  # optional
    #   "intent": "call_user",  # optional
    #   "requested_by": "telegram"  # optional
    # }
Key requirements:

Validate required fields (action, phone)
Use existing twilio_handler.make_call() method
Return JSON response: {"status": "calling", "message": "Calling you now", "call_sid": "..."}
Handle errors gracefully with proper HTTP status codes
Log all incoming requests for debugging
Location: Add after the existing /webhook/n8n route (around line 303)

2. Optional: Status Callback Endpoint
File: communication/twilio_media_streams.py

Add /tars/status endpoint for TARS to POST status updates back to n8n:

@self.app.route('/tars/status', methods=['POST'])
def tars_status():
    """Receive status updates from TARS (for future use)."""
    # This endpoint can be used if TARS needs to report
    # call status back to n8n (e.g., "call failed", "call completed")
Note: This is optional and can be implemented later if bidirectional status updates are needed.

3. Update Configuration
File: core/config.py

Ensure these config variables exist and are documented:

N8N_WEBHOOK_URL: For TARS → n8n (already exists)
N8N_TARS_WEBHOOK_URL: For n8n → TARS (already exists, verify usage)
WEBHOOK_BASE_URL: Public URL where TARS is exposed (needs to be set to tunnel URL)
4. Integration with OutboundCallAgent
File: communication/twilio_media_streams.py

The /call endpoint should:

Extract phone number from request
Optionally extract goal/reminder message if provided
Call self.make_call(to_number=phone, reminder_message=goal_message)
Return structured JSON response
Note: The existing OutboundCallAgent logic can be reused, but the HTTP endpoint provides direct access without going through Gemini function calls.

5. Error Handling & Validation
Requirements:

Validate phone number format
Check that action is "call_user" (extensible for future actions)
Handle Twilio API errors gracefully
Return appropriate HTTP status codes (200, 400, 500)
Log all errors for debugging
6. Documentation for n8n Workflow
Create or update documentation explaining:

The exact JSON payload format for /call endpoint
How to configure n8n HTTP Request node
How to set up Telegram → n8n → TARS flow
How to handle responses and send confirmations back to Telegram
Technical Details
Request Format (n8n → TARS)
{
  "action": "call_user",
  "phone": "+1XXXXXXXXXX",
  "source": "kipp",
  "chat_id": 8326230132,
  "intent": "call_user",
  "requested_by": "telegram"
}
Response Format (TARS → n8n)
{
  "status": "calling",
  "message": "Calling you now",
  "call_sid": "CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
Error Response Format
{
  "status": "error",
  "error": "Invalid phone number format",
  "message": "Please provide a valid phone number in E.164 format"
}
Files to Modify
communication/twilio_media_streams.py
Add /call route (after line 303)
Add /tars/status route (optional, for future use)
Ensure proper error handling and logging
core/config.py
Verify N8N_TARS_WEBHOOK_URL is properly documented
Ensure WEBHOOK_BASE_URL can be set to tunnel URL
Documentation (optional but recommended)
Update docs/INTEGRATION_GUIDE.md or create docs/N8N_INTEGRATION.md
Document the API contract and n8n workflow setup
Testing Considerations
Local testing: Use curl or Postman to test /call endpoint locally
Tunnel testing: Once exposed via tunnel, test from n8n HTTP Request node
End-to-end: Test full flow: Telegram → n8n → TARS → actual phone call
Error cases: Test with invalid phone numbers, missing fields, etc.
Security Considerations
The endpoint should validate requests (consider API key or source IP whitelist if needed)
Phone numbers should be validated before calling
Rate limiting may be needed for production use
Future Enhancements (Not in Initial Implementation)
Status callback mechanism (TARS → n8n → Telegram)
Support for additional actions beyond "call_user"
Webhook signature verification
Request authentication/authorization
