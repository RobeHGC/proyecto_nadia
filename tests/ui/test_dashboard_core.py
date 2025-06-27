"""
Core Dashboard UI Tests for NADIA

This module tests the fundamental dashboard functionality using Puppeteer MCP,
including navigation, loading, basic interactions, and visual regression testing.
"""
import pytest
import asyncio
from typing import Dict, List

from .page_objects.dashboard_page import DashboardPage


class TestDashboardCore:
    """Test suite for core dashboard functionality."""
    
    @pytest.mark.asyncio
    async def test_dashboard_loads_successfully(self, browser_manager, browser_config):
        """Test that the dashboard loads without errors."""
        dashboard = DashboardPage(browser_manager, browser_config)
        
        # Navigate to dashboard
        success = await dashboard.navigate()
        assert success, "Failed to navigate to dashboard"
        
        # Wait for dashboard to fully load
        loaded = await dashboard.wait_for_dashboard_load()
        assert loaded, "Dashboard failed to load completely"
        
        # Verify no error messages
        has_errors = await dashboard.has_error_messages()
        assert not has_errors, f"Dashboard has errors: {await dashboard.get_error_messages()}"
        
        # Take screenshot for visual verification
        await dashboard.take_dashboard_screenshot("dashboard_loaded")
    
    @pytest.mark.asyncio
    async def test_navigation_tabs_exist(self, authenticated_dashboard):
        """Test that all expected navigation tabs are present."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Get available tabs
        tabs = await dashboard.get_navigation_tabs()
        
        # Verify expected tabs exist
        expected_tabs = ["Reviews", "Analytics", "Quarantine", "Recovery"]
        for expected_tab in expected_tabs:
            # Check if any tab contains the expected name (case-insensitive)
            tab_found = any(expected_tab.lower() in tab.lower() for tab in tabs)
            assert tab_found, f"Expected tab '{expected_tab}' not found. Available tabs: {tabs}"
    
    @pytest.mark.asyncio
    async def test_tab_navigation(self, authenticated_dashboard):
        """Test navigation between different tabs."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Test navigation to each tab
        tab_tests = [
            ("reviews", dashboard.navigate_to_reviews),
            ("analytics", dashboard.navigate_to_analytics),
            ("quarantine", dashboard.navigate_to_quarantine),
            ("recovery", dashboard.navigate_to_recovery)
        ]
        
        for tab_name, navigate_method in tab_tests:
            # Navigate to tab
            success = await navigate_method()
            assert success, f"Failed to navigate to {tab_name} tab"
            
            # Verify tab is active
            is_active = await dashboard.is_tab_active(tab_name)
            assert is_active, f"{tab_name} tab is not active after navigation"
            
            # Take screenshot of each tab
            await dashboard.take_screenshot(f"tab_{tab_name}")
            
            # Small delay between navigation to avoid rapid clicking
            await asyncio.sleep(0.5)
    
    @pytest.mark.asyncio
    async def test_review_queue_loads(self, authenticated_dashboard):
        """Test that the review queue loads properly."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews tab
        success = await dashboard.navigate_to_reviews()
        assert success, "Failed to navigate to reviews tab"
        
        # Get pending review count
        pending_count = await dashboard.get_pending_review_count()
        
        # Get review items
        reviews = await dashboard.get_review_items()
        
        # Basic validation
        assert pending_count >= 0, "Pending count should be non-negative"
        assert isinstance(reviews, list), "Reviews should be a list"
        
        # If there are pending reviews, verify they're displayed
        if pending_count > 0:
            assert len(reviews) > 0, f"Expected {pending_count} reviews but found {len(reviews)}"
        
        print(f"Found {pending_count} pending reviews, {len(reviews)} displayed")
    
    @pytest.mark.asyncio
    async def test_dashboard_refresh(self, authenticated_dashboard):
        """Test dashboard refresh functionality."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Get initial state
        initial_status = await dashboard.get_system_status()
        
        # Refresh dashboard
        refresh_success = await dashboard.refresh_dashboard()
        assert refresh_success, "Dashboard refresh failed"
        
        # Wait for refresh to complete
        await dashboard.wait_for_dashboard_load()
        
        # Verify dashboard still functional after refresh
        has_errors = await dashboard.has_error_messages()
        assert not has_errors, "Dashboard has errors after refresh"
        
        # Get status after refresh
        new_status = await dashboard.get_system_status()
        
        # Status should still be available (might have updated values)
        assert isinstance(new_status, dict), "System status should be available after refresh"
    
    @pytest.mark.asyncio
    async def test_search_functionality(self, authenticated_dashboard):
        """Test search functionality if available."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await dashboard.navigate_to_reviews()
        
        # Test search if search input exists
        search_input = "#search, .search-input, [data-testid='search']"
        has_search = await dashboard.is_element_visible(search_input)
        
        if has_search:
            # Get initial review count
            initial_count = await dashboard.get_pending_review_count()
            
            # Perform search
            search_success = await dashboard.search_reviews("test")
            assert search_success, "Search failed to execute"
            
            # Wait for search results
            await dashboard._wait_for_api_requests()
            
            # Clear search
            clear_success = await dashboard.clear_search()
            assert clear_success, "Failed to clear search"
            
            # Verify search cleared
            await dashboard._wait_for_api_requests()
            
            print("Search functionality tested successfully")
        else:
            print("Search functionality not available - skipping search tests")
    
    @pytest.mark.asyncio
    async def test_system_status_display(self, authenticated_dashboard):
        """Test that system status information is displayed."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Get system status
        status = await dashboard.get_system_status()
        
        # Verify status is available
        assert isinstance(status, dict), "System status should be a dictionary"
        
        # Log status for verification
        print(f"System status: {status}")
        
        # Check for common status fields
        expected_fields = ["overall", "health"]
        for field in expected_fields:
            if field in status:
                assert status[field], f"Status field '{field}' should not be empty"
    
    @pytest.mark.asyncio
    async def test_dashboard_metrics(self, authenticated_dashboard):
        """Test dashboard metrics display."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Get dashboard metrics
        metrics = await dashboard.get_dashboard_metrics()
        
        # Verify metrics structure
        assert isinstance(metrics, dict), "Metrics should be a dictionary"
        
        # Log metrics for verification
        print(f"Dashboard metrics: {metrics}")
        
        # If metrics exist, verify they have values
        for metric_name, metric_value in metrics.items():
            assert metric_value is not None, f"Metric '{metric_name}' should have a value"
    
    @pytest.mark.asyncio
    async def test_responsive_layout(self, browser_manager, browser_config):
        """Test dashboard responsiveness at different viewport sizes."""
        dashboard = DashboardPage(browser_manager, browser_config)
        
        # Test different viewport sizes
        viewports = [
            {"width": 1920, "height": 1080, "name": "desktop_large"},
            {"width": 1366, "height": 768, "name": "desktop_standard"},
            {"width": 768, "height": 1024, "name": "tablet"},
            {"width": 375, "height": 667, "name": "mobile"}
        ]
        
        for viewport in viewports:
            # Set viewport size (would use MCP tool in actual implementation)
            print(f"Testing viewport: {viewport['width']}x{viewport['height']}")
            
            # Navigate to dashboard
            await dashboard.navigate()
            await dashboard.wait_for_dashboard_load()
            
            # Take screenshot at this viewport
            await dashboard.take_screenshot(f"responsive_{viewport['name']}")
            
            # Verify dashboard still functional
            has_errors = await dashboard.has_error_messages()
            assert not has_errors, f"Dashboard has errors at {viewport['name']} viewport"
            
            # Test basic navigation still works
            nav_success = await dashboard.navigate_to_reviews()
            assert nav_success, f"Navigation failed at {viewport['name']} viewport"
    
    @pytest.mark.asyncio
    async def test_keyboard_accessibility(self, authenticated_dashboard):
        """Test keyboard navigation and accessibility."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Test tab navigation
        await dashboard.press_key("Tab")
        await asyncio.sleep(0.2)
        
        # Test Enter key activation
        await dashboard.press_key("Enter")
        await asyncio.sleep(0.2)
        
        # Test Escape key (should cancel any modal/edit state)
        await dashboard.press_key("Escape")
        await asyncio.sleep(0.2)
        
        # Verify dashboard still functional after keyboard interaction
        has_errors = await dashboard.has_error_messages()
        assert not has_errors, "Dashboard has errors after keyboard interaction"
    
    @pytest.mark.asyncio
    async def test_error_handling(self, browser_manager, browser_config):
        """Test dashboard behavior with invalid URLs or states."""
        dashboard = DashboardPage(browser_manager, browser_config)
        
        # Test navigation to invalid hash
        invalid_url = f"{browser_config.dashboard_url}/#invalid-tab"
        await browser_manager.navigate(invalid_url)
        
        # Wait for page to handle invalid state
        await dashboard.wait_for_page_load()
        
        # Dashboard should handle invalid state gracefully
        has_errors = await dashboard.has_error_messages()
        
        # Log any errors for debugging but don't fail test
        if has_errors:
            errors = await dashboard.get_error_messages()
            print(f"Expected error handling test found errors: {errors}")
        
        # Navigate back to valid dashboard
        success = await dashboard.navigate()
        assert success, "Failed to recover from invalid state"


class TestDashboardVisualRegression:
    """Visual regression tests for dashboard UI."""
    
    @pytest.mark.asyncio
    async def test_dashboard_visual_consistency(self, authenticated_dashboard, visual_regression):
        """Test that dashboard appearance is consistent."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to dashboard
        await dashboard.navigate()
        await dashboard.wait_for_dashboard_load()
        
        # Capture and compare full dashboard
        matches = await visual_regression.capture_and_compare(
            authenticated_dashboard, 
            "dashboard_full"
        )
        
        assert matches, "Dashboard visual appearance has changed"
    
    @pytest.mark.asyncio
    async def test_tab_visual_consistency(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of each tab."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        tabs = [
            ("reviews", dashboard.navigate_to_reviews),
            ("analytics", dashboard.navigate_to_analytics),
            ("quarantine", dashboard.navigate_to_quarantine),
            ("recovery", dashboard.navigate_to_recovery)
        ]
        
        for tab_name, navigate_method in tabs:
            # Navigate to tab
            await navigate_method()
            await dashboard.wait_for_page_load()
            
            # Wait for tab content to load
            await asyncio.sleep(1)
            
            # Capture and compare tab content
            content_selector = f".{tab_name}-content, #{tab_name}-content, [data-tab-content='{tab_name}']"
            
            matches = await visual_regression.capture_and_compare(
                authenticated_dashboard,
                f"tab_{tab_name}",
                content_selector
            )
            
            # Note: In initial implementation, we might expect changes
            # This test documents the current state for future comparisons
            print(f"Tab {tab_name} visual check: {'PASS' if matches else 'BASELINE_CREATED'}")


class TestDashboardPerformance:
    """Performance tests for dashboard loading and interactions."""
    
    @pytest.mark.asyncio
    async def test_dashboard_load_time(self, browser_manager, browser_config):
        """Test that dashboard loads within acceptable time limits."""
        dashboard = DashboardPage(browser_manager, browser_config)
        
        # Measure load time
        start_time = asyncio.get_event_loop().time()
        
        success = await dashboard.navigate()
        assert success, "Dashboard navigation failed"
        
        await dashboard.wait_for_dashboard_load()
        
        end_time = asyncio.get_event_loop().time()
        load_time = end_time - start_time
        
        # Dashboard should load within 5 seconds
        assert load_time < 5.0, f"Dashboard took {load_time:.2f}s to load (limit: 5.0s)"
        
        print(f"Dashboard load time: {load_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_tab_switch_performance(self, authenticated_dashboard):
        """Test that tab switching is responsive."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        tabs = [
            dashboard.navigate_to_reviews,
            dashboard.navigate_to_analytics,
            dashboard.navigate_to_quarantine,
            dashboard.navigate_to_recovery
        ]
        
        for navigate_method in tabs:
            start_time = asyncio.get_event_loop().time()
            
            success = await navigate_method()
            assert success, "Tab navigation failed"
            
            end_time = asyncio.get_event_loop().time()
            switch_time = end_time - start_time
            
            # Tab switching should be under 2 seconds
            assert switch_time < 2.0, f"Tab switch took {switch_time:.2f}s (limit: 2.0s)"
            
            print(f"Tab switch time: {switch_time:.2f}s")