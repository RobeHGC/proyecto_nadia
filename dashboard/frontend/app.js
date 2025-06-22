// NADIA HITL Dashboard JavaScript
class HITLDashboard {
    constructor() {
        this.apiBase = 'http://localhost:8000';
        this.apiKey = 'miclavesegura45mil'; // Must match DASHBOARD_API_KEY in .env
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
    
    async init() {
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
            this.updateQuotaDisplay(metrics.gemini_quota_used_today, metrics.gemini_quota_total);
            this.updateSavingsDisplay(metrics.savings_today_usd);
        } catch (error) {
            console.error('Failed to load metrics:', error);
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
        
        const reviewerNotes = prompt('Optional reviewer notes (for training data analysis):') || '';
        
        try {
            // NUEVO: Prepare approval data with CTA information
            const approvalData = {
                final_bubbles: finalBubbles,
                edit_tags: this.selectedTags,
                quality_score: this.qualityScore,
                reviewer_notes: reviewerNotes
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
        
        const reviewerNotes = prompt('Reason for rejection:') || '';
        
        try {
            const response = await fetch(`${this.apiBase}/reviews/${this.currentReview.id}/reject`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify({
                    reviewer_notes: reviewerNotes
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
            if (!choice) return; // User cancelled
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
        const percentage = (used / total) * 100;
        const quotaText = `${used.toLocaleString()} / ${total.toLocaleString()}`;
        
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
        const reason = prompt('Reason for status change (optional):', 'Manual update from dashboard') || 'Manual update from dashboard';
        
        try {
            const response = await fetch(`${this.apiBase}/users/${this.currentReview.user_id}/customer-status`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify({
                    user_id: this.currentReview.user_id,
                    customer_status: newStatus,
                    reason: reason,
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

// Initialize dashboard when page loads
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new HITLDashboard();
});