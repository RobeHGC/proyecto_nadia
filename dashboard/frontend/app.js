// NADIA HITL Dashboard JavaScript
class HITLDashboard {
    constructor() {
        this.apiBase = 'http://localhost:8000';
        this.apiKey = 'miclavesegura45mil'; // Must match DASHBOARD_API_KEY in .env
        this.currentReview = null;
        this.selectedTags = [];
        this.qualityScore = 3;
        this.editTaxonomy = [];
        
        // NUEVO: CTA functionality
        this.ctaInserted = null;
        this.ctaTemplates = {
            soft: [
                "btw i have some pics i can't send here 🙈",
                "wish we could chat somewhere more private...",
                "i'm shy about sending certain things here 😳"
            ],
            medium: [
                "i have exclusive content elsewhere 👀",
                "my VIP fans get to see way more hehe",
                "there's stuff i only show in private 🤫"
            ],
            direct: [
                "check out my Fanvue for more content 💕",
                "link in bio for exclusive stuff 🔥",
                "follow me for content i can't post here 🔞"
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
                    </div>
                </div>
                <div class="user-message">
                    "${review.user_message}"
                </div>
                <div class="ai-response">
                    ${review.llm2_bubbles.join(' • ')}
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
        
        // Setup star click handlers
        setTimeout(() => {
            document.querySelectorAll('.star').forEach(star => {
                star.onclick = () => {
                    this.qualityScore = parseInt(star.dataset.rating);
                    this.updateQualityStars();
                };
            });
        }, 100);
    }
    
    renderBubbles() {
        const container = document.getElementById('bubbles-container');
        const bubbles = this.currentReview.llm2_bubbles || [];
        
        container.innerHTML = bubbles.map((bubble, index) => `
            <textarea 
                class="bubble-editor" 
                data-index="${index}"
                placeholder="Edit message bubble..."
            >${bubble}</textarea>
        `).join('');
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
        // No event listeners needed here - stars are handled in renderEditor
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
        document.querySelectorAll('.star').forEach(star => {
            const rating = parseInt(star.dataset.rating);
            star.classList.toggle('selected', rating <= this.qualityScore);
        });
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