"""
Sensor event handler
Processes sensor telemetry data and triggers alerts
"""
import logging
from typing import Optional, Callable, Dict, List, Awaitable
from datetime import datetime
from events.types import (
    EventBase,
    SensorTelemetryEvent,
    EventType,
)

logger = logging.getLogger(__name__)


class SensorThresholds:
    """Default sensor thresholds for alert generation"""
    
    GAS_LEVELS = {
        "good": (0, 500),
        "normal": (500, 1200),
        "warning": (1200, 2000),
        "dangerous": (2000, 3000),
        "very_dangerous": (3000, float("inf")),
    }
    
    LIGHT_LEVELS = {
        "very_bright": (50, 300),
        "bright": (300, 800),
        "normal": (800, 1500),
        "medium": (1500, 2500),
        "dark": (2500, 3500),
        "very_dark": (3500, 4095),
    }
    
    TEMPERATURE_LEVELS = {
        "cold": (0, 18),
        "cool": (18, 22),
        "normal": (22, 28),
        "warm": (28, 32),
        "hot": (32, 40),
        "very_hot": (40, float("inf")),
    }
    
    HUMIDITY_LEVELS = {
        "very_dry": (0, 30),
        "dry": (30, 40),
        "normal": (40, 60),
        "humid": (60, 70),
        "very_humid": (70, 100),
    }

    @classmethod
    def get_gas_status(cls, value: float) -> str:
        for status, (min_val, max_val) in cls.GAS_LEVELS.items():
            if min_val <= value < max_val:
                return status
        return "very_dangerous"

    @classmethod
    def get_light_status(cls, value: float) -> str:
        for status, (min_val, max_val) in cls.LIGHT_LEVELS.items():
            if min_val <= value < max_val:
                return status
        return "very_dark"

    @classmethod
    def get_temperature_status(cls, value: float) -> str:
        for status, (min_val, max_val) in cls.TEMPERATURE_LEVELS.items():
            if min_val <= value < max_val:
                return status
        return "very_hot"

    @classmethod
    def get_humidity_status(cls, value: float) -> str:
        for status, (min_val, max_val) in cls.HUMIDITY_LEVELS.items():
            if min_val <= value < max_val:
                return status
        return "very_humid"

    @classmethod
    def get_sensor_status(cls, sensor_type: str, value: float) -> str:
        getters = {
            "gas": cls.get_gas_status,
            "light": cls.get_light_status,
            "temperature": cls.get_temperature_status,
            "humidity": cls.get_humidity_status,
        }
        getter = getters.get(sensor_type)
        if getter:
            return getter(value)
        return "normal"


class SensorEventHandler:
    """
    Handler for sensor telemetry events
    Stores data and triggers threshold alerts
    """

    def __init__(
        self,
        state_store=None,
        alert_handler=None,
        on_threshold_exceeded: Optional[Callable[..., Awaitable]] = None
    ):
        """
        Args:
            state_store: State store for sensor data (Redis)
            alert_handler: Alert handler for triggering alerts
            on_threshold_exceeded: Callback when sensor exceeds threshold
        """
        self._state_store = state_store
        self._alert_handler = alert_handler
        self._on_threshold_exceeded = on_threshold_exceeded
        self._thresholds = SensorThresholds()

    async def handle_event(self, event: EventBase) -> None:
        """Route event to appropriate handler"""
        if isinstance(event, SensorTelemetryEvent):
            await self._handle_telemetry(event)
        elif event.event_type == EventType.SENSOR_THRESHOLD_EXCEEDED:
            await self._handle_threshold_exceeded(event)

    async def _handle_telemetry(self, event: SensorTelemetryEvent) -> None:
        """Handle sensor telemetry data"""
        logger.debug(
            f"Sensor data: {event.sensor_type} = {event.value} {event.unit} "
            f"at {event.location or 'unknown location'}"
        )

        # Get status from thresholds
        status = self._thresholds.get_sensor_status(event.sensor_type, event.value)
        
        # Update state store with sensor data
        if self._state_store:
            try:
                await self._state_store.update_sensor_data(
                    sensor_type=event.sensor_type,
                    value=event.value,
                    unit=event.unit,
                    location=event.location,
                    status=status,
                    device_uid=event.device_uid
                )
            except Exception as e:
                logger.error(f"Failed to update sensor data in state store: {e}")

        # Check for threshold exceedance
        severity = event.get_severity()
        if severity in ("warning", "critical"):
            await self._trigger_threshold_alert(event, severity)

    async def _handle_threshold_exceeded(self, event: EventBase) -> None:
        """Handle threshold exceeded event"""
        logger.warning(
            f"Sensor threshold exceeded: {event.sensor_type} = {event.value}"
        )

        if self._on_threshold_exceeded:
            try:
                await self._on_threshold_exceeded(event)
            except Exception as e:
                logger.error(f"Error in threshold callback: {e}")

    async def _trigger_threshold_alert(
        self, 
        event: SensorTelemetryEvent, 
        severity: str
    ) -> None:
        """Trigger alert when sensor exceeds threshold"""
        status = self._thresholds.get_sensor_status(event.sensor_type, event.value)
        
        alert_message = self._build_alert_message(event, status)
        
        if self._alert_handler:
            try:
                await self._alert_handler.create_alert(
                    name=f"{event.sensor_type.capitalize()} Alert",
                    message=alert_message,
                    severity=severity,
                    sensor_type=event.sensor_type,
                    sensor_value=event.value,
                    device_uid=event.device_uid,
                    location=event.location
                )
            except Exception as e:
                logger.error(f"Failed to create alert: {e}")

        if self._on_threshold_exceeded:
            try:
                await self._on_threshold_exceeded(event)
            except Exception as e:
                logger.error(f"Error in threshold callback: {e}")

    def _build_alert_message(
        self, 
        event: SensorTelemetryEvent, 
        status: str
    ) -> str:
        """Build alert message based on sensor type and status"""
        location = event.location or "không xác định"
        
        status_messages = {
            "gas": {
                "warning": f"Cảnh báo: Mức khí gas tại {location} đang cao ({event.value:.0f} ppm)",
                "critical": f"Nguy hiểm: Mức khí gas tại {location} rất cao ({event.value:.0f} ppm)",
            },
            "temperature": {
                "warning": f"Cảnh báo: Nhiệt độ tại {location} không thoải mái ({event.value:.1f}°C)",
                "critical": f"Nguy hiểm: Nhiệt độ tại {location} nguy hiểm ({event.value:.1f}°C)",
            },
            "humidity": {
                "warning": f"Cảnh báo: Độ ẩm tại {location} không bình thường ({event.value:.0f}%)",
                "critical": f"Nguy hiểm: Độ ẩm tại {location} quá cao ({event.value:.0f}%)",
            },
            "light": {
                "warning": f"Cảnh báo: Ánh sáng tại {location} không phù hợp ({event.value:.0f})",
                "critical": f"Nguy hiểm: Ánh sáng tại {location} quá sáng ({event.value:.0f})",
            },
        }
        
        messages = status_messages.get(event.sensor_type, {}).get(severity)
        if messages:
            return messages
        
        return f"Cảnh báo {severity}: {event.sensor_type} tại {location} = {event.value} {event.unit}"

    def set_state_store(self, state_store) -> None:
        """Set state store instance"""
        self._state_store = state_store

    def set_alert_handler(self, alert_handler) -> None:
        """Set alert handler instance"""
        self._alert_handler = alert_handler

    def set_on_threshold_exceeded(self, callback: Callable[..., Awaitable]) -> None:
        """Set threshold exceeded callback"""
        self._on_threshold_exceeded = callback


async def create_sensor_event_handler(
    state_store=None,
    alert_handler=None
) -> SensorEventHandler:
    """Factory function to create sensor event handler"""
    return SensorEventHandler(
        state_store=state_store,
        alert_handler=alert_handler
    )
