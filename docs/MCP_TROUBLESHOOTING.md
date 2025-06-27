# MCP Troubleshooting Guide

**Document Version**: 1.0  
**Last Updated**: December 27, 2025  
**Related**: [GitHub Issue #45](https://github.com/RobeHGC/chatbot_nadia/issues/45)

## 📋 Overview

This document provides comprehensive troubleshooting procedures for the Model Context Protocol (MCP) debugging system in the NADIA project. Use this guide to diagnose and resolve common MCP-related issues.

## 🚨 Quick Diagnostic Commands

Before diving into specific issues, run these quick diagnostic commands:

```bash
# Check MCP server installation status
npm list @modelcontextprotocol/server-postgres @modelcontextprotocol/server-filesystem
pip list | grep mcp-server-git

# Verify Claude settings configuration
cat ~/.claude/settings.local.json | jq '.mcpServers'

# Test database connection
psql postgresql://localhost/nadia_hitl -c "SELECT version();"

# Check Redis connection
redis-cli ping

# Verify filesystem permissions
ls -la /home/rober/projects/chatbot_nadia/.claude/
```

## 🔧 Common Issues and Solutions

### 1. **MCP Server Not Available**

#### **Symptoms**
- Error: "MCP server not found"
- Function calls to `mcp__*` return "not available"
- Claude reports MCP tools are not accessible

#### **Diagnostic Steps**
```bash
# Check if MCP servers are installed
npm list @modelcontextprotocol/server-postgres
npm list @modelcontextprotocol/server-filesystem
pip show mcp-server-git

# Check if servers are running (if applicable)
ps aux | grep mcp

# Verify Claude configuration
cat ~/.claude/settings.local.json
```

#### **Solutions**

**Solution 1: Reinstall MCP Servers**
```bash
# PostgreSQL MCP Server
npm install @modelcontextprotocol/server-postgres@0.6.2

# Filesystem MCP Server  
npm install @modelcontextprotocol/server-filesystem@2025.3.28

# Git MCP Server (Python)
cd mcp-servers-temp/src/git
pip install -e .
```

**Solution 2: Fix Claude Configuration**
```json
// ~/.claude/settings.local.json
{
  "mcpServers": {
    "postgres-nadia": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-postgres", "postgresql:///nadia_hitl"]
    },
    "filesystem-nadia": {
      "command": "npx", 
      "args": ["@modelcontextprotocol/server-filesystem", "/home/rober/projects/chatbot_nadia"]
    },
    "git-nadia": {
      "command": "python",
      "args": ["-m", "mcp_server_git", "--repository", "/home/rober/projects/chatbot_nadia"]
    }
  }
}
```

### 2. **Database Connection Issues**

#### **Symptoms**
- Error: "connection to server failed"
- `mcp__postgres-nadia__query` returns connection errors
- PostgreSQL permission errors

#### **Diagnostic Steps**
```bash
# Test direct database connection
psql postgresql://localhost/nadia_hitl -c "SELECT 1;"

# Check if PostgreSQL is running
systemctl status postgresql
# or
brew services list | grep postgres

# Verify database exists
psql -U postgres -l | grep nadia_hitl

# Check connection parameters
echo $DATABASE_URL
```

#### **Solutions**

**Solution 1: Start PostgreSQL Service**
```bash
# Linux/systemd
sudo systemctl start postgresql
sudo systemctl enable postgresql

# macOS with Homebrew
brew services start postgresql@14

# Docker
docker run -d --name postgres -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:14
```

**Solution 2: Create Database**
```bash
# Connect as superuser and create database
psql -U postgres -c "CREATE DATABASE nadia_hitl;"

# Run migrations
cd /home/rober/projects/chatbot_nadia
python scripts/migrate.py
```

**Solution 3: Fix Connection String**
```bash
# Set correct DATABASE_URL
export DATABASE_URL="postgresql://username:password@localhost:5432/nadia_hitl"

# Or update .env file
echo "DATABASE_URL=postgresql://localhost/nadia_hitl" >> .env
```

### 3. **File Access Permission Errors**

#### **Symptoms**
- Error: "Permission denied" when reading files
- `mcp__filesystem-nadia__read_file` fails
- Access denied to project directories

#### **Diagnostic Steps**
```bash
# Check file permissions
ls -la /home/rober/projects/chatbot_nadia/

# Verify user ownership
whoami
id

# Check specific file permissions
ls -la /home/rober/projects/chatbot_nadia/.env

# Test file read access
cat /home/rober/projects/chatbot_nadia/README.md | head -5
```

#### **Solutions**

**Solution 1: Fix File Permissions**
```bash
# Fix project directory permissions
chmod -R 755 /home/rober/projects/chatbot_nadia/

# Fix specific file permissions
chmod 644 /home/rober/projects/chatbot_nadia/.env.example

# Change ownership if needed
sudo chown -R $(whoami):$(whoami) /home/rober/projects/chatbot_nadia/
```

**Solution 2: Update MCP Configuration**
```json
// Ensure correct path in ~/.claude/settings.local.json
{
  "mcpServers": {
    "filesystem-nadia": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "/home/rober/projects/chatbot_nadia"]
    }
  }
}
```

### 4. **Git Repository Access Issues**

#### **Symptoms**
- Git MCP commands fail
- "Not a git repository" errors
- Git blame/log commands return empty results

#### **Diagnostic Steps**
```bash
# Verify git repository
cd /home/rober/projects/chatbot_nadia
git status

# Check git configuration
git config --list

# Test git commands manually
git log --oneline -5
git blame README.md | head -5
```

#### **Solutions**

**Solution 1: Initialize/Fix Git Repository**
```bash
cd /home/rober/projects/chatbot_nadia

# If not a git repo, initialize
git init
git remote add origin https://github.com/RobeHGC/chatbot_nadia.git
git fetch origin
git checkout main

# If corrupted, fix
git fsck --full
git gc --aggressive --prune=now
```

**Solution 2: Configure Git MCP Server**
```bash
# Reinstall git MCP server
cd mcp-servers-temp/src/git
pip install -e .

# Test git MCP server directly
python -m mcp_server_git --repository /home/rober/projects/chatbot_nadia
```

### 5. **Performance Issues**

#### **Symptoms**
- MCP operations taking too long
- Database queries timing out
- File operations extremely slow

#### **Diagnostic Steps**
```bash
# Check system resources
top
htop
df -h

# Monitor database performance
# In psql:
SELECT * FROM pg_stat_activity WHERE state = 'active';

# Check for large files
find /home/rober/projects/chatbot_nadia -type f -size +10M

# Monitor Redis performance
redis-cli info memory
```

#### **Solutions**

**Solution 1: Optimize Database Queries**
```sql
-- Enable query logging for analysis
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();

-- Add missing indexes
CREATE INDEX CONCURRENTLY idx_messages_created_at ON messages(created_at);
CREATE INDEX CONCURRENTLY idx_recovery_requests_status ON recovery_requests(status);

-- Update table statistics
ANALYZE;
```

**Solution 2: Clean Up Large Files**
```bash
# Clean up logs
find logs/ -name "*.log" -mtime +7 -delete

# Clean up temporary files
find /tmp -name "*nadia*" -mtime +1 -delete

# Clean up old backups
find backups/ -name "*.sql.gz" -mtime +30 -delete
```

**Solution 3: Tune MCP Configuration**
```json
// Add timeout and performance settings
{
  "mcpServers": {
    "postgres-nadia": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-postgres", "postgresql:///nadia_hitl"],
      "timeout": 30000
    }
  }
}
```

### 6. **UI Testing (Puppeteer) Issues**

#### **Symptoms**
- Puppeteer MCP operations fail
- Browser automation errors
- Screenshot capture failures

#### **Diagnostic Steps**
```bash
# Check if Chrome/Chromium is installed
google-chrome --version
# or
chromium --version

# Test Puppeteer installation
npm list puppeteer

# Check dashboard accessibility
curl -I http://localhost:3000

# Verify test environment
cd tests/ui
python -c "import pytest; print('Pytest available')"
```

#### **Solutions**

**Solution 1: Install Browser Dependencies**
```bash
# Install Chrome (Ubuntu/Debian)
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install google-chrome-stable

# Install Puppeteer dependencies
npm install puppeteer
npx puppeteer browsers install chrome
```

**Solution 2: Fix Dashboard Service**
```bash
# Start dashboard service
cd /home/rober/projects/chatbot_nadia
python dashboard/backend/static_server.py &

# Verify dashboard is running
curl http://localhost:3000

# Check logs for errors
tail -f logs/dashboard.log
```

## 🔍 Advanced Diagnostics

### **Complete System Health Check**

```bash
#!/bin/bash
# MCP System Health Check Script

echo "=== MCP System Health Check ==="

# Check MCP server installations
echo "1. Checking MCP Server Installations..."
npm list @modelcontextprotocol/server-postgres @modelcontextprotocol/server-filesystem 2>/dev/null
pip show mcp-server-git 2>/dev/null

# Check Claude configuration
echo "2. Checking Claude Configuration..."
if [ -f ~/.claude/settings.local.json ]; then
    echo "✓ Claude settings file exists"
    jq '.mcpServers | keys' ~/.claude/settings.local.json 2>/dev/null
else
    echo "✗ Claude settings file missing"
fi

# Check database connection
echo "3. Testing Database Connection..."
if psql postgresql://localhost/nadia_hitl -c "SELECT 1;" &>/dev/null; then
    echo "✓ Database connection successful"
else
    echo "✗ Database connection failed"
fi

# Check filesystem access
echo "4. Testing Filesystem Access..."
if [ -r /home/rober/projects/chatbot_nadia/README.md ]; then
    echo "✓ Filesystem access successful"
else
    echo "✗ Filesystem access failed"
fi

# Check git repository
echo "5. Testing Git Repository..."
cd /home/rober/projects/chatbot_nadia
if git status &>/dev/null; then
    echo "✓ Git repository accessible"
else
    echo "✗ Git repository issues"
fi

echo "=== Health Check Complete ==="
```

### **Performance Monitoring**

```bash
#!/bin/bash
# Monitor MCP Performance

echo "=== MCP Performance Monitor ==="

# Database query performance
echo "Top 5 slowest queries:"
psql postgresql://localhost/nadia_hitl -c "
SELECT query, mean_time, calls, total_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 5;"

# File system performance
echo "Largest files in project:"
find /home/rober/projects/chatbot_nadia -type f -exec ls -lh {} + | sort -k5 -hr | head -10

# Memory usage
echo "System memory usage:"
free -h

echo "=== Performance Monitor Complete ==="
```

## 🛡️ Security Troubleshooting

### **Security Checklist**

```bash
#!/bin/bash
# MCP Security Audit

echo "=== MCP Security Audit ==="

# Check file permissions
echo "1. File Permissions Audit..."
find /home/rober/projects/chatbot_nadia -name "*.env*" -exec ls -la {} \;
find /home/rober/projects/chatbot_nadia -name "*key*" -exec ls -la {} \;

# Check for exposed secrets
echo "2. Secret Exposure Check..."
grep -r "API_KEY\|SECRET\|PASSWORD" /home/rober/projects/chatbot_nadia --exclude-dir=node_modules --exclude="*.md" | head -5

# Check database permissions
echo "3. Database Permissions..."
psql postgresql://localhost/nadia_hitl -c "\du"

# Check MCP configuration security
echo "4. MCP Configuration Security..."
if [ -f ~/.claude/settings.local.json ]; then
    echo "Claude settings permissions:"
    ls -la ~/.claude/settings.local.json
fi

echo "=== Security Audit Complete ==="
```

## 📞 Escalation Procedures

### **When to Escalate**

- **Data Loss Risk**: If MCP operations might cause data loss
- **Security Breach**: If secrets or credentials are exposed
- **Production Impact**: If issues affect production systems
- **Persistent Failures**: If troubleshooting steps don't resolve issues after 30 minutes

### **Escalation Steps**

1. **Document the Issue**
   ```bash
   # Create issue report
   echo "MCP Issue Report - $(date)" > /tmp/mcp-issue-report.txt
   echo "Symptoms: [describe symptoms]" >> /tmp/mcp-issue-report.txt
   echo "Steps Taken: [list troubleshooting steps]" >> /tmp/mcp-issue-report.txt
   echo "System State:" >> /tmp/mcp-issue-report.txt
   # Run health check script
   ./health-check.sh >> /tmp/mcp-issue-report.txt
   ```

2. **Create GitHub Issue**
   ```bash
   gh issue create --title "MCP System Issue: [Brief Description]" \
     --body-file /tmp/mcp-issue-report.txt \
     --label "mcp,bug,priority-high"
   ```

3. **Notify Team**
   - Alert development team through established channels
   - Include issue link and severity assessment
   - Provide immediate workaround if available

### **Emergency Procedures**

#### **Immediate System Recovery**
```bash
# Stop all MCP-related processes
pkill -f mcp-server
pkill -f postgres

# Restart essential services
sudo systemctl restart postgresql
sudo systemctl restart redis

# Clear MCP cache/state
rm -rf ~/.claude/mcp-cache/
rm -rf /tmp/mcp-*

# Restart with minimal configuration
cp ~/.claude/settings.local.json ~/.claude/settings.local.json.backup
echo '{"mcpServers": {}}' > ~/.claude/settings.local.json
```

#### **Rollback Procedures**
```bash
# Restore previous configuration
cp ~/.claude/settings.local.json.backup ~/.claude/settings.local.json

# Restore database if needed
psql postgresql://localhost/nadia_hitl < backups/latest_backup.sql

# Verify system integrity
python scripts/verify_system_integrity.py
```

## 📚 Additional Resources

- **MCP Official Documentation**: [Model Context Protocol](https://modelcontextprotocol.io/)
- **Technical Setup Guide**: `checkpoints/SESSION_DEC26_2025_MCP_DEBUGGING_SETUP.md`
- **Usage Guidelines**: `docs/MCP_USAGE_GUIDELINES.md`
- **Project Architecture**: `docs/ARCHITECTURE.md`
- **Security Guidelines**: `SECURITY.md`

## 🔄 Regular Maintenance

### **Daily Checks**
- Verify MCP server availability
- Check database connection health
- Monitor filesystem access permissions
- Review error logs for MCP-related issues

### **Weekly Maintenance**
- Update MCP server packages
- Clean up temporary files and logs
- Review and optimize slow database queries
- Update security configurations

### **Monthly Reviews**
- Full security audit of MCP access
- Performance optimization review
- Documentation updates
- Team training on new MCP features

---

**Need Immediate Help?**
1. Run the health check script: `./scripts/mcp-health-check.sh`
2. Check recent logs: `tail -f logs/api.log | grep -i mcp`
3. Create GitHub issue with `mcp` and `urgent` labels
4. Follow escalation procedures above

**Document Last Updated**: December 27, 2025  
**Next Review Date**: January 27, 2026