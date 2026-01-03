# Goal-Based Outbound Calling - Quick Guide

## What is it?

TARS can now make phone calls on your behalf with specific objectives in mind. Perfect for:
- Booking appointments
- Making inquiries
- Following up with people
- Any task that requires a phone call

## How to Use

### Simple Example
Just tell TARS naturally:
```
"Call my dentist to book an appointment for Wednesday at 2pm"
```

TARS will:
1. Look up your dentist's phone number from contacts (if saved)
2. Make the call immediately
3. During the call, try to book Wednesday at 2pm
4. If that time isn't available, gather alternative times
5. Text you the alternative times for approval

### Advanced Example
```
"Call the DMV to ask about my license renewal.
I prefer to go on Thursday or Friday afternoon if possible"
```

### With Contact Lookup
```
"Call Helen to see if she wants to meet for dinner next Tuesday evening"
```
TARS will look up Helen's number from your contacts automatically.

## Key Features

### Smart Goal Handling
- **Preferred time specified**: TARS will try to get that exact slot
- **No time specified**: TARS will gather available options
- **Alternatives provided**: TARS knows your backup preferences

### Automatic Fallback
If your preferred time isn't available, TARS will:
1. Ask for alternative times during the call
2. Send you a text message with the options
3. Wait for your approval before confirming

### Call Tracking
All goal-based calls are saved to the database:
- What was the goal
- Who was called
- What time you preferred
- The result/outcome

## Commands

### Make a Call
```
"Call [contact/number] to [goal] [optional: preferred time]"
```

Examples:
- "Call 555-1234 to schedule a consultation"
- "Call Dr. Smith to book a checkup for next Monday at 10am"
- "Call the restaurant to make a reservation for Saturday night"

### List Pending Calls
```
"What calls do I have scheduled?"
"Show me my pending call goals"
```

### Cancel a Call
```
"Cancel the call to [contact name]"
```

## Database Schema

Call goals are stored in the `call_goals` table:

| Field | Description |
|-------|-------------|
| phone_number | Who to call |
| contact_name | Name of person/organization |
| goal_type | appointment, inquiry, followup, etc. |
| goal_description | What to accomplish |
| preferred_date | Your preferred date |
| preferred_time | Your preferred time |
| alternative_options | Backup options |
| status | pending, in_progress, completed, failed |
| result | What happened |
| call_sid | Twilio call ID |

## Example Scenarios

### Scenario 1: Dental Appointment
**You**: "Call my dentist to book a cleaning for Wednesday at 2pm. If that's not available, Thursday or Friday afternoon works too."

**TARS**: *Looks up dentist number* → *Makes call* → *During call, tries to book Wednesday 2pm* → *If unavailable, gathers Thursday/Friday afternoon slots* → *Texts you: "Wednesday 2pm not available. Options: Thursday 3pm or Friday 1pm. Reply which works."*

### Scenario 2: Quick Inquiry
**You**: "Call the gym and ask about their monthly membership rates"

**TARS**: *Makes call* → *Asks about membership* → *Takes notes* → *After call, tells you: "Monthly membership is $50, includes all classes. Want me to book a tour?"*

### Scenario 3: Personal Follow-up
**You**: "Call Helen to see if she's free for lunch tomorrow"

**TARS**: *Looks up Helen's number* → *Calls her* → *Casually asks about lunch* → *Reports back: "Helen said she's free after 1pm tomorrow"*

## Technical Details

### Files Modified
- `database.py`: Added `call_goals` table
- `sub_agents_tars.py`: Added `OutboundCallAgent` class
- `main_tars.py`: Registered new agent and function
- `README.md`: Updated documentation

### Agent Functions
- `_schedule_call()`: Creates goal and makes call
- `_list_call_goals()`: Shows pending calls
- `_cancel_call()`: Cancels a scheduled call
- `_format_goal_message()`: Creates structured goal for TARS to follow

### How TARS Receives the Goal
When making a call, TARS gets a formatted message like:
```
CALL OBJECTIVE for Dr. Smith's Office:
Type: appointment
Goal: Book a dental cleaning
Preferred: Wednesday at 2pm
Alternatives: Thursday or Friday afternoon

IMPORTANT: If the preferred time is not available,
gather alternative times and text them to Máté for approval.
```

This is passed as the `reminder_message` parameter to Twilio, which TARS sees during the call.

## Tips

1. **Save contacts first**: Add important contacts so TARS can look them up by name
2. **Be specific about goals**: "Book appointment" is better than just "call"
3. **Provide alternatives**: Gives TARS flexibility to find a good time
4. **Check pending calls**: Use "show my pending calls" to track what's queued

## Future Enhancements

Potential additions:
- Schedule calls for later (not just immediate)
- Retry failed calls automatically
- Learn from past successful calls
- Integration with calendar systems
- Voice confirmation after calls

---

**Created**: 2026-01-03
**Status**: Fully Functional ✅
