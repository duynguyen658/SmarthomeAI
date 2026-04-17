"""
Device State Store - Redis-backed state management
Provides fast access to device states with TTL and history
"""
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from core.config import get_config, RedisSettings
from core.exceptions import StateStoreException

logger = logging.getLogger(__name__)


class StateStore:
    """
    Redis-backed state store for device and sensor data
    Provides fast read/write access with automatic TTL management
    """

    # Key prefixes
    DEVICE_PREFIX = "smarthome:device:"
    SENSOR_PREFIX = "smarthome:sensor:"
    STATE_PREFIX = "smarthome:state:"
    HISTORY_PREFIX = "smarthome:history:"
    WORKING_PREFIX = "smarthome:working:"

    # Default TTL (24 hours)
    DEFAULT_TTL = 86400
    SENSOR_TTL = 300  # 5 minutes for sensor data
    HISTORY_TTL = 604800  # 7 days for history

    def __init__(self, redis_url: str = None, settings: RedisSettings = None):
        config = get_config()
        redis_settings = settings or config.redis
        
        self._redis_url = redis_url or redis_settings.connection_url
        self._redis: Optional[redis.Redis] = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, using mock state store")
            self._connected = True
            self._mock_store: Dict[str, Dict] = {}
            return

        try:
            self._redis = redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis.ping()
            self._connected = True
            logger.info("Connected to Redis state store")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = True
            self._mock_store: Dict[str, Dict] = {}
            logger.info("Using mock state store (in-memory)")

    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self._redis:
            await self._redis.close()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ==================== Device State Operations ====================

    async def set_state(
        self,
        device_uid: str,
        state: str,
        attributes: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None,
        ttl: int = None
    ) -> None:
        """
        Set device state
        
        Args:
            device_uid: Unique device identifier
            state: New state (online, offline, on, off, error)
            attributes: Additional state attributes
            metadata: Device metadata
            ttl: Time-to-live in seconds
        """
        key = f"{self.DEVICE_PREFIX}{device_uid}"
        ttl = ttl or self.DEFAULT_TTL

        data = {
            "state": state,
            "attributes": json.dumps(attributes or {}),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if metadata:
            data["metadata"] = json.dumps(metadata)

        if not REDIS_AVAILABLE or not self._redis:
            self._mock_store[key] = data
            return

        try:
            pipe = self._redis.pipeline()
            pipe.hset(key, mapping=data)
            pipe.expire(key, ttl)
            
            # Store previous state for change detection
            prev_key = f"{self.STATE_PREFIX}{device_uid}:prev"
            prev_state = await self._redis.hget(key, "state")
            if prev_state and prev_state != state:
                await self._redis.set(prev_key, prev_state, ex=self.DEFAULT_TTL)
            
            await pipe.execute()
            
            logger.debug(f"Set state for {device_uid}: {state}")
        except Exception as e:
            logger.error(f"Failed to set state for {device_uid}: {e}")
            raise StateStoreException("set_state", str(e))

    async def get_state(self, device_uid: str) -> Optional[Dict[str, Any]]:
        """
        Get device state
        
        Returns:
            State dict with state, attributes, metadata, or None if not found
        """
        key = f"{self.DEVICE_PREFIX}{device_uid}"

        if not REDIS_AVAILABLE or not self._redis:
            data = self._mock_store.get(key)
            if data:
                data["attributes"] = json.loads(data.get("attributes", "{}"))
            return data

        try:
            data = await self._redis.hgetall(key)
            if not data:
                return None
            
            data["attributes"] = json.loads(data.get("attributes", "{}"))
            if "metadata" in data:
                data["metadata"] = json.loads(data["metadata"])
            
            return data
        except Exception as e:
            logger.error(f"Failed to get state for {device_uid}: {e}")
            return None

    async def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all device states
        
        Returns:
            Dict mapping device_uid to state dict
        """
        states = {}

        if not REDIS_AVAILABLE or not self._redis:
            for key, data in self._mock_store.items():
                if key.startswith(self.DEVICE_PREFIX):
                    uid = key.replace(self.DEVICE_PREFIX, "")
                    states[uid] = data.copy()
                    states[uid]["attributes"] = json.loads(data.get("attributes", "{}"))
            return states

        try:
            keys = await self._redis.keys(f"{self.DEVICE_PREFIX}*")
            
            for key in keys:
                if ":state:" in key:
                    continue
                uid = key.replace(self.DEVICE_PREFIX, "")
                data = await self.get_state(uid)
                if data:
                    states[uid] = data
            
            return states
        except Exception as e:
            logger.error(f"Failed to get all states: {e}")
            return {}

    async def update_attribute(
        self,
        device_uid: str,
        attribute: str,
        value: Any
    ) -> None:
        """Update a specific attribute in device state"""
        key = f"{self.DEVICE_PREFIX}{device_uid}"

        if not REDIS_AVAILABLE or not self._redis:
            if key in self._mock_store:
                attrs = json.loads(self._mock_store[key].get("attributes", "{}"))
                attrs[attribute] = value
                self._mock_store[key]["attributes"] = json.dumps(attrs)
            return

        try:
            attributes = await self._redis.hget(key, "attributes")
            attrs = json.loads(attributes or "{}")
            attrs[attribute] = value
            
            await self._redis.hset(
                key,
                mapping={
                    "attributes": json.dumps(attrs),
                    "updated_at": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to update attribute for {device_uid}: {e}")
            raise StateStoreException("update_attribute", str(e))

    async def delete_state(self, device_uid: str) -> bool:
        """Delete device state"""
        key = f"{self.DEVICE_PREFIX}{device_uid}"

        if not REDIS_AVAILABLE or not self._redis:
            if key in self._mock_store:
                del self._mock_store[key]
                return True
            return False

        try:
            result = await self._redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete state for {device_uid}: {e}")
            return False

    # ==================== Sensor Data Operations ====================

    async def update_sensor_data(
        self,
        sensor_type: str,
        value: float,
        unit: str = None,
        location: str = None,
        device_uid: str = None,
        status: str = "normal",
        timestamp: datetime = None
    ) -> None:
        """Update sensor data"""
        key = f"{self.SENSOR_PREFIX}{sensor_type}"
        if device_uid:
            key = f"{key}:{device_uid}"
        elif location:
            key = f"{key}:{location}"

        data = {
            "value": str(value),
            "unit": unit or "",
            "status": status,
            "timestamp": (timestamp or datetime.utcnow()).isoformat()
        }
        if location:
            data["location"] = location
        if device_uid:
            data["device_uid"] = device_uid

        if not REDIS_AVAILABLE or not self._redis:
            self._mock_store[key] = data
            return

        try:
            pipe = self._redis.pipeline()
            pipe.hset(key, mapping=data)
            pipe.expire(key, self.SENSOR_TTL)
            
            # Add to sensor history (sorted set)
            history_key = f"{self.HISTORY_PREFIX}sensor:{sensor_type}"
            score = (timestamp or datetime.utcnow()).timestamp()
            pipe.zadd(history_key, {json.dumps(data): score})
            pipe.expire(history_key, self.HISTORY_TTL)
            
            await pipe.execute()
        except Exception as e:
            logger.error(f"Failed to update sensor data: {e}")

    async def get_sensor_data(
        self,
        sensor_type: str,
        device_uid: str = None,
        location: str = None
    ) -> Optional[Dict[str, Any]]:
        """Get latest sensor data"""
        key = f"{self.SENSOR_PREFIX}{sensor_type}"
        if device_uid:
            key = f"{key}:{device_uid}"
        elif location:
            key = f"{key}:{location}"

        if not REDIS_AVAILABLE or not self._redis:
            return self._mock_store.get(key)

        try:
            data = await self._redis.hgetall(key)
            if data and "value" in data:
                data["value"] = float(data["value"])
            return data or None
        except Exception as e:
            logger.error(f"Failed to get sensor data: {e}")
            return None

    async def get_sensor_history(
        self,
        sensor_type: str,
        limit: int = 100,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get sensor data history"""
        history_key = f"{self.HISTORY_PREFIX}sensor:{sensor_type}"

        if not REDIS_AVAILABLE or not self._redis:
            return []

        try:
            min_score = start_time.timestamp() if start_time else "-inf"
            max_score = end_time.timestamp() if end_time else "+inf"
            
            results = await self._redis.zrangebyscore(
                history_key,
                min=min_score,
                max=max_score,
                start=0,
                num=limit,
                withscores=True
            )
            
            history = []
            for data_str, score in results:
                try:
                    data = json.loads(data_str)
                    data["timestamp"] = datetime.fromtimestamp(score).isoformat()
                    history.append(data)
                except:
                    continue
            
            return history
        except Exception as e:
            logger.error(f"Failed to get sensor history: {e}")
            return []

    # ==================== Working Memory Operations ====================

    async def set_working(
        self,
        user_id: str,
        key: str,
        value: Any,
        ttl: int = 3600
    ) -> None:
        """Set working memory for a user"""
        full_key = f"{self.WORKING_PREFIX}{user_id}:{key}"

        if not REDIS_AVAILABLE or not self._redis:
            self._mock_store[full_key] = value
            return

        try:
            await self._redis.set(
                full_key,
                json.dumps(value),
                ex=ttl
            )
        except Exception as e:
            logger.error(f"Failed to set working memory: {e}")

    async def get_working(self, user_id: str, key: str) -> Optional[Any]:
        """Get working memory for a user"""
        full_key = f"{self.WORKING_PREFIX}{user_id}:{key}"

        if not REDIS_AVAILABLE or not self._redis:
            return self._mock_store.get(full_key)

        try:
            value = await self._redis.get(full_key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Failed to get working memory: {e}")
            return None

    async def delete_working(self, user_id: str, key: str = None) -> None:
        """Delete working memory"""
        if key:
            full_key = f"{self.WORKING_PREFIX}{user_id}:{key}"
            if not REDIS_AVAILABLE or not self._redis:
                self._mock_store.pop(full_key, None)
                return
            await self._redis.delete(full_key)
        else:
            # Delete all working memory for user
            pattern = f"{self.WORKING_PREFIX}{user_id}:*"
            if not REDIS_AVAILABLE or not self._redis:
                keys_to_delete = [k for k in self._mock_store if k.startswith(pattern)]
                for k in keys_to_delete:
                    del self._mock_store[k]
                return
            
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)


# Global state store instance
_state_store: Optional[StateStore] = None


async def get_state_store() -> StateStore:
    """Get or create state store singleton"""
    global _state_store
    if _state_store is None:
        _state_store = StateStore()
        await _state_store.connect()
    return _state_store


async def close_state_store() -> None:
    """Close state store connection"""
    global _state_store
    if _state_store:
        await _state_store.disconnect()
        _state_store = None
