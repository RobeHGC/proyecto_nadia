/**
 * MCP Health Dashboard Widget
 * Displays automated MCP health check status in the dashboard
 */

class MCPHealthWidget {
    constructor(containerId) {
        this.containerId = containerId;
        this.refreshInterval = 60000; // 60 seconds (reduced from 30s to prevent rate limiting)
        this.intervalId = null;
        this.init();
    }

    init() {
        this.createWidget();
        this.loadHealthData();
        this.startAutoRefresh();
    }

    createWidget() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error('MCP Health Widget container not found:', this.containerId);
            return;
        }

        container.innerHTML = `
            <div class="mcp-health-widget">
                <div class="widget-header">
                    <h3>🔧 MCP Health Status</h3>
                    <div class="widget-controls">
                        <button id="mcp-refresh-btn" class="btn-icon" title="Refresh">↻</button>
                        <button id="mcp-expand-btn" class="btn-icon" title="Expand">⤢</button>
                    </div>
                </div>
                <div class="widget-content">
                    <div id="mcp-overall-status" class="status-indicator">
                        <span class="status-dot"></span>
                        <span class="status-text">Loading...</span>
                    </div>
                    <div id="mcp-checks-summary" class="checks-grid">
                        <!-- Dynamic content -->
                    </div>
                    <div class="widget-footer">
                        <span id="mcp-last-update">Last update: --</span>
                        <a href="#" id="mcp-view-details">View Details</a>
                    </div>
                </div>
            </div>
        `;

        // Add event listeners
        document.getElementById('mcp-refresh-btn').addEventListener('click', () => {
            this.loadHealthData();
        });

        document.getElementById('mcp-expand-btn').addEventListener('click', () => {
            this.showDetailedView();
        });

        document.getElementById('mcp-view-details').addEventListener('click', (e) => {
            e.preventDefault();
            this.showDetailedView();
        });
    }

    async loadHealthData() {
        try {
            const response = await fetch('/api/mcp/health', {
                headers: {
                    'Authorization': `Bearer ${window.dashboardConfig?.apiKey || ''}`
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.updateWidget(data);
        } catch (error) {
            console.error('Failed to load MCP health data:', error);
            this.showError('Failed to load health data');
        }
    }

    updateWidget(data) {
        // Update overall status
        const statusIndicator = document.getElementById('mcp-overall-status');
        const statusDot = statusIndicator.querySelector('.status-dot');
        const statusText = statusIndicator.querySelector('.status-text');

        const statusClass = this.getStatusClass(data.overall_status);
        statusDot.className = `status-dot ${statusClass}`;
        statusText.textContent = data.overall_status;

        // Update checks summary
        const checksGrid = document.getElementById('mcp-checks-summary');
        checksGrid.innerHTML = '';

        Object.entries(data.checks_summary || {}).forEach(([command, status]) => {
            const checkElement = this.createCheckElement(command, status);
            checksGrid.appendChild(checkElement);
        });

        // Update last update time
        const lastUpdate = document.getElementById('mcp-last-update');
        lastUpdate.textContent = `Last update: ${this.formatTime(data.last_check)}`;

        // Show alerts if any
        if (data.active_alerts > 0) {
            this.showAlertBadge(data.active_alerts);
        }
    }

    createCheckElement(command, status) {
        const element = document.createElement('div');
        element.className = 'check-item';
        
        const statusClass = this.getStatusClass(status.status);
        const displayName = this.getDisplayName(command);
        
        element.innerHTML = `
            <div class="check-header">
                <span class="check-name">${displayName}</span>
                <span class="check-status ${statusClass}">${status.status}</span>
            </div>
            <div class="check-details">
                <small>${this.formatTime(status.timestamp)}</small>
                ${status.issues_count > 0 ? `<span class="issue-count">${status.issues_count} issues</span>` : ''}
                ${status.alerts_count > 0 ? `<span class="alert-count">${status.alerts_count} alerts</span>` : ''}
            </div>
        `;

        // Add click handler for details
        element.addEventListener('click', () => {
            this.showCommandDetails(command);
        });

        return element;
    }

    getStatusClass(status) {
        switch (status) {
            case 'HEALTHY': return 'status-healthy';
            case 'WARNING': return 'status-warning';
            case 'CRITICAL': return 'status-critical';
            default: return 'status-unknown';
        }
    }

    getDisplayName(command) {
        const names = {
            'health-check': 'System Health',
            'security-check': 'Security Scan',
            'redis-health': 'Redis Health',
            'performance': 'Performance'
        };
        return names[command] || command;
    }

    formatTime(timestamp) {
        if (!timestamp) return '--';
        
        try {
            const date = new Date(timestamp);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);

            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
            return date.toLocaleDateString();
        } catch (error) {
            return '--';
        }
    }

    showError(message) {
        const statusIndicator = document.getElementById('mcp-overall-status');
        const statusDot = statusIndicator.querySelector('.status-dot');
        const statusText = statusIndicator.querySelector('.status-text');

        statusDot.className = 'status-dot status-error';
        statusText.textContent = message;
    }

    showAlertBadge(count) {
        const header = document.querySelector('.mcp-health-widget .widget-header h3');
        
        // Remove existing badge
        const existingBadge = header.querySelector('.alert-badge');
        if (existingBadge) {
            existingBadge.remove();
        }

        // Add new badge
        const badge = document.createElement('span');
        badge.className = 'alert-badge';
        badge.textContent = count;
        header.appendChild(badge);
    }

    async showCommandDetails(command) {
        try {
            const response = await fetch(`/api/mcp/health/${command}`, {
                headers: {
                    'Authorization': `Bearer ${window.dashboardConfig?.apiKey || ''}`
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.showModal(this.getDisplayName(command), data);
        } catch (error) {
            console.error('Failed to load command details:', error);
            alert('Failed to load command details');
        }
    }

    showDetailedView() {
        // Open detailed MCP health view
        window.open('/mcp-health-dashboard.html', '_blank');
    }

    showModal(title, data) {
        // Create modal overlay
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>${title} Details</h3>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="detail-row">
                        <strong>Status:</strong> 
                        <span class="status-badge ${this.getStatusClass(data.status)}">${data.status}</span>
                    </div>
                    <div class="detail-row">
                        <strong>Last Check:</strong> ${this.formatTime(data.timestamp)}
                    </div>
                    ${data.issues.length > 0 ? `
                        <div class="detail-section">
                            <strong>Issues:</strong>
                            <ul>
                                ${data.issues.map(issue => `<li>${issue}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                    ${data.alerts.length > 0 ? `
                        <div class="detail-section">
                            <strong>Alerts:</strong>
                            <ul>
                                ${data.alerts.map(alert => `<li>${alert}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                    ${Object.keys(data.metrics).length > 0 ? `
                        <div class="detail-section">
                            <strong>Metrics:</strong>
                            <div class="metrics-grid">
                                ${Object.entries(data.metrics).map(([key, value]) => 
                                    `<div><span>${key}:</span> <span>${value}</span></div>`
                                ).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary modal-close">Close</button>
                    <button class="btn-primary" onclick="mcpHealthWidget.runHealthCheck('${data.command}')">
                        Run Check Now
                    </button>
                </div>
            </div>
        `;

        // Add to document
        document.body.appendChild(modal);

        // Add event listeners
        modal.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay') || e.target.classList.contains('modal-close')) {
                modal.remove();
            }
        });
    }

    async runHealthCheck(command) {
        try {
            const response = await fetch(`/api/mcp/health/${command}/run`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${window.dashboardConfig?.apiKey || ''}`
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            
            // Close modal
            const modal = document.querySelector('.modal-overlay');
            if (modal) modal.remove();

            // Refresh widget
            this.loadHealthData();

            // Show notification
            this.showNotification(`Health check for ${this.getDisplayName(command)} completed: ${data.status}`);
        } catch (error) {
            console.error('Failed to run health check:', error);
            alert('Failed to run health check');
        }
    }

    showNotification(message) {
        // Simple notification - can be enhanced
        const notification = document.createElement('div');
        notification.className = 'notification';
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    startAutoRefresh() {
        this.intervalId = setInterval(() => {
            this.loadHealthData();
        }, this.refreshInterval);
    }

    stopAutoRefresh() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }

    destroy() {
        this.stopAutoRefresh();
        const container = document.getElementById(this.containerId);
        if (container) {
            container.innerHTML = '';
        }
    }
}

// CSS Styles (add to dashboard CSS)
const mcpHealthStyles = `
.mcp-health-widget {
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    padding: 16px;
    margin-bottom: 16px;
}

.widget-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    border-bottom: 1px solid #eee;
    padding-bottom: 8px;
}

.widget-header h3 {
    margin: 0;
    font-size: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.alert-badge {
    background: #dc3545;
    color: white;
    border-radius: 12px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: bold;
}

.widget-controls {
    display: flex;
    gap: 8px;
}

.btn-icon {
    background: none;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 4px 8px;
    cursor: pointer;
    font-size: 14px;
}

.btn-icon:hover {
    background: #f5f5f5;
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    padding: 8px;
    border-radius: 4px;
    background: #f8f9fa;
}

.status-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
}

.status-healthy { background: #28a745; }
.status-warning { background: #ffc107; }
.status-critical { background: #dc3545; }
.status-unknown { background: #6c757d; }
.status-error { background: #dc3545; }

.checks-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 8px;
    margin-bottom: 16px;
}

.check-item {
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 8px;
    cursor: pointer;
    transition: background 0.2s;
}

.check-item:hover {
    background: #f8f9fa;
}

.check-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}

.check-name {
    font-weight: 500;
    font-size: 14px;
}

.check-status {
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 12px;
    font-weight: bold;
    color: white;
}

.check-details {
    display: flex;
    gap: 8px;
    font-size: 12px;
    color: #666;
}

.issue-count, .alert-count {
    background: #dc3545;
    color: white;
    padding: 1px 4px;
    border-radius: 2px;
}

.widget-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
    color: #666;
    border-top: 1px solid #eee;
    padding-top: 8px;
}

.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal-content {
    background: white;
    border-radius: 8px;
    max-width: 600px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    border-bottom: 1px solid #eee;
}

.modal-close {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
}

.modal-body {
    padding: 16px;
}

.detail-row {
    margin-bottom: 8px;
}

.detail-section {
    margin: 16px 0;
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 8px;
}

.status-badge {
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: bold;
    color: white;
}

.modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 16px;
    border-top: 1px solid #eee;
}

.notification {
    position: fixed;
    top: 20px;
    right: 20px;
    background: #28a745;
    color: white;
    padding: 12px 16px;
    border-radius: 4px;
    z-index: 1001;
}
`;

// Add styles to document
if (!document.getElementById('mcp-health-styles')) {
    const style = document.createElement('style');
    style.id = 'mcp-health-styles';
    style.textContent = mcpHealthStyles;
    document.head.appendChild(style);
}

// Global instance
window.mcpHealthWidget = null;

// Initialize widget when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check if container exists
    if (document.getElementById('mcp-health-widget-container')) {
        window.mcpHealthWidget = new MCPHealthWidget('mcp-health-widget-container');
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MCPHealthWidget;
}