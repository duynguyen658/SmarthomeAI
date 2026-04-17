"""
Script để xóa composite unique constraint từ bảng devices
Xóa constraint uq_device_type_location_name để chỉ kiểm tra MAC address unique
"""
import sys
import os

# Thêm thư mục gốc vào path để import database
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine
from sqlalchemy import text

def drop_composite_constraint():
    """Xóa composite unique constraint uq_device_type_location_name"""
    try:
        with engine.begin() as conn:
            # Kiểm tra constraint có tồn tại không
            check_query = text("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'devices' 
                AND constraint_name = 'uq_device_type_location_name'
            """)
            result = conn.execute(check_query)
            exists = result.fetchone()
            
            if exists:
                # Xóa constraint
                drop_query = text("ALTER TABLE devices DROP CONSTRAINT IF EXISTS uq_device_type_location_name")
                conn.execute(drop_query)
                print("Đã xóa constraint 'uq_device_type_location_name' thành công!")
            else:
                print("Constraint 'uq_device_type_location_name' không tồn tại trong database.")
        
        return True
    except Exception as e:
        print(f"Lỗi: {e}")
        print("\nVui lòng kiểm tra:")
        print("1. PostgreSQL đã được cài đặt và đang chạy")
        print("2. Thông tin kết nối trong file .env đúng")
        print("3. Database đã được tạo")
        return False

if __name__ == "__main__":
    print("Đang xóa composite unique constraint...")
    print("Constraint: uq_device_type_location_name\n")
    
    if drop_composite_constraint():
        print("\nHoàn tất! Bây giờ bạn có thể tạo nhiều thiết bị cùng tên/loại/vị trí.")
        print("Chỉ MAC address cần phải unique.")
    else:
        print("\nKhông thể xóa constraint. Vui lòng kiểm tra lại cấu hình.")
