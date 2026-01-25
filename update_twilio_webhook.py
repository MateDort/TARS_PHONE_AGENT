#!/usr/bin/env python3
"""Update Twilio phone number webhook configuration."""
import os
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv()

# Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
WEBHOOK_BASE_URL = os.getenv('WEBHOOK_BASE_URL')

if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, WEBHOOK_BASE_URL]):
    print("❌ Missing required environment variables")
    print(f"   TWILIO_ACCOUNT_SID: {'✓' if TWILIO_ACCOUNT_SID else '✗'}")
    print(f"   TWILIO_AUTH_TOKEN: {'✓' if TWILIO_AUTH_TOKEN else '✗'}")
    print(f"   TWILIO_PHONE_NUMBER: {'✓' if TWILIO_PHONE_NUMBER else '✗'}")
    print(f"   WEBHOOK_BASE_URL: {'✓' if WEBHOOK_BASE_URL else '✗'}")
    exit(1)

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Construct webhook URLs
voice_webhook_url = f"{WEBHOOK_BASE_URL}/webhook/voice"
status_callback_url = f"{WEBHOOK_BASE_URL}/webhook/status"

print(f"\n📱 Twilio Phone Number: {TWILIO_PHONE_NUMBER}")
print(f"🔗 Webhook Base URL: {WEBHOOK_BASE_URL}")
print(f"\nFetching current configuration...")

try:
    # Get phone number SID
    incoming_phone_numbers = client.incoming_phone_numbers.list(phone_number=TWILIO_PHONE_NUMBER)
    
    if not incoming_phone_numbers:
        print(f"❌ Phone number {TWILIO_PHONE_NUMBER} not found in your Twilio account")
        exit(1)
    
    phone_number_sid = incoming_phone_numbers[0].sid
    phone_number = incoming_phone_numbers[0]
    
    print(f"\n📞 Current Configuration:")
    print(f"   Voice URL: {phone_number.voice_url or '(not set)'}")
    print(f"   Voice Method: {phone_number.voice_method or '(not set)'}")
    print(f"   Status Callback: {phone_number.status_callback or '(not set)'}")
    
    # Check if update is needed
    needs_update = (
        phone_number.voice_url != voice_webhook_url or
        phone_number.voice_method != 'POST'
    )
    
    if needs_update:
        print(f"\n⚠️  Configuration needs updating!")
        print(f"\n🔄 Updating to:")
        print(f"   Voice URL: {voice_webhook_url}")
        print(f"   Voice Method: POST")
        print(f"   Status Callback: {status_callback_url}")
        
        # Update phone number configuration
        client.incoming_phone_numbers(phone_number_sid).update(
            voice_url=voice_webhook_url,
            voice_method='POST',
            status_callback=status_callback_url,
            status_callback_method='POST'
        )
        
        print(f"\n✅ Webhook configuration updated successfully!")
    else:
        print(f"\n✅ Configuration is already up to date!")
    
    print(f"\n🎉 Ready to receive calls!")
    print(f"\nTest your setup:")
    print(f"   1. Call {TWILIO_PHONE_NUMBER}")
    print(f"   2. Check terminal logs for connection")

except Exception as e:
    print(f"\n❌ Error: {e}")
    exit(1)
