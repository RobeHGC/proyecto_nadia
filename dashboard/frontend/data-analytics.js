// data-analytics.js
/**
 * NADIA Data Analytics Dashboard
 * Advanced analytics and data management interface
 */

class DataAnalytics {
    constructor() {
        this.API_BASE = window.location.origin.replace(':3000', ':8000');
        this.API_KEY = null; // Will be loaded from server
        this.charts = {};
        this.dataTable = null;
        this.refreshInterval = null;
        this.currentBackupId = null;
        this.theme = localStorage.getItem('theme') || 'light';
        
        this.init();
    }

    async init() {
        console.log('Initializing Data Analytics Dashboard...');
        
        // Load configuration from server first
        await this.loadConfig();
        
        // Apply saved theme
        this.applyTheme();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Initialize components
        await this.loadOverviewData();
        this.initializeDataTable();
        this.initializeCharts();
        await this.loadBackups();
        
        // Start auto-refresh
        this.startAutoRefresh();
        
        console.log('Data Analytics Dashboard initialized successfully');
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            if (response.ok) {
                const config = await response.json();
                this.API_KEY = config.apiKey;
                this.API_BASE = config.apiBase;
            } else {
                // Fallback to localStorage or default
                this.API_KEY = localStorage.getItem('dashboardApiKey') || 'miclavesegura45mil';
            }
        } catch (error) {
            console.warn('Failed to load config from server, using fallback:', error);
            this.API_KEY = localStorage.getItem('dashboardApiKey') || 'miclavesegura45mil';
        }
    }

    setupEventListeners() {
        // Tab switch events
        document.querySelectorAll('[data-bs-toggle="pill"]').forEach(tab => {
            tab.addEventListener('shown.bs.tab', (e) => {
                const target = e.target.getAttribute('data-bs-target');
                this.onTabSwitch(target);
            });
        });

        // Cleanup type radio buttons
        document.querySelectorAll('input[name="cleanup-type"]').forEach(radio => {
            radio.addEventListener('change', this.toggleCleanupInputs.bind(this));
        });

        // Filter inputs with debouncing
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce(this.onSearchChange.bind(this), 500));
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', this.handleKeyboardShortcuts.bind(this));
    }

    onTabSwitch(target) {
        switch(target) {
            case '#data':
                if (this.dataTable) {
                    this.dataTable.columns.adjust().responsive.recalc();
                }
                break;
            case '#charts':
                this.resizeCharts();
                break;
            case '#backups':
                this.loadBackups();
                break;
            case '#integrity':
                this.loadIntegrityReport();
                break;
        }
    }

    async loadOverviewData() {
        try {
            this.showLoading();
            
            const response = await this.apiCall('/api/analytics/metrics');
            const metrics = response.data || response;
            
            this.updateOverviewMetrics(metrics);
            this.updateOverviewChart(metrics.daily_messages || []);
            this.updateLastUpdated();
            
        } catch (error) {
            console.error('Error loading overview data:', error);
            this.showToast('Error loading overview data', 'error');
        } finally {
            this.hideLoading();
        }
    }

    updateOverviewMetrics(metrics) {
        // Calculate totals
        const totalMessages = metrics.daily_messages?.reduce((sum, day) => sum + day.count, 0) || 0;
        const activeUsers = new Set(metrics.daily_messages?.map(d => d.user_id)).size || 0;
        const dailyCost = metrics.cost_metrics?.reduce((sum, day) => sum + day.cost, 0) || 0;
        const cacheRatio = 0.75; // From system stats
        
        // Update metric cards
        document.getElementById('total-messages').textContent = totalMessages.toLocaleString();
        document.getElementById('active-users').textContent = activeUsers.toLocaleString();
        document.getElementById('daily-cost').textContent = '$' + dailyCost.toFixed(3);
        document.getElementById('cache-ratio').textContent = (cacheRatio * 100).toFixed(1) + '%';
        
        // Update queue status
        const queueStatus = document.getElementById('queue-status');
        if (queueStatus) {
            queueStatus.textContent = 'Normal';
            queueStatus.className = 'status-badge status-online';
        }
    }

    updateOverviewChart(dailyData) {
        const ctx = document.getElementById('overview-chart');
        if (!ctx) return;

        if (this.charts.overview) {
            this.charts.overview.destroy();
        }

        const labels = dailyData.map(d => new Date(d.date).toLocaleDateString());
        const data = dailyData.map(d => d.count);

        // Set canvas dimensions explicitly before creating chart
        ctx.style.maxHeight = '300px';
        ctx.style.height = '300px';
        ctx.style.width = '100%';

        this.charts.overview = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Messages',
                    data: data,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#6366f1',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                aspectRatio: 2, // Width/Height ratio (fallback)
                onResize: function(chart, size) {
                    // Prevent infinite height growth
                    if (size.height > 300) {
                        chart.canvas.style.height = '300px';
                        chart.canvas.style.maxHeight = '300px';
                    }
                },
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
                            display: false
                        }
                    }
                }
            }
        });
    }

    initializeDataTable() {
        const table = document.getElementById('data-table');
        if (!table) return;

        this.dataTable = $(table).DataTable({
            processing: true,
            serverSide: true,
            responsive: true,
            pageLength: 25,
            lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
            ajax: {
                url: `${this.API_BASE}/api/analytics/data`,
                type: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.API_KEY}`
                },
                data: (d) => {
                    return {
                        page: Math.floor(d.start / d.length) + 1,
                        limit: d.length,
                        sort_by: d.columns[d.order[0].column].data || 'created_at',
                        sort_order: d.order[0].dir,
                        search: d.search.value,
                        date_from: document.getElementById('date-from')?.value,
                        date_to: document.getElementById('date-to')?.value,
                        user_id: document.getElementById('user-id-filter')?.value,
                        customer_status: document.getElementById('customer-status-filter')?.value
                    };
                },
                dataSrc: (json) => {
                    // Update pagination info
                    json.recordsTotal = json.pagination?.total || 0;
                    json.recordsFiltered = json.pagination?.total || 0;
                    return json.data || [];
                },
                error: (xhr, error, thrown) => {
                    console.error('DataTable AJAX error:', error);
                    this.showToast('Error loading data', 'error');
                }
            },
            columns: [
                // GRUPO 1: Identificación y Estado
                { 
                    data: 'user_id', 
                    width: '90px',
                    render: (data) => {
                        return data ? `<code>${data}</code>` : '--';
                    }
                },
                { 
                    data: 'conversation_id', 
                    width: '80px',
                    render: (data) => {
                        return data ? `<small class="text-muted">${data.slice(-6)}</small>` : '--';
                    }
                },
                { 
                    data: 'customer_status', 
                    width: '110px',
                    render: (data) => {
                        if (!data) return '<span class="badge bg-secondary">UNKNOWN</span>';
                        const statusConfig = {
                            'PROSPECT': { bg: 'bg-secondary', icon: 'fas fa-user' },
                            'LEAD_QUALIFIED': { bg: 'bg-success', icon: 'fas fa-star' },
                            'CUSTOMER': { bg: 'bg-warning text-dark', icon: 'fas fa-crown' },
                            'CHURNED': { bg: 'bg-danger', icon: 'fas fa-user-times' },
                            'LEAD_EXHAUSTED': { bg: 'bg-dark', icon: 'fas fa-ban' }
                        };
                        const config = statusConfig[data] || { bg: 'bg-secondary', icon: 'fas fa-question' };
                        return `<span class="badge ${config.bg}" title="${data}">
                            <i class="${config.icon} me-1"></i>${data.replace('_', ' ')}
                        </span>`;
                    }
                },
                { 
                    data: 'review_status', 
                    width: '100px',
                    render: (data) => {
                        if (!data) return '<span class="badge bg-light text-dark">--</span>';
                        const statusConfig = {
                            'pending': { bg: 'bg-warning', icon: 'fas fa-clock' },
                            'reviewing': { bg: 'bg-info', icon: 'fas fa-eye' },
                            'approved': { bg: 'bg-success', icon: 'fas fa-check' },
                            'rejected': { bg: 'bg-danger', icon: 'fas fa-times' }
                        };
                        const config = statusConfig[data] || { bg: 'bg-secondary', icon: 'fas fa-question' };
                        return `<span class="badge ${config.bg}" title="${data}">
                            <i class="${config.icon} me-1"></i>${data.toUpperCase()}
                        </span>`;
                    }
                },
                
                // GRUPO 2: Contenido y Ediciones
                { 
                    data: 'user_message',
                    width: '150px',
                    render: (data) => {
                        if (!data) return '--';
                        const preview = data.length > 40 ? data.substring(0, 40) + '...' : data;
                        return `<span title="${data.replace(/"/g, '&quot;')}" class="user-message-preview">${preview}</span>`;
                    }
                },
                { 
                    data: 'final_bubbles',
                    width: '100px',
                    render: (data) => {
                        if (!data) return '--';
                        let bubbles = [];
                        try {
                            bubbles = Array.isArray(data) ? data : JSON.parse(data);
                        } catch {
                            bubbles = [data];
                        }
                        const content = bubbles.join(' ');
                        const preview = content.length > 30 ? content.substring(0, 30) + '...' : content;
                        return `<span class="badge bg-primary" title="${content.replace(/"/g, '&quot;')}">
                            ${bubbles.length} bubble${bubbles.length !== 1 ? 's' : ''}
                        </span><br><small class="text-muted">${preview}</small>`;
                    }
                },
                { 
                    data: 'edit_tags',
                    width: '120px',
                    render: (data) => {
                        if (!data || !Array.isArray(data) || data.length === 0) {
                            return '<span class="badge bg-light text-dark">No edits</span>';
                        }
                        const tagColors = {
                            'TONE_': 'bg-info',
                            'STRUCT_': 'bg-warning text-dark',
                            'CONTENT_': 'bg-success',
                            'ENGLISH_': 'bg-primary',
                            'CTA_': 'bg-danger'
                        };
                        
                        const tags = data.slice(0, 3).map(tag => {
                            const prefix = Object.keys(tagColors).find(p => tag.startsWith(p));
                            const color = prefix ? tagColors[prefix] : 'bg-secondary';
                            const shortTag = tag.replace(/^(TONE_|STRUCT_|CONTENT_|ENGLISH_|CTA_)/, '');
                            return `<span class="badge ${color} me-1 mb-1" style="font-size: 0.6rem;" title="${tag}">${shortTag}</span>`;
                        }).join('');
                        
                        const extraCount = data.length > 3 ? `<br><small class="text-muted">+${data.length - 3} more</small>` : '';
                        return tags + extraCount;
                    }
                },
                { 
                    data: 'quality_score',
                    width: '80px',
                    render: (data) => {
                        if (!data) return '--';
                        const stars = '★'.repeat(data) + '☆'.repeat(5 - data);
                        const color = data >= 4 ? 'text-success' : data >= 3 ? 'text-warning' : 'text-danger';
                        return `<span class="${color}" title="Quality Score: ${data}/5">${stars}</span>`;
                    }
                },
                
                // GRUPO 3: Riesgos y CTA
                { 
                    data: 'constitution_risk_score',
                    width: '80px',
                    render: (data) => {
                        if (data === null || data === undefined) return '--';
                        const score = parseFloat(data);
                        let color = 'text-success'; // Verde para < 0.3
                        let bgColor = 'bg-success';
                        
                        if (score >= 0.7) {
                            color = 'text-danger';
                            bgColor = 'bg-danger';
                        } else if (score >= 0.3) {
                            color = 'text-warning';
                            bgColor = 'bg-warning text-dark';
                        }
                        
                        return `<span class="badge ${bgColor}" title="Risk Score: ${score.toFixed(2)}">
                            ${score.toFixed(2)}
                        </span>`;
                    }
                },
                { 
                    data: 'constitution_recommendation',
                    width: '90px',
                    render: (data) => {
                        if (!data) return '--';
                        const recConfig = {
                            'approve': { bg: 'bg-success', icon: 'fas fa-check' },
                            'review': { bg: 'bg-warning text-dark', icon: 'fas fa-exclamation-triangle' },
                            'flag': { bg: 'bg-danger', icon: 'fas fa-flag' }
                        };
                        const config = recConfig[data.toLowerCase()] || { bg: 'bg-secondary', icon: 'fas fa-question' };
                        return `<span class="badge ${config.bg}" title="Recommendation: ${data}">
                            <i class="${config.icon} me-1"></i>${data.toUpperCase()}
                        </span>`;
                    }
                },
                { 
                    data: 'cta_data',
                    width: '90px',
                    render: (data) => {
                        if (!data || !data.type) return '<span class="badge bg-light text-dark">None</span>';
                        const type = data.type.toUpperCase();
                        const colors = {
                            'SOFT': 'bg-info',
                            'MEDIUM': 'bg-warning text-dark',
                            'DIRECT': 'bg-danger'
                        };
                        const color = colors[type] || 'bg-secondary';
                        const inserted = data.inserted ? ' ✓' : '';
                        return `<span class="badge ${color}" title="CTA Type: ${type}${inserted}">
                            ${type}${inserted}
                        </span>`;
                    }
                },
                { 
                    data: 'reviewer_notes',
                    width: '200px',
                    render: (data, type, row) => {
                        const notes = data || '';
                        const shortNotes = notes.length > 50 ? notes.substring(0, 50) + '...' : notes;
                        const isEmpty = !notes.trim();
                        
                        return `<div class="reviewer-notes-cell">
                            <div class="reviewer-notes-display ${isEmpty ? 'empty' : ''}" 
                                 onclick="analytics.editReviewerNotes('${row.id}', '${notes.replace(/'/g, '&#39;')}')"
                                 title="${notes || 'Click to add reviewer notes'}">
                                ${isEmpty ? 'Click to add notes...' : shortNotes}
                            </div>
                        </div>`;
                    }
                },
                
                // GRUPO 4: Performance
                { 
                    data: 'review_time_seconds',
                    width: '80px',
                    render: (data) => {
                        if (!data) return '--';
                        const seconds = parseInt(data);
                        if (seconds < 60) {
                            return `<span class="badge bg-success">${seconds}s</span>`;
                        } else {
                            const minutes = Math.floor(seconds / 60);
                            const remainingSeconds = seconds % 60;
                            const color = seconds < 120 ? 'bg-info' : seconds < 300 ? 'bg-warning text-dark' : 'bg-danger';
                            return `<span class="badge ${color}">${minutes}m ${remainingSeconds}s</span>`;
                        }
                    }
                },
                { 
                    data: 'total_cost_usd',
                    width: '70px',
                    render: (data, type, row) => {
                        const cost = parseFloat(data || 0);
                        if (cost === 0) return '<span class="text-muted">$0.00</span>';
                        
                        const color = cost < 0.001 ? 'text-success' : cost < 0.01 ? 'text-info' : 'text-warning';
                        return `<span class="${color}" title="LLM1: $${(row.llm1_cost_usd || 0).toFixed(4)}, LLM2: $${(row.llm2_cost_usd || 0).toFixed(4)}">
                            $${cost.toFixed(4)}
                        </span>`;
                    }
                },
                { 
                    data: 'created_at',
                    width: '120px',
                    render: (data) => {
                        if (!data) return '--';
                        const date = new Date(data);
                        const now = new Date();
                        const diffMs = now - date;
                        const diffMins = Math.floor(diffMs / 60000);
                        const diffHours = Math.floor(diffMs / 3600000);
                        const diffDays = Math.floor(diffMs / 86400000);
                        
                        let timeAgo = '';
                        if (diffMins < 60) {
                            timeAgo = `${diffMins}m ago`;
                        } else if (diffHours < 24) {
                            timeAgo = `${diffHours}h ago`;
                        } else {
                            timeAgo = `${diffDays}d ago`;
                        }
                        
                        return `<span title="${date.toLocaleString()}">${timeAgo}</span>`;
                    }
                },
                { 
                    data: 'id',
                    width: '60px',
                    orderable: false,
                    render: (data) => {
                        return `
                            <button class="btn btn-sm btn-outline-primary" onclick="analytics.viewFullDetails(${data})" title="View All Details">
                                <i class="fas fa-search-plus"></i>
                            </button>
                        `;
                    }
                }
            ],
            order: [[14, 'desc']], // Sort by created_at desc (column 14)
            language: {
                emptyTable: "No data available",
                info: "Showing _START_ to _END_ of _TOTAL_ entries",
                infoEmpty: "Showing 0 to 0 of 0 entries",
                loadingRecords: "Loading...",
                processing: "Processing...",
                search: "Search:",
                paginate: {
                    first: "First",
                    last: "Last",
                    next: "Next",
                    previous: "Previous"
                }
            }
        });

        // Add row highlighting for recent changes
        this.dataTable.on('draw.dt', () => {
            const now = new Date();
            const tenMinutesAgo = new Date(now - 10 * 60 * 1000);
            
            this.dataTable.rows().every(function() {
                const data = this.data();
                const createdAt = new Date(data.created_at);
                
                if (createdAt > tenMinutesAgo) {
                    $(this.node()).addClass('data-highlight');
                }
            });
            
            // Re-apply persistent filters after draw
            this.applyPersistentFilters();
        });

        // Add click handler for rows
        $('#data-table tbody').on('click', 'tr', (e) => {
            // Ignore if clicking on action button
            if ($(e.target).closest('button').length) return;
            
            const data = this.dataTable.row(e.currentTarget).data();
            if (data) {
                this.viewFullDetails(data.id);
            }
        });
    }

    initializeCharts() {
        this.loadChartData();
    }

    async loadChartData() {
        try {
            const response = await this.apiCall('/api/analytics/metrics');
            const metrics = response.data || response;
            
            this.createCTAChart(metrics.cta_distribution || []);
            this.createQualityChart(metrics.quality_scores || []);
            this.createHeatmapChart(metrics.hourly_activity || []);
            this.createFunnelChart(metrics.conversion_funnel || []);
            this.createCostChart(metrics.cost_metrics || []);
            
        } catch (error) {
            console.error('Error loading chart data:', error);
            this.showToast('Error loading charts', 'error');
        }
    }

    createCTAChart(data) {
        const ctx = document.getElementById('cta-chart');
        if (!ctx || !data.length) return;

        if (this.charts.cta) {
            this.charts.cta.destroy();
        }

        const colors = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981'];
        
        this.charts.cta = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(d => d.type.charAt(0).toUpperCase() + d.type.slice(1)),
                datasets: [{
                    data: data.map(d => d.count),
                    backgroundColor: colors.slice(0, data.length),
                    borderWidth: 2,
                    borderColor: '#fff'
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

    createQualityChart(data) {
        const ctx = document.getElementById('quality-chart');
        if (!ctx || !data.length) return;

        if (this.charts.quality) {
            this.charts.quality.destroy();
        }

        this.charts.quality = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => `${d.score} Star${d.score !== 1 ? 's' : ''}`),
                datasets: [{
                    label: 'Count',
                    data: data.map(d => d.count),
                    backgroundColor: '#6366f1',
                    borderColor: '#4f46e5',
                    borderWidth: 1
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
                        beginAtZero: true
                    }
                }
            }
        });
    }

    createHeatmapChart(data) {
        const ctx = document.getElementById('heatmap-chart');
        if (!ctx) return;

        if (this.charts.heatmap) {
            this.charts.heatmap.destroy();
        }

        // Create 24-hour data array
        const hourlyData = new Array(24).fill(0);
        data.forEach(d => {
            hourlyData[d.hour] = d.count;
        });

        this.charts.heatmap = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: Array.from({length: 24}, (_, i) => `${i}:00`),
                datasets: [{
                    label: 'Messages',
                    data: hourlyData,
                    backgroundColor: hourlyData.map(count => {
                        const maxCount = Math.max(...hourlyData);
                        const opacity = maxCount > 0 ? count / maxCount : 0;
                        return `rgba(99, 102, 241, ${0.3 + opacity * 0.7})`;
                    }),
                    borderColor: '#6366f1',
                    borderWidth: 1
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
                        beginAtZero: true
                    }
                }
            }
        });
    }

    createFunnelChart(data) {
        const ctx = document.getElementById('funnel-chart');
        if (!ctx || !data.length) return;

        if (this.charts.funnel) {
            this.charts.funnel.destroy();
        }

        this.charts.funnel = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d.status),
                datasets: [{
                    label: 'Users',
                    data: data.map(d => d.user_count),
                    backgroundColor: [
                        '#6366f1',
                        '#8b5cf6',
                        '#10b981',
                        '#f59e0b',
                        '#ef4444'
                    ].slice(0, data.length),
                    borderWidth: 1,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                indexAxis: 'y',
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    createCostChart(data) {
        const ctx = document.getElementById('cost-chart');
        if (!ctx || !data.length) return;

        if (this.charts.cost) {
            this.charts.cost.destroy();
        }

        this.charts.cost = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => new Date(d.date).toLocaleDateString()),
                datasets: [{
                    label: 'Daily Cost (USD)',
                    data: data.map(d => d.cost),
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true,
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
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(3);
                            }
                        }
                    }
                }
            }
        });
    }

    async loadBackups() {
        try {
            const response = await this.apiCall('/api/analytics/backups');
            const backups = response.data || response;
            
            this.renderBackupsList(backups);
            
        } catch (error) {
            console.error('Error loading backups:', error);
            this.showToast('Error loading backups', 'error');
        }
    }

    renderBackupsList(backups) {
        const container = document.getElementById('backups-list');
        if (!container) return;

        if (!backups || backups.length === 0) {
            container.innerHTML = `
                <div class="text-center py-5">
                    <i class="fas fa-database fa-3x text-muted mb-3"></i>
                    <h5>No backups found</h5>
                    <p class="text-muted">Create your first backup to get started</p>
                </div>
            `;
            return;
        }

        container.innerHTML = backups.map(backup => `
            <div class="backup-item">
                <div class="d-flex justify-content-between align-items-center">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">${backup.name}</h6>
                        <div class="d-flex gap-3 text-muted small">
                            <span><i class="fas fa-calendar me-1"></i>${new Date(backup.created_at).toLocaleString()}</span>
                            <span><i class="fas fa-hdd me-1"></i>${this.formatFileSize(backup.size_bytes)}</span>
                            <span><i class="fas fa-${backup.compressed ? 'compress' : 'file'} me-1"></i>${backup.compressed ? 'Compressed' : 'Uncompressed'}</span>
                            <span class="badge ${backup.file_exists ? 'bg-success' : 'bg-danger'}">
                                ${backup.file_exists ? 'Available' : 'Missing'}
                            </span>
                        </div>
                    </div>
                    <div class="d-flex gap-2">
                        <button class="btn btn-sm btn-outline-info" onclick="analytics.viewBackupDetails('${backup.backup_id}')" title="View Details">
                            <i class="fas fa-info-circle"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-success" onclick="analytics.restoreBackup('${backup.backup_id}', '${backup.name}')" 
                                ${!backup.file_exists ? 'disabled' : ''} title="Restore">
                            <i class="fas fa-undo"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="analytics.deleteBackup('${backup.backup_id}')" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `).join('');
    }

    // Filter and Search Functions
    applyFilters() {
        if (this.dataTable) {
            this.dataTable.ajax.reload();
        }
    }

    clearFilters() {
        // Clear all filters including quick filters
        document.getElementById('search-input').value = '';
        document.getElementById('date-from').value = '';
        document.getElementById('date-to').value = '';
        document.getElementById('user-id-filter').value = '';
        
        // Clear quick filters
        this.clearQuickFilters();
        
        if (this.dataTable) {
            this.dataTable.search('').ajax.reload();
        }
    }

    // Quick Filters Implementation
    applyQuickFilters() {
        if (!this.dataTable) return;
        
        // Get quick filter values
        const customerStatus = document.getElementById('customer-status-filter').value;
        const ctaInserted = document.getElementById('cta-inserted-filter').checked;
        const needsReview = document.getElementById('needs-review-filter').checked;
        const riskMin = parseFloat(document.getElementById('risk-score-min').value) / 100;
        const riskMax = parseFloat(document.getElementById('risk-score-max').value) / 100;
        
        // Custom filtering function
        $.fn.dataTable.ext.search.push((settings, data, dataIndex) => {
            // Get the full row data
            const row = this.dataTable.row(dataIndex).data();
            
            // Customer Status filter
            if (customerStatus && row.customer_status !== customerStatus) {
                return false;
            }
            
            // Risk Score filter
            const riskScore = parseFloat(row.constitution_risk_score) || 0;
            if (riskScore < riskMin || riskScore > riskMax) {
                return false;
            }
            
            // CTA Inserted filter
            if (ctaInserted) {
                if (!row.cta_data || !row.cta_data.type || !row.cta_data.inserted) {
                    return false;
                }
            }
            
            // Needs Review filter
            if (needsReview) {
                const needsReviewFlag = 
                    (parseFloat(row.constitution_risk_score) > 0.5) ||
                    (row.constitution_recommendation && row.constitution_recommendation.toLowerCase() !== 'approve');
                
                if (!needsReviewFlag) {
                    return false;
                }
            }
            
            return true;
        });
        
        // Redraw table with filters applied
        this.dataTable.draw();
        
        // Update active filters display
        this.updateActiveFiltersDisplay();
        
        // Remove the custom filter to prevent stacking
        $.fn.dataTable.ext.search.pop();
        
        // Re-apply the filter for persistence
        this.currentQuickFilters = {
            customerStatus,
            ctaInserted,
            needsReview,
            riskMin,
            riskMax
        };
        
        // Apply persistent filter
        this.applyPersistentFilters();
    }

    applyPersistentFilters() {
        if (!this.currentQuickFilters || !this.dataTable) return;
        
        $.fn.dataTable.ext.search.push((settings, data, dataIndex) => {
            const row = this.dataTable.row(dataIndex).data();
            const filters = this.currentQuickFilters;
            
            // Apply all filters
            if (filters.customerStatus && row.customer_status !== filters.customerStatus) {
                return false;
            }
            
            const riskScore = parseFloat(row.constitution_risk_score) || 0;
            if (riskScore < filters.riskMin || riskScore > filters.riskMax) {
                return false;
            }
            
            if (filters.ctaInserted && (!row.cta_data || !row.cta_data.type || !row.cta_data.inserted)) {
                return false;
            }
            
            if (filters.needsReview) {
                const needsReviewFlag = 
                    (parseFloat(row.constitution_risk_score) > 0.5) ||
                    (row.constitution_recommendation && row.constitution_recommendation.toLowerCase() !== 'approve');
                
                if (!needsReviewFlag) {
                    return false;
                }
            }
            
            return true;
        });
    }

    updateRiskScoreFilter() {
        const minValue = parseFloat(document.getElementById('risk-score-min').value) / 100;
        const maxValue = parseFloat(document.getElementById('risk-score-max').value) / 100;
        
        // Ensure min doesn't exceed max
        if (minValue > maxValue) {
            document.getElementById('risk-score-min').value = maxValue * 100;
        }
        
        // Update display
        document.getElementById('risk-score-value').textContent = 
            `${minValue.toFixed(2)} - ${maxValue.toFixed(2)}`;
        
        // Apply filters
        this.applyQuickFilters();
    }

    clearQuickFilters() {
        // Reset quick filter controls
        document.getElementById('customer-status-filter').value = '';
        document.getElementById('cta-inserted-filter').checked = false;
        document.getElementById('needs-review-filter').checked = false;
        document.getElementById('risk-score-min').value = 0;
        document.getElementById('risk-score-max').value = 100;
        document.getElementById('risk-score-value').textContent = '0.0 - 1.0';
        
        // Clear persistent filters
        this.currentQuickFilters = null;
        
        // Clear all custom filters
        $.fn.dataTable.ext.search = [];
        
        // Redraw table
        if (this.dataTable) {
            this.dataTable.draw();
        }
        
        // Hide active filters display
        document.getElementById('active-filters-display').style.display = 'none';
    }

    updateActiveFiltersDisplay() {
        const activeFilters = [];
        const display = document.getElementById('active-filters-display');
        const text = document.getElementById('active-filters-text');
        
        // Check Customer Status
        const customerStatus = document.getElementById('customer-status-filter').value;
        if (customerStatus) {
            activeFilters.push(`Customer Status: ${customerStatus}`);
        }
        
        // Check Risk Score
        const riskMin = parseFloat(document.getElementById('risk-score-min').value) / 100;
        const riskMax = parseFloat(document.getElementById('risk-score-max').value) / 100;
        if (riskMin > 0 || riskMax < 1) {
            activeFilters.push(`Risk Score: ${riskMin.toFixed(2)} - ${riskMax.toFixed(2)}`);
        }
        
        // Check CTA Filter
        if (document.getElementById('cta-inserted-filter').checked) {
            activeFilters.push('CTA Inserted');
        }
        
        // Check Needs Review
        if (document.getElementById('needs-review-filter').checked) {
            activeFilters.push('Needs Review');
        }
        
        // Update display
        if (activeFilters.length > 0) {
            text.textContent = activeFilters.join(' | ');
            display.style.display = 'block';
        } else {
            display.style.display = 'none';
        }
    }

    onSearchChange() {
        if (this.dataTable) {
            this.dataTable.ajax.reload();
        }
    }

    // Advanced Filter Functions
    applyFilters() {
        // Get values from advanced filter inputs
        const searchValue = document.getElementById('search-input')?.value || '';
        const dateFrom = document.getElementById('date-from')?.value || '';
        const dateTo = document.getElementById('date-to')?.value || '';
        const userId = document.getElementById('user-id-filter')?.value || '';

        // Store filter values for DataTable ajax reload
        this.currentFilters = {
            search: searchValue,
            date_from: dateFrom,
            date_to: dateTo,
            user_id: userId
        };

        // Reload the DataTable with new filters
        if (this.dataTable) {
            this.dataTable.ajax.reload();
        }

        this.showToast('Filters applied', 'success');
    }

    clearFilters() {
        // Clear all filter inputs
        const searchInput = document.getElementById('search-input');
        const dateFromInput = document.getElementById('date-from');
        const dateToInput = document.getElementById('date-to');
        const userIdInput = document.getElementById('user-id-filter');

        if (searchInput) searchInput.value = '';
        if (dateFromInput) dateFromInput.value = '';
        if (dateToInput) dateToInput.value = '';
        if (userIdInput) userIdInput.value = '';

        // Clear stored filters
        this.currentFilters = null;

        // Also clear quick filters
        this.clearQuickFilters();

        // Reload the DataTable
        if (this.dataTable) {
            this.dataTable.ajax.reload();
        }

        this.showToast('All filters cleared', 'info');
    }

    // Backup Functions
    createBackup() {
        const modal = new bootstrap.Modal(document.getElementById('createBackupModal'));
        modal.show();
    }

    async executeBackup() {
        try {
            const name = document.getElementById('backup-name').value;
            const includeData = document.getElementById('include-data').checked;
            const compress = document.getElementById('compress-backup').checked;

            this.showProgress('Creating backup...', 0);

            const response = await this.apiCall('/api/analytics/backup', 'POST', {
                name: name || null,
                include_data: includeData,
                compress: compress
            });

            this.updateProgress('Backup created successfully!', 100);
            
            setTimeout(() => {
                this.hideProgress();
                bootstrap.Modal.getInstance(document.getElementById('createBackupModal')).hide();
                this.loadBackups();
                this.showToast('Backup created successfully', 'success');
            }, 1000);

        } catch (error) {
            console.error('Error creating backup:', error);
            this.hideProgress();
            this.showToast('Error creating backup: ' + error.message, 'error');
        }
    }

    restoreBackup(backupId, backupName) {
        this.currentBackupId = backupId;
        
        // Update modal content
        document.getElementById('restore-backup-name').textContent = backupName;
        
        const modal = new bootstrap.Modal(document.getElementById('restoreBackupModal'));
        modal.show();
    }

    async executeRestore() {
        try {
            this.showProgress('Restoring backup...', 0);

            const response = await this.apiCall(`/api/analytics/restore/${this.currentBackupId}`, 'POST');

            this.updateProgress('Backup restored successfully!', 100);
            
            setTimeout(() => {
                this.hideProgress();
                bootstrap.Modal.getInstance(document.getElementById('restoreBackupModal')).hide();
                this.showToast('Backup restored successfully', 'success');
                
                // Refresh all data
                this.loadOverviewData();
                if (this.dataTable) {
                    this.dataTable.ajax.reload();
                }
            }, 1000);

        } catch (error) {
            console.error('Error restoring backup:', error);
            this.hideProgress();
            this.showToast('Error restoring backup: ' + error.message, 'error');
        }
    }

    // Data Management Functions
    toggleCleanupInputs() {
        const rangeInputs = document.getElementById('date-range-inputs');
        const isRangeSelected = document.getElementById('date-range').checked;
        
        if (rangeInputs) {
            rangeInputs.style.display = isRangeSelected ? 'block' : 'none';
        }
    }

    async previewCleanup() {
        try {
            const cleanupType = document.querySelector('input[name="cleanup-type"]:checked').value;
            const data = { test_data_only: cleanupType === 'test', confirm: false };
            
            if (cleanupType === 'range') {
                const dateFrom = document.getElementById('cleanup-date-from').value;
                const dateTo = document.getElementById('cleanup-date-to').value;
                
                // Only include dates if they're not empty
                if (dateFrom) data.date_from = dateFrom;
                if (dateTo) data.date_to = dateTo;
                
                data.test_data_only = false;
            }

            const response = await this.apiCall('/api/analytics/clean', 'POST', data);
            
            const preview = document.getElementById('cleanup-preview');
            preview.style.display = 'block';
            preview.innerHTML = `
                <div class="alert alert-warning">
                    <h6>Cleanup Preview</h6>
                    <ul class="mb-0">
                        <li><strong>${response.records_to_delete}</strong> records will be deleted</li>
                        <li>Date range: ${response.oldest} to ${response.newest}</li>
                    </ul>
                </div>
            `;

        } catch (error) {
            console.error('Error previewing cleanup:', error);
            this.showToast('Error previewing cleanup: ' + error.message, 'error');
        }
    }

    async executeCleanup() {
        if (!confirm('Are you sure you want to execute this cleanup? This action cannot be undone.')) {
            return;
        }

        try {
            const cleanupType = document.querySelector('input[name="cleanup-type"]:checked').value;
            const data = { test_data_only: cleanupType === 'test', confirm: true };
            
            if (cleanupType === 'range') {
                const dateFrom = document.getElementById('cleanup-date-from').value;
                const dateTo = document.getElementById('cleanup-date-to').value;
                
                // Only include dates if they're not empty
                if (dateFrom) data.date_from = dateFrom;
                if (dateTo) data.date_to = dateTo;
                
                data.test_data_only = false;
            }

            this.showProgress('Cleaning data...', 0);

            const response = await this.apiCall('/api/analytics/clean', 'POST', data);

            this.updateProgress('Data cleaned successfully!', 100);
            
            setTimeout(() => {
                this.hideProgress();
                this.showToast(`Deleted ${response.deleted_count} records`, 'success');
                
                // Refresh data
                this.loadOverviewData();
                if (this.dataTable) {
                    this.dataTable.ajax.reload();
                }
            }, 1000);

        } catch (error) {
            console.error('Error executing cleanup:', error);
            this.hideProgress();
            this.showToast('Error executing cleanup: ' + error.message, 'error');
        }
    }

    // Export Functions
    async exportData() {
        try {
            const format = 'csv'; // Default format
            const params = new URLSearchParams({
                format: format,
                date_from: document.getElementById('date-from')?.value || '',
                date_to: document.getElementById('date-to')?.value || '',
                user_id: document.getElementById('user-id-filter')?.value || ''
            });

            // Remove empty parameters
            for (let [key, value] of [...params]) {
                if (!value) {
                    params.delete(key);
                }
            }

            const url = `${this.API_BASE}/api/analytics/export?${params}`;
            
            // Debug: Log the API key being used
            console.log('exportData() - Using API Key:', this.API_KEY);
            console.log('exportData() - Full Authorization header:', `Bearer ${this.API_KEY}`);
            
            // Use fetch with proper authorization header
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.API_KEY}`
                }
            });

            if (!response.ok) {
                throw new Error(`Export failed: ${response.status} ${response.statusText}`);
            }

            // Get the blob and create download
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            
            // Create and trigger download
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = `nadia_export_${new Date().toISOString().split('T')[0]}.${format}`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            // Clean up the blob URL
            window.URL.revokeObjectURL(downloadUrl);
            
            this.showToast('Export completed', 'success');

        } catch (error) {
            console.error('Error exporting data:', error);
            this.showToast('Error exporting data: ' + error.message, 'error');
        }
    }

    async exportFullData() {
        try {
            const format = document.getElementById('export-format').value;
            const params = new URLSearchParams({
                format: format,
                date_from: document.getElementById('export-date-from')?.value || '',
                date_to: document.getElementById('export-date-to')?.value || ''
            });

            // Remove empty parameters
            for (let [key, value] of [...params]) {
                if (!value) {
                    params.delete(key);
                }
            }

            const url = `${this.API_BASE}/api/analytics/export?${params}`;
            
            // Use fetch with proper authorization header
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${this.API_KEY}`
                }
            });

            if (!response.ok) {
                throw new Error(`Export failed: ${response.status} ${response.statusText}`);
            }

            // Get the blob and create download
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            
            // Create and trigger download
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = `nadia_export_${new Date().toISOString().split('T')[0]}.${format}`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            // Clean up the blob URL
            window.URL.revokeObjectURL(downloadUrl);
            
            this.showToast('Export completed', 'success');

        } catch (error) {
            console.error('Error exporting data:', error);
            this.showToast('Error exporting data: ' + error.message, 'error');
        }
    }

    // UI Helper Functions
    viewDetails(id) {
        this.showToast('Detail view not implemented yet', 'info');
    }

    async viewFullDetails(id) {
        try {
            this.showLoading();
            
            // Get the full record data from the current table data
            const tableData = this.dataTable.data().toArray();
            const record = tableData.find(row => row.id === id);
            
            if (!record) {
                this.showToast('Record not found', 'error');
                return;
            }
            
            this.renderFullDetailsModal(record);
            
            const modal = new bootstrap.Modal(document.getElementById('fullDetailsModal'));
            modal.show();
            
        } catch (error) {
            console.error('Error viewing full details:', error);
            this.showToast('Error loading details: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    renderFullDetailsModal(record) {
        // Update modal title
        document.getElementById('detail-record-id').textContent = `User ${record.user_id} - Message #${record.id}`;
        
        // SECCIÓN 1: Timeline
        this.renderTimeline(record);
        
        // SECCIÓN 2: Message Evolution
        this.renderMessageEvolution(record);
        
        // SECCIÓN 3: Analysis
        this.renderAnalysisSection(record);
        
        // SECCIÓN 4: Customer Journey
        this.renderCustomerJourney(record);
        
        // Store current record for export
        this.currentDetailRecord = record;
    }

    renderTimeline(record) {
        const timeline = [];
        
        // Message received
        if (record.user_message_timestamp || record.created_at) {
            timeline.push({
                time: new Date(record.user_message_timestamp || record.created_at),
                icon: 'fas fa-envelope',
                color: 'primary',
                title: 'Message Received',
                content: `User ${record.user_id} sent message`
            });
        }
        
        // LLM1 Processing
        if (record.llm1_model) {
            const processingTime = record.llm1_tokens_used ? 
                `${(record.llm1_tokens_used / 50).toFixed(1)}s` : 'N/A';
            timeline.push({
                time: new Date(record.created_at),
                icon: 'fas fa-robot',
                color: 'info',
                title: 'Processed by LLM1',
                content: `${record.llm1_model} - Processing time: ${processingTime}`
            });
        }
        
        // LLM2 Processing
        if (record.llm2_model) {
            const processingTime = record.llm2_tokens_used ? 
                `${(record.llm2_tokens_used / 50).toFixed(1)}s` : 'N/A';
            timeline.push({
                time: new Date(record.created_at),
                icon: 'fas fa-magic',
                color: 'warning',
                title: 'Refined by LLM2',
                content: `${record.llm2_model} - Processing time: ${processingTime}`
            });
        }
        
        // Human Review
        if (record.review_started_at && record.reviewer_id) {
            timeline.push({
                time: new Date(record.review_started_at),
                icon: 'fas fa-user-edit',
                color: 'secondary',
                title: 'Review Started',
                content: `Reviewer: ${record.reviewer_id}`
            });
        }
        
        if (record.review_completed_at) {
            timeline.push({
                time: new Date(record.review_completed_at),
                icon: 'fas fa-check-circle',
                color: 'success',
                title: 'Review Completed',
                content: `Review time: ${this.formatReviewTime(record.review_time_seconds)}`
            });
        }
        
        // Message Sent
        if (record.messages_sent_at) {
            timeline.push({
                time: new Date(record.messages_sent_at),
                icon: 'fas fa-paper-plane',
                color: 'success',
                title: 'Message Sent',
                content: 'Final message delivered to user'
            });
        }
        
        // Sort timeline by time
        timeline.sort((a, b) => a.time - b.time);
        
        // Render timeline
        const container = document.getElementById('timeline-section');
        container.innerHTML = timeline.map(item => `
            <div class="timeline-item">
                <div class="timeline-time">${item.time.toLocaleTimeString()}</div>
                <div class="timeline-content">
                    <i class="${item.icon} text-${item.color} me-2"></i>
                    <strong>${item.title}</strong><br>
                    <small class="text-muted">${item.content}</small>
                </div>
            </div>
        `).join('');
    }

    renderMessageEvolution(record) {
        // User Message
        document.getElementById('evolution-user').innerHTML = `
            <div class="text-dark">${record.user_message || '<span class="text-muted">No message</span>'}</div>
        `;
        
        // LLM1 Response
        document.getElementById('evolution-llm1').innerHTML = `
            <div class="text-secondary">${record.llm1_raw_response || '<span class="text-muted">No response</span>'}</div>
        `;
        
        // LLM2 Bubbles
        const llm2Bubbles = this.parseBubbles(record.llm2_bubbles);
        document.getElementById('evolution-llm2').innerHTML = llm2Bubbles.length > 0 ?
            llm2Bubbles.map((bubble, idx) => `
                <div class="bubble-item">
                    <small class="text-muted">Bubble ${idx + 1}:</small><br>
                    ${bubble}
                </div>
            `).join('') : '<span class="text-muted">No bubbles</span>';
        
        // Final Version
        const finalBubbles = this.parseBubbles(record.final_bubbles);
        document.getElementById('evolution-final').innerHTML = finalBubbles.length > 0 ?
            finalBubbles.map((bubble, idx) => `
                <div class="bubble-item bg-success bg-opacity-10">
                    <small class="text-muted">Bubble ${idx + 1}:</small><br>
                    ${bubble}
                </div>
            `).join('') : '<span class="text-muted">No final version</span>';
        
        // Edit Tags
        if (record.edit_tags && record.edit_tags.length > 0) {
            document.getElementById('evolution-edits').innerHTML = `
                <small class="text-muted">Edits Applied:</small><br>
                ${record.edit_tags.map(tag => {
                    const color = this.getTagColor(tag);
                    return `<span class="badge ${color} me-1">${tag}</span>`;
                }).join('')}
            `;
        } else {
            document.getElementById('evolution-edits').innerHTML = '';
        }
    }

    renderAnalysisSection(record) {
        // Risk Score
        const riskScore = parseFloat(record.constitution_risk_score) || 0;
        document.getElementById('risk-score-label').textContent = riskScore.toFixed(2);
        document.getElementById('risk-score-text').textContent = riskScore.toFixed(2);
        
        const riskBar = document.getElementById('risk-score-bar');
        riskBar.style.width = `${riskScore * 100}%`;
        riskBar.className = 'progress-bar';
        
        if (riskScore < 0.3) {
            riskBar.classList.add('bg-success');
        } else if (riskScore < 0.7) {
            riskBar.classList.add('bg-warning');
        } else {
            riskBar.classList.add('bg-danger');
        }
        
        // Risk Flags
        const flagsContainer = document.getElementById('risk-flags');
        if (record.constitution_flags && record.constitution_flags.length > 0) {
            flagsContainer.innerHTML = `
                <label class="form-label">Risk Flags:</label>
                <div>
                    ${record.constitution_flags.map(flag => 
                        `<span class="badge bg-warning text-dark me-1 mb-1">${flag}</span>`
                    ).join('')}
                </div>
            `;
        } else {
            flagsContainer.innerHTML = `
                <label class="form-label">Risk Flags:</label>
                <div><span class="badge bg-success">No flags detected</span></div>
            `;
        }
        
        // Quality Stars
        document.getElementById('quality-stars').innerHTML = this.renderQualityStars(record.quality_score);
        
        // Cost Breakdown
        const llm1Cost = parseFloat(record.llm1_cost_usd) || 0;
        const llm2Cost = parseFloat(record.llm2_cost_usd) || 0;
        const totalCost = llm1Cost + llm2Cost;
        
        document.getElementById('cost-llm1-model').textContent = record.llm1_model || 'N/A';
        document.getElementById('cost-llm1-amount').textContent = `$${llm1Cost.toFixed(6)}`;
        document.getElementById('cost-llm2-model').textContent = record.llm2_model || 'N/A';
        document.getElementById('cost-llm2-amount').textContent = `$${llm2Cost.toFixed(6)}`;
        document.getElementById('cost-total').textContent = `$${totalCost.toFixed(6)}`;
    }

    renderCustomerJourney(record) {
        // Customer Status
        document.getElementById('customer-status-display').innerHTML = 
            this.renderCustomerStatusBadge(record.customer_status);
        
        // LTV
        const ltv = parseFloat(record.ltv_usd) || 0;
        document.getElementById('customer-ltv').textContent = `$${ltv.toFixed(2)}`;
        
        // CTA History
        const ctaHistory = [];
        
        // Add sent CTAs
        if (record.cta_data && record.cta_data.type) {
            ctaHistory.push({
                time: record.created_at,
                type: 'sent',
                content: `${record.cta_data.type} CTA ${record.cta_data.inserted ? 'inserted' : 'suggested'}`,
                icon: 'fas fa-bullhorn'
            });
        }
        
        // Add CTA responses
        if (record.cta_response_type) {
            ctaHistory.push({
                time: record.updated_at || record.created_at,
                type: 'response',
                content: `User response: ${record.cta_response_type.replace('_', ' ')}`,
                icon: this.getCTAResponseIcon(record.cta_response_type)
            });
        }
        
        // Add other CTAs from history
        if (record.cta_sent_count > 0) {
            ctaHistory.push({
                time: record.last_cta_sent_at,
                type: 'info',
                content: `Total CTAs sent to this user: ${record.cta_sent_count}`,
                icon: 'fas fa-info-circle'
            });
        }
        
        // Render CTA history
        const ctaContainer = document.getElementById('cta-history');
        if (ctaHistory.length > 0) {
            ctaContainer.innerHTML = ctaHistory.map(event => `
                <div class="cta-event ${event.type}">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <i class="${event.icon} me-2"></i>
                            <strong>${event.content}</strong>
                        </div>
                        <small class="text-muted">${event.time ? new Date(event.time).toLocaleDateString() : ''}</small>
                    </div>
                </div>
            `).join('');
        } else {
            ctaContainer.innerHTML = '<div class="text-muted">No CTA history available</div>';
        }
    }

    parseBubbles(bubbles) {
        if (!bubbles) return [];
        if (Array.isArray(bubbles)) return bubbles;
        
        try {
            const parsed = JSON.parse(bubbles);
            return Array.isArray(parsed) ? parsed : [bubbles];
        } catch {
            return [bubbles];
        }
    }

    getTagColor(tag) {
        if (tag.startsWith('TONE_')) return 'bg-info';
        if (tag.startsWith('STRUCT_')) return 'bg-warning text-dark';
        if (tag.startsWith('CONTENT_')) return 'bg-success';
        if (tag.startsWith('ENGLISH_')) return 'bg-primary';
        if (tag.startsWith('CTA_')) return 'bg-danger';
        return 'bg-secondary';
    }

    getCTAResponseIcon(response) {
        const icons = {
            'IGNORED': 'fas fa-eye-slash',
            'POLITE_DECLINE': 'fas fa-hand-paper',
            'INTERESTED': 'fas fa-heart',
            'CONVERTED': 'fas fa-dollar-sign',
            'RUDE_DECLINE': 'fas fa-times'
        };
        return icons[response] || 'fas fa-question';
    }

    // Helper functions for rendering specific elements
    renderCustomerStatusBadge(status) {
        if (!status) return '<span class="badge bg-secondary">UNKNOWN</span>';
        const statusConfig = {
            'PROSPECT': { bg: 'bg-secondary', icon: 'fas fa-user' },
            'LEAD_QUALIFIED': { bg: 'bg-success', icon: 'fas fa-star' },
            'CUSTOMER': { bg: 'bg-warning text-dark', icon: 'fas fa-crown' },
            'CHURNED': { bg: 'bg-danger', icon: 'fas fa-user-times' },
            'LEAD_EXHAUSTED': { bg: 'bg-dark', icon: 'fas fa-ban' }
        };
        const config = statusConfig[status] || { bg: 'bg-secondary', icon: 'fas fa-question' };
        return `<span class="badge ${config.bg}"><i class="${config.icon} me-1"></i>${status.replace('_', ' ')}</span>`;
    }

    renderReviewStatusBadge(status) {
        if (!status) return '<span class="badge bg-light text-dark">--</span>';
        const statusConfig = {
            'pending': { bg: 'bg-warning', icon: 'fas fa-clock' },
            'reviewing': { bg: 'bg-info', icon: 'fas fa-eye' },
            'approved': { bg: 'bg-success', icon: 'fas fa-check' },
            'rejected': { bg: 'bg-danger', icon: 'fas fa-times' }
        };
        const config = statusConfig[status] || { bg: 'bg-secondary', icon: 'fas fa-question' };
        return `<span class="badge ${config.bg}"><i class="${config.icon} me-1"></i>${status.toUpperCase()}</span>`;
    }

    formatBubbles(bubbles) {
        if (!bubbles) return '<span class="text-muted">--</span>';
        
        try {
            const bubbleArray = Array.isArray(bubbles) ? bubbles : JSON.parse(bubbles);
            return bubbleArray.map((bubble, index) => 
                `<div class="border-start border-primary border-3 ps-2 mb-2">
                    <small class="text-muted">Bubble ${index + 1}:</small><br>
                    ${bubble}
                </div>`
            ).join('');
        } catch {
            return `<div class="border-start border-primary border-3 ps-2">${bubbles}</div>`;
        }
    }

    renderRiskScore(score) {
        if (score === null || score === undefined) return '--';
        const scoreNum = parseFloat(score);
        let color = 'success';
        if (scoreNum >= 0.7) color = 'danger';
        else if (scoreNum >= 0.3) color = 'warning';
        
        return `<span class="badge bg-${color}">${scoreNum.toFixed(2)}</span>`;
    }

    renderConstitutionRecommendation(rec) {
        if (!rec) return '--';
        const config = {
            'approve': { bg: 'bg-success', icon: 'fas fa-check' },
            'review': { bg: 'bg-warning text-dark', icon: 'fas fa-exclamation-triangle' },
            'flag': { bg: 'bg-danger', icon: 'fas fa-flag' }
        };
        const conf = config[rec.toLowerCase()] || { bg: 'bg-secondary', icon: 'fas fa-question' };
        return `<span class="badge ${conf.bg}"><i class="${conf.icon} me-1"></i>${rec.toUpperCase()}</span>`;
    }

    renderConstitutionFlags(flags) {
        if (!flags || !Array.isArray(flags) || flags.length === 0) {
            return '<span class="badge bg-success">No flags</span>';
        }
        
        return flags.map(flag => 
            `<span class="badge bg-warning text-dark me-1">${flag}</span>`
        ).join('');
    }

    renderQualityStars(score) {
        if (!score) return '--';
        const stars = '★'.repeat(score) + '☆'.repeat(5 - score);
        const color = score >= 4 ? 'text-success' : score >= 3 ? 'text-warning' : 'text-danger';
        return `<span class="${color}">${stars} (${score}/5)</span>`;
    }

    formatReviewTime(seconds) {
        if (!seconds) return '--';
        const sec = parseInt(seconds);
        if (sec < 60) return `${sec}s`;
        const min = Math.floor(sec / 60);
        const remainingSec = sec % 60;
        return `${min}m ${remainingSec}s`;
    }

    renderCTAResponse(response) {
        if (!response) return '--';
        const config = {
            'IGNORED': { bg: 'bg-secondary', icon: 'fas fa-eye-slash' },
            'POLITE_DECLINE': { bg: 'bg-warning text-dark', icon: 'fas fa-hand-paper' },
            'INTERESTED': { bg: 'bg-info', icon: 'fas fa-heart' },
            'CONVERTED': { bg: 'bg-success', icon: 'fas fa-dollar-sign' },
            'RUDE_DECLINE': { bg: 'bg-danger', icon: 'fas fa-times' }
        };
        const conf = config[response] || { bg: 'bg-secondary', icon: 'fas fa-question' };
        return `<span class="badge ${conf.bg}"><i class="${conf.icon} me-1"></i>${response.replace('_', ' ')}</span>`;
    }

    renderCTAData(data) {
        if (!data) return '<span class="text-muted">No CTA data</span>';
        
        return `<pre class="bg-light p-2 rounded"><code>${JSON.stringify(data, null, 2)}</code></pre>`;
    }

    renderEditTagsFull(tags) {
        if (!tags || !Array.isArray(tags) || tags.length === 0) {
            return '<div class="alert alert-info">No edits were made to this message.</div>';
        }
        
        const tagsByCategory = {
            'TONE_': [],
            'STRUCT_': [],
            'CONTENT_': [],
            'ENGLISH_': [],
            'CTA_': [],
            'OTHER': []
        };
        
        tags.forEach(tag => {
            const category = Object.keys(tagsByCategory).find(cat => tag.startsWith(cat)) || 'OTHER';
            tagsByCategory[category].push(tag);
        });
        
        const categoryNames = {
            'TONE_': 'Tone Adjustments',
            'STRUCT_': 'Structure Changes',
            'CONTENT_': 'Content Modifications',
            'ENGLISH_': 'Language/Style',
            'CTA_': 'Call-to-Action',
            'OTHER': 'Other'
        };
        
        const colors = {
            'TONE_': 'info',
            'STRUCT_': 'warning',
            'CONTENT_': 'success',
            'ENGLISH_': 'primary',
            'CTA_': 'danger',
            'OTHER': 'secondary'
        };
        
        let html = '';
        Object.keys(tagsByCategory).forEach(category => {
            if (tagsByCategory[category].length > 0) {
                html += `
                    <div class="mb-3">
                        <h6 class="text-${colors[category]}">${categoryNames[category]}</h6>
                        <div class="d-flex flex-wrap gap-1">
                            ${tagsByCategory[category].map(tag => 
                                `<span class="badge bg-${colors[category]} bg-opacity-75">${tag}</span>`
                            ).join('')}
                        </div>
                    </div>
                `;
            }
        });
        
        return html || '<div class="alert alert-info">No categorized tags found.</div>';
    }

    exportSingleRecord() {
        if (!this.currentDetailRecord) {
            this.showToast('No record selected for export', 'error');
            return;
        }
        
        const data = JSON.stringify(this.currentDetailRecord, null, 2);
        const blob = new Blob([data], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const link = document.createElement('a');
        link.href = url;
        link.download = `nadia_record_${this.currentDetailRecord.id}_${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        URL.revokeObjectURL(url);
        this.showToast('Record exported successfully', 'success');
    }

    viewBackupDetails(backupId) {
        this.showToast('Backup details not implemented yet', 'info');
    }

    async deleteBackup(backupId) {
        if (!confirm('Are you sure you want to delete this backup? This action cannot be undone.')) {
            return;
        }

        try {
            await this.apiCall(`/api/analytics/backups/${backupId}`, 'DELETE');
            this.showToast('Backup deleted successfully', 'success');
            // Refresh the backups list
            this.loadBackups();
        } catch (error) {
            console.error('Error deleting backup:', error);
            this.showToast('Error deleting backup: ' + error.message, 'error');
        }
    }

    startAutoRefresh() {
        // Refresh every 30 seconds
        this.refreshInterval = setInterval(() => {
            this.showAutoRefreshIndicator();
            
            // Only refresh if on overview tab
            const activeTab = document.querySelector('.nav-link.active');
            if (activeTab && activeTab.getAttribute('data-bs-target') === '#overview') {
                this.loadOverviewData();
            }
            
            setTimeout(() => this.hideAutoRefreshIndicator(), 2000);
        }, 30000);
    }

    showAutoRefreshIndicator() {
        const indicator = document.querySelector('.auto-refresh-indicator');
        if (indicator) {
            indicator.classList.add('show');
        }
    }

    hideAutoRefreshIndicator() {
        const indicator = document.querySelector('.auto-refresh-indicator');
        if (indicator) {
            indicator.classList.remove('show');
        }
    }

    showLoading() {
        const spinner = document.querySelector('.loading-spinner');
        if (spinner) {
            spinner.style.display = 'block';
        }
    }

    hideLoading() {
        const spinner = document.querySelector('.loading-spinner');
        if (spinner) {
            spinner.style.display = 'none';
        }
    }

    showProgress(message, progress) {
        const modal = new bootstrap.Modal(document.getElementById('progressModal'));
        document.getElementById('progress-message').textContent = message;
        document.getElementById('progress-bar').style.width = progress + '%';
        modal.show();
    }

    updateProgress(message, progress) {
        document.getElementById('progress-message').textContent = message;
        document.getElementById('progress-bar').style.width = progress + '%';
    }

    hideProgress() {
        const modal = bootstrap.Modal.getInstance(document.getElementById('progressModal'));
        if (modal) {
            modal.hide();
        }
    }

    updateLastUpdated() {
        const element = document.getElementById('last-updated');
        if (element) {
            element.textContent = new Date().toLocaleTimeString();
        }
    }

    resizeCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart && chart.resize) {
                chart.resize();
            }
        });
    }

    // Theme Functions
    toggleTheme() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        this.applyTheme();
        localStorage.setItem('theme', this.theme);
    }

    applyTheme() {
        const icon = document.getElementById('theme-icon');
        if (this.theme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
            if (icon) icon.className = 'fas fa-sun';
        } else {
            document.documentElement.removeAttribute('data-theme');
            if (icon) icon.className = 'fas fa-moon';
        }
    }

    // Keyboard Shortcuts
    handleKeyboardShortcuts(e) {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 'r':
                    e.preventDefault();
                    this.loadOverviewData();
                    break;
                case 'f':
                    e.preventDefault();
                    document.getElementById('search-input')?.focus();
                    break;
                case 'e':
                    e.preventDefault();
                    this.exportData();
                    break;
            }
        }
    }

    // Utility Functions
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

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    showToast(message, type = 'info') {
        const container = document.querySelector('.toast-container');
        if (!container) return;

        const toastId = 'toast-' + Date.now();
        const bgClass = {
            'success': 'bg-success',
            'error': 'bg-danger',
            'warning': 'bg-warning',
            'info': 'bg-info'
        }[type] || 'bg-info';

        const toastHtml = `
            <div class="toast ${bgClass} text-white" id="${toastId}" role="alert">
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', toastHtml);
        
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { delay: 5000 });
        toast.show();
        
        // Clean up after toast is hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }

    // === REVIEWER NOTES EDITING METHODS ===
    
    editReviewerNotes(interactionId, currentNotes) {
        // Prevent table click event from firing
        event.stopPropagation();
        
        // Find the cell containing this notes display
        const cell = event.target.closest('.reviewer-notes-cell');
        if (!cell) return;
        
        // Store original content for cancel functionality
        const originalContent = cell.innerHTML;
        
        // Clean up the notes (decode HTML entities)
        const decodedNotes = currentNotes.replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&');
        
        // Store original content in a data attribute
        cell.setAttribute('data-original-content', originalContent);
        
        // Create edit interface
        cell.innerHTML = `
            <textarea class="reviewer-notes-input" placeholder="Add your review notes...">${decodedNotes}</textarea>
            <div class="reviewer-notes-actions">
                <button class="btn-save-notes" onclick="analytics.saveReviewerNotes('${interactionId}', this)">
                    <i class="fas fa-check me-1"></i>Save
                </button>
                <button class="btn-cancel-notes" onclick="analytics.cancelEditReviewerNotes(this)">
                    <i class="fas fa-times me-1"></i>Cancel
                </button>
            </div>
        `;
        
        // Focus on textarea
        const textarea = cell.querySelector('.reviewer-notes-input');
        textarea.focus();
        textarea.setSelectionRange(textarea.value.length, textarea.value.length);
        
        // Handle Enter+Ctrl to save
        textarea.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                this.saveReviewerNotes(interactionId, textarea.parentNode.querySelector('.btn-save-notes'));
            } else if (e.key === 'Escape') {
                this.cancelEditReviewerNotes(textarea.parentNode.querySelector('.btn-cancel-notes'));
            }
        });
    }
    
    async saveReviewerNotes(interactionId, buttonElement) {
        const cell = buttonElement.closest('.reviewer-notes-cell');
        const textarea = cell.querySelector('.reviewer-notes-input');
        const newNotes = textarea.value.trim();
        
        try {
            // Show loading state
            buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';
            buttonElement.disabled = true;
            
            // Make API call to update notes
            await this.apiCall(`/interactions/${interactionId}/reviewer-notes`, 'POST', {
                reviewer_notes: newNotes
            });
            
            // Update the display
            const isEmpty = !newNotes;
            const shortNotes = newNotes.length > 50 ? newNotes.substring(0, 50) + '...' : newNotes;
            
            cell.innerHTML = `
                <div class="reviewer-notes-display ${isEmpty ? 'empty' : ''}" 
                     onclick="analytics.editReviewerNotes('${interactionId}', '${newNotes.replace(/'/g, '&#39;')}')"
                     title="${newNotes || 'Click to add reviewer notes'}">
                    ${isEmpty ? 'Click to add notes...' : shortNotes}
                </div>
            `;
            
            // Update the DataTable data
            if (this.dataTable) {
                const rowData = this.dataTable.row(cell.closest('tr')).data();
                rowData.reviewer_notes = newNotes;
                this.dataTable.row(cell.closest('tr')).data(rowData).draw(false);
            }
            
            this.showToast('Reviewer notes updated successfully', 'success');
            
        } catch (error) {
            console.error('Error updating reviewer notes:', error);
            this.showToast('Failed to update reviewer notes', 'error');
            
            // Reset button state
            buttonElement.innerHTML = '<i class="fas fa-check me-1"></i>Save';
            buttonElement.disabled = false;
        }
    }
    
    cancelEditReviewerNotes(buttonElement) {
        const cell = buttonElement.closest('.reviewer-notes-cell');
        // Get the original content from data attribute
        const originalContent = cell.getAttribute('data-original-content');
        cell.innerHTML = originalContent;
        // Remove the data attribute to clean up
        cell.removeAttribute('data-original-content');
    }

    // === INTEGRITY REPORT METHODS ===
    
    async loadIntegrityReport() {
        try {
            this.showLoading();
            const report = await this.apiCall('/api/analytics/integrity');
            this.displayIntegrityReport(report);
        } catch (error) {
            console.error('Error loading integrity report:', error);
            this.showToast('Error loading integrity report', 'error');
        } finally {
            this.hideLoading();
        }
    }

    async refreshIntegrity() {
        await this.loadIntegrityReport();
        this.showToast('Integrity report refreshed', 'success');
    }

    displayIntegrityReport(report) {
        // Update summary cards
        document.getElementById('schema-health').textContent = report.summary.schema_health;
        document.getElementById('data-health').textContent = report.summary.data_health;
        document.getElementById('alert-count').textContent = report.summary.total_alerts;
        document.getElementById('last-check').textContent = new Date(report.timestamp).toLocaleTimeString();

        // Update alert count color
        const alertElement = document.getElementById('alert-count');
        const alertCard = alertElement.closest('.metric-card');
        if (report.summary.critical_issues > 0) {
            alertCard.classList.add('border-danger');
            alertElement.className = 'fw-bold text-danger mb-1';
        } else if (report.summary.warnings > 0) {
            alertCard.classList.add('border-warning');
            alertElement.className = 'fw-bold text-warning mb-1';
        } else {
            alertCard.classList.add('border-success');
            alertElement.className = 'fw-bold text-success mb-1';
        }

        // Display alerts
        this.displayIntegrityAlerts(report.alerts);

        // Display data quality metrics
        this.displayDataQualityMetrics(report.data_quality);

        // Display schema check
        this.displaySchemaCheck(report.schema_check);

        // Display transformations
        this.displayTransformations(report.transformations);
    }

    displayIntegrityAlerts(alerts) {
        const container = document.getElementById('integrity-alerts');
        if (!container) return;

        if (alerts.length === 0) {
            container.innerHTML = `
                <div class="alert alert-success">
                    <i class="fas fa-check-circle me-2"></i>
                    No integrity issues detected. All systems are operating normally.
                </div>
            `;
            return;
        }

        let alertsHtml = '';
        alerts.forEach(alert => {
            const alertClass = alert.type === 'error' ? 'danger' : 
                              alert.type === 'warning' ? 'warning' : 'success';
            
            alertsHtml += `
                <div class="alert alert-${alertClass} mb-3">
                    <div class="d-flex align-items-start">
                        <span class="me-2" style="font-size: 1.2em;">${alert.icon}</span>
                        <div class="flex-grow-1">
                            <h6 class="alert-heading mb-1">${alert.title}</h6>
                            <p class="mb-1">${alert.message}</p>
                            ${alert.recommendation ? `<small class="text-muted"><strong>Recommendation:</strong> ${alert.recommendation}</small>` : ''}
                            ${alert.details ? `
                                <details class="mt-2">
                                    <summary class="btn btn-sm btn-outline-${alertClass}">View Details</summary>
                                    <pre class="mt-2 p-2 bg-light rounded"><code>${JSON.stringify(alert.details, null, 2)}</code></pre>
                                </details>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = alertsHtml;
    }

    displayDataQualityMetrics(dataQuality) {
        const metrics = dataQuality.metrics;
        const percentages = dataQuality.percentages;
        
        if (!metrics || !percentages) return;

        // Customer Status Completion
        const customerStatusPct = 100 - (percentages.null_customer_status_pct || 0);
        document.getElementById('customer-status-pct').textContent = `${customerStatusPct.toFixed(1)}%`;
        document.getElementById('customer-status-bar').style.width = `${customerStatusPct}%`;

        // First Messages
        document.getElementById('first-messages-pct').textContent = `${percentages.first_messages_pct || 0}%`;
        document.getElementById('first-messages-bar').style.width = `${percentages.first_messages_pct || 0}%`;

        // Approved with Final Output
        const approvedFinalPct = 100 - (percentages.approved_without_final_pct || 0);
        document.getElementById('approved-final-pct').textContent = `${approvedFinalPct.toFixed(1)}%`;
        document.getElementById('approved-final-bar').style.width = `${approvedFinalPct}%`;

        // LLM Model Tracking
        const llmModelsPct = 100 - (percentages.missing_llm_models_pct || 0);
        document.getElementById('llm-models-pct').textContent = `${llmModelsPct.toFixed(1)}%`;
        document.getElementById('llm-models-bar').style.width = `${llmModelsPct}%`;
    }

    displaySchemaCheck(schemaCheck) {
        const container = document.getElementById('schema-check');
        if (!container) return;

        let html = `
            <div class="mb-3">
                <div class="d-flex justify-content-between">
                    <span>Expected Fields:</span>
                    <span class="badge bg-primary">${schemaCheck.total_expected}</span>
                </div>
                <div class="d-flex justify-content-between">
                    <span>Actual Fields:</span>
                    <span class="badge bg-info">${schemaCheck.total_actual}</span>
                </div>
            </div>
        `;

        if (schemaCheck.missing_fields && schemaCheck.missing_fields.length > 0) {
            html += `
                <div class="alert alert-danger p-2 mb-2">
                    <small><strong>Missing Fields (${schemaCheck.missing_fields.length}):</strong></small>
                    <ul class="mb-0 mt-1">
                        ${schemaCheck.missing_fields.map(field => 
                            `<li><code>${field.field}</code> (${field.expected_type})</li>`
                        ).join('')}
                    </ul>
                </div>
            `;
        }

        if (schemaCheck.type_mismatches && schemaCheck.type_mismatches.length > 0) {
            html += `
                <div class="alert alert-warning p-2 mb-2">
                    <small><strong>Type Mismatches (${schemaCheck.type_mismatches.length}):</strong></small>
                    <ul class="mb-0 mt-1">
                        ${schemaCheck.type_mismatches.map(field => 
                            `<li><code>${field.field}</code><br>
                             Expected: ${field.expected_type}<br>
                             Actual: ${field.actual_type}</li>`
                        ).join('')}
                    </ul>
                </div>
            `;
        }

        if (schemaCheck.missing_fields.length === 0 && schemaCheck.type_mismatches.length === 0) {
            html += `
                <div class="alert alert-success p-2">
                    <i class="fas fa-check me-1"></i>
                    <small>All fields match expected schema</small>
                </div>
            `;
        }

        container.innerHTML = html;
    }

    displayTransformations(transformations) {
        const container = document.getElementById('transformations-list');
        if (!container) return;

        if (!transformations || transformations.length === 0) {
            container.innerHTML = `
                <div class="alert alert-info p-2">
                    <small>No data transformations applied</small>
                </div>
            `;
            return;
        }

        let html = '';
        transformations.forEach(transform => {
            const safeClass = transform.safe ? 'success' : 'warning';
            const safeIcon = transform.safe ? 'check' : 'exclamation-triangle';
            
            html += `
                <div class="border rounded p-2 mb-2">
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <small class="fw-bold">${transform.field}</small>
                            <br>
                            <small class="text-muted">${transform.transformation}</small>
                        </div>
                        <span class="badge bg-${safeClass}">
                            <i class="fas fa-${safeIcon}"></i>
                        </span>
                    </div>
                    <small class="text-muted d-block mt-1">
                        Location: ${transform.location}
                    </small>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    // === END INTEGRITY METHODS ===

    async apiCall(endpoint, method = 'GET', data = null) {
        const options = {
            method: method,
            headers: {
                'Authorization': `Bearer ${this.API_KEY}`,
                'Content-Type': 'application/json'
            }
        };

        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(`${this.API_BASE}${endpoint}`, options);
        
        if (!response.ok) {
            const error = await response.text();
            throw new Error(`API Error: ${response.status} - ${error}`);
        }

        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return await response.json();
        } else {
            return await response.blob();
        }
    }
}

// Global Functions (called from HTML)
let analytics;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    analytics = new DataAnalytics();
});

// Global theme toggle function
function toggleTheme() {
    if (analytics) {
        analytics.toggleTheme();
    }
}

// Global functions for HTML onclick handlers
function applyFilters() {
    if (analytics) {
        analytics.applyFilters();
    }
}

function clearFilters() {
    if (analytics) {
        analytics.clearFilters();
    }
}

function exportData() {
    if (analytics) {
        analytics.exportData();
    }
}

function createBackup() {
    if (analytics) {
        analytics.createBackup();
    }
}

function executeBackup() {
    if (analytics) {
        analytics.executeBackup();
    }
}

function executeRestore() {
    if (analytics) {
        analytics.executeRestore();
    }
}

function previewCleanup() {
    if (analytics) {
        analytics.previewCleanup();
    }
}

function executeCleanup() {
    if (analytics) {
        analytics.executeCleanup();
    }
}

function exportFullData() {
    if (analytics) {
        analytics.exportFullData();
    }
}

// Integrity Report Functions
function refreshIntegrity() {
    if (analytics) {
        analytics.refreshIntegrity();
    }
}