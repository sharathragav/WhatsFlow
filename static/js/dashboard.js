/**
 * WhatsApp Marketing Dashboard - Core JavaScript
 * Handles global dashboard functionality, navigation, and utilities
 */

class WhatsAppDashboard {
    constructor() {
        this.init();
        this.bindEvents();
        this.startPeriodicUpdates();
    }

    init() {
        console.log('WhatsApp Marketing Dashboard initialized');
        this.initializeTooltips();
        this.initializePopovers();
        this.updateLastActivity();
    }

    bindEvents() {
        // Global event listeners
        document.addEventListener('DOMContentLoaded', () => {
            this.handlePageLoad();
        });

        // Navigation active state
        this.updateActiveNavigation();

        // Global form validations
        this.initializeFormValidations();

        // Global search functionality
        this.initializeGlobalSearch();

        // Keyboard shortcuts
        this.initializeKeyboardShortcuts();
    }

    handlePageLoad() {
        // Add loading animations
        document.body.classList.add('loaded');
        
        // Initialize any charts on the page
        this.initializeCharts();
        
        // Check for any pending notifications
        this.checkNotifications();
    }

    updateActiveNavigation() {
        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
        
        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === currentPath) {
                link.classList.add('active');
            }
        });
    }

    initializeTooltips() {
        // Initialize Bootstrap tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    initializePopovers() {
        // Initialize Bootstrap popovers
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function (popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    }

    initializeFormValidations() {
        // Add custom form validation styles
        const forms = document.querySelectorAll('.needs-validation');
        
        Array.from(forms).forEach(form => {
            form.addEventListener('submit', event => {
                if (!form.checkValidity()) {
                    event.preventDefault();
                    event.stopPropagation();
                }
                form.classList.add('was-validated');
            }, false);
        });
    }

    initializeGlobalSearch() {
        const searchInput = document.getElementById('globalSearch');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce((e) => {
                this.performGlobalSearch(e.target.value);
            }, 300));
        }
    }

    performGlobalSearch(query) {
        if (query.length < 2) return;
        
        // Implement global search functionality
        console.log('Searching for:', query);
        // This would search across customers, campaigns, etc.
    }

    initializeKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K for global search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                const searchInput = document.getElementById('globalSearch');
                if (searchInput) {
                    searchInput.focus();
                }
            }
            
            // Escape to close modals
            if (e.key === 'Escape') {
                const openModals = document.querySelectorAll('.modal.show');
                openModals.forEach(modal => {
                    const modalInstance = bootstrap.Modal.getInstance(modal);
                    if (modalInstance) {
                        modalInstance.hide();
                    }
                });
            }
        });
    }

    initializeCharts() {
        // Initialize any Chart.js charts on the page
        const chartElements = document.querySelectorAll('canvas[id$="Chart"]');
        chartElements.forEach(canvas => {
            if (!canvas.chart) { // Prevent re-initialization
                this.createChart(canvas);
            }
        });
    }

    createChart(canvas) {
        const chartType = canvas.id.replace('Chart', '').toLowerCase();
        
        // Basic chart configuration based on chart type
        const configs = {
            'messagevolume': this.getMessageVolumeConfig(),
            'successrate': this.getSuccessRateConfig(),
            'campaign': this.getCampaignConfig(),
            'customergrowth': this.getCustomerGrowthConfig()
        };
        
        const config = configs[charttype] || this.getDefaultConfig();
        canvas.chart = new Chart(canvas, config);
    }

    getMessageVolumeConfig() {
        return {
            type: 'line',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [{
                    label: 'Messages Sent',
                    data: [1200, 1800, 2200, 2800, 3200, 3800],
                    borderColor: '#25D366',
                    backgroundColor: 'rgba(37, 211, 102, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: this.getDefaultChartOptions()
        };
    }

    getSuccessRateConfig() {
        return {
            type: 'doughnut',
            data: {
                labels: ['Success', 'Failed'],
                datasets: [{
                    data: [85, 15],
                    backgroundColor: ['#25D366', '#FF6B6B'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        };
    }

    getCampaignConfig() {
        return {
            type: 'bar',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [{
                    label: 'Campaigns',
                    data: [12, 15, 18, 22, 19, 25],
                    backgroundColor: '#128C7E',
                    borderRadius: 4
                }]
            },
            options: this.getDefaultChartOptions()
        };
    }

    getCustomerGrowthConfig() {
        return {
            type: 'line',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [{
                    label: 'Total Customers',
                    data: [100, 150, 200, 280, 350, 420],
                    borderColor: '#075E54',
                    backgroundColor: 'rgba(7, 94, 84, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: this.getDefaultChartOptions()
        };
    }

    getDefaultChartOptions() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    }
                },
                x: {
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    }
                }
            }
        };
    }

    getDefaultConfig() {
        return {
            type: 'line',
            data: {
                labels: [],
                datasets: []
            },
            options: this.getDefaultChartOptions()
        };
    }

    checkNotifications() {
        // Check for system notifications
        this.checkSystemStatus();
        this.checkPendingTasks();
    }

    async checkSystemStatus() {
        try {
            // Check if WhatsApp is connected
            const response = await fetch('/api/status');
            const data = await response.json();
            
            if (data.status === 'processing') {
                this.showNotification('Bulk sending in progress', 'info');
            }
        } catch (error) {
            console.warn('Could not check system status:', error);
        }
    }

    checkPendingTasks() {
        // Check for any pending tasks or incomplete processes
        const pendingTasks = localStorage.getItem('pendingTasks');
        if (pendingTasks) {
            const tasks = JSON.parse(pendingTasks);
            if (tasks.length > 0) {
                this.showNotification(`You have ${tasks.length} pending tasks`, 'warning');
            }
        }
    }

    startPeriodicUpdates() {
        // Update dashboard every 30 seconds
        setInterval(() => {
            this.updateDashboardStats();
            this.updateLastActivity();
        }, 30000);
    }

    async updateDashboardStats() {
        try {
            // Update stats cards if on dashboard page
            if (window.location.pathname === '/') {
                const statsCards = document.querySelectorAll('.stat-number');
                // Add subtle animation to indicate update
                statsCards.forEach(card => {
                    card.style.opacity = '0.7';
                    setTimeout(() => {
                        card.style.opacity = '1';
                    }, 200);
                });
            }
        } catch (error) {
            console.warn('Could not update dashboard stats:', error);
        }
    }

    updateLastActivity() {
        const now = new Date().toLocaleTimeString();
        const activityElement = document.getElementById('lastActivity');
        if (activityElement) {
            activityElement.textContent = `Last updated: ${now}`;
        }
    }

    // Utility Methods
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    showNotification(message, type = 'info', duration = 5000) {
        const notification = this.createNotification(message, type);
        document.body.appendChild(notification);
        
        // Show notification
        setTimeout(() => {
            notification.classList.add('show');
        }, 100);
        
        // Auto-hide notification
        setTimeout(() => {
            this.hideNotification(notification);
        }, duration);
    }

    createNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Add close functionality
        const closeBtn = notification.querySelector('.btn-close');
        closeBtn.addEventListener('click', () => {
            this.hideNotification(notification);
        });
        
        return notification;
    }

    hideNotification(notification) {
        notification.classList.remove('show');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }

    formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    }

    formatDate(date) {
        return new Intl.DateTimeFormat('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }).format(new Date(date));
    }

    formatFileSize(bytes) {
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        if (bytes === 0) return '0 Bytes';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
    }

    validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    validatePhone(phone) {
        const re = /^[\+]?[1-9][\d]{0,15}$/;
        return re.test(phone.replace(/\s/g, ''));
    }

    // Data persistence helpers
    saveToStorage(key, data) {
        try {
            localStorage.setItem(key, JSON.stringify(data));
        } catch (error) {
            console.warn('Could not save to localStorage:', error);
        }
    }

    loadFromStorage(key, defaultValue = null) {
        try {
            const data = localStorage.getItem(key);
            return data ? JSON.parse(data) : defaultValue;
        } catch (error) {
            console.warn('Could not load from localStorage:', error);
            return defaultValue;
        }
    }

    // API helpers
    async apiCall(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API call failed:', error);
            throw error;
        }
    }

    // Export data as CSV
    exportToCSV(data, filename) {
        const csv = this.convertToCSV(data);
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }

    convertToCSV(data) {
        if (!data.length) return '';
        
        const headers = Object.keys(data[0]);
        const csvContent = [
            headers.join(','),
            ...data.map(row => 
                headers.map(header => 
                    JSON.stringify(row[header] || '')
                ).join(',')
            )
        ].join('\n');
        
        return csvContent;
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.whatsappDashboard = new WhatsAppDashboard();
});

// Global utility functions
window.dashboardUtils = {
    showToast: (message, type = 'info') => {
        if (window.whatsappDashboard) {
            window.whatsappDashboard.showNotification(message, type);
        }
    },
    
    formatNumber: (num) => {
        if (window.whatsappDashboard) {
            return window.whatsappDashboard.formatNumber(num);
        }
        return num.toLocaleString();
    },
    
    formatDate: (date) => {
        if (window.whatsappDashboard) {
            return window.whatsappDashboard.formatDate(date);
        }
        return new Date(date).toLocaleDateString();
    }
};
