#!/usr/bin/env python3
"""Test script to verify N8N connection."""
import asyncio
import aiohttp
import json
import sys
from config import Config

async def test_n8n_connection():
    """Test connection to N8N webhook."""
    print("=" * 60)
    print("N8N Connection Test")
    print("=" * 60)
    
    # Check if URL is configured
    n8n_webhook_url = Config.N8N_WEBHOOK_URL
    
    if not n8n_webhook_url:
        print("❌ ERROR: N8N_WEBHOOK_URL is not configured in .env file")
        print("\nPlease add to your .env file:")
        print("N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/tars")
        return False
    
    # Fix common .env file issues: remove duplicate variable name if present
    if n8n_webhook_url.startswith("N8N_WEBHOOK_URL="):
        print("⚠️  WARNING: Found duplicate variable name in .env file")
        print(f"   Original value: {n8n_webhook_url}")
        n8n_webhook_url = n8n_webhook_url.replace("N8N_WEBHOOK_URL=", "", 1)
        print(f"   Extracted URL: {n8n_webhook_url}")
        print("   Please fix your .env file to: N8N_WEBHOOK_URL=https://...")
        print()
    
    print(f"✓ N8N_WEBHOOK_URL is configured: {n8n_webhook_url}")
    print()
    
    # Prepare test message
    test_message = "Test connection from TARS"
    payload = {
        "message": test_message
    }
    
    print(f"Sending test message: '{test_message}'")
    print(f"URL: {n8n_webhook_url}")
    print()
    
    try:
        async with aiohttp.ClientSession() as session:
            print("⏳ Connecting to N8N...")
            async with session.post(
                n8n_webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                print(f"✓ HTTP Status: {response.status}")
                print()
                
                # Try to get JSON response
                try:
                    result = await response.json()
                    print("✓ Response (JSON):")
                    print(json.dumps(result, indent=2))
                    print()
                    
                    if response.status == 200:
                        print("✅ SUCCESS: N8N connection is working!")
                        return True
                    else:
                        print(f"⚠️  WARNING: N8N returned status {response.status}")
                        return False
                        
                except Exception as e:
                    # If not JSON, get text response
                    text_result = await response.text()
                    print("✓ Response (Text):")
                    print(text_result)
                    print()
                    
                    if response.status == 200:
                        print("✅ SUCCESS: N8N connection is working!")
                        return True
                    else:
                        print(f"⚠️  WARNING: N8N returned status {response.status}")
                        return False
                        
    except aiohttp.ClientConnectorError as e:
        print(f"❌ ERROR: Could not connect to N8N")
        print(f"   Details: {e}")
        print()
        print("Possible issues:")
        print("  - N8N instance is not running")
        print("  - Webhook URL is incorrect")
        print("  - Network/firewall blocking connection")
        return False
        
    except asyncio.TimeoutError:
        print("❌ ERROR: Connection timeout (10 seconds)")
        print("   N8N did not respond in time")
        return False
        
    except Exception as e:
        print(f"❌ ERROR: Unexpected error")
        print(f"   Details: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(test_n8n_connection())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
