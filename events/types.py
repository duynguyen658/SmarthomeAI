"""
Event type definitions for Smart Home system
Pydantic models for all event types
"""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


class EventType(str, Enum):
    """Event type enumeration"""
    # Device events
    DEVICE_STATE_CHANGED = "device.state.changed"
    DEVICE_COMMAND = "device.command"
    DEVICE_TELEMETRY = "device.telemetry"
    DEVICE_ONLINE = "device.online"
    DEVICE_OFFLINE = "device.offline"
    DEVICE_ERROR = "device.error"

    # Sensor events
    SENSOR_DATA = "sensor.data"
    SENSOR_THRESHOLD_EXCEEDED = "sensor.threshold.exceeded"

    # Alert events
    ALERT_TRIGGERED = "alert.triggered"
    ALERT_ACKNOWLEDGED = "alert.acknowledged"
    ALERT_RESOLVED = "alert.resolved"

    # Rule events
    RULE_TRIGGERED = "rule.triggered"
    RULE_EXECUTED = "rule.executed"
    RULE_FAILED = "rule.failed"

    # System events
    SYSTEM_STATUS = "system.status"
    SYSTEM_CONFIG_CHANGED = "system.config.changed"
    SYSTEM_READY = "system.ready"
    SYSTEM_SHUTDOWN = "system.shutdown"


class EventBase(BaseModel):
    """Base model for all events"""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "smarthome"
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_mqtt_payload(self) -> Dict[str, Any]:
        """Convert event to MQTT payload"""
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_mqtt_payload(cls, payload: Dict[str, Any]) -> "EventBase":
        """Create event from MQTT payload"""
        return cls(**payload)


class DeviceStateEvent(EventBase):
    """Event emitted when device state changes"""
    event_type: EventType = EventType.DEVICE_STATE_CHANGED
    device_id: Optional[int] = None
    device_uid: str
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    location: Optional[str] = None
    state: str
    previous_state: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)

    @property
    def mqtt_topic(self) -> str:
        return f"smarthome/devices/{self.device_uid}/state"

    @property
    def is_on(self) -> bool:
        return self.state.lower() in ("on", "online", "1", "true")

    @property
    def is_off(self) -> bool:
        return self.state.lower() in ("off", "offline", "0", "false")


class DeviceCommandEvent(EventBase):
    """Event for device control commands"""
    event_type: EventType = EventType.DEVICE_COMMAND
    device_id: Optional[int] = None
    device_uid: str
    device_name: Optional[str] = None
    command: str  # on, off, set, toggle, dim, etc.
    params: Dict[str, Any] = Field(default_factory=dict)
    response_topic: Optional[str] = None

    @property
    def mqtt_topic(self) -> str:
        return f"smarthome/devices/{self.device_uid}/command"

    @property
    def action(self) -> str:
        return self.params.get("action", self.command)


class SensorTelemetryEvent(EventBase):
    """Event for sensor telemetry data"""
    event_type: EventType = EventType.SENSOR_DATA
    device_id: Optional[int] = None
    device_uid: Optional[str] = None
    sensor_type: str  # temperature, humidity, light, gas
    value: float
    unit: str
    location: Optional[str] = None
    quality: str = "good"  # good, uncertain, bad
    timestamp_ms: Optional[int] = None  # Sensor timestamp in milliseconds

    @property
    def mqtt_topic(self) -> str:
        base = f"smarthome/devices/{self.device_uid or 'sensor'}/telemetry"
        return f"{base}/{self.sensor_type}"

    def get_severity(self) -> str:
        """Determine severity based on sensor type and value"""
        if self.sensor_type == "gas":
            if self.value < 500:
                return "info"
            elif self.value < 1200:
                return "info"
            elif self.value < 2000:
                return "warning"
            elif self.value < 3000:
                return "critical"
            else:
                return "critical"
        elif self.sensor_type == "temperature":
            if 18 <= self.value <= 28:
                return "info"
            elif 28 < self.value <= 35 or 10 <= self.value < 18:
                return "warning"
            else:
                return "critical"
        return "info"


class AlertEvent(EventBase):
    """Event for alert notifications"""
    event_type: EventType = EventType.ALERT_TRIGGERED
    alert_id: Optional[int] = None
    rule_id: Optional[int] = None
    name: str
    severity: str = "info"  # info, warning, critical
    message: str
    sensor_type: Optional[str] = None
    sensor_value: Optional[float] = None
    threshold: Optional[float] = None
    acknowledged: bool = False
    resolved: bool = False

    @property
    def mqtt_topic(self) -> str:
        return f"smarthome/alerts/{self.severity}"

    def acknowledge(self):
        self.acknowledged = True
        self.event_type = EventType.ALERT_ACKNOWLEDGED

    def resolve(self):
        self.resolved = True
        self.event_type = EventType.ALERT_RESOLVED


class SystemEvent(EventBase):
    """Event for system-level events"""
    event_type: EventType = EventType.SYSTEM_STATUS
    component: str  # mqtt, database, redis, qdrant, agent, etc.
    status: str  # healthy, degraded, unhealthy
    message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)


class RuleEvent(EventBase):
    """Event for rule engine events"""
    event_type: EventType = EventType.RULE_EXECUTED
    rule_id: str
    rule_name: str
    trigger_type: str  # event, schedule, manual
    conditions_matched: bool = True
    actions_executed: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "success"  # success, partial, failed
    error: Optional[str] = None
    execution_time_ms: int = 0

    @property
    def mqtt_topic(self) -> str:
        return f"smarthome/rules/{self.rule_id}/execution"


# Event factory functions
def create_device_state_event(
    device_uid: str,
    state: str,
    previous_state: str = None,
    **kwargs
) -> DeviceStateEvent:
    """Factory function to create device state event"""
    return DeviceStateEvent(
        device_uid=device_uid,
        state=state,
        previous_state=previous_state,
        **{k: v for k, v in kwargs.items() if k in DeviceStateEvent.model_fields}
    )


def create_device_command_event(
    device_uid: str,
    command: str,
    params: Dict[str, Any] = None,
    **kwargs
) -> DeviceCommandEvent:
    """Factory function to create device command event"""
    return DeviceCommandEvent(
        device_uid=device_uid,
        command=command,
        params=params or {},
        **{k: v for k, v in kwargs.items() if k in DeviceCommandEvent.model_fields}
    )


def create_sensor_event(
    sensor_type: str,
    value: float,
    unit: str,
    **kwargs
) -> SensorTelemetryEvent:
    """Factory function to create sensor telemetry event"""
    return SensorTelemetryEvent(
        sensor_type=sensor_type,
        value=value,
        unit=unit,
        **{k: v for k, v in kwargs.items() if k in SensorTelemetryEvent.model_fields}
    )


def create_alert_event(
    name: str,
    message: str,
    severity: str = "info",
    **kwargs
) -> AlertEvent:
    """Factory function to create alert event"""
    return AlertEvent(
        name=name,
        message=message,
        severity=severity,
        **{k: v for k, v in kwargs.items() if k in AlertEvent.model_fields}
    )
