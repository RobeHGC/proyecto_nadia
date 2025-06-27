# tests/config/resilience_config.py
"""Configuration parameters for resilience and performance testing."""
import os
from typing import Dict, Any

# Load Test Configuration
LOAD_TEST_PARAMS = {
    "light_load": {
        "message_burst": {"count": 50, "duration_seconds": 10},
        "concurrent_users": {"users": 5, "messages_per_user": 10},
        "resource_monitoring": {"duration_seconds": 20, "interval": 1.0}
    },
    "medium_load": {
        "message_burst": {"count": 100, "duration_seconds": 15}, 
        "concurrent_users": {"users": 25, "messages_per_user": 4},
        "resource_monitoring": {"duration_seconds": 30, "interval": 0.5}
    },
    "stress_load": {
        "message_burst": {"count": 300, "duration_seconds": 60},
        "concurrent_users": {"users": 50, "messages_per_user": 10},
        "resource_monitoring": {"duration_seconds": 60, "interval": 0.5}
    }
}

# API Resilience Configuration
API_RESILIENCE_PARAMS = {
    "timeout_scenarios": {
        "short_timeout": 2.0,
        "medium_timeout": 10.0, 
        "long_timeout": 30.0
    },
    "rate_limiting": {
        "high_failure_rate": 0.8,
        "medium_failure_rate": 0.5,
        "low_failure_rate": 0.2
    },
    "network_failures": {
        "intermittent_pattern": [True, False, True, False, False],  # 60% failure
        "high_failure_pattern": [True, True, False, True, False],  # 80% failure
        "recovery_pattern": [True, True, True, False, False]       # Initial failures, then recovery
    }
}

# Concurrency Test Configuration  
CONCURRENCY_PARAMS = {
    "memory_access": {
        "light": {"user_count": 5, "operations_per_user": 10},
        "medium": {"user_count": 20, "operations_per_user": 15},
        "heavy": {"user_count": 50, "operations_per_user": 20}
    },
    "database_operations": {
        "light": {"concurrent_writes": 10},
        "medium": {"concurrent_writes": 25},
        "heavy": {"concurrent_writes": 50}
    },
    "redis_connections": {
        "light": {"concurrent_connections": 15, "operations_per_connection": 5},
        "medium": {"concurrent_connections": 25, "operations_per_connection": 10},
        "heavy": {"concurrent_connections": 50, "operations_per_connection": 15}
    }
}

# Resource Exhaustion Configuration
RESOURCE_EXHAUSTION_PARAMS = {
    "memory_testing": {
        "light": {"target_mb": 50, "increment_mb": 5},
        "medium": {"target_mb": 100, "increment_mb": 10},
        "stress": {"target_mb": 200, "increment_mb": 20}
    },
    "connection_testing": {
        "light": {"max_connections": 25},
        "medium": {"max_connections": 50},
        "heavy": {"max_connections": 100}
    },
    "cpu_testing": {
        "light": {"duration_seconds": 5, "cpu_threads": 2},
        "medium": {"duration_seconds": 10, "cpu_threads": 4},
        "heavy": {"duration_seconds": 20, "cpu_threads": 8}
    }
}

# Performance Benchmarks
PERFORMANCE_BENCHMARKS = {
    "response_time": {
        "normal_load_max": 2.0,      # seconds
        "stress_load_max": 5.0,      # seconds
        "timeout_threshold": 10.0    # seconds
    },
    "throughput": {
        "minimum_sustained": 100,    # messages per minute
        "target_burst": 300,         # messages per minute
        "degradation_threshold": 0.7 # 70% of normal throughput
    },
    "memory_usage": {
        "stable_operation_mb": 500,  # MB
        "load_operation_mb": 1024,   # MB
        "critical_threshold_mb": 2048 # MB
    },
    "error_rates": {
        "normal_load_max": 0.10,     # 10% (realistic with 5% simulated failure rate)
        "stress_load_max": 0.15,     # 15%
        "critical_threshold": 0.25   # 25%
    }
}

# Test Environment Configuration
TEST_ENVIRONMENT = {
    "allowed_environments": ["test", "development", "local"],
    "prohibited_environments": ["production", "staging", "prod"],
    "resource_limits": {
        "max_test_duration_minutes": 30,
        "max_memory_allocation_mb": 512,
        "max_cpu_threads": 8,
        "max_file_size_mb": 100
    }
}

# Test Timeouts
TEST_TIMEOUTS = {
    "default_test_timeout": 60.0,      # seconds
    "load_test_timeout": 120.0,        # seconds  
    "stress_test_timeout": 300.0,      # seconds
    "resource_test_timeout": 180.0,    # seconds
    "api_test_timeout": 30.0           # seconds
}

def get_load_test_config(load_level: str = "light_load") -> Dict[str, Any]:
    """Get load test configuration for specified level."""
    return LOAD_TEST_PARAMS.get(load_level, LOAD_TEST_PARAMS["light_load"])

def get_concurrency_config(test_type: str, intensity: str = "light") -> Dict[str, Any]:
    """Get concurrency test configuration."""
    return CONCURRENCY_PARAMS.get(test_type, {}).get(intensity, {})

def get_performance_benchmark(category: str) -> Dict[str, Any]:
    """Get performance benchmark thresholds."""
    return PERFORMANCE_BENCHMARKS.get(category, {})

def is_test_environment_safe() -> bool:
    """Check if current environment is safe for resilience testing."""
    current_env = os.getenv('ENVIRONMENT', '').lower()
    node_env = os.getenv('NODE_ENV', '').lower()
    
    # Check prohibited environments
    prohibited = TEST_ENVIRONMENT["prohibited_environments"]
    if current_env in prohibited or node_env in prohibited:
        return False
    
    # Allow if explicitly in allowed environments
    allowed = TEST_ENVIRONMENT["allowed_environments"]
    if current_env in allowed or node_env in allowed:
        return True
    
    # Default to safe if no environment specified (assume local development)
    if not current_env and not node_env:
        return True
    
    return False

def get_resource_limit(limit_type: str) -> Any:
    """Get resource limit for testing."""
    return TEST_ENVIRONMENT["resource_limits"].get(limit_type)

def get_test_timeout(test_category: str) -> float:
    """Get timeout for specific test category."""
    return TEST_TIMEOUTS.get(f"{test_category}_timeout", TEST_TIMEOUTS["default_test_timeout"])