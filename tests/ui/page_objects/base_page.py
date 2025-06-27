"""
Base Page Object for NADIA Dashboard UI Testing

This module provides the base page object class that all other page objects inherit from.
It encapsulates common functionality for browser automation using Puppeteer MCP.
"""
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import asyncio


class BasePage(ABC):
    """
    Base page object class for NADIA dashboard testing.
    
    This class provides common functionality that all page objects need:
    - Browser manager integration
    - Common wait operations
    - Element interaction helpers
    - Screenshot capabilities
    """
    
    def __init__(self, browser_manager, config):
        """
        Initialize base page object.
        
        Args:
            browser_manager: PuppeteerMCPManager instance
            config: BrowserConfig instance
        """
        self.browser = browser_manager
        self.config = config
        self.base_url = config.dashboard_url
        
    @property
    @abstractmethod
    def page_url(self) -> str:
        """URL path for this specific page (relative to base_url)."""
        pass
    
    @property
    @abstractmethod
    def page_title_selector(self) -> str:
        """CSS selector for the main page title/header."""
        pass
    
    @property
    @abstractmethod
    def loading_indicator_selector(self) -> str:
        """CSS selector for loading indicators on this page."""
        pass
    
    async def navigate(self) -> bool:
        """Navigate to this page."""
        full_url = f"{self.base_url}{self.page_url}"
        success = await self.browser.navigate(full_url)
        if success:
            await self.wait_for_page_load()
        return success
    
    async def wait_for_page_load(self, timeout: int = 10000) -> bool:
        """Wait for the page to fully load."""
        # Wait for page title to be visible
        if self.page_title_selector:
            await self.wait_for_element(self.page_title_selector, timeout)
        
        # Wait for any loading indicators to disappear
        if self.loading_indicator_selector:
            await self.wait_for_element_to_disappear(self.loading_indicator_selector, timeout)
        
        # Wait for any pending API requests
        await self._wait_for_api_requests()
        
        return True
    
    async def wait_for_element(self, selector: str, timeout: int = None) -> bool:
        """Wait for an element to appear on the page."""
        return await self.browser.wait_for_element(selector, timeout)
    
    async def wait_for_element_to_disappear(self, selector: str, timeout: int = 5000) -> bool:
        """Wait for an element to disappear from the page."""
        script = f"""
        new Promise((resolve) => {{
            const checkGone = () => {{
                const element = document.querySelector('{selector}');
                if (!element || window.getComputedStyle(element).display === 'none') {{
                    resolve(true);
                }} else {{
                    setTimeout(checkGone, 100);
                }}
            }};
            checkGone();
            
            // Timeout after specified time
            setTimeout(() => resolve(true), {timeout});
        }});
        """
        
        await self.browser.evaluate(script)
        return True
    
    async def click_element(self, selector: str, wait_for_response: bool = True) -> bool:
        """
        Click an element and optionally wait for any resulting API calls.
        
        Args:
            selector: CSS selector for element to click
            wait_for_response: Whether to wait for API responses after clicking
        """
        success = await self.browser.click(selector)
        if success and wait_for_response:
            await self._wait_for_api_requests()
        return success
    
    async def fill_input(self, selector: str, value: str, clear_first: bool = True) -> bool:
        """
        Fill an input field with a value.
        
        Args:
            selector: CSS selector for input field
            value: Value to enter
            clear_first: Whether to clear the field first
        """
        if clear_first:
            # Clear the field first
            await self.browser.click(selector)
            clear_script = f"""
            const element = document.querySelector('{selector}');
            if (element) {{
                element.select();
                element.value = '';
                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
            """
            await self.browser.evaluate(clear_script)
        
        return await self.browser.fill(selector, value)
    
    async def get_element_text(self, selector: str) -> str:
        """Get the text content of an element."""
        script = f"""
        const element = document.querySelector('{selector}');
        return element ? element.textContent.trim() : '';
        """
        
        result = await self.browser.evaluate(script)
        return result or ""
    
    async def get_element_attribute(self, selector: str, attribute: str) -> str:
        """Get an attribute value from an element."""
        script = f"""
        const element = document.querySelector('{selector}');
        return element ? element.getAttribute('{attribute}') || '' : '';
        """
        
        result = await self.browser.evaluate(script)
        return result or ""
    
    async def is_element_visible(self, selector: str) -> bool:
        """Check if an element is visible on the page."""
        script = f"""
        const element = document.querySelector('{selector}');
        if (!element) return false;
        
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        
        return style.display !== 'none' && 
               style.visibility !== 'hidden' && 
               style.opacity !== '0' &&
               rect.width > 0 && 
               rect.height > 0;
        """
        
        result = await self.browser.evaluate(script)
        return bool(result)
    
    async def is_element_enabled(self, selector: str) -> bool:
        """Check if an element is enabled (not disabled)."""
        script = f"""
        const element = document.querySelector('{selector}');
        return element ? !element.disabled : false;
        """
        
        result = await self.browser.evaluate(script)
        return bool(result)
    
    async def get_all_elements_text(self, selector: str) -> List[str]:
        """Get text content from all matching elements."""
        script = f"""
        const elements = document.querySelectorAll('{selector}');
        return Array.from(elements).map(el => el.textContent.trim());
        """
        
        result = await self.browser.evaluate(script)
        return result or []
    
    async def count_elements(self, selector: str) -> int:
        """Count the number of elements matching a selector."""
        script = f"""
        return document.querySelectorAll('{selector}').length;
        """
        
        result = await self.browser.evaluate(script)
        return int(result) if result is not None else 0
    
    async def take_screenshot(self, name: str, selector: str = None) -> bool:
        """Take a screenshot of the page or specific element."""
        return await self.browser.screenshot(name, selector)
    
    async def scroll_to_element(self, selector: str) -> bool:
        """Scroll to make an element visible."""
        script = f"""
        const element = document.querySelector('{selector}');
        if (element) {{
            element.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            return true;
        }}
        return false;
        """
        
        result = await self.browser.evaluate(script)
        
        if result:
            # Wait a moment for smooth scrolling to complete
            await asyncio.sleep(0.5)
        
        return bool(result)
    
    async def hover_element(self, selector: str) -> bool:
        """Hover over an element."""
        # First scroll to element to ensure it's visible
        await self.scroll_to_element(selector)
        
        script = f"""
        const element = document.querySelector('{selector}');
        if (element) {{
            const event = new MouseEvent('mouseover', {{
                view: window,
                bubbles: true,
                cancelable: true
            }});
            element.dispatchEvent(event);
            return true;
        }}
        return false;
        """
        
        result = await self.browser.evaluate(script)
        return bool(result)
    
    async def get_table_data(self, table_selector: str) -> List[Dict[str, str]]:
        """
        Extract data from a table element.
        
        Returns list of dictionaries where keys are column headers.
        """
        script = f"""
        const table = document.querySelector('{table_selector}');
        if (!table) return [];
        
        const headers = Array.from(table.querySelectorAll('thead th, thead td'))
            .map(th => th.textContent.trim());
        
        const rows = Array.from(table.querySelectorAll('tbody tr'));
        
        return rows.map(row => {{
            const cells = Array.from(row.querySelectorAll('td, th'));
            const rowData = {{}};
            headers.forEach((header, index) => {{
                if (cells[index]) {{
                    rowData[header] = cells[index].textContent.trim();
                }}
            }});
            return rowData;
        }});
        """
        
        result = await self.browser.evaluate(script)
        return result or []
    
    async def select_dropdown_option(self, select_selector: str, option_value: str) -> bool:
        """Select an option from a dropdown."""
        script = f"""
        const select = document.querySelector('{select_selector}');
        if (select) {{
            select.value = '{option_value}';
            select.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
        }}
        return false;
        """
        
        result = await self.browser.evaluate(script)
        return bool(result)
    
    async def _wait_for_api_requests(self, timeout: int = 5000) -> None:
        """Wait for any pending AJAX requests to complete."""
        script = f"""
        new Promise((resolve) => {{
            let timeoutId;
            
            const checkComplete = () => {{
                // Check for jQuery if available
                if (window.jQuery && jQuery.active > 0) {{
                    timeoutId = setTimeout(checkComplete, 100);
                    return;
                }}
                
                // Check for fetch requests (modern approach)
                if (window.performance) {{
                    const perfEntries = performance.getEntriesByType('navigation');
                    // Basic check - in real implementation might be more sophisticated
                }}
                
                clearTimeout(timeoutId);
                resolve(true);
            }};
            
            // Start checking
            checkComplete();
            
            // Timeout fallback
            setTimeout(() => {{
                clearTimeout(timeoutId);
                resolve(true);
            }}, {timeout});
        }});
        """
        
        await self.browser.evaluate(script)
    
    async def wait_for_text_in_element(self, selector: str, expected_text: str, timeout: int = 5000) -> bool:
        """Wait for specific text to appear in an element."""
        script = f"""
        new Promise((resolve) => {{
            const checkText = () => {{
                const element = document.querySelector('{selector}');
                if (element && element.textContent.includes('{expected_text}')) {{
                    resolve(true);
                }} else {{
                    setTimeout(checkText, 100);
                }}
            }};
            
            checkText();
            
            // Timeout
            setTimeout(() => resolve(false), {timeout});
        }});
        """
        
        result = await self.browser.evaluate(script)
        return bool(result)
    
    async def press_key(self, key: str, selector: str = None) -> bool:
        """
        Press a keyboard key, optionally on a specific element.
        
        Args:
            key: Key to press (e.g., 'Enter', 'Escape', 'Tab')
            selector: Optional element to focus before pressing key
        """
        if selector:
            await self.browser.click(selector)
        
        script = f"""
        const event = new KeyboardEvent('keydown', {{
            key: '{key}',
            code: '{key}',
            bubbles: true,
            cancelable: true
        }});
        
        const target = {'document.querySelector("' + selector + '")' if selector else 'document.activeElement || document.body'};
        target.dispatchEvent(event);
        
        // Also dispatch keyup
        const upEvent = new KeyboardEvent('keyup', {{
            key: '{key}',
            code: '{key}',
            bubbles: true,
            cancelable: true
        }});
        target.dispatchEvent(upEvent);
        
        return true;
        """
        
        result = await self.browser.evaluate(script)
        return bool(result)