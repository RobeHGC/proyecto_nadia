"""
Basic screenshot functionality test for UI testing framework validation.
"""
import pytest
import os


@pytest.mark.asyncio
async def test_screenshot_functionality(browser_manager, browser_config, visual_regression):
    """Test that screenshot functionality works correctly."""
    # Navigate to dashboard (this should work with our mock implementation)
    navigation_success = await browser_manager.navigate(browser_config.dashboard_url)
    
    print(f"Navigation result: {navigation_success}")
    
    # Take a screenshot
    screenshot_success = await browser_manager.screenshot("test_basic_functionality")
    
    print(f"Screenshot result: {screenshot_success}")
    
    # Check that screenshot file was created
    screenshot_path = "tests/ui/screenshots/current/test_basic_functionality.png"
    screenshot_exists = os.path.exists(screenshot_path)
    
    print(f"Screenshot file exists: {screenshot_exists}")
    print(f"Screenshot path: {screenshot_path}")
    
    # Test visual regression comparison (should create baseline if none exists)
    visual_result = await visual_regression.capture_and_compare(
        browser_manager, "test_framework_validation", tolerance=0.1
    )
    
    print(f"Visual regression result: {visual_result}")
    
    # Assertions
    assert navigation_success, "Navigation to dashboard failed"
    assert screenshot_success, "Screenshot capture failed"
    assert screenshot_exists, f"Screenshot file not created at {screenshot_path}"
    assert visual_result, "Visual regression test failed"
    
    print("✅ All screenshot functionality tests passed")


@pytest.mark.asyncio
async def test_mcp_adapter_direct(browser_manager):
    """Test MCP adapter directly without fixtures."""
    from tests.ui.mcp_adapter import get_mcp_manager
    
    # Get MCP manager
    manager = await get_mcp_manager()
    
    # Test navigation
    nav_result = await manager.call_tool("puppeteer_navigate", {
        "url": "http://localhost:8000"
    })
    
    print(f"Direct navigation result: {nav_result.success}")
    print(f"Navigation data: {nav_result.data}")
    
    # Test screenshot
    screenshot_result = await manager.call_tool("puppeteer_screenshot", {
        "name": "direct_test_screenshot"
    })
    
    print(f"Direct screenshot result: {screenshot_result.success}")
    print(f"Screenshot data: {screenshot_result.data}")
    
    # Test click
    click_result = await manager.call_tool("puppeteer_click", {
        "selector": "body"
    })
    
    print(f"Direct click result: {click_result.success}")
    print(f"Click data: {click_result.data}")
    
    # Assertions
    assert nav_result.success, f"Direct navigation failed: {nav_result.error}"
    assert screenshot_result.success, f"Direct screenshot failed: {screenshot_result.error}"
    assert click_result.success, f"Direct click failed: {click_result.error}"
    
    print("✅ Direct MCP adapter tests passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])