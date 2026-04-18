// ===================================
// Smart Home AI - Main Application
// ===================================

// Configuration
const CONFIG = {
    apiUrl: localStorage.getItem('apiUrl') || 'http://localhost:8000/api/chat',
    userId: localStorage.getItem('userId') || 'admin_user',
    sessionId: localStorage.getItem('sessionId') || 'session_web_' + Date.now()
};

// State
let currentSection = 'dashboard';
let isServerOnline = false;
let isRecording = false;
let recognition = null;
let synthesis = window.speechSynthesis;

// ===================================
// Initialize
// ===================================
document.addEventListener('DOMContentLoaded', () => {
    initializeTheme();
    initializeNavigation();
    initializeChat();
    initializeControls();
    initializeVoice();
    checkServerStatus();
    updateClock();
    loadDashboardDevices();
    
    // Update time every second
    setInterval(updateClock, 1000);
    
    // Check server status every 10 seconds
    setInterval(checkServerStatus, 10000);
    
    // Fetch sensor data every 30 seconds
    setInterval(fetchSensorData, 30000);
});

// ===================================
// Theme Management
// ===================================
function initializeTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    const themeIcon = document.querySelector('.theme-toggle i');
    themeIcon.className = savedTheme === 'dark' ? 'ri-moon-line' : 'ri-sun-line';
    
    document.getElementById('themeToggle').addEventListener('click', toggleTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    const themeIcon = document.querySelector('.theme-toggle i');
    themeIcon.className = newTheme === 'dark' ? 'ri-moon-line' : 'ri-sun-line';
}

function updateClock() {
    const now = new Date();
    const options = { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    };
    document.getElementById('currentTime').textContent = now.toLocaleDateString('vi-VN', options);
}

// ===================================
// Navigation
// ===================================
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
    if (section === 'devices') {
        loadControlPanel();
    }
    if (section === 'automation' && typeof initializeAutomation === 'function') {
        initializeAutomation();
    }
    if (section === 'alerts' && typeof initializeAlerts === 'function') {
        initializeAlerts();
    }
}

// ===================================
// Server Status
// ===================================
async function checkServerStatus() {
    try {
        const response = await fetch(CONFIG.apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                query: 'ping', 
                user_id: CONFIG.userId, 
                session_id: CONFIG.sessionId 
            })
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
        statusText.textContent = 'Online';
    } else {
        statusDot.classList.remove('online');
        statusText.textContent = 'Offline';
    }
}

// ===================================
// Voice Control (Speech Recognition)
// ===================================
async function checkMicrophonePermission() {
    try {
        const result = await navigator.permissions.query({ name: 'microphone' });
        console.log('Microphone permission:', result.state);
        return result.state === 'granted';
    } catch (e) {
        console.log('Permission query not supported, trying getUserMedia');
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach(track => track.stop());
            return true;
        } catch (e2) {
            return false;
        }
    }
}

async function initializeVoice() {
    // Check browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    console.log('Browser:', navigator.userAgent);
    console.log('SpeechRecognition API:', SpeechRecognition ? 'Available' : 'Not available');
    
    if (!SpeechRecognition) {
        showToast('error', 'Trình duyệt không hỗ trợ nhận dạng giọng nói. Dùng Chrome/Edge để có kết quả tốt nhất.');
        document.getElementById('voiceBtn').style.display = 'none';
        return;
    }
    
    // Check microphone permission
    const hasPermission = await checkMicrophonePermission();
    console.log('Has microphone permission:', hasPermission);
    
    if (!hasPermission) {
        showToast('warning', 'Cần cấp quyền microphone. Click vào biểu tượng 🔒 trên thanh URL và cho phép Microphone.');
        // Still show the button but will show permission error when clicked
    }
    
    recognition = new SpeechRecognition();
    recognition.lang = 'vi-VN';
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    
    recognition.onstart = () => {
        isRecording = true;
        updateVoiceUI(true);
        showToast('info', 'Đang nghe... Nói lệnh của bạn');
    };
    
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        document.getElementById('chatInput').value = transcript;
        sendMessage();
    };
    
    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        isRecording = false;
        updateVoiceUI(false);
        
        switch(event.error) {
            case 'no-speech':
                showToast('warning', 'Không nhận được giọng nói. Hãy nói to và rõ hơn.');
                break;
            case 'not-allowed':
            case 'permission-denied':
                showToast('error', 'Không có quyền microphone. Vào chrome://settings/siteData tìm localhost và xóa, sau đó refresh lại trang.');
                break;
            case 'network':
                showToast('error', 'Lỗi mạng. Kiểm tra kết nối internet.');
                break;
            case 'audio-capture':
                showToast('error', 'Không tìm thấy microphone.');
                break;
            default:
                showToast('error', 'Lỗi nhận dạng giọng nói: ' + event.error);
        }
    };
    
    recognition.onend = () => {
        isRecording = false;
        updateVoiceUI(false);
    };
    
    // Request permission on init
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            stream.getTracks().forEach(track => track.stop());
            console.log('Microphone access granted');
        })
        .catch(err => {
            console.log('Microphone access denied:', err);
        });
}

async function toggleVoice() {
    if (!recognition) {
        showToast('error', 'Trình duyệt không hỗ trợ nhận dạng giọng nói. Dùng Chrome/Edge nhé!');
        return;
    }
    
    if (isRecording) {
        recognition.stop();
    } else {
        try {
            // First check permission
            const hasPermission = await checkMicrophonePermission();
            if (!hasPermission) {
                showToast('error', 'Cần cấp quyền microphone! Click 🔒 trên URL bar và cho phép Microphone.');
                return;
            }
            recognition.start();
        } catch (e) {
            console.error('Recognition start error:', e);
            if (e.name === 'NotAllowedError') {
                showToast('error', 'Không có quyền microphone. Refresh trang và cho phép Microphone!');
            } else {
                showToast('error', 'Lỗi: ' + e.message);
            }
        }
    }
}

function updateVoiceUI(recording) {
    const voiceBtn = document.getElementById('voiceBtn');
    const voiceIcon = document.getElementById('voiceIcon');
    const voiceLabel = document.getElementById('voiceLabel');
    
    if (recording) {
        voiceBtn.classList.add('recording');
        voiceIcon.className = 'ri-mic-fill';
        voiceLabel.textContent = 'Dừng';
    } else {
        voiceBtn.classList.remove('recording');
        voiceIcon.className = 'ri-mic-line';
        voiceLabel.textContent = 'Giọng nói';
    }
}

// ===================================
// Text to Speech (Response)
// ===================================
function speakText(text) {
    if (!synthesis) return;
    
    // Cancel any ongoing speech
    synthesis.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'vi-VN';
    utterance.rate = 1;
    utterance.pitch = 1;
    
    // Try to find Vietnamese voice
    const voices = synthesis.getVoices();
    const vnVoice = voices.find(v => v.lang.includes('vi'));
    if (vnVoice) {
        utterance.voice = vnVoice;
    }
    
    synthesis.speak(utterance);
}

// ===================================
// Chat
// ===================================
function initializeChat() {
    const chatInput = document.getElementById('chatInput');
    const sendButton = document.getElementById('sendButton');
    const quickButtons = document.querySelectorAll('.quick-cmd');

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
    
    // Load voices
    if (synthesis) {
        synthesis.onvoiceschanged = () => {
            synthesis.getVoices();
        };
    }
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
            // Speak the response
            speakText(data.response);
            // Refresh device status after command
            setTimeout(() => {
                loadDashboardDevices();
                loadControlPanel();
            }, 500);
        } else if (response.status === 429) {
            removeTypingIndicator(typingId);
            addMessage('assistant', 'Quota API Gemini đã hết hôm nay. Vui lòng thử lại vào ngày mai hoặc cập nhật API key mới.');
            showToast('error', 'Đã hết quota API Gemini!', 5000);
        } else if (response.status === 503) {
            removeTypingIndicator(typingId);
            addMessage('assistant', 'Gemini API đang bận. Vui lòng thử lại sau vài phút.');
            showToast('warning', 'Gemini API đang quá tải, thử lại sau!', 5000);
        } else {
            removeTypingIndicator(typingId);
            addMessage('assistant', `Xin lỗi, có lỗi xảy ra: ${data.detail || 'Không xác định'}`);
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
    
    const avatarIcon = role === 'user' ? 'ri-user-line' : 'ri-robot-line';
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="${avatarIcon}"></i>
        </div>
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
        <div class="message-avatar">
            <i class="ri-robot-line"></i>
        </div>
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

// ===================================
// Dashboard
// ===================================
function loadDashboardDevices() {
    fetch('/api/devices')
        .then(res => res.json())
        .then(devices => {
            const container = document.getElementById('dashboardDevices');
            const activeCount = devices.filter(d => d.status === 'ON').length;
            
            document.getElementById('activeDevices').textContent = activeCount;
            document.getElementById('totalDevices').textContent = devices.length;
            
            if (devices.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="ri-robot-line"></i>
                        <p>Chưa có thiết bị nào. Hãy thêm thiết bị mới!</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = devices.map(device => {
                const icon = getDeviceIcon(device.device_type);
                const isOn = device.status === 'ON';
                return `
                    <div class="device-card ${isOn ? 'active' : ''}">
                        <div class="device-icon">${icon}</div>
                        <div class="device-info">
                            <h4>${device.device_name}</h4>
                            <p>${device.location}</p>
                        </div>
                        <div class="device-toggle" onclick="toggleDashboardDevice(${device.id}, '${device.status}')">
                            <i class="ri-power-line"></i>
                        </div>
                    </div>
                `;
            }).join('');
        })
        .catch(err => {
            console.error('Error loading devices:', err);
            document.getElementById('dashboardDevices').innerHTML = `
                <div class="error-state">
                    <p>Không thể tải thiết bị</p>
                </div>
            `;
        });
}

function getDeviceIcon(type) {
    const icons = {
        'light': '<i class="ri-lightbulb-line"></i>',
        'fan': '<i class="ri-windy-line"></i>',
        'sensor': '<i class="ri-dashboard-line"></i>',
        'switch': '<i class="ri-toggle-line"></i>',
        'ac': '<i class="ri-snowy-line"></i>'
    };
    return icons[type] || '<i class="ri-device-line"></i>';
}

function toggleDashboardDevice(deviceId, currentStatus) {
    const newStatus = currentStatus === 'ON' ? 'OFF' : 'ON';
    controlDevice(deviceId, newStatus);
}

// ===================================
// Control Panel
// ===================================
function loadControlPanel() {
    fetch('/api/devices')
        .then(res => res.json())
        .then(devices => {
            const container = document.getElementById('controlPanel');
            
            if (devices.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="ri-robot-line"></i>
                        <p>Chưa có thiết bị nào. Hãy thêm thiết bị mới!</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = devices.map(device => {
                const isLight = device.device_type === 'light';
                const iconClass = isLight ? 'light' : 'fan';
                const icon = isLight ? 'ri-lightbulb-line' : 'ri-windy-line';
                const isOn = device.status === 'ON';
                
                return `
                    <div class="control-card">
                        <div class="control-header">
                            <div class="control-icon ${iconClass}">
                                <i class="${icon}"></i>
                            </div>
                            <div>
                                <h3>${device.device_name}</h3>
                                <span>${device.location}</span>
                            </div>
                        </div>
                        <div class="control-actions">
                            <button class="control-btn on ${isOn ? 'active' : ''}" 
                                    onclick="controlDevice(${device.id}, 'ON')">
                                BẬT
                            </button>
                            <button class="control-btn off ${!isOn ? 'active' : ''}" 
                                    onclick="controlDevice(${device.id}, 'OFF')">
                                TẮT
                            </button>
                        </div>
                        <div class="control-status">
                            Trạng thái: <strong>${device.status}</strong>
                        </div>
                    </div>
                `;
            }).join('');
        })
        .catch(err => {
            console.error('Error loading control panel:', err);
        });
}

async function controlDevice(deviceId, action) {
    try {
        const response = await fetch(`/api/devices/${deviceId}/control`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action })
        });
        
        if (response.ok) {
            showToast('success', `Đã ${action === 'ON' ? 'bật' : 'tắt'} thiết bị`);
            loadDashboardDevices();
            loadControlPanel();
        } else {
            showToast('error', 'Không thể điều khiển thiết bị');
        }
    } catch (error) {
        console.error('Control error:', error);
        showToast('error', 'Lỗi kết nối');
    }
}

// ===================================
// Quick Control
// ===================================
async function quickControl(deviceType, location, action) {
    try {
        const response = await fetch(CONFIG.apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: `${action === 'on' ? 'Bật' : 'Tắt'} ${deviceType}${location !== 'all' ? ' ' + location : ''}`,
                user_id: CONFIG.userId,
                session_id: CONFIG.sessionId
            })
        });
        
        if (response.ok) {
            showToast('success', `Đã gửi lệnh ${action === 'on' ? 'bật' : 'tắt'} ${deviceType}`);
            setTimeout(() => {
                loadDashboardDevices();
                loadControlPanel();
            }, 500);
        }
    } catch (error) {
        console.error('Quick control error:', error);
        showToast('error', 'Lỗi kết nối');
    }
}

// ===================================
// Sensor Data
// ===================================
async function fetchSensorData() {
    // Try to get sensor data from API
    try {
        const response = await fetch('/api/sensors');
        if (response.ok) {
            const data = await response.json();
            updateSensorDisplay(data);
        }
    } catch (error) {
        // Use mock data for demo
        updateSensorDisplay({
            temperature: (25 + Math.random() * 10).toFixed(1),
            humidity: (60 + Math.random() * 20).toFixed(1),
            gas: (Math.random() * 500).toFixed(0)
        });
    }
}

function updateSensorDisplay(data) {
    // Temperature
    document.getElementById('temperature').textContent = `${data.temperature}°C`;
    const tempStatus = document.getElementById('tempStatus');
    const temp = parseFloat(data.temperature);
    if (temp > 35) {
        tempStatus.textContent = '⚠️ Nóng';
        tempStatus.style.color = '#ef4444';
    } else if (temp > 30) {
        tempStatus.textContent = '🌡️ Cao';
        tempStatus.style.color = '#f59e0b';
    } else if (temp < 18) {
        tempStatus.textContent = '❄️ Lạnh';
        tempStatus.style.color = '#3b82f6';
    } else {
        tempStatus.textContent = '✅ Bình thường';
        tempStatus.style.color = '#10b981';
    }
    
    // Humidity
    document.getElementById('humidity').textContent = `${data.humidity}%`;
    const humidStatus = document.getElementById('humidStatus');
    const humid = parseFloat(data.humidity);
    if (humid > 80) {
        humidStatus.textContent = '💧 Ẩm';
        humidStatus.style.color = '#3b82f6';
    } else if (humid < 30) {
        humidStatus.textContent = '🏜️ Khô';
        humidStatus.style.color = '#f59e0b';
    } else {
        humidStatus.textContent = '✅ Tốt';
        humidStatus.style.color = '#10b981';
    }
    
    // Gas (MQ2)
    document.getElementById('gas').textContent = `${data.gas} PPM`;
    const gasStatus = document.getElementById('gasStatus');
    const gas = parseFloat(data.gas);
    if (gas > 1000) {
        gasStatus.textContent = '🚨 NGUY HIỂM';
        gasStatus.style.color = '#ef4444';
        document.querySelector('.metric-card.gas').style.border = '2px solid #ef4444';
        showToast('error', 'Cảnh báo: Phát hiện khí gas!', 10000);
    } else if (gas > 500) {
        gasStatus.textContent = '⚠️ Cao';
        gasStatus.style.color = '#f59e0b';
        document.querySelector('.metric-card.gas').style.border = '2px solid #f59e0b';
    } else {
        gasStatus.textContent = '✅ An toàn';
        gasStatus.style.color = '#10b981';
        document.querySelector('.metric-card.gas').style.border = '1px solid var(--border-color)';
    }
}

// ===================================
// Toast Notifications
// ===================================
function showToast(type, message, duration = 3000) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: 'ri-check-line',
        error: 'ri-close-line',
        warning: 'ri-alert-line',
        info: 'ri-information-line'
    };
    
    toast.innerHTML = `
        <div class="toast-icon">
            <i class="${icons[type]}"></i>
        </div>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'toastIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ===================================
// Initialize on load
// ===================================
fetchSensorData();
