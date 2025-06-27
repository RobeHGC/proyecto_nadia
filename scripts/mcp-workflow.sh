#!/bin/bash

# MCP Workflow Helper Script
# Purpose: Streamline common MCP operations for NADIA developers

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[MCP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
MCP Workflow Helper for NADIA Development

Usage: $0 <command> [options]

Commands:
    debug-user <user_id>        Debug issues for a specific user
    slow-api <endpoint>         Investigate slow API endpoint
    security-check              Run pre-commit security scan
    health-check                Full system health check
    perf-baseline               Create performance baseline
    find-error <pattern>        Search for error patterns
    db-stats                    Show database statistics
    redis-health                Check Redis queue health
    recent-changes <path>       Show recent git changes for path
    
Examples:
    $0 debug-user 12345
    $0 slow-api /api/messages/review
    $0 find-error "user_id.*undefined"

EOF
}

# Debug user function
debug_user() {
    local user_id=$1
    if [ -z "$user_id" ]; then
        print_error "User ID required"
        exit 1
    fi

    print_status "Debugging user: $user_id"
    
    echo -e "\n${BLUE}=== Database Record ===${NC}"
    mcp postgres-nadia query --sql "SELECT * FROM user_current_status WHERE user_id = '$user_id'"
    
    echo -e "\n${BLUE}=== Recent Conversations ===${NC}"
    mcp postgres-nadia query --sql "
        SELECT conversation_id, status, created_at, updated_at 
        FROM conversations 
        WHERE user_id = '$user_id' 
        ORDER BY created_at DESC 
        LIMIT 5"
    
    echo -e "\n${BLUE}=== Redis Data ===${NC}"
    mcp redis-nadia get_user_history --user_id "$user_id" 2>/dev/null || print_warning "No Redis data found"
    
    print_success "User debug complete"
}

# Investigate slow API
slow_api() {
    local endpoint=$1
    if [ -z "$endpoint" ]; then
        print_error "Endpoint required"
        exit 1
    fi

    print_status "Investigating slow API: $endpoint"
    
    echo -e "\n${BLUE}=== API Latency ===${NC}"
    mcp performance-nadia check_api_latency --endpoint "$endpoint"
    
    echo -e "\n${BLUE}=== Active Database Queries ===${NC}"
    mcp postgres-nadia query --sql "
        SELECT pid, now() - pg_stat_activity.query_start AS duration, query 
        FROM pg_stat_activity 
        WHERE state = 'active' 
        ORDER BY duration DESC 
        LIMIT 5"
    
    echo -e "\n${BLUE}=== System Performance ===${NC}"
    mcp performance-nadia get_current_metrics
    
    print_success "API investigation complete"
}

# Security check
security_check() {
    print_status "Running security checks..."
    
    local failed=0
    
    echo -e "\n${BLUE}=== Environment Files ===${NC}"
    if ! mcp security-nadia scan_environment_files; then
        print_error "Environment file issues detected"
        failed=1
    fi
    
    echo -e "\n${BLUE}=== API Keys ===${NC}"
    if ! mcp security-nadia detect_api_keys; then
        print_error "Exposed API keys detected"
        failed=1
    fi
    
    echo -e "\n${BLUE}=== File Permissions ===${NC}"
    if ! mcp security-nadia audit_permissions; then
        print_warning "Permission issues detected"
    fi
    
    if [ $failed -eq 0 ]; then
        print_success "All security checks passed"
        return 0
    else
        print_error "Security issues found - please fix before committing"
        return 1
    fi
}

# Health check
health_check() {
    print_status "Running system health check..."
    
    echo -e "\n${BLUE}=== System Health ===${NC}"
    mcp health-nadia check_system_health
    
    echo -e "\n${BLUE}=== Service Status ===${NC}"
    mcp health-nadia check_critical_services
    
    echo -e "\n${BLUE}=== Database Health ===${NC}"
    mcp postgres-nadia query --sql "
        SELECT current_database() as database, 
               pg_size_pretty(pg_database_size(current_database())) as size,
               (SELECT count(*) FROM pg_stat_activity) as connections"
    
    echo -e "\n${BLUE}=== Redis Health ===${NC}"
    mcp redis-nadia analyze_queue_health
    
    print_success "Health check complete"
}

# Performance baseline
perf_baseline() {
    local baseline_file="perf_baseline_$(date +%Y%m%d_%H%M%S).json"
    
    print_status "Creating performance baseline..."
    
    mcp performance-nadia analyze_system_performance > "$baseline_file"
    
    print_success "Baseline saved to: $baseline_file"
    echo "Compare later with: mcp performance-nadia analyze_system_performance | diff $baseline_file -"
}

# Find error patterns
find_error() {
    local pattern=$1
    if [ -z "$pattern" ]; then
        print_error "Search pattern required"
        exit 1
    fi

    print_status "Searching for error pattern: $pattern"
    
    echo -e "\n${BLUE}=== Log Files ===${NC}"
    mcp filesystem-nadia search_files --pattern "$pattern" --path "logs/"
    
    echo -e "\n${BLUE}=== Source Code ===${NC}"
    mcp filesystem-nadia search_files --pattern "$pattern" --path "."
    
    echo -e "\n${BLUE}=== Recent Commits ===${NC}"
    mcp git-nadia search_commits --query "$pattern" --limit 5
    
    print_success "Search complete"
}

# Database statistics
db_stats() {
    print_status "Gathering database statistics..."
    
    echo -e "\n${BLUE}=== Table Sizes ===${NC}"
    mcp postgres-nadia query --sql "
        SELECT schemaname, tablename, 
               pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
        FROM pg_tables 
        WHERE schemaname = 'public' 
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC"
    
    echo -e "\n${BLUE}=== Table Activity ===${NC}"
    mcp postgres-nadia query --sql "
        SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del, n_live_tup
        FROM pg_stat_user_tables 
        ORDER BY n_tup_ins + n_tup_upd + n_tup_del DESC 
        LIMIT 10"
    
    print_success "Database stats complete"
}

# Redis health
redis_health() {
    print_status "Checking Redis health..."
    
    echo -e "\n${BLUE}=== Queue Status ===${NC}"
    mcp redis-nadia analyze_queue_health
    
    echo -e "\n${BLUE}=== Memory Info ===${NC}"
    mcp redis-nadia get_memory_info
    
    print_success "Redis health check complete"
}

# Recent changes
recent_changes() {
    local path=$1
    if [ -z "$path" ]; then
        path="."
    fi

    print_status "Showing recent changes for: $path"
    
    echo -e "\n${BLUE}=== Recent Commits ===${NC}"
    mcp git-nadia get_commit_history --path "$path" --limit 10
    
    echo -e "\n${BLUE}=== File Changes ===${NC}"
    mcp git-nadia get_file_diff --file "$path" --commits 5
    
    print_success "Change history complete"
}

# Main script logic
case "$1" in
    debug-user)
        debug_user "$2"
        ;;
    slow-api)
        slow_api "$2"
        ;;
    security-check)
        security_check
        ;;
    health-check)
        health_check
        ;;
    perf-baseline)
        perf_baseline
        ;;
    find-error)
        find_error "$2"
        ;;
    db-stats)
        db_stats
        ;;
    redis-health)
        redis_health
        ;;
    recent-changes)
        recent_changes "$2"
        ;;
    help|--help|-h|"")
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac