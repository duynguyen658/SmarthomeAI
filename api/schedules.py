"""
API endpoints cho Scheduling & Automation
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from database import get_db, Schedule, Device
from scheduler import add_schedule_job, remove_schedule_job, update_schedule_job

router = APIRouter(prefix="/schedules", tags=["Schedules"])


# Pydantic models
class ScheduleCreate(BaseModel):
    name: str
    device_id: int
    action: str  # 'ON' or 'OFF'
    time: str  # HH:MM format
    days: Optional[List[str]] = None  # ["monday", "tuesday", ...]
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    device_id: Optional[int] = None
    action: Optional[str] = None
    time: Optional[str] = None
    days: Optional[List[str]] = None
    enabled: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: int
    name: str
    device_id: int
    device_name: Optional[str] = None
    device_location: Optional[str] = None
    action: str
    time: str
    days: Optional[List[str]] = None
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[ScheduleResponse])
async def get_schedules(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lấy danh sách tất cả schedules"""
    schedules = db.query(Schedule).offset(skip).limit(limit).all()
    result = []
    for schedule in schedules:
        device = db.query(Device).filter(Device.id == schedule.device_id).first()
        schedule_dict = {
            "id": schedule.id,
            "name": schedule.name,
            "device_id": schedule.device_id,
            "device_name": device.device_name if device else None,
            "device_location": device.location if device else None,
            "action": schedule.action,
            "time": schedule.time,
            "days": schedule.get_days_list(),
            "enabled": schedule.enabled,
            "created_at": schedule.created_at.isoformat() if schedule.created_at else None
        }
        result.append(schedule_dict)
    return result


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Lấy thông tin một schedule cụ thể"""
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    device = db.query(Device).filter(Device.id == schedule.device_id).first()
    return {
        "id": schedule.id,
        "name": schedule.name,
        "device_id": schedule.device_id,
        "device_name": device.name if device else None,
        "device_location": device.location if device else None,
        "action": schedule.action,
        "time": schedule.time,
        "days": schedule.get_days_list(),
        "enabled": schedule.enabled,
        "created_at": schedule.created_at.isoformat() if schedule.created_at else None
    }


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(schedule: ScheduleCreate, db: Session = Depends(get_db)):
    """Tạo schedule mới"""
    # Validate device exists
    device = db.query(Device).filter(Device.id == schedule.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Validate action
    if schedule.action.upper() not in ['ON', 'OFF']:
        raise HTTPException(status_code=400, detail="Action must be 'ON' or 'OFF'")
    
    # Validate time format (HH:MM)
    try:
        hour, minute = map(int, schedule.time.split(':'))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except:
        raise HTTPException(status_code=400, detail="Time must be in HH:MM format (24-hour)")
    
    # Validate days if provided
    valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    if schedule.days:
        for day in schedule.days:
            if day.lower() not in valid_days:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid day: {day}. Must be one of: {', '.join(valid_days)}"
                )
    
    db_schedule = Schedule(
        name=schedule.name,
        device_id=schedule.device_id,
        action=schedule.action.upper(),
        time=schedule.time,
        enabled=schedule.enabled
    )
    db_schedule.set_days_list(schedule.days)
    
    try:
        db.add(db_schedule)
        db.commit()
        db.refresh(db_schedule)
        
        # Add to scheduler if enabled
        if db_schedule.enabled:
            add_schedule_job(db_schedule)
        
        # Return with device info
        return {
            "id": db_schedule.id,
            "name": db_schedule.name,
            "device_id": db_schedule.device_id,
            "device_name": device.device_name,
            "device_location": device.location,
            "action": db_schedule.action,
            "time": db_schedule.time,
            "days": db_schedule.get_days_list(),
            "enabled": db_schedule.enabled,
            "created_at": db_schedule.created_at.isoformat() if db_schedule.created_at else None
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating schedule: {str(e)}")


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    schedule_update: ScheduleUpdate,
    db: Session = Depends(get_db)
):
    """Cập nhật schedule"""
    db_schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Validate device if updating
    if schedule_update.device_id:
        device = db.query(Device).filter(Device.id == schedule_update.device_id).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
    
    # Validate action if updating
    if schedule_update.action and schedule_update.action.upper() not in ['ON', 'OFF']:
        raise HTTPException(status_code=400, detail="Action must be 'ON' or 'OFF'")
    
    # Validate time if updating
    if schedule_update.time:
        try:
            hour, minute = map(int, schedule_update.time.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except:
            raise HTTPException(status_code=400, detail="Time must be in HH:MM format (24-hour)")
    
    # Update fields
    if schedule_update.name is not None:
        db_schedule.name = schedule_update.name
    if schedule_update.device_id is not None:
        db_schedule.device_id = schedule_update.device_id
    if schedule_update.action is not None:
        db_schedule.action = schedule_update.action.upper()
    if schedule_update.time is not None:
        db_schedule.time = schedule_update.time
    if schedule_update.days is not None:
        db_schedule.set_days_list(schedule_update.days)
    if schedule_update.enabled is not None:
        db_schedule.enabled = schedule_update.enabled
    
    try:
        db.commit()
        db.refresh(db_schedule)
        
        # Update scheduler
        update_schedule_job(db_schedule)
        
        # Get device info
        device = db.query(Device).filter(Device.id == db_schedule.device_id).first()
        return {
            "id": db_schedule.id,
            "name": db_schedule.name,
            "device_id": db_schedule.device_id,
            "device_name": device.device_name if device else None,
            "device_location": device.location if device else None,
            "action": db_schedule.action,
            "time": db_schedule.time,
            "days": db_schedule.get_days_list(),
            "enabled": db_schedule.enabled,
            "created_at": db_schedule.created_at.isoformat() if db_schedule.created_at else None
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating schedule: {str(e)}")


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Xóa schedule"""
    db_schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    try:
        # Remove from scheduler
        remove_schedule_job(schedule_id)
        
        # Delete from database
        db.delete(db_schedule)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting schedule: {str(e)}")


@router.post("/{schedule_id}/toggle")
async def toggle_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Bật/tắt schedule"""
    db_schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    db_schedule.enabled = not db_schedule.enabled
    
    try:
        db.commit()
        db.refresh(db_schedule)
        
        # Update scheduler
        update_schedule_job(db_schedule)
        
        return {
            "id": db_schedule.id,
            "enabled": db_schedule.enabled,
            "message": f"Schedule {'enabled' if db_schedule.enabled else 'disabled'}"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error toggling schedule: {str(e)}")

