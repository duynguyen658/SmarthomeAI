// Device Management JavaScript
const API_BASE = window.location.origin;

// Helper function to show toast
function showToast(type, message) {
    const container = document.getElementById('toastContainer');
    if (!container) {
        alert(message);
        return;
    }
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icons = {
        success: 'ri-check-line',
        error: 'ri-close-line',
        warning: 'ri-alert-line',
        info: 'ri-information-line'
    };
    toast.innerHTML = `
        <div class="toast-icon"><i class="${icons[type]}"></i></div>
        <span class="toast-message">${message}</span>
    `;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'toastIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

let devices = [];
let editingDeviceId = null;
let formInitialized = false; // Flag để tránh đăng ký event listener nhiều lần
let isProcessing = false; // Flag để tránh xử lý nhiều lần cùng lúc

// Initialize device management
function initializeDeviceManagement() {
    loadDevices();
    setupDeviceForm();
}

// Load devices from API
async function loadDevices() {
    const container = document.getElementById('devicesList');
    if (!container) return;
    
    // Hiển thị loading state
    container.innerHTML = '<p class="loading-state">Đang tải danh sách thiết bị...</p>';
    
    try {
        const url = `${API_BASE}/api/devices`;
        console.log('Fetching devices from:', url);
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        });
        
        console.log('Response status:', response.status);
        console.log('Response headers:', Object.fromEntries(response.headers.entries()));
        
        // Kiểm tra Content-Type để đảm bảo là JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('Response is not JSON. Status:', response.status);
            console.error('Response text (first 500 chars):', text.substring(0, 500));
            container.innerHTML = `<p class="error-state">Lỗi: Server trả về dữ liệu không đúng định dạng (${response.status}). Kiểm tra console để xem chi tiết.</p>`;
            return;
        }
        
        if (response.ok) {
            try {
                devices = await response.json();
                renderDevicesList();
            } catch (jsonError) {
                console.error('Error parsing JSON:', jsonError);
                container.innerHTML = `<p class="error-state">Lỗi khi đọc dữ liệu từ server</p>`;
            }
        } else {
            try {
                const error = await response.json();
                container.innerHTML = `<p class="error-state">Lỗi khi tải danh sách thiết bị: ${error.detail || response.statusText}</p>`;
            } catch (jsonError) {
                // Nếu không parse được JSON, hiển thị status text
                container.innerHTML = `<p class="error-state">Lỗi ${response.status}: ${response.statusText}</p>`;
            }
            console.error('Error loading devices:', response.status, response.statusText);
        }
    } catch (error) {
        container.innerHTML = `<p class="error-state">Lỗi kết nối: ${error.message}</p>`;
        console.error('Error loading devices:', error);
    }
}

// Render devices list
function renderDevicesList() {
    const container = document.getElementById('devicesList');
    if (!container) return;

    if (devices.length === 0) {
        container.innerHTML = '<p class="empty-state">Chưa có thiết bị nào. Hãy thêm thiết bị mới!</p>';
        return;
    }

    container.innerHTML = devices.map(device => {
        const macDisplay = device.mac_address ? `<small style="color: var(--text-secondary); font-size: 0.75rem;">MAC: ${device.mac_address}</small>` : '';
        const mqttDisplay = device.mqtt_topic ? `<small style="color: var(--text-secondary); font-size: 0.75rem;">MQTT: ${device.mqtt_topic}</small>` : '';
        return `
        <div class="device-item" data-id="${device.id}">
            <div class="device-item-header">
                <div class="device-item-info">
                    <h4>${device.device_name}</h4>
                    <p>${device.location} • ${device.device_type}</p>
                    ${macDisplay}
                    ${mqttDisplay}
                </div>
                <div class="device-item-status">
                    <span class="status-badge ${device.status.toLowerCase()}">${device.status}</span>
                </div>
            </div>
            <div class="device-item-actions">
                <button class="action-btn control-btn" onclick="controlDevice(${device.id}, '${device.status === 'ON' ? 'OFF' : 'ON'}')">
                    ${device.status === 'ON' ? 'Tắt' : 'Bật'}
                </button>
                <button class="action-btn edit-btn" onclick="editDevice(${device.id})">Sửa</button>
                <button class="action-btn delete-btn" onclick="deleteDevice(${device.id})">Xóa</button>
            </div>
        </div>
    `;
    }).join('');
}

// Setup device form (chỉ đăng ký 1 lần)
function setupDeviceForm() {
    // Tránh đăng ký event listener nhiều lần
    if (formInitialized) return;
    
    const form = document.getElementById('deviceForm');
    if (form && !form.hasAttribute('data-listener-attached')) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await saveDevice();
        }, { once: false });
        form.setAttribute('data-listener-attached', 'true');
    }

    const cancelBtn = document.getElementById('cancelDeviceForm');
    if (cancelBtn && !cancelBtn.hasAttribute('data-listener-attached')) {
        cancelBtn.addEventListener('click', () => {
            resetDeviceForm();
        });
        cancelBtn.setAttribute('data-listener-attached', 'true');
    }

    // Setup edit device form
    const editForm = document.getElementById('deviceEditForm');
    if (editForm && !editForm.hasAttribute('data-listener-attached')) {
        editForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await updateDevice();
        }, { once: false });
        editForm.setAttribute('data-listener-attached', 'true');
    }

    const cancelEditBtn = document.getElementById('cancelEditDeviceForm');
    if (cancelEditBtn && !cancelEditBtn.hasAttribute('data-listener-attached')) {
        cancelEditBtn.addEventListener('click', () => {
            resetEditDeviceForm();
            if (typeof switchSection === 'function') {
                switchSection('device-management');
            }
        });
        cancelEditBtn.setAttribute('data-listener-attached', 'true');
    }
    
    formInitialized = true;
}

// Save device (chỉ tạo mới)
async function saveDevice() {
    // Tránh xử lý nhiều lần cùng lúc
    if (isProcessing) {
        console.log('Đang xử lý, bỏ qua request này...');
        return;
    }
    
    isProcessing = true;
    
    const deviceData = {
        device_name: document.getElementById('deviceName').value,
        device_type: document.getElementById('deviceType').value,
        location: document.getElementById('deviceLocation').value,
        mac_address: document.getElementById('deviceMacAddress').value.trim() || null,
        mqtt_topic: document.getElementById('deviceMqttTopic').value.trim() || null
    };

    try {
        const response = await fetch(`${API_BASE}/api/devices`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(deviceData)
        });

        if (response.ok) {
            resetDeviceForm();
            await loadDevices();
            showToast('success', 'Đã thêm thiết bị mới!');
        } else {
            const error = await response.json();
            let errorMessage = 'Lỗi khi lưu thiết bị';
            let existingDeviceId = null;
            
            if (error.detail) {
                if (typeof error.detail === 'object' && error.detail.message) {
                    errorMessage = error.detail.message;
                    if (error.detail.existing_device_id) {
                        existingDeviceId = error.detail.existing_device_id;
                    }
                } else {
                    errorMessage = error.detail;
                }
            }
            
            // Nếu có thiết bị trùng, hỏi người dùng có muốn chỉnh sửa không
            if (existingDeviceId) {
                const shouldEdit = confirm(errorMessage + '\n\nBạn có muốn chỉnh sửa thiết bị này không?');
                if (shouldEdit) {
                    // Đảm bảo devices đã được load trước khi edit
                    await loadDevices();
                    editDevice(existingDeviceId);
                    return;
                }
            } else {
                alert(`Lỗi: ${errorMessage}`);
            }
        }
    } catch (error) {
        console.error('Error saving device:', error);
        showToast('error', 'Lỗi khi lưu thiết bị');
    } finally {
        isProcessing = false;
    }
}

// Update device (chỉnh sửa)
async function updateDevice() {
    // Tránh xử lý nhiều lần cùng lúc
    if (isProcessing) {
        console.log('Đang xử lý, bỏ qua request này...');
        return;
    }
    
    isProcessing = true;
    
    const deviceId = document.getElementById('editDeviceId').value;
    if (!deviceId) {
        alert('Không tìm thấy ID thiết bị');
        isProcessing = false;
        return;
    }

    const deviceData = {
        device_name: document.getElementById('editDeviceName').value,
        device_type: document.getElementById('editDeviceType').value,
        location: document.getElementById('editDeviceLocation').value,
        mac_address: document.getElementById('editDeviceMacAddress').value.trim() || null,
        mqtt_topic: document.getElementById('editDeviceMqttTopic').value.trim() || null
    };

    try {
        const response = await fetch(`${API_BASE}/api/devices/${deviceId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(deviceData)
        });

        if (response.ok) {
            resetEditDeviceForm();
            await loadDevices();
            showToast('success', 'Đã cập nhật thiết bị!');
            // Quay lại trang quản lý thiết bị
            if (typeof switchSection === 'function') {
                switchSection('device-management');
            }
        } else {
            const error = await response.json();
            let errorMessage = 'Lỗi khi cập nhật thiết bị';
            
            if (error.detail) {
                if (typeof error.detail === 'object' && error.detail.message) {
                    errorMessage = error.detail.message;
                } else {
                    errorMessage = error.detail;
                }
            }
            
            showToast('error', errorMessage);
        }
    } catch (error) {
        console.error('Error updating device:', error);
        showToast('error', 'Lỗi khi cập nhật thiết bị');
    } finally {
        isProcessing = false;
    }
}

// Edit device - chuyển sang trang edit
function editDevice(deviceId) {
    const device = devices.find(d => d.id === deviceId);
    if (!device) {
        alert('Không tìm thấy thiết bị');
        return;
    }

    editingDeviceId = deviceId;
    
    // Fill form edit
    document.getElementById('editDeviceId').value = device.id;
    document.getElementById('editDeviceName').value = device.device_name;
    document.getElementById('editDeviceType').value = device.device_type;
    document.getElementById('editDeviceLocation').value = device.location;
    document.getElementById('editDeviceMacAddress').value = device.mac_address || '';
    document.getElementById('editDeviceMqttTopic').value = device.mqtt_topic || '';
    
    // Chuyển sang section edit-device
    if (typeof switchSection === 'function') {
        switchSection('edit-device');
    } else {
        // Fallback nếu switchSection chưa được load
        document.querySelectorAll('.content-section').forEach(sec => {
            sec.classList.remove('active');
        });
        document.getElementById('edit-device').classList.add('active');
        
        // Update navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
    }
}

// Delete device
async function deleteDevice(deviceId) {
    if (!confirm('Bạn có chắc muốn xóa thiết bị này?')) return;
    
    // Tránh xử lý nhiều lần cùng lúc
    if (isProcessing) {
        console.log('Đang xử lý, bỏ qua request này...');
        return;
    }
    
    isProcessing = true;

    try {
        const response = await fetch(`${API_BASE}/api/devices/${deviceId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            await loadDevices();
            showToast('success', 'Đã xóa thiết bị!');
        } else {
            showToast('error', 'Lỗi khi xóa thiết bị');
        }
    } catch (error) {
        console.error('Error deleting device:', error);
        showToast('error', 'Lỗi khi xóa thiết bị');
    } finally {
        isProcessing = false;
    }
}

// Control device
async function controlDevice(deviceId, action) {
    try {
        const response = await fetch(`${API_BASE}/api/devices/${deviceId}/control`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });

        if (response.ok) {
            loadDevices();
            showToast('success', `Đã ${action === 'ON' ? 'bật' : 'tắt'} thiết bị`);
        } else {
            showToast('error', 'Lỗi khi điều khiển thiết bị');
        }
    } catch (error) {
        console.error('Error controlling device:', error);
        showToast('error', 'Lỗi khi điều khiển thiết bị');
    }
}

// Reset device form (create)
function resetDeviceForm() {
    editingDeviceId = null;
    document.getElementById('deviceForm').reset();
}

// Reset edit device form
function resetEditDeviceForm() {
    editingDeviceId = null;
    document.getElementById('deviceEditForm').reset();
    document.getElementById('editDeviceId').value = '';
}

// Make functions global
window.editDevice = editDevice;
window.deleteDevice = deleteDevice;
window.controlDevice = controlDevice;

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDeviceManagement);
} else {
    initializeDeviceManagement();
}

