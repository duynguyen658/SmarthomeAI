// Configuration
const CONFIG = {
    apiUrl: localStorage.getItem('apiUrl') || 'http://localhost:8000/api/chat',
    userId: localStorage.getItem('userId') || 'admin_user',
    sessionId: localStorage.getItem('sessionId') || 'session_web_01'
};

// State
let currentSection = 'dashboard';
let isServerOnline = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeTheme();
    initializeNavigation();
    initializeChat();
    initializeControls();
    initializeSettings();
    checkServerStatus();
    setInterval(checkServerStatus, 5000); // Check every 5 seconds
});

// Theme Management
function initializeTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeToggle(savedTheme);

    document.getElementById('themeToggle').addEventListener('click', toggleTheme);
    document.getElementById('themeSelect').value = savedTheme;
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeToggle(newTheme);
    document.getElementById('themeSelect').value = newTheme;
}

function updateThemeToggle(theme) {
    const toggle = document.getElementById('themeToggle');
    toggle.innerHTML = theme === 'dark' ? '<span></span>' : '<span></span>';
}

// Navigation
function initializeNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const section = item.getAttribute('data-section');
            switchSection(section);
        });
    });
}

function switchSection(section) {
    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-section') === section) {
            item.classList.add('active');
        }
    });

    // Update content
    document.querySelectorAll('.content-section').forEach(sec => {
        sec.classList.remove('active');
    });
    document.getElementById(section).classList.add('active');
    currentSection = section;
    
    // Initialize section-specific features
    if (section === 'device-management' && typeof initializeDeviceManagement === 'function') {
        initializeDeviceManagement();
    }
    if (section === 'edit-device') {
        // Load device data if editing
        // Cần đảm bảo devices đã được load
        if (typeof initializeDeviceManagement === 'function') {
            initializeDeviceManagement();
        }
        
        // Đợi một chút để devices được load
        setTimeout(() => {
            if (typeof editingDeviceId !== 'undefined' && editingDeviceId && typeof devices !== 'undefined' && devices && devices.length > 0) {
                const device = devices.find(d => d.id === editingDeviceId);
                if (device) {
                    // Fill form edit
                    document.getElementById('editDeviceId').value = device.id;
                    document.getElementById('editDeviceName').value = device.device_name;
                    document.getElementById('editDeviceType').value = device.device_type;
                    document.getElementById('editDeviceLocation').value = device.location;
                    document.getElementById('editDeviceMacAddress').value = device.mac_address || '';
                    document.getElementById('editDeviceMqttTopic').value = device.mqtt_topic || '';
                } else {
                    // Không tìm thấy thiết bị, quay lại trang quản lý
                    alert('Vui lòng chọn thiết bị từ trang Quản Lý Thiết Bị để chỉnh sửa');
                    switchSection('device-management');
                }
            } else {
                // Chưa có thiết bị nào được chọn, quay lại trang quản lý
                alert('Vui lòng chọn thiết bị từ trang Quản Lý Thiết Bị để chỉnh sửa');
                switchSection('device-management');
            }
        }, 100);
    }
    if (section === 'automation' && typeof initializeAutomation === 'function') {
        initializeAutomation();
    }
    if (section === 'alerts' && typeof initializeAlerts === 'function') {
        initializeAlerts();
    }
}

// Server Status
async function checkServerStatus() {
    try {
        const response = await fetch(CONFIG.apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: 'ping', user_id: CONFIG.userId, session_id: CONFIG.sessionId })
        });
        
        isServerOnline = response.ok;
    } catch (error) {
        isServerOnline = false;
    }

    updateServerStatus();
}

function updateServerStatus() {
    const statusDot = document.getElementById('serverStatus');
    const statusText = document.getElementById('serverStatusText');
    
    if (isServerOnline) {
        statusDot.classList.add('online');
        statusText.textContent = 'Đang hoạt động';
    } else {
        statusDot.classList.remove('online');
        statusText.textContent = 'Mất kết nối';
    }
}

// Chat
function initializeChat() {
    const chatInput = document.getElementById('chatInput');
    const sendButton = document.getElementById('sendButton');
    const quickButtons = document.querySelectorAll('.quick-btn');

    // Send on Enter
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Send button
    sendButton.addEventListener('click', sendMessage);

    // Quick actions
    quickButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const query = btn.getAttribute('data-query');
            chatInput.value = query;
            sendMessage();
        });
    });
}

async function sendMessage() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();

    if (!message) return;

    // Add user message
    addMessage('user', message);
    input.value = '';

    // Show typing indicator
    const typingId = addTypingIndicator();

    try {
        const response = await fetch(CONFIG.apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: message,
                user_id: CONFIG.userId,
                session_id: CONFIG.sessionId
            })
        });

        const data = await response.json();
        removeTypingIndicator(typingId);
        
        if (response.ok) {
            addMessage('assistant', data.response);
        } else {
            addMessage('assistant', 'Xin lỗi, có lỗi xảy ra khi xử lý yêu cầu.');
        }
    } catch (error) {
        removeTypingIndicator(typingId);
        addMessage('assistant', 'Không thể kết nối đến server. Vui lòng kiểm tra lại.');
        console.error('Error:', error);
    }
}

function addMessage(role, text) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const avatar = role === 'user' ? '👤' : '🤖';
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <p>${escapeHtml(text)}</p>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function addTypingIndicator() {
    const messagesContainer = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    const id = 'typing-' + Date.now();
    typingDiv.id = id;
    typingDiv.className = 'message assistant';
    typingDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <p>Đang suy nghĩ...</p>
        </div>
    `;
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    return id;
}

function removeTypingIndicator(id) {
    const typingDiv = document.getElementById(id);
    if (typingDiv) {
        typingDiv.remove();
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Device Controls
function initializeControls() {
    const controlButtons = document.querySelectorAll('.control-btn');
    
    controlButtons.forEach(btn => {
        btn.addEventListener('click', async () => {
            const device = btn.getAttribute('data-device');
            const location = btn.getAttribute('data-location');
            const action = btn.getAttribute('data-action');
            
            const command = action === 'on' 
                ? `Bật ${device} ${location}`
                : `Tắt ${device} ${location}`;
            
            // Update UI immediately
            updateDeviceStatus(device, location, action === 'on' ? 'ON' : 'OFF');
            
            // Send command to AI
            try {
                const response = await fetch(CONFIG.apiUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: command,
                        user_id: CONFIG.userId,
                        session_id: CONFIG.sessionId
                    })
                });
                
                const data = await response.json();
                console.log('Control response:', data);
            } catch (error) {
                console.error('Control error:', error);
            }
        });
    });
}

function updateDeviceStatus(device, location, status) {
    const deviceType = device === 'đèn' ? 'light' : 'fan';
    const statusElement = document.getElementById(`${deviceType}Status`);
    const controlStatusElement = document.getElementById(`${deviceType}ControlStatus`);
    
    if (statusElement) {
        const badge = statusElement.querySelector('.status-badge');
        badge.textContent = status;
        badge.className = `status-badge ${status.toLowerCase()}`;
    }
    
    if (controlStatusElement) {
        controlStatusElement.textContent = status;
    }
}

// Settings
function initializeSettings() {
    // Load saved settings
    document.getElementById('apiUrl').value = CONFIG.apiUrl;
    document.getElementById('userId').value = CONFIG.userId;
    document.getElementById('sessionId').value = CONFIG.sessionId;
    
    // Save settings
    document.getElementById('saveSettings').addEventListener('click', () => {
        CONFIG.apiUrl = document.getElementById('apiUrl').value;
        CONFIG.userId = document.getElementById('userId').value;
        CONFIG.sessionId = document.getElementById('sessionId').value;
        
        localStorage.setItem('apiUrl', CONFIG.apiUrl);
        localStorage.setItem('userId', CONFIG.userId);
        localStorage.setItem('sessionId', CONFIG.sessionId);
        
        alert('Đã lưu cài đặt!');
    });
    
    // Reset settings
    document.getElementById('resetSettings').addEventListener('click', () => {
        if (confirm('Bạn có chắc muốn đặt lại cài đặt?')) {
            localStorage.clear();
            location.reload();
        }
    });
    
    // Theme select
    document.getElementById('themeSelect').addEventListener('change', (e) => {
        const theme = e.target.value;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        updateThemeToggle(theme);
    });
}

// Metrics Update (placeholder - can be connected to real sensor data)
function updateMetrics(data) {
    if (data.temperature) {
        document.getElementById('temperature').textContent = `${data.temperature}°C`;
    }
    if (data.humidity) {
        document.getElementById('humidity').textContent = `${data.humidity}%`;
    }
    if (data.light) {
        document.getElementById('light').textContent = data.light;
    }
    if (data.gas) {
        document.getElementById('gas').textContent = data.gas;
    }
}

