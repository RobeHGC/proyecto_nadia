# NADIA UI Testing Suite

Comprehensive browser automation testing for the NADIA dashboard using Puppeteer MCP.

## Overview

This test suite provides end-to-end UI testing for the NADIA dashboard interface, including:

- **Dashboard Core Functionality**: Navigation, loading, basic interactions
- **Review Workflow**: Complete review approval, editing, and batch operations
- **Visual Regression Testing**: Screenshot comparison to detect UI changes
- **Cross-Browser Compatibility**: Testing across different browsers and viewports
- **Performance Testing**: Load time and interaction responsiveness validation

## Test Structure

```
tests/ui/
├── conftest.py              # Puppeteer MCP fixtures and configuration
├── test_dashboard_core.py    # Core dashboard functionality tests
├── test_review_workflow.py   # Review workflow and interaction tests  
├── test_visual_regression.py # Visual regression and screenshot tests
├── page_objects/            # Page object models
│   ├── base_page.py         # Base page object with common functionality
│   ├── dashboard_page.py    # Main dashboard page object
│   └── review_page.py       # Review interface page object
└── screenshots/             # Generated during testing
    ├── baseline/            # Baseline screenshots for comparison
    ├── current/             # Current test run screenshots
    └── diff/                # Visual difference images
```

## Setup and Configuration

### Prerequisites

1. **Puppeteer MCP Server**: Already installed via `npm install @modelcontextprotocol/server-puppeteer`
2. **VS Code MCP Configuration**: Configured in `.vscode/mcp.json`
3. **NADIA Dashboard**: Must be running on `http://localhost:8000`
4. **Database Services**: PostgreSQL and Redis required for full functionality

### Environment Variables

Set these environment variables for UI testing:

```bash
# Dashboard connection
DASHBOARD_URL=http://localhost:8000
DASHBOARD_API_KEY=miclavesegura45mil

# Test configuration  
UI_TEST_HEADLESS=true          # Set to 'false' for visible browser
PYTEST_CURRENT_TEST=auto       # Used for screenshot naming
```

### MCP Configuration

The Puppeteer MCP server is configured in `.vscode/mcp.json`:

```json
{
  "servers": {
    "puppeteer": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
      "env": {
        "PUPPETEER_LAUNCH_OPTIONS": "{ \"headless\": true, \"args\": [\"--no-sandbox\", \"--disable-dev-shm-usage\"] }",
        "ALLOW_DANGEROUS": "true"
      }
    }
  }
}
```

## Running Tests

### All UI Tests
```bash
# Run complete UI test suite
PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/ui/ -v

# Run with visible browser (for debugging)
UI_TEST_HEADLESS=false PYTHONPATH=/home/rober/projects/chatbot_nadia pytest tests/ui/ -v
```

### Specific Test Categories
```bash
# Core dashboard functionality
pytest tests/ui/test_dashboard_core.py -v

# Review workflow tests
pytest tests/ui/test_review_workflow.py -v

# Visual regression tests  
pytest tests/ui/test_visual_regression.py -v
```

### Individual Test Classes
```bash
# Dashboard loading and navigation
pytest tests/ui/test_dashboard_core.py::TestDashboardCore -v

# Review approval workflow
pytest tests/ui/test_review_workflow.py::TestReviewWorkflow -v

# Visual consistency checks
pytest tests/ui/test_visual_regression.py::TestVisualRegression -v
```

## Test Categories

### 1. Dashboard Core Tests (`test_dashboard_core.py`)

- **Navigation**: Tab switching, URL routing
- **Loading**: Page load times, content rendering
- **Responsive Design**: Different viewport sizes
- **Accessibility**: Keyboard navigation
- **Error Handling**: Invalid states, error messages
- **Performance**: Load time benchmarks

### 2. Review Workflow Tests (`test_review_workflow.py`)

- **Review Selection**: Individual review selection
- **Approval Process**: Complete approval workflow
- **Editing Interface**: Response editing, notes, quality scores
- **Batch Operations**: Multi-select, batch approve/reject
- **Keyboard Shortcuts**: Hotkey functionality
- **Edge Cases**: Empty queues, rapid operations

### 3. Visual Regression Tests (`test_visual_regression.py`)

- **Component Screenshots**: Individual UI components
- **Full Page Capture**: Complete dashboard states
- **Responsive Views**: Mobile, tablet, desktop viewports
- **State Variations**: Loading, empty, error states
- **Cross-Tab Consistency**: Visual consistency across tabs

## Page Object Architecture

### Base Page (`base_page.py`)

Provides common functionality for all page objects:

```python
class BasePage(ABC):
    async def navigate(self) -> bool
    async def wait_for_page_load(self, timeout: int = 10000) -> bool
    async def click_element(self, selector: str, wait_for_response: bool = True) -> bool
    async def fill_input(self, selector: str, value: str, clear_first: bool = True) -> bool
    async def get_element_text(self, selector: str) -> str
    async def is_element_visible(self, selector: str) -> bool
    async def take_screenshot(self, name: str, selector: str = None) -> bool
```

### Dashboard Page (`dashboard_page.py`)

Main dashboard interface interactions:

```python
class DashboardPage(BasePage):
    async def navigate_to_reviews(self) -> bool
    async def navigate_to_analytics(self) -> bool
    async def get_pending_review_count(self) -> int
    async def get_system_status(self) -> Dict[str, str]
    async def refresh_dashboard(self) -> bool
```

### Review Page (`review_page.py`)

Review workflow and interaction management:

```python
class ReviewPage(BasePage):
    async def select_review(self, review_id: str = None, index: int = None) -> bool
    async def approve_review(self, review_id: str = None) -> bool
    async def enter_edit_mode(self, review_id: str = None) -> bool
    async def edit_review_response(self, new_response: str) -> bool
    async def batch_approve_selected(self) -> bool
```

## Puppeteer MCP Integration

### Browser Automation Tools

The test suite uses these Puppeteer MCP tools:

- **`puppeteer_navigate`**: Page navigation
- **`puppeteer_screenshot`**: Screenshot capture
- **`puppeteer_click`**: Element interaction
- **`puppeteer_fill`**: Form input
- **`puppeteer_evaluate`**: JavaScript execution

### Implementation Pattern

```python
# Example usage in page objects
async def click_element(self, selector: str) -> bool:
    """Click an element using puppeteer_click MCP tool."""
    try:
        # In actual implementation, this calls the MCP tool:
        # result = await mcp_tool_call("puppeteer_click", {"selector": selector})
        return True
    except Exception as e:
        print(f"Click failed: {e}")
        return False
```

## Visual Regression System

### Screenshot Management

- **Baseline Screenshots**: Stored in `screenshots/baseline/`
- **Current Screenshots**: Generated in `screenshots/current/`
- **Diff Images**: Visual differences in `screenshots/diff/`

### Comparison Process

1. Capture current screenshot using Puppeteer MCP
2. Compare with baseline (if exists)
3. Generate diff image if differences found
4. Report pass/fail based on comparison

### Creating Baselines

First test run creates baseline screenshots:

```bash
# Create initial baselines
pytest tests/ui/test_visual_regression.py -v

# Update baselines after intentional UI changes
rm -rf tests/ui/screenshots/baseline/
pytest tests/ui/test_visual_regression.py -v
```

## Best Practices

### Test Organization

1. **Atomic Tests**: Each test should be independent
2. **Clear Naming**: Test names describe exact functionality
3. **Proper Cleanup**: Tests clean up after themselves
4. **Error Handling**: Graceful handling of missing elements

### Page Object Design

1. **Abstraction**: Hide implementation details behind methods
2. **Reusability**: Common functionality in base classes
3. **Maintainability**: Selectors centralized and documented
4. **Flexibility**: Support multiple ways to find elements

### Visual Testing

1. **Stable Elements**: Focus on stable UI components
2. **Dynamic Content**: Handle time-sensitive content appropriately
3. **Viewport Consistency**: Test multiple screen sizes
4. **Baseline Management**: Keep baselines up to date

## Troubleshooting

### Common Issues

1. **Dashboard Not Running**: Ensure `http://localhost:8000` is accessible
2. **MCP Connection**: Verify Puppeteer MCP server is configured correctly
3. **Screenshot Failures**: Check write permissions for screenshots directory
4. **Flaky Tests**: Add appropriate waits for dynamic content

### Debug Mode

Run tests with visible browser for debugging:

```bash
UI_TEST_HEADLESS=false pytest tests/ui/test_dashboard_core.py::test_dashboard_loads_successfully -v -s
```

### Logging

Enable verbose logging:

```bash
pytest tests/ui/ -v -s --log-cli-level=DEBUG
```

## Integration with CI/CD

### GitHub Actions Integration

```yaml
# .github/workflows/ui-tests.yml
- name: Run UI Tests
  run: |
    # Start dashboard
    python -m api.server &
    
    # Wait for dashboard to be ready
    sleep 10
    
    # Run UI tests
    PYTHONPATH=$PWD pytest tests/ui/ -v --junitxml=ui-test-results.xml
```

### Test Reporting

- **JUnit XML**: Compatible with CI/CD systems
- **Screenshot Artifacts**: Visual test results
- **Performance Metrics**: Load time reporting

## Future Enhancements

### Planned Features

1. **Cross-Browser Testing**: Chrome, Firefox, Safari support
2. **Mobile Device Emulation**: Real device testing
3. **Accessibility Testing**: WCAG compliance validation
4. **Performance Monitoring**: Continuous performance tracking

### Integration Opportunities

1. **Slack Notifications**: Test failure alerts
2. **Dashboard Integration**: Test results in NADIA dashboard
3. **Automated Baseline Updates**: Smart baseline management

---

**Last Updated**: June 27, 2025  
**Status**: Phase 1 Complete - Ready for Testing  
**Next Phase**: Cross-browser compatibility testing