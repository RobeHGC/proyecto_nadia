# MCP Integration Guide

> **Quick Start**: How to integrate MCP tools into your NADIA development workflow

## 1. Command Line Integration

### Using the MCP Workflow Script
```bash
# Make it available globally (optional)
sudo ln -s $(pwd)/scripts/mcp-workflow.sh /usr/local/bin/mcp-nadia

# Common commands
mcp-nadia health-check              # Full system health
mcp-nadia debug-user 12345         # Debug specific user
mcp-nadia slow-api /api/messages   # Investigate slow endpoint
mcp-nadia security-check           # Pre-commit security scan
```

### Using Make Commands
```bash
make mcp-help                      # Show all MCP commands
make mcp-health                    # Run health checks
make mcp-security                  # Run security scan
make mcp-debug USER=12345          # Debug user
make mcp-slow-api ENDPOINT=/api/messages
make mcp-error PATTERN="undefined"
```

## 2. VS Code Integration

### Running MCP Tasks
1. Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
2. Type "Tasks: Run Task"
3. Select from MCP tasks:
   - MCP: System Health Check
   - MCP: Security Scan
   - MCP: Debug User
   - MCP: Find Error Pattern

### Keyboard Shortcuts (add to keybindings.json)
```json
[
  {
    "key": "ctrl+shift+h",
    "command": "workbench.action.tasks.runTask",
    "args": "MCP: System Health Check"
  },
  {
    "key": "ctrl+shift+s",
    "command": "workbench.action.tasks.runTask",
    "args": "MCP: Security Scan"
  }
]
```

## 3. Git Hooks Integration

### Install Pre-commit Hook
```bash
# Install the security pre-commit hook
cp scripts/git-hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# Test it
git add .
git commit -m "test" # Will run security checks
```

### Custom Hooks
Create your own hooks in `.git/hooks/`:
```bash
# .git/hooks/pre-push
#!/bin/bash
./scripts/mcp-workflow.sh health-check || exit 1
./scripts/mcp-workflow.sh security-check || exit 1
```

## 4. Daily Workflow Examples

### Morning Routine
```bash
# Start your day
make mcp-health                    # Check system health
make mcp-perf                      # Create performance baseline
git pull origin main               # Get latest changes
```

### Before Starting New Feature
```bash
# Understand existing code
mcp-nadia recent-changes api/      # See what changed recently
make mcp-health                    # Ensure system is healthy
make test-unit                     # Run quick tests
```

### Debugging Production Issue
```bash
# Quick diagnosis
make mcp-health                    # Overall health
mcp-nadia debug-user $USER_ID      # User-specific issues
mcp-nadia slow-api $ENDPOINT       # Performance issues
mcp-nadia find-error "$ERROR"      # Error patterns
```

### Before Committing
```bash
# Automated by pre-commit hook, or run manually
make mcp-security                  # Security scan
make lint                          # Code quality
make test-unit                     # Quick tests
```

## 5. Team Collaboration

### Sharing Debug Sessions
```bash
# Save debug session
mcp-nadia debug-user 12345 > debug_reports/user_12345_$(date +%Y%m%d).txt

# Share in PR description
cat debug_reports/user_12345_*.txt
```

### Creating Team Dashboards
```bash
# Create daily report
cat > daily_mcp_check.sh << 'EOF'
#!/bin/bash
echo "# Daily MCP Report - $(date)" > daily_report.md
echo "## System Health" >> daily_report.md
make mcp-health >> daily_report.md
echo "## Performance Metrics" >> daily_report.md
make mcp-perf >> daily_report.md
EOF

# Schedule with cron
crontab -e
# Add: 0 9 * * * /path/to/daily_mcp_check.sh
```

## 6. CI/CD Integration

### GitHub Actions Example
```yaml
name: MCP Checks
on: [push, pull_request]

jobs:
  mcp-checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run MCP Security Check
        run: ./scripts/mcp-workflow.sh security-check
        
      - name: Run MCP Health Check
        run: ./scripts/mcp-workflow.sh health-check
        
      - name: Upload Performance Baseline
        if: github.ref == 'refs/heads/main'
        run: |
          ./scripts/mcp-workflow.sh perf-baseline
          # Upload to artifact storage
```

### Jenkins Pipeline
```groovy
pipeline {
    agent any
    stages {
        stage('MCP Security') {
            steps {
                sh './scripts/mcp-workflow.sh security-check'
            }
        }
        stage('MCP Health') {
            steps {
                sh './scripts/mcp-workflow.sh health-check'
            }
        }
    }
}
```

## 7. Troubleshooting

### Common Issues

**MCP command not found**
```bash
# Check if script exists
ls -la scripts/mcp-workflow.sh

# Make executable
chmod +x scripts/mcp-workflow.sh

# Add to PATH
export PATH=$PATH:$(pwd)/scripts
```

**Permission denied**
```bash
# Check MCP server permissions
ls -la mcp-servers-temp/src/

# Fix permissions
chmod +x mcp-servers-temp/src/*/index.js
```

**No MCP server response**
```bash
# Check if MCP servers are configured
cat ~/.mcp/servers.json

# Restart MCP servers
# (Depends on your MCP setup)
```

## 8. Best Practices

1. **Use MCP Early and Often**
   - Run health checks at start of day
   - Create baselines before major changes
   - Use security checks before every commit

2. **Combine Tools**
   - Use multiple MCP servers together
   - Chain commands for comprehensive analysis
   - Create custom workflows for your needs

3. **Document Findings**
   - Save important debug sessions
   - Share useful commands with team
   - Update this guide with new patterns

4. **Automate Repetitive Tasks**
   - Create aliases for common commands
   - Use git hooks for automatic checks
   - Schedule regular health monitoring

## Quick Reference Card

```bash
# Essential Commands
make mcp-health                    # System health
make mcp-security                  # Security scan
make mcp-debug USER=xxx            # Debug user
make mcp-slow-api ENDPOINT=xxx     # API performance
make mcp-error PATTERN=xxx         # Find errors

# Workflow Script
./scripts/mcp-workflow.sh help     # Show all options
./scripts/mcp-workflow.sh health-check
./scripts/mcp-workflow.sh security-check
./scripts/mcp-workflow.sh debug-user <id>
./scripts/mcp-workflow.sh slow-api <endpoint>
./scripts/mcp-workflow.sh find-error <pattern>

# VS Code
Cmd+Shift+P → "Tasks: Run Task" → Select MCP task

# Git Integration
cp scripts/git-hooks/pre-commit .git/hooks/
```

---

For detailed information about each MCP server and advanced usage, see:
- [MCP Developer Workflow Guide](./MCP_DEVELOPER_WORKFLOW.md)
- [MCP Usage Guidelines](./MCP_USAGE_GUIDELINES.md)