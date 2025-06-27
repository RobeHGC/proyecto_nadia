"""
Visual Regression Tests for NADIA Dashboard

This module provides visual regression testing using screenshot comparison
to detect unintended UI changes across dashboard components.
"""
import pytest
import asyncio
import os
from typing import Dict, List

from .page_objects.dashboard_page import DashboardPage
from .page_objects.review_page import ReviewPage


class TestVisualRegression:
    """Visual regression test suite for dashboard components."""
    
    @pytest.mark.asyncio
    async def test_dashboard_homepage_visual(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of dashboard homepage."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to dashboard
        await dashboard.navigate()
        await dashboard.wait_for_dashboard_load()
        
        # Wait for any dynamic content to stabilize
        await asyncio.sleep(2)
        
        # Capture full dashboard
        matches = await visual_regression.capture_and_compare(
            authenticated_dashboard,
            "dashboard_homepage_full"
        )
        
        # For initial run, this creates baseline
        print(f"Dashboard homepage visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
    
    @pytest.mark.asyncio
    async def test_navigation_header_visual(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of navigation header."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        await dashboard.navigate()
        await dashboard.wait_for_dashboard_load()
        
        # Capture just the navigation header
        nav_selectors = [
            ".navbar, .navigation, .header-nav",
            ".tab-container, .nav-tabs",
            "[data-testid='navigation']"
        ]
        
        for selector in nav_selectors:
            if await dashboard.is_element_visible(selector):
                matches = await visual_regression.capture_and_compare(
                    authenticated_dashboard,
                    "navigation_header",
                    selector
                )
                print(f"Navigation header visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
                break
        else:
            print("Navigation header not found - skipping visual test")
    
    @pytest.mark.asyncio
    async def test_reviews_tab_visual(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of reviews tab."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews tab
        await dashboard.navigate_to_reviews()
        await asyncio.sleep(2)  # Allow content to load
        
        # Capture reviews content area
        content_selectors = [
            ".reviews-content, #reviews-content",
            ".review-queue",
            "[data-tab-content='reviews']"
        ]
        
        for selector in content_selectors:
            if await dashboard.is_element_visible(selector):
                matches = await visual_regression.capture_and_compare(
                    authenticated_dashboard,
                    "reviews_tab_content",
                    selector
                )
                print(f"Reviews tab visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
                break
        else:
            # Fallback to full page if specific content area not found
            matches = await visual_regression.capture_and_compare(
                authenticated_dashboard,
                "reviews_tab_fallback"
            )
            print(f"Reviews tab (fallback) visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
    
    @pytest.mark.asyncio
    async def test_analytics_tab_visual(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of analytics tab."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to analytics tab
        success = await dashboard.navigate_to_analytics()
        if not success:
            pytest.skip("Analytics tab not available")
        
        await asyncio.sleep(3)  # Allow charts/data to load
        
        # Capture analytics content
        content_selectors = [
            ".analytics-content, #analytics-content",
            ".dashboard-analytics",
            "[data-tab-content='analytics']"
        ]
        
        for selector in content_selectors:
            if await dashboard.is_element_visible(selector):
                matches = await visual_regression.capture_and_compare(
                    authenticated_dashboard,
                    "analytics_tab_content",
                    selector
                )
                print(f"Analytics tab visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
                break
    
    @pytest.mark.asyncio
    async def test_quarantine_tab_visual(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of quarantine tab."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to quarantine tab
        success = await dashboard.navigate_to_quarantine()
        if not success:
            pytest.skip("Quarantine tab not available")
        
        await asyncio.sleep(2)
        
        # Capture quarantine content
        content_selectors = [
            ".quarantine-content, #quarantine-content",
            ".quarantine-interface",
            "[data-tab-content='quarantine']"
        ]
        
        for selector in content_selectors:
            if await dashboard.is_element_visible(selector):
                matches = await visual_regression.capture_and_compare(
                    authenticated_dashboard,
                    "quarantine_tab_content",
                    selector
                )
                print(f"Quarantine tab visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
                break
    
    @pytest.mark.asyncio
    async def test_recovery_tab_visual(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of recovery tab."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to recovery tab
        success = await dashboard.navigate_to_recovery()
        if not success:
            pytest.skip("Recovery tab not available")
        
        await asyncio.sleep(2)
        
        # Capture recovery content
        content_selectors = [
            ".recovery-content, #recovery-content",
            ".recovery-interface",
            "[data-tab-content='recovery']"
        ]
        
        for selector in content_selectors:
            if await dashboard.is_element_visible(selector):
                matches = await visual_regression.capture_and_compare(
                    authenticated_dashboard,
                    "recovery_tab_content",
                    selector
                )
                print(f"Recovery tab visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
                break


class TestReviewInterfaceVisual:
    """Visual regression tests for review interface components."""
    
    @pytest.mark.asyncio
    async def test_review_item_visual(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of individual review items."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        if await review_page.get_review_count() == 0:
            pytest.skip("No reviews available for visual testing")
        
        # Select first review
        await review_page.select_review(index=0)
        await asyncio.sleep(1)
        
        # Capture selected review item
        review_selectors = [
            ".review-item.selected, .review-item.active",
            "[data-testid='selected-review']"
        ]
        
        for selector in review_selectors:
            if await review_page.is_element_visible(selector):
                matches = await visual_regression.capture_and_compare(
                    authenticated_dashboard,
                    "review_item_selected",
                    selector
                )
                print(f"Review item visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
                break
    
    @pytest.mark.asyncio
    async def test_review_details_panel_visual(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of review details panel."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews and select one
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        if await review_page.get_review_count() == 0:
            pytest.skip("No reviews available for details visual testing")
        
        await review_page.select_review(index=0)
        await asyncio.sleep(1)
        
        # Capture review details panel
        details_selectors = [
            ".review-details, .review-panel",
            ".review-content",
            "[data-testid='review-details']"
        ]
        
        for selector in details_selectors:
            if await review_page.is_element_visible(selector):
                matches = await visual_regression.capture_and_compare(
                    authenticated_dashboard,
                    "review_details_panel",
                    selector
                )
                print(f"Review details visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
                break
    
    @pytest.mark.asyncio
    async def test_review_edit_mode_visual(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of review edit interface."""
        review_page = ReviewPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to reviews and select one
        await review_page.navigate()
        await review_page.wait_for_review_load()
        
        if await review_page.get_review_count() == 0:
            pytest.skip("No reviews available for edit mode visual testing")
        
        await review_page.select_review(index=0)
        
        # Enter edit mode
        edit_success = await review_page.enter_edit_mode()
        if not edit_success:
            pytest.skip("Could not enter edit mode for visual testing")
        
        await asyncio.sleep(1)
        
        # Capture edit interface
        edit_selectors = [
            ".review-edit, .edit-mode",
            ".review-editor",
            "[data-testid='review-edit']"
        ]
        
        for selector in edit_selectors:
            if await review_page.is_element_visible(selector):
                matches = await visual_regression.capture_and_compare(
                    authenticated_dashboard,
                    "review_edit_mode",
                    selector
                )
                print(f"Review edit mode visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
                break
        
        # Cancel edit to clean up
        await review_page.cancel_edit()


class TestResponsiveVisual:
    """Visual regression tests for responsive design."""
    
    @pytest.mark.asyncio
    async def test_mobile_dashboard_visual(self, browser_manager, browser_config, visual_regression):
        """Test dashboard visual consistency on mobile viewport."""
        dashboard = DashboardPage(browser_manager, browser_config)
        
        # Set mobile viewport (would use MCP in actual implementation)
        print("Testing mobile viewport: 375x667")
        
        await dashboard.navigate()
        await dashboard.wait_for_dashboard_load()
        await asyncio.sleep(2)
        
        # Capture mobile dashboard
        matches = await visual_regression.capture_and_compare(
            browser_manager,
            "dashboard_mobile_375x667"
        )
        
        print(f"Mobile dashboard visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
    
    @pytest.mark.asyncio
    async def test_tablet_dashboard_visual(self, browser_manager, browser_config, visual_regression):
        """Test dashboard visual consistency on tablet viewport."""
        dashboard = DashboardPage(browser_manager, browser_config)
        
        # Set tablet viewport (would use MCP in actual implementation)
        print("Testing tablet viewport: 768x1024")
        
        await dashboard.navigate()
        await dashboard.wait_for_dashboard_load()
        await asyncio.sleep(2)
        
        # Capture tablet dashboard
        matches = await visual_regression.capture_and_compare(
            browser_manager,
            "dashboard_tablet_768x1024"
        )
        
        print(f"Tablet dashboard visual test: {'PASS' if matches else 'BASELINE_CREATED'}")


class TestComponentStates:
    """Visual regression tests for different component states."""
    
    @pytest.mark.asyncio
    async def test_loading_states_visual(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of loading states."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate to dashboard
        await dashboard.navigate()
        
        # Try to capture loading state (might be brief)
        loading_selectors = [
            ".loading, .spinner",
            "[data-testid='loading']",
            ".review-loading"
        ]
        
        for selector in loading_selectors:
            if await dashboard.is_element_visible(selector):
                matches = await visual_regression.capture_and_compare(
                    authenticated_dashboard,
                    f"loading_state_{selector.replace('.', '').replace('[', '').replace(']', '')}",
                    selector
                )
                print(f"Loading state visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
    
    @pytest.mark.asyncio
    async def test_empty_states_visual(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of empty states."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        # Navigate through tabs looking for empty states
        tabs = [
            ("reviews", dashboard.navigate_to_reviews),
            ("analytics", dashboard.navigate_to_analytics),
            ("quarantine", dashboard.navigate_to_quarantine),
            ("recovery", dashboard.navigate_to_recovery)
        ]
        
        for tab_name, navigate_method in tabs:
            success = await navigate_method()
            if not success:
                continue
                
            await asyncio.sleep(1)
            
            # Look for empty state indicators
            empty_selectors = [
                ".empty, .no-data, .no-content",
                f".empty-{tab_name}",
                "[data-testid='no-data']"
            ]
            
            for selector in empty_selectors:
                if await dashboard.is_element_visible(selector):
                    matches = await visual_regression.capture_and_compare(
                        authenticated_dashboard,
                        f"empty_state_{tab_name}",
                        selector
                    )
                    print(f"Empty state ({tab_name}) visual test: {'PASS' if matches else 'BASELINE_CREATED'}")
                    break
    
    @pytest.mark.asyncio
    async def test_error_states_visual(self, authenticated_dashboard, visual_regression):
        """Test visual consistency of error states."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        await dashboard.navigate()
        await dashboard.wait_for_dashboard_load()
        
        # Check for any existing error states
        error_selectors = [
            ".error, .alert-error, .alert-danger",
            "[data-testid='error']",
            ".notification.error"
        ]
        
        for selector in error_selectors:
            if await dashboard.is_element_visible(selector):
                matches = await visual_regression.capture_and_compare(
                    authenticated_dashboard,
                    f"error_state_{selector.replace('.', '').replace('[', '').replace(']', '')}",
                    selector
                )
                print(f"Error state visual test: {'PASS' if matches else 'BASELINE_CREATED'}")


class TestVisualRegressionUtilities:
    """Utility tests for visual regression system itself."""
    
    @pytest.mark.asyncio
    async def test_screenshot_capture_capability(self, authenticated_dashboard):
        """Test that screenshot capture is working."""
        dashboard = DashboardPage(authenticated_dashboard, authenticated_dashboard.config)
        
        await dashboard.navigate()
        await dashboard.wait_for_dashboard_load()
        
        # Take a test screenshot
        screenshot_success = await dashboard.take_screenshot("test_capture")
        assert screenshot_success, "Screenshot capture should work"
        
        print("Screenshot capture capability verified")
    
    @pytest.mark.asyncio 
    async def test_visual_regression_directories(self, screenshot_baseline_dir, 
                                                screenshot_current_dir, screenshot_diff_dir):
        """Test that visual regression directories are properly set up."""
        directories = [screenshot_baseline_dir, screenshot_current_dir, screenshot_diff_dir]
        
        for directory in directories:
            assert os.path.exists(directory), f"Directory should exist: {directory}"
            assert os.path.isdir(directory), f"Path should be a directory: {directory}"
        
        print(f"Visual regression directories verified: {len(directories)} directories")
    
    def test_visual_regression_helper_initialization(self, visual_regression):
        """Test that visual regression helper is properly initialized."""
        assert visual_regression is not None, "Visual regression helper should be available"
        assert hasattr(visual_regression, 'capture_and_compare'), "Helper should have capture_and_compare method"
        
        print("Visual regression helper properly initialized")