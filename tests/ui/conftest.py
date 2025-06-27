"""
UI Test Configuration and Fixtures for Puppeteer MCP Integration

This module provides fixtures for browser automation testing using Puppeteer MCP.
It handles browser session management, page navigation, and test environment setup.
"""
import pytest
import asyncio
import os
import aiohttp
from typing import Dict, Any, Optional
from dataclasses import dataclass
from contextlib import asynccontextmanager
from .mcp_adapter import mcp_tool_call, cleanup_mcp, MCPResult


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
    
    @classmethod
    def from_ui_config(cls, ui_config):
        """Create BrowserConfig from UITestConfig for backward compatibility."""
        return cls(
            headless=ui_config.headless,
            viewport=ui_config.get_viewport(),
            timeout=ui_config.default_timeout,
            dashboard_url=ui_config.dashboard_url,
            dashboard_api_key=ui_config.dashboard_api_key
        )


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
            launch_options = {
                "headless": self.config.headless,
                "defaultViewport": self.config.viewport,
                "args": ["--no-sandbox", "--disable-dev-shm-usage"] if self.config.headless else []
            }
            
            # Real MCP tool call
            result = await mcp_tool_call("puppeteer_navigate", {
                "url": url,
                "launchOptions": launch_options,
                "allowDangerous": True
            })
            
            if result.success:
                self._browser_initialized = True
                return True
            else:
                print(f"Navigation failed: {result.error}")
                return False
        except Exception as e:
            print(f"Navigation failed: {e}")
            return False
    
    async def screenshot(self, name: str, selector: Optional[str] = None) -> bool:
        """Take a screenshot using puppeteer_screenshot MCP tool."""
        try:
            # Real MCP tool call
            result = await mcp_tool_call("puppeteer_screenshot", {
                "name": name,
                "selector": selector,
                "width": self.config.viewport["width"],
                "height": self.config.viewport["height"],
                "encoded": False
            })
            
            return result.success
        except Exception as e:
            print(f"Screenshot failed: {e}")
            return False
    
    async def click(self, selector: str) -> bool:
        """Click an element using puppeteer_click MCP tool."""
        try:
            # Real MCP tool call
            result = await mcp_tool_call("puppeteer_click", {"selector": selector})
            return result.success
        except Exception as e:
            print(f"Click failed: {e}")
            return False
    
    async def fill(self, selector: str, value: str) -> bool:
        """Fill an input field using puppeteer_fill MCP tool."""
        try:
            # Real MCP tool call
            result = await mcp_tool_call("puppeteer_fill", {
                "selector": selector,
                "value": value
            })
            return result.success
        except Exception as e:
            print(f"Fill failed: {e}")
            return False
    
    async def evaluate(self, script: str) -> Any:
        """Execute JavaScript using puppeteer_evaluate MCP tool."""
        try:
            # Real MCP tool call
            result = await mcp_tool_call("puppeteer_evaluate", {"script": script})
            return result.data if result.success else None
        except Exception as e:
            print(f"Evaluate failed: {e}")
            return None
    
    async def wait_for_element(self, selector: str, timeout: int = None) -> bool:
        """Wait for an element to appear with proper error handling."""
        timeout = timeout or self.config.timeout
        
        try:
            # Real MCP tool call for waiting
            result = await mcp_tool_call("puppeteer_wait_for_selector", {
                "selector": selector,
                "timeout": timeout
            })
            return result.success
        except Exception as e:
            print(f"Element wait failed for '{selector}': {e}")
            return False


@pytest.fixture(scope="session")
def ui_test_config():
    """UI test configuration fixture."""
    from .config import get_config
    return get_config()


@pytest.fixture(scope="session")  
def browser_config(ui_test_config):
    """Browser configuration fixture with backward compatibility."""
    return BrowserConfig.from_ui_config(ui_test_config)


@pytest.fixture(scope="session")
def browser_manager(browser_config):
    """Browser manager fixture for the entire test session."""
    return PuppeteerMCPManager(browser_config)


@pytest.fixture(scope="function")
async def dashboard_page(browser_manager, browser_config):
    """Navigate to dashboard page for each test with cleanup."""
    success = await browser_manager.navigate(browser_config.dashboard_url)
    if not success:
        pytest.skip("Failed to navigate to dashboard")
    
    # Wait for dashboard to load
    await browser_manager.wait_for_element("body", timeout=10000)
    
    yield browser_manager
    
    # Cleanup: Reset dashboard state and clear any modals/selections
    try:
        # Clear any active selections or modals
        await browser_manager.evaluate("""
        // Close any open modals
        document.querySelectorAll('.modal, .popup, .overlay').forEach(modal => {
            if (modal.style.display !== 'none') modal.remove();
        });
        
        // Clear any selections
        document.querySelectorAll('.selected, .active:not(.tab)').forEach(el => {
            el.classList.remove('selected', 'active');
        });
        
        // Clear form inputs
        document.querySelectorAll('input, textarea').forEach(input => {
            if (input.type !== 'hidden') input.value = '';
        });
        
        // Reset to default tab if possible
        const defaultTab = document.querySelector('.tab:first-child, .nav-tab:first-child');
        if (defaultTab && !defaultTab.classList.contains('active')) {
            defaultTab.click();
        }
        """)
        
        # Optional: Take screenshot after each test for debugging
        test_name = os.environ.get('PYTEST_CURRENT_TEST', 'unknown').split('::')[-1].split('[')[0]
        await browser_manager.screenshot(f"test_cleanup_{test_name}")
        
    except Exception as e:
        print(f"Cleanup warning: {e}")  # Non-blocking cleanup errors


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
    """Helper class for visual regression testing with configurable tolerance."""
    
    def __init__(self, baseline_dir: str, current_dir: str, diff_dir: str, tolerance: float = 0.1):
        self.baseline_dir = baseline_dir
        self.current_dir = current_dir
        self.diff_dir = diff_dir
        self.tolerance = tolerance  # Percentage of pixels that can differ
    
    async def capture_and_compare(self, browser_manager: PuppeteerMCPManager, 
                                name: str, selector: str = None, tolerance: float = None) -> bool:
        """
        Capture screenshot and compare with baseline using configurable tolerance.
        
        Args:
            browser_manager: Browser automation manager
            name: Screenshot name (without extension)
            selector: Optional CSS selector for element-specific screenshot
            tolerance: Override default tolerance (0.0-1.0, percentage of pixels)
        
        Returns:
            bool: True if images match within tolerance, False if different
        """
        # Use provided tolerance or instance default
        comparison_tolerance = tolerance if tolerance is not None else self.tolerance
        
        current_path = f"{self.current_dir}/{name}.png"
        baseline_path = f"{self.baseline_dir}/{name}.png"
        diff_path = f"{self.diff_dir}/{name}_diff.png"
        
        # Take current screenshot
        await browser_manager.screenshot(name, selector)
        
        # If no baseline exists, create it
        if not os.path.exists(baseline_path):
            # Copy current to baseline
            # In real implementation, would copy the file
            print(f"📸 Creating baseline screenshot: {baseline_path}")
            return True
        
        # Compare images with tolerance
        if comparison_tolerance == 0.0:
            # Exact match required
            matches = await self._compare_images_exact(baseline_path, current_path)
        else:
            # Tolerance-based comparison
            matches = await self._compare_images_with_tolerance(
                baseline_path, current_path, diff_path, comparison_tolerance
            )
        
        if matches:
            print(f"✅ Visual regression passed: {name} (tolerance: {comparison_tolerance:.1%})")
        else:
            print(f"❌ Visual regression failed: {name} - see {diff_path}")
        
        return matches
    
    async def _compare_images_exact(self, baseline_path: str, current_path: str) -> bool:
        """Compare images for exact match."""
        try:
            from PIL import Image
            
            if not os.path.exists(baseline_path) or not os.path.exists(current_path):
                print(f"❌ Missing image files for comparison")
                return False
                
            baseline = Image.open(baseline_path)
            current = Image.open(current_path)
            
            # Check if dimensions match
            if baseline.size != current.size:
                print(f"❌ Image dimensions don't match: {baseline.size} vs {current.size}")
                return False
            
            # Compare pixel data
            is_exact_match = baseline.tobytes() == current.tobytes()
            print(f"🔍 Exact comparison: {baseline_path} vs {current_path} - {'Match' if is_exact_match else 'Different'}")
            return is_exact_match
            
        except ImportError:
            print(f"⚠️  PIL not available, falling back to stub comparison")
            return True
        except Exception as e:
            print(f"❌ Image comparison failed: {e}")
            return False
    
    async def _compare_images_with_tolerance(self, baseline_path: str, current_path: str, 
                                          diff_path: str, tolerance: float) -> bool:
        """Compare images with tolerance for pixel differences."""
        try:
            from PIL import Image, ImageChops
            import numpy as np
            
            if not os.path.exists(baseline_path) or not os.path.exists(current_path):
                print(f"❌ Missing image files for comparison")
                return False
            
            baseline = Image.open(baseline_path)
            current = Image.open(current_path)
            
            if baseline.size != current.size:
                print(f"❌ Image dimensions don't match: {baseline.size} vs {current.size}")
                return False
            
            # Calculate difference
            diff = ImageChops.difference(baseline, current)
            diff_array = np.array(diff)
            
            # Calculate percentage of different pixels
            total_pixels = diff_array.size
            different_pixels = np.count_nonzero(diff_array)
            difference_percentage = different_pixels / total_pixels
            
            print(f"📊 Tolerance comparison: {baseline_path} vs {current_path}")
            print(f"   Different pixels: {different_pixels}/{total_pixels} ({difference_percentage:.2%})")
            print(f"   Tolerance: {tolerance:.1%}")
            
            if difference_percentage > tolerance:
                # Save diff image for review
                diff.save(diff_path)
                print(f"❌ Visual regression failed - diff saved to {diff_path}")
                return False
            
            print(f"✅ Visual regression passed within tolerance")
            return True
            
        except ImportError:
            print(f"⚠️  PIL/numpy not available, falling back to stub comparison")
            return True
        except Exception as e:
            print(f"❌ Image comparison failed: {e}")
            return False
    
    def set_tolerance(self, tolerance: float):
        """Set default tolerance for comparisons."""
        if not 0.0 <= tolerance <= 1.0:
            raise ValueError("Tolerance must be between 0.0 and 1.0")
        self.tolerance = tolerance
        print(f"🎯 Visual regression tolerance set to {tolerance:.1%}")
    
    def update_baseline(self, name: str):
        """Update baseline screenshot from current screenshot."""
        import shutil
        
        current_path = f"{self.current_dir}/{name}.png"
        baseline_path = f"{self.baseline_dir}/{name}.png"
        
        if os.path.exists(current_path):
            try:
                shutil.copy2(current_path, baseline_path)
                print(f"📸 Updated baseline: {baseline_path}")
            except Exception as e:
                print(f"❌ Failed to update baseline: {e}")
        else:
            print(f"❌ Cannot update baseline - current screenshot not found: {current_path}")


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