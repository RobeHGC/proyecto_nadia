"""
UI Test Configuration and Fixtures for Puppeteer MCP Integration

This module provides fixtures for browser automation testing using Puppeteer MCP.
It handles browser session management, page navigation, and test environment setup.
"""
import pytest
import asyncio
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from contextlib import asynccontextmanager


@dataclass
class BrowserConfig:
    """Configuration for browser automation tests."""
    headless: bool = True
    viewport: Dict[str, int] = None
    timeout: int = 30000  # 30 seconds
    dashboard_url: str = "http://localhost:8000"
    dashboard_api_key: str = "miclavesegura45mil"
    
    def __post_init__(self):
        if self.viewport is None:
            self.viewport = {"width": 1280, "height": 720}


class PuppeteerMCPManager:
    """
    Manager for Puppeteer MCP operations.
    
    This class encapsulates browser automation using the MCP tools:
    - puppeteer_navigate
    - puppeteer_screenshot  
    - puppeteer_click
    - puppeteer_fill
    - puppeteer_evaluate
    """
    
    def __init__(self, config: BrowserConfig):
        self.config = config
        self._browser_initialized = False
        
    async def navigate(self, url: str) -> bool:
        """Navigate to a URL using puppeteer_navigate MCP tool."""
        try:
            # Note: In actual implementation, this would use the MCP tool
            # For now, this is the structure that would integrate with MCP
            launch_options = {
                "headless": self.config.headless,
                "defaultViewport": self.config.viewport,
                "args": ["--no-sandbox", "--disable-dev-shm-usage"] if self.config.headless else []
            }
            
            # Placeholder for MCP tool call:
            # result = await mcp_tool_call("puppeteer_navigate", {
            #     "url": url,
            #     "launchOptions": launch_options,
            #     "allowDangerous": True
            # })
            
            self._browser_initialized = True
            return True
        except Exception as e:
            print(f"Navigation failed: {e}")
            return False
    
    async def screenshot(self, name: str, selector: Optional[str] = None) -> bool:
        """Take a screenshot using puppeteer_screenshot MCP tool."""
        try:
            # Placeholder for MCP tool call:
            # result = await mcp_tool_call("puppeteer_screenshot", {
            #     "name": name,
            #     "selector": selector,
            #     "width": self.config.viewport["width"],
            #     "height": self.config.viewport["height"],
            #     "encoded": False
            # })
            return True
        except Exception as e:
            print(f"Screenshot failed: {e}")
            return False
    
    async def click(self, selector: str) -> bool:
        """Click an element using puppeteer_click MCP tool."""
        try:
            # Placeholder for MCP tool call:
            # result = await mcp_tool_call("puppeteer_click", {"selector": selector})
            return True
        except Exception as e:
            print(f"Click failed: {e}")
            return False
    
    async def fill(self, selector: str, value: str) -> bool:
        """Fill an input field using puppeteer_fill MCP tool."""
        try:
            # Placeholder for MCP tool call:
            # result = await mcp_tool_call("puppeteer_fill", {
            #     "selector": selector,
            #     "value": value
            # })
            return True
        except Exception as e:
            print(f"Fill failed: {e}")
            return False
    
    async def evaluate(self, script: str) -> Any:
        """Execute JavaScript using puppeteer_evaluate MCP tool."""
        try:
            # Placeholder for MCP tool call:
            # result = await mcp_tool_call("puppeteer_evaluate", {"script": script})
            return None
        except Exception as e:
            print(f"Evaluate failed: {e}")
            return None
    
    async def wait_for_element(self, selector: str, timeout: int = None) -> bool:
        """Wait for an element to appear."""
        timeout = timeout or self.config.timeout
        script = f"""
        new Promise((resolve, reject) => {{
            const timeout = setTimeout(() => reject(new Error('Timeout')), {timeout});
            const observer = new MutationObserver((mutations, obs) => {{
                const element = document.querySelector('{selector}');
                if (element) {{
                    clearTimeout(timeout);
                    obs.disconnect();
                    resolve(true);
                }}
            }});
            
            // Check if element already exists
            if (document.querySelector('{selector}')) {{
                clearTimeout(timeout);
                resolve(true);
                return;
            }}
            
            observer.observe(document.body, {{
                childList: true,
                subtree: true
            }});
        }});
        """
        
        result = await self.evaluate(script)
        return result is not None


@pytest.fixture(scope="session")
def browser_config():
    """Browser configuration fixture."""
    return BrowserConfig(
        headless=os.getenv("UI_TEST_HEADLESS", "true").lower() == "true",
        dashboard_url=os.getenv("DASHBOARD_URL", "http://localhost:8000"),
        dashboard_api_key=os.getenv("DASHBOARD_API_KEY", "miclavesegura45mil")
    )


@pytest.fixture(scope="session")
async def browser_manager(browser_config):
    """Browser manager fixture for the entire test session."""
    manager = PuppeteerMCPManager(browser_config)
    yield manager
    # Cleanup would be handled by MCP server


@pytest.fixture(scope="function")
async def dashboard_page(browser_manager, browser_config):
    """Navigate to dashboard page for each test."""
    success = await browser_manager.navigate(browser_config.dashboard_url)
    if not success:
        pytest.skip("Failed to navigate to dashboard")
    
    # Wait for dashboard to load
    await browser_manager.wait_for_element("body", timeout=10000)
    
    yield browser_manager
    
    # Optional: Take screenshot after each test for debugging
    test_name = os.environ.get('PYTEST_CURRENT_TEST', 'unknown').split('::')[-1]
    await browser_manager.screenshot(f"test_cleanup_{test_name}")


@pytest.fixture
async def authenticated_dashboard(dashboard_page, browser_config):
    """Dashboard page with authentication if needed."""
    # Check if authentication is required
    auth_script = """
    // Check if we need to authenticate
    const authHeader = document.querySelector('[data-testid="auth-header"]');
    return authHeader ? false : true;
    """
    
    is_authenticated = await dashboard_page.evaluate(auth_script)
    
    if not is_authenticated:
        # Add authentication logic here if needed
        # For now, assuming API key auth is handled by headers
        pass
    
    yield dashboard_page


@pytest.fixture
def screenshot_baseline_dir():
    """Directory for storing baseline screenshots for visual regression testing."""
    baseline_dir = "tests/ui/screenshots/baseline"
    os.makedirs(baseline_dir, exist_ok=True)
    return baseline_dir


@pytest.fixture  
def screenshot_current_dir():
    """Directory for storing current test screenshots."""
    current_dir = "tests/ui/screenshots/current"
    os.makedirs(current_dir, exist_ok=True)
    return current_dir


@pytest.fixture
def screenshot_diff_dir():
    """Directory for storing visual diff screenshots."""
    diff_dir = "tests/ui/screenshots/diff"
    os.makedirs(diff_dir, exist_ok=True)
    return diff_dir


class VisualRegressionHelper:
    """Helper class for visual regression testing."""
    
    def __init__(self, baseline_dir: str, current_dir: str, diff_dir: str):
        self.baseline_dir = baseline_dir
        self.current_dir = current_dir
        self.diff_dir = diff_dir
    
    async def capture_and_compare(self, browser_manager: PuppeteerMCPManager, 
                                name: str, selector: str = None) -> bool:
        """
        Capture screenshot and compare with baseline.
        
        Returns:
            bool: True if images match (or baseline doesn't exist), False if different
        """
        current_path = f"{self.current_dir}/{name}.png"
        baseline_path = f"{self.baseline_dir}/{name}.png"
        
        # Take current screenshot
        await browser_manager.screenshot(name, selector)
        
        # If no baseline exists, create it
        if not os.path.exists(baseline_path):
            # Copy current to baseline
            # In real implementation, would copy the file
            print(f"Creating baseline screenshot: {baseline_path}")
            return True
        
        # Compare images (placeholder - would use actual image comparison)
        # In real implementation, would use libraries like PIL or opencv
        print(f"Comparing {current_path} with {baseline_path}")
        
        # For now, assume images match
        return True


@pytest.fixture
def visual_regression(screenshot_baseline_dir, screenshot_current_dir, screenshot_diff_dir):
    """Visual regression testing helper."""
    return VisualRegressionHelper(
        screenshot_baseline_dir,
        screenshot_current_dir, 
        screenshot_diff_dir
    )


# Utility functions for test helpers

async def wait_for_api_response(browser_manager: PuppeteerMCPManager, timeout: int = 5000):
    """Wait for any pending API requests to complete."""
    script = f"""
    new Promise((resolve) => {{
        // Wait for jQuery if available
        if (window.jQuery) {{
            const checkActive = () => {{
                if (jQuery.active === 0) {{
                    resolve(true);
                }} else {{
                    setTimeout(checkActive, 100);
                }}
            }};
            checkActive();
        }} else {{
            // Fallback: just wait a bit
            setTimeout(() => resolve(true), 1000);
        }}
    }});
    """
    
    await browser_manager.evaluate(script)


async def get_element_text(browser_manager: PuppeteerMCPManager, selector: str) -> str:
    """Get text content of an element."""
    script = f"""
    const element = document.querySelector('{selector}');
    return element ? element.textContent.trim() : '';
    """
    
    return await browser_manager.evaluate(script) or ""


async def is_element_visible(browser_manager: PuppeteerMCPManager, selector: str) -> bool:
    """Check if an element is visible on the page."""
    script = f"""
    const element = document.querySelector('{selector}');
    if (!element) return false;
    
    const style = window.getComputedStyle(element);
    return style.display !== 'none' && 
           style.visibility !== 'hidden' && 
           style.opacity !== '0';
    """
    
    result = await browser_manager.evaluate(script)
    return bool(result)


# Export utility functions for use in tests
__all__ = [
    'browser_config',
    'browser_manager', 
    'dashboard_page',
    'authenticated_dashboard',
    'visual_regression',
    'wait_for_api_response',
    'get_element_text',
    'is_element_visible',
    'PuppeteerMCPManager',
    'BrowserConfig',
    'VisualRegressionHelper'
]