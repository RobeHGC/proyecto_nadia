# 🔒 Security Guidelines for NADIA Project

## Critical Security Notice

This project contains sensitive credentials and user data. **NEVER commit sensitive files to Git**.

## Protected Files

### 🚫 NEVER Commit These Files
- `.env` - Production credentials
- `.env.testing` - Test credentials  
- `*.session` - Telegram session files
- `*.log` - Log files may contain sensitive data
- `backups/*.sql` - Database backups
- `*.key`, `*.pem` - Private keys
- User data CSV files

### ✅ Safe to Commit
- `.env.example` - Template with dummy values
- `.env.testing.example` - Test template
- Code files (`.py`, `.js`) without hardcoded credentials
- Documentation files

## Environment Setup

1. **Copy example files**:
   ```bash
   cp .env.example .env
   cp .env.testing.example .env.testing
   ```

2. **Fill with real credentials** (never commit these):
   - Telegram API credentials
   - OpenAI/Anthropic/Gemini API keys
   - Database connection strings
   - Dashboard API keys

## Git Protection Status

- ✅ `.gitignore` configured to exclude sensitive files
- ✅ `bot_session.session` marked as `--assume-unchanged`
- ✅ Environment files protected

## Security Measures Implemented

### Pre-commit Protection
```bash
# Check for credentials before committing
grep -r "sk-" . --exclude-dir=.git --exclude="*.example" --exclude="SECURITY.md"
```

### Credential Rotation Policy
- **Rotate API keys every 90 days**
- **Rotate after any suspected exposure**
- **Use different keys for development/production**

### Data Protection
- User conversations stored with encryption
- Database backups excluded from Git
- Session files protected with file permissions

## Emergency Response

### If Credentials Are Exposed
1. **Immediately rotate all API keys**
2. **Remove from Git history**:
   ```bash
   git filter-branch --force --index-filter \
     'git rm --cached --ignore-unmatch .env .env.testing *.session' \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. **Force push to clean remote**:
   ```bash
   git push origin --force --all
   ```
4. **Audit logs for unauthorized access**

### User Data Incident
1. **Stop all services immediately**
2. **Assess data exposure scope**
3. **Notify affected users if required**
4. **Implement additional protections**

## Compliance Notes

- **GDPR**: User data anonymization required
- **SOC 2**: Access controls documented
- **API Terms**: Follow rate limits and usage policies

## Regular Security Tasks

### Weekly
- [ ] Review access logs
- [ ] Check for new sensitive files
- [ ] Verify backup encryption

### Monthly  
- [ ] Audit user permissions
- [ ] Review API key usage
- [ ] Update security documentation

### Quarterly
- [ ] Rotate API credentials
- [ ] Security penetration testing
- [ ] Review incident response plan

---

⚠️ **Remember**: Security is everyone's responsibility. When in doubt, ask before committing!