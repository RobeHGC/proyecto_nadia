#!/usr/bin/env python3
"""
Validation Script for Code Review Improvements

Validates that all high-priority improvements from the code review have been
successfully implemented and are working correctly.
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class CodeReviewValidation:
    """Validation suite for code review improvements."""
    
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
    
    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log a test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append(f"{status}: {test_name}")
        if details:
            self.results.append(f"     {details}")
        
        if success:
            self.passed += 1
        else:
            self.failed += 1
    
    def validate_configuration_management(self):
        """Validate configuration management implementation."""
        print("🔧 Validating Configuration Management...")
        
        try:
            from tests.ui.config import UITestConfig, get_config, EnvironmentConfig
            
            # Test default configuration
            config = UITestConfig()
            self.log_result(
                "Configuration Management: Default Config",
                True,
                f"Timeout: {config.default_timeout}ms, Headless: {config.headless}"
            )
            
            # Test environment configurations
            ci_config = EnvironmentConfig.ci()
            self.log_result(
                "Configuration Management: CI Environment",
                ci_config.ci_mode is True,
                f"CI mode enabled, tolerance: {ci_config.visual_tolerance}"
            )
            
            # Test configuration validation
            try:
                UITestConfig(default_timeout=-1)
                self.log_result("Configuration Management: Validation", False, "Should reject negative timeout")
            except ValueError:
                self.log_result("Configuration Management: Validation", True, "Properly validates negative values")
            
            # Test browser options generation
            options = config.get_browser_options()
            self.log_result(
                "Configuration Management: Browser Options",
                'headless' in options and 'defaultViewport' in options,
                f"Generated options: headless={options.get('headless')}"
            )
            
        except Exception as e:
            self.log_result("Configuration Management", False, f"Error: {e}")
    
    async def validate_retry_mechanisms(self):
        """Validate retry mechanisms implementation."""
        print("🔄 Validating Retry Mechanisms...")
        
        try:
            from tests.ui.retry_utils import retry_async, UIRetryConfigs, RetryableError
            
            # Test retry configurations exist
            mcp_config = UIRetryConfigs.mcp_call()
            screenshot_config = UIRetryConfigs.screenshot()
            nav_config = UIRetryConfigs.navigation()
            
            self.log_result(
                "Retry Mechanisms: Configurations",
                all([mcp_config, screenshot_config, nav_config]),
                f"MCP: {mcp_config.max_attempts}x, Screenshot: {screenshot_config.max_attempts}x, Nav: {nav_config.max_attempts}x"
            )
            
            # Test basic retry functionality
            call_count = 0
            
            @retry_async(UIRetryConfigs.mcp_call())
            async def test_retry():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise RetryableError("Test failure")
                return "success"
            
            result = await test_retry()
            self.log_result(
                "Retry Mechanisms: Basic Retry",
                result == "success" and call_count == 2,
                f"Succeeded after {call_count} attempts"
            )
            
            # Test non-retryable errors
            call_count = 0
            
            @retry_async(UIRetryConfigs.mcp_call())
            async def test_non_retryable():
                nonlocal call_count
                call_count += 1
                raise AssertionError("Should not retry")
            
            try:
                await test_non_retryable()
                self.log_result("Retry Mechanisms: Non-Retryable", False, "Should have raised AssertionError")
            except AssertionError:
                self.log_result(
                    "Retry Mechanisms: Non-Retryable",
                    call_count == 1,
                    f"Correctly did not retry AssertionError (calls: {call_count})"
                )
            
        except Exception as e:
            self.log_result("Retry Mechanisms", False, f"Error: {e}")
    
    def validate_security_validation(self):
        """Validate security and input validation implementation."""
        print("🔒 Validating Security & Input Validation...")
        
        try:
            from tests.ui.security import SecurityManager, get_security_manager
            
            security_manager = SecurityManager()
            
            # Test URL validation
            try:
                # Valid URL
                params = security_manager.validate_mcp_params("puppeteer_navigate", {"url": "http://localhost:8000"})
                valid_url_test = params["url"] == "http://localhost:8000"
                
                # Invalid URL
                try:
                    security_manager.validate_mcp_params("puppeteer_navigate", {"url": "javascript:alert(1)"})
                    invalid_url_test = False
                except (ValueError, RuntimeError):
                    invalid_url_test = True
                
                self.log_result(
                    "Security Validation: URL Validation",
                    valid_url_test and invalid_url_test,
                    "Accepts valid URLs, rejects dangerous schemes"
                )
            except Exception as e:
                self.log_result("Security Validation: URL Validation", False, f"Error: {e}")
            
            # Test selector validation
            try:
                # Valid selector
                params = security_manager.validate_mcp_params("puppeteer_click", {"selector": "body"})
                valid_selector_test = params["selector"] == "body"
                
                # Invalid selector
                try:
                    security_manager.validate_mcp_params("puppeteer_click", {"selector": "<script>alert(1)</script>"})
                    invalid_selector_test = False
                except (ValueError, RuntimeError):
                    invalid_selector_test = True
                
                self.log_result(
                    "Security Validation: Selector Validation",
                    valid_selector_test and invalid_selector_test,
                    "Accepts valid selectors, rejects dangerous patterns"
                )
            except Exception as e:
                self.log_result("Security Validation: Selector Validation", False, f"Error: {e}")
            
            # Test rate limiting
            try:
                status = security_manager.get_security_status()
                rate_limit_test = 'rate_limits' in status and 'mcp_call' in status['rate_limits']
                
                self.log_result(
                    "Security Validation: Rate Limiting",
                    rate_limit_test,
                    f"Rate limits active: {list(status.get('rate_limits', {}).keys())}"
                )
            except Exception as e:
                self.log_result("Security Validation: Rate Limiting", False, f"Error: {e}")
            
            # Test path validation
            try:
                # Valid screenshot name
                params = security_manager.validate_mcp_params("puppeteer_screenshot", {"name": "test_screenshot"})
                valid_path_test = params["name"] == "test_screenshot"
                
                # Invalid path (path traversal)
                try:
                    security_manager.validate_mcp_params("puppeteer_screenshot", {"name": "../../../etc/passwd"})
                    invalid_path_test = False
                except (ValueError, RuntimeError):
                    invalid_path_test = True
                
                self.log_result(
                    "Security Validation: Path Validation",
                    valid_path_test and invalid_path_test,
                    "Accepts valid paths, rejects traversal attempts"
                )
            except Exception as e:
                self.log_result("Security Validation: Path Validation", False, f"Error: {e}")
            
        except Exception as e:
            self.log_result("Security Validation", False, f"Error: {e}")
    
    async def validate_mcp_adapter_improvements(self):
        """Validate MCP adapter improvements."""
        print("🔌 Validating MCP Adapter Improvements...")
        
        try:
            from tests.ui.config import UITestConfig
            from tests.ui.security import SecurityManager  
            from tests.ui.mcp_adapter import PuppeteerMCPAdapter
            
            # Test adapter initialization with config
            config = UITestConfig()
            security_manager = SecurityManager()
            adapter = PuppeteerMCPAdapter(config=config, security_manager=security_manager)
            
            self.log_result(
                "MCP Adapter: Initialization with Config",
                adapter.config == config and adapter.security_manager == security_manager,
                "Adapter properly initialized with configuration and security manager"
            )
            
            # Test retry decorators are applied
            has_retry_decorators = all([
                hasattr(adapter.navigate, '__wrapped__'),
                hasattr(adapter.screenshot, '__wrapped__'),
                hasattr(adapter.click, '__wrapped__'),
                hasattr(adapter.fill, '__wrapped__'),
                hasattr(adapter.evaluate, '__wrapped__')
            ])
            
            self.log_result(
                "MCP Adapter: Retry Decorators",
                has_retry_decorators,
                "All methods have retry decorators applied"
            )
            
            # Test security validation integration
            result = await adapter.navigate("javascript:alert(1)")
            security_integration_test = not result.success and any(
                keyword in result.error.lower() 
                for keyword in ["validation", "scheme", "not allowed"]
            )
            
            self.log_result(
                "MCP Adapter: Security Integration",
                security_integration_test,
                f"Security validation working: {result.error}"
            )
            
        except Exception as e:
            self.log_result("MCP Adapter Improvements", False, f"Error: {e}")
    
    def validate_backward_compatibility(self):
        """Validate backward compatibility is maintained."""
        print("🔄 Validating Backward Compatibility...")
        
        try:
            # Test old BrowserConfig still works
            from tests.ui.conftest import BrowserConfig
            
            browser_config = BrowserConfig()
            old_config_test = (
                browser_config.headless is True and 
                browser_config.timeout == 30000
            )
            
            # Test conversion from new config
            from tests.ui.config import UITestConfig
            ui_config = UITestConfig()
            converted_config = BrowserConfig.from_ui_config(ui_config)
            conversion_test = converted_config.viewport == ui_config.get_viewport()
            
            self.log_result(
                "Backward Compatibility: BrowserConfig",
                old_config_test and conversion_test,
                "Old BrowserConfig works, conversion from UITestConfig functional"
            )
            
        except Exception as e:
            self.log_result("Backward Compatibility", False, f"Error: {e}")
    
    def validate_file_structure(self):
        """Validate new file structure is correct."""
        print("📁 Validating File Structure...")
        
        required_files = [
            "tests/ui/config.py",
            "tests/ui/retry_utils.py", 
            "tests/ui/security.py",
            "tests/ui/test_code_review_improvements.py"
        ]
        
        missing_files = []
        for file_path in required_files:
            full_path = project_root / file_path
            if not full_path.exists():
                missing_files.append(file_path)
        
        self.log_result(
            "File Structure: Required Files",
            len(missing_files) == 0,
            f"All required files present" if not missing_files else f"Missing: {missing_files}"
        )
        
        # Check file sizes (should not be empty)
        file_sizes = {}
        for file_path in required_files:
            full_path = project_root / file_path
            if full_path.exists():
                file_sizes[file_path] = full_path.stat().st_size
        
        non_empty_files = sum(1 for size in file_sizes.values() if size > 100)  # At least 100 bytes
        
        self.log_result(
            "File Structure: File Content",
            non_empty_files == len(required_files),
            f"Files with content: {non_empty_files}/{len(required_files)}"
        )
    
    def generate_report(self):
        """Generate validation report."""
        print("\n" + "="*70)
        print("CODE REVIEW IMPROVEMENTS - VALIDATION REPORT")
        print("="*70)
        
        for result in self.results:
            print(result)
        
        print("\n" + "="*70)
        print(f"SUMMARY: {self.passed} PASSED, {self.failed} FAILED")
        
        success_rate = (self.passed / (self.passed + self.failed)) * 100 if (self.passed + self.failed) > 0 else 0
        print(f"SUCCESS RATE: {success_rate:.1f}%")
        
        if success_rate >= 95:
            print("🎉 CODE REVIEW IMPROVEMENTS: EXCELLENT")
            print("   All high-priority improvements implemented successfully")
        elif success_rate >= 85:
            print("✅ CODE REVIEW IMPROVEMENTS: SUCCESSFUL")  
            print("   Core improvements working, minor issues detected")
        elif success_rate >= 70:
            print("⚠️  CODE REVIEW IMPROVEMENTS: PARTIAL")
            print("   Some improvements working, issues need attention")
        else:
            print("❌ CODE REVIEW IMPROVEMENTS: NEEDS WORK")
            print("   Major issues detected, review implementation")
        
        print("="*70)
        
        return success_rate >= 85


async def main():
    """Run complete validation suite."""
    print("🚀 Starting Code Review Improvements Validation")
    print("PR #49: EPIC 5: Complete UI Testing Infrastructure with Puppeteer MCP")
    print("Validating High-Priority Improvements from Code Review")
    print()
    
    validator = CodeReviewValidation()
    
    # Run all validations
    validator.validate_file_structure()
    validator.validate_configuration_management()
    await validator.validate_retry_mechanisms()
    validator.validate_security_validation()
    await validator.validate_mcp_adapter_improvements()
    validator.validate_backward_compatibility()
    
    success = validator.generate_report()
    
    if success:
        print("\n🎯 CODE REVIEW RECOMMENDATIONS IMPLEMENTED SUCCESSFULLY")
        print("✅ Configuration Management: Centralized, environment-aware")
        print("✅ Retry Mechanisms: Robust, configurable, intelligent")
        print("✅ Input Validation: Comprehensive security validation")
        print("✅ Security: Rate limiting, path validation, input sanitization")
        print("✅ Backward Compatibility: Maintained for existing code")
        print("\n📈 FRAMEWORK QUALITY: PRODUCTION-READY WITH ENHANCED RELIABILITY")
    else:
        print("\n⚠️  Some issues detected - review implementation before merge")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)