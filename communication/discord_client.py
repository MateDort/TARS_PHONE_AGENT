"""Discord Client for TARS."""
import logging
import asyncio
import os
import discord
from core.config import Config
from core.event_bus import event_bus

logger = logging.getLogger(__name__)

class DiscordClient(discord.Client):
    """Handles Discord communication for TARS."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.token = os.getenv('DISCORD_TOKEN')
        self.channel_id = os.getenv('DISCORD_CHANNEL_ID')
        if self.channel_id:
            self.channel_id = int(self.channel_id)
            
        self.is_running = False

    async def start_client(self):
        """Start the Discord client (wrapper to avoid blocking)."""
        if not self.token:
            logger.warning("DISCORD_TOKEN not set. Discord client disabled.")
            return

        # Discord.py run is blocking, so we need to run it in a task or use start/login
        try:
            # Connect EventBus
            event_bus.subscribe('notification.send', self._handle_notification_event)
            event_bus.subscribe('log.discord', self._handle_log_event)
            
            # Start connection
            await self.login(self.token)
            await self.connect()
        except discord.errors.PrivilegedIntentsRequired:
            logger.error("Discord Privileged Intents not enabled! Please enable 'Message Content Intent' in Discord Developer Portal.")
            # Optional: Retry with limited intents? But we need message content...
        except Exception as e:
            logger.error(f"Failed to start Discord Client: {e}")

    async def on_ready(self):
        self.is_running = True
        logger.info(f'Discord Client logged in as {self.user}')
        
    async def on_message(self, message):
        # Ignore own messages
        if message.author == self.user:
            return

        logger.info(f"Discord message from {message.author}: {message.content}")
        
        # Publish event
        await event_bus.publish('chat.message.received', {
            'platform': 'discord',
            'user_id': message.author.id,
            'username': message.author.name,
            'text': message.content,
            'channel_id': message.channel.id
        })

    async def _handle_notification_event(self, data: dict):
        """Handle outgoing notification event."""
        if not self.is_running:
            return
            
        # Determine target channel
        target_channel_id = data.get('channel_id', self.channel_id)
        message_text = data.get('message')
        
        if target_channel_id and message_text:
            try:
                channel = self.get_channel(target_channel_id)
                if channel:
                    await channel.send(message_text)
                else:
                    # If channel not in cache, fetch it
                    channel = await self.fetch_channel(target_channel_id)
                    await channel.send(message_text)
            except Exception as e:
                logger.error(f"Failed to send Discord message: {e}")

    async def _handle_log_event(self, data: dict):
        """Handle structured log event from background workers."""
        if not self.is_running or not self.channel_id:
            return

        task_id = data.get('task_id')
        msg_type = data.get('type')
        message = data.get('message', '')
        command = data.get('command')
        phase = data.get('phase')
        
        # Format message based on type
        formatted_msg = ""
        
        if msg_type == 'task_started':
             formatted_msg = f"🚀 **Task Started**\n{message}"
        elif msg_type == 'phase_complete':
             formatted_msg = f"✅ **Phase Complete**: {phase}\n{message}"
        elif msg_type == 'error':
             formatted_msg = f"❌ **Error**\n{message}"
        elif msg_type == 'task_complete':
             formatted_msg = f"🎉 **Task Complete**\n{message}"
        else:
             # Regular progress
             formatted_msg = f"ℹ️ **Update** ({task_id}): {message}"
             
        if command:
            formatted_msg += f"\n```bash\n{command}\n```"
            
        try:
            channel = self.get_channel(self.channel_id)
            if not channel:
                channel = await self.fetch_channel(self.channel_id)
            await channel.send(formatted_msg)
        except Exception as e:
             logger.error(f"Failed to send log to Discord: {e}")

# Global accessor
discord_client = DiscordClient()
