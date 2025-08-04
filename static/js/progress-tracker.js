/**
 * WhatsApp Progress Tracker
 * Handles real-time progress monitoring and log display
 */

class ProgressTracker {
    constructor(options = {}) {
        this.options = {
            pollInterval: 2000, // 2 seconds
            maxLogs: 1000,
            autoScroll: true,
            ...options
        };
        
        this.isMonitoring = false;
        this.monitoringInterval = null;
        this.lastLogCount = 0;
        this.progressData = {
            current: 0,
            total: 0,
            success_count: 0,
            failure_count: 0,
            logs: [],
            is_active: false
        };
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.setupProgressDisplay();
        console.log('Progress Tracker initialized');
    }

    bindEvents() {
        // Auto-scroll toggle
        const autoScrollToggle = document.getElementById('autoScroll');
        if (autoScrollToggle) {
            autoScrollToggle.addEventListener('change', (e) => {
                this.options.autoScroll = e.target.checked;
            });
        }

        // Clear logs button
        const clearLogsBtn = document.querySelector('[onclick="clearLogs()"]');
        if (clearLogsBtn) {
            clearLogsBtn.addEventListener('click', () => {
                this.clearLogs();
            });
        }

        // Stop process button
        const stopBtn = document.getElementById('stopBtn');
        if (stopBtn) {
            stopBtn.addEventListener('click', () => {
                this.stopProcess();
            });
        }
    }

    setupProgressDisplay() {
        // Initialize progress elements
        this.elements = {
            totalCount: document.getElementById('totalCount'),
            currentCount: document.getElementById('currentCount'),
            successCount: document.getElementById('successCount'),
            failureCount: document.getElementById('failureCount'),
            progressBar: document.getElementById('progressBar'),
            progressPercentage: document.getElementById('progressPercentage'),
            logsContainer: document.getElementById('logsContainer'),
            stopBtn: document.getElementById('stopBtn'),
            sendBtn: document.getElementById('sendBtn')
        };

        // Add initial log entry
        this.addLogEntry('Progress tracker ready. Upload files to begin sending.', 'info');
    }

    startMonitoring() {
        if (this.isMonitoring) return;
        
        this.isMonitoring = true;
        this.lastLogCount = 0;
        
        console.log('Starting progress monitoring');
        this.addLogEntry('Starting progress monitoring...', 'info');
        
        this.monitoringInterval = setInterval(() => {
            this.fetchProgress();
        }, this.options.pollInterval);
        
        // Show stop button
        if (this.elements.stopBtn) {
            this.elements.stopBtn.style.display = 'inline-block';
        }
    }

    stopMonitoring() {
        if (!this.isMonitoring) return;
        
        this.isMonitoring = false;
        
        if (this.monitoringInterval) {
            clearInterval(this.monitoringInterval);
            this.monitoringInterval = null;
        }
        
        console.log('Stopped progress monitoring');
        this.addLogEntry('Progress monitoring stopped.', 'warning');
        
        // Hide stop button
        if (this.elements.stopBtn) {
            this.elements.stopBtn.style.display = 'none';
        }
        
        // Reset send button
        this.resetSendButton();
    }

    async fetchProgress() {
        try {
            const response = await fetch('/api/progress');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.handleProgressUpdate(data);
            
        } catch (error) {
            console.error('Error fetching progress:', error);
            this.addLogEntry(`Error fetching progress: ${error.message}`, 'error');
            
            // If we get multiple errors, stop monitoring
            if (!this.progressData.is_active) {
                this.stopMonitoring();
            }
        }
    }

    handleProgressUpdate(data) {
        const previousData = { ...this.progressData };
        this.progressData = data;
        
        // Update progress display
        this.updateProgressDisplay(data);
        
        // Add new log entries
        this.updateLogs(data.logs || []);
        
        // Check if process completed
        if (previousData.is_active && !data.is_active) {
            this.handleProcessComplete();
        }
        
        // Update monitoring status
        if (!data.is_active && this.isMonitoring) {
            this.stopMonitoring();
        }
    }

    updateProgressDisplay(data) {
        // Update counters
        if (this.elements.totalCount) {
            this.elements.totalCount.textContent = this.formatNumber(data.total || 0);
        }
        
        if (this.elements.currentCount) {
            this.elements.currentCount.textContent = this.formatNumber(data.current || 0);
        }
        
        if (this.elements.successCount) {
            this.elements.successCount.textContent = this.formatNumber(data.success_count || 0);
        }
        
        if (this.elements.failureCount) {
            this.elements.failureCount.textContent = this.formatNumber(data.failure_count || 0);
        }
        
        // Update progress bar
        const percentage = data.total > 0 ? Math.round((data.current / data.total) * 100) : 0;
        
        if (this.elements.progressBar) {
            this.elements.progressBar.style.width = `${percentage}%`;
            this.elements.progressBar.setAttribute('aria-valuenow', percentage);
        }
        
        if (this.elements.progressPercentage) {
            this.elements.progressPercentage.textContent = `${percentage}%`;
        }
        
        // Update progress bar color based on success rate
        if (this.elements.progressBar && data.total > 0) {
            const successRate = data.success_count / (data.success_count + data.failure_count);
            if (successRate < 0.5) {
                this.elements.progressBar.classList.add('bg-warning');
                this.elements.progressBar.classList.remove('bg-success');
            } else if (successRate > 0.8) {
                this.elements.progressBar.classList.add('bg-success');
                this.elements.progressBar.classList.remove('bg-warning');
            }
        }
    }

    updateLogs(newLogs) {
        if (!newLogs || !Array.isArray(newLogs)) return;
        
        // Only add new logs (after the last known log count)
        const logsToAdd = newLogs.slice(this.lastLogCount);
        
        logsToAdd.forEach(logText => {
            const logType = this.determineLogType(logText);
            this.addLogEntry(logText, logType);
        });
        
        this.lastLogCount = newLogs.length;
        
        // Limit the number of log entries
        this.trimLogs();
    }

    determineLogType(logText) {
        if (logText.includes('✓') || logText.includes('Success') || logText.includes('successfully')) {
            return 'success';
        } else if (logText.includes('✗') || logText.includes('Failed') || logText.includes('Error') || logText.includes('error')) {
            return 'error';
        } else if (logText.includes('Warning') || logText.includes('Retry') || logText.includes('warning')) {
            return 'warning';
        }
        return 'info';
    }

    addLogEntry(message, type = 'info') {
        if (!this.elements.logsContainer) return;
        
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${type}`;
        logEntry.innerHTML = `
            <span class="log-timestamp">[${timestamp}]</span>
            <span class="log-message">${this.escapeHtml(message)}</span>
        `;
        
        this.elements.logsContainer.appendChild(logEntry);
        
        // Auto-scroll if enabled
        if (this.options.autoScroll) {
            this.scrollToBottom();
        }
        
        // Add animation
        logEntry.style.opacity = '0';
        logEntry.style.transform = 'translateY(10px)';
        
        requestAnimationFrame(() => {
            logEntry.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            logEntry.style.opacity = '1';
            logEntry.style.transform = 'translateY(0)';
        });
    }

    scrollToBottom() {
        if (this.elements.logsContainer) {
            this.elements.logsContainer.scrollTop = this.elements.logsContainer.scrollHeight;
        }
    }

    trimLogs() {
        if (!this.elements.logsContainer) return;
        
        const logEntries = this.elements.logsContainer.querySelectorAll('.log-entry');
        if (logEntries.length > this.options.maxLogs) {
            const entriesToRemove = logEntries.length - this.options.maxLogs;
            for (let i = 0; i < entriesToRemove; i++) {
                logEntries[i].remove();
            }
        }
    }

    clearLogs() {
        if (this.elements.logsContainer) {
            this.elements.logsContainer.innerHTML = '';
        }
        
        // Reset counters
        this.resetCounters();
        
        this.addLogEntry('Logs cleared.', 'info');
        this.lastLogCount = 0;
    }

    resetCounters() {
        const elements = [
            'totalCount', 'currentCount', 'successCount', 'failureCount'
        ];
        
        elements.forEach(elementId => {
            const element = this.elements[elementId];
            if (element) {
                element.textContent = '0';
            }
        });
        
        // Reset progress bar
        if (this.elements.progressBar) {
            this.elements.progressBar.style.width = '0%';
        }
        
        if (this.elements.progressPercentage) {
            this.elements.progressPercentage.textContent = '0%';
        }
    }

    handleProcessComplete() {
        const successCount = this.progressData.success_count || 0;
        const failureCount = this.progressData.failure_count || 0;
        const total = successCount + failureCount;
        
        if (total > 0) {
            const successRate = Math.round((successCount / total) * 100);
            this.addLogEntry(
                `Process completed! Sent ${successCount}/${total} messages (${successRate}% success rate)`,
                successRate > 80 ? 'success' : successRate > 50 ? 'warning' : 'error'
            );
        } else {
            this.addLogEntry('Process completed with no messages sent.', 'warning');
        }
        
        // Show completion notification
        this.showCompletionNotification(successCount, failureCount);
        
        // Reset UI
        this.resetSendButton();
    }

    showCompletionNotification(successCount, failureCount) {
        const total = successCount + failureCount;
        const successRate = total > 0 ? Math.round((successCount / total) * 100) : 0;
        
        let message, type;
        if (successRate > 90) {
            message = `Excellent! ${successCount} messages sent successfully.`;
            type = 'success';
        } else if (successRate > 70) {
            message = `Good job! ${successCount} messages sent, ${failureCount} failed.`;
            type = 'info';
        } else {
            message = `Process completed with issues. ${successCount} sent, ${failureCount} failed.`;
            type = 'warning';
        }
        
        if (window.dashboardUtils) {
            window.dashboardUtils.showToast(message, type);
        }
    }

    resetSendButton() {
        if (this.elements.sendBtn) {
            this.elements.sendBtn.disabled = false;
            this.elements.sendBtn.innerHTML = '<i class="fas fa-paper-plane me-1"></i>Start Sending';
        }
    }

    stopProcess() {
        // This would call an API endpoint to stop the process
        // For now, we'll just stop monitoring
        this.addLogEntry('Stop requested by user...', 'warning');
        this.stopMonitoring();
        
        if (window.dashboardUtils) {
            window.dashboardUtils.showToast('Process stop requested', 'info');
        }
    }

    // Utility methods
    formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, (m) => map[m]);
    }

    // Export progress data
    exportProgressData() {
        const data = {
            timestamp: new Date().toISOString(),
            progress: this.progressData,
            logs: Array.from(this.elements.logsContainer.querySelectorAll('.log-entry')).map(entry => ({
                timestamp: entry.querySelector('.log-timestamp').textContent,
                message: entry.querySelector('.log-message').textContent,
                type: entry.className.includes('log-success') ? 'success' :
                      entry.className.includes('log-error') ? 'error' :
                      entry.className.includes('log-warning') ? 'warning' : 'info'
            }))
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `whatsapp-progress-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    // Get current progress statistics
    getStats() {
        return {
            total: this.progressData.total || 0,
            current: this.progressData.current || 0,
            success: this.progressData.success_count || 0,
            failure: this.progressData.failure_count || 0,
            percentage: this.progressData.total > 0 ? 
                Math.round((this.progressData.current / this.progressData.total) * 100) : 0,
            successRate: (this.progressData.success_count + this.progressData.failure_count) > 0 ?
                Math.round((this.progressData.success_count / (this.progressData.success_count + this.progressData.failure_count)) * 100) : 0,
            isActive: this.progressData.is_active || false
        };
    }

    // Check if process is currently running
    isProcessActive() {
        return this.progressData.is_active || false;
    }

    // Manual progress update (for testing)
    simulateProgress(current, total, success = 0, failure = 0) {
        const data = {
            current,
            total,
            success_count: success,
            failure_count: failure,
            is_active: current < total,
            logs: [`Simulated progress: ${current}/${total}`]
        };
        
        this.handleProgressUpdate(data);
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ProgressTracker;
} else {
    window.ProgressTracker = ProgressTracker;
}
