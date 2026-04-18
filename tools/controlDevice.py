from paho.mqtt import client as mqtt_client
import time 
import json 
import sys 
import os
import redis
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path để import database
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redis client cho sensor data
redis_client = None
try:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.ping()
    print("Redis connected for sensor data")
except Exception as e:
    print(f"Redis not available: {e}")
    redis_client = None

try:
    from database import SessionLocal, Device
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("Warning: Database not available, using hardcoded devices")

# --- CẤU HÌNH ---
MQTT_BROKER = "10.50.112.136"
MQTT_PORT = 1883
MQTT_TOPIC_PUB = "smartHome/command"
MQTT_TOPIC_SUB = "smartHome/sensor/data"
MQTT_TIMEOUT = 5  # seconds

# Backward compatibility - giữ lại cho legacy code
HOME_DEVICE = {
    "phòng khách": ["đèn", "quạt"]
}

real_time_state = {
    "phòng khách": {"đèn": "OFF", "quạt": "OFF"}
}

client = mqtt_client.Client(callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Kết nối MQTT thành công")
        client.subscribe(MQTT_TOPIC_SUB)
    else:
        print(f"Lỗi kết nối: {rc}")

def on_message(client, userdata, msg):
    """Callback khi nhận message từ MQTT - xử lý cả device command và sensor data"""
    global real_time_state
    try:
        data = json.loads(msg.payload.decode())
        
        # ========================================
        # XỬ LÝ SENSOR DATA (từ ESP32 DHT22)
        # ========================================
        if "temperature" in data or "humidity" in data or "gas" in data:
            if redis_client:
                # Lưu từng sensor vào Redis với key riêng
                if "temperature" in data:
                    redis_client.set("sensor/temperature", json.dumps({"value": data["temperature"]}))
                    print(f"📤 Redis: temperature = {data['temperature']}")
                if "humidity" in data:
                    redis_client.set("sensor/humidity", json.dumps({"value": data["humidity"]}))
                    print(f"📤 Redis: humidity = {data['humidity']}")
                if "gas" in data:
                    redis_client.set("sensor/gas", json.dumps({"value": data["gas"]}))
                    print(f"📤 Redis: gas = {data['gas']}")
            else:
                print("Redis not available, sensor data not saved")
            return  # Không xử lý tiếp
        
        # ========================================
        # XỬ LÝ DEVICE COMMAND (từ backend/app)
        # ========================================
        if "location" in data and "device" in data:
            location = data["location"].lower()
            device_code = data["device"]  # 'light' hoặc 'fan'
            status = data["status"]
            
            # Update database nếu có
            if DB_AVAILABLE:
                db = SessionLocal()
                try:
                    device = db.query(Device).filter(
                        Device.location.ilike(f"%{location}%"),
                        Device.device_type == device_code
                    ).first()
                    
                    if device:
                        device.status = status
                        db.commit()
                        print(f"Đồng bộ DB: {device.device_name} tại {location} đang {status}")
                except Exception as e:
                    print(f"Error syncing to database: {e}")
                    db.rollback()
                finally:
                    db.close()
            
            # Update real_time_state (backward compatibility)
            device_type = "đèn" if device_code == "light" else "quạt"
            if location not in real_time_state:
                real_time_state[location] = {}
            real_time_state[location][device_type] = status
            print(f"🔄 Đồng bộ: {device_type} tại {location} đang {status}")
    except Exception as e:
        print(f"Lỗi nhận tin: {e}")

client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_start()
except Exception as e:
        print(f"Lỗi MQTT: {e}")

def get_device_from_db(device_name: str, location: str):
    """Lấy device từ database"""
    if not DB_AVAILABLE:
        print(f"[DEBUG] DB_AVAILABLE=False, bỏ qua database")
        return None
    
    print(f"[DEBUG] DB_AVAILABLE=True, đang tìm device={device_name}, location={location}")
    
    # Chuyển đổi device_name sang device_type
    device_type = None
    if "đèn" in device_name.lower() or "light" in device_name.lower():
        device_type = "light"
    elif "quạt" in device_name.lower() or "fan" in device_name.lower():
        device_type = "fan"
    
    db = SessionLocal()
    try:
        if device_type:
            # Tìm theo device_type và location
            device = db.query(Device).filter(
                Device.location.ilike(f"%{location}%"),
                Device.device_type == device_type
            ).first()
        else:
            # Fallback: tìm theo device_name và location
            device = db.query(Device).filter(
                Device.location.ilike(f"%{location}%"),
                Device.device_name.ilike(f"%{device_name}%")
            ).first()
        return device
    except Exception as e:
        print(f"Error querying database: {e}")
        return None
    finally:
        db.close()


def safe_publish(topic, payload, timeout=MQTT_TIMEOUT):
    """Publish MQTT message với timeout - không block quá lâu"""
    try:
        if not client.is_connected():
            print(f"[MQTT] Not connected, skipping publish")
            return False
        
        result = client.publish(topic, payload)
        if result.rc == mqtt_client.MQTT_ERR_SUCCESS:
            print(f"[MQTT] Published OK to {topic}")
            return True
        else:
            print(f"[MQTT] Publish failed, rc={result.rc}")
            return False
    except Exception as e:
        print(f"[MQTT] Publish error: {e}")
        return False


def turn_on_device(device: str, location: str):
    """Bật thiết bị - hỗ trợ cả database và hardcoded"""
    loc = location.lower()
    
    # Thử tìm trong database trước
    db_device = None
    if DB_AVAILABLE:
        db_device = get_device_from_db(device, location)
    
    if db_device:
        # Sử dụng device từ database
        dev_code = db_device.device_type  # 'light' hoặc 'fan'
        dev_name = db_device.device_name
        payload = {"device": dev_code, "location": loc, "status": "ON"}
        print(f"[DEBUG] Publishing: {payload}")
        
        if safe_publish(MQTT_TOPIC_PUB, json.dumps(payload)):
            print(f"[DEBUG] Publish successful")
        else:
            print(f"[DEBUG] Publish failed")
        
        # Update database status
        if DB_AVAILABLE:
            db = SessionLocal()
            try:
                db_device.status = "ON"
                db.commit()
            except Exception as e:
                print(f"Error updating device status: {e}")
                db.rollback()
            finally:
                db.close()
        
        # Update real_time_state for backward compatibility
        if loc not in real_time_state:
            real_time_state[loc] = {}
        real_time_state[loc][dev_name.lower()] = "ON"
        
        return f"Đã gửi lệnh bật {dev_name} tại {location}."
    else:
        # Fallback to hardcoded logic (backward compatibility)
        print(f"[DEBUG] Database device not found, using fallback for device={device}, location={loc}")
        dev = "đèn" if "đèn" in device.lower() or "light" in device.lower() else "quạt"
        
        # Tìm phòng có thiết bị này
        target_loc = loc
        if loc not in HOME_DEVICE or dev not in HOME_DEVICE[loc]:
            # Tìm phòng có thiết bị này
            for room, devices in HOME_DEVICE.items():
                if dev in devices:
                    target_loc = room
                    break
            else:
                return f"Hệ thống không tìm thấy {dev} ở {location}."
        
        dev_code = "light" if dev == "đèn" else "fan"
        payload = {"device": dev_code, "location": target_loc, "status": "ON"}
        print(f"[DEBUG] Publishing fallback: {payload}")
        
        if safe_publish(MQTT_TOPIC_PUB, json.dumps(payload)):
            print(f"[DEBUG] Publish successful")
        else:
            print(f"[DEBUG] Publish failed")
        
        real_time_state[loc][dev] = "ON"
        return f"Đã gửi lệnh bật {dev} tại {location}."

def turn_off_device(device: str, location: str):
    """Tắt thiết bị - hỗ trợ cả database và hardcoded"""
    loc = location.lower()
    
    # Thử tìm trong database trước
    db_device = None
    if DB_AVAILABLE:
        db_device = get_device_from_db(device, location)
    
    if db_device:
        # Sử dụng device từ database
        dev_code = db_device.device_type  # 'light' hoặc 'fan'
        dev_name = db_device.device_name
        payload = {"device": dev_code, "location": loc, "status": "OFF"}
        print(f"[DEBUG] Publishing: {payload}")
        
        if safe_publish(MQTT_TOPIC_PUB, json.dumps(payload)):
            print(f"[DEBUG] Publish successful")
        else:
            print(f"[DEBUG] Publish failed")
        
        # Update database status
        if DB_AVAILABLE:
            db = SessionLocal()
            try:
                db_device.status = "OFF"
                db.commit()
            except Exception as e:
                print(f"Error updating device status: {e}")
                db.rollback()
            finally:
                db.close()
        
        # Update real_time_state for backward compatibility
        if loc not in real_time_state:
            real_time_state[loc] = {}
        real_time_state[loc][dev_name.lower()] = "OFF"
        
        return f"Đã gửi lệnh tắt {dev_name} tại {location}."
    else:
        # Fallback to hardcoded logic (backward compatibility)
        print(f"[DEBUG] Database device not found, using fallback for device={device}, location={loc}")
        dev = "đèn" if "đèn" in device.lower() or "light" in device.lower() else "quạt"
        
        # Tìm phòng có thiết bị này
        target_loc = loc
        if loc not in HOME_DEVICE or dev not in HOME_DEVICE[loc]:
            # Tìm phòng có thiết bị này
            for room, devices in HOME_DEVICE.items():
                if dev in devices:
                    target_loc = room
                    break
            else:
                return f"Hệ thống không tìm thấy {dev} ở {location}."
        
        dev_code = "light" if dev == "đèn" else "fan"
        payload = {"device": dev_code, "location": target_loc, "status": "OFF"}
        print(f"[DEBUG] Publishing fallback: {payload}")
        
        if safe_publish(MQTT_TOPIC_PUB, json.dumps(payload)):
            print(f"[DEBUG] Publish successful")
        else:
            print(f"[DEBUG] Publish failed")
        
        real_time_state[loc][dev] = "OFF"
        return f"Đã gửi lệnh tắt {dev} tại {location}."


def check_status(device: str, location: str):
    """Kiểm tra trạng thái thiết bị - hỗ trợ cả database và hardcoded"""
    global real_time_state
    loc = location.lower()
    
    # Thử tìm trong database trước
    db_device = None
    if DB_AVAILABLE:
        db_device = get_device_from_db(device, location)
    
    if db_device:
        status = db_device.status
        return f"Trạng thái của {db_device.device_name} tại {location} là {status}."
    else:
        # Fallback to hardcoded logic
        dev = "đèn" if "đèn" in device.lower() or "light" in device.lower() else "quạt"
        
        if loc in real_time_state and dev in real_time_state[loc]:
            status = real_time_state[loc][dev]
            return f"Trạng thái của {dev} tại {location} là {status}."
        
        return f"Tôi không tìm thấy thông tin {dev} tại {location}."


def sync_device_status_from_mqtt():
    """Đồng bộ trạng thái thiết bị từ MQTT message vào database"""
    # Function này được gọi từ on_message callback
    pass

if __name__ == "__main__":
    time.sleep(1)
    print(check_status("đèn", "phòng khách"))   
    print(check_status("quạt", "phòng khách"))   
