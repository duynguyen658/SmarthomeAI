"""
Notification Service - Monitor sensor data và tạo alerts
"""
import asyncio
from datetime import datetime
from database import SessionLocal, AlertRule, Notification
from tools.rqThingsboard import get_sensor_data
import re

# WebSocket connections để push notifications
websocket_connections = []


def add_websocket_connection(websocket):
    """Thêm WebSocket connection"""
    websocket_connections.append(websocket)


def remove_websocket_connection(websocket):
    """Xóa WebSocket connection"""
    if websocket in websocket_connections:
        websocket_connections.remove(websocket)


async def broadcast_notification(notification_data: dict):
    """Broadcast notification đến tất cả WebSocket connections"""
    disconnected = []
    for ws in websocket_connections:
        try:
            await ws.send_json(notification_data)
        except:
            disconnected.append(ws)
    
    # Remove disconnected connections
    for ws in disconnected:
        remove_websocket_connection(ws)


def parse_sensor_value(sensor_data: str) -> float:
    """Parse giá trị số từ sensor data string"""
    # Extract number from string like "Giá trị cảm biến temperature: 25.5"
    match = re.search(r'[\d.]+', sensor_data)
    if match:
        try:
            return float(match.group())
        except:
            pass
    return None


def check_alert_condition(value: float, rule: AlertRule) -> bool:
    """Kiểm tra xem giá trị có thỏa mãn alert condition không"""
    if value is None:
        return False
    
    condition = rule.condition.lower()
    threshold = rule.threshold_value
    
    if condition == 'gt':  # Greater than
        return value > threshold
    elif condition == 'lt':  # Less than
        return value < threshold
    elif condition == 'eq':  # Equal
        return abs(value - threshold) < 0.01  # Small tolerance for float comparison
    elif condition == 'between':
        if rule.threshold_max is None:
            return False
        return threshold <= value <= rule.threshold_max
    else:
        return False


def create_notification(rule: AlertRule, sensor_value: float, db) -> Notification:
    """Tạo notification mới"""
    # Determine severity based on sensor type and value
    severity = "info"
    if rule.sensor_type in ['gas', 'temperature']:
        if rule.condition == 'gt' and sensor_value > rule.threshold_value * 1.5:
            severity = "critical"
        elif rule.condition == 'gt':
            severity = "warning"
    
    # Create message
    condition_text = {
        'gt': 'vượt quá',
        'lt': 'thấp hơn',
        'eq': 'bằng',
        'between': 'trong khoảng'
    }
    
    message = (
        f"{rule.name}: {rule.sensor_type} "
        f"{condition_text.get(rule.condition, rule.condition)} "
        f"{rule.threshold_value}"
    )
    if rule.condition == 'between' and rule.threshold_max:
        message += f" - {rule.threshold_max}"
    message += f" (Giá trị hiện tại: {sensor_value:.2f})"
    
    notification = Notification(
        alert_rule_id=rule.id,
        message=message,
        severity=severity
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    return notification


async def check_alerts():
    """Background task để kiểm tra alerts mỗi 30 giây"""
    while True:
        try:
            db = SessionLocal()
            try:
                # Lấy tất cả enabled alert rules
                rules = db.query(AlertRule).filter(AlertRule.enabled == True).all()
                
                for rule in rules:
                    try:
                        # Lấy sensor data
                        sensor_data_str = get_sensor_data(rule.sensor_type)
                        sensor_value = parse_sensor_value(sensor_data_str)
                        
                        if sensor_value is None:
                            continue
                        
                        # Kiểm tra condition
                        if check_alert_condition(sensor_value, rule):
                            # Tạo notification
                            notification = create_notification(rule, sensor_value, db)
                            
                            # Broadcast qua WebSocket
                            notification_data = {
                                "id": notification.id,
                                "message": notification.message,
                                "severity": notification.severity,
                                "created_at": notification.created_at.isoformat() if notification.created_at else None,
                                "read": notification.read
                            }
                            await broadcast_notification(notification_data)
                            
                            print(f"Alert triggered: {rule.name} - {notification.message}")
                    except Exception as e:
                        print(f"Error checking alert rule {rule.id}: {e}")
                        continue
            finally:
                db.close()
        except Exception as e:
            print(f"Error in check_alerts: {e}")
        
        # Wait 30 seconds before next check
        await asyncio.sleep(30)


def start_notification_service():
    """Khởi động notification service - task will be created in async context"""
    print("Notification service started")


def get_recent_notifications(limit: int = 50, unread_only: bool = False):
    """Lấy notifications gần đây"""
    db = SessionLocal()
    try:
        query = db.query(Notification).order_by(Notification.created_at.desc())
        if unread_only:
            query = query.filter(Notification.read == False)
        return query.limit(limit).all()
    finally:
        db.close()


def mark_notification_read(notification_id: int):
    """Đánh dấu notification là đã đọc"""
    db = SessionLocal()
    try:
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        if notification:
            notification.read = True
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        print(f"Error marking notification as read: {e}")
        return False
    finally:
        db.close()

