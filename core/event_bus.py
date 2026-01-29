"""Event Bus for TARS - Enabling asynchronous communication between agents."""
import logging
import json
import asyncio
import redis.asyncio as redis
from typing import Callable, Dict, Any, List
from core.config import Config

logger = logging.getLogger(__name__)

class EventBus:
    """Redis-based Pub/Sub Event Bus for TARS Agents."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.redis = None
            cls._instance.pubsub = None
            cls._instance.handlers: Dict[str, List[Callable]] = {}
            cls._instance.is_running = False
        return cls._instance

    async def connect(self):
        """Connect to Redis."""
        if not self.redis:
            self.redis = redis.Redis(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                decode_responses=True
            )
            self.pubsub = self.redis.pubsub()
            logger.info("EventBus connected to Redis.")

    async def start_listening(self):
        """Start the main listener loop for subscribed channels."""
        if self.is_running:
            return
            
        await self.connect()
        self.is_running = True
        
        # Subscribe to all channels that have handlers
        if self.handlers:
            await self.pubsub.subscribe(*self.handlers.keys())
            
        logger.info(f"EventBus listening on channels: {list(self.handlers.keys())}")
        
        asyncio.create_task(self._listener_loop())

    async def _listener_loop(self):
        """Internal loop to process incoming messages."""
        try:
            while self.is_running:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    channel = message['channel']
                    data_str = message['data']
                    try:
                        data = json.loads(data_str)
                        await self._dispatch(channel, data)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to decode JSON from channel {channel}: {data_str}")
                else:
                    await asyncio.sleep(0.01)  # Prevent busy loop
        except Exception as e:
            logger.error(f"EventBus listener error: {e}")
            # Attempt reconnect logic could go here
            self.is_running = False

    async def _dispatch(self, channel: str, data: Dict[str, Any]):
        """Dispatch message to registered handlers."""
        if channel in self.handlers:
            for handler in self.handlers[channel]:
                try:
                    # Fire and forget handlers? Or await?
                    # For autonomy, fire and forget logic is usually safer to prevent blocking the bus
                    asyncio.create_task(handler(data))
                except Exception as e:
                    logger.error(f"Error in handler for {channel}: {e}")

    async def publish(self, channel: str, message: Dict[str, Any]):
        """Publish a message to a channel."""
        if not self.redis:
            await self.connect()
        
        # Add timestamp and metadata if missing
        if 'timestamp' not in message:
            import time
            message['timestamp'] = time.time()
            
        try:
            await self.redis.publish(channel, json.dumps(message))
            logger.debug(f"Published to {channel}: {message}")
        except Exception as e:
            logger.error(f"Failed to publish to {channel}: {e}")

    def subscribe(self, channel: str, callback: Callable):
        """Register a callback for a channel.
        
        Args:
            channel: The channel name (e.g., 'tars.core.voice_transcribed')
            callback: Async function taking one argument (dict)
        """
        if channel not in self.handlers:
            self.handlers[channel] = []
            # If already running, need to update redis subscription
            if self.is_running and self.pubsub:
                asyncio.create_task(self.pubsub.subscribe(channel))
                
        self.handlers[channel].append(callback)
        logger.info(f"Subscribed callback to {channel}")

    async def close(self):
        """Close Redis connection."""
        self.is_running = False
        if self.pubsub:
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()

# Global accessor
event_bus = EventBus()
