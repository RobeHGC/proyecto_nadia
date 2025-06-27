# MCP Alerts Setup Guide

> **Quick Start**: How to set up automated alerting for MCP health monitoring

## Overview

The MCP Alert system monitors your NADIA infrastructure and sends notifications when issues are detected. It supports multiple channels including Slack, Discord, Email, and custom webhooks.

## Quick Setup

### 1. **Interactive Setup (Recommended)**
```bash
# Run interactive setup script
make mcp-setup-alerts

# Or directly:
./scripts/setup-mcp-alerts.sh
```

This will guide you through configuring:
- Slack notifications
- Discord notifications  
- Email alerts
- Custom webhooks
- Alert thresholds

### 2. **Test Configuration**
```bash
# Test all configured channels
make mcp-test-alerts

# Send test alert
make mcp-send-test-alert

# View alert statistics
make mcp-alert-stats
```

### 3. **Start Monitoring**
```bash
# Option A: Start daemon with alerts
make mcp-daemon-start

# Option B: Install cron jobs  
make mcp-install-cron
```

## Alert Channels

### **Slack Integration**

1. **Create Webhook:**
   - Go to https://api.slack.com/messaging/webhooks
   - Create webhook for your workspace
   - Copy webhook URL

2. **Configure:**
   ```bash
   ./scripts/setup-mcp-alerts.sh
   # Select Slack and enter webhook URL
   ```

3. **Test:**
   ```bash
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"🚨 MCP Test Alert"}' \
     YOUR_WEBHOOK_URL
   ```

### **Discord Integration**

1. **Create Webhook:**
   - Go to Server Settings → Integrations → Webhooks
   - Create new webhook
   - Copy webhook URL

2. **Configure:**
   ```bash
   ./scripts/setup-mcp-alerts.sh
   # Select Discord and enter webhook URL
   ```

### **Email Integration**

Supports any SMTP server (Gmail, Outlook, custom):

```bash
./scripts/setup-mcp-alerts.sh
# Configure SMTP settings:
# - Server: smtp.gmail.com
# - Port: 587
# - Username/Password
# - Recipients
```

**Gmail Setup:**
1. Enable 2-factor authentication
2. Generate app password
3. Use app password (not regular password)

### **Custom Webhooks**

For integration with monitoring systems:

```bash
./scripts/setup-mcp-alerts.sh
# Enter webhook URL and optional auth headers
```

Webhook payload format:
```json
{
  "alert": {
    "timestamp": "2025-01-27T10:30:00Z",
    "type": "health_check_failure",
    "severity": "CRITICAL",
    "message": "MCP health check has failed 3 times",
    "daemon": "mcp_health_daemon"
  },
  "source": "nadia_mcp_monitor"
}
```

## Alert Types

### **Health Check Alerts**
- `health_check_failure` - System health check failures
- `security_check_failure` - Security scan failures  
- `redis_health_failure` - Redis connectivity issues

### **Threshold Alerts**
- `threshold_cpu_usage` - CPU usage > 80%
- `threshold_memory_usage` - Memory usage > 85%
- `threshold_queue_size` - Queue size > 1000 items
- `threshold_disk_usage` - Disk usage > 90%

### **Component Alerts**
- `component_failure_api` - API server issues
- `component_failure_bot` - Telegram bot issues
- `component_failure_database` - Database connectivity

## Alert Configuration

### **Configuration File**
Location: `monitoring/alert_config.json`

```json
{
  "global": {
    "alert_cooldown_minutes": 30,
    "max_alerts_per_hour": 10,
    "enable_alert_grouping": true
  },
  "channels": {
    "slack": {
      "enabled": true,
      "webhook_url": "https://hooks.slack.com/...",
      "severity_filter": ["CRITICAL", "WARNING"]
    },
    "email": {
      "enabled": true,
      "smtp_server": "smtp.gmail.com",
      "severity_filter": ["CRITICAL"]
    }
  },
  "thresholds": {
    "consecutive_failures": 3,
    "cpu_threshold": 80,
    "memory_threshold": 85
  }
}
```

### **Severity Levels**
- **CRITICAL** - Immediate attention required
- **WARNING** - Issue needs monitoring
- **INFO** - Informational notifications

### **Rate Limiting**
- **Cooldown**: Prevents duplicate alerts (default: 30 minutes)
- **Rate Limit**: Max alerts per hour (default: 10)
- **Grouping**: Similar alerts are grouped together

## API Endpoints

### **Alert Management**
```bash
# Get recent alerts
curl "http://localhost:8000/api/mcp/alerts" \
  -H "Authorization: Bearer YOUR_API_KEY"

# Get alert statistics
curl "http://localhost:8000/api/mcp/alerts/stats" \
  -H "Authorization: Bearer YOUR_API_KEY"

# Test alert channels
curl -X POST "http://localhost:8000/api/mcp/alerts/test" \
  -H "Authorization: Bearer YOUR_API_KEY"

# Send manual alert
curl -X POST "http://localhost:8000/api/mcp/alerts/send?alert_type=manual&message=Test&severity=INFO" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Makefile Commands

```bash
# Setup and Configuration
make mcp-setup-alerts          # Interactive setup
make mcp-test-alerts           # Test channels
make mcp-alert-stats          # View statistics

# Alert Management  
make mcp-send-test-alert      # Send test alert
make mcp-daemon-start         # Start with alerts
make mcp-install-cron         # Cron-based alerts

# Monitoring
make mcp-daemon-status        # Check daemon
make mcp-cron-status          # Check cron jobs
```

## Troubleshooting

### **No Alerts Received**

1. **Check Configuration:**
   ```bash
   ./scripts/setup-mcp-alerts.sh show
   ```

2. **Test Channels:**
   ```bash
   make mcp-test-alerts
   ```

3. **Check Logs:**
   ```bash
   tail -f logs/mcp-health-daemon.log
   ```

### **Too Many Alerts**

1. **Adjust Cooldown:**
   ```json
   {
     "global": {
       "alert_cooldown_minutes": 60,
       "max_alerts_per_hour": 5
     }
   }
   ```

2. **Filter Severity:**
   ```json
   {
     "channels": {
       "slack": {
         "severity_filter": ["CRITICAL"]
       }
     }
   }
   ```

### **Webhook Failures**

1. **Test Manually:**
   ```bash
   curl -X POST "YOUR_WEBHOOK_URL" \
     -H "Content-Type: application/json" \
     -d '{"text":"test"}'
   ```

2. **Check Authentication:**
   ```json
   {
     "webhook": {
       "auth_header": "Authorization",
       "auth_token": "Bearer YOUR_TOKEN"
     }
   }
   ```

### **Email Issues**

1. **Gmail App Passwords:**
   - Enable 2FA
   - Generate app-specific password
   - Use app password, not regular password

2. **SMTP Settings:**
   ```bash
   # Test SMTP connection
   python3 -c "
   import smtplib
   server = smtplib.SMTP('smtp.gmail.com', 587)
   server.starttls()
   server.login('user@gmail.com', 'app_password')
   print('SMTP connection successful')
   server.quit()
   "
   ```

## Advanced Configuration

### **Custom Alert Types**
```python
# In your code
from monitoring.mcp_alert_manager import send_mcp_alert

await send_mcp_alert(
    "custom_alert",
    "Custom application alert message",
    "WARNING"
)
```

### **System Command Integration**
```json
{
  "channels": {
    "system_command": {
      "enabled": true,
      "command": "systemctl restart nadia-api",
      "severity_filter": ["CRITICAL"]
    }
  }
}
```

### **Webhook Authentication**
```json
{
  "webhook": {
    "enabled": true,
    "url": "https://your-monitoring.com/webhook",
    "headers": {
      "User-Agent": "NADIA-MCP-Monitor"
    },
    "auth_header": "X-API-Key",
    "auth_token": "your-secret-key"
  }
}
```

## Integration Examples

### **Grafana Integration**
```bash
# Webhook for Grafana alerts
curl -X POST "http://localhost:8000/api/mcp/alerts/send" \
  -H "Authorization: Bearer API_KEY" \
  -d "alert_type=grafana_alert&message=High CPU detected&severity=WARNING"
```

### **Prometheus Integration**
```yaml
# prometheus.yml
rule_files:
  - "mcp_alerts.yml"

# mcp_alerts.yml  
groups:
  - name: mcp.rules
    rules:
      - alert: MCPHealthDown
        expr: up{job="mcp-health"} == 0
        annotations:
          description: "MCP health check is down"
```

### **Log Monitoring**
```bash
# Monitor logs for errors
tail -f /var/log/nadia.log | grep ERROR | while read line; do
  curl -X POST "http://localhost:8000/api/mcp/alerts/send" \
    -H "Authorization: Bearer API_KEY" \
    -d "alert_type=log_error&message=$line&severity=WARNING"
done
```

## Best Practices

1. **Start Simple:**
   - Begin with one channel (Slack/Discord)
   - Use CRITICAL alerts only
   - Gradually add more channels

2. **Tune Thresholds:**
   - Monitor for false positives
   - Adjust thresholds based on usage
   - Use WARNING → CRITICAL escalation

3. **Test Regularly:**
   - Monthly channel tests
   - Verify alert delivery
   - Update contact information

4. **Document Procedures:**
   - Response procedures for each alert
   - Escalation paths
   - Recovery steps

## Quick Start Checklist

- [ ] Run `make mcp-setup-alerts`
- [ ] Configure at least one channel (Slack/Discord/Email)
- [ ] Test with `make mcp-test-alerts`
- [ ] Start monitoring with `make mcp-daemon-start` or `make mcp-install-cron`
- [ ] Verify alerts are working
- [ ] Document alert response procedures
- [ ] Schedule regular testing

---

**Next Steps:**
- Set up alert response procedures
- Integrate with incident management
- Configure escalation policies
- Set up alert analytics and reporting

For more information, see:
- [MCP Developer Workflow Guide](./MCP_DEVELOPER_WORKFLOW.md)
- [MCP Integration Guide](./MCP_INTEGRATION_GUIDE.md)