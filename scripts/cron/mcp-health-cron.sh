#!/bin/bash

# MCP Health Check Cron Script
# Alternative to systemd daemon for scheduled health checks

set -e

# Configuration
PROJECT_ROOT="/home/rober/projects/chatbot_nadia"
SCRIPT_DIR="$PROJECT_ROOT/scripts"
LOG_DIR="$PROJECT_ROOT/logs"
WORKFLOW_SCRIPT="$SCRIPT_DIR/mcp-workflow.sh"

# Colors for logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging function
log_message() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        "ERROR")
            echo -e "${RED}[$timestamp] ERROR: $message${NC}" | tee -a "$LOG_DIR/mcp-health-cron.log"
            ;;
        "WARN")
            echo -e "${YELLOW}[$timestamp] WARN: $message${NC}" | tee -a "$LOG_DIR/mcp-health-cron.log"
            ;;
        "INFO")
            echo -e "${GREEN}[$timestamp] INFO: $message${NC}" | tee -a "$LOG_DIR/mcp-health-cron.log"
            ;;
        *)
            echo "[$timestamp] $message" | tee -a "$LOG_DIR/mcp-health-cron.log"
            ;;
    esac
}

# Check if script exists
if [ ! -f "$WORKFLOW_SCRIPT" ]; then
    log_message "ERROR" "MCP workflow script not found: $WORKFLOW_SCRIPT"
    exit 1
fi

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Change to project directory
cd "$PROJECT_ROOT"

# Function to run MCP command with error handling
run_mcp_check() {
    local command=$1
    local description=$2
    
    log_message "INFO" "Starting $description"
    
    if timeout 300 "$WORKFLOW_SCRIPT" "$command" >> "$LOG_DIR/mcp-health-cron.log" 2>&1; then
        log_message "INFO" "$description completed successfully"
        return 0
    else
        local exit_code=$?
        log_message "ERROR" "$description failed with exit code $exit_code"
        return $exit_code
    fi
}

# Function to send alert
send_alert() {
    local subject=$1
    local message=$2
    
    # Log alert
    log_message "ERROR" "ALERT: $subject - $message"
    
    # Store alert in file for external monitoring
    echo "$(date '+%Y-%m-%d %H:%M:%S') | $subject | $message" >> "$LOG_DIR/mcp-alerts.log"
    
    # Optional: Send to monitoring system
    # curl -X POST "http://monitoring-system/alert" -d "subject=$subject&message=$message" 2>/dev/null || true
}

# Parse command line arguments
case "${1:-health}" in
    "health")
        run_mcp_check "health-check" "System Health Check"
        ;;
    "security")
        run_mcp_check "security-check" "Security Scan"
        ;;
    "performance")
        run_mcp_check "perf-baseline" "Performance Baseline"
        ;;
    "redis")
        run_mcp_check "redis-health" "Redis Health Check"
        ;;
    "all")
        log_message "INFO" "Running all MCP health checks"
        
        failed_checks=0
        
        if ! run_mcp_check "health-check" "System Health Check"; then
            ((failed_checks++))
            send_alert "Health Check Failed" "System health check failed"
        fi
        
        if ! run_mcp_check "security-check" "Security Scan"; then
            ((failed_checks++))
            send_alert "Security Check Failed" "Security scan detected issues"
        fi
        
        if ! run_mcp_check "redis-health" "Redis Health Check"; then
            ((failed_checks++))
            send_alert "Redis Health Failed" "Redis health check failed"
        fi
        
        if [ $failed_checks -eq 0 ]; then
            log_message "INFO" "All health checks completed successfully"
        else
            log_message "ERROR" "$failed_checks health checks failed"
            exit 1
        fi
        ;;
    "install-cron")
        log_message "INFO" "Installing cron jobs for MCP health checks"
        
        # Create cron entries
        cron_entries=$(cat << 'EOF'
# MCP Health Check Cron Jobs
# System health check every 15 minutes
*/15 * * * * /home/rober/projects/chatbot_nadia/scripts/cron/mcp-health-cron.sh health >/dev/null 2>&1

# Security scan every 4 hours
0 */4 * * * /home/rober/projects/chatbot_nadia/scripts/cron/mcp-health-cron.sh security >/dev/null 2>&1

# Performance baseline twice daily
0 6,18 * * * /home/rober/projects/chatbot_nadia/scripts/cron/mcp-health-cron.sh performance >/dev/null 2>&1

# Redis health check every 10 minutes
*/10 * * * * /home/rober/projects/chatbot_nadia/scripts/cron/mcp-health-cron.sh redis >/dev/null 2>&1

# Comprehensive check once daily
0 2 * * * /home/rober/projects/chatbot_nadia/scripts/cron/mcp-health-cron.sh all >/dev/null 2>&1
EOF
)
        
        # Add to crontab
        (crontab -l 2>/dev/null || echo "") | grep -v "MCP Health Check" | cat - <(echo "$cron_entries") | crontab -
        
        log_message "INFO" "Cron jobs installed successfully"
        log_message "INFO" "Use 'crontab -l' to verify installation"
        ;;
    "uninstall-cron")
        log_message "INFO" "Removing MCP health check cron jobs"
        
        # Remove from crontab
        (crontab -l 2>/dev/null || echo "") | grep -v "MCP Health Check" | grep -v "mcp-health-cron.sh" | crontab -
        
        log_message "INFO" "Cron jobs removed successfully"
        ;;
    "status")
        log_message "INFO" "MCP Health Check Status"
        
        # Show recent log entries
        if [ -f "$LOG_DIR/mcp-health-cron.log" ]; then
            echo "Last 10 log entries:"
            tail -n 10 "$LOG_DIR/mcp-health-cron.log"
        fi
        
        # Show recent alerts
        if [ -f "$LOG_DIR/mcp-alerts.log" ]; then
            echo ""
            echo "Recent alerts:"
            tail -n 5 "$LOG_DIR/mcp-alerts.log"
        fi
        
        # Show cron jobs
        echo ""
        echo "Installed cron jobs:"
        crontab -l 2>/dev/null | grep -E "mcp-health-cron\.sh|MCP Health Check" || echo "No MCP cron jobs found"
        ;;
    "help")
        cat << 'EOF'
MCP Health Check Cron Script

Usage: mcp-health-cron.sh [command]

Commands:
    health          Run system health check (default)
    security        Run security scan
    performance     Run performance baseline
    redis           Run Redis health check
    all             Run all health checks
    install-cron    Install cron jobs for automated checks
    uninstall-cron  Remove cron jobs
    status          Show status and recent logs
    help            Show this help message

Cron Schedule (after install-cron):
    */15 * * * *    System health check (every 15 minutes)
    */10 * * * *    Redis health check (every 10 minutes)
    0 */4 * * *     Security scan (every 4 hours)
    0 6,18 * * *    Performance baseline (6 AM and 6 PM)
    0 2 * * *       All checks (2 AM daily)

Logs:
    General: /home/rober/projects/chatbot_nadia/logs/mcp-health-cron.log
    Alerts:  /home/rober/projects/chatbot_nadia/logs/mcp-alerts.log

Examples:
    ./mcp-health-cron.sh health
    ./mcp-health-cron.sh install-cron
    ./mcp-health-cron.sh status
EOF
        ;;
    *)
        log_message "ERROR" "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac