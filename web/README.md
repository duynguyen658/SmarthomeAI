# Smart Home Web Interface

Giao diện web hiện đại thay thế Streamlit cho hệ thống Smart Home AI.

## Tính Năng

- 🎨 **Giao diện hiện đại**: Thiết kế đẹp, responsive, hỗ trợ dark/light theme
- 💬 **Chat AI**: Tương tác với AI assistant qua giao diện chat
- 📊 **Dashboard**: Hiển thị metrics và trạng thái thiết bị
- 🎛️ **Điều khiển thiết bị**: Bật/tắt thiết bị trực tiếp từ giao diện
- ⚙️ **Cài đặt**: Tùy chỉnh API URL, User ID, Session ID

## Cách Sử Dụng

1. **Khởi động Backend**:
   ```bash
   python main.py
   ```

2. **Mở trình duyệt**:
   - Truy cập: `http://localhost:8000`
   - Giao diện sẽ tự động load

3. **Các chức năng**:
   - **Dashboard**: Xem tổng quan hệ thống
   - **AI Chat**: Trò chuyện với AI assistant
   - **Thiết Bị**: Điều khiển thiết bị trực tiếp
   - **Cài Đặt**: Cấu hình hệ thống

## Cấu Trúc File

```
web/
├── index.html    # Giao diện chính
├── styles.css    # Styling
└── app.js        # JavaScript logic
```

## Tùy Chỉnh

### Thay đổi Theme
- Click vào nút 🌙/☀️ ở sidebar
- Hoặc vào Settings > Chế Độ

### Thay đổi API URL
- Vào Settings
- Sửa API Server URL
- Click "Lưu Cài Đặt"

## Lưu ý

- Giao diện tự động lưu cài đặt vào localStorage
- Server status được kiểm tra mỗi 5 giây
- Hỗ trợ responsive trên mobile

