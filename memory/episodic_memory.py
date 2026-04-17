"""
Episodic Memory
Stores event history and interaction records
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of episodic events"""
    DEVICE_CONTROL = "device_control"
    SENSOR_READING = "sensor_reading"
    RULE_EXECUTED = "rule_executed"
    ALERT_TRIGGERED = "alert_triggered"
    NOTIFICATION_SENT = "notification_sent"
    USER_INTERACTION = "user_interaction"
    SCENE_ACTIVATED = "scene_activated"
    SYSTEM_EVENT = "system_event"


class EpisodicMemory:
    """
    Episodic memory storage
    Stores event history for recall and learning
    """

    def __init__(self, db_session=None):
        self._db = db_session
        # In-memory storage if no DB
        self._events: List[Dict[str, Any]] = []
        self._max_events = 10000

    def set_db_session(self, session) -> None:
        """Set database session"""
        self._db = session

    async def add(
        self,
        user_id: str,
        event_type: EventType,
        event_data: Dict[str, Any],
        timestamp: datetime = None,
        context: Dict[str, Any] = None
    ) -> str:
        """
        Add an episodic event
        
        Args:
            user_id: User identifier
            event_type: Type of event
            event_data: Event data
            timestamp: Event timestamp
            context: Additional context
            
        Returns:
            Event ID
        """
        from uuid import uuid4
        import json
        
        event_id = str(uuid4())
        timestamp = timestamp or datetime.utcnow()

        event = {
            "id": event_id,
            "user_id": user_id,
            "event_type": event_type.value if isinstance(event_type, EventType) else event_type,
            "event_data": event_data,
            "timestamp": timestamp.isoformat(),
            "context": context or {},
            "created_at": datetime.utcnow().isoformat()
        }

        self._events.append(event)
        
        # Trim if needed
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        logger.debug(f"Added episodic event: {event_id} ({event_type})")
        return event_id

    async def get_recent(
        self,
        user_id: str,
        limit: int = 50,
        event_type: EventType = None,
        since: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent events
        
        Args:
            user_id: User identifier
            limit: Maximum events
            event_type: Filter by type
            since: Only events after this time
            
        Returns:
            List of events
        """
        events = [e for e in self._events if e["user_id"] == user_id]

        if event_type:
            event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
            events = [e for e in events if e["event_type"] == event_type_str]

        if since:
            since_str = since.isoformat()
            events = [e for e in events if e["timestamp"] >= since_str]

        # Sort by timestamp descending
        events = sorted(events, key=lambda x: x["timestamp"], reverse=True)

        return events[:limit]

    async def get_interactions(
        self,
        user_id: str,
        limit: int = 100,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get recent user interactions"""
        since = datetime.utcnow() - timedelta(days=days)
        return await self.get_recent(
            user_id=user_id,
            limit=limit,
            event_type=EventType.USER_INTERACTION,
            since=since
        )

    async def get_device_history(
        self,
        user_id: str,
        device_uid: str = None,
        limit: int = 100,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get device control history"""
        since = datetime.utcnow() - timedelta(days=days)
        events = await self.get_recent(
            user_id=user_id,
            limit=limit,
            event_type=EventType.DEVICE_CONTROL,
            since=since
        )

        if device_uid:
            events = [
                e for e in events
                if e["event_data"].get("device_uid") == device_uid
            ]

        return events

    async def get_alert_history(
        self,
        user_id: str,
        limit: int = 50,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get alert history"""
        since = datetime.utcnow() - timedelta(days=days)
        return await self.get_recent(
            user_id=user_id,
            limit=limit,
            event_type=EventType.ALERT_TRIGGERED,
            since=since
        )

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search events by content
        
        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum results
            
        Returns:
            Matching events
        """
        query_lower = query.lower()
        events = [
            e for e in self._events
            if e["user_id"] == user_id
            and (
                query_lower in str(e["event_data"]).lower()
                or query_lower in str(e.get("context", {})).lower()
            )
        ]

        events = sorted(events, key=lambda x: x["timestamp"], reverse=True)
        return events[:limit]

    async def get_daily_summary(
        self,
        user_id: str,
        date: datetime = None
    ) -> Dict[str, Any]:
        """
        Get summary of events for a day
        
        Args:
            user_id: User identifier
            date: Date to summarize
            
        Returns:
            Summary dict
        """
        from datetime import datetime, timedelta
        
        date = date or datetime.utcnow()
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        events = await self.get_recent(
            user_id=user_id,
            limit=10000,
            since=start_of_day
        )

        # Count by type
        by_type = {}
        for event in events:
            event_type = event["event_type"]
            by_type[event_type] = by_type.get(event_type, 0) + 1

        # Device controls
        device_controls = [
            e for e in events
            if e["event_type"] == EventType.DEVICE_CONTROL.value
        ]

        # Alerts
        alerts = [
            e for e in events
            if e["event_type"] == EventType.ALERT_TRIGGERED.value
        ]

        return {
            "date": date.strftime("%Y-%m-%d"),
            "total_events": len(events),
            "by_type": by_type,
            "device_controls": len(device_controls),
            "alerts": len(alerts),
            "interactions": by_type.get(EventType.USER_INTERACTION.value, 0)
        }

    async def delete_before(self, cutoff: datetime) -> int:
        """Delete events before cutoff date"""
        cutoff_str = cutoff.isoformat()
        original_count = len(self._events)
        
        self._events = [
            e for e in self._events
            if e["timestamp"] >= cutoff_str
        ]
        
        deleted = original_count - len(self._events)
        logger.info(f"Deleted {deleted} events before {cutoff_str}")
        
        return deleted

    async def count(self, user_id: str = None) -> int:
        """Count events"""
        if user_id:
            return sum(1 for e in self._events if e["user_id"] == user_id)
        return len(self._events)
