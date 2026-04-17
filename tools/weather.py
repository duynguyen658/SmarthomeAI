import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Lấy API key từ environment variable
weather_api_key = os.getenv("WEATHER_API_KEY", "")

def get_weather(city: str) -> str:
    """Lấy thông tin thời tiết cho một thành phố cụ thể."""
    if not weather_api_key:
        return "Lỗi: Chưa cấu hình WEATHER_API_KEY trong file .env"
    
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": weather_api_key,
        "units": "metric",
        "lang": "vi"
    }
    try:
        response = requests.get(base_url, params=params)
        data = response.json()
        if data["cod"] != 200:
            return f"Lỗi: {data.get('message', 'Không thể lấy dữ liệu thời tiết.')}"
        weather_desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]
        weather_info = (f"Thời tiết ở {city}:\n"
                        f"Mô tả: {weather_desc}\n"
                        f"Nhiệt độ: {temp}°C\n"
                        f"Độ ẩm: {humidity}%\n"
                        f"Tốc độ gió: {wind_speed} m/s")
        return weather_info
    except Exception as e:
        return f"Lỗi khi lấy dữ liệu thời tiết: {e}"

# Test code (chỉ chạy khi chạy trực tiếp file này)
if __name__ == "__main__":
    print(get_weather("Hanoi"))