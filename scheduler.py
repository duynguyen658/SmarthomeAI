"""
Scheduler service sử dụng APScheduler để chạy scheduled tasks
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import asyncio
from database import SessionLocal, Schedule, Device
from tools.controlDevice import turn_on_device, turn_off_device

scheduler = AsyncIOScheduler()


def get_day_of_week_number(day_name: str) -> int:
    """Convert day name to number (0=Monday, 6=Sunday)"""
    days_map = {
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
        'saturday': 5,
        'sunday': 6
    }
    return days_map.get(day_name.lower(), None)


async def execute_schedule(schedule_id: int):
    """Execute a scheduled task"""
    db = SessionLocal()
    try:
        schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
        if not schedule or not schedule.enabled:
            return
        
        device = db.query(Device).filter(Device.id == schedule.device_id).first()
        if not device:
            print(f"Schedule {schedule_id}: Device not found")
            return
        
        # Execute action
        if schedule.action.upper() == 'ON':
            result = turn_on_device(device.device_name, device.location)
        else:
            result = turn_off_device(device.device_name, device.location)
        
        print(f"Schedule '{schedule.name}' executed: {result}")
    except Exception as e:
        print(f"Error executing schedule {schedule_id}: {e}")
    finally:
        db.close()


def add_schedule_job(schedule: Schedule):
    """Thêm một schedule vào scheduler"""
    job_id = f"schedule_{schedule.id}"
    
    # Parse time (HH:MM format)
    try:
        hour, minute = map(int, schedule.time.split(':'))
    except:
        print(f"Invalid time format for schedule {schedule.id}: {schedule.time}")
        return None
    
    # Parse days
    days_list = schedule.get_days_list()
    
    if not days_list or len(days_list) == 0:
        # Chạy mỗi ngày nếu không có days specified
        trigger = CronTrigger(hour=hour, minute=minute)
    else:
        # Chạy vào các ngày cụ thể
        day_numbers = [get_day_of_week_number(day) for day in days_list if get_day_of_week_number(day) is not None]
        if not day_numbers:
            print(f"No valid days for schedule {schedule.id}")
            return None
        
        trigger = CronTrigger(day_of_week=','.join(map(str, day_numbers)), hour=hour, minute=minute)
    
    # Add job
    scheduler.add_job(
        execute_schedule,
        trigger=trigger,
        args=[schedule.id],
        id=job_id,
        replace_existing=True
    )
    
    return job_id


def remove_schedule_job(schedule_id: int):
    """Xóa schedule job khỏi scheduler"""
    job_id = f"schedule_{schedule_id}"
    try:
        scheduler.remove_job(job_id)
    except:
        pass  # Job might not exist


def update_schedule_job(schedule: Schedule):
    """Cập nhật schedule job"""
    remove_schedule_job(schedule.id)
    if schedule.enabled:
        add_schedule_job(schedule)


def load_all_schedules():
    """Load tất cả enabled schedules vào scheduler khi khởi động"""
    db = SessionLocal()
    try:
        schedules = db.query(Schedule).filter(Schedule.enabled == True).all()
        for schedule in schedules:
            add_schedule_job(schedule)
        print(f"Loaded {len(schedules)} schedules into scheduler")
    except Exception as e:
        print(f"Error loading schedules: {e}")
    finally:
        db.close()


def start_scheduler():
    """Khởi động scheduler"""
    if not scheduler.running:
        load_all_schedules()
        scheduler.start()
        print("Scheduler started")


def stop_scheduler():
    """Dừng scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        print("Scheduler stopped")

