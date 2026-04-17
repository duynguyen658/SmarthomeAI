// Notifications JavaScript
const API_BASE = window.location.origin.replace('http://', 'ws://').replace('https://', 'wss://');

let notifications = [];
let ws = null;

// Initialize notifications
function initializeNotifications() {
    loadNotifications();
    connectWebSocket();
    requestNotificationPermission();
}

// Request browser notification permission
function requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

// Load notifications from API
async function loadNotifications() {
    try {
        const response = await fetch(`${window.location.origin}/api/alerts/notifications?limit=20`);
        if (response.ok) {
            notifications = await response.json();
            renderNotifications();
        }
    } catch (error) {
        console.error('Error loading notifications:', error);
    }
}

// Render notifications
function renderNotifications() {
    const container = document.getElementById('notificationsPanel');
    if (!container) return;

    if (notifications.length === 0) {
        container.innerHTML = '<p class="empty-state">Chưa có thông báo nào</p>';
        return;
    }

    // Sort by created_at descending
    const sorted = [...notifications].sort((a, b) => {
        const dateA = new Date(a.created_at);
        const dateB = new Date(b.created_at);
        return dateB - dateA;
    });

    container.innerHTML = sorted.map(notif => {
        const severityClass = notif.severity || 'info';
        const readClass = notif.read ? 'read' : 'unread';
        const date = new Date(notif.created_at);
        const timeStr = date.toLocaleString('vi-VN');
        
        return `
            <div class="notification-item ${readClass}" data-id="${notif.id}">
                <div class="notification-content">
                    <div class="notification-severity ${severityClass}"></div>
                    <div class="notification-text">
                        <p>${escapeHtml(notif.message)}</p>
                        <span class="notification-time">${timeStr}</span>
                    </div>
                </div>
                ${!notif.read ? `
                    <button class="mark-read-btn" onclick="markNotificationRead(${notif.id})" title="Đánh dấu đã đọc">
                        ✓
                    </button>
                ` : ''}
            </div>
        `;
    }).join('');
}

// Connect WebSocket
function connectWebSocket() {
    try {
        ws = new WebSocket(`${API_BASE}/api/alerts/ws/notifications`);
        
        ws.onopen = () => {
            console.log('WebSocket connected');
        };
        
        ws.onmessage = (event) => {
            try {
                const notification = JSON.parse(event.data);
                addNotification(notification);
                showBrowserNotification(notification);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
        
        ws.onclose = () => {
            console.log('WebSocket disconnected, reconnecting...');
            // Reconnect after 3 seconds
            setTimeout(connectWebSocket, 3000);
        };
    } catch (error) {
        console.error('Error connecting WebSocket:', error);
    }
}

// Add new notification
function addNotification(notification) {
    // Check if notification already exists
    const exists = notifications.find(n => n.id === notification.id);
    if (!exists) {
        notifications.unshift(notification);
        // Keep only last 50 notifications
        if (notifications.length > 50) {
            notifications = notifications.slice(0, 50);
        }
        renderNotifications();
    }
}

// Show browser notification
function showBrowserNotification(notification) {
    if ('Notification' in window && Notification.permission === 'granted') {
        const severityEmoji = {
            'info': '',
            'warning': '',
            'critical': ''
        };
        
        new Notification('Smart Home Alert', {
            body: notification.message,
            icon: '/assets/logo.png',
            tag: `notification-${notification.id}`,
            requireInteraction: notification.severity === 'critical'
        });
    }
}

// Mark notification as read
async function markNotificationRead(notificationId) {
    try {
        const response = await fetch(`${window.location.origin}/api/alerts/notifications/${notificationId}/read`, {
            method: 'POST'
        });

        if (response.ok) {
            // Update local notification
            const notif = notifications.find(n => n.id === notificationId);
            if (notif) {
                notif.read = true;
                renderNotifications();
            }
        }
    } catch (error) {
        console.error('Error marking notification as read:', error);
    }
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Make functions global
window.markNotificationRead = markNotificationRead;

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeNotifications);
} else {
    initializeNotifications();
}

