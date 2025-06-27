# MCP Developer Workflow Guide

> **Purpose**: This guide provides practical, scenario-based workflows for integrating MCP tools into daily NADIA development activities.

## Table of Contents

1. [Overview](#overview)
2. [Common Development Workflows](#common-development-workflows)
3. [Development Scenarios](#development-scenarios)
4. [Tool Orchestration](#tool-orchestration)
5. [Best Practices](#best-practices)
6. [Quick Start Scenarios](#quick-start-scenarios)

## Overview

The MCP (Model Context Protocol) system provides direct access to databases, filesystem, git repository, and custom monitoring tools. This guide shows how to integrate these tools into your development workflow for maximum efficiency.

### Available MCP Tools

| Tool | Purpose | Primary Use Cases |
|------|---------|-------------------|
| **postgres-nadia** | Database queries | Data investigation, schema analysis |
| **filesystem-nadia** | File operations | Code search, file analysis |
| **git-nadia** | Git history | Change tracking, blame analysis |
| **health-nadia** | System health | Service monitoring, dependency checks |
| **performance-nadia** | Performance metrics | Bottleneck detection, optimization |
| **security-nadia** | Security scanning | Vulnerability detection, config audits |
| **redis-nadia** | Redis operations | Queue analysis, cache inspection |

## Common Development Workflows

### 1. Bug Investigation Workflow

**Scenario**: Users report "undefined user_id" errors in the dashboard

```bash
# Step 1: Check current system health
mcp health-nadia check_system_health

# Step 2: Search for error patterns in logs
mcp filesystem-nadia search_files --pattern "user_id.*undefined" --path "/logs"

# Step 3: Analyze database state
mcp postgres-nadia query --sql "SELECT * FROM user_current_status WHERE user_id IS NULL"

# Step 4: Check Redis for inconsistent data
mcp redis-nadia analyze_queue_health

# Step 5: Review recent code changes
mcp git-nadia get_commit_history --path "dashboard/frontend/app.js" --limit 10
```

**Resolution Pattern**:
1. Identify error frequency and timing
2. Correlate with recent deployments
3. Check data consistency across systems
4. Implement fix with validation

### 2. Performance Optimization Workflow

**Scenario**: API endpoints responding slowly

```bash
# Step 1: Get performance baseline
mcp performance-nadia analyze_system_performance

# Step 2: Identify slow queries
mcp performance-nadia check_database_performance

# Step 3: Analyze specific endpoint
mcp postgres-nadia query --sql "
  SELECT query, calls, mean_exec_time 
  FROM pg_stat_statements 
  WHERE query LIKE '%user_current_status%' 
  ORDER BY mean_exec_time DESC 
  LIMIT 10"

# Step 4: Check for memory issues
mcp performance-nadia detect_bottlenecks

# Step 5: Review code for N+1 queries
mcp filesystem-nadia search_files --pattern "async.*for.*await" --path "api/"
```

**Optimization Steps**:
1. Identify slowest components
2. Add database indexes if needed
3. Implement caching strategies
4. Batch operations where possible

### 3. Security Review Workflow

**Scenario**: Pre-deployment security check

```bash
# Step 1: Scan for exposed secrets
mcp security-nadia scan_environment_files

# Step 2: Check API key usage
mcp security-nadia detect_api_keys

# Step 3: Audit file permissions
mcp security-nadia audit_permissions

# Step 4: Validate configuration
mcp security-nadia analyze_configuration --check redis --check postgres

# Step 5: Review recent changes for security issues
mcp git-nadia get_file_diff --file ".env.example" --commits 5
```

**Security Checklist**:
- [ ] No hardcoded credentials
- [ ] Environment files not in git
- [ ] Proper file permissions (644/755)
- [ ] API keys rotated regularly
- [ ] Dependencies up to date

## Development Scenarios

### New Feature Development

**Before Starting**:
```bash
# Understand existing code structure
mcp filesystem-nadia directory_tree --path "api/"

# Check current test coverage
mcp filesystem-nadia search_files --pattern "test|spec" --path "tests/"

# Review similar features
mcp git-nadia search_commits --query "feature.*user.*management"
```

**During Development**:
```bash
# Monitor performance impact
mcp performance-nadia analyze_system_performance --baseline

# Test database migrations
mcp postgres-nadia query --sql "\d user_current_status"

# Validate Redis operations
mcp redis-nadia get_memory_info
```

**Before Merging**:
```bash
# Run security scan
mcp security-nadia scan_project

# Check for performance regression
mcp performance-nadia compare_metrics --baseline "main"

# Validate health checks pass
mcp health-nadia run_comprehensive_check
```

### Production Issue Response

**Immediate Actions**:
```bash
# Step 1: System health overview
mcp health-nadia check_critical_services

# Step 2: Check error rates
mcp postgres-nadia query --sql "
  SELECT COUNT(*), error_type, MAX(created_at) 
  FROM error_logs 
  WHERE created_at > NOW() - INTERVAL '1 hour' 
  GROUP BY error_type"

# Step 3: Redis queue status
mcp redis-nadia analyze_queue_health --detailed

# Step 4: Resource utilization
mcp performance-nadia get_current_metrics
```

**Root Cause Analysis**:
```bash
# Historical comparison
mcp git-nadia get_commit_history --since "2 hours ago"

# Configuration changes
mcp filesystem-nadia get_file_info --path ".env"

# Database state changes
mcp postgres-nadia query --sql "
  SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del 
  FROM pg_stat_user_tables 
  WHERE n_tup_ins + n_tup_upd + n_tup_del > 1000"
```

## Tool Orchestration

### Combined Tool Usage Examples

#### Example 1: Full System Audit
```bash
#!/bin/bash
# system_audit.sh

echo "=== System Health Check ==="
mcp health-nadia check_system_health

echo "=== Performance Metrics ==="
mcp performance-nadia analyze_system_performance

echo "=== Security Scan ==="
mcp security-nadia scan_project --comprehensive

echo "=== Database Health ==="
mcp postgres-nadia query --sql "
  SELECT current_database(), pg_size_pretty(pg_database_size(current_database()))"

echo "=== Redis Status ==="
mcp redis-nadia get_memory_info
```

#### Example 2: Debug User Issue
```bash
#!/bin/bash
# debug_user.sh

USER_ID=$1

echo "=== User Database Record ==="
mcp postgres-nadia query --sql "
  SELECT * FROM user_current_status WHERE user_id = '$USER_ID'"

echo "=== User Redis Data ==="
mcp redis-nadia get_user_history --user_id "$USER_ID"

echo "=== Recent User Interactions ==="
mcp postgres-nadia query --sql "
  SELECT * FROM conversations 
  WHERE user_id = '$USER_ID' 
  ORDER BY created_at DESC 
  LIMIT 10"
```

### Automation Scripts

Create helper scripts for common operations:

```bash
# mcp-helpers/quick-debug.sh
#!/bin/bash

case "$1" in
  "slow-api")
    mcp performance-nadia check_api_latency
    mcp postgres-nadia query --sql "SELECT * FROM pg_stat_activity WHERE state = 'active'"
    ;;
  "user-error")
    mcp filesystem-nadia search_files --pattern "user_id.*undefined|null.*user" --path "logs/"
    mcp redis-nadia analyze_queue_health
    ;;
  "memory-leak")
    mcp performance-nadia get_process_analysis
    mcp redis-nadia get_memory_info --detailed
    ;;
esac
```

## Best Practices

### Efficiency Tips

1. **Batch Operations**
   ```bash
   # Instead of multiple queries
   mcp postgres-nadia query --sql "
     WITH stats AS (
       SELECT COUNT(*) as total_users FROM user_current_status
     ), active AS (
       SELECT COUNT(*) as active FROM conversations WHERE created_at > NOW() - INTERVAL '1 day'
     )
     SELECT * FROM stats, active"
   ```

2. **Use Specific Searches**
   ```bash
   # Good: Specific pattern and path
   mcp filesystem-nadia search_files --pattern "RedisConnectionMixin" --path "utils/"
   
   # Avoid: Broad searches
   mcp filesystem-nadia search_files --pattern "redis"
   ```

3. **Cache Frequent Queries**
   ```bash
   # Save baseline metrics
   mcp performance-nadia analyze_system_performance > baseline.json
   
   # Compare later
   mcp performance-nadia analyze_system_performance | diff baseline.json -
   ```

### Team Collaboration

1. **Document Debugging Sessions**
   ```bash
   # Create investigation report
   echo "# Debug Session $(date)" > debug_reports/issue_123.md
   mcp health-nadia check_system_health >> debug_reports/issue_123.md
   ```

2. **Share MCP Commands**
   ```bash
   # Add to team runbook
   echo "mcp postgres-nadia query --sql 'YOUR_QUERY'" >> team_runbook.md
   ```

3. **Create Team Dashboards**
   ```bash
   # Regular health check script
   #!/bin/bash
   mcp health-nadia check_critical_services | tee -a daily_health.log
   mcp performance-nadia get_current_metrics | tee -a daily_metrics.log
   ```

## Quick Start Scenarios

### "I need to debug a slow API endpoint"
```bash
mcp performance-nadia check_api_latency --endpoint "/api/messages/review"
mcp postgres-nadia query --sql "EXPLAIN ANALYZE SELECT * FROM conversations WHERE status = 'pending'"
mcp redis-nadia analyze_queue_health
```

### "I want to find all database queries affecting user_current_status"
```bash
mcp filesystem-nadia search_files --pattern "user_current_status" --path "database/"
mcp git-nadia search_commits --query "user_current_status"
mcp postgres-nadia query --sql "\d user_current_status"
```

### "I need to verify no secrets are exposed before committing"
```bash
mcp security-nadia scan_environment_files
mcp security-nadia detect_api_keys
mcp git-nadia get_uncommitted_changes | grep -i "api_key\|secret\|password"
```

### "I want to understand how message flow works"
```bash
# Trace message flow
mcp filesystem-nadia search_files --pattern "handle_message|process_message" --path "agents/"
mcp postgres-nadia query --sql "SELECT DISTINCT status FROM conversations"
mcp redis-nadia analyze_queue_health --show-flow
```

## Integration with Development Tools

### VS Code Integration
```json
{
  "tasks": [
    {
      "label": "MCP: Check System Health",
      "type": "shell",
      "command": "mcp health-nadia check_system_health"
    },
    {
      "label": "MCP: Security Scan",
      "type": "shell",
      "command": "mcp security-nadia scan_project"
    }
  ]
}
```

### Git Hooks
```bash
# .git/hooks/pre-commit
#!/bin/bash
mcp security-nadia scan_environment_files || exit 1
mcp security-nadia detect_api_keys || exit 1
```

### Makefile Integration
```makefile
.PHONY: mcp-health mcp-security mcp-perf

mcp-health:
	@mcp health-nadia check_system_health

mcp-security:
	@mcp security-nadia scan_project

mcp-perf:
	@mcp performance-nadia analyze_system_performance

mcp-all: mcp-health mcp-security mcp-perf
```

## Conclusion

The MCP system transforms debugging from multi-step investigations to single-command solutions. By integrating these workflows into your daily development practice, you can:

- Reduce debugging time by 95%
- Catch security issues before deployment
- Optimize performance proactively
- Maintain system health continuously

Remember: MCP tools are most powerful when used in combination. Start with health checks, dive deep with specific tools, and automate repetitive workflows.

---

**Next Steps**:
1. Try the quick start scenarios
2. Create your own helper scripts
3. Share useful commands with the team
4. Contribute new workflows to this guide

For more information, see:
- [MCP Usage Guidelines](./MCP_USAGE_GUIDELINES.md)
- [MCP Security](./MCP_SECURITY.md)
- [MCP Troubleshooting](./MCP_TROUBLESHOOTING.md)
- [MCP Quick Reference](./MCP_QUICK_REFERENCE.md)