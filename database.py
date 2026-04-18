"""
Database setup và models cho Smart Home system
Sử dụng PostgreSQL với SQLAlchemy ORM
"""
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

# PostgreSQL connection string từ environment variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "smarthome")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")

# Tạo connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Tạo engine với pool settings
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,  # Kiểm tra connection trước khi dùng
    pool_size=5,
    max_overflow=10
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Device(Base):
    """Model cho thiết bị"""
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)  # SERIAL trong PostgreSQL
    device_uid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    device_name = Column(String(100), nullable=False)
    device_type = Column(String(50), nullable=False)  # 'light', 'fan', 'sensor', etc.
    location = Column(String(50), nullable=False)
    mac_address = Column(String(50), unique=True, nullable=True, index=True)
    mqtt_topic = Column(String, nullable=True)
    status = Column(String, default="OFF")  # 'ON', 'OFF'
    icon = Column(String, nullable=True)  # Icon name
    capabilities = Column(JSONB, nullable=True, default=list)  # ['on_off', 'dimming', 'color']
    device_metadata = Column(JSONB, nullable=True, default=dict)  # manufacturer, model, firmware
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    schedules = relationship("Schedule", back_populates="device", cascade="all, delete-orphan")
    state = relationship("DeviceState", back_populates="device", uselist=False, cascade="all, delete-orphan")


class DeviceState(Base):
    """Model cho trạng thái thiết bị (Redis-backed nhưng cũng persist vào DB)"""
    __tablename__ = "device_states"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, unique=True)
    state = Column(String(32), nullable=False, default="offline")  # online, offline, on, off, error
    attributes = Column(JSONB, nullable=True, default=dict)  # brightness, color, temperature, etc.
    last_seen = Column(DateTime, nullable=True)
    last_command = Column(DateTime, nullable=True)
    version = Column(Integer, default=1)  # Optimistic locking
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    device = relationship("Device", back_populates="state")


class Schedule(Base):
    """Model cho lịch tự động"""
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    action = Column(String, nullable=False)  # 'ON' or 'OFF'
    time = Column(String, nullable=False)  # HH:MM format
    days = Column(Text, nullable=True)  # JSON array: ["monday", "tuesday", ...]
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    device = relationship("Device", back_populates="schedules")
    
    def get_days_list(self):
        """Convert days JSON string to list"""
        if self.days:
            try:
                return json.loads(self.days)
            except:
                return []
        return []
    
    def set_days_list(self, days_list):
        """Convert days list to JSON string"""
        self.days = json.dumps(days_list) if days_list else None


class AlertRule(Base):
    """Model cho quy tắc cảnh báo"""
    __tablename__ = "alert_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    sensor_type = Column(String, nullable=False)  # 'temperature', 'humidity', 'gas', 'light'
    condition = Column(String, nullable=False)  # 'gt', 'lt', 'eq', 'between'
    threshold_value = Column(Float, nullable=True)
    threshold_max = Column(Float, nullable=True)  # For 'between' condition
    enabled = Column(Boolean, default=True)
    notification_type = Column(String, default="browser")  # 'browser', 'email', 'sms'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    notifications = relationship("Notification", back_populates="alert_rule", cascade="all, delete-orphan")


class Notification(Base):
    """Model cho notifications"""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=True)
    message = Column(String, nullable=False)
    severity = Column(String, default="info")  # 'info', 'warning', 'critical'
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    alert_rule = relationship("AlertRule", back_populates="notifications")


def init_db():
    """Khởi tạo database và tạo tables"""
    try:
        Base.metadata.create_all(bind=engine)
        print(f"Database initialized: PostgreSQL at {DB_HOST}:{DB_PORT}/{DB_NAME}")
    except Exception as e:
        print(f"Error initializing database: {e}")
        print("Please ensure PostgreSQL is running and credentials are correct in .env file")
        raise


def get_db():
    """Dependency để lấy database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_from_hardcoded():
    """Migrate devices từ hardcoded dict sang database"""
    from tools.controlDevice import HOME_DEVICE
    
    db = SessionLocal()
    try:
        # Xóa tất cả devices cũ
        db.query(Device).delete()
        
        # Migrate từ HOME_DEVICE
        device_icons = {
            "đèn": "",
            "quạt": "",
            "light": "",
            "fan": ""
        }
        
        for location, devices in HOME_DEVICE.items():
            for device_name in devices:
                device_type = "light" if "đèn" in device_name.lower() or "light" in device_name.lower() else "fan"
                icon = device_icons.get(device_name.lower(), "")
                
                device = Device(
                    device_name=device_name,
                    device_type=device_type,
                    location=location,
                    status="OFF",
                    icon=icon
                )
                db.add(device)
        
        db.commit()
        print(f"Migrated {len(HOME_DEVICE)} locations with devices to database")
    except Exception as e:
        db.rollback()
        print(f"Error during migration: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    # Initialize database
    init_db()
    # Migrate existing devices
    migrate_from_hardcoded()
    print("Database setup complete!")

