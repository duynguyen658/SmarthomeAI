// Automation & Scheduling JavaScript
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

let schedules = [];
let devices = [];
let editingScheduleId = null;

// Initialize automation
function initializeAutomation() {
    loadDevices();
    loadSchedules();
    setupScheduleForm();
}

// Load devices for schedule form
async function loadDevices() {
    try {
        const response = await fetch(`${API_BASE}/api/devices`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                devices = await response.json();
                populateDeviceSelect();
                console.log(`Đã tải ${devices.length} thiết bị từ database`);
            } else {
                console.error('Response is not JSON');
            }
        } else {
            console.error('Error loading devices:', response.status, response.statusText);
        }
    } catch (error) {
        console.error('Error loading devices:', error);
    }
}

// Populate device select
function populateDeviceSelect() {
    const select = document.getElementById('scheduleDeviceId');
    if (!select) return;

    if (devices.length === 0) {
        select.innerHTML = '<option value="">Chưa có thiết bị nào. Vui lòng thêm thiết bị trước!</option>';
        return;
    }

    select.innerHTML = '<option value="">Chọn thiết bị...</option>' +
        devices.map(device => 
            `<option value="${device.id}">${device.device_name} (${device.location} - ${device.device_type})</option>`
        ).join('');
}

// Load schedules
async function loadSchedules() {
    try {
        const response = await fetch(`${API_BASE}/api/schedules`);
        if (response.ok) {
            schedules = await response.json();
            renderSchedulesList();
        } else {
            console.error('Error loading schedules:', response.statusText);
        }
    } catch (error) {
        console.error('Error loading schedules:', error);
    }
}

// Render schedules list
function renderSchedulesList() {
    const container = document.getElementById('schedulesList');
    if (!container) return;

    if (schedules.length === 0) {
        container.innerHTML = '<p class="empty-state">Chưa có lịch nào. Hãy tạo lịch mới!</p>';
        return;
    }

    container.innerHTML = schedules.map(schedule => {
        const daysText = schedule.days && schedule.days.length > 0
            ? schedule.days.join(', ')
            : 'Mỗi ngày';
        
        return `
            <div class="schedule-item" data-id="${schedule.id}">
                <div class="schedule-item-header">
                    <div class="schedule-item-info">
                        <h4>${schedule.name}</h4>
                        <p>${schedule.device_name || 'N/A'} • ${schedule.action} • ${schedule.time}</p>
                        <p class="schedule-days">${daysText}</p>
                    </div>
                    <div class="schedule-item-status">
                        <span class="status-badge ${schedule.enabled ? 'on' : 'off'}">
                            ${schedule.enabled ? 'BẬT' : 'TẮT'}
                        </span>
                    </div>
                </div>
                <div class="schedule-item-actions">
                    <button class="action-btn toggle-btn" onclick="toggleSchedule(${schedule.id})">
                        ${schedule.enabled ? 'Tắt' : 'Bật'}
                    </button>
                    <button class="action-btn edit-btn" onclick="editSchedule(${schedule.id})">Sửa</button>
                    <button class="action-btn delete-btn" onclick="deleteSchedule(${schedule.id})">Xóa</button>
                </div>
            </div>
        `;
    }).join('');
}

// Setup schedule form
function setupScheduleForm() {
    const form = document.getElementById('scheduleForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveSchedule();
    });

    document.getElementById('cancelScheduleForm')?.addEventListener('click', () => {
        resetScheduleForm();
    });
}

// Save schedule
async function saveSchedule() {
    const form = document.getElementById('scheduleForm');
    const scheduleId = document.getElementById('scheduleId').value;
    
    // Get selected days
    const dayCheckboxes = document.querySelectorAll('#scheduleForm input[type="checkbox"]:checked');
    const days = Array.from(dayCheckboxes).map(cb => cb.value);
    
    const scheduleData = {
        name: document.getElementById('scheduleName').value,
        device_id: parseInt(document.getElementById('scheduleDeviceId').value),
        action: document.getElementById('scheduleAction').value,
        time: document.getElementById('scheduleTime').value,
        days: days.length > 0 ? days : null,
        enabled: true
    };

    try {
        const url = scheduleId 
            ? `${API_BASE}/api/schedules/${scheduleId}`
            : `${API_BASE}/api/schedules`;
        
        const method = scheduleId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(scheduleData)
        });

        if (response.ok) {
            resetScheduleForm();
            loadSchedules();
            showToast('success', scheduleId ? 'Đã cập nhật lịch!' : 'Đã tạo lịch mới!');
        } else {
            const error = await response.json();
            showToast('error', `Lỗi: ${error.detail || 'Không thể lưu lịch'}`);
        }
    } catch (error) {
        console.error('Error saving schedule:', error);
        showToast('error', 'Lỗi khi lưu lịch');
    }
}

// Edit schedule
function editSchedule(scheduleId) {
    const schedule = schedules.find(s => s.id === scheduleId);
    if (!schedule) return;

    editingScheduleId = scheduleId;
    document.getElementById('scheduleId').value = schedule.id;
    document.getElementById('scheduleName').value = schedule.name;
    document.getElementById('scheduleDeviceId').value = schedule.device_id;
    document.getElementById('scheduleAction').value = schedule.action;
    
    // Convert time to HH:MM format for time input
    const [hours, minutes] = schedule.time.split(':');
    document.getElementById('scheduleTime').value = `${hours}:${minutes}`;
    
    // Check days
    document.querySelectorAll('#scheduleForm input[type="checkbox"]').forEach(cb => {
        cb.checked = schedule.days && schedule.days.includes(cb.value);
    });
    
    document.getElementById('scheduleFormTitle').textContent = 'Sửa Lịch';
    
    // Scroll to form
    document.getElementById('scheduleForm').scrollIntoView({ behavior: 'smooth' });
}

// Delete schedule
async function deleteSchedule(scheduleId) {
    if (!confirm('Bạn có chắc muốn xóa lịch này?')) return;

    try {
        const response = await fetch(`${API_BASE}/api/schedules/${scheduleId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            loadSchedules();
            showToast('success', 'Đã xóa lịch!');
        } else {
            showToast('error', 'Lỗi khi xóa lịch');
        }
    } catch (error) {
        console.error('Error deleting schedule:', error);
        showToast('error', 'Lỗi khi xóa lịch');
    }
}

// Toggle schedule
async function toggleSchedule(scheduleId) {
    try {
        const response = await fetch(`${API_BASE}/api/schedules/${scheduleId}/toggle`, {
            method: 'POST'
        });

        if (response.ok) {
            loadSchedules();
        } else {
            alert('Lỗi khi bật/tắt lịch');
        }
    } catch (error) {
        console.error('Error toggling schedule:', error);
        alert('Lỗi khi bật/tắt lịch');
    }
}

// Reset schedule form
function resetScheduleForm() {
    editingScheduleId = null;
    document.getElementById('scheduleForm').reset();
    document.getElementById('scheduleId').value = '';
    document.getElementById('scheduleFormTitle').textContent = 'Tạo Lịch Mới';
    document.querySelectorAll('#scheduleForm input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
    });
}

// Make functions global
window.editSchedule = editSchedule;
window.deleteSchedule = deleteSchedule;
window.toggleSchedule = toggleSchedule;

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAutomation);
} else {
    initializeAutomation();
}

