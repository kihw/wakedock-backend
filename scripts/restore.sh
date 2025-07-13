#!/bin/bash

# WakeDock Restore Script
# Restores database, configuration, and volumes from backup

set -euo pipefail

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
RESTORE_TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

usage() {
    cat << EOF
Usage: $0 [OPTIONS] BACKUP_FILE

Restore WakeDock from backup archive.

OPTIONS:
    --verify            Verify backup integrity without restoring
    --force            Force restore without confirmation
    --database-only    Restore only the database
    --config-only      Restore only configuration files
    --no-restart       Don't restart services after restore
    --help             Show this help message

EXAMPLES:
    $0 backups/wakedock_backup_20240101_120000.tar.gz
    $0 --verify backups/wakedock_backup_20240101_120000.tar.gz
    $0 --database-only --force backup.tar.gz

EOF
}

# Parse command line arguments
VERIFY_ONLY=false
FORCE_RESTORE=false
DATABASE_ONLY=false
CONFIG_ONLY=false
NO_RESTART=false
BACKUP_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --verify)
            VERIFY_ONLY=true
            shift
            ;;
        --force)
            FORCE_RESTORE=true
            shift
            ;;
        --database-only)
            DATABASE_ONLY=true
            shift
            ;;
        --config-only)
            CONFIG_ONLY=true
            shift
            ;;
        --no-restart)
            NO_RESTART=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        -*)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            BACKUP_FILE="$1"
            shift
            ;;
    esac
done

if [[ -z "$BACKUP_FILE" ]]; then
    error "Backup file is required"
    usage
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Check if running on Windows (Git Bash/WSL)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    COMPOSE_CMD="docker-compose"
elif command -v wsl.exe &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Extract backup archive
TEMP_DIR="./temp_restore_${RESTORE_TIMESTAMP}"
log "Extracting backup archive..."

mkdir -p "$TEMP_DIR"
if [[ "$BACKUP_FILE" == *.tar.gz ]]; then
    tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR" --strip-components=1
elif [[ "$BACKUP_FILE" == *.zip ]]; then
    unzip -q "$BACKUP_FILE" -d "$TEMP_DIR"
else
    error "Unsupported backup format. Expected .tar.gz or .zip"
    exit 1
fi

success "Backup extracted to: $TEMP_DIR"

# Verify backup integrity
verify_backup() {
    log "Verifying backup integrity..."
    
    local errors=0
    
    # Check required files
    local required_files=(
        "backup_info.json"
        "database_backup.sql.gz"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$TEMP_DIR/$file" ]]; then
            error "Missing required file: $file"
            ((errors++))
        fi
    done
    
    # Check backup metadata
    if [[ -f "$TEMP_DIR/backup_info.json" ]]; then
        if ! python3 -m json.tool "$TEMP_DIR/backup_info.json" > /dev/null 2>&1; then
            error "Invalid backup metadata format"
            ((errors++))
        else
            local backup_info=$(cat "$TEMP_DIR/backup_info.json")
            log "Backup Information:"
            echo "$backup_info" | python3 -m json.tool
        fi
    fi
    
    # Check database backup
    if [[ -f "$TEMP_DIR/database_backup.sql.gz" ]]; then
        if ! gzip -t "$TEMP_DIR/database_backup.sql.gz"; then
            error "Database backup is corrupted"
            ((errors++))
        else
            success "Database backup verified"
        fi
    fi
    
    # Check configuration files
    if [[ -d "$TEMP_DIR/config" ]]; then
        success "Configuration backup found"
    else
        warn "No configuration backup found"
    fi
    
    # Check volume backups
    if [[ -d "$TEMP_DIR/volumes" ]]; then
        local volume_count=$(ls "$TEMP_DIR/volumes"/*.tar.gz 2>/dev/null | wc -l || echo 0)
        log "Found $volume_count volume backups"
    else
        warn "No volume backups found"
    fi
    
    if [[ $errors -eq 0 ]]; then
        success "Backup verification completed successfully"
        return 0
    else
        error "Backup verification failed with $errors errors"
        return 1
    fi
}

# Run verification
if ! verify_backup; then
    error "Backup verification failed"
    cleanup_temp
    exit 1
fi

if [[ "$VERIFY_ONLY" == "true" ]]; then
    log "Verification complete. Backup is valid."
    cleanup_temp
    exit 0
fi

# Confirmation prompt
if [[ "$FORCE_RESTORE" != "true" ]]; then
    echo
    warn "⚠️  WARNING: This will restore WakeDock from backup and may overwrite existing data!"
    echo
    
    if [[ -f "$TEMP_DIR/backup_info.json" ]]; then
        local backup_date=$(python3 -c "import json; print(json.load(open('$TEMP_DIR/backup_info.json'))['date'])" 2>/dev/null || echo "unknown")
        echo "Backup date: $backup_date"
    fi
    
    echo "Current services will be stopped and data will be replaced."
    echo
    read -p "Are you sure you want to continue? (yes/no): " -r
    
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log "Restore cancelled by user"
        cleanup_temp
        exit 0
    fi
fi

cleanup_temp() {
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}

# Stop services
if [[ "$NO_RESTART" != "true" ]]; then
    log "Stopping WakeDock services..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" down || warn "Some services may not have been running"
fi

# Restore database
restore_database() {
    log "Restoring database..."
    
    # Start only database service
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d db
    
    # Wait for database to be ready
    log "Waiting for database to be ready..."
    for i in {1..30}; do
        if $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T db pg_isready -U wakedock; then
            break
        fi
        if [[ $i -eq 30 ]]; then
            error "Database failed to start within 30 seconds"
            return 1
        fi
        sleep 1
    done
    
    # Drop existing database and recreate
    log "Recreating database..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T db psql -U wakedock -d postgres -c "DROP DATABASE IF EXISTS wakedock;"
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T db psql -U wakedock -d postgres -c "CREATE DATABASE wakedock;"
    
    # Restore from backup
    log "Importing database backup..."
    if gunzip -c "$TEMP_DIR/database_backup.sql.gz" | $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T db psql -U wakedock -d wakedock; then
        success "Database restored successfully"
    else
        error "Failed to restore database"
        return 1
    fi
}

# Restore configuration
restore_config() {
    log "Restoring configuration..."
    
    if [[ -d "$TEMP_DIR/config" ]]; then
        # Backup current configuration
        if [[ -f ".env" ]]; then
            cp .env ".env.backup.${RESTORE_TIMESTAMP}"
            log "Current .env backed up to .env.backup.${RESTORE_TIMESTAMP}"
        fi
        
        # Restore configuration files
        if [[ -f "$TEMP_DIR/config/.env" ]]; then
            cp "$TEMP_DIR/config/.env" .env
            success "Environment configuration restored"
        fi
        
        if [[ -d "$TEMP_DIR/config/caddy" ]]; then
            cp -r "$TEMP_DIR/config/caddy"/* caddy/ 2>/dev/null || warn "Failed to restore Caddy configuration"
            success "Caddy configuration restored"
        fi
        
        if [[ -d "$TEMP_DIR/config/app_config" ]]; then
            cp -r "$TEMP_DIR/config/app_config"/* config/ 2>/dev/null || warn "Failed to restore app configuration"
            success "Application configuration restored"
        fi
    else
        warn "No configuration backup found to restore"
    fi
}

# Restore volumes
restore_volumes() {
    log "Restoring volumes..."
    
    if [[ -d "$TEMP_DIR/volumes" ]]; then
        for volume_backup in "$TEMP_DIR/volumes"/*.tar.gz; do
            if [[ -f "$volume_backup" ]]; then
                local volume_name=$(basename "$volume_backup" .tar.gz)
                log "Restoring volume: $volume_name"
                
                # Remove existing volume
                docker volume rm "$volume_name" 2>/dev/null || true
                
                # Create new volume and restore data
                docker volume create "$volume_name"
                docker run --rm \
                    -v "$volume_name:/restore" \
                    -v "$(pwd)/$volume_backup:/backup.tar.gz:ro" \
                    alpine:latest \
                    sh -c "cd /restore && tar -xzf /backup.tar.gz"
                
                success "Volume restored: $volume_name"
            fi
        done
    else
        warn "No volume backups found to restore"
    fi
}

# Perform restore based on options
if [[ "$CONFIG_ONLY" == "true" ]]; then
    restore_config
elif [[ "$DATABASE_ONLY" == "true" ]]; then
    restore_database
else
    # Full restore
    restore_config
    restore_database
    restore_volumes
fi

# Restart services
if [[ "$NO_RESTART" != "true" ]]; then
    log "Starting WakeDock services..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d
    
    # Wait for services to be healthy
    log "Waiting for services to start..."
    sleep 10
    
    # Health check
    log "Performing health check..."
    for i in {1..30}; do
        if curl -sf http://localhost:8000/api/v1/system/health > /dev/null 2>&1; then
            success "Services are healthy"
            break
        fi
        if [[ $i -eq 30 ]]; then
            warn "Health check timeout - services may still be starting"
        fi
        sleep 2
    done
fi

# Cleanup
cleanup_temp

# Generate restore report
cat > "restore_report_${RESTORE_TIMESTAMP}.txt" << EOF
WakeDock Restore Report
======================
Restore Date: $(date)
Backup File: $BACKUP_FILE
Status: SUCCESS

Restored Components:
$(if [[ "$CONFIG_ONLY" != "true" && "$DATABASE_ONLY" != "true" ]] || [[ "$DATABASE_ONLY" == "true" ]]; then echo "- Database: ✓"; fi)
$(if [[ "$CONFIG_ONLY" != "true" && "$DATABASE_ONLY" != "true" ]] || [[ "$CONFIG_ONLY" == "true" ]]; then echo "- Configuration: ✓"; fi)
$(if [[ "$CONFIG_ONLY" != "true" && "$DATABASE_ONLY" != "true" ]]; then echo "- Volumes: ✓"; fi)

Next Steps:
1. Verify all services are running: docker-compose ps
2. Test functionality through the dashboard
3. Check logs for any errors: docker-compose logs
4. Update any changed configuration as needed

Service Status:
$(docker-compose -f "$COMPOSE_FILE" ps 2>/dev/null || echo "Unable to check service status")
EOF

success "Restore completed successfully!"
success "Report: restore_report_${RESTORE_TIMESTAMP}.txt"

# Send notification if configured
if [[ -n "${RESTORE_WEBHOOK_URL:-}" ]]; then
    curl -X POST "${RESTORE_WEBHOOK_URL}" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"✅ WakeDock restore completed from: $(basename "$BACKUP_FILE")\"}" \
        > /dev/null 2>&1 || warn "Failed to send notification"
fi

log "Restore Summary:"
echo "  - Backup: $(basename "$BACKUP_FILE")"
echo "  - Components: $(if [[ "$DATABASE_ONLY" == "true" ]]; then echo "Database only"; elif [[ "$CONFIG_ONLY" == "true" ]]; then echo "Configuration only"; else echo "Full restore"; fi)"
echo "  - Report: restore_report_${RESTORE_TIMESTAMP}.txt"

exit 0
