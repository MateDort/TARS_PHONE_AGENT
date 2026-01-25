#!/usr/bin/env python3
"""Send a message to N8N."""
import asyncio
import aiohttp
import json
import sys
from config import Config

async def send_message(message: str):
    """Send a message to N8N webhook."""
    # Get N8N webhook URL
    n8n_webhook_url = Config.N8N_WEBHOOK_URL
    
    if not n8n_webhook_url:
        print("❌ ERROR: N8N_WEBHOOK_URL is not configured in .env file")
        return False
    
    # Fix common .env file issues: remove duplicate variable name if present
    if n8n_webhook_url.startswith("N8N_WEBHOOK_URL="):
        n8n_webhook_url = n8n_webhook_url.replace("N8N_WEBHOOK_URL=", "", 1)
    
    # Prepare payload
    payload = {
        "message": message
    }
    
    print(f"Sending message to N8N: '{message}'")
    print(f"URL: {n8n_webhook_url}")
    print()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                n8n_webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                print(f"HTTP Status: {response.status}")
                
                # Try to get JSON response
                try:
                    result = await response.json()
                    print("Response:")
                    print(json.dumps(result, indent=2))
                    
                    if response.status == 200:
                        print("\n✅ Message sent successfully!")
                        return True
                    else:
                        print(f"\n⚠️  Warning: N8N returned status {response.status}")
                        return False
                        
                except Exception:
                    # If not JSON, get text response
                    text_result = await response.text()
                    print("Response:")
                    print(text_result)
                    
                    if response.status == 200:
                        print("\n✅ Message sent successfully!")
                        return True
                    else:
                        print(f"\n⚠️  Warning: N8N returned status {response.status}")
                        return False
                        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    message = sys.argv[1] if len(sys.argv) > 1 else "hello"
    try:
        success = asyncio.run(send_message(message))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
