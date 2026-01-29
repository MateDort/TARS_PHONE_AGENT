"""Telegram Bot Client for TARS."""
import logging
import asyncio
import os
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from core.config import Config
from core.event_bus import event_bus

logger = logging.getLogger(__name__)

class TelegramClient:
    """Handles Telegram communication for TARS."""
    
    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_TARS_CHAT_ID or Config.TELEGRAM_MATE_CHAT_ID
        self.app = None
        self.bot = None
        self.is_running = False

    async def start(self):
        """Start the Telegram bot."""
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN not set. Telegram client disabled.")
            return

        try:
            self.app = ApplicationBuilder().token(self.token).build()
            self.bot = self.app.bot
            
            # Register handlers
            self.app.add_handler(CommandHandler("start", self._start_command))
            self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_message))
            self.app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))
            self.app.add_handler(MessageHandler(filters.PHOTO, self._handle_photo))
            
            # Start polling (non-blocking way requires generic run_polling or manual handling)
            # Since TARS has its own loop, we typically use initialize() + start() + updater.start_polling()
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            
            self.is_running = True
            logger.info("Telegram Client started.")
            
            # Subscribe to notifications
            event_bus.subscribe('notification.send', self._handle_notification_event)
            
        except Exception as e:
            logger.error(f"Failed to start Telegram Client: {e}")

    async def stop(self):
        """Stop the bot."""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            self.is_running = False
            logger.info("Telegram Client stopped.")

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Hello! I am TARS. Use /help to see commands.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages."""
        text = update.message.text
        user_id = update.effective_user.id
        
        logger.info(f"Telegram message from {user_id}: {text}")
        
        # Publish event
        await event_bus.publish('chat.message.received', {
            'platform': 'telegram',
            'user_id': user_id,
            'username': update.effective_user.username or update.effective_user.first_name,
            'text': text,
            'chat_id': update.effective_chat.id
        })

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming voice messages."""
        user_id = update.effective_user.id
        file_id = update.message.voice.file_id
        
        logger.info(f"Telegram voice message from {user_id}")
        
        try:
            # Download file
            new_file = await context.bot.get_file(file_id)
            os.makedirs("/tmp/tars_media", exist_ok=True)
            file_path = f"/tmp/tars_media/voice_{file_id}.ogg"
            await new_file.download_to_drive(file_path)
            
            await event_bus.publish('chat.voice.received', {
                'platform': 'telegram',
                'user_id': user_id,
                'username': update.effective_user.username,
                'file_id': file_id,
                'file_path': file_path,
                'chat_id': update.effective_chat.id
            })
        except Exception as e:
            logger.error(f"Failed to download voice message: {e}")
            await update.message.reply_text("I couldn't download your voice message. My apologies.")

    async def _handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming photo messages."""
        user_id = update.effective_user.id
        # Get the largest photo
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        logger.info(f"Telegram photo from {user_id}")
        
        try:
            # Download file
            new_file = await context.bot.get_file(file_id)
            os.makedirs("/tmp/tars_media", exist_ok=True)
            file_path = f"/tmp/tars_media/photo_{file_id}.jpg"
            await new_file.download_to_drive(file_path)
            
            await event_bus.publish('chat.photo.received', {
                'platform': 'telegram',
                'user_id': user_id,
                'username': update.effective_user.username,
                'file_id': file_id,
                'caption': update.message.caption or "",
                'file_path': file_path,
                'chat_id': update.effective_chat.id
            })
        except Exception as e:
             logger.error(f"Failed to download photo: {e}")
             await update.message.reply_text("I couldn't download the photo. My apologies.")

    async def _handle_notification_event(self, data: dict):
        """Handle outgoing notification event."""
        if not self.is_running or not self.bot:
            return
            
        target_chat = data.get('chat_id', self.chat_id)
        message = data.get('message')
        
        if target_chat and message:
            try:
                await self.bot.send_message(chat_id=target_chat, text=message)
            except Exception as e:
                logger.error(f"Failed to send Telegram message: {e}")

    async def send_message(self, text: str, chat_id: str = None):
        """Direct send method."""
        target = chat_id or self.chat_id
        if target and self.bot:
             await self.bot.send_message(chat_id=target, text=text)

# Global accessor
telegram_client = TelegramClient()
