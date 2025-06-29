// knowledge-management.js
// JavaScript for NADIA Knowledge Management Interface

class KnowledgeManager {
    constructor() {
        this.apiBase = 'http://localhost:8000';
        this.apiKey = null;
        this.init();
    }
    
    async init() {
        // Load configuration from server
        await this.loadConfig();
        this.setupEventListeners();
    }
    
    async loadConfig() {
        try {
            const response = await fetch('/api/config');
            if (response.ok) {
                const config = await response.json();
                this.apiKey = config.apiKey;
                this.apiBase = config.apiBase;
            } else {
                console.warn('Failed to load config from server');
                this.apiKey = 'dev-fallback-key';
            }
        } catch (error) {
            console.error('Failed to load config:', error);
            this.apiKey = 'dev-fallback-key';
        }
    }
    
    getAuthHeaders() {
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.apiKey}`
        };
    }
    
    setupEventListeners() {
        // Upload form
        document.getElementById('uploadForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.uploadDocument();
        });
        
        // Search form
        document.getElementById('searchForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.searchKnowledge();
        });
        
        // User learning form
        document.getElementById('userForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.updateUserLearning();
        });
    }
    
    async uploadDocument() {
        const form = document.getElementById('uploadForm');
        const formData = new FormData(form);
        
        const document = {
            title: formData.get('title'),
            content: formData.get('content'),
            source: formData.get('source'),
            category: formData.get('category'),
            metadata: {}
        };
        
        try {
            const response = await fetch(`${this.apiBase}/api/knowledge/documents`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(document)
            });
            
            if (response.ok) {
                const result = await response.json();
                this.showMessage('success', `Document uploaded successfully! ID: ${result.document_id}`);
                form.reset();
            } else {
                const error = await response.json();
                this.showMessage('error', `Upload failed: ${error.detail}`);
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showMessage('error', 'Upload failed. Check if RAG system is available.');
        }
    }
    
    async searchKnowledge() {
        const query = document.getElementById('searchQuery').value;
        const categoryFilter = document.getElementById('searchCategory').value;
        
        if (!query.trim()) {
            this.showMessage('error', 'Please enter a search query');
            return;
        }
        
        try {
            const params = new URLSearchParams({
                query: query,
                max_results: '10'
            });
            
            if (categoryFilter) {
                params.append('category_filter', categoryFilter);
            }
            
            const response = await fetch(`${this.apiBase}/api/knowledge/documents/search?${params}`, {
                headers: this.getAuthHeaders()
            });
            
            if (response.ok) {
                const results = await response.json();
                this.displaySearchResults(results);
            } else {
                const error = await response.json();
                this.showMessage('error', `Search failed: ${error.detail}`);
            }
        } catch (error) {
            console.error('Search error:', error);
            this.showMessage('error', 'Search failed. Check if RAG system is available.');
        }
    }
    
    displaySearchResults(results) {
        const container = document.getElementById('searchResults');
        
        if (results.length === 0) {
            container.innerHTML = '<div class="search-result">No results found.</div>';
            return;
        }
        
        let html = `<h4>Found ${results.length} results:</h4>`;
        
        results.forEach(result => {
            const similarityPercent = Math.round(result.similarity_score * 100);
            html += `
                <div class="search-result">
                    <div class="result-title">
                        ${result.title}
                        <span class="similarity-score">${similarityPercent}%</span>
                    </div>
                    <div class="result-meta">
                        Category: ${result.category} | Source: ${result.source}
                    </div>
                    <div class="result-content">
                        ${result.content.length > 200 ? result.content.substring(0, 200) + '...' : result.content}
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }
    
    async updateUserLearning() {
        const userId = document.getElementById('userId').value;
        const interestsInput = document.getElementById('interests').value;
        
        if (!userId.trim()) {
            this.showMessage('error', 'Please enter a user ID');
            return;
        }
        
        const learningData = {
            user_id: userId,
            interests: interestsInput ? interestsInput.split(',').map(s => s.trim()) : null
        };
        
        try {
            const response = await fetch(`${this.apiBase}/api/knowledge/user-learning`, {
                method: 'POST',
                headers: this.getAuthHeaders(),
                body: JSON.stringify(learningData)
            });
            
            if (response.ok) {
                const result = await response.json();
                this.showMessage('success', 'User learning updated successfully!');
                document.getElementById('userForm').reset();
            } else {
                const error = await response.json();
                this.showMessage('error', `Update failed: ${error.detail}`);
            }
        } catch (error) {
            console.error('User learning update error:', error);
            this.showMessage('error', 'Update failed. Check if RAG system is available.');
        }
    }
    
    async getUserPreferences() {
        const userId = document.getElementById('userId').value;
        
        if (!userId.trim()) {
            this.showMessage('error', 'Please enter a user ID');
            return;
        }
        
        try {
            const response = await fetch(`${this.apiBase}/api/knowledge/user/${userId}/preferences`, {
                headers: this.getAuthHeaders()
            });
            
            if (response.ok) {
                const preferences = await response.json();
                this.displayUserPreferences(preferences);
            } else {
                const error = await response.json();
                this.showMessage('error', `Failed to get preferences: ${error.detail}`);
            }
        } catch (error) {
            console.error('Get preferences error:', error);
            this.showMessage('error', 'Failed to get preferences. Check if RAG system is available.');
        }
    }
    
    displayUserPreferences(preferences) {
        const container = document.getElementById('userResults');
        
        if (!preferences.preferences_found) {
            container.innerHTML = '<div class="search-result">No preferences found for this user.</div>';
            return;
        }
        
        let html = `
            <div class="search-result">
                <div class="result-title">User Preferences for ${preferences.user_id}</div>
                <div class="result-content">
                    <strong>Interests:</strong> ${preferences.interests.join(', ') || 'None'}<br>
                    <strong>Last Updated:</strong> ${preferences.last_updated ? new Date(preferences.last_updated).toLocaleString() : 'Never'}
                </div>
            </div>
        `;
        
        container.innerHTML = html;
    }
    
    async loadStats() {
        const container = document.getElementById('statsContainer');
        container.innerHTML = '<div class="loading">Loading statistics...</div>';
        
        try {
            const response = await fetch(`${this.apiBase}/api/knowledge/stats`, {
                headers: this.getAuthHeaders()
            });
            
            if (response.ok) {
                const stats = await response.json();
                this.displayStats(stats);
            } else {
                const error = await response.json();
                container.innerHTML = `<div class="error-message">Failed to load stats: ${error.detail}</div>`;
            }
        } catch (error) {
            console.error('Stats loading error:', error);
            container.innerHTML = '<div class="error-message">Failed to load stats. RAG system may not be available.</div>';
        }
    }
    
    displayStats(stats) {
        const container = document.getElementById('statsContainer');
        
        const html = `
            <div class="stat-card">
                <div class="stat-number">${stats.total_documents}</div>
                <div class="stat-label">Knowledge Documents</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${stats.total_users_with_preferences}</div>
                <div class="stat-label">Users with Preferences</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${stats.total_conversation_embeddings}</div>
                <div class="stat-label">Conversation Embeddings</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${stats.embeddings_cache_size}</div>
                <div class="stat-label">Embeddings Cache Size</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${stats.rag_system_status}</div>
                <div class="stat-label">RAG System Status</div>
            </div>
        `;
        
        container.innerHTML = html;
    }
    
    showMessage(type, message) {
        // Remove existing messages
        const existingMessages = document.querySelectorAll('.success-message, .error-message');
        existingMessages.forEach(msg => msg.remove());
        
        // Create new message
        const messageDiv = document.createElement('div');
        messageDiv.className = type === 'success' ? 'success-message' : 'error-message';
        messageDiv.textContent = message;
        
        // Insert at the beginning of the active tab content
        const activeTab = document.querySelector('.tab-content.active');
        activeTab.insertBefore(messageDiv, activeTab.firstChild);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            messageDiv.remove();
        }, 5000);
    }
}

// Tab switching functionality
function showTab(tabName) {
    // Hide all tab contents
    const contents = document.querySelectorAll('.tab-content');
    contents.forEach(content => content.classList.remove('active'));
    
    // Remove active class from all tabs
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => tab.classList.remove('active'));
    
    // Show selected tab content
    document.getElementById(tabName).classList.add('active');
    
    // Add active class to clicked tab
    event.target.classList.add('active');
}

// Global functions for HTML onclick handlers
function loadStats() {
    window.knowledgeManager.loadStats();
}

function getUserPreferences() {
    window.knowledgeManager.getUserPreferences();
}

// Initialize the knowledge manager when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.knowledgeManager = new KnowledgeManager();
});