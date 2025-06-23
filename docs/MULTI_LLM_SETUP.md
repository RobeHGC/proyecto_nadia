# Multi-LLM System Setup Guide

This guide covers the complete setup and verification of NADIA's multi-LLM system that uses Gemini 2.0 Flash for creative generation and GPT-4o-mini for refinement.

## Overview

The multi-LLM architecture provides:
- **Cost Optimization**: Leverage Gemini's free tier for creative generation
- **Quality Enhancement**: Use GPT-4o-mini for refinement and formatting
- **Comprehensive Tracking**: Monitor usage, costs, and performance metrics
- **Quota Management**: Intelligent handling of Gemini API limits

## Prerequisites

1. **API Keys Required**:
   - OpenAI API key (for GPT-4o-mini)
   - Google Gemini API key (for Gemini 2.0 Flash)

2. **Database Migration**:
   - Apply the LLM tracking migration before using the system

3. **Redis Setup**:
   - Required for quota management and caching

## Step 1: Environment Configuration

Create or update your `.env` file with multi-LLM configuration:

```bash
# Existing configuration
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
PHONE_NUMBER=+1234567890
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://user:pass@localhost/nadia_hitl

# Multi-LLM Configuration
OPENAI_API_KEY=sk-...your-openai-key...
GEMINI_API_KEY=AIza...your-gemini-key...

# LLM Provider Settings
LLM1_PROVIDER=gemini
LLM1_MODEL=gemini-2.0-flash-exp
LLM2_PROVIDER=openai
LLM2_MODEL=gpt-4o-mini

# Optional: Dashboard API
DASHBOARD_API_KEY=your-secure-api-key
```

### Getting API Keys

#### OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key (starts with `sk-`)

#### Gemini API Key
1. Go to https://makersuite.google.com/app/apikey
2. Create a new API key
3. Copy the key (starts with `AIza`)

## Step 2: Database Migration

Apply the multi-LLM tracking migration:

```bash
# Navigate to project directory
cd /path/to/chatbot_nadia

# Apply migration
psql -d nadia_hitl -f database/migrations/add_llm_tracking.sql
```

The migration adds these columns to the `interactions` table:
- `llm1_model` - Model used for creative generation
- `llm2_model` - Model used for refinement
- `llm1_cost_usd` - Cost for LLM1 usage
- `llm2_cost_usd` - Cost for LLM2 usage

## Step 3: Install Dependencies

Ensure all required packages are installed:

```bash
pip install -r requirements.txt
```

Key new dependencies:
- `google-generativeai==0.8.3` - Gemini API client
- Enhanced Redis usage for quota management

## Step 4: Verification

Run the verification script to ensure everything is working:

```bash
# Quick verification
python scripts/verify_multi_llm.py

# Comprehensive integration tests
pytest tests/test_multi_llm_integration.py -v
```

The verification script will check:
- ✅ API key configuration
- ✅ LLM client initialization
- ✅ Quota manager functionality
- ✅ End-to-end message processing
- ✅ Cost calculation accuracy
- ✅ Database integration

## Step 5: Run the System

Start the system components:

```bash
# Terminal 1: API Server
python api/server.py

# Terminal 2: Dashboard (optional)
python dashboard/backend/static_server.py

# Terminal 3: Telegram Bot
python userbot.py
```

## Configuration Options

### LLM Provider Combinations

The system supports flexible LLM combinations:

#### Option 1: Gemini + GPT (Recommended)
```bash
LLM1_PROVIDER=gemini
LLM1_MODEL=gemini-2.0-flash-exp
LLM2_PROVIDER=openai
LLM2_MODEL=gpt-4o-mini
```
- **Best for**: Cost optimization with free Gemini tier
- **Cost**: ~$0.0001 per message (refinement only)

#### Option 2: GPT + GPT (Fallback)
```bash
LLM1_PROVIDER=openai
LLM1_MODEL=gpt-4o-mini
LLM2_PROVIDER=openai
LLM2_MODEL=gpt-4o-mini
```
- **Best for**: Consistency when Gemini quotas are exceeded
- **Cost**: ~$0.0003 per message

#### Option 3: Gemini + Gemini (Experimental)
```bash
LLM1_PROVIDER=gemini
LLM1_MODEL=gemini-2.0-flash-exp
LLM2_PROVIDER=gemini
LLM2_MODEL=gemini-2.0-flash-exp
```
- **Best for**: Maximum cost savings (if within quotas)
- **Cost**: $0.00 per message (free tier)

## Quota Management

### Gemini Free Tier Limits
- **Daily**: 32,000 tokens
- **Per Minute**: 1,500 tokens
- **Monitoring**: Real-time tracking via Redis

### Quota Monitoring
```bash
# Check current usage in Redis
redis-cli
> GET gemini_quota:daily:user_123
> GET gemini_quota:minute:user_123
```

### Quota Exceeded Behavior
When Gemini quotas are exceeded:
1. System automatically falls back to OpenAI
2. Cost tracking continues normally
3. Dashboard shows quota status
4. Quotas reset automatically (daily/minute)

## Dashboard Integration

The dashboard displays multi-LLM information:

### Model Badges
- 🟢 **Gemini**: Green badge for Gemini responses
- 🔵 **GPT**: Blue badge for GPT responses
- 🟠 **FREE**: Orange badge for free tier usage

### Cost Analytics
- Daily cost breakdown by model
- Savings compared to GPT-only
- Usage distribution charts
- Quota utilization graphs

### Review Interface
- Model information for each response
- Cost per interaction
- Performance metrics
- Risk analysis from Constitution

## Troubleshooting

### Common Issues

#### 1. "Gemini API key not working"
```bash
# Test your key directly
curl -H "Content-Type: application/json" \
     -d '{"contents":[{"parts":[{"text":"Hello"}]}]}' \
     "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=YOUR_KEY"
```

#### 2. "OpenAI API key invalid"
```bash
# Test OpenAI key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_KEY"
```

#### 3. "Database migration failed"
- Ensure PostgreSQL is running
- Check database connection string
- Verify user has CREATE TABLE permissions
- Run migration manually line by line

#### 4. "Quota exceeded immediately"
- Check if you've used Gemini API elsewhere today
- Verify Redis is running and accessible
- Reset quotas manually: `redis-cli DEL gemini_quota:daily:*`

#### 5. "Models not switching correctly"
- Verify environment variables are set
- Check logs for LLM factory initialization
- Run verification script for detailed diagnosis

### Performance Issues

#### Slow Response Times
1. **Check API latency**:
   ```bash
   # Monitor response times
   tail -f logs/app.log | grep "generation_time"
   ```

2. **Redis performance**:
   ```bash
   redis-cli --latency -h localhost -p 6379
   ```

3. **Database queries**:
   ```bash
   # Enable PostgreSQL slow query log
   ALTER SYSTEM SET log_min_duration_statement = 1000;
   ```

#### High Costs
1. **Monitor token usage**:
   ```bash
   # Check average tokens per message
   SELECT AVG(tokens_used) FROM interactions WHERE created_at > NOW() - INTERVAL '24 hours';
   ```

2. **Quota utilization**:
   ```bash
   # Check Gemini usage efficiency
   SELECT 
     COUNT(*) as total_messages,
     SUM(CASE WHEN llm1_model LIKE '%gemini%' THEN 1 ELSE 0 END) as gemini_usage,
     AVG(llm1_cost_usd + llm2_cost_usd) as avg_cost
   FROM interactions 
   WHERE created_at > NOW() - INTERVAL '24 hours';
   ```

### Debug Mode

Enable detailed logging:

```bash
# Add to .env
DEBUG=True
LOG_LEVEL=DEBUG

# Or run with debug
PYTHONPATH=. python -m logging.basicConfig userbot.py
```

## Cost Analysis

### Expected Savings

With 100 messages per day (typical usage):

| Configuration | Daily Cost | Monthly Cost | Annual Cost |
|---------------|------------|--------------|-------------|
| **Multi-LLM (Gemini + GPT)** | $0.01 | $0.30 | $3.65 |
| GPT-4o-mini only | $0.03 | $0.90 | $10.95 |
| GPT-4 only | $6.00 | $180.00 | $2,190.00 |

**Savings**: Up to 99.8% compared to GPT-4 only

### Cost Breakdown per Message
- **LLM1 (Gemini)**: $0.00 (free tier)
- **LLM2 (GPT-4o-mini)**: ~$0.0001
- **Total**: ~$0.0001 per message

## Monitoring and Analytics

### Key Metrics to Track

1. **Model Distribution**:
   ```sql
   SELECT 
     llm1_model, 
     COUNT(*) as usage_count,
     AVG(llm1_cost_usd + llm2_cost_usd) as avg_cost
   FROM interactions 
   GROUP BY llm1_model;
   ```

2. **Quota Efficiency**:
   ```bash
   # Daily Gemini usage vs limit
   redis-cli GET gemini_quota:daily:total
   ```

3. **Response Quality**:
   ```sql
   SELECT 
     llm1_model,
     AVG(constitution_risk_score) as avg_risk,
     COUNT(*) as message_count
   FROM interactions 
   WHERE created_at > NOW() - INTERVAL '7 days'
   GROUP BY llm1_model;
   ```

4. **Performance Metrics**:
   ```sql
   SELECT 
     DATE(created_at) as date,
     AVG(EXTRACT(EPOCH FROM response_time)) as avg_response_time,
     SUM(tokens_used) as total_tokens
   FROM interactions 
   GROUP BY DATE(created_at) 
   ORDER BY date DESC;
   ```

### Dashboard Analytics

Access real-time analytics at:
- **Main Dashboard**: http://localhost:3000
- **API Metrics**: http://localhost:8000/metrics/dashboard
- **Cost Analytics**: Integrated in dashboard sidebar

## Production Deployment

### Environment Variables (Production)
```bash
# Security
DASHBOARD_API_KEY=production-secure-key-here
ALLOWED_ORIGINS=https://yourdomain.com

# Performance
REDIS_URL=redis://production-redis:6379/0
DATABASE_URL=postgresql://user:pass@production-db:5432/nadia_hitl

# Monitoring
LOG_LEVEL=INFO
DEBUG=False
```

### Scaling Considerations

1. **Redis Clustering**: For high-volume deployments
2. **Database Connection Pooling**: Use pgbouncer for PostgreSQL
3. **Load Balancing**: Multiple API server instances
4. **Monitoring**: Prometheus/Grafana for metrics

### Security Checklist

- [ ] Strong API keys with appropriate permissions
- [ ] HTTPS in production
- [ ] Redis AUTH enabled
- [ ] Database SSL connections
- [ ] Rate limiting configured
- [ ] CORS origins restricted
- [ ] Regular key rotation schedule

## Support and Maintenance

### Regular Tasks

1. **Weekly**: Review cost analytics and quota usage
2. **Weekly**: Check for failed API calls in logs
3. **Monthly**: Rotate API keys
4. **Monthly**: Database cleanup of old interactions
5. **Quarterly**: Review and optimize LLM configuration

### Backup Strategy

1. **Database**: Regular PostgreSQL backups
2. **Configuration**: Version control all .env files
3. **Redis**: Backup quota states for recovery
4. **Logs**: Archive for audit and debugging

---

## Quick Reference

### Start System
```bash
python scripts/verify_multi_llm.py  # Verify first
python userbot.py                   # Start bot
```

### Check Status
```bash
# API health
curl http://localhost:8000/health

# Dashboard
curl -H "Authorization: Bearer your-key" \
     http://localhost:8000/metrics/dashboard
```

### Emergency Fallback
If multi-LLM fails, temporarily disable:
```bash
# Set both to OpenAI
export LLM1_PROVIDER=openai
export LLM2_PROVIDER=openai
```

### Common Commands
```bash
# Reset Gemini quotas
redis-cli DEL "gemini_quota:*"

# Check recent interactions
psql -d nadia_hitl -c "SELECT llm1_model, llm2_model, llm1_cost_usd + llm2_cost_usd as total_cost FROM interactions ORDER BY created_at DESC LIMIT 5;"

# Run full test suite
pytest tests/ -v --asyncio-mode=auto
```

For additional support, check logs and run the verification script with debug output:
```bash
DEBUG=True python scripts/verify_multi_llm.py
```