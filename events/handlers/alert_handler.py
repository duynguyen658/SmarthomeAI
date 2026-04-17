"""
Alert event handler
Processes and manages alerts
"""
import logging
from typing import Optional, Callable, List, Dict, Any, Awaitable
from datetime import datetime
from events.types import AlertEvent, EventType

logger = logging.getLogger(__name__)


class AlertEventHandler:
    """
    Handler for alert events
    Creates, manages, and broadcasts alerts
    """

    def __init__(
        self,
        notification_service=None,
        event_bus=None,
        on_alert_created: Optional[Callable[..., Awaitable]] = None,
        on_alert_resolved: Optional[Callable[..., Awaitable]] = None
    ):
        """
        Args:
            notification_service: Service for sending notifications
            event_bus: Event bus for broadcasting alerts
            on_alert_created: Callback when alert is created
            on_alert_resolved: Callback when alert is resolved
        """
        self._notification_service = notification_service
        self._event_bus = event_bus
        self._on_alert_created = on_alert_created
        self._on_alert_resolved = on_alert_resolved
        
        # Active alerts tracking
        self._active_alerts: Dict[str, AlertEvent] = {}
        
        # Alert history
        self._alert_history: List[AlertEvent] = []
        self._max_history = 1000

    async def handle_event(self, event: AlertEvent) -> None:
        """Handle alert event"""
        if event.event_type == EventType.ALERT_TRIGGERED:
            await self._handle_alert_triggered(event)
        elif event.event_type == EventType.ALERT_ACKNOWLEDGED:
            await self._handle_alert_acknowledged(event)
        elif event.event_type == EventType.ALERT_RESOLVED:
            await self._handle_alert_resolved(event)

    async def create_alert(
        self,
        name: str,
        message: str,
        severity: str = "info",
        sensor_type: str = None,
        sensor_value: float = None,
        threshold: float = None,
        device_uid: str = None,
        location: str = None,
        user_id: str = None,
        **kwargs
    ) -> AlertEvent:
        """
        Create a new alert
        
        Returns:
            Created AlertEvent
        """
        # Check for duplicate alert
        alert_key = f"{name}:{device_uid}:{sensor_type}"
        if alert_key in self._active_alerts:
            existing = self._active_alerts[alert_key]
            # Update existing alert if severity increased
            severity_levels = {"info": 0, "warning": 1, "critical": 2}
            if severity_levels.get(severity, 0) > severity_levels.get(existing.severity, 0):
                existing.severity = severity
                existing.sensor_value = sensor_value
                existing.message = message
                logger.info(f"Updated existing alert: {alert_key}")
            return existing

        # Create new alert
        alert = AlertEvent(
            name=name,
            message=message,
            severity=severity,
            sensor_type=sensor_type,
            sensor_value=sensor_value,
            threshold=threshold,
            user_id=user_id,
            metadata={
                "device_uid": device_uid,
                "location": location,
                **kwargs
            }
        )

        # Store active alert
        self._active_alerts[alert_key] = alert
        self._alert_history.append(alert)
        
        # Trim history if needed
        if len(self._alert_history) > self._max_history:
            self._alert_history = self._alert_history[-self._max_history:]

        logger.info(f"Alert created: {name} ({severity})")

        # Send notification
        await self._send_notification(alert)

        # Broadcast event
        if self._event_bus:
            await self._event_bus.emit(alert)

        # Call callback
        if self._on_alert_created:
            try:
                await self._on_alert_created(alert)
            except Exception as e:
                logger.error(f"Error in alert created callback: {e}")

        return alert

    async def acknowledge_alert(self, alert_key: str) -> bool:
        """
        Acknowledge an alert
        
        Args:
            alert_key: Alert identifier
            
        Returns:
            True if acknowledged, False if not found
        """
        if alert_key not in self._active_alerts:
            return False

        alert = self._active_alerts[alert_key]
        alert.acknowledge()

        logger.info(f"Alert acknowledged: {alert_key}")

        # Broadcast acknowledgment
        if self._event_bus:
            await self._event_bus.emit(alert)

        return True

    async def resolve_alert(
        self, 
        alert_key: str, 
        reason: str = None
    ) -> bool:
        """
        Resolve an alert
        
        Args:
            alert_key: Alert identifier
            reason: Optional resolution reason
            
        Returns:
            True if resolved, False if not found
        """
        if alert_key not in self._active_alerts:
            return False

        alert = self._active_alerts[alert_key]
        alert.resolve()
        
        if reason:
            alert.metadata["resolution_reason"] = reason

        logger.info(f"Alert resolved: {alert_key} ({reason or 'auto'})")

        # Remove from active alerts
        del self._active_alerts[alert_key]

        # Broadcast resolution
        if self._event_bus:
            await self._event_bus.emit(alert)

        # Call callback
        if self._on_alert_resolved:
            try:
                await self._on_alert_resolved(alert)
            except Exception as e:
                logger.error(f"Error in alert resolved callback: {e}")

        return True

    async def resolve_alerts_for_device(self, device_uid: str) -> int:
        """
        Resolve all alerts for a specific device
        
        Args:
            device_uid: Device UID
            
        Returns:
            Number of alerts resolved
        """
        resolved = 0
        keys_to_resolve = []
        
        for key, alert in self._active_alerts.items():
            if alert.metadata.get("device_uid") == device_uid:
                keys_to_resolve.append(key)
        
        for key in keys_to_resolve:
            if await self.resolve_alert(key, "Device status normalized"):
                resolved += 1
        
        return resolved

    async def get_active_alerts(
        self, 
        severity: str = None,
        sensor_type: str = None
    ) -> List[AlertEvent]:
        """
        Get active alerts
        
        Args:
            severity: Filter by severity
            sensor_type: Filter by sensor type
            
        Returns:
            List of active alerts
        """
        alerts = list(self._active_alerts.values())
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if sensor_type:
            alerts = [a for a in alerts if a.sensor_type == sensor_type]
        
        return sorted(alerts, key=lambda a: (
            -{"critical": 0, "warning": 1, "info": 2}.get(a.severity, 3),
            -a.timestamp.timestamp()
        ))

    async def get_alert_history(
        self, 
        limit: int = 100,
        severity: str = None
    ) -> List[AlertEvent]:
        """
        Get alert history
        
        Args:
            limit: Maximum number of alerts to return
            severity: Filter by severity
            
        Returns:
            List of historical alerts
        """
        history = self._alert_history[-limit:]
        
        if severity:
            history = [a for a in history if a.severity == severity]
        
        return list(reversed(history))

    async def _handle_alert_triggered(self, event: AlertEvent) -> None:
        """Handle incoming alert triggered event"""
        alert_key = f"{event.name}:{event.metadata.get('device_uid')}:{event.sensor_type}"
        
        if alert_key not in self._active_alerts:
            await self.create_alert(
                name=event.name,
                message=event.message,
                severity=event.severity,
                sensor_type=event.sensor_type,
                sensor_value=event.sensor_value,
                threshold=event.threshold,
                user_id=event.user_id,
                **event.metadata
            )

    async def _handle_alert_acknowledged(self, event: AlertEvent) -> None:
        """Handle alert acknowledgment"""
        alert_key = f"{event.name}:{event.metadata.get('device_uid')}:{event.sensor_type}"
        await self.acknowledge_alert(alert_key)

    async def _handle_alert_resolved(self, event: AlertEvent) -> None:
        """Handle alert resolution"""
        alert_key = f"{event.name}:{event.metadata.get('device_uid')}:{event.sensor_type}"
        await self.resolve_alert(alert_key, event.metadata.get("resolution_reason"))

    async def _send_notification(self, alert: AlertEvent) -> None:
        """Send notification for alert"""
        if not self._notification_service:
            return

        try:
            await self._notification_service.send(
                title=f"[{alert.severity.upper()}] {alert.name}",
                message=alert.message,
                severity=alert.severity,
                user_id=alert.user_id
            )
        except Exception as e:
            logger.error(f"Failed to send alert notification: {e}")

    def set_notification_service(self, service) -> None:
        """Set notification service"""
        self._notification_service = service

    def set_event_bus(self, event_bus) -> None:
        """Set event bus"""
        self._event_bus = event_bus

    def set_on_alert_created(self, callback: Callable[..., Awaitable]) -> None:
        """Set alert created callback"""
        self._on_alert_created = callback

    def set_on_alert_resolved(self, callback: Callable[..., Awaitable]) -> None:
        """Set alert resolved callback"""
        self._on_alert_resolved = callback


async def create_alert_event_handler(
    notification_service=None,
    event_bus=None
) -> AlertEventHandler:
    """Factory function to create alert event handler"""
    return AlertEventHandler(
        notification_service=notification_service,
        event_bus=event_bus
    )
