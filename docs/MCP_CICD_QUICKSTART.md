# MCP CI/CD Quick Start Guide

> **Goal**: Get MCP integrated into your CI/CD pipeline in 15 minutes

## 🚀 Quick Setup (5 minutes)

### **1. Copy Workflow Files**
```bash
# Copy GitHub Actions workflows
cp .github/workflows/mcp-security-gate.yml .github/workflows/
cp .github/workflows/mcp-deployment-validation.yml .github/workflows/

# Make scripts executable
chmod +x scripts/mcp-workflow.sh
chmod +x scripts/deployment-health-check.sh
```

### **2. Set Repository Secrets**
In GitHub → Settings → Secrets:
- `SLACK_WEBHOOK` (optional) - For notifications
- `API_KEY` (optional) - For authenticated API tests

### **3. Test Locally**
```bash
# Test security checks
make mcp-ci-security

# Test health checks  
make mcp-ci-health

# Test full pipeline
make ci-full-pipeline
```

## 🔒 Security Gate (Essential)

The security gate **blocks** commits with security issues:

### **What it checks:**
- ✅ MCP security scan
- ✅ Hardcoded secrets detection
- ✅ Vulnerable dependencies
- ✅ Static security analysis

### **When it runs:**
- Every push to `main`/`develop`
- Every pull request

### **Result:**
- ❌ **BLOCKS** merge if security issues found
- ✅ **ALLOWS** merge if all checks pass

## 📊 Deployment Validation (Recommended)

Validates deployments automatically:

### **What it validates:**
- ✅ API health and responsiveness
- ✅ Database connectivity
- ✅ Redis operations
- ✅ Performance baselines
- ✅ Integration tests

### **When it runs:**
- After security gate passes
- On `main` and `develop` branches

## 🛠️ Platform-Specific Setup

### **GitHub Actions** (Ready to use)
Files already provided:
- `.github/workflows/mcp-security-gate.yml`
- `.github/workflows/mcp-deployment-validation.yml`

### **GitLab CI**
Add to `.gitlab-ci.yml`:
```yaml
include:
  - local: 'docs/MCP_CICD_INTEGRATION.md'  # Copy examples

mcp-security:
  stage: security
  script:
    - make mcp-ci-security
```

### **Jenkins**
Copy `Jenkinsfile` example from [MCP CI/CD Integration Guide](./MCP_CICD_INTEGRATION.md)

## 🔧 Essential Commands

### **Development**
```bash
# Pre-commit checks
make mcp-pre-commit

# Install git hooks
make mcp-setup-git-hooks

# Full CI validation locally
make mcp-ci-full
```

### **CI Pipeline**
```bash
# Security gate (blocks on failure)
make ci-security-gate

# Complete pipeline
make ci-full-pipeline

# Deployment validation
make mcp-deployment-validate ENV=staging
```

## ⚡ Quick Fixes

### **Security Check Failing?**
```bash
# See what failed
./scripts/mcp-workflow.sh security-check

# Common fixes:
# 1. Remove hardcoded secrets
# 2. Update .gitignore for .env files
# 3. Fix vulnerable dependencies
```

### **Health Check Failing?**
```bash
# Debug health issues
./scripts/mcp-workflow.sh health-check

# Check services are running:
# 1. Database connection
# 2. Redis connection
# 3. API server status
```

### **Pipeline Too Slow?**
```bash
# Skip non-essential checks in CI
export MCP_CI_FAST_MODE=true
make mcp-ci-security  # Only critical checks
```

## 📋 Checklist

Copy this checklist for your team:

### **Initial Setup**
- [ ] Copy workflow files to `.github/workflows/`
- [ ] Set repository secrets (`SLACK_WEBHOOK`, `API_KEY`)
- [ ] Test locally with `make mcp-ci-full`
- [ ] Create test PR to verify security gate works

### **Team Onboarding**
- [ ] Install git hooks: `make mcp-setup-git-hooks`
- [ ] Run pre-commit checks: `make mcp-pre-commit`
- [ ] Test deployment validation locally
- [ ] Configure alert notifications

### **Production Ready**
- [ ] Security gate blocks merges ✅
- [ ] Deployment validation runs on releases ✅
- [ ] Alerts configured for failures ✅
- [ ] Team trained on MCP commands ✅

## 🎯 Success Criteria

Your CI/CD integration is working when:

1. **Security Gate**: PRs blocked if security issues detected
2. **Fast Feedback**: Developers get results in < 5 minutes  
3. **Deployment Safety**: Deployments validated automatically
4. **Alert Coverage**: Team notified of failures immediately

## 🆘 Troubleshooting

### **"MCP command not found"**
```bash
chmod +x scripts/mcp-workflow.sh
export PYTHONPATH=$PWD
```

### **"Security check always fails"**
```bash
# Check for common issues
grep -r "api_key\|secret" --include="*.py" .
find . -name ".env" -not -path "./.git/*"
```

### **"Health check fails in CI"**
```bash
# Ensure services are available
# Check docker-compose.yml or CI services config
# Verify DATABASE_URL and REDIS_URL are set
```

### **"Workflows not triggering"**
```bash
# Check workflow files are in .github/workflows/
# Verify YAML syntax is valid
# Check branch protection rules
```

## 📚 Next Steps

Once basic integration works:

1. **Advanced Security**: Configure dependency scanning
2. **Performance Monitoring**: Set up performance regression detection  
3. **Custom Alerts**: Add Slack/Discord notifications
4. **Blue-Green Deployment**: Implement automated deployment validation

## 🔗 Related Documentation

- [Complete CI/CD Integration Guide](./MCP_CICD_INTEGRATION.md)
- [MCP Developer Workflow Guide](./MCP_DEVELOPER_WORKFLOW.md)
- [MCP Alerts Setup Guide](./MCP_ALERTS_GUIDE.md)

---

**Need Help?** 
- Check the [MCP Troubleshooting Guide](./MCP_TROUBLESHOOTING.md)
- Run `make mcp-workflow` for available commands
- Test locally before pushing: `make mcp-ci-full`