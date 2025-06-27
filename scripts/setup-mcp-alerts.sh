#!/bin/bash

# MCP Alerts Setup Script
# Interactive setup for MCP monitoring alerts

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="/home/rober/projects/chatbot_nadia"
CONFIG_FILE="$PROJECT_ROOT/monitoring/alert_config.json"

print_header() {
    echo -e "${BLUE}"
    echo "======================================================"
    echo "           MCP Alerts Configuration Setup"
    echo "======================================================"
    echo -e "${NC}"
}

print_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

ask_yes_no() {
    local question="$1"
    local default="${2:-n}"
    
    while true; do
        if [ "$default" = "y" ]; then
            read -p "$question [Y/n]: " answer
            answer=${answer:-y}
        else
            read -p "$question [y/N]: " answer
            answer=${answer:-n}
        fi
        
        case $answer in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

setup_slack() {
    print_step "Setting up Slack notifications"
    
    if ask_yes_no "Do you want to enable Slack alerts?"; then
        echo ""
        echo "To set up Slack alerts, you need to create a webhook URL:"
        echo "1. Go to https://api.slack.com/messaging/webhooks"
        echo "2. Create a new webhook for your workspace"
        echo "3. Copy the webhook URL"
        echo ""
        
        read -p "Enter Slack webhook URL: " slack_webhook
        
        if [ -n "$slack_webhook" ]; then
            echo "Slack configuration:"
            echo "  Webhook URL: $slack_webhook"
            
            # Test webhook
            if ask_yes_no "Test Slack webhook now?"; then
                curl -X POST -H 'Content-type: application/json' \
                    --data '{"text":"🚨 MCP Alert Test - Slack integration is working!"}' \
                    "$slack_webhook" && \
                    print_info "Slack test successful!" || \
                    print_warning "Slack test failed - please check webhook URL"
            fi
            
            SLACK_ENABLED="true"
            SLACK_WEBHOOK="$slack_webhook"
        else
            print_warning "No webhook URL provided - Slack alerts disabled"
            SLACK_ENABLED="false"
            SLACK_WEBHOOK=""
        fi
    else
        SLACK_ENABLED="false"
        SLACK_WEBHOOK=""
    fi
}

setup_discord() {
    print_step "Setting up Discord notifications"
    
    if ask_yes_no "Do you want to enable Discord alerts?"; then
        echo ""
        echo "To set up Discord alerts, you need to create a webhook URL:"
        echo "1. Go to your Discord server settings"
        echo "2. Go to Integrations > Webhooks"
        echo "3. Create a new webhook"
        echo "4. Copy the webhook URL"
        echo ""
        
        read -p "Enter Discord webhook URL: " discord_webhook
        
        if [ -n "$discord_webhook" ]; then
            echo "Discord configuration:"
            echo "  Webhook URL: $discord_webhook"
            
            # Test webhook
            if ask_yes_no "Test Discord webhook now?"; then
                curl -X POST -H 'Content-type: application/json' \
                    --data '{"content":"🚨 MCP Alert Test - Discord integration is working!"}' \
                    "$discord_webhook" && \
                    print_info "Discord test successful!" || \
                    print_warning "Discord test failed - please check webhook URL"
            fi
            
            DISCORD_ENABLED="true"
            DISCORD_WEBHOOK="$discord_webhook"
        else
            print_warning "No webhook URL provided - Discord alerts disabled"
            DISCORD_ENABLED="false"
            DISCORD_WEBHOOK=""
        fi
    else
        DISCORD_ENABLED="false"
        DISCORD_WEBHOOK=""
    fi
}

setup_email() {
    print_step "Setting up Email notifications"
    
    if ask_yes_no "Do you want to enable Email alerts?"; then
        echo ""
        echo "Email configuration requires SMTP settings:"
        
        read -p "SMTP Server (default: smtp.gmail.com): " smtp_server
        smtp_server=${smtp_server:-smtp.gmail.com}
        
        read -p "SMTP Port (default: 587): " smtp_port
        smtp_port=${smtp_port:-587}
        
        read -p "SMTP Username/Email: " smtp_username
        read -s -p "SMTP Password: " smtp_password
        echo ""
        
        read -p "From Email (default: $smtp_username): " from_email
        from_email=${from_email:-$smtp_username}
        
        read -p "To Email(s) (comma-separated): " to_emails
        
        if [ -n "$smtp_username" ] && [ -n "$smtp_password" ] && [ -n "$to_emails" ]; then
            echo "Email configuration:"
            echo "  SMTP Server: $smtp_server:$smtp_port"
            echo "  Username: $smtp_username"
            echo "  From: $from_email"
            echo "  To: $to_emails"
            
            # Test email
            if ask_yes_no "Test email configuration now?" && command -v python3 >/dev/null; then
                python3 -c "
import smtplib
from email.mime.text import MimeText
try:
    server = smtplib.SMTP('$smtp_server', $smtp_port)
    server.starttls()
    server.login('$smtp_username', '$smtp_password')
    
    msg = MimeText('🚨 MCP Alert Test - Email integration is working!')
    msg['Subject'] = 'MCP Alert Test'
    msg['From'] = '$from_email'
    msg['To'] = '$to_emails'
    
    server.send_message(msg)
    server.quit()
    print('Email test successful!')
except Exception as e:
    print(f'Email test failed: {e}')
" && print_info "Email test completed" || print_warning "Email test had issues"
            fi
            
            EMAIL_ENABLED="true"
            EMAIL_SMTP_SERVER="$smtp_server"
            EMAIL_SMTP_PORT="$smtp_port"
            EMAIL_USERNAME="$smtp_username"
            EMAIL_PASSWORD="$smtp_password"
            EMAIL_FROM="$from_email"
            EMAIL_TO="$to_emails"
        else
            print_warning "Incomplete email configuration - Email alerts disabled"
            EMAIL_ENABLED="false"
        fi
    else
        EMAIL_ENABLED="false"
    fi
}

setup_webhook() {
    print_step "Setting up Custom Webhook notifications"
    
    if ask_yes_no "Do you want to enable custom webhook alerts?"; then
        echo ""
        read -p "Webhook URL: " webhook_url
        read -p "Authentication header name (optional): " auth_header
        read -p "Authentication token (optional): " auth_token
        
        if [ -n "$webhook_url" ]; then
            echo "Webhook configuration:"
            echo "  URL: $webhook_url"
            echo "  Auth Header: $auth_header"
            
            # Test webhook
            if ask_yes_no "Test webhook now?"; then
                test_payload='{"alert":{"type":"test","severity":"INFO","message":"MCP Alert Test"}}'
                
                if [ -n "$auth_header" ] && [ -n "$auth_token" ]; then
                    curl -X POST -H 'Content-type: application/json' \
                         -H "$auth_header: $auth_token" \
                         --data "$test_payload" \
                         "$webhook_url" && \
                         print_info "Webhook test successful!" || \
                         print_warning "Webhook test failed"
                else
                    curl -X POST -H 'Content-type: application/json' \
                         --data "$test_payload" \
                         "$webhook_url" && \
                         print_info "Webhook test successful!" || \
                         print_warning "Webhook test failed"
                fi
            fi
            
            WEBHOOK_ENABLED="true"
            WEBHOOK_URL="$webhook_url"
            WEBHOOK_AUTH_HEADER="$auth_header"
            WEBHOOK_AUTH_TOKEN="$auth_token"
        else
            WEBHOOK_ENABLED="false"
        fi
    else
        WEBHOOK_ENABLED="false"
    fi
}

setup_thresholds() {
    print_step "Setting up Alert Thresholds"
    
    echo ""
    echo "Configure when alerts should be triggered:"
    
    read -p "Consecutive failures before alert (default: 3): " consecutive_failures
    consecutive_failures=${consecutive_failures:-3}
    
    read -p "CPU usage threshold % (default: 80): " cpu_threshold
    cpu_threshold=${cpu_threshold:-80}
    
    read -p "Memory usage threshold % (default: 85): " memory_threshold
    memory_threshold=${memory_threshold:-85}
    
    read -p "Queue size threshold (default: 1000): " queue_threshold
    queue_threshold=${queue_threshold:-1000}
    
    read -p "Disk usage threshold % (default: 90): " disk_threshold
    disk_threshold=${disk_threshold:-90}
    
    read -p "Alert cooldown minutes (default: 30): " alert_cooldown
    alert_cooldown=${alert_cooldown:-30}
    
    read -p "Max alerts per hour (default: 10): " max_alerts_hour
    max_alerts_hour=${max_alerts_hour:-10}
    
    echo ""
    echo "Threshold configuration:"
    echo "  Consecutive failures: $consecutive_failures"
    echo "  CPU threshold: $cpu_threshold%"
    echo "  Memory threshold: $memory_threshold%"
    echo "  Queue threshold: $queue_threshold"
    echo "  Disk threshold: $disk_threshold%"
    echo "  Alert cooldown: $alert_cooldown minutes"
    echo "  Max alerts/hour: $max_alerts_hour"
}

generate_config() {
    print_step "Generating configuration file"
    
    mkdir -p "$(dirname "$CONFIG_FILE")"
    
    cat > "$CONFIG_FILE" << EOF
{
  "global": {
    "alert_cooldown_minutes": $alert_cooldown,
    "max_alerts_per_hour": $max_alerts_hour,
    "enable_alert_grouping": true
  },
  "channels": {
    "slack": {
      "enabled": $SLACK_ENABLED,
      "webhook_url": "$SLACK_WEBHOOK",
      "severity_filter": ["CRITICAL", "WARNING"]
    },
    "discord": {
      "enabled": $DISCORD_ENABLED,
      "webhook_url": "$DISCORD_WEBHOOK",
      "severity_filter": ["CRITICAL", "WARNING"]
    },
    "email": {
      "enabled": $EMAIL_ENABLED,
      "smtp_server": "${EMAIL_SMTP_SERVER:-smtp.gmail.com}",
      "smtp_port": ${EMAIL_SMTP_PORT:-587},
      "username": "${EMAIL_USERNAME:-}",
      "password": "${EMAIL_PASSWORD:-}",
      "from_email": "${EMAIL_FROM:-}",
      "to_emails": [$(echo "$EMAIL_TO" | sed 's/,/", "/g' | sed 's/^/"/' | sed 's/$/"/')],
      "severity_filter": ["CRITICAL"]
    },
    "webhook": {
      "enabled": $WEBHOOK_ENABLED,
      "url": "${WEBHOOK_URL:-}",
      "headers": {},
      "auth_header": "${WEBHOOK_AUTH_HEADER:-}",
      "auth_token": "${WEBHOOK_AUTH_TOKEN:-}",
      "severity_filter": ["CRITICAL", "WARNING"]
    },
    "system_command": {
      "enabled": false,
      "command": "echo 'MCP Alert: {severity} - {type}' >> /var/log/mcp-alerts.log",
      "severity_filter": ["CRITICAL"]
    }
  },
  "thresholds": {
    "consecutive_failures": $consecutive_failures,
    "cpu_threshold": $cpu_threshold,
    "memory_threshold": $memory_threshold,
    "queue_threshold": $queue_threshold,
    "disk_threshold": $disk_threshold,
    "response_time_threshold": 5000
  }
}
EOF
    
    print_info "Configuration saved to: $CONFIG_FILE"
}

test_alert_system() {
    print_step "Testing complete alert system"
    
    if ask_yes_no "Send test alerts through all configured channels?"; then
        echo ""
        print_info "Sending test alerts..."
        
        cd "$PROJECT_ROOT"
        python3 -c "
import asyncio
import sys
sys.path.append('.')
from monitoring.mcp_alert_manager import MCPAlertManager

async def test():
    manager = MCPAlertManager()
    
    # Test all channels
    results = await manager.test_channels()
    print('\\nTest results:')
    for channel, success in results.items():
        status = '✓' if success else '✗'
        print(f'  {status} {channel}')
    
    # Send actual test alert
    test_alert = {
        'timestamp': '$(date -u +"%Y-%m-%dT%H:%M:%SZ")',
        'type': 'setup_test',
        'severity': 'INFO',
        'message': 'MCP Alert system setup completed successfully!',
        'daemon': 'setup_script'
    }
    
    success = await manager.process_alert(test_alert)
    print(f'\\nTest alert sent: {\"✓\" if success else \"✗\"}')

asyncio.run(test())
" && print_info "Alert system test completed" || print_warning "Alert system test had issues"
    fi
}

show_summary() {
    print_step "Setup Summary"
    
    echo ""
    echo "MCP Alerts Configuration Complete!"
    echo ""
    echo "Enabled channels:"
    [ "$SLACK_ENABLED" = "true" ] && echo "  ✓ Slack"
    [ "$DISCORD_ENABLED" = "true" ] && echo "  ✓ Discord"
    [ "$EMAIL_ENABLED" = "true" ] && echo "  ✓ Email"
    [ "$WEBHOOK_ENABLED" = "true" ] && echo "  ✓ Custom Webhook"
    
    echo ""
    echo "Configuration file: $CONFIG_FILE"
    echo ""
    echo "Next steps:"
    echo "1. Start MCP health daemon: make mcp-daemon-start"
    echo "2. Or install cron jobs: make mcp-install-cron"
    echo "3. Monitor alerts: tail -f logs/mcp-health-daemon.log"
    echo "4. View alert stats: curl http://localhost:8000/api/mcp/alerts"
    echo ""
    echo "To reconfigure alerts, run this script again:"
    echo "  $0"
}

main() {
    print_header
    
    print_info "This script will help you set up MCP monitoring alerts."
    print_info "You can configure Slack, Discord, Email, and webhook notifications."
    echo ""
    
    if [ -f "$CONFIG_FILE" ]; then
        print_warning "Existing configuration found at: $CONFIG_FILE"
        if ! ask_yes_no "Do you want to reconfigure alerts?"; then
            echo "Configuration unchanged."
            exit 0
        fi
        echo ""
    fi
    
    # Setup each channel
    setup_slack
    echo ""
    setup_discord
    echo ""
    setup_email
    echo ""
    setup_webhook
    echo ""
    setup_thresholds
    echo ""
    
    # Generate config
    generate_config
    echo ""
    
    # Test system
    test_alert_system
    echo ""
    
    # Show summary
    show_summary
}

# Check if running with help flag
case "${1:-}" in
    "-h"|"--help"|"help")
        echo "MCP Alerts Setup Script"
        echo ""
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  -h, --help    Show this help message"
        echo "  test          Test existing configuration"
        echo "  show          Show current configuration"
        echo ""
        echo "This script will interactively configure MCP monitoring alerts"
        echo "including Slack, Discord, Email, and webhook notifications."
        exit 0
        ;;
    "test")
        print_header
        if [ -f "$CONFIG_FILE" ]; then
            cd "$PROJECT_ROOT"
            python3 monitoring/mcp_alert_manager.py
        else
            print_error "No configuration found. Run setup first: $0"
        fi
        exit 0
        ;;
    "show")
        print_header
        if [ -f "$CONFIG_FILE" ]; then
            echo "Current configuration:"
            cat "$CONFIG_FILE" | python3 -m json.tool
        else
            print_error "No configuration found. Run setup first: $0"
        fi
        exit 0
        ;;
esac

# Run main setup
main