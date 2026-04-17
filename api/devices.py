"""
API endpoints cho Device Management
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from database import get_db, Device
from tools.controlDevice import turn_on_device, turn_off_device

router = APIRouter(tags=["Devices"])


# Pydantic models
class DeviceCreate(BaseModel):
    device_name: str
    device_type: str  # 'light', 'fan', 'sensor', etc.
    location: str
    mac_address: Optional[str] = None
    mqtt_topic: Optional[str] = None
    icon: Optional[str] = None


class DeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    location: Optional[str] = None
    mac_address: Optional[str] = None
    mqtt_topic: Optional[str] = None
    icon: Optional[str] = None
    status: Optional[str] = None


class DeviceResponse(BaseModel):
    id: int
    device_uid: str  # UUID as string
    device_name: str
    device_type: str
    location: str
    mac_address: Optional[str]
    mqtt_topic: Optional[str]
    status: str
    icon: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DeviceControl(BaseModel):
    action: str  # 'ON' or 'OFF'


def serialize_device(device: Device) -> DeviceResponse:
    """Helper function để serialize Device model thành DeviceResponse"""
    return DeviceResponse(
        id=device.id,
        device_uid=str(device.device_uid),
        device_name=device.device_name,
        device_type=device.device_type,
        location=device.location,
        mac_address=device.mac_address,
        mqtt_topic=device.mqtt_topic,
        status=device.status,
        icon=device.icon,
        created_at=device.created_at
    )


@router.get("/devices", response_model=List[DeviceResponse])
async def get_devices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lấy danh sách tất cả devices"""
    devices = db.query(Device).offset(skip).limit(limit).all()
    return [serialize_device(device) for device in devices]


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: int, db: Session = Depends(get_db)):
    """Lấy thông tin một device cụ thể"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return serialize_device(device)


@router.post("/devices", response_model=DeviceResponse, status_code=201)
async def create_device(device: DeviceCreate, db: Session = Depends(get_db)):
    """Tạo device mới"""
    # Validate device type
    valid_types = ['light', 'fan', 'sensor', 'switch', 'thermostat']
    if device.device_type not in valid_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid device type. Must be one of: {', '.join(valid_types)}"
        )
    
    # Kiểm tra MAC address unique nếu có
    if device.mac_address:
        existing_mac = db.query(Device).filter(Device.mac_address == device.mac_address).first()
        if existing_mac:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "MAC address already exists",
                    "message": f"MAC address '{device.mac_address}' đã được sử dụng bởi thiết bị khác",
                    "existing_device_id": existing_mac.id,
                    "suggestion": "Vui lòng sử dụng MAC address khác hoặc xóa thiết bị cũ"
                }
            )
    
    db_device = Device(
        device_name=device.device_name,
        device_type=device.device_type,
        location=device.location,
        mac_address=device.mac_address,
        mqtt_topic=device.mqtt_topic,
        icon=device.icon or "",
        status="OFF"
    )
    
    try:
        db.add(db_device)
        db.commit()
        db.refresh(db_device)
        # Convert UUID to string for response
        return serialize_device(db_device)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating device: {str(e)}")


@router.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: int, 
    device_update: DeviceUpdate, 
    db: Session = Depends(get_db)
):
    """Cập nhật thông tin device"""
    db_device = db.query(Device).filter(Device.id == device_id).first()
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Lấy dữ liệu cập nhật
    update_data = device_update.dict(exclude_unset=True)
    
    # Kiểm tra MAC address unique nếu có thay đổi
    if 'mac_address' in update_data and update_data['mac_address']:
        existing_mac = db.query(Device).filter(
            Device.mac_address == update_data['mac_address'],
            Device.id != device_id
        ).first()
        if existing_mac:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "MAC address already exists",
                    "message": f"MAC address '{update_data['mac_address']}' đã được sử dụng bởi thiết bị khác",
                    "existing_device_id": existing_mac.id,
                    "suggestion": "Vui lòng sử dụng MAC address khác hoặc xóa thiết bị cũ"
                }
            )
    
    # Update fields
    for field, value in update_data.items():
        setattr(db_device, field, value)
    
    try:
        db.commit()
        db.refresh(db_device)
        return serialize_device(db_device)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating device: {str(e)}")


@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(device_id: int, db: Session = Depends(get_db)):
    """Xóa device"""
    db_device = db.query(Device).filter(Device.id == device_id).first()
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    try:
        db.delete(db_device)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting device: {str(e)}")


@router.post("/devices/{device_id}/control")
async def control_device(
    device_id: int,
    control: DeviceControl,
    db: Session = Depends(get_db)
):
    """Điều khiển device trực tiếp (ON/OFF)"""
    db_device = db.query(Device).filter(Device.id == device_id).first()
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if control.action.upper() not in ['ON', 'OFF']:
        raise HTTPException(status_code=400, detail="Action must be 'ON' or 'OFF'")
    
    # Gọi function điều khiển
    if control.action.upper() == 'ON':
        result = turn_on_device(db_device.device_name, db_device.location)
    else:
        result = turn_off_device(db_device.device_name, db_device.location)
    
    # Refresh device status từ database
    db.refresh(db_device)
    
    return {
        "message": result,
        "device_id": device_id,
        "status": db_device.status
    }

