/**
 * Admin Dashboard JavaScript
 */

class AdminDashboard {
    constructor() {
        this.charts = {};
        this.websocket = null;
        this.refreshInterval = 30000; // 30 seconds
        this.init();
    }

    init() {
        this.initCharts();
        this.initWebSocket();
        this.initEventListeners();
        this.startAutoRefresh();
        this.loadInitialData();
    }

    initCharts() {
        // Real-time users chart
        const usersCtx = document.getElementById('usersChart');
        if (usersCtx) {
            this.charts.users = new Chart(usersCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Aktif Kullanıcılar',
                        data: [],
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: '#f1f5f9'
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            }
                        }
                    }
                }
            });
        }

        // API Response times chart
        const apiCtx = document.getElementById('apiChart');
        if (apiCtx) {
            this.charts.api = new Chart(apiCtx, {
                type: 'bar',
                data: {
                    labels: ['GET', 'POST', 'PUT', 'DELETE'],
                    datasets: [{
                        label: 'Ortalama Yanıt Süresi (ms)',
                        data: [120, 250, 180, 90],
                        backgroundColor: [
                            '#10b981',
                            '#3b82f6', 
                            '#f59e0b',
                            '#ef4444'
                        ],
                        borderRadius: 8
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: '#f1f5f9'
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            }
                        }
                    }
                }
            });
        }

        // Revenue chart
        const revenueCtx = document.getElementById('revenueChart');
        if (revenueCtx) {
            this.charts.revenue = new Chart(revenueCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Randevu Ücreti', 'Premium Üyelik', 'Komisyon'],
                    datasets: [{
                        data: [60, 25, 15],
                        backgroundColor: [
                            '#667eea',
                            '#10b981', 
                            '#f59e0b'
                        ],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }
    }

    initWebSocket() {
        // WebSocket for real-time updates
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/admin/`;
        
        try {
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };

            this.websocket.onclose = () => {
                // Reconnect after 5 seconds
                setTimeout(() => this.initWebSocket(), 5000);
            };
        } catch (error) {
            console.log('WebSocket not available, falling back to polling');
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'stats_update':
                this.updateStats(data.stats);
                break;
            case 'new_user':
                this.handleNewUser(data.user);
                break;
            case 'alert':
                this.showAlert(data.alert);
                break;
        }
    }

    initEventListeners() {
        // Refresh button
        document.getElementById('refreshBtn')?.addEventListener('click', () => {
            this.refreshDashboard();
        });

        // Export buttons
        document.getElementById('exportPDF')?.addEventListener('click', () => {
            this.exportReport('pdf');
        });

        document.getElementById('exportExcel')?.addEventListener('click', () => {
            this.exportReport('excel');
        });

        // Time range selector
        document.getElementById('timeRange')?.addEventListener('change', (e) => {
            this.loadData(e.target.value);
        });

        // User search
        document.getElementById('userSearch')?.addEventListener('input', (e) => {
            this.searchUsers(e.target.value);
        });
    }

    startAutoRefresh() {
        setInterval(() => {
            this.refreshDashboard();
        }, this.refreshInterval);
    }

    loadInitialData() {
        this.loadStats();
        this.loadRecentActivity();
        this.loadSystemHealth();
        this.loadAPIMetrics();
    }

    async loadStats() {
        try {
            const response = await fetch('/api/v1/admin/stats/');
            const data = await response.json();
            
            if (data.success) {
                this.updateStats(data.data);
            }
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    updateStats(stats) {
        // Update stat cards
        document.getElementById('totalUsers').textContent = stats.total_users || 0;
        document.getElementById('totalDietitians').textContent = stats.total_dietitians || 0;
        document.getElementById('totalAppointments').textContent = stats.total_appointments || 0;
        document.getElementById('totalRevenue').textContent = `₺${stats.total_revenue || 0}`;

        // Update percentage changes
        this.updatePercentageChange('usersChange', stats.users_change);
        this.updatePercentageChange('dietitiansChange', stats.dietitians_change);
        this.updatePercentageChange('appointmentsChange', stats.appointments_change);
        this.updatePercentageChange('revenueChange', stats.revenue_change);

        // Update charts with new data
        this.updateCharts(stats);
    }

    updatePercentageChange(elementId, change) {
        const element = document.getElementById(elementId);
        if (element && change !== undefined) {
            const icon = change >= 0 ? 'fa-arrow-up' : 'fa-arrow-down';
            const color = change >= 0 ? 'text-success' : 'text-danger';
            element.innerHTML = `<i class="fas ${icon} me-1"></i>${Math.abs(change)}% bu ay`;
            element.className = `opacity-75 ${color}`;
        }
    }

    updateCharts(stats) {
        // Update users chart
        if (this.charts.users && stats.users_timeline) {
            this.charts.users.data.labels = stats.users_timeline.labels;
            this.charts.users.data.datasets[0].data = stats.users_timeline.data;
            this.charts.users.update('none');
        }

        // Update API chart
        if (this.charts.api && stats.api_metrics) {
            this.charts.api.data.datasets[0].data = stats.api_metrics;
            this.charts.api.update('none');
        }
    }

    async loadRecentActivity() {
        try {
            const response = await fetch('/api/v1/admin/recent-activity/');
            const data = await response.json();
            
            if (data.success) {
                this.updateRecentActivity(data.data);
            }
        } catch (error) {
            console.error('Error loading recent activity:', error);
        }
    }

    updateRecentActivity(activities) {
        const tbody = document.getElementById('recentActivityBody');
        if (!tbody || !activities) return;

        tbody.innerHTML = activities.map(activity => `
            <tr>
                <td>
                    <div class="d-flex align-items-center">
                        <div class="avatar me-3">${activity.user.name.charAt(0)}</div>
                        <div>
                            <div class="fw-medium">${activity.user.name}</div>
                            <small class="text-muted">${activity.user.email}</small>
                        </div>
                    </div>
                </td>
                <td>
                    <span class="badge ${activity.type === 'DIYETISYEN' ? 'bg-success' : 'bg-primary'}">
                        ${activity.type}
                    </span>
                </td>
                <td>${this.formatDate(activity.date)}</td>
                <td>
                    <span class="badge badge-status ${activity.active ? 'bg-success' : 'bg-secondary'}">
                        ${activity.active ? 'Aktif' : 'Pasif'}
                    </span>
                </td>
                <td>
                    <div class="dropdown">
                        <button class="btn btn-sm btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown">
                            İşlem
                        </button>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="/admin/users/${activity.user.id}/">Görüntüle</a></li>
                            <li><a class="dropdown-item" href="/admin/users/${activity.user.id}/edit/">Düzenle</a></li>
                            <li><a class="dropdown-item text-danger" href="#" onclick="confirmDelete(${activity.user.id})">Sil</a></li>
                        </ul>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    async loadSystemHealth() {
        try {
            const response = await fetch('/api/v1/monitoring/metrics/health/');
            const data = await response.json();
            
            if (data.success) {
                this.updateSystemHealth(data.data);
            }
        } catch (error) {
            console.error('Error loading system health:', error);
        }
    }

    updateSystemHealth(health) {
        // Update progress bars
        this.updateProgressBar('cpuUsage', health.system?.cpu_usage || 0);
        this.updateProgressBar('memoryUsage', health.system?.memory_usage || 0);
        this.updateProgressBar('diskUsage', health.system?.disk_usage || 0);

        // Update system status
        const statusElement = document.getElementById('systemStatus');
        if (statusElement) {
            const isHealthy = health.system?.cpu_usage < 80 && 
                             health.system?.memory_usage < 90 && 
                             health.system?.disk_usage < 85;
            
            if (isHealthy) {
                statusElement.innerHTML = `
                    <div class="text-success mb-2">
                        <i class="fas fa-check-circle fa-2x"></i>
                    </div>
                    <div class="fw-medium">Sistem Sağlıklı</div>
                    <small class="text-muted">Son kontrol: ${this.formatTime(new Date())}</small>
                `;
            } else {
                statusElement.innerHTML = `
                    <div class="text-warning mb-2">
                        <i class="fas fa-exclamation-triangle fa-2x"></i>
                    </div>
                    <div class="fw-medium">Dikkat Gerekiyor</div>
                    <small class="text-muted">Kaynak kullanımı yüksek</small>
                `;
            }
        }
    }

    updateProgressBar(elementId, percentage) {
        const element = document.getElementById(elementId);
        if (element) {
            const progressBar = element.querySelector('.progress-bar');
            const percentText = element.parentElement.querySelector('.fw-medium');
            
            if (progressBar) {
                progressBar.style.width = `${percentage}%`;
                
                // Update color based on percentage
                progressBar.className = 'progress-bar';
                if (percentage < 60) {
                    progressBar.classList.add('bg-success');
                } else if (percentage < 80) {
                    progressBar.classList.add('bg-warning');
                } else {
                    progressBar.classList.add('bg-danger');
                }
            }
            
            if (percentText) {
                percentText.textContent = `${percentage}%`;
            }
        }
    }

    async loadAPIMetrics() {
        try {
            const response = await fetch('/api/v1/monitoring/metrics/summary/?minutes=60');
            const data = await response.json();
            
            if (data.success) {
                this.updateAPIMetrics(data.data.metrics);
            }
        } catch (error) {
            console.error('Error loading API metrics:', error);
        }
    }

    updateAPIMetrics(metrics) {
        // Update API stats cards
        document.getElementById('totalRequests').textContent = metrics.total_requests || 0;
        document.getElementById('errorRate').textContent = `${(metrics.error_rate || 0).toFixed(1)}%`;
        document.getElementById('avgResponseTime').textContent = `${(metrics.average_response_time || 0).toFixed(0)}ms`;
        document.getElementById('requestsPerMinute').textContent = (metrics.requests_per_minute || 0).toFixed(0);
    }

    refreshDashboard() {
        this.loadStats();
        this.loadRecentActivity();
        this.loadSystemHealth();
        this.loadAPIMetrics();
        
        // Show refresh indicator
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Yenileniyor...';
            setTimeout(() => {
                refreshBtn.innerHTML = '<i class="fas fa-sync me-1"></i>Yenile';
            }, 1000);
        }
    }

    async exportReport(format) {
        try {
            const response = await fetch(`/api/v1/monitoring/metrics/export/?format=${format}`);
            
            if (format === 'csv') {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `dashboard-report-${new Date().toISOString().split('T')[0]}.csv`;
                a.click();
                window.URL.revokeObjectURL(url);
            } else {
                const data = await response.json();
                console.log('Export data:', data);
            }
        } catch (error) {
            console.error('Error exporting report:', error);
            this.showAlert({
                type: 'error',
                message: 'Rapor dışa aktarılırken hata oluştu'
            });
        }
    }

    async searchUsers(query) {
        if (query.length < 2) return;

        try {
            const response = await fetch(`/api/v1/users/search/?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            if (data.success) {
                this.updateRecentActivity(data.results);
            }
        } catch (error) {
            console.error('Error searching users:', error);
        }
    }

    showAlert(alert) {
        const alertContainer = document.getElementById('alertContainer');
        if (!alertContainer) return;

        const alertElement = document.createElement('div');
        alertElement.className = `alert alert-${alert.type === 'error' ? 'danger' : alert.type} alert-dismissible fade show`;
        alertElement.innerHTML = `
            ${alert.message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        alertContainer.appendChild(alertElement);

        // Auto remove after 5 seconds
        setTimeout(() => {
            alertElement.remove();
        }, 5000);
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('tr-TR', {
            day: 'numeric',
            month: 'short',
            year: 'numeric'
        });
    }

    formatTime(date) {
        return date.toLocaleTimeString('tr-TR', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.adminDashboard = new AdminDashboard();
});

// Global functions
function confirmDelete(userId) {
    if (confirm('Bu kullanıcıyı silmek istediğinizden emin misiniz?')) {
        deleteUser(userId);
    }
}

async function deleteUser(userId) {
    try {
        const response = await fetch(`/api/v1/admin/users/${userId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        });

        if (response.ok) {
            window.adminDashboard.showAlert({
                type: 'success',
                message: 'Kullanıcı başarıyla silindi'
            });
            window.adminDashboard.loadRecentActivity();
        }
    } catch (error) {
        console.error('Error deleting user:', error);
    }
}

function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}