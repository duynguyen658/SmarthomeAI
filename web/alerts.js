// Alerts JavaScript
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

let alertRules = [];
let editingAlertRuleId = null;

// Initialize alerts
function initializeAlerts() {
    loadAlertRules();
    setupAlertRuleForm();
}

// Load alert rules
async function loadAlertRules() {
    try {
        const response = await fetch(`${API_BASE}/api/alerts/rules`);
        if (response.ok) {
            alertRules = await response.json();
            renderAlertRulesList();
        } else {
            console.error('Error loading alert rules:', response.statusText);
        }
    } catch (error) {
        console.error('Error loading alert rules:', error);
    }
}

// Render alert rules list
function renderAlertRulesList() {
    const container = document.getElementById('alertRulesList');
    if (!container) return;

    if (alertRules.length === 0) {
        container.innerHTML = '<p class="empty-state">Chưa có quy tắc cảnh báo nào. Hãy tạo quy tắc mới!</p>';
        return;
    }

    const conditionText = {
        'gt': 'Lớn hơn',
        'lt': 'Nhỏ hơn',
        'eq': 'Bằng',
        'between': 'Trong khoảng'
    };

    container.innerHTML = alertRules.map(rule => {
        const condition = conditionText[rule.condition] || rule.condition;
        const thresholdText = rule.condition === 'between' && rule.threshold_max
            ? `${rule.threshold_value} - ${rule.threshold_max}`
            : rule.threshold_value;
        
        return `
            <div class="alert-rule-item" data-id="${rule.id}">
                <div class="alert-rule-item-header">
                    <div class="alert-rule-item-info">
                        <h4>${rule.name}</h4>
                        <p>${rule.sensor_type} ${condition} ${thresholdText}</p>
                    </div>
                    <div class="alert-rule-item-status">
                        <span class="status-badge ${rule.enabled ? 'on' : 'off'}">
                            ${rule.enabled ? 'BẬT' : 'TẮT'}
                        </span>
                    </div>
                </div>
                <div class="alert-rule-item-actions">
                    <button class="action-btn edit-btn" onclick="editAlertRule(${rule.id})">Sửa</button>
                    <button class="action-btn delete-btn" onclick="deleteAlertRule(${rule.id})">Xóa</button>
                </div>
            </div>
        `;
    }).join('');
}

// Setup alert rule form
function setupAlertRuleForm() {
    const form = document.getElementById('alertRuleForm');
    if (!form) return;

    // Show/hide threshold_max based on condition
    document.getElementById('alertCondition')?.addEventListener('change', (e) => {
        const maxGroup = document.getElementById('alertThresholdMaxGroup');
        if (maxGroup) {
            maxGroup.style.display = e.target.value === 'between' ? 'block' : 'none';
        }
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveAlertRule();
    });

    document.getElementById('cancelAlertRuleForm')?.addEventListener('click', () => {
        resetAlertRuleForm();
    });
}

// Save alert rule
async function saveAlertRule() {
    const form = document.getElementById('alertRuleForm');
    const alertRuleId = document.getElementById('alertRuleId').value;
    
    const alertRuleData = {
        name: document.getElementById('alertRuleName').value,
        sensor_type: document.getElementById('alertSensorType').value,
        condition: document.getElementById('alertCondition').value,
        threshold_value: parseFloat(document.getElementById('alertThreshold').value),
        threshold_max: document.getElementById('alertCondition').value === 'between'
            ? parseFloat(document.getElementById('alertThresholdMax').value)
            : null,
        enabled: true,
        notification_type: 'browser'
    };

    try {
        const url = alertRuleId 
            ? `${API_BASE}/api/alerts/rules/${alertRuleId}`
            : `${API_BASE}/api/alerts/rules`;
        
        const method = alertRuleId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(alertRuleData)
        });

        if (response.ok) {
            resetAlertRuleForm();
            loadAlertRules();
            showToast('success', alertRuleId ? 'Đã cập nhật quy tắc!' : 'Đã tạo quy tắc mới!');
        } else {
            const error = await response.json();
            showToast('error', `Lỗi: ${error.detail || 'Không thể lưu quy tắc'}`);
        }
    } catch (error) {
        console.error('Error saving alert rule:', error);
        showToast('error', 'Lỗi khi lưu quy tắc');
    }
}

// Edit alert rule
function editAlertRule(ruleId) {
    const rule = alertRules.find(r => r.id === ruleId);
    if (!rule) return;

    editingAlertRuleId = ruleId;
    document.getElementById('alertRuleId').value = rule.id;
    document.getElementById('alertRuleName').value = rule.name;
    document.getElementById('alertSensorType').value = rule.sensor_type;
    document.getElementById('alertCondition').value = rule.condition;
    document.getElementById('alertThreshold').value = rule.threshold_value;
    
    if (rule.threshold_max) {
        document.getElementById('alertThresholdMax').value = rule.threshold_max;
    }
    
    // Show/hide threshold_max
    const maxGroup = document.getElementById('alertThresholdMaxGroup');
    if (maxGroup) {
        maxGroup.style.display = rule.condition === 'between' ? 'block' : 'none';
    }
    
    document.getElementById('alertRuleFormTitle').textContent = 'Sửa Quy Tắc Cảnh Báo';
    
    // Scroll to form
    document.getElementById('alertRuleForm').scrollIntoView({ behavior: 'smooth' });
}

// Delete alert rule
async function deleteAlertRule(ruleId) {
    if (!confirm('Bạn có chắc muốn xóa quy tắc này?')) return;

    try {
        const response = await fetch(`${API_BASE}/api/alerts/rules/${ruleId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            loadAlertRules();
            showToast('success', 'Đã xóa quy tắc!');
        } else {
            showToast('error', 'Lỗi khi xóa quy tắc');
        }
    } catch (error) {
        console.error('Error deleting alert rule:', error);
        showToast('error', 'Lỗi khi xóa quy tắc');
    }
}

// Reset alert rule form
function resetAlertRuleForm() {
    editingAlertRuleId = null;
    document.getElementById('alertRuleForm').reset();
    document.getElementById('alertRuleId').value = '';
    document.getElementById('alertRuleFormTitle').textContent = 'Tạo Quy Tắc Cảnh Báo';
    document.getElementById('alertThresholdMaxGroup').style.display = 'none';
}

// Make functions global
window.editAlertRule = editAlertRule;
window.deleteAlertRule = deleteAlertRule;

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAlerts);
} else {
    initializeAlerts();
}

