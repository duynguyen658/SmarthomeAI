"""
Device Registry - Database-backed device management
Provides CRUD operations and device control
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from core.exceptions import DeviceNotFoundException, DeviceControlException
from core.logging import LoggerMixin

logger = logging.getLogger(__name__)


class DeviceRegistry(LoggerMixin):
    """
    Device Registry for managing devices
    Handles CRUD operations and device control
    """

    def __init__(self, db_session: AsyncSession = None):
        self._db = db_session

    def set_session(self, session: AsyncSession) -> None:
        """Set database session"""
        self._db = session

    async def get_device(self, device_id: int) -> Optional[Any]:
        """Get device by ID"""
        from database import Device
        result = await self._db.execute(
            select(Device).where(Device.id == device_id)
        )
        return result.scalar_one_or_none()

    async def get_device_by_uid(self, device_uid: str) -> Optional[Any]:
        """Get device by UID"""
        from database import Device
        result = await self._db.execute(
            select(Device).where(Device.device_uid == device_uid)
        )
        return result.scalar_one_or_none()

    async def get_device_by_mac(self, mac_address: str) -> Optional[Any]:
        """Get device by MAC address"""
        from database import Device
        result = await self._db.execute(
            select(Device).where(Device.mac_address == mac_address)
        )
        return result.scalar_one_or_none()

    async def list_devices(
        self,
        device_type: str = None,
        location: str = None,
        status: str = None
    ) -> List[Any]:
        """List devices with optional filters"""
        from database import Device
        
        query = select(Device)
        
        if device_type:
            query = query.where(Device.device_type == device_type)
        if location:
            query = query.where(Device.location.ilike(f"%{location}%"))
        if status:
            query = query.where(Device.status == status)
        
        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def create_device(self, device_data: Dict[str, Any]) -> Any:
        """Create a new device"""
        from database import Device, DeviceState
        
        device = Device(**device_data)
        self._db.add(device)
        await self._db.commit()
        await self._db.refresh(device)
        
        # Create initial state
        state = DeviceState(
            device_id=device.id,
            state="offline"
        )
        self._db.add(state)
        await self._db.commit()
        
        self.logger.info(f"Created device: {device.device_name} ({device.device_uid})")
        return device

    async def update_device(
        self,
        device_id: int,
        update_data: Dict[str, Any]
    ) -> Optional[Any]:
        """Update device information"""
        from database import Device
        
        await self._db.execute(
            update(Device)
            .where(Device.id == device_id)
            .values(**update_data, updated_at=datetime.utcnow())
        )
        await self._db.commit()
        
        return await self.get_device(device_id)

    async def delete_device(self, device_id: int) -> bool:
        """Delete a device"""
        from database import Device
        
        result = await self._db.execute(
            delete(Device).where(Device.id == device_id)
        )
        await self._db.commit()
        
        return result.rowcount > 0

    async def update_device_state(
        self,
        device_id: int,
        state: str,
        attributes: Dict[str, Any] = None
    ) -> bool:
        """Update device state in database"""
        from database import DeviceState
        
        try:
            await self._db.execute(
                update(DeviceState)
                .where(DeviceState.device_id == device_id)
                .values(
                    state=state,
                    attributes=attributes or {},
                    last_seen=datetime.utcnow()
                )
            )
            await self._db.commit()
            
            # Also update status in Device table
            from database import Device
            await self._db.execute(
                update(Device)
                .where(Device.id == device_id)
                .values(status=state.upper())
            )
            await self._db.commit()
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to update device state: {e}")
            await self._db.rollback()
            return False

    async def control_device(
        self,
        device_id: int,
        action: str,
        params: Dict[str, Any] = None,
        publish_event: bool = True
    ) -> Dict[str, Any]:
        """
        Control a device (turn on/off)
        
        Args:
            device_id: Device ID
            action: Action (on, off, toggle, set)
            params: Additional parameters
            publish_event: Whether to publish MQTT event
            
        Returns:
            Result dict with success status and message
        """
        device = await self.get_device(device_id)
        if not device:
            raise DeviceNotFoundException(device_id=str(device_id))

        # Determine new state
        if action == "on":
            new_state = "on"
        elif action == "off":
            new_state = "off"
        elif action == "toggle":
            current = await self._get_device_state(device_id)
            new_state = "off" if current == "on" else "on"
        elif action == "set" and params:
            new_state = params.get("state", "on")
        else:
            raise DeviceControlException(
                str(device_id),
                action,
                "Unknown action"
            )

        # Publish MQTT command
        if publish_event:
            await self._publish_command(device, new_state, params)

        # Update database state
        await self.update_device_state(device_id, new_state, params)

        self.logger.info(f"Device {device.device_name} set to {new_state}")

        return {
            "success": True,
            "device_id": device_id,
            "device_name": device.device_name,
            "state": new_state,
            "action": action
        }

    async def _publish_command(
        self,
        device: Any,
        state: str,
        params: Dict[str, Any] = None
    ) -> None:
        """Publish command to MQTT broker"""
        try:
            from events.event_bus import get_event_bus
            from events.types import create_device_command_event
            
            event_bus = await get_event_bus()
            
            event = create_device_command_event(
                device_uid=str(device.device_uid),
                command=state,
                device_id=device.id,
                device_name=device.device_name,
                device_type=device.device_type,
                location=device.location,
                params={
                    "action": state,
                    **(params or {})
                }
            )
            
            await event_bus.publish(f"smarthome/devices/{device.device_uid}/command", event)
            
        except Exception as e:
            self.logger.error(f"Failed to publish command: {e}")

    async def _get_device_state(self, device_id: int) -> str:
        """Get current device state"""
        from database import DeviceState
        
        result = await self._db.execute(
            select(DeviceState).where(DeviceState.device_id == device_id)
        )
        state = result.scalar_one_or_none()
        return state.state if state else "off"

    async def get_device_state(self, device_id: int) -> Dict[str, Any]:
        """Get full device state including attributes"""
        device = await self.get_device(device_id)
        if not device:
            raise DeviceNotFoundException(device_id=str(device_id))

        state_obj = await self._get_device_state(device_id)
        
        return {
            "device_id": device.id,
            "device_uid": str(device.device_uid),
            "device_name": device.device_name,
            "device_type": device.device_type,
            "location": device.location,
            "state": state_obj.state if hasattr(state_obj, "state") else state_obj,
            "attributes": state_obj.attributes if hasattr(state_obj, "attributes") else {},
            "last_seen": state_obj.last_seen if hasattr(state_obj, "last_seen") else None,
        }

    async def get_devices_by_location(self, location: str) -> List[Any]:
        """Get all devices in a location"""
        return await self.list_devices(location=location)

    async def get_devices_by_type(self, device_type: str) -> List[Any]:
        """Get all devices of a specific type"""
        return await self.list_devices(device_type=device_type)

    async def get_online_devices(self) -> List[Any]:
        """Get all online devices"""
        from database import Device, DeviceState
        
        result = await self._db.execute(
            select(Device)
            .join(DeviceState)
            .where(DeviceState.state != "offline")
        )
        return list(result.scalars().all())


# Global device registry instance
_device_registry: Optional[DeviceRegistry] = None


def get_device_registry() -> DeviceRegistry:
    """Get device registry singleton"""
    global _device_registry
    if _device_registry is None:
        _device_registry = DeviceRegistry()
    return _device_registry


def set_device_registry(registry: DeviceRegistry) -> None:
    """Set device registry instance"""
    global _device_registry
    _device_registry = registry
