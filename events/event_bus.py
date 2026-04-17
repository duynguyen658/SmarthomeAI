"""
MQTT Event Bus - Central event hub for Smart Home system
Handles pub/sub operations with MQTT broker
"""
import asyncio
import json
from typing import Callable, Dict, List, Optional, Any, Set
from contextlib import asynccontextmanager
import logging

try:
    import aiomqtt
    AIOMQTT_AVAILABLE = True
except ImportError:
    AIOMQTT_AVAILABLE = False

from core.config import get_config, MQTTSettings
from core.exceptions import MQTTConnectionException, EventBusException
from events.types import EventBase, EventType

logger = logging.getLogger(__name__)


class TopicMatcher:
    """Utility class for MQTT topic matching with wildcards"""
    
    @staticmethod
    def matches(topic: str, pattern: str) -> bool:
        """
        Check if topic matches pattern
        Supports + (single level) and # (multi-level) wildcards
        
        Example:
            "smarthome/devices/light/state" matches "smarthome/devices/+/state"
            "smarthome/devices/room/light/state" matches "smarthome/devices/#"
        """
        if pattern == "#":
            return True
        
        if "#" not in pattern:
            # No multi-level wildcard, use simple matching
            if "+" not in pattern:
                return topic == pattern
            else:
                # Split by '/' and compare level by level
                topic_parts = topic.split("/")
                pattern_parts = pattern.split("/")
                
                if len(topic_parts) != len(pattern_parts):
                    return False
                
                for t, p in zip(topic_parts, pattern_parts):
                    if p != "+" and p != t:
                        return False
                return True
        else:
            # Has multi-level wildcard
            pattern_without_hash = pattern.replace("#", "")
            return topic.startswith(pattern_without_hash.rstrip("/"))
    
    @staticmethod
    def get_levels(topic: str) -> List[str]:
        """Get topic levels"""
        return topic.split("/")


class EventBus:
    """
    Central event bus for Smart Home system
    Implements singleton pattern with async initialization
    """
    _instance: Optional["EventBus"] = None
    _lock = asyncio.Lock()

    def __init__(
        self,
        broker: str = None,
        port: int = None,
        settings: MQTTSettings = None
    ):
        config = get_config()
        mqtt_settings = settings or config.mqtt
        
        self.broker = broker or mqtt_settings.mqtt_broker
        self.port = port or mqtt_settings.mqtt_port
        self.username = mqtt_settings.mqtt_username
        self.password = mqtt_settings.mqtt_password
        self.keepalive = mqtt_settings.mqtt_keepalive
        self.default_qos = mqtt_settings.mqtt_qos
        self.default_retain = mqtt_settings.mqtt_retain
        self.client_id = mqtt_settings.mqtt_client_id

        self._client: Optional[aiomqtt.Client] = None
        self._connected = False
        self._connecting = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 60
        
        # Subscription handlers
        self._handlers: Dict[str, List[Callable]] = {}
        self._pattern_handlers: List[tuple[str, Callable]] = []  # (pattern, handler)
        
        # Event type handlers (dispatch by event type)
        self._event_handlers: Dict[EventType, List[Callable]] = {}
        
        # Listening task
        self._listen_task: Optional[asyncio.Task] = None
        
        # Topic matcher
        self._matcher = TopicMatcher()

    @classmethod
    async def get_instance(cls, **kwargs) -> "EventBus":
        """Get or create EventBus singleton instance"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
                    await cls._instance.connect()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton instance (for testing)"""
        cls._instance = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Connect to MQTT broker with retry logic"""
        if self._connected or self._connecting:
            return

        self._connecting = True
        
        try:
            if not AIOMQTT_AVAILABLE:
                logger.warning("aiomqtt not available, using mock event bus")
                self._connected = True
                self._connecting = False
                return

            logger.info(f"Connecting to MQTT broker at {self.broker}:{self.port}")
            
            client_config = aiomqtt.Client.Config(
                client_id=self.client_id,
                clean_session=True,
            )
            
            self._client = aiomqtt.Client(config=client_config)
            
            if self.username and self.password:
                self._client.set_credentials(self.username, self.password)
            
            await self._client.__aenter__()
            self._connected = True
            self._connecting = False
            self._reconnect_delay = 1
            
            logger.info("Successfully connected to MQTT broker")
            
            # Start listening task
            self._listen_task = asyncio.create_task(self._listen())
            
        except Exception as e:
            self._connected = False
            self._connecting = False
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise MQTTConnectionException(self.broker, self.port, str(e))

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker"""
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        if self._client:
            await self._client.__aexit__(None, None)
        
        self._connected = False
        logger.info("Disconnected from MQTT broker")

    async def reconnect(self) -> None:
        """Reconnect with exponential backoff"""
        if self._connected:
            return
        
        self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)
        logger.info(f"Attempting to reconnect in {self._reconnect_delay} seconds...")
        
        await asyncio.sleep(self._reconnect_delay)
        
        try:
            await self.connect()
        except MQTTConnectionException:
            pass  # Will retry on next call

    async def publish(
        self,
        topic: str,
        event: EventBase,
        qos: int = None,
        retain: bool = None
    ) -> None:
        """
        Publish event to MQTT topic
        
        Args:
            topic: MQTT topic
            event: Event to publish
            qos: Quality of Service (0, 1, 2)
            retain: Whether to retain message
        """
        qos = qos if qos is not None else self.default_qos
        retain = retain if retain is not None else self.default_retain

        if not self._connected:
            logger.warning("Not connected to MQTT, attempting to connect...")
            await self.connect()

        try:
            payload = json.dumps(event.model_dump(mode="json"), default=str)
            
            if AIOMQTT_AVAILABLE and self._client:
                await self._client.publish(topic, payload, qos=qos, retain=retain)
                logger.debug(f"Published to {topic}: {event.event_type}")
            else:
                logger.debug(f"[Mock] Would publish to {topic}: {event.model_dump()}")
                
        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")
            raise EventBusException("publish", str(e))

    async def subscribe(
        self,
        topic: str,
        handler: Callable,
        qos: int = None
    ) -> None:
        """
        Subscribe to MQTT topic
        
        Args:
            topic: MQTT topic (supports + and # wildcards)
            handler: Callback function (dict) -> None
            qos: Quality of Service
        """
        qos = qos if qos is not None else self.default_qos

        # Store handler
        if topic not in self._handlers:
            self._handlers[topic] = []
            
            # Subscribe in MQTT
            if self._connected and AIOMQTT_AVAILABLE and self._client:
                await self._client.subscribe(topic, qos=qos)
                logger.info(f"Subscribed to topic: {topic}")
        
        self._handlers[topic].append(handler)
        
        # Also add to pattern handlers for wildcard matching
        if "+" in topic or "#" in topic:
            self._pattern_handlers.append((topic, handler))

    async def unsubscribe(self, topic: str, handler: Callable) -> None:
        """Unsubscribe handler from topic"""
        if topic in self._handlers:
            if handler in self._handlers[topic]:
                self._handlers[topic].remove(handler)
            
            if not self._handlers[topic]:
                del self._handlers[topic]
                if self._connected and AIOMQTT_AVAILABLE and self._client:
                    await self._client.unsubscribe(topic)

    def on_event(self, event_type: EventType, handler: Callable) -> None:
        """
        Register handler for specific event type
        Handler receives the event object directly
        
        Args:
            event_type: Type of event to handle
            handler: Async function (event) -> None
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def off_event(self, event_type: EventType, handler: Callable) -> None:
        """Remove event type handler"""
        if event_type in self._event_handlers:
            if handler in self._event_handlers[event_type]:
                self._event_handlers[event_type].remove(handler)

    async def emit(self, event: EventBase) -> None:
        """
        Emit event to all registered handlers
        
        Args:
            event: Event to emit
        """
        # Get MQTT topic from event
        topic = getattr(event, "mqtt_topic", f"smarthome/{event.event_type}")
        
        # Publish to MQTT
        if self._connected:
            await self.publish(topic, event)
        
        # Call registered handlers
        await self._dispatch_event(event)

    async def _dispatch_event(self, event: EventBase) -> None:
        """Dispatch event to all matching handlers"""
        event_type = event.event_type
        event_dict = event.model_dump() if hasattr(event, "model_dump") else event.__dict__
        
        # Call event type handlers
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")

    async def _listen(self) -> None:
        """Listen for MQTT messages"""
        if not AIOMQTT_AVAILABLE or not self._client:
            logger.warning("MQTT client not available, skipping message listening")
            return

        while self._connected:
            try:
                async for message in self._client.messages:
                    topic = message.topic
                    payload_str = message.payload.decode()
                    
                    try:
                        payload = json.loads(payload_str)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in message from {topic}")
                        continue
                    
                    # Find matching handlers
                    handlers = self._handlers.get(topic, [])
                    
                    # Also check pattern handlers
                    for pattern, handler in self._pattern_handlers:
                        if self._matcher.matches(topic, pattern):
                            if handler not in handlers:
                                handlers.append(handler)
                    
                    # Call handlers
                    for handler in handlers:
                        try:
                            asyncio.create_task(self._handle_message(handler, payload))
                        except Exception as e:
                            logger.error(f"Error dispatching message from {topic}: {e}")
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message listener: {e}")
                await self.reconnect()

    async def _handle_message(self, handler: Callable, payload: Dict[str, Any]) -> None:
        """Handle incoming MQTT message"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(payload)
            else:
                handler(payload)
        except Exception as e:
            logger.error(f"Error in message handler: {e}")


@asynccontextmanager
async def event_bus_context():
    """Context manager for event bus lifecycle"""
    bus = await EventBus.get_instance()
    try:
        yield bus
    finally:
        await bus.disconnect()


class MockEventBus:
    """
    Mock event bus for testing without MQTT broker
    """
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._event_handlers: Dict[EventType, List[Callable]] = {}
        self._published_events: List[EventBase] = []
        self._connected = True

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def publish(self, topic: str, event: EventBase, **kwargs) -> None:
        self._published_events.append(event)
        logger.debug(f"[Mock] Published to {topic}: {event.event_type}")

    async def subscribe(self, topic: str, handler: Callable, **kwargs) -> None:
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)

    async def emit(self, event: EventBase) -> None:
        self._published_events.append(event)
        
        event_dict = event.model_dump() if hasattr(event, "model_dump") else {}
        
        # Call handlers
        topic = getattr(event, "mqtt_topic", "")
        if topic in self._handlers:
            for handler in self._handlers[topic]:
                await handler(event_dict)
        
        # Call event type handlers
        if event.event_type in self._event_handlers:
            for handler in self._event_handlers[event.event_type]:
                await handler(event)

    def on_event(self, event_type: EventType, handler: Callable) -> None:
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def get_published_events(self) -> List[EventBase]:
        return self._published_events

    def clear_events(self) -> None:
        self._published_events.clear()


async def get_event_bus() -> EventBus:
    """Get event bus instance"""
    return await EventBus.get_instance()
