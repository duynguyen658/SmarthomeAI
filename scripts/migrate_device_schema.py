"""
Script migration để chuyển đổi schema devices từ cũ sang mới
Chạy script này một lần sau khi cập nhật database.py
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "smarthome")
DB_USER = os.getenv("DB_USER", "iot_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "iot_password")

def migrate_device_schema():
    """Migrate devices table từ schema cũ sang mới"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Kiểm tra xem đã có cột device_uid chưa
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='devices' AND column_name='device_uid'
        """)
        
        if cursor.fetchone():
            print("Schema đã được migrate rồi. Không cần migrate lại.")
            cursor.close()
            conn.close()
            return
        
        print("Bắt đầu migration...")
        
        # 1. Thêm các cột mới
        print("1. Thêm các cột mới...")
        cursor.execute("""
            ALTER TABLE devices 
            ADD COLUMN IF NOT EXISTS device_uid UUID DEFAULT gen_random_uuid(),
            ADD COLUMN IF NOT EXISTS device_name VARCHAR(100),
            ADD COLUMN IF NOT EXISTS device_type VARCHAR(50),
            ADD COLUMN IF NOT EXISTS mac_address VARCHAR(50);
        """)
        
        # 2. Copy dữ liệu từ cột cũ sang cột mới
        print("2. Copy dữ liệu từ cột cũ sang cột mới...")
        cursor.execute("""
            UPDATE devices 
            SET device_name = name,
                device_type = type
            WHERE device_name IS NULL OR device_type IS NULL;
        """)
        
        # 3. Tạo unique constraint cho mac_address
        print("3. Tạo unique constraint cho mac_address...")
        try:
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_mac_address 
                ON devices(mac_address) 
                WHERE mac_address IS NOT NULL;
            """)
        except Exception as e:
            print(f"   Lưu ý: {e}")
        
        # 4. Tạo composite unique constraint
        print("4. Tạo composite unique constraint...")
        try:
            cursor.execute("""
                ALTER TABLE devices 
                ADD CONSTRAINT uq_device_type_location_name 
                UNIQUE (device_type, location, device_name);
            """)
        except Exception as e:
            print(f"   Lưu ý: {e}")
        
        # 5. Tạo index cho device_uid
        print("5. Tạo index cho device_uid...")
        try:
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_devices_device_uid 
                ON devices(device_uid);
            """)
        except Exception as e:
            print(f"   Lưu ý: {e}")
        
        # 6. Đảm bảo device_uid không null
        print("6. Đảm bảo device_uid không null...")
        cursor.execute("""
            UPDATE devices 
            SET device_uid = gen_random_uuid() 
            WHERE device_uid IS NULL;
        """)
        
        cursor.execute("""
            ALTER TABLE devices 
            ALTER COLUMN device_uid SET NOT NULL,
            ALTER COLUMN device_name SET NOT NULL,
            ALTER COLUMN device_type SET NOT NULL;
        """)
        
        print("Migration hoàn tất!")
        print("\nLưu ý: Các cột cũ (name, type) vẫn còn trong database.")
        print("Bạn có thể xóa chúng sau khi đã xác nhận mọi thứ hoạt động tốt:")
        print("  ALTER TABLE devices DROP COLUMN name;")
        print("  ALTER TABLE devices DROP COLUMN type;")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Lỗi migration: {e}")
        print("\nVui lòng kiểm tra:")
        print("1. PostgreSQL đã được cài đặt và đang chạy")
        print("2. Thông tin kết nối trong file .env đúng")
        print("3. Database đã được tạo")

if __name__ == "__main__":
    print("Đang migrate schema devices...")
    print(f"Host: {DB_HOST}:{DB_PORT}")
    print(f"Database: {DB_NAME}")
    print(f"User: {DB_USER}\n")
    
    migrate_device_schema()

