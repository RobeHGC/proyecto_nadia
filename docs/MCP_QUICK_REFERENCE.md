# MCP Quick Reference Guide

**Version**: 1.0 | **Updated**: Dec 27, 2025 | **Related**: [Issue #45](https://github.com/RobeHGC/chatbot_nadia/issues/45)

## 🚀 Quick Start

```bash
# Health Check
psql postgresql://localhost/nadia_hitl -c "SELECT 1;"  # Database
ls /home/rober/projects/chatbot_nadia/README.md        # Filesystem  
git status                                              # Git

# MCP Configuration Location
~/.claude/settings.local.json
```

## 📊 Available MCP Servers

| Server | Purpose | Functions | Risk Level |
|--------|---------|-----------|------------|
| **postgres-nadia** | Database queries | `query` | Medium |
| **filesystem-nadia** | File operations | `read_file`, `search_files`, `list_directory` | Low |
| **git-nadia** | Repository analysis | Git commands | Low |
| **puppeteer-nadia** | UI testing | Browser automation | High |

## 🗃️ Database Queries (postgres-nadia)

### **Common Patterns**
```sql
-- System Status
SELECT status, COUNT(*) FROM recovery_requests GROUP BY status;
SELECT COUNT(*) FROM messages WHERE created_at > NOW() - INTERVAL '1 hour';

-- User Analytics  
SELECT user_id, COUNT(*) as msg_count FROM messages 
WHERE created_at > CURRENT_DATE GROUP BY user_id LIMIT 10;

-- Performance Analysis
EXPLAIN ANALYZE SELECT * FROM user_current_status WHERE customer_status = 'LEAD_QUALIFIED';

-- Error Investigation
SELECT error_message, COUNT(*) FROM error_logs 
WHERE created_at > NOW() - INTERVAL '24 hours' 
GROUP BY error_message ORDER BY count DESC;
```

### **✅ Safe Queries** 
- `SELECT` with `LIMIT`
- `COUNT()`, `AVG()`, `MAX()`, `MIN()` 
- `EXPLAIN ANALYZE`
- Time-windowed queries

### **❌ Prohibited**
- `INSERT`, `UPDATE`, `DELETE`
- `DROP`, `ALTER`, `CREATE`
- Queries accessing passwords/secrets
- Bulk export operations

## 📁 File Operations (filesystem-nadia)

### **Function Reference**
```bash
# Read specific file
mcp__filesystem-nadia__read_file:
  path: "/home/rober/projects/chatbot_nadia/api/server.py"

# Search for patterns
mcp__filesystem-nadia__search_files:
  path: "/home/rober/projects/chatbot_nadia"
  pattern: "redis"
  excludePatterns: ["node_modules", ".git", "*.log"]

# List directory contents
mcp__filesystem-nadia__list_directory:
  path: "/home/rober/projects/chatbot_nadia/agents"

# Project structure overview
mcp__filesystem-nadia__directory_tree:
  path: "/home/rober/projects/chatbot_nadia"
```

### **✅ Safe Paths**
- `/home/rober/projects/chatbot_nadia/**/*.py`
- `/home/rober/projects/chatbot_nadia/**/*.js`
- `/home/rober/projects/chatbot_nadia/**/*.md`
- `/home/rober/projects/chatbot_nadia/logs/*.log`

### **❌ Restricted**
- `*.env*`, `*.key`, `*.secret`
- `/etc/`, `/var/`, `/proc/`
- `~/.ssh/`, `~/.aws/`
- Production configuration files

## 🔄 Git Operations (git-nadia)

### **Common Commands**
```bash
# Recent history
git log --oneline --graph --decorate -n 20

# Search commits  
git log --grep="MCP" --oneline
git log --author="developer@example.com"

# File investigation
git blame api/server.py
git log --follow -- agents/supervisor_agent.py

# Changes analysis
git diff main..feature-branch
git show commit-hash
git diff --stat HEAD~5..HEAD
```

### **✅ Allowed Operations**
- `git log`, `git show`, `git diff`
- `git blame`, `git grep`
- `git status` (read-only)
- `git branch` (list only)

### **❌ Prohibited**
- `git push`, `git commit`, `git merge`
- `git config --global`
- `git remote add/set-url`
- Any write operations

## 🎭 UI Testing (puppeteer-nadia)

### **Common Patterns**
```javascript
// Screenshot capture
await page.screenshot({
  path: 'tests/ui/screenshots/feature-test.png',
  fullPage: true
});

// Element interaction
await page.click('[data-testid="submit-btn"]');
await page.fill('#input-field', 'test value');
await page.waitForSelector('.success-message');

// Dashboard navigation
await page.goto('http://localhost:3000');
await page.waitForLoadState('networkidle');
```

### **Best Practices**
- Use `data-testid` attributes
- Wait for elements before interaction
- Capture screenshots for verification
- Test in isolated environments only

## 🚨 Quick Troubleshooting

### **MCP Server Not Available**
```bash
# Check installations
npm list @modelcontextprotocol/server-postgres
pip show mcp-server-git

# Restart servers (if needed)
pkill -f mcp-server; # restart Claude
```

### **Database Connection Failed**
```bash
# Test connection
psql postgresql://localhost/nadia_hitl -c "SELECT version();"

# Check service
systemctl status postgresql  # Linux
brew services list | grep postgres  # macOS
```

### **Permission Denied**
```bash
# Check file permissions
ls -la /home/rober/projects/chatbot_nadia/

# Verify Claude config
cat ~/.claude/settings.local.json | jq '.mcpServers'
```

### **Slow Performance**  
```sql
-- Find slow queries
SELECT query, mean_time FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 5;

-- Add LIMIT to large results
SELECT * FROM large_table LIMIT 100;
```

## 📋 Security Checklist

### **Before Each Session**
- [ ] Verify development environment (not production)
- [ ] Check for sensitive files in project scope
- [ ] Confirm read-only operations only
- [ ] Review recent MCP access logs

### **During Operations**
- [ ] Use `LIMIT` clauses in database queries
- [ ] Avoid accessing files with secrets
- [ ] Stay within project directory boundaries
- [ ] Monitor query execution times

### **After Session**
- [ ] Review operations performed
- [ ] Clear any temporary files created
- [ ] Report any security concerns
- [ ] Update documentation if needed

## 🎯 Common Use Cases

### **Bug Investigation**
1. **Database Query**: Check error patterns
   ```sql
   SELECT error_type, COUNT(*) FROM error_logs 
   WHERE created_at > NOW() - INTERVAL '24 hours' 
   GROUP BY error_type;
   ```

2. **File Analysis**: Review relevant code
   ```bash
   mcp__filesystem-nadia__search_files:
     pattern: "error_handling"
     path: "/home/rober/projects/chatbot_nadia"
   ```

3. **Git Investigation**: Find recent changes
   ```bash
   git log --since="24 hours ago" --oneline
   git blame problematic_file.py
   ```

### **Performance Analysis**
1. **Database Performance**
   ```sql
   EXPLAIN ANALYZE SELECT * FROM messages 
   WHERE user_id = 'specific_user' AND created_at > NOW() - INTERVAL '1 hour';
   ```

2. **Resource Usage**
   ```bash
   mcp__filesystem-nadia__search_files:
     pattern: "memory.*usage"
     path: "/home/rober/projects/chatbot_nadia/logs"
   ```

### **Code Review**
1. **File Changes**
   ```bash
   git diff --name-only HEAD~1 HEAD
   ```

2. **Code Analysis**
   ```bash
   mcp__filesystem-nadia__read_file:
     path: "/home/rober/projects/chatbot_nadia/changed_file.py"
   ```

## 🔗 Quick Links

### **Documentation**
- **[Full Usage Guide](MCP_USAGE_GUIDELINES.md)** - Comprehensive usage instructions
- **[Troubleshooting](MCP_TROUBLESHOOTING.md)** - Detailed problem resolution
- **[Security Guide](MCP_SECURITY.md)** - Security policies and procedures

### **Technical References**
- **[MCP Setup](../checkpoints/SESSION_DEC26_2025_MCP_DEBUGGING_SETUP.md)** - Technical implementation
- **[Project Architecture](ARCHITECTURE.md)** - System overview
- **[API Documentation](http://localhost:8000/docs)** - Interactive API docs

### **Support**
- **GitHub Issues**: Use `mcp` label for MCP-related issues
- **Emergency**: Follow escalation procedures in security guide
- **Training**: Contact team lead for MCP training sessions

## ⚡ Performance Tips

### **Database Optimization**
- Always use `LIMIT` for large result sets
- Filter by time ranges: `WHERE created_at > NOW() - INTERVAL '1 hour'`
- Use `EXPLAIN ANALYZE` to understand query performance
- Avoid `SELECT *` on large tables

### **File Operations**
- Use specific paths instead of broad searches
- Include `excludePatterns` for faster searches
- Read only necessary portions of large files
- Cache frequently accessed file contents

### **Git Operations**
- Limit history depth: `git log -n 20`
- Use specific file paths when possible
- Combine related git commands in single analysis

## 📊 Monitoring

### **Key Metrics to Watch**
- Query execution time > 5 seconds
- File operations > 100 per session  
- Large result sets > 10MB
- Failed authentication attempts

### **Daily Health Checks**
```bash
# Quick system verification
psql postgresql://localhost/nadia_hitl -c "SELECT COUNT(*) FROM messages;"
ls /home/rober/projects/chatbot_nadia/README.md >/dev/null && echo "✓ Filesystem OK"
git status >/dev/null && echo "✓ Git OK"
```

---

**💡 Pro Tip**: Bookmark this page for quick reference during debugging sessions!

**🔄 Last Updated**: December 27, 2025 | **Next Review**: January 27, 2026