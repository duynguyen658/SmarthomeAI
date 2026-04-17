"""
Script để tạo database smarthome trong PostgreSQL
Chạy script này TRƯỚC KHI chạy database.py
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")
DB_NAME = os.getenv("DB_NAME", "smarthome")

def create_database():
    """Tạo database nếu chưa tồn tại"""
    try:
        # Kết nối đến PostgreSQL server (không chỉ định database)
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Kiểm tra xem database đã tồn tại chưa
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(f'CREATE DATABASE {DB_NAME}')
            print(f"Database '{DB_NAME}' đã được tạo thành công!")
        else:
            print(f"Database '{DB_NAME}' đã tồn tại.")
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"Lỗi PostgreSQL: {e}")
        print("\nHãy đảm bảo:")
        print("1. PostgreSQL đang chạy")
        print("2. Username/password đúng trong .env")
        raise

if __name__ == "__main__":
    create_database()
