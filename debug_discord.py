
import os
import asyncio
import discord
from dotenv import load_dotenv

load_dotenv(override=True)

TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID')

print(f"Token present: {bool(TOKEN)}")
print(f"Channel ID: {CHANNEL_ID}")

class DebugClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        
        try:
            channel = self.get_channel(int(CHANNEL_ID))
            if not channel:
                print("Channel not in cache, fetching...")
                channel = await self.fetch_channel(int(CHANNEL_ID))
            
            print(f"Found channel: {channel.name} ({channel.id})")
            await channel.send("🤖 TARS Debug: This is a test message from the debug script.")
            print("Message sent successfully!")
        except Exception as e:
            print(f"Error sending message: {e}")
        
        await self.close()

async def main():
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in .env")
        return
    
    client = DebugClient()
    try:
        await client.start(TOKEN)
    except Exception as e:
        print(f"Login failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
