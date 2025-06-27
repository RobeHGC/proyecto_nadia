// NADIA HITL Dashboard JavaScript
class HITLDashboard {
    constructor() {
        this.apiBase = 'http://localhost:8000';
        this.apiKey = null; // Will be loaded from server
        this.currentReview = null;
        this.selectedTags = [];
        this.qualityScore = 3;
        this.editTaxonomy = [];
        this.starHandlers = new Map(); // Store star event handlers for cleanup
        this.globalStarListenerAdded = false; // Track if we've added the global listener
        
        // NUEVO: CTA functionality
        this.ctaInserted = null;
        this.ctaTemplates = {
            soft: [
                "btw i have some pics i can't send here 🙈 check my profile",
                "wish we could chat somewhere more private... link in bio",
                "i'm shy about sending certain things here 😳 fanvue.com/nadiagarc",
                "there's so much more i want to show you 😘 find me on fanvue"
            ],
            medium: [
                "i have exclusive content elsewhere 👀 fanvue.com/nadiagarc",
                "my VIP fans get to see way more hehe → fanvue.com/nadiagarc",
                "there's stuff i only show in private 🤫 link: fanvue.com/nadiagarc",
                "i have a special place for my naughtiest content 😏 check fanvue.com/nadiagarc"
            ],
            direct: [
                "check out my Fanvue for more content 💕 https://www.fanvue.com/nadiagarc",
                "link in bio for exclusive stuff 🔥 https://www.fanvue.com/nadiagarc",
                "follow me for content i can't post here 🔞 https://www.fanvue.com/nadiagarc",
                "you can find my spicy content on fanvue 😈 https://www.fanvue.com/nadiagarc"
            ]
        };
        
        this.init();
    }
    
    getAuthHeaders() {
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.apiKey}`
        };
    }
    
    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            if (response.ok) {
                const config = await response.json();
                this.apiKey = config.apiKey;
                this.apiBase = config.apiBase;
            } else {
                // Fallback - should not be needed in production
                console.warn('Failed to load config from server, this is a security issue');
                this.apiKey = 'dev-fallback-key';
            }
        } catch (error) {
            console.error('Failed to load config from server:', error);
            this.apiKey = 'dev-fallback-key';
        }
    }
    
    async init() {
        // Load configuration from server first
        await this.loadConfig();
        await this.loadEditTaxonomy();
        await this.loadMetrics();
        await this.loadReviews();
        this.setupEventListeners();
        // Don't setup stars on init - wait until a review is selected
        
        // Auto-refresh every 30 seconds
        setInterval(() => {
            this.loadMetrics();
            this.loadReviews();
        }, 30000);
    }
    
    async loadEditTaxonomy() {
        try {
            const response = await fetch(`${this.apiBase}/edit-taxonomy`, {
                headers: this.getAuthHeaders()
            });
            this.editTaxonomy = await response.json();
            this.renderTagButtons();
        } catch (error) {
            console.error('Failed to load edit taxonomy:', error);
        }
    }
    
    async loadMetrics() {
        try {
            const response = await fetch(`${this.apiBase}/metrics/dashboard`, {
                headers: this.getAuthHeaders()
            });
            
            if (!response.ok) {
                console.error('Metrics request failed:', response.status, response.statusText);
                return;
            }
            
            const metrics = await response.json();
            
            document.getElementById('pending-count').textContent = metrics.pending_reviews;
            document.getElementById('reviewed-today').textContent = metrics.reviewed_today;
            
            const avgTime = metrics.avg_review_time_seconds;
            const avgTimeFormatted = avgTime > 0 ? `${Math.round(avgTime)}s` : '-';
            document.getElementById('avg-review-time').textContent = avgTimeFormatted;
            
            // Update multi-LLM metrics
            console.log('Metrics received:', {
                quota_used: metrics.gemini_quota_used_today,
                quota_total: metrics.gemini_quota_total,
                savings: metrics.savings_today_usd,
                all_metrics: metrics
            });
            this.updateQuotaDisplay(metrics.gemini_quota_used_today, metrics.gemini_quota_total);
            this.updateSavingsDisplay(metrics.savings_today_usd);
        } catch (error) {
            console.error('Failed to load metrics:', error);
        }
        
        // Load recovery metrics
        this.loadRecoveryMetrics();
        
        // Load coherence metrics
        this.loadCoherenceMetrics();
    }

    // ===============================================
    // RECOVERY AGENT FUNCTIONALITY
    // ===============================================
    
    async loadRecoveryMetrics() {
        try {
            const response = await fetch(`${this.apiBase}/recovery/status`, {
                headers: this.getAuthHeaders()
            });
            
            if (!response.ok) {
                console.warn('Recovery API not available');
                document.getElementById('recovery-status').textContent = 'N/A';
                document.getElementById('recovered-messages').textContent = '0';
                return;
            }
            
            const data = await response.json();
            
            // Update metrics bar
            document.getElementById('recovery-status').textContent = data.enabled ? 
                (data.status === 'healthy' ? '✅ Active' : `⚠️ ${data.status}`) : 
                '❌ Disabled';
            
            document.getElementById('recovered-messages').textContent = 
                data.stats?.total_recovered_messages || '0';
                
            // Update recovery tab if visible
            if (document.getElementById('recovery-tab').style.display !== 'none') {
                this.updateRecoveryTab(data);
            }
            
        } catch (error) {
            console.warn('Recovery metrics unavailable:', error);
            document.getElementById('recovery-status').textContent = 'Error';
            document.getElementById('recovered-messages').textContent = '-';
        }
    }
    
    async updateRecoveryTab(data) {
        // Update status cards
        document.getElementById('recoverySystemStatus').textContent = 
            data.enabled ? (data.status || 'Unknown') : 'Disabled';
        document.getElementById('totalRecoveredMessages').textContent = 
            data.stats?.total_recovered_messages || '0';
        document.getElementById('usersTracked').textContent = 
            data.cursor_summary?.total_users || '0';
        document.getElementById('lastRecoveryOperation').textContent = 
            data.stats?.last_successful_recovery ? 
                this.formatRelativeTime(data.stats.last_successful_recovery.started_at) : 'Never';
        
        // Load recovery operations history and recovered messages
        this.loadRecoveryHistory();
        this.loadRecoveredMessages();
    }
    
    async loadRecoveryHistory() {
        try {
            const response = await fetch(`${this.apiBase}/recovery/history?limit=20`, {
                headers: this.getAuthHeaders()
            });
            
            if (!response.ok) return;
            
            const data = await response.json();
            const tbody = document.getElementById('recoveryOperationsBody');
            
            if (data.operations.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="padding: 20px; text-align: center; color: #666;">No operations yet</td></tr>';
                return;
            }
            
            tbody.innerHTML = data.operations.map(op => `
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">${op.operation_type}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">${this.formatRelativeTime(op.started_at)}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">
                        <span class="operation-status ${op.status}">${op.status}</span>
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">${op.users_checked || 0}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">${op.messages_recovered || 0}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">${op.messages_skipped || 0}</td>
                </tr>
            `).join('');
            
        } catch (error) {
            console.error('Failed to load recovery history:', error);
        }
    }
    
    async triggerRecovery() {
        const userId = prompt('Enter user ID to recover (leave empty for all users):');
        
        if (userId === null) return; // Cancelled
        
        try {
            const response = await fetch(`${this.apiBase}/recovery/trigger`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify({
                    user_id: userId || null,
                    max_messages: 100
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const result = await response.json();
            alert(`Recovery triggered successfully!\nOperation ID: ${result.operation_id}\nTarget: ${result.user_id || 'All users'}`);
            
            // Refresh recovery data
            setTimeout(() => {
                this.loadRecoveryMetrics();
            }, 2000);
            
        } catch (error) {
            console.error('Failed to trigger recovery:', error);
            alert('Failed to trigger recovery. Please check the console for details.');
        }
    }
    
    async loadRecoveredMessages() {
        try {
            const response = await fetch(`${this.apiBase}/recovery/messages?limit=20`, {
                headers: this.getAuthHeaders()
            });
            
            if (!response.ok) return;
            
            const data = await response.json();
            const tbody = document.getElementById('recoveredMessagesBody');
            
            if (data.messages.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="padding: 20px; text-align: center; color: #666;">No recovered messages yet</td></tr>';
                return;
            }
            
            tbody.innerHTML = data.messages.map(msg => `
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">
                        <div style="font-weight: 600;">${msg.nickname || msg.user_id}</div>
                        <div style="font-size: 0.8em; color: #666;">${msg.user_id}</div>
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6; max-width: 200px;">
                        <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${msg.user_message}">
                            ${msg.user_message}
                        </div>
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6; font-size: 0.9em;">
                        ${this.formatRelativeTime(msg.telegram_date)}
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6; font-size: 0.9em;">
                        ${this.formatRelativeTime(msg.created_at)}
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6; font-size: 0.9em; color: #666;">
                        ${msg.recovery_delay_hours ? `${msg.recovery_delay_hours.toFixed(1)}h` : 'N/A'}
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">
                        <span class="status-badge ${msg.review_status === 'approved' ? 'approved' : msg.review_status === 'pending' ? 'pending' : 'other'}" style="padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">
                            ${msg.review_status}
                        </span>
                    </td>
                </tr>
            `).join('');
            
        } catch (error) {
            console.error('Failed to load recovered messages:', error);
        }
    }
    
    formatRelativeTime(dateString) {
        if (!dateString) return 'Unknown';
        
        try {
            const date = new Date(dateString);
            const now = new Date();
            const diffMs = now - date;
            const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            const diffDays = Math.floor(diffHours / 24);
            
            if (diffDays > 0) {
                return `${diffDays}d ago`;
            } else if (diffHours > 0) {
                return `${diffHours}h ago`;
            } else {
                const diffMins = Math.floor(diffMs / (1000 * 60));
                return `${diffMins}m ago`;
            }
        } catch (e) {
            return 'Invalid date';
        }
    }
    
    // ===============================================
    // COHERENCE & SCHEDULE SYSTEM FUNCTIONALITY
    // ===============================================
    
    async loadCoherenceMetrics() {
        try {
            const response = await fetch(`${this.apiBase}/api/coherence/metrics`, {
                headers: this.getAuthHeaders()
            });
            
            if (!response.ok) {
                console.warn('Coherence API not available');
                document.getElementById('coherence-score').textContent = 'N/A';
                document.getElementById('active-commitments').textContent = '0';
                document.getElementById('schedule-conflicts').textContent = '0';
                return;
            }
            
            const data = await response.json();
            
            // Update coherence metrics
            document.getElementById('coherence-score').textContent = `${data.coherence_score}%`;
            document.getElementById('active-commitments').textContent = data.active_commitments || '0';
            document.getElementById('schedule-conflicts').textContent = data.schedule_conflicts_24h || '0';
            
            // Update color based on coherence score
            const scoreElement = document.getElementById('coherence-score');
            if (data.coherence_score >= 95) {
                scoreElement.style.color = '#4caf50'; // Green
            } else if (data.coherence_score >= 80) {
                scoreElement.style.color = '#ff9800'; // Orange
            } else {
                scoreElement.style.color = '#f44336'; // Red
            }
            
            console.log('Coherence metrics loaded:', data);
            
        } catch (error) {
            console.warn('Coherence metrics unavailable:', error);
            document.getElementById('coherence-score').textContent = 'Error';
            document.getElementById('active-commitments').textContent = '-';
            document.getElementById('schedule-conflicts').textContent = '-';
        }
    }
    
    async loadCoherenceViolations() {
        try {
            const response = await fetch(`${this.apiBase}/api/coherence/violations?limit=20`, {
                headers: this.getAuthHeaders()
            });
            
            if (!response.ok) {
                console.warn('Coherence violations API not available');
                return [];
            }
            
            const data = await response.json();
            return data.violations || [];
            
        } catch (error) {
            console.warn('Failed to load coherence violations:', error);
            return [];
        }
    }
    
    async getUserCommitments(userId) {
        try {
            const response = await fetch(`${this.apiBase}/users/${userId}/commitments?status=active&limit=10`, {
                headers: this.getAuthHeaders()
            });
            
            if (!response.ok) {
                console.warn('User commitments API not available');
                return [];
            }
            
            const data = await response.json();
            return data.commitments || [];
            
        } catch (error) {
            console.warn('Failed to load user commitments:', error);
            return [];
        }
    }
    
    async loadReviews() {
        try {
            const response = await fetch(`${this.apiBase}/reviews/pending?limit=50`, {
                headers: this.getAuthHeaders()
            });
            const reviews = await response.json();
            this.renderReviews(reviews);
        } catch (error) {
            console.error('Failed to load reviews:', error);
            document.getElementById('review-list').innerHTML = '<div class="empty-state"><h3>Error loading reviews</h3><p>Please check the API connection</p></div>';
        }
    }
    
    renderReviews(reviews) {
        const container = document.getElementById('review-list');
        
        if (reviews.length === 0) {
            container.innerHTML = '<div class="empty-state"><h3>🎉 All caught up!</h3><p>No pending reviews</p></div>';
            return;
        }
        
        container.innerHTML = reviews.map(review => `
            <div class="review-item" data-id="${review.id}" onclick="dashboard.selectReview('${review.id}')">
                <div class="review-meta">
                    <span class="user-id">User ${review.user_id}</span>
                    <span class="user-badges" id="badges-${review.user_id}">
                        <span class="loading-badge">Loading...</span>
                        ${review.is_recovered_message ? '<span class="recovered-badge" title="Message recovered during system downtime">🔄 Recovered</span>' : ''}
                    </span>
                    <div>
                        <span class="priority-badge ${this.getPriorityClass(review.priority_score)}">
                            ${this.formatPriority(review.priority_score)}
                        </span>
                        <span class="risk-badge ${this.getRiskClass(review.constitution_recommendation)}">
                            ${review.constitution_recommendation.toUpperCase()}
                        </span>
                        ${this.renderCacheWarning(review)}
                    </div>
                </div>
                <div class="user-message">
                    "${review.user_message}"
                </div>
                <div class="ai-response">
                    ${review.llm2_bubbles.join(' • ')}
                </div>
                <div class="badges-container">
                    ${this.formatModelBadges(review.llm1_model, review.llm2_model, review.llm1_cost_usd, review.llm2_cost_usd)}
                </div>
            </div>
        `).join('');
        
        // Load nickname badges for unique users only
        const uniqueUsers = [...new Set(reviews.map(r => r.user_id))];
        uniqueUsers.forEach(userId => {
            this.loadUserBadges(userId);
        });
    }
    
    async loadUserBadges(userId) {
        try {
            const response = await fetch(`${this.apiBase}/users/${userId}/customer-status`, {
                headers: this.getAuthHeaders()
            });
            
            if (response.ok) {
                const statusData = await response.json();
                this.renderUserBadges(userId, statusData);
            } else {
                this.renderUserBadges(userId, null);
            }
        } catch (error) {
            console.error(`Failed to load user badges for ${userId}:`, error);
            this.renderUserBadges(userId, null);
        }
    }
    
    renderUserBadges(userId, statusData) {
        const badgesContainer = document.getElementById(`badges-${userId}`);
        if (!badgesContainer) return;
        
        if (!statusData) {
            badgesContainer.innerHTML = '<span class="error-badge">Error</span>';
            return;
        }
        
        const nickname = statusData.nickname || 'No name';
        const status = statusData.customer_status || 'PROSPECT';
        
        badgesContainer.innerHTML = `
            <span class="nickname-badge" title="Click to edit nickname" onclick="dashboard.editNickname('${userId}', '${nickname}')">
                👤 ${nickname}
            </span>
        `;
    }
    
    async editNickname(userId, currentNickname) {
        const newNickname = prompt('Enter new nickname:', currentNickname);
        if (newNickname && newNickname !== currentNickname) {
            try {
                const response = await fetch(`${this.apiBase}/users/${userId}/nickname`, {
                    method: 'POST',
                    headers: this.getAuthHeaders(),
                    body: JSON.stringify({ nickname: newNickname })
                });
                
                if (response.ok) {
                    // Reload badges to show updated nickname
                    this.loadUserBadges(userId);
                } else {
                    alert('Failed to update nickname');
                }
            } catch (error) {
                console.error('Error updating nickname:', error);
                alert('Error updating nickname');
            }
        }
    }
    
    getPriorityClass(priority) {
        if (priority >= 0.8) return 'priority-high';
        if (priority >= 0.5) return 'priority-medium';
        return 'priority-low';
    }
    
    formatPriority(priority) {
        return `${Math.round(priority * 100)}%`;
    }
    
    getRiskClass(recommendation) {
        switch (recommendation) {
            case 'flag': return 'risk-flag';
            case 'review': return 'risk-review';
            case 'approve': return 'risk-approve';
            default: return 'risk-review';
        }
    }
    
    getScoreClass(score) {
        if (score >= 0.7) return 'score-high';
        if (score >= 0.4) return 'score-medium';
        return 'score-low';
    }
    
    async selectReview(reviewId) {
        // Update UI selection
        document.querySelectorAll('.review-item').forEach(item => {
            item.classList.remove('selected');
        });
        document.querySelector(`[data-id="${reviewId}"]`).classList.add('selected');
        
        // Load detailed review data
        try {
            const response = await fetch(`${this.apiBase}/reviews/${reviewId}`, {
                headers: this.getAuthHeaders()
            });
            this.currentReview = await response.json();
            
            // Don't set customer status from cached review data - load fresh from API instead
            
            this.renderEditor();
        } catch (error) {
            console.error('Failed to load review details:', error);
        }
    }
    
    renderEditor() {
        document.getElementById('no-selection').style.display = 'none';
        document.getElementById('editor-form').style.display = 'block';
        
        // Render bubbles
        this.renderBubbles();
        
        // Reset form state
        this.selectedTags = [];
        this.qualityScore = 3;
        this.updateTagButtons();
        this.updateQualityStars();
        
        // Load customer status for this user
        this.loadCustomerStatus();
        
        // Setup star click handlers with a small delay to ensure DOM is ready
        setTimeout(() => {
            this.setupQualityStars();
        }, 0);
    }
    
    renderBubbles() {
        const container = document.getElementById('bubbles-container');
        const bubbles = this.currentReview.llm2_bubbles || [];
        
        // Show LLM1 raw response first
        let html = '';
        if (this.currentReview.llm1_raw_response) {
            html += `
                <div class="llm-section">
                    <h4 class="llm-header">
                        <span class="llm-badge llm1">LLM1 (Creative)</span>
                        <span class="model-name">${this.currentReview.llm1_model || 'Unknown'}</span>
                    </h4>
                    <div class="llm1-response">${this.currentReview.llm1_raw_response}</div>
                </div>
            `;
        }
        
        // Show LLM2 bubbles (editable)
        html += `
            <div class="llm-section">
                <h4 class="llm-header">
                    <span class="llm-badge llm2">LLM2 (Refined)</span>
                    <span class="model-name">${this.currentReview.llm2_model || 'Unknown'}</span>
                </h4>
                <div class="bubbles-editable">
                    ${bubbles.map((bubble, index) => `
                        <div class="bubble-container">
                            <textarea 
                                class="bubble-editor" 
                                data-index="${index}"
                                placeholder="Edit message bubble..."
                            >${bubble}</textarea>
                            <button class="btn-delete-bubble" onclick="dashboard.deleteBubble(${index})" title="Delete bubble">
                                🗑️
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        
        // Add Constitution analysis section
        if (this.currentReview.constitution_analysis) {
            const analysis = this.currentReview.constitution_analysis;
            html += `
                <div class="llm-section constitution-section">
                    <h4 class="llm-header">
                        <span class="llm-badge constitution">🛡️ Constitution Analysis</span>
                        <span class="risk-badge ${this.getRiskClass(analysis.recommendation)}">
                            ${analysis.recommendation.toUpperCase()}
                        </span>
                    </h4>
                    <div class="constitution-content">
                        <div class="constitution-score">
                            <strong>Risk Score:</strong> 
                            <span class="score-value ${this.getScoreClass(analysis.risk_score)}">
                                ${(analysis.risk_score * 100).toFixed(1)}%
                            </span>
                        </div>
                        ${analysis.flags && analysis.flags.length > 0 ? `
                            <div class="constitution-flags">
                                <strong>Flags:</strong>
                                <div class="flags-list">
                                    ${analysis.flags.map(flag => `<span class="flag-item">${flag}</span>`).join('')}
                                </div>
                            </div>
                        ` : ''}
                        ${analysis.violations && analysis.violations.length > 0 ? `
                            <div class="constitution-violations">
                                <strong>Violations:</strong>
                                <ul class="violations-list">
                                    ${analysis.violations.map(violation => `<li>${violation}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }
        
        container.innerHTML = html;
    }
    
    renderTagButtons() {
        const container = document.getElementById('tag-buttons');
        
        container.innerHTML = this.editTaxonomy.map(tag => `
            <button 
                class="tag-btn" 
                data-tag="${tag.code}"
                onclick="dashboard.toggleTag('${tag.code}')"
                title="${tag.description}"
            >
                ${tag.code}
            </button>
        `).join('');
    }
    
    setupEventListeners() {
        // Simple event delegation for star clicks
        if (!this.globalStarListenerAdded) {
            document.addEventListener('click', (e) => {
                if (e.target.classList.contains('star') && e.target.closest('#quality-stars')) {
                    const rating = parseInt(e.target.dataset.rating);
                    if (rating && this.currentReview) {
                        this.qualityScore = rating;
                        this.updateQualityStars();
                        console.log(`Quality score set to: ${rating}`);
                    }
                }
            });
            this.globalStarListenerAdded = true;
        }
    }
    
    toggleTag(tagCode) {
        if (this.selectedTags.includes(tagCode)) {
            this.selectedTags = this.selectedTags.filter(t => t !== tagCode);
        } else {
            this.selectedTags.push(tagCode);
        }
        this.updateTagButtons();
    }
    
    updateTagButtons() {
        document.querySelectorAll('.tag-btn').forEach(btn => {
            const tag = btn.dataset.tag;
            btn.classList.toggle('selected', this.selectedTags.includes(tag));
        });
    }
    
    updateQualityStars() {
        console.log('Updating quality stars, current score:', this.qualityScore);
        document.querySelectorAll('.star').forEach(star => {
            const rating = parseInt(star.dataset.rating);
            const isSelected = rating <= this.qualityScore;
            star.classList.toggle('selected', isSelected);
            console.log(`Star ${rating}: ${isSelected ? 'selected' : 'unselected'}`);
        });
    }
    
    setupQualityStars() {
        // Stars are now handled by global event delegation
        // Just update the visual state
        this.updateQualityStars();
    }
    
    getFinalBubbles() {
        const textareas = document.querySelectorAll('.bubble-editor');
        return Array.from(textareas)
            .map(textarea => textarea.value.trim())
            .filter(text => text.length > 0);
    }
    
    async approveReview() {
        if (!this.currentReview) return;
        
        const finalBubbles = this.getFinalBubbles();
        if (finalBubbles.length === 0) {
            alert('Please provide at least one message bubble');
            return;
        }
        
        const reviewerNotes = prompt('Optional reviewer notes (for training data analysis):');
        
        // Check if user cancelled the prompt
        if (reviewerNotes === null) {
            console.log('User cancelled review approval');
            return; // Exit without saving anything
        }
        
        try {
            // NUEVO: Prepare approval data with CTA information
            const approvalData = {
                final_bubbles: finalBubbles,
                edit_tags: this.selectedTags,
                quality_score: this.qualityScore,
                reviewer_notes: reviewerNotes || ''
            };
            
            // NUEVO: Add CTA metadata if CTA was inserted
            if (this.ctaInserted) {
                approvalData.cta_metadata = this.ctaInserted;
            }
            
            const response = await fetch(`${this.apiBase}/reviews/${this.currentReview.id}/approve`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(approvalData)
            });
            
            if (response.ok) {
                const result = await response.json();
                let message = '✅ Review approved and message sent!';
                
                // NUEVO: Show CTA insertion confirmation
                if (result.cta_inserted) {
                    message += `\n🎯 CTA ${result.cta_type.toUpperCase()} successfully inserted!`;
                }
                
                alert(message);
                this.loadReviews();
                this.loadMetrics();
                this.clearEditor();
            } else {
                const error = await response.json();
                alert(`Failed to approve: ${error.detail}`);
            }
        } catch (error) {
            console.error('Failed to approve review:', error);
            alert('Failed to approve review. Please try again.');
        }
    }
    
    async rejectReview() {
        if (!this.currentReview) return;
        
        const reviewerNotes = prompt('Reason for rejection:');
        
        // Check if user cancelled the prompt
        if (reviewerNotes === null) {
            console.log('User cancelled review rejection');
            return; // Exit without saving anything
        }
        
        try {
            const response = await fetch(`${this.apiBase}/reviews/${this.currentReview.id}/reject`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify({
                    reviewer_notes: reviewerNotes || ''
                })
            });
            
            if (response.ok) {
                alert('❌ Review rejected');
                this.loadReviews();
                this.loadMetrics();
                this.clearEditor();
            } else {
                const error = await response.json();
                alert(`Failed to reject: ${error.detail}`);
            }
        } catch (error) {
            console.error('Failed to reject review:', error);
            alert('Failed to reject review. Please try again.');
        }
    }
    
    async cancelReview() {
        if (!this.currentReview) return;
        
        // Confirm cancellation to prevent accidental clicks
        const confirmed = confirm('Are you sure you want to cancel this review?\n\nThis will return the review to the pending queue without saving any changes.');
        if (!confirmed) return;
        
        const reviewerNotes = prompt('Optional reason for cancellation (for logging):');
        
        // Check if user cancelled the prompt
        if (reviewerNotes === null) {
            console.log('User cancelled cancellation reason prompt');
            return; // Exit without cancelling the review
        }
        
        try {
            const response = await fetch(`${this.apiBase}/reviews/${this.currentReview.id}/cancel`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify({
                    reviewer_notes: reviewerNotes || ''
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                alert('🚫 Review cancelled successfully.\n\nThe review has been returned to the pending queue for other reviewers.');
                this.loadReviews();
                this.loadMetrics();
                this.clearEditor();
            } else {
                const error = await response.json();
                alert(`Failed to cancel: ${error.detail}`);
            }
        } catch (error) {
            console.error('Failed to cancel review:', error);
            alert('Failed to cancel review. Please try again.');
        }
    }
    
    // NUEVO: CTA Methods
    insertCTA(type) {
        if (!this.currentReview) return;
        
        const templates = this.ctaTemplates[type];
        if (!templates || templates.length === 0) return;
        
        // Show template selector if multiple options
        let selectedTemplate;
        if (templates.length === 1) {
            selectedTemplate = templates[0];
        } else {
            const options = templates.map((t, i) => `${i + 1}. ${t}`).join('\n');
            const choice = prompt(`Select CTA ${type.toUpperCase()} template:\n\n${options}\n\nEnter number (1-${templates.length}):`);
            if (choice === null || choice === '') {
                console.log('User cancelled CTA template selection');
                return; // User cancelled
            }
            const index = parseInt(choice) - 1;
            if (index >= 0 && index < templates.length) {
                selectedTemplate = templates[index];
            } else {
                return; // Invalid choice
            }
        }
        
        // Add as new bubble
        const container = document.getElementById('bubbles-container');
        const newTextarea = document.createElement('textarea');
        newTextarea.className = 'bubble-editor cta-bubble';
        newTextarea.value = selectedTemplate;
        newTextarea.placeholder = 'CTA message bubble...';
        newTextarea.style.borderLeft = '4px solid #ff6b6b'; // Visual indicator
        container.appendChild(newTextarea);
        
        // Add CTA tag
        const ctaTag = `CTA_${type.toUpperCase()}`;
        if (!this.selectedTags.includes(ctaTag)) {
            this.selectedTags.push(ctaTag);
            this.updateTagButtons();
        }
        
        // Store CTA metadata
        this.ctaInserted = {
            type: type,
            text: selectedTemplate,
            position: container.children.length - 1,
            timestamp: new Date().toISOString()
        };
        
        console.log(`CTA ${type} inserted:`, this.ctaInserted);
        
        // Visual feedback
        this.showCTAFeedback(type);
    }
    
    showCTAFeedback(type) {
        // Create temporary feedback message
        const feedback = document.createElement('div');
        feedback.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #4caf50;
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            z-index: 1000;
            font-weight: bold;
        `;
        feedback.textContent = `✅ CTA ${type.toUpperCase()} insertado`;
        document.body.appendChild(feedback);
        
        // Remove after 3 seconds
        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.parentNode.removeChild(feedback);
            }
        }, 3000);
    }
    
    clearEditor() {
        document.getElementById('no-selection').style.display = 'block';
        document.getElementById('editor-form').style.display = 'none';
        this.currentReview = null;
        this.selectedTags = [];
        this.qualityScore = 3;
        // NUEVO: Reset CTA state
        this.ctaInserted = null;
    }
    
    // Multi-LLM helper functions
    formatModelBadges(llm1Model, llm2Model, llm1Cost, llm2Cost) {
        let badges = '';
        
        if (llm1Model) {
            const isFree = llm1Model.toLowerCase().includes('gemini') && (llm1Cost === 0 || llm1Cost === null);
            badges += this.formatModelBadge(llm1Model, isFree, 'LLM-1');
        }
        
        if (llm2Model) {
            const isFree = llm2Model.toLowerCase().includes('gemini') && (llm2Cost === 0 || llm2Cost === null);
            badges += this.formatModelBadge(llm2Model, isFree, 'LLM-2');
        }
        
        return badges;
    }
    
    formatModelBadge(model, isFree, label) {
        const modelName = model.split('-')[0] || model; // "gemini-2.0-flash-exp" -> "gemini"
        const isGemini = modelName.toLowerCase().includes('gemini');
        const badgeClass = isGemini ? 'model-badge-gemini' : 'model-badge-gpt';
        const freeText = isFree ? '<span class="model-badge-free">FREE</span>' : '';
        
        return `<span class="model-badge ${badgeClass}">
            ${label}: ${modelName.charAt(0).toUpperCase() + modelName.slice(1)}
            ${freeText}
        </span>`;
    }
    
    updateQuotaDisplay(used, total) {
        // Sanitize input values
        const safeUsed = isNaN(used) || !isFinite(used) ? 0 : Math.max(0, used);
        const safeTotal = isNaN(total) || !isFinite(total) || total <= 0 ? 32000 : total;
        
        const percentage = Math.min(100, (safeUsed / safeTotal) * 100);
        const quotaText = `${safeUsed.toLocaleString()} / ${safeTotal.toLocaleString()}`;
        
        document.getElementById('gemini-quota').textContent = `${percentage.toFixed(1)}%`;
        document.getElementById('quota-text').textContent = quotaText;
        document.getElementById('quota-progress-fill').style.width = `${percentage}%`;
    }
    
    updateSavingsDisplay(savings) {
        const formattedSavings = savings > 0 ? `$${savings.toFixed(4)}` : '$0.00';
        document.getElementById('savings-today').textContent = formattedSavings;
    }
    
    renderCacheWarning(review) {
        // En renderReviews()
        if (review.cache_ratio !== undefined && review.cache_ratio < 0.5) {
            // Agregar warning badge
            return '<span class="cache-warning">⚠️ Low Cache</span>';
        }
        return '';
    }
    
    deleteBubble(index) {
        if (!this.currentReview) return;
        
        // Get current bubble values from DOM
        const textareas = document.querySelectorAll('.bubble-editor');
        const currentValues = Array.from(textareas).map(ta => ta.value);
        
        if (currentValues.length <= 1) {
            alert('Cannot delete the last bubble. At least one bubble is required.');
            return;
        }
        
        if (confirm('Are you sure you want to delete this bubble?')) {
            // Remove the bubble from the array
            currentValues.splice(index, 1);
            
            // Update the review object
            this.currentReview.llm2_bubbles = currentValues;
            
            // Re-render only the bubbles section
            this.renderBubbles();
        }
    }
    
    deleteCTA() {
        const ctaBubbles = document.querySelectorAll('.cta-bubble');
        if (ctaBubbles.length === 0) {
            alert('No CTA bubbles to delete.');
            return;
        }
        
        if (confirm('Are you sure you want to delete all CTA bubbles?')) {
            ctaBubbles.forEach(bubble => bubble.remove());
            this.ctaInserted = null;
            
            // Remove CTA tags from selected tags
            const ctaTags = ['CTA_SOFT', 'CTA_MEDIUM', 'CTA_DIRECT'];
            this.selectedTags = this.selectedTags.filter(tag => !ctaTags.includes(tag));
            this.updateTagButtons();
        }
    }
    
    async loadCustomerStatus() {
        if (!this.currentReview) return;
        
        try {
            const response = await fetch(`${this.apiBase}/users/${this.currentReview.user_id}/customer-status`, {
                headers: this.getAuthHeaders()
            });
            
            if (response.ok) {
                const statusData = await response.json();
                this.updateCustomerStatusDisplay(statusData);
            } else {
                // Default to PROSPECT if no data found
                this.updateCustomerStatusDisplay({
                    customer_status: 'PROSPECT',
                    ltv_usd: 0.0
                });
            }
        } catch (error) {
            console.error('Failed to load customer status:', error);
            this.updateCustomerStatusDisplay({
                customer_status: 'PROSPECT',
                ltv_usd: 0.0
            });
        }
    }
    
    updateCustomerStatusDisplay(statusData) {
        // Update dropdown selection
        const dropdown = document.getElementById('customer-status-select');
        if (dropdown) {
            dropdown.value = statusData.customer_status || 'PROSPECT';
        }
        
        // Update current status display
        const statusBadge = document.querySelector('.status-badge');
        const ltvDisplay = document.querySelector('.ltv-display');
        
        if (statusBadge) {
            const status = statusData.customer_status || 'PROSPECT';
            statusBadge.textContent = `Current: ${status}`;
            statusBadge.className = `status-badge ${status}`;
        }
        
        if (ltvDisplay) {
            const ltv = statusData.ltv_usd || 0;
            ltvDisplay.textContent = `LTV: $${ltv.toFixed(2)}`;
        }
        
        // Clear LTV input
        const ltvInput = document.getElementById('ltv-input');
        if (ltvInput) {
            ltvInput.value = '';
        }
    }
    
    async updateCustomerStatus() {
        if (!this.currentReview) {
            alert('No review selected');
            return;
        }
        
        const dropdown = document.getElementById('customer-status-select');
        const ltvInput = document.getElementById('ltv-input');
        
        if (!dropdown) {
            alert('Customer status selector not found');
            return;
        }
        
        const newStatus = dropdown.value;
        const ltvAmount = parseFloat(ltvInput.value) || 0;
        const reason = prompt('Reason for status change (optional):', 'Manual update from dashboard');
        
        // Check if user cancelled the prompt
        if (reason === null) {
            console.log('User cancelled customer status update');
            return; // Exit without saving anything
        }
        
        try {
            const response = await fetch(`${this.apiBase}/users/${this.currentReview.user_id}/customer-status`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify({
                    user_id: this.currentReview.user_id,
                    customer_status: newStatus,
                    reason: reason || 'Manual update from dashboard',
                    ltv_amount: ltvAmount
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                
                // Update display with new status
                this.updateCustomerStatusDisplay({
                    customer_status: result.new_status,
                    ltv_usd: (result.ltv_added || 0)
                });
                
                // Show success message
                let message = `✅ Customer status updated!\n${result.previous_status} → ${result.new_status}`;
                if (result.ltv_added > 0) {
                    message += `\nLTV added: $${result.ltv_added.toFixed(2)}`;
                }
                
                alert(message);
                
                // Refresh reviews to show any updates
                this.loadReviews();
                
            } else {
                const error = await response.json();
                alert(`Failed to update customer status: ${error.detail}`);
            }
        } catch (error) {
            console.error('Failed to update customer status:', error);
            alert('Failed to update customer status. Please try again.');
        }
    }
}

// Global functions for HTML onclick handlers
function addBubble() {
    const container = document.getElementById('bubbles-container');
    const newTextarea = document.createElement('textarea');
    newTextarea.className = 'bubble-editor';
    newTextarea.placeholder = 'New message bubble...';
    container.appendChild(newTextarea);
}

function approveReview() {
    dashboard.approveReview();
}

function rejectReview() {
    dashboard.rejectReview();
}

// NUEVO: CTA Global Functions
function insertCTASoft() {
    dashboard.insertCTA('soft');
}

function insertCTAMedium() {
    dashboard.insertCTA('medium');
}

function insertCTADirect() {
    dashboard.insertCTA('direct');
}

// ===== TAB MANAGEMENT =====

function switchTab(tabName) {
    console.log('🔄 switchTab called with:', tabName);
    
    try {
        // Hide all tab contents
        const tabContents = document.querySelectorAll('.tab-content');
        console.log('📑 Found tab contents:', tabContents.length);
        tabContents.forEach(tab => tab.classList.remove('active'));
        
        // Remove active class from all tab buttons
        const tabButtons = document.querySelectorAll('.tab-button');
        console.log('🔘 Found tab buttons:', tabButtons.length);
        tabButtons.forEach(button => button.classList.remove('active'));
        
        // Show selected tab content
        const selectedTab = document.getElementById(`${tabName}-tab`);
        console.log('📋 Selected tab element:', selectedTab);
        if (selectedTab) {
            selectedTab.classList.add('active');
        }
        
        // Activate selected tab button (simplified)
        console.log('🔘 Looking for button with tabName:', tabName);
        const buttons = document.querySelectorAll('.tab-button');
        buttons.forEach(button => {
            if (button.onclick && button.onclick.toString().includes(tabName)) {
                button.classList.add('active');
                console.log('✅ Button activated');
            }
        });
        
        // Load content based on tab
        if (tabName === 'quarantine') {
            console.log('🔄 Loading quarantine tab...');
            if (window.dashboard) {
                console.log('📝 Dashboard found, loading messages...');
                window.dashboard.loadQuarantineMessages();
                window.dashboard.loadQuarantineStats();
            } else {
                console.error('❌ Dashboard not initialized!');
            }
        } else if (tabName === 'review') {
            window.dashboard.loadReviews();
        }
        
    } catch (error) {
        console.error('💥 Error in switchTab:', error);
    }
}

// ===== QUARANTINE MANAGEMENT =====

// Add quarantine methods to HITLDashboard class
HITLDashboard.prototype.loadQuarantineMessages = async function() {
    console.log('🚀 loadQuarantineMessages called!');
    try {
        console.log('📡 Making API call to quarantine/messages...');
        const response = await fetch(`${this.apiBase}/quarantine/messages?limit=50`, {
            headers: this.getAuthHeaders()
        });
        
        console.log('📥 Response received:', response.status);
        if (response.ok) {
            const data = await response.json();
            console.log('📊 Data received:', data);
            this.renderQuarantineMessages(data.messages);
            
            // Update badge count
            const badge = document.getElementById('quarantine-count');
            if (data.messages.length > 0) {
                badge.textContent = data.messages.length;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        } else {
            console.error('Failed to load quarantine messages');
            document.getElementById('quarantine-list').innerHTML = '<div class="empty-state">Failed to load quarantine messages</div>';
        }
    } catch (error) {
        console.error('Error loading quarantine messages:', error);
        document.getElementById('quarantine-list').innerHTML = '<div class="empty-state">Error loading quarantine messages</div>';
    }
};

HITLDashboard.prototype.loadQuarantineStats = async function() {
    try {
        const response = await fetch(`${this.apiBase}/quarantine/stats`, {
            headers: this.getAuthHeaders()
        });
        
        if (response.ok) {
            const stats = await response.json();
            
            // Update statistics display
            document.getElementById('active-protocols').textContent = stats.active_protocols || 0;
            document.getElementById('quarantine-messages-count').textContent = stats.total_messages_quarantined || 0;
            document.getElementById('cost-saved').textContent = `$${(stats.total_cost_saved_usd || 0).toFixed(4)}`;
            document.getElementById('messages-24h').textContent = stats.messages_last_24h || 0;
        }
    } catch (error) {
        console.error('Error loading quarantine stats:', error);
    }
};

HITLDashboard.prototype.renderQuarantineMessages = function(messages) {
    const container = document.getElementById('quarantine-list');
    
    if (!messages || messages.length === 0) {
        container.innerHTML = '<div class="empty-state"><h3>No messages in quarantine</h3><p>All users are currently active</p></div>';
        // Hide batch controls when no messages
        document.getElementById('batch-controls').style.display = 'none';
        return;
    }
    
    // Show batch controls when there are messages
    document.getElementById('batch-controls').style.display = 'block';
    
    const messagesHtml = messages.map(msg => {
        const ageHours = Math.floor(msg.age_hours || 0);
        const ageText = ageHours < 1 ? 'Just now' : 
                       ageHours < 24 ? `${ageHours}h ago` : 
                       `${Math.floor(ageHours / 24)}d ago`;
        
        const nickname = msg.nickname || 'Unknown';
        const customerStatus = msg.customer_status || 'PROSPECT';
        
        return `
            <div class="quarantine-message" data-message-id="${msg.message_id}">
                <div class="quarantine-meta">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <input type="checkbox" class="message-checkbox" data-message-id="${msg.message_id}" onchange="dashboard.updateSelection()">
                        <div class="quarantine-user">
                            ${nickname} (${msg.user_id})
                            <span class="status-badge status-${customerStatus.toLowerCase()}">${customerStatus}</span>
                        </div>
                    </div>
                    <div class="quarantine-age">${ageText}</div>
                </div>
                
                <div class="quarantine-message-text">${msg.message_text}</div>
                
                <div class="quarantine-actions">
                    <button class="btn-quarantine btn-process" onclick="dashboard.processQuarantineMessage('${msg.message_id}', 'process')">
                        ✅ Process Only
                    </button>
                    <button class="btn-quarantine btn-process-deactivate" onclick="dashboard.processQuarantineMessage('${msg.message_id}', 'process_and_deactivate')">
                        🔓 Process & Deactivate Protocol
                    </button>
                    <button class="btn-quarantine btn-delete-quarantine" onclick="dashboard.deleteQuarantineMessage('${msg.message_id}')">
                        🗑️ Delete
                    </button>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = messagesHtml;
    
    // Reset selection state
    this.clearSelection();
};

HITLDashboard.prototype.processQuarantineMessage = async function(messageId, action) {
    if (!confirm(`Are you sure you want to ${action === 'process_and_deactivate' ? 'process this message and deactivate the protocol' : 'process this message'}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${this.apiBase}/quarantine/${messageId}/process?action=${action}`, {
            method: 'POST',
            headers: this.getAuthHeaders()
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Show success message
            const actionText = result.protocol_deactivated ? 'processed and protocol deactivated' : 'processed';
            alert(`Message ${actionText} successfully`);
            
            // Refresh quarantine list and stats
            this.loadQuarantineMessages();
            this.loadQuarantineStats();
            
            // If protocol was deactivated, refresh review queue too
            if (result.protocol_deactivated) {
                this.loadReviews();
            }
        } else {
            const error = await response.json();
            alert(`Failed to process message: ${error.detail}`);
        }
    } catch (error) {
        console.error('Error processing quarantine message:', error);
        alert('Failed to process message. Please try again.');
    }
};

HITLDashboard.prototype.deleteQuarantineMessage = async function(messageId) {
    if (!confirm('Are you sure you want to delete this quarantine message?')) {
        return;
    }
    
    try {
        const response = await fetch(`${this.apiBase}/quarantine/${messageId}`, {
            method: 'DELETE',
            headers: this.getAuthHeaders()
        });
        
        if (response.ok) {
            alert('Message deleted successfully');
            this.loadQuarantineMessages();
            this.loadQuarantineStats();
        } else {
            const error = await response.json();
            alert(`Failed to delete message: ${error.detail}`);
        }
    } catch (error) {
        console.error('Error deleting quarantine message:', error);
        alert('Failed to delete message. Please try again.');
    }
};

HITLDashboard.prototype.activateProtocol = async function(userId, reason) {
    try {
        const response = await fetch(`${this.apiBase}/users/${userId}/protocol?action=activate&reason=${encodeURIComponent(reason)}`, {
            method: 'POST',
            headers: this.getAuthHeaders()
        });
        
        if (response.ok) {
            alert(`Protocol activated for user ${userId}`);
            this.loadReviews(); // Refresh review queue
            this.loadQuarantineStats(); // Update stats if on quarantine tab
        } else {
            const error = await response.json();
            alert(`Failed to activate protocol: ${error.detail}`);
        }
    } catch (error) {
        console.error('Error activating protocol:', error);
        alert('Failed to activate protocol. Please try again.');
    }
};

// ===== BATCH OPERATIONS =====

HITLDashboard.prototype.updateSelection = function() {
    const checkboxes = document.querySelectorAll('.message-checkbox');
    const selectedCheckboxes = document.querySelectorAll('.message-checkbox:checked');
    const selectedCount = selectedCheckboxes.length;
    
    // Update counter
    document.getElementById('selected-count').textContent = `${selectedCount} selected`;
    
    // Enable/disable batch buttons
    const batchButtons = document.querySelectorAll('#batch-controls button');
    batchButtons.forEach(btn => {
        if (btn.onclick && btn.onclick.toString().includes('batch')) {
            btn.disabled = selectedCount === 0;
            btn.style.opacity = selectedCount === 0 ? '0.5' : '1';
        }
    });
};

HITLDashboard.prototype.clearSelection = function() {
    const checkboxes = document.querySelectorAll('.message-checkbox');
    checkboxes.forEach(checkbox => checkbox.checked = false);
    this.updateSelection();
};

HITLDashboard.prototype.batchProcessQuarantine = async function(action) {
    const selectedCheckboxes = document.querySelectorAll('.message-checkbox:checked');
    const messageIds = Array.from(selectedCheckboxes).map(cb => cb.getAttribute('data-message-id'));
    
    if (messageIds.length === 0) {
        alert('Please select at least one message');
        return;
    }
    
    const actionText = action === 'process' ? 'process' : 'delete';
    if (!confirm(`Are you sure you want to ${actionText} ${messageIds.length} selected message(s)?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${this.apiBase}/quarantine/batch-process?action=${action}`, {
            method: 'POST',
            headers: this.getAuthHeaders(),
            body: JSON.stringify(messageIds)
        });
        
        if (response.ok) {
            const result = await response.json();
            const successCount = result.results.processed;
            const failedCount = result.results.failed;
            
            let message = `Successfully ${actionText}ed ${successCount} message(s)`;
            if (failedCount > 0) {
                message += `, ${failedCount} failed`;
            }
            
            alert(message);
            
            // Refresh data
            this.loadQuarantineMessages();
            this.loadQuarantineStats();
            
            // If processed messages, refresh review queue too
            if (action === 'process') {
                this.loadReviews();
            }
        } else {
            const error = await response.json();
            alert(`Batch ${actionText} failed: ${error.detail}`);
        }
    } catch (error) {
        console.error(`Error in batch ${actionText}:`, error);
        alert(`Failed to ${actionText} messages. Please try again.`);
    }
};

// ===== PROTOCOL MODAL =====

HITLDashboard.prototype.showProtocolModal = function() {
    const modal = document.getElementById('protocol-modal');
    modal.style.display = 'block';
    
    // Clear previous values
    document.getElementById('protocol-user-id').value = '';
    document.getElementById('protocol-reason').value = '';
    
    // Focus on user ID input
    setTimeout(() => {
        document.getElementById('protocol-user-id').focus();
    }, 100);
};

HITLDashboard.prototype.closeProtocolModal = function() {
    const modal = document.getElementById('protocol-modal');
    modal.style.display = 'none';
};

HITLDashboard.prototype.confirmActivateProtocol = function() {
    const userId = document.getElementById('protocol-user-id').value.trim();
    const reason = document.getElementById('protocol-reason').value.trim();
    
    if (!userId) {
        alert('Please enter a user ID');
        document.getElementById('protocol-user-id').focus();
        return;
    }
    
    // Confirm action
    if (!confirm(`Are you sure you want to activate the silence protocol for user: ${userId}?`)) {
        return;
    }
    
    this.activateProtocol(userId, reason || 'Manual activation from dashboard');
    this.closeProtocolModal();
};

// ===== ENHANCED REVIEW QUEUE =====

HITLDashboard.prototype.addProtocolButtonToReview = function(reviewElement, userId) {
    // Add a quick protocol button to individual review items
    const existingButton = reviewElement.querySelector('.btn-quick-protocol');
    if (existingButton) return; // Already added
    
    const protocolButton = document.createElement('button');
    protocolButton.className = 'btn-quick-protocol';
    protocolButton.innerHTML = '🔇';
    protocolButton.title = `Activate protocol for user ${userId}`;
    protocolButton.style.cssText = 'position: absolute; top: 0.5rem; right: 0.5rem; background: #dc3545; color: white; border: none; border-radius: 4px; padding: 0.25rem 0.5rem; cursor: pointer; font-size: 0.8rem;';
    
    protocolButton.onclick = (e) => {
        e.stopPropagation();
        this.quickActivateProtocol(userId);
    };
    
    // Add to review element (make it relative positioned)
    reviewElement.style.position = 'relative';
    reviewElement.appendChild(protocolButton);
};

HITLDashboard.prototype.quickActivateProtocol = function(userId) {
    if (!confirm(`Activate silence protocol for user ${userId}?\n\nThis will quarantine their future messages.`)) {
        return;
    }
    
    const reason = prompt('Enter reason (optional):') || 'Quick activation from review queue';
    this.activateProtocol(userId, reason);
};

// ===== MODAL CLICK OUTSIDE TO CLOSE =====

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('protocol-modal');
    if (event.target === modal) {
        dashboard.closeProtocolModal();
    }
};

// Close modal with Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const modal = document.getElementById('protocol-modal');
        if (modal.style.display === 'block') {
            dashboard.closeProtocolModal();
        }
    }
});

// ===== ENHANCED METRICS =====

HITLDashboard.prototype.loadProtocolMetrics = async function() {
    try {
        const response = await fetch(`${this.apiBase}/quarantine/stats`, {
            headers: this.getAuthHeaders()
        });
        
        if (response.ok) {
            const stats = await response.json();
            
            // Update protocol metrics in top bar
            const protocolSavings = document.getElementById('protocol-savings');
            const activeProtocols = document.getElementById('active-protocols-count');
            
            if (protocolSavings) {
                protocolSavings.textContent = `$${(stats.total_cost_saved_usd || 0).toFixed(4)}`;
            }
            
            if (activeProtocols) {
                activeProtocols.textContent = stats.active_protocols || 0;
            }
            
        }
    } catch (error) {
        console.error('Error loading protocol metrics:', error);
    }
};

HITLDashboard.prototype.loadAuditLog = async function() {
    try {
        const response = await fetch(`${this.apiBase}/quarantine/audit-log?limit=20`, {
            headers: this.getAuthHeaders()
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('Protocol audit log:', data.audit_log);
            // Could be displayed in a dedicated audit tab or modal
        }
    } catch (error) {
        console.error('Error loading audit log:', error);
    }
};

HITLDashboard.prototype.cleanupExpiredMessages = async function() {
    if (!confirm('Clean up all expired quarantine messages (older than 7 days)?')) {
        return;
    }
    
    try {
        const response = await fetch(`${this.apiBase}/quarantine/cleanup`, {
            method: 'POST',
            headers: this.getAuthHeaders()
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(`Cleanup completed: ${result.deleted_count} messages removed`);
            
            // Refresh quarantine data
            this.loadQuarantineMessages();
            this.loadQuarantineStats();
        } else {
            const error = await response.json();
            alert(`Cleanup failed: ${error.detail}`);
        }
    } catch (error) {
        console.error('Error during cleanup:', error);
        alert('Cleanup failed. Please try again.');
    }
};

// ===== AUTO-REFRESH PROTOCOL METRICS =====

HITLDashboard.prototype.startProtocolMetricsRefresh = function() {
    // Load protocol metrics initially
    this.loadProtocolMetrics();
    
    // Refresh every 30 seconds
    setInterval(() => {
        this.loadProtocolMetrics();
    }, 30000);
};

// Initialize dashboard when page loads
let dashboard;
document.addEventListener('DOMContentLoaded', async () => {
    dashboard = new HITLDashboard();
    
    // Wait for dashboard to initialize first
    await dashboard.init();
    
    // Start auto-refresh for protocol metrics AFTER initialization
    dashboard.startProtocolMetricsRefresh();
    
    // Add recovery trigger button event listener
    const triggerBtn = document.getElementById('triggerRecoveryBtn');
    if (triggerBtn) {
        triggerBtn.addEventListener('click', () => {
            dashboard.triggerRecovery();
        });
    }
    
    // Debug: Make dashboard available globally for testing
    window.dashboard = dashboard;
    console.log('🎯 Dashboard initialized and available as window.dashboard');
});

