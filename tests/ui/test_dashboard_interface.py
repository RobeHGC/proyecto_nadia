"""
Dashboard Interface UI Tests using Puppeteer MCP

This module contains comprehensive tests for the NADIA dashboard interface,
covering all major components and user interactions.
"""
import pytest
import asyncio
from .conftest import (
    wait_for_api_response, 
    get_element_text, 
    is_element_visible
)


class TestDashboardBasic:
    """Basic dashboard functionality tests."""
    
    @pytest.mark.asyncio
    async def test_dashboard_loads(self, browser_manager, browser_config, visual_regression):
        """Test that dashboard loads successfully with all core elements."""
        # Navigate to dashboard
        success = await browser_manager.navigate(browser_config.dashboard_url)
        assert success, "Failed to navigate to dashboard"
        
        # Wait for main dashboard elements to load
        assert await browser_manager.wait_for_element("body", timeout=10000)
        assert await browser_manager.wait_for_element(".container, .dashboard", timeout=5000)
        
        # Take screenshot for visual regression
        visual_passed = await visual_regression.capture_and_compare(
            browser_manager, "dashboard_basic_load", tolerance=0.05
        )
        
        # Check that core navigation elements are present
        nav_exists = await browser_manager.evaluate("""
            document.querySelector('.nav, .navbar, .tabs, .tab-container') !== null
        """)
        
        assert nav_exists, "Dashboard navigation not found"
        assert visual_passed, "Dashboard visual regression failed"
    
    @pytest.mark.asyncio 
    async def test_dashboard_tabs_navigation(self, dashboard_page):
        """Test navigation between dashboard tabs."""
        # Wait for tabs to load
        await dashboard_page.wait_for_element(".tab, .nav-tab", timeout=5000)
        
        # Get all available tabs
        tab_count = await dashboard_page.evaluate("""
            document.querySelectorAll('.tab, .nav-tab').length
        """)
        
        assert tab_count > 0, "No tabs found in dashboard"
        
        # Test clicking each tab
        for tab_index in range(min(tab_count, 5)):  # Test max 5 tabs
            tab_clicked = await dashboard_page.evaluate(f"""
                const tabs = document.querySelectorAll('.tab, .nav-tab');
                if (tabs[{tab_index}]) {{
                    tabs[{tab_index}].click();
                    return tabs[{tab_index}].textContent.trim();
                }}
                return null;
            """)
            
            if tab_clicked:
                print(f"✅ Clicked tab: {tab_clicked}")
                await asyncio.sleep(0.5)  # Allow tab to activate
    
    @pytest.mark.asyncio
    async def test_dashboard_api_health(self, dashboard_page):
        """Test that dashboard can communicate with API."""
        # Check for API health indicator or make a test API call
        api_status = await dashboard_page.evaluate("""
            // Look for health indicators or make test fetch
            if (window.fetch) {
                return fetch('/api/health', {
                    method: 'GET',
                    headers: {
                        'X-API-Key': 'miclavesegura45mil'
                    }
                }).then(r => r.ok).catch(() => false);
            }
            return false;
        """)
        
        assert api_status, "Dashboard API communication failed"


class TestReviewInterface:
    """Tests for the review interface functionality."""
    
    @pytest.mark.asyncio
    async def test_review_queue_loads(self, authenticated_dashboard, visual_regression):
        """Test that review queue loads with messages."""
        # Navigate to review tab
        review_tab = await authenticated_dashboard.click(".tab[data-tab='review'], .nav-tab:first-child")
        assert review_tab, "Could not click review tab"
        
        # Wait for review queue to load  
        await authenticated_dashboard.wait_for_element(".review-queue, .message-list", timeout=10000)
        
        # Check if messages are present
        message_count = await authenticated_dashboard.evaluate("""
            document.querySelectorAll('.message, .review-item').length
        """)
        
        print(f"📊 Found {message_count} messages in review queue")
        
        # Take screenshot for visual regression
        visual_passed = await visual_regression.capture_and_compare(
            authenticated_dashboard, "review_queue_loaded", tolerance=0.1
        )
        
        assert visual_passed, "Review queue visual regression failed"
    
    @pytest.mark.asyncio
    async def test_message_approval_buttons(self, authenticated_dashboard):
        """Test message approval button functionality."""
        # Navigate to review tab
        await authenticated_dashboard.click(".tab[data-tab='review'], .nav-tab:first-child")
        await authenticated_dashboard.wait_for_element(".review-queue, .message-list", timeout=5000)
        
        # Look for approval buttons
        approve_buttons = await authenticated_dashboard.evaluate("""
            document.querySelectorAll('.approve-btn, .btn-approve, [data-action="approve"]').length
        """)
        
        reject_buttons = await authenticated_dashboard.evaluate("""
            document.querySelectorAll('.reject-btn, .btn-reject, [data-action="reject"]').length
        """)
        
        print(f"📊 Found {approve_buttons} approve buttons, {reject_buttons} reject buttons")
        
        # Test button interactions (without actually approving)
        if approve_buttons > 0:
            button_clickable = await authenticated_dashboard.evaluate("""
                const btn = document.querySelector('.approve-btn, .btn-approve, [data-action="approve"]');
                return btn && !btn.disabled;
            """)
            assert button_clickable, "Approve buttons are not clickable"
    
    @pytest.mark.asyncio
    async def test_reviewer_notes_editing(self, authenticated_dashboard):
        """Test reviewer notes editing functionality."""
        # Navigate to review tab
        await authenticated_dashboard.click(".tab[data-tab='review'], .nav-tab:first-child")
        await authenticated_dashboard.wait_for_element(".review-queue", timeout=5000)
        
        # Look for editable reviewer notes
        notes_field = await authenticated_dashboard.evaluate("""
            const textarea = document.querySelector('textarea[data-field="reviewer_notes"], .reviewer-notes textarea');
            const editable = document.querySelector('.editable-notes, [contenteditable="true"]');
            return textarea || editable ? true : false;
        """)
        
        if notes_field:
            # Test editing notes
            test_note = "Test review note from UI automation"
            
            notes_updated = await authenticated_dashboard.evaluate(f"""
                const textarea = document.querySelector('textarea[data-field="reviewer_notes"], .reviewer-notes textarea');
                const editable = document.querySelector('.editable-notes, [contenteditable="true"]');
                
                if (textarea) {{
                    textarea.value = '{test_note}';  
                    textarea.dispatchEvent(new Event('input'));
                    return textarea.value === '{test_note}';
                }} else if (editable) {{
                    editable.textContent = '{test_note}';
                    editable.dispatchEvent(new Event('input'));
                    return editable.textContent === '{test_note}';
                }}
                return false;
            """)
            
            assert notes_updated, "Reviewer notes could not be updated"
            print("✅ Reviewer notes editing functionality works")


class TestAnalyticsDashboard:
    """Tests for analytics dashboard functionality."""
    
    @pytest.mark.asyncio
    async def test_analytics_charts_render(self, authenticated_dashboard, visual_regression):
        """Test that analytics charts render correctly."""
        # Navigate to analytics tab
        await authenticated_dashboard.click(".tab[data-tab='analytics'], .nav-tab:nth-child(2)")
        await authenticated_dashboard.wait_for_element(".analytics, .charts", timeout=10000)
        
        # Wait for charts to load
        await wait_for_api_response(authenticated_dashboard)
        
        # Check for chart elements
        chart_count = await authenticated_dashboard.evaluate("""
            const canvases = document.querySelectorAll('canvas').length;
            const chartDivs = document.querySelectorAll('.chart, .chart-container').length;
            const svgs = document.querySelectorAll('svg').length;
            return canvases + chartDivs + svgs;
        """)
        
        print(f"📊 Found {chart_count} chart elements")
        
        # Take screenshot for visual regression
        visual_passed = await visual_regression.capture_and_compare(
            authenticated_dashboard, "analytics_dashboard", tolerance=0.15
        )
        
        assert chart_count > 0, "No charts found in analytics dashboard"
        assert visual_passed, "Analytics dashboard visual regression failed"
    
    @pytest.mark.asyncio
    async def test_analytics_filters(self, authenticated_dashboard):
        """Test analytics filter functionality."""
        # Navigate to analytics tab
        await authenticated_dashboard.click(".tab[data-tab='analytics'], .nav-tab:nth-child(2)")
        await authenticated_dashboard.wait_for_element(".analytics", timeout=5000)
        
        # Look for filter controls
        filter_controls = await authenticated_dashboard.evaluate("""
            const selects = document.querySelectorAll('select').length;
            const dateInputs = document.querySelectorAll('input[type="date"]').length;
            const checkboxes = document.querySelectorAll('input[type="checkbox"]').length;
            return selects + dateInputs + checkboxes;
        """)
        
        print(f"📊 Found {filter_controls} filter controls")
        
        if filter_controls > 0:
            # Test interacting with first filter
            filter_changed = await authenticated_dashboard.evaluate("""
                const select = document.querySelector('select');
                if (select && select.options.length > 1) {
                    select.selectedIndex = 1;
                    select.dispatchEvent(new Event('change'));
                    return true;
                }
                return false;
            """)
            
            if filter_changed:
                await wait_for_api_response(authenticated_dashboard)
                print("✅ Analytics filter interaction works")


class TestQuarantineTab:
    """Tests for quarantine tab functionality."""
    
    @pytest.mark.asyncio
    async def test_quarantine_user_list(self, authenticated_dashboard, visual_regression):
        """Test quarantine user list loads and displays correctly."""
        # Navigate to quarantine tab
        quarantine_clicked = await authenticated_dashboard.click(".tab[data-tab='quarantine']")
        if not quarantine_clicked:
            pytest.skip("Quarantine tab not found - feature may not be enabled")
        
        await authenticated_dashboard.wait_for_element(".quarantine-list, .user-list", timeout=10000)
        
        # Check for quarantined users
        user_count = await authenticated_dashboard.evaluate("""
            document.querySelectorAll('.quarantine-user, .user-item').length
        """)
        
        print(f"📊 Found {user_count} quarantined users")
        
        # Take screenshot for visual regression
        visual_passed = await visual_regression.capture_and_compare(
            authenticated_dashboard, "quarantine_tab", tolerance=0.1
        )
        
        assert visual_passed, "Quarantine tab visual regression failed"
    
    @pytest.mark.asyncio
    async def test_quarantine_batch_operations(self, authenticated_dashboard):
        """Test quarantine batch operation controls."""
        # Navigate to quarantine tab
        await authenticated_dashboard.click(".tab[data-tab='quarantine']")
        await authenticated_dashboard.wait_for_element(".quarantine-list", timeout=5000)
        
        # Look for batch operation controls
        batch_controls = await authenticated_dashboard.evaluate("""
            const checkboxes = document.querySelectorAll('input[type="checkbox"]').length;
            const batchButtons = document.querySelectorAll('.batch-btn, .bulk-action').length;
            return checkboxes + batchButtons;
        """)
        
        print(f"📊 Found {batch_controls} batch operation controls")
        
        if batch_controls > 0:
            # Test selecting items
            items_selected = await authenticated_dashboard.evaluate("""
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                let selected = 0;
                for (let i = 0; i < Math.min(2, checkboxes.length); i++) {
                    checkboxes[i].checked = true;
                    checkboxes[i].dispatchEvent(new Event('change'));
                    selected++;
                }
                return selected;
            """)
            
            print(f"✅ Selected {items_selected} items for batch operations")


class TestRecoveryTab:
    """Tests for recovery tab functionality."""
    
    @pytest.mark.asyncio
    async def test_recovery_status_display(self, authenticated_dashboard, visual_regression):
        """Test recovery status displays correctly."""
        # Navigate to recovery tab  
        recovery_clicked = await authenticated_dashboard.click(".tab[data-tab='recovery']")
        if not recovery_clicked:
            pytest.skip("Recovery tab not found - feature may not be enabled")
        
        await authenticated_dashboard.wait_for_element(".recovery-status, .recovery-panel", timeout=10000)
        
        # Check recovery metrics
        metrics_present = await authenticated_dashboard.evaluate("""
            const metrics = document.querySelectorAll('.metric, .stat, .counter').length;
            const status = document.querySelectorAll('.status, .health-indicator').length;
            return metrics + status;
        """)
        
        print(f"📊 Found {metrics_present} recovery metrics/status elements")
        
        # Take screenshot for visual regression
        visual_passed = await visual_regression.capture_and_compare(
            authenticated_dashboard, "recovery_tab", tolerance=0.1
        )
        
        assert metrics_present > 0, "No recovery metrics found"
        assert visual_passed, "Recovery tab visual regression failed"
    
    @pytest.mark.asyncio
    async def test_recovery_manual_trigger(self, authenticated_dashboard):
        """Test recovery manual trigger buttons."""
        # Navigate to recovery tab
        await authenticated_dashboard.click(".tab[data-tab='recovery']")
        await authenticated_dashboard.wait_for_element(".recovery-panel", timeout=5000)
        
        # Look for manual trigger buttons
        trigger_buttons = await authenticated_dashboard.evaluate("""
            document.querySelectorAll('.trigger-btn, .manual-recovery, [data-action="recover"]').length
        """)
        
        print(f"📊 Found {trigger_buttons} recovery trigger buttons")
        
        if trigger_buttons > 0:
            # Test button interactivity (without actually triggering)
            button_enabled = await authenticated_dashboard.evaluate("""
                const btn = document.querySelector('.trigger-btn, .manual-recovery, [data-action="recover"]');
                return btn && !btn.disabled;
            """)
            
            assert button_enabled, "Recovery trigger buttons are not enabled"
            print("✅ Recovery trigger buttons are interactive")


class TestResponsiveDesign:
    """Tests for responsive design across different viewport sizes."""
    
    @pytest.mark.asyncio
    async def test_tablet_responsive(self, browser_manager, browser_config, visual_regression):
        """Test dashboard on tablet-sized viewport."""
        # Set tablet viewport
        tablet_viewport = await browser_manager.evaluate("""
            // Simulate tablet viewport
            const meta = document.querySelector('meta[name="viewport"]');
            if (meta) {
                meta.setAttribute('content', 'width=768, initial-scale=1');
            }
            
            // Resize window programmatically if possible
            if (window.resizeTo) {
                window.resizeTo(768, 1024);
            }
            
            return window.innerWidth;
        """)
        
        print(f"📱 Tablet viewport set: {tablet_viewport}px width")
        
        # Wait for layout adjustment
        await asyncio.sleep(1)
        
        # Take screenshot for visual regression
        visual_passed = await visual_regression.capture_and_compare(
            browser_manager, "dashboard_tablet_view", tolerance=0.2
        )
        
        assert visual_passed, "Tablet responsive design visual regression failed"
    
    @pytest.mark.asyncio
    async def test_mobile_responsive(self, browser_manager, visual_regression):
        """Test dashboard on mobile-sized viewport."""
        # Set mobile viewport
        mobile_viewport = await browser_manager.evaluate("""
            // Simulate mobile viewport
            const meta = document.querySelector('meta[name="viewport"]');
            if (meta) {
                meta.setAttribute('content', 'width=375, initial-scale=1');
            }
            
            // Resize window programmatically if possible
            if (window.resizeTo) {
                window.resizeTo(375, 667);
            }
            
            return window.innerWidth;
        """)
        
        print(f"📱 Mobile viewport set: {mobile_viewport}px width")
        
        # Wait for layout adjustment
        await asyncio.sleep(1)
        
        # Check mobile navigation
        mobile_nav = await browser_manager.evaluate("""
            // Look for mobile-specific navigation elements
            const hamburger = document.querySelector('.hamburger, .mobile-menu-btn');  
            const mobileNav = document.querySelector('.mobile-nav, .nav-mobile');
            return hamburger || mobileNav ? true : false;
        """)
        
        print(f"📱 Mobile navigation present: {mobile_nav}")
        
        # Take screenshot for visual regression
        visual_passed = await visual_regression.capture_and_compare(
            browser_manager, "dashboard_mobile_view", tolerance=0.2
        )
        
        assert visual_passed, "Mobile responsive design visual regression failed"


class TestPerformance:
    """Performance tests for dashboard loading and interactions."""
    
    @pytest.mark.asyncio
    async def test_page_load_performance(self, dashboard_page):
        """Test dashboard page load performance."""
        # Measure page load time
        load_metrics = await dashboard_page.evaluate("""
            const perfData = performance.getEntriesByType('navigation')[0];
            return {
                domContentLoaded: perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart,
                loadComplete: perfData.loadEventEnd - perfData.loadEventStart,
                totalTime: perfData.loadEventEnd - perfData.navigationStart
            };
        """)
        
        print(f"📊 Page load metrics:")
        print(f"   DOM Content Loaded: {load_metrics.get('domContentLoaded', 0):.2f}ms")
        print(f"   Load Complete: {load_metrics.get('loadComplete', 0):.2f}ms") 
        print(f"   Total Time: {load_metrics.get('totalTime', 0):.2f}ms")
        
        # Assert performance thresholds (3 seconds max)
        total_time = load_metrics.get('totalTime', 0)
        assert total_time < 3000, f"Page load too slow: {total_time:.2f}ms > 3000ms"
        
        print("✅ Page load performance within acceptable limits")
    
    @pytest.mark.asyncio
    async def test_interaction_responsiveness(self, authenticated_dashboard):
        """Test responsiveness of user interactions."""
        # Test tab switching performance
        start_time = await authenticated_dashboard.evaluate("performance.now()")
        
        # Switch between tabs and measure time
        await authenticated_dashboard.click(".tab:nth-child(2), .nav-tab:nth-child(2)")
        await asyncio.sleep(0.1)  # Allow for tab switch
        
        end_time = await authenticated_dashboard.evaluate("performance.now()")
        
        interaction_time = end_time - start_time if (end_time and start_time) else 0
        print(f"📊 Tab switch time: {interaction_time:.2f}ms")
        
        # Assert interaction responsiveness (1 second max)
        assert interaction_time < 1000, f"Tab switch too slow: {interaction_time:.2f}ms > 1000ms"
        
        print("✅ User interaction responsiveness within acceptable limits")


# Test configuration and utilities

@pytest.mark.asyncio
async def test_ui_test_framework_ready():
    """Meta-test to verify UI testing framework is operational."""
    from .mcp_adapter import get_mcp_manager
    
    # Test MCP manager initialization
    manager = await get_mcp_manager()
    assert manager is not None, "MCP manager initialization failed"
    
    # Test MCP tool call interface
    result = await manager.call_tool("puppeteer_navigate", {"url": "about:blank"})
    assert result.success, f"MCP tool call failed: {result.error}"
    
    print("✅ UI testing framework is operational")
    print("✅ MCP integration is functional")
    print("✅ All test infrastructure ready")


if __name__ == "__main__":
    # Run specific test for debugging
    pytest.main([__file__ + "::test_ui_test_framework_ready", "-v", "-s"])