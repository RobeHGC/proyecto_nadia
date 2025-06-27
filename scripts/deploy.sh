#!/bin/bash
# NADIA HITL Production Deployment Script
# Automated deployment with health checks and rollback capability

set -euo pipefail

# ====================================================================
# Configuration and Variables
# ====================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/tmp/nadia_deploy_${TIMESTAMP}.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${ENVIRONMENT:-production}"
SKIP_TESTS="${SKIP_TESTS:-false}"
SKIP_BACKUP="${SKIP_BACKUP:-false}"
TIMEOUT="${TIMEOUT:-300}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

# ====================================================================
# Utility Functions
# ====================================================================

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗${NC} $1" | tee -a "$LOG_FILE"
}

show_help() {
    cat << EOF
NADIA HITL Deployment Script

Usage: $0 [OPTIONS]

Options:
    -e, --environment ENV     Environment to deploy (production|staging) [default: production]
    -s, --skip-tests         Skip running tests before deployment
    -b, --skip-backup        Skip database backup before deployment
    -t, --timeout SECONDS   Health check timeout in seconds [default: 300]
    -f, --compose-file FILE  Docker compose file to use [default: docker-compose.yml]
    -h, --help              Show this help message

Environment Variables:
    BUILD_VERSION           Version tag for the build [default: latest]
    BUILD_COMMIT           Git commit hash [auto-detected]
    SKIP_TESTS             Skip tests if set to 'true'
    SKIP_BACKUP            Skip backup if set to 'true'

Examples:
    # Standard production deployment
    $0

    # Deploy specific version
    BUILD_VERSION=v1.2.3 $0

    # Deploy to staging
    $0 --environment staging

    # Quick deployment (skip tests and backup)
    $0 --skip-tests --skip-backup
EOF
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not available"
        exit 1
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed or not available"
        exit 1
    fi
    
    # Check if we're in the project root
    if [[ ! -f "$PROJECT_ROOT/docker-compose.yml" ]]; then
        log_error "docker-compose.yml not found. Are you in the project root?"
        exit 1
    fi
    
    # Check if environment file exists
    local env_file="$PROJECT_ROOT/.env"
    if [[ "$ENVIRONMENT" != "production" ]]; then
        env_file="$PROJECT_ROOT/.env.$ENVIRONMENT"
    fi
    
    if [[ ! -f "$env_file" ]]; then
        log_error "Environment file $env_file not found"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

run_tests() {
    if [[ "$SKIP_TESTS" == "true" ]]; then
        log_warning "Skipping tests as requested"
        return 0
    fi
    
    log "Running tests before deployment..."
    
    cd "$PROJECT_ROOT"
    
    # Run linting
    if ! docker run --rm -v "$(pwd):/app" -w /app python:3.12-slim bash -c "pip install ruff && ruff check ."; then
        log_error "Linting failed"
        return 1
    fi
    
    # Run tests
    if ! docker-compose -f docker-compose.dev.yml run --rm nadia-api-dev python -m pytest tests/ -v; then
        log_error "Tests failed"
        return 1
    fi
    
    log_success "All tests passed"
}

backup_database() {
    if [[ "$SKIP_BACKUP" == "true" ]]; then
        log_warning "Skipping database backup as requested"
        return 0
    fi
    
    log "Creating database backup..."
    
    local backup_dir="$PROJECT_ROOT/backups"
    local backup_file="nadia_backup_${TIMESTAMP}.sql"
    
    mkdir -p "$backup_dir"
    
    # Create database backup
    if docker-compose exec -T postgres pg_dump -U postgres nadia_hitl > "$backup_dir/$backup_file"; then
        log_success "Database backup created: $backup_file"
        
        # Compress backup
        gzip "$backup_dir/$backup_file"
        log_success "Backup compressed: ${backup_file}.gz"
        
        # Keep only last 10 backups
        cd "$backup_dir"
        ls -t nadia_backup_*.sql.gz | tail -n +11 | xargs -r rm
        log "Cleaned up old backups (keeping last 10)"
    else
        log_error "Database backup failed"
        return 1
    fi
}

build_images() {
    log "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Set build arguments
    local build_version="${BUILD_VERSION:-latest}"
    local build_commit="${BUILD_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')}"
    local build_date="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    
    log "Build version: $build_version"
    log "Build commit: $build_commit"
    log "Build date: $build_date"
    
    # Build images
    if docker-compose -f "$COMPOSE_FILE" build \
        --build-arg BUILD_VERSION="$build_version" \
        --build-arg BUILD_COMMIT="$build_commit" \
        --build-arg BUILD_DATE="$build_date"; then
        log_success "Docker images built successfully"
    else
        log_error "Docker image build failed"
        return 1
    fi
}

deploy_services() {
    log "Deploying services..."
    
    cd "$PROJECT_ROOT"
    
    # Stop existing services gracefully
    log "Stopping existing services..."
    docker-compose -f "$COMPOSE_FILE" down --timeout 30
    
    # Start infrastructure services first
    log "Starting infrastructure services..."
    docker-compose -f "$COMPOSE_FILE" up -d postgres redis
    
    # Wait for infrastructure to be ready
    log "Waiting for infrastructure services..."
    sleep 10
    
    # Start application services
    log "Starting application services..."
    docker-compose -f "$COMPOSE_FILE" up -d nadia-bot nadia-api nadia-dashboard nadia-worker
    
    # Start monitoring services
    log "Starting monitoring services..."
    docker-compose -f "$COMPOSE_FILE" up -d prometheus grafana nginx
    
    log_success "All services started"
}

wait_for_health() {
    log "Performing health checks..."
    
    local start_time=$(date +%s)
    local timeout_time=$((start_time + TIMEOUT))
    
    local services=("nadia-api:8000/health" "nadia-dashboard:3000")
    
    for service in "${services[@]}"; do
        local service_name="${service%%:*}"
        local health_url="http://${service}"
        
        log "Checking health of $service_name..."
        
        while true; do
            local current_time=$(date +%s)
            
            if [[ $current_time -gt $timeout_time ]]; then
                log_error "Health check timeout for $service_name"
                return 1
            fi
            
            if docker-compose exec -T nadia-api curl -f -s "$health_url" > /dev/null 2>&1; then
                log_success "$service_name is healthy"
                break
            fi
            
            log "Waiting for $service_name to be ready..."
            sleep 5
        done
    done
    
    log_success "All health checks passed"
}

show_deployment_status() {
    log "Deployment Status:"
    echo
    
    # Show running containers
    log "Running containers:"
    docker-compose -f "$COMPOSE_FILE" ps
    echo
    
    # Show resource usage
    log "Resource usage:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
    echo
    
    # Show access URLs
    log "Access URLs:"
    echo "  Dashboard: http://localhost:3000"
    echo "  API: http://localhost:8000"
    echo "  Monitoring: http://localhost:3001"
    echo "  API Documentation: http://localhost:8000/docs"
    echo
}

rollback() {
    log_error "Deployment failed. Initiating rollback..."
    
    # Stop failed deployment
    docker-compose -f "$COMPOSE_FILE" down --timeout 30
    
    # Restore database if backup exists
    local latest_backup=$(ls -t "$PROJECT_ROOT/backups"/nadia_backup_*.sql.gz 2>/dev/null | head -n1)
    if [[ -n "$latest_backup" && "$SKIP_BACKUP" != "true" ]]; then
        log "Restoring database from $latest_backup..."
        gunzip -c "$latest_backup" | docker-compose exec -T postgres psql -U postgres -d nadia_hitl
        log_success "Database restored"
    fi
    
    log_error "Rollback completed. Please check logs and fix issues before retrying."
    exit 1
}

cleanup() {
    log "Cleaning up..."
    
    # Remove unused Docker images
    docker image prune -f
    
    # Remove unused volumes (with confirmation)
    # docker volume prune -f
    
    log_success "Cleanup completed"
}

# ====================================================================
# Main Deployment Process
# ====================================================================

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -s|--skip-tests)
                SKIP_TESTS="true"
                shift
                ;;
            -b|--skip-backup)
                SKIP_BACKUP="true"
                shift
                ;;
            -t|--timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            -f|--compose-file)
                COMPOSE_FILE="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Validate environment
    if [[ "$ENVIRONMENT" != "production" && "$ENVIRONMENT" != "staging" ]]; then
        log_error "Invalid environment: $ENVIRONMENT (must be 'production' or 'staging')"
        exit 1
    fi
    
    # Update compose file for environment
    if [[ "$ENVIRONMENT" == "staging" ]]; then
        COMPOSE_FILE="docker-compose.staging.yml"
    fi
    
    log "Starting NADIA HITL deployment to $ENVIRONMENT environment"
    log "Compose file: $COMPOSE_FILE"
    log "Log file: $LOG_FILE"
    echo
    
    # Set trap for rollback on failure
    trap rollback ERR
    
    # Deployment steps
    check_prerequisites
    run_tests
    backup_database
    build_images
    deploy_services
    wait_for_health
    show_deployment_status
    cleanup
    
    # Remove trap
    trap - ERR
    
    log_success "Deployment completed successfully!"
    log "Deployment log saved to: $LOG_FILE"
}

# Run main function with all arguments
main "$@"