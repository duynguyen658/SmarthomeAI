"""
API endpoints cho Alerts & Notifications
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from database import get_db, AlertRule, Notification
from notification_service import (
    add_websocket_connection,
    remove_websocket_connection,
    get_recent_notifications,
    mark_notification_read
)

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# Pydantic models
class AlertRuleCreate(BaseModel):
    name: str
    sensor_type: str  # 'temperature', 'humidity', 'gas', 'light'
    condition: str  # 'gt', 'lt', 'eq', 'between'
    threshold_value: float
    threshold_max: Optional[float] = None  # For 'between' condition
    enabled: bool = True
    notification_type: str = "browser"  # 'browser', 'email', 'sms'


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    sensor_type: Optional[str] = None
    condition: Optional[str] = None
    threshold_value: Optional[float] = None
    threshold_max: Optional[float] = None
    enabled: Optional[bool] = None
    notification_type: Optional[str] = None


class AlertRuleResponse(BaseModel):
    id: int
    name: str
    sensor_type: str
    condition: str
    threshold_value: float
    threshold_max: Optional[float]
    enabled: bool
    notification_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    id: int
    alert_rule_id: Optional[int]
    message: str
    severity: str
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/rules", response_model=List[AlertRuleResponse])
async def get_alert_rules(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Lấy danh sách tất cả alert rules"""
    rules = db.query(AlertRule).offset(skip).limit(limit).all()
    return rules


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    """Lấy thông tin một alert rule cụ thể"""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


@router.post("/rules", response_model=AlertRuleResponse, status_code=201)
async def create_alert_rule(rule: AlertRuleCreate, db: Session = Depends(get_db)):
    """Tạo alert rule mới"""
    # Validate sensor type
    valid_sensor_types = ['temperature', 'humidity', 'gas', 'light']
    if rule.sensor_type not in valid_sensor_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sensor type. Must be one of: {', '.join(valid_sensor_types)}"
        )
    
    # Validate condition
    valid_conditions = ['gt', 'lt', 'eq', 'between']
    if rule.condition not in valid_conditions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid condition. Must be one of: {', '.join(valid_conditions)}"
        )
    
    # Validate threshold_max for 'between' condition
    if rule.condition == 'between' and rule.threshold_max is None:
        raise HTTPException(
            status_code=400,
            detail="threshold_max is required for 'between' condition"
        )
    
    db_rule = AlertRule(
        name=rule.name,
        sensor_type=rule.sensor_type,
        condition=rule.condition,
        threshold_value=rule.threshold_value,
        threshold_max=rule.threshold_max,
        enabled=rule.enabled,
        notification_type=rule.notification_type
    )
    
    try:
        db.add(db_rule)
        db.commit()
        db.refresh(db_rule)
        return db_rule
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating alert rule: {str(e)}")


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: int,
    rule_update: AlertRuleUpdate,
    db: Session = Depends(get_db)
):
    """Cập nhật alert rule"""
    db_rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    # Validate if updating condition to 'between'
    if rule_update.condition == 'between' and rule_update.threshold_max is None:
        if db_rule.threshold_max is None:
            raise HTTPException(
                status_code=400,
                detail="threshold_max is required for 'between' condition"
            )
    
    # Update fields
    update_data = rule_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_rule, field, value)
    
    try:
        db.commit()
        db.refresh(db_rule)
        return db_rule
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating alert rule: {str(e)}")


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    """Xóa alert rule"""
    db_rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    try:
        db.delete(db_rule)
        db.commit()
        return None
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting alert rule: {str(e)}")


@router.get("/notifications", response_model=List[NotificationResponse])
async def get_notifications(
    limit: int = 50,
    unread_only: bool = False,
    db: Session = Depends(get_db)
):
    """Lấy danh sách notifications"""
    notifications = get_recent_notifications(limit=limit, unread_only=unread_only)
    return notifications


@router.post("/notifications/{notification_id}/read")
async def mark_notification_as_read(notification_id: int):
    """Đánh dấu notification là đã đọc"""
    success = mark_notification_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read", "id": notification_id}


@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket):
    """WebSocket endpoint cho real-time notifications"""
    await websocket.accept()
    add_websocket_connection(websocket)
    
    try:
        # Send recent unread notifications on connect
        notifications = get_recent_notifications(limit=10, unread_only=True)
        for notification in notifications:
            try:
                await websocket.send_json({
                    "id": notification.id,
                    "message": notification.message,
                    "severity": notification.severity,
                    "created_at": notification.created_at.isoformat() if notification.created_at else None,
                    "read": notification.read
                })
            except:
                pass  # Skip if can't send
        
        # Keep connection alive
        while True:
            try:
                await websocket.receive_text()
            except:
                break
    except WebSocketDisconnect:
        remove_websocket_connection(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        remove_websocket_connection(websocket)

