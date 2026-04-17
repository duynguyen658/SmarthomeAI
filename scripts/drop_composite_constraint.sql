-- Script SQL để xóa composite unique constraint từ bảng devices
-- Xóa constraint uq_device_type_location_name để chỉ kiểm tra MAC address unique
-- Chạy script này trong PostgreSQL: psql -U postgres -d smarthome -f scripts/drop_composite_constraint.sql

-- Kiểm tra và xóa constraint
ALTER TABLE devices 
DROP CONSTRAINT IF EXISTS uq_device_type_location_name;

-- Kiểm tra kết quả
SELECT constraint_name 
FROM information_schema.table_constraints 
WHERE table_name = 'devices' 
AND constraint_name = 'uq_device_type_location_name';

-- Nếu không có kết quả trả về, constraint đã được xóa thành công

