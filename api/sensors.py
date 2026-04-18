"""
Sensors API - Get sensor data from MQTT/Redis
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import os

router = APIRouter()

# Try to connect to Redis for sensor data
redis_client = None
try:
    import redis
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.ping()
except Exception:
    redis_client = None


class SensorData(BaseModel):
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    gas: Optional[float] = None
    light: Optional[float] = None
    source: str = "mock"


@router.get("/sensors", response_model=SensorData)
async def get_sensors():
    """
    Get current sensor readings.
    Tries to read from Redis first, falls back to mock data.
    """
    sensor_data = {
        "temperature": None,
        "humidity": None,
        "gas": None,
        "light": None,
        "source": "mock"
    }
    
    redis_keys_found = []
    redis_data_found = False
    
    # Try to get from Redis
    if redis_client:
        try:
            # Try various sensor keys
            for key in ["sensor/temperature", "sensors/temperature", "temperature", 
                       "sensor/humidity", "sensors/humidity", "humidity",
                       "sensor/gas", "sensors/gas", "mq2/gas", "gas",
                       "sensor/light", "sensors/light", "light"]:
                value = redis_client.get(key)
                if value:
                    redis_keys_found.append(f"{key}={value}")
                    redis_data_found = True
                    try:
                        data = json.loads(value)
                        if "temperature" in key:
                            sensor_data["temperature"] = float(data.get("value", data))
                        elif "humidity" in key:
                            sensor_data["humidity"] = float(data.get("value", data))
                        elif "gas" in key or "mq2" in key:
                            sensor_data["gas"] = float(data.get("value", data))
                        elif "light" in key:
                            sensor_data["light"] = float(data.get("value", data))
                    except (json.JSONDecodeError, ValueError, TypeError):
                        try:
                            val = float(value)
                            if "temperature" in key:
                                sensor_data["temperature"] = val
                            elif "humidity" in key:
                                sensor_data["humidity"] = val
                            elif "gas" in key or "mq2" in key:
                                sensor_data["gas"] = val
                            elif "light" in key:
                                sensor_data["light"] = val
                        except ValueError:
                            pass
            sensor_data["source"] = "redis"
            print(f"[SensorAPI] Redis keys found: {redis_keys_found}")
        except Exception as e:
            print(f"Redis error: {e}")
    else:
        print("[SensorAPI] Redis client not available!")
    
    # If no data from Redis, try MQTT topic cache
    if not redis_data_found:
        print("[SensorAPI] No data from Redis, using mock data")
        # Return realistic mock data for demo
        import random
        sensor_data = {
            "temperature": round(25 + random.uniform(0, 10), 1),
            "humidity": round(60 + random.uniform(0, 25), 1),
            "gas": round(random.uniform(100, 400), 0),
            "light": round(random.uniform(0, 100), 0),
            "source": "mock"
        }
    
    print(f"[SensorAPI] Returning: temp={sensor_data['temperature']}, humi={sensor_data['humidity']}, gas={sensor_data['gas']}")
    return sensor_data


@router.get("/sensors/{sensor_type}")
async def get_sensor(sensor_type: str):
    """Get specific sensor reading"""
    sensors = await get_sensors()
    
    if sensor_type == "temperature":
        return {"type": "temperature", "value": sensors.temperature}
    elif sensor_type == "humidity":
        return {"type": "humidity", "value": sensors.humidity}
    elif sensor_type == "gas" or sensor_type == "mq2":
        return {"type": "gas", "value": sensors.gas}
    elif sensor_type == "light":
        return {"type": "light", "value": sensors.light}
    else:
        raise HTTPException(status_code=404, detail=f"Sensor '{sensor_type}' not found")
