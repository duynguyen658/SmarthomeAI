"""
Device event handler
Processes device state change and command events
"""
import logging
from typing import Optional, Callable, Awaitable
from events.types import (
    EventBase,
    DeviceStateEvent,
    DeviceCommandEvent,
    EventType,
)

logger = logging.getLogger(__name__)


class DeviceEventHandler:
    """
    Handler for device-related events
    Updates device state in database and state store
    """

    def __init__(
        self,
        state_store=None,
        device_registry=None,
        on_state_change: Optional[Callable[..., Awaitable]] = None
    ):
        """
        Args:
            state_store: State store instance (Redis)
            device_registry: Device registry instance
            on_state_change: Optional callback when device state changes
        """
        self._state_store = state_store
        self._device_registry = device_registry
        self._on_state_change = on_state_change

    async def handle_event(self, event: EventBase) -> None:
        """Route event to appropriate handler"""
        if isinstance(event, DeviceStateEvent):
            await self._handle_state_change(event)
        elif isinstance(event, DeviceCommandEvent):
            await self._handle_command(event)
        elif event.event_type == EventType.DEVICE_ONLINE:
            await self._handle_device_online(event)
        elif event.event_type == EventType.DEVICE_OFFLINE:
            await self._handle_device_offline(event)
        elif event.event_type == EventType.DEVICE_ERROR:
            await self._handle_device_error(event)

    async def _handle_state_change(self, event: DeviceStateEvent) -> None:
        """Handle device state change event"""
        logger.info(
            f"Device state changed: {event.device_uid} -> {event.state} "
            f"(was: {event.previous_state})"
        )

        # Update state store
        if self._state_store:
            try:
                await self._state_store.set_state(
                    device_uid=event.device_uid,
                    state=event.state,
                    attributes=event.attributes,
                    metadata={
                        "device_type": event.device_type,
                        "location": event.location,
                        "device_name": event.device_name,
                    }
                )
            except Exception as e:
                logger.error(f"Failed to update state store: {e}")

        # Update device registry
        if self._device_registry and event.device_id:
            try:
                await self._device_registry.update_device_state(
                    device_id=event.device_id,
                    state=event.state,
                    attributes=event.attributes
                )
            except Exception as e:
                logger.error(f"Failed to update device registry: {e}")

        # Call state change callback
        if self._on_state_change:
            try:
                await self._on_state_change(event)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")

    async def _handle_command(self, event: DeviceCommandEvent) -> None:
        """Handle device command event"""
        logger.info(
            f"Device command: {event.device_uid} -> {event.command} "
            f"(params: {event.params})"
        )

        # Validate command
        if event.command not in ("on", "off", "set", "toggle", "dim"):
            logger.warning(f"Unknown command: {event.command}")
            return

        # Command will be executed by the device or forwarded
        # This is logged for audit purposes
        logger.debug(f"Command logged for {event.device_uid}: {event.command}")

    async def _handle_device_online(self, event: EventBase) -> None:
        """Handle device coming online"""
        logger.info(f"Device online: {event.device_uid if hasattr(event, 'device_uid') else event}")

        if self._state_store:
            device_uid = getattr(event, "device_uid", None)
            if device_uid:
                await self._state_store.set_state(device_uid, "online")

    async def _handle_device_offline(self, event: EventBase) -> None:
        """Handle device going offline"""
        logger.info(f"Device offline: {event.device_uid if hasattr(event, 'device_uid') else event}")

        if self._state_store:
            device_uid = getattr(event, "device_uid", None)
            if device_uid:
                await self._state_store.set_state(device_uid, "offline")

    async def _handle_device_error(self, event: EventBase) -> None:
        """Handle device error event"""
        error_msg = getattr(event, "message", "Unknown error")
        device_uid = getattr(event, "device_uid", "unknown")
        logger.error(f"Device error for {device_uid}: {error_msg}")

        if self._state_store and device_uid != "unknown":
            await self._state_store.set_state(device_uid, "error", attributes={"error": error_msg})

    def set_state_store(self, state_store) -> None:
        """Set state store instance"""
        self._state_store = state_store

    def set_device_registry(self, registry) -> None:
        """Set device registry instance"""
        self._device_registry = registry

    def set_on_state_change(self, callback: Callable[..., Awaitable]) -> None:
        """Set state change callback"""
        self._on_state_change = callback


async def create_device_event_handler(
    state_store=None,
    device_registry=None
) -> DeviceEventHandler:
    """Factory function to create device event handler"""
    return DeviceEventHandler(
        state_store=state_store,
        device_registry=device_registry
    )
