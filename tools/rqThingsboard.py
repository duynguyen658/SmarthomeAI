import requests
import time
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Lấy thông tin từ environment variables hoặc dùng giá trị mặc định
TB_URL = os.getenv("TB_URL", "http://10.0.18.255:8080")
TB_USER = os.getenv("TB_USER", "")
TB_PASS = os.getenv("TB_PASS", "")
DEVICE_ID = os.getenv("DEVICE_ID", "")

tb_token = None
token_timestamp = 0
def get_tb_token():
    global tb_token, token_timestamp
    if tb_token and time.time() - token_timestamp < 3600:
        return tb_token
    url = f"{TB_URL}/api/auth/login"
    try:
        response = requests.post(url, json={"username": TB_USER, "password": TB_PASS})
        if response.status_code == 200:
            tb_token = response.json().get("token")
            token_timestamp = time.time()
            print("Lấy token ThingsBoard thành công.")
            return tb_token
        else:
            print(f"Lỗi lấy token: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Lỗi kết nối ThingsBoard: {e}")
        return None
# ====================================================
# LẤY GIÁ TRỊ MỚI NHẤT
# ====================================================
def get_sensor_data(sensor_type: str):
    token = get_tb_token()
    if not token:
        return "Không lấy được token."
    url = f"{TB_URL}/api/plugins/telemetry/DEVICE/{DEVICE_ID}/values/timeseries"
    headers = {"X-Authorization": f"Bearer {token}"}
    params = {"keys": sensor_type}
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return f"Lỗi API: {response.status_code} - {response.text}"
        data = response.json()
        if sensor_type in data:
            value = data[sensor_type][0]["value"]
            return f"Giá trị cảm biến {sensor_type}: {value}"
        else:
            return f"Không có dữ liệu cho {sensor_type}."

    except Exception as e:
        return f"Lỗi khi đọc cảm biến: {e}"
# ====================================================
# LẤY LỊCH SỬ — TRUNG BÌNH, MAX, MIN
# ====================================================
def get_history_data(sensor_type: str, hours_ago: int = 1):
    token = get_tb_token()
    if not token:
        return "Không lấy được token."
    end_ts = int(time.time() * 1000)
    start_ts = end_ts - hours_ago * 3600 * 1000

    url = f"{TB_URL}/api/plugins/telemetry/DEVICE/{DEVICE_ID}/values/timeseries"
    params = {
        "keys": sensor_type,
        "startTs": start_ts,
        "endTs": end_ts,
        "limit": 200
    }
    headers = {"X-Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return f"Lỗi API: {response.status_code} - {response.text}"
        data = response.json()
        if sensor_type not in data:
            return f"Không có dữ liệu {sensor_type}."
        # Lấy danh sách giá trị
        values = [float(x["value"]) for x in data[sensor_type]]
        if not values:
            return f"Không có dữ liệu trong {hours_ago} giờ qua."
        avg_val = sum(values) / len(values)
        max_val = max(values)
        min_val = min(values)
        return (f"Dữ liệu {sensor_type} trong {hours_ago} giờ qua:\n"
                f"- Trung bình: {avg_val:.2f}\n"
                f"- Cao nhất: {max_val}\n"
                f"- Thấp nhất: {min_val}")
    except Exception as e:
        return f"Lỗi truy xuất lịch sử: {e}"


# ============================
# KIỂM TRA (chỉ chạy khi chạy trực tiếp file này)
# ============================
if __name__ == "__main__":
    print(get_sensor_data("light"))
    print(get_history_data("light", 1))