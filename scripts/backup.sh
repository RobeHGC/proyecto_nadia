#!/bin/bash
# NADIA HITL Automated Backup Script
# Comprehensive backup solution for database, configuration, and logs

set -euo pipefail

# ====================================================================
# Configuration
# ====================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default configuration
RETENTION_DAYS="${RETENTION_DAYS:-30}"
COMPRESS_BACKUPS="${COMPRESS_BACKUPS:-true}"
ENCRYPT_BACKUPS="${ENCRYPT_BACKUPS:-false}"
BACKUP_TYPE="${BACKUP_TYPE:-full}"
S3_UPLOAD="${S3_UPLOAD:-false}"

# ====================================================================
# Utility Functions
# ====================================================================

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗${NC} $1"
}

show_help() {
    cat << EOF
NADIA HITL Backup Script

Usage: $0 [OPTIONS]

Options:
    -t, --type TYPE           Backup type: full|database|config|logs [default: full]
    -d, --retention DAYS      Retention period in days [default: 30]
    -o, --output DIR          Backup output directory [default: ./backups]
    -c, --compress            Compress backups [default: true]
    -e, --encrypt             Encrypt backups with GPG [default: false]
    -s, --s3-upload           Upload to S3 after backup [default: false]
    -h, --help                Show this help message

Backup Types:
    full        Complete backup (database + config + logs)
    database    Database backup only
    config      Configuration files backup only
    logs        Log files backup only

Environment Variables:
    BACKUP_DIR              Custom backup directory
    RETENTION_DAYS          Backup retention period
    COMPRESS_BACKUPS        Enable/disable compression
    ENCRYPT_BACKUPS         Enable/disable encryption
    GPG_RECIPIENT           GPG recipient for encryption
    AWS_S3_BUCKET           S3 bucket for uploads
    AWS_PROFILE             AWS profile to use

Examples:
    # Full backup with 7-day retention
    $0 --type full --retention 7

    # Database backup only
    $0 --type database

    # Encrypted backup with S3 upload
    $0 --encrypt --s3-upload
EOF
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if running containers exist
    if ! docker-compose ps | grep -q nadia; then
        log_warning "NADIA containers not running. Some backups may be limited."
    fi
    
    # Check backup directory
    mkdir -p "$BACKUP_DIR"
    if [[ ! -w "$BACKUP_DIR" ]]; then
        log_error "Backup directory $BACKUP_DIR is not writable"
        exit 1
    fi
    
    # Check compression tools
    if [[ "$COMPRESS_BACKUPS" == "true" ]] && ! command -v gzip &> /dev/null; then
        log_error "gzip not found but compression is enabled"
        exit 1
    fi
    
    # Check encryption tools
    if [[ "$ENCRYPT_BACKUPS" == "true" ]] && ! command -v gpg &> /dev/null; then
        log_error "GPG not found but encryption is enabled"
        exit 1
    fi
    
    # Check S3 tools
    if [[ "$S3_UPLOAD" == "true" ]] && ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found but S3 upload is enabled"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

backup_database() {
    log "Backing up database..."
    
    local db_backup_file="$BACKUP_DIR/nadia_db_${TIMESTAMP}.sql"
    
    # Check if PostgreSQL container is running
    if docker-compose ps postgres | grep -q Up; then
        # Backup from running container
        if docker-compose exec -T postgres pg_dump -U postgres -d nadia_hitl > "$db_backup_file"; then
            log_success "Database backup created: $(basename "$db_backup_file")"
            
            # Add metadata
            cat << EOF >> "$db_backup_file"
-- Backup Metadata
-- Timestamp: $TIMESTAMP
-- Server: $(hostname)
-- Docker Image: $(docker-compose images postgres --format "{{.Image}}")
-- Database Size: $(docker-compose exec -T postgres psql -U postgres -d nadia_hitl -c "SELECT pg_size_pretty(pg_database_size('nadia_hitl'));" -t | xargs)
EOF
            
        else
            log_error "Database backup failed"
            return 1
        fi
    else
        log_warning "PostgreSQL container not running. Skipping database backup."
        return 0
    fi
    
    # Compress if enabled
    if [[ "$COMPRESS_BACKUPS" == "true" ]]; then
        gzip "$db_backup_file"
        db_backup_file="${db_backup_file}.gz"
        log_success "Database backup compressed"
    fi
    
    # Encrypt if enabled
    if [[ "$ENCRYPT_BACKUPS" == "true" ]]; then
        encrypt_file "$db_backup_file"
    fi
    
    echo "$db_backup_file"
}

backup_redis() {
    log "Backing up Redis data..."
    
    local redis_backup_file="$BACKUP_DIR/nadia_redis_${TIMESTAMP}.rdb"
    
    # Check if Redis container is running
    if docker-compose ps redis | grep -q Up; then
        # Save Redis data
        docker-compose exec -T redis redis-cli BGSAVE
        sleep 2
        
        # Copy RDB file
        if docker cp "$(docker-compose ps -q redis):/data/dump.rdb" "$redis_backup_file"; then
            log_success "Redis backup created: $(basename "$redis_backup_file")"
        else
            log_warning "Redis backup failed"
            return 1
        fi
    else
        log_warning "Redis container not running. Skipping Redis backup."
        return 0
    fi
    
    # Compress if enabled
    if [[ "$COMPRESS_BACKUPS" == "true" ]]; then
        gzip "$redis_backup_file"
        redis_backup_file="${redis_backup_file}.gz"
        log_success "Redis backup compressed"
    fi
    
    # Encrypt if enabled
    if [[ "$ENCRYPT_BACKUPS" == "true" ]]; then
        encrypt_file "$redis_backup_file"
    fi
    
    echo "$redis_backup_file"
}

backup_configuration() {
    log "Backing up configuration files..."
    
    local config_backup_file="$BACKUP_DIR/nadia_config_${TIMESTAMP}.tar"
    
    # Create list of config files
    local config_files=(
        ".env"
        ".env.production"
        ".env.staging"
        "docker-compose.yml"
        "docker-compose.dev.yml"
        "docker-compose.staging.yml"
        "nginx/nginx.conf"
        "monitoring/prometheus.yml"
        "monitoring/alert_rules.yml"
        "persona/"
        "database/migrations/"
    )
    
    # Create tar archive with existing files only
    cd "$PROJECT_ROOT"
    local existing_files=()
    for file in "${config_files[@]}"; do
        if [[ -e "$file" ]]; then
            existing_files+=("$file")
        fi
    done
    
    if [[ ${#existing_files[@]} -gt 0 ]]; then
        tar -cf "$config_backup_file" "${existing_files[@]}"
        log_success "Configuration backup created: $(basename "$config_backup_file")"
        
        # Add metadata file
        cat << EOF > "$BACKUP_DIR/config_metadata_${TIMESTAMP}.txt"
Configuration Backup Metadata
============================
Timestamp: $TIMESTAMP
Server: $(hostname)
Git Commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')
Git Branch: $(git branch --show-current 2>/dev/null || echo 'unknown')
Docker Version: $(docker --version)
Docker Compose Version: $(docker-compose --version)

Files Included:
$(printf '%s\n' "${existing_files[@]}")
EOF
        
    else
        log_warning "No configuration files found"
        return 0
    fi
    
    # Compress if enabled
    if [[ "$COMPRESS_BACKUPS" == "true" ]]; then
        gzip "$config_backup_file"
        config_backup_file="${config_backup_file}.gz"
        log_success "Configuration backup compressed"
    fi
    
    # Encrypt if enabled
    if [[ "$ENCRYPT_BACKUPS" == "true" ]]; then
        encrypt_file "$config_backup_file"
    fi
    
    echo "$config_backup_file"
}

backup_logs() {
    log "Backing up log files..."
    
    local logs_backup_file="$BACKUP_DIR/nadia_logs_${TIMESTAMP}.tar"
    
    # Create list of log directories
    local log_paths=(
        "logs/"
        "data/"
    )
    
    # Create tar archive with existing directories only
    cd "$PROJECT_ROOT"
    local existing_paths=()
    for path in "${log_paths[@]}"; do
        if [[ -d "$path" ]]; then
            existing_paths+=("$path")
        fi
    done
    
    if [[ ${#existing_paths[@]} -gt 0 ]]; then
        tar -cf "$logs_backup_file" "${existing_paths[@]}" 2>/dev/null || true
        log_success "Logs backup created: $(basename "$logs_backup_file")"
    else
        log_warning "No log directories found"
        return 0
    fi
    
    # Compress if enabled
    if [[ "$COMPRESS_BACKUPS" == "true" ]]; then
        gzip "$logs_backup_file"
        logs_backup_file="${logs_backup_file}.gz"
        log_success "Logs backup compressed"
    fi
    
    # Encrypt if enabled
    if [[ "$ENCRYPT_BACKUPS" == "true" ]]; then
        encrypt_file "$logs_backup_file"
    fi
    
    echo "$logs_backup_file"
}

encrypt_file() {
    local file="$1"
    
    if [[ -z "${GPG_RECIPIENT:-}" ]]; then
        log_error "GPG_RECIPIENT not set but encryption requested"
        return 1
    fi
    
    if gpg --trust-model always --encrypt -r "$GPG_RECIPIENT" "$file"; then
        rm "$file"  # Remove unencrypted file
        log_success "File encrypted: $(basename "$file").gpg"
        echo "${file}.gpg"
    else
        log_error "Encryption failed for $file"
        return 1
    fi
}

upload_to_s3() {
    local files=("$@")
    
    if [[ -z "${AWS_S3_BUCKET:-}" ]]; then
        log_error "AWS_S3_BUCKET not set but S3 upload requested"
        return 1
    fi
    
    log "Uploading backups to S3..."
    
    local aws_profile_arg=""
    if [[ -n "${AWS_PROFILE:-}" ]]; then
        aws_profile_arg="--profile $AWS_PROFILE"
    fi
    
    for file in "${files[@]}"; do
        if [[ -f "$file" ]]; then
            local s3_key="nadia-backups/$(basename "$file")"
            if aws s3 cp "$file" "s3://$AWS_S3_BUCKET/$s3_key" $aws_profile_arg; then
                log_success "Uploaded to S3: $s3_key"
            else
                log_error "Failed to upload $file to S3"
            fi
        fi
    done
}

cleanup_old_backups() {
    log "Cleaning up old backups (retention: $RETENTION_DAYS days)..."
    
    # Find and delete old backup files
    local deleted_count=0
    while IFS= read -r -d '' file; do
        if [[ -f "$file" ]]; then
            rm "$file"
            ((deleted_count++))
        fi
    done < <(find "$BACKUP_DIR" -name "nadia_*" -type f -mtime +$RETENTION_DAYS -print0 2>/dev/null)
    
    if [[ $deleted_count -gt 0 ]]; then
        log_success "Cleaned up $deleted_count old backup files"
    else
        log "No old backup files to clean up"
    fi
}

generate_backup_report() {
    local backup_files=("$@")
    
    log "Generating backup report..."
    
    local report_file="$BACKUP_DIR/backup_report_${TIMESTAMP}.txt"
    
    cat << EOF > "$report_file"
NADIA HITL Backup Report
========================
Date: $(date)
Backup Type: $BACKUP_TYPE
Server: $(hostname)
Script Version: 1.0

Backup Configuration:
- Retention Days: $RETENTION_DAYS
- Compression: $COMPRESS_BACKUPS
- Encryption: $ENCRYPT_BACKUPS
- S3 Upload: $S3_UPLOAD

Files Created:
EOF
    
    for file in "${backup_files[@]}"; do
        if [[ -f "$file" ]]; then
            local size=$(du -h "$file" | cut -f1)
            echo "- $(basename "$file") ($size)" >> "$report_file"
        fi
    done
    
    cat << EOF >> "$report_file"

System Status:
- Docker Containers: $(docker-compose ps --format "{{.Name}}" | wc -l) running
- Disk Usage: $(df -h "$BACKUP_DIR" | tail -n1 | awk '{print $5}') used
- Backup Directory Size: $(du -sh "$BACKUP_DIR" | cut -f1)

EOF
    
    log_success "Backup report generated: $(basename "$report_file")"
}

# ====================================================================
# Main Backup Process
# ====================================================================

main() {
    local backup_files=()
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -t|--type)
                BACKUP_TYPE="$2"
                shift 2
                ;;
            -d|--retention)
                RETENTION_DAYS="$2"
                shift 2
                ;;
            -o|--output)
                BACKUP_DIR="$2"
                shift 2
                ;;
            -c|--compress)
                COMPRESS_BACKUPS="true"
                shift
                ;;
            -e|--encrypt)
                ENCRYPT_BACKUPS="true"
                shift
                ;;
            -s|--s3-upload)
                S3_UPLOAD="true"
                shift
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
    
    # Validate backup type
    if [[ ! "$BACKUP_TYPE" =~ ^(full|database|config|logs)$ ]]; then
        log_error "Invalid backup type: $BACKUP_TYPE"
        exit 1
    fi
    
    log "Starting NADIA HITL backup ($BACKUP_TYPE)"
    log "Backup directory: $BACKUP_DIR"
    log "Retention: $RETENTION_DAYS days"
    echo
    
    check_prerequisites
    
    # Perform backup based on type
    case $BACKUP_TYPE in
        "full")
            log "Performing full backup..."
            backup_files+=($(backup_database))
            backup_files+=($(backup_redis))
            backup_files+=($(backup_configuration))
            backup_files+=($(backup_logs))
            ;;
        "database")
            backup_files+=($(backup_database))
            backup_files+=($(backup_redis))
            ;;
        "config")
            backup_files+=($(backup_configuration))
            ;;
        "logs")
            backup_files+=($(backup_logs))
            ;;
    esac
    
    # Upload to S3 if requested
    if [[ "$S3_UPLOAD" == "true" ]]; then
        upload_to_s3 "${backup_files[@]}"
    fi
    
    # Generate report
    generate_backup_report "${backup_files[@]}"
    
    # Cleanup old backups
    cleanup_old_backups
    
    log_success "Backup completed successfully!"
    log "Backup files created: ${#backup_files[@]}"
    for file in "${backup_files[@]}"; do
        if [[ -f "$file" ]]; then
            local size=$(du -h "$file" | cut -f1)
            log "  - $(basename "$file") ($size)"
        fi
    done
}

# Run main function with all arguments
main "$@"