"""
Dashboard Page Object for NADIA UI Testing

This module provides page object for the main dashboard interface,
including navigation, review queue, and basic dashboard functionality.
"""
from typing import List, Dict, Optional
from .base_page import BasePage


class DashboardPage(BasePage):
    """Page object for the main NADIA dashboard."""
    
    @property
    def page_url(self) -> str:
        return "/"
    
    @property 
    def page_title_selector(self) -> str:
        return "h1, .dashboard-title, [data-testid='dashboard-title']"
    
    @property
    def loading_indicator_selector(self) -> str:
        return ".loading, .spinner, [data-testid='loading']"
    
    # Navigation selectors
    REVIEWS_TAB = "#reviews-tab, [data-tab='reviews']"
    ANALYTICS_TAB = "#analytics-tab, [data-tab='analytics']"
    QUARANTINE_TAB = "#quarantine-tab, [data-tab='quarantine']"
    RECOVERY_TAB = "#recovery-tab, [data-tab='recovery']"
    
    # Review queue selectors
    REVIEW_QUEUE = "#review-queue, .review-queue"
    REVIEW_ITEMS = ".review-item, [data-testid='review-item']"
    PENDING_COUNT = ".pending-count, [data-testid='pending-count']"
    
    # Status indicators
    STATUS_INDICATOR = ".status-indicator, [data-testid='status']"
    HEALTH_STATUS = ".health-status, [data-testid='health-status']"
    
    async def get_current_tab(self) -> str:
        """Get the currently active tab."""
        script = """
        const activeTab = document.querySelector('.tab.active, .nav-tab.active');
        return activeTab ? activeTab.textContent.trim() : '';
        """
        
        result = await self.browser.evaluate(script)
        return result or "unknown"
    
    async def navigate_to_reviews(self) -> bool:
        """Navigate to the reviews tab."""
        success = await self.click_element(self.REVIEWS_TAB)
        if success:
            await self.wait_for_element(self.REVIEW_QUEUE)
        return success
    
    async def navigate_to_analytics(self) -> bool:
        """Navigate to the analytics tab."""
        success = await self.click_element(self.ANALYTICS_TAB)
        if success:
            # Wait for analytics content to load
            await self.wait_for_element(".analytics-content, #analytics-content")
        return success
    
    async def navigate_to_quarantine(self) -> bool:
        """Navigate to the quarantine tab."""
        success = await self.click_element(self.QUARANTINE_TAB)
        if success:
            # Wait for quarantine content to load
            await self.wait_for_element(".quarantine-content, #quarantine-content")
        return success
    
    async def navigate_to_recovery(self) -> bool:
        """Navigate to the recovery tab."""
        success = await self.click_element(self.RECOVERY_TAB)
        if success:
            # Wait for recovery content to load
            await self.wait_for_element(".recovery-content, #recovery-content")
        return success
    
    async def get_pending_review_count(self) -> int:
        """Get the number of pending reviews."""
        if not await self.is_element_visible(self.PENDING_COUNT):
            return 0
        
        count_text = await self.get_element_text(self.PENDING_COUNT)
        
        # Extract number from text like "5 pending" or just "5"
        import re
        match = re.search(r'\d+', count_text)
        return int(match.group()) if match else 0
    
    async def get_review_items(self) -> List[Dict[str, str]]:
        """Get list of review items with their basic info."""
        if not await self.is_element_visible(self.REVIEW_ITEMS):
            return []
        
        script = f"""
        const items = document.querySelectorAll('{self.REVIEW_ITEMS}');
        return Array.from(items).map(item => {{
            const id = item.getAttribute('data-review-id') || 
                      item.querySelector('[data-review-id]')?.getAttribute('data-review-id') || 
                      '';
            
            const message = item.querySelector('.user-message, [data-testid="user-message"]')?.textContent?.trim() || '';
            const user = item.querySelector('.user-info, [data-testid="user-info"]')?.textContent?.trim() || '';
            const timestamp = item.querySelector('.timestamp, [data-testid="timestamp"]')?.textContent?.trim() || '';
            
            return {{
                id: id,
                message: message,
                user: user,
                timestamp: timestamp
            }};
        }});
        """
        
        result = await self.browser.evaluate(script)
        return result or []
    
    async def get_system_status(self) -> Dict[str, str]:
        """Get current system status information."""
        status_info = {}
        
        # Overall status
        if await self.is_element_visible(self.STATUS_INDICATOR):
            status_info['overall'] = await self.get_element_text(self.STATUS_INDICATOR)
        
        # Health status
        if await self.is_element_visible(self.HEALTH_STATUS):
            status_info['health'] = await self.get_element_text(self.HEALTH_STATUS)
        
        # Additional status indicators
        script = """
        const statusElements = document.querySelectorAll('[data-status], .status-item');
        const status = {};
        
        statusElements.forEach(element => {
            const key = element.getAttribute('data-status') || 
                       element.className.match(/status-(\w+)/)?.[1] || 
                       'unknown';
            const value = element.textContent.trim();
            status[key] = value;
        });
        
        return status;
        """
        
        additional_status = await self.browser.evaluate(script)
        if additional_status:
            status_info.update(additional_status)
        
        return status_info
    
    async def refresh_dashboard(self) -> bool:
        """Refresh the dashboard data."""
        refresh_button = ".refresh-btn, [data-action='refresh'], button[title*='refresh' i]"
        
        if await self.is_element_visible(refresh_button):
            return await self.click_element(refresh_button)
        else:
            # Fallback: refresh the page
            return await self.navigate()
    
    async def search_reviews(self, query: str) -> bool:
        """Search for reviews using the search functionality."""
        search_input = "#search, .search-input, [data-testid='search']"
        search_button = ".search-btn, [data-action='search']"
        
        if not await self.is_element_visible(search_input):
            return False
        
        # Enter search query
        await self.fill_input(search_input, query)
        
        # Click search button if available, otherwise rely on search-as-you-type
        if await self.is_element_visible(search_button):
            await self.click_element(search_button)
        else:
            # Trigger search with Enter key
            await self.press_key('Enter', search_input)
        
        # Wait for search results
        await self._wait_for_api_requests()
        
        return True
    
    async def clear_search(self) -> bool:
        """Clear the search query."""
        search_input = "#search, .search-input, [data-testid='search']"
        clear_button = ".search-clear, [data-action='clear-search']"
        
        if await self.is_element_visible(clear_button):
            return await self.click_element(clear_button)
        elif await self.is_element_visible(search_input):
            await self.fill_input(search_input, "")
            await self.press_key('Enter', search_input)
            return True
        
        return False
    
    async def get_navigation_tabs(self) -> List[str]:
        """Get list of available navigation tabs."""
        script = """
        const tabs = document.querySelectorAll('.tab, .nav-tab, [role="tab"]');
        return Array.from(tabs).map(tab => tab.textContent.trim()).filter(text => text);
        """
        
        result = await self.browser.evaluate(script)
        return result or []
    
    async def is_tab_active(self, tab_name: str) -> bool:
        """Check if a specific tab is currently active."""
        script = f"""
        const tabs = document.querySelectorAll('.tab, .nav-tab, [role="tab"]');
        const targetTab = Array.from(tabs).find(tab => 
            tab.textContent.trim().toLowerCase().includes('{tab_name.lower()}'));
        
        if (!targetTab) return false;
        
        return targetTab.classList.contains('active') || 
               targetTab.getAttribute('aria-selected') === 'true';
        """
        
        result = await self.browser.evaluate(script)
        return bool(result)
    
    async def get_dashboard_metrics(self) -> Dict[str, str]:
        """Get dashboard metrics/statistics."""
        script = """
        const metrics = {};
        
        // Look for metric cards or stat elements
        const metricElements = document.querySelectorAll(
            '.metric, .stat, .dashboard-stat, [data-metric]'
        );
        
        metricElements.forEach(element => {
            const label = element.querySelector('.label, .metric-label')?.textContent?.trim() ||
                         element.getAttribute('data-metric') ||
                         'unknown';
            
            const value = element.querySelector('.value, .metric-value')?.textContent?.trim() ||
                         element.textContent.trim();
            
            metrics[label] = value;
        });
        
        return metrics;
        """
        
        result = await self.browser.evaluate(script)
        return result or {}
    
    async def wait_for_dashboard_load(self, timeout: int = 15000) -> bool:
        """Wait for the dashboard to fully load with all its components."""
        # Wait for basic page load
        await self.wait_for_page_load()
        
        # Wait for specific dashboard elements
        dashboard_elements = [
            ".dashboard-content",
            ".review-queue",
            "#reviews-tab",
            ".tab, .nav-tab"
        ]
        
        for selector in dashboard_elements:
            try:
                await self.wait_for_element(selector, timeout=3000)
            except:
                # Continue if optional elements don't load
                pass
        
        return True
    
    async def take_dashboard_screenshot(self, name: str = "dashboard") -> bool:
        """Take a screenshot of the entire dashboard."""
        return await self.take_screenshot(name)
    
    async def has_error_messages(self) -> bool:
        """Check if there are any error messages displayed."""
        error_selectors = [
            ".error, .alert-error, .alert-danger",
            "[data-testid='error']",
            ".notification.error"
        ]
        
        for selector in error_selectors:
            if await self.is_element_visible(selector):
                return True
        
        return False
    
    async def get_error_messages(self) -> List[str]:
        """Get any error messages currently displayed."""
        if not await self.has_error_messages():
            return []
        
        script = """
        const errorSelectors = [
            '.error', '.alert-error', '.alert-danger',
            '[data-testid="error"]', '.notification.error'
        ];
        
        const errors = [];
        errorSelectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                const text = el.textContent.trim();
                if (text) errors.push(text);
            });
        });
        
        return [...new Set(errors)]; // Remove duplicates
        """
        
        result = await self.browser.evaluate(script)
        return result or []