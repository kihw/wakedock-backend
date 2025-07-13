#!/bin/bash

# WakeDock Backup Script
# Creates comprehensive backups of database, configuration, and volumes

set -euo pipefail

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="wakedock_backup_${TIMESTAMP}"
COMPOSE_FILE="docker-compose.prod.yml"

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

# Check if running on Windows (Git Bash/WSL)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    # Windows paths
    BACKUP_DIR="./backups"
    COMPOSE_CMD="docker-compose"
elif command -v wsl.exe &> /dev/null; then
    # WSL
    COMPOSE_CMD="docker-compose"
else
    # Linux/macOS
    COMPOSE_CMD="docker-compose"
fi

# Create backup directory
mkdir -p "${BACKUP_DIR}/${BACKUP_NAME}"
cd "${BACKUP_DIR}/${BACKUP_NAME}"

log "Starting WakeDock backup: ${BACKUP_NAME}"

# Check if services are running
if ! ${COMPOSE_CMD} -f "../../${COMPOSE_FILE}" ps | grep -q "Up"; then
    error "WakeDock services are not running. Please start them first."
    exit 1
fi

# 1. Database backup
log "Creating database backup..."
if ${COMPOSE_CMD} -f "../../${COMPOSE_FILE}" exec -T db pg_dump -U wakedock wakedock > database_backup.sql; then
    success "Database backup created: database_backup.sql"
else
    error "Failed to create database backup"
    exit 1
fi

# Compress database backup
gzip database_backup.sql
success "Database backup compressed: database_backup.sql.gz"

# 2. Configuration backup
log "Creating configuration backup..."
mkdir -p config
cp -r ../../.env config/ 2>/dev/null || warn ".env file not found"
cp -r ../../docker-compose*.yml config/ 2>/dev/null || warn "Docker compose files not found"
cp -r ../../caddy/ config/ 2>/dev/null || warn "Caddy configuration not found"
cp -r ../../config/ config/app_config/ 2>/dev/null || warn "App configuration not found"
success "Configuration backup created"

# 3. Application data backup
log "Creating application data backup..."
mkdir -p volumes

# Backup named volumes
VOLUMES=$(${COMPOSE_CMD} -f "../../${COMPOSE_FILE}" config --volumes)
for volume in $VOLUMES; do
    log "Backing up volume: $volume"
    
    # Create temporary container to access volume
    docker run --rm \
        -v "${volume}:/source:ro" \
        -v "$(pwd)/volumes:/backup" \
        alpine:latest \
        tar -czf "/backup/${volume}.tar.gz" -C /source . || warn "Failed to backup volume: $volume"
done

# 4. Secrets backup (if using Docker secrets)
log "Creating secrets backup..."
mkdir -p secrets
if docker secret ls --format "table {{.Name}}" | grep -q wakedock; then
    docker secret ls --format "{{.Name}}" | grep wakedock > secrets/secret_names.txt
    warn "Secrets names saved. Manual intervention required for secret values."
else
    echo "No Docker secrets found" > secrets/no_secrets.txt
fi

# 5. Create backup metadata
log "Creating backup metadata..."
cat > backup_info.json << EOF
{
    "backup_name": "${BACKUP_NAME}",
    "timestamp": "${TIMESTAMP}",
    "date": "$(date -Iseconds)",
    "version": "$(${COMPOSE_CMD} -f "../../${COMPOSE_FILE}" exec -T api python -c "import wakedock; print(wakedock.__version__)" 2>/dev/null || echo "unknown")",
    "docker_version": "$(docker version --format '{{.Server.Version}}')",
    "compose_version": "$(${COMPOSE_CMD} version --short)",
    "host": "$(hostname)",
    "user": "$(whoami)",
    "services": $(${COMPOSE_CMD} -f "../../${COMPOSE_FILE}" ps --services --format json 2>/dev/null || echo "[]"),
    "volumes": [$(echo "$VOLUMES" | sed 's/^/"/;s/$/"/' | tr '\n' ',' | sed 's/,$//')],
    "backup_size": "$(du -sh . | cut -f1)"
}
EOF

# 6. Health check before backup completion
log "Performing health check..."
if curl -sf http://localhost:8000/api/v1/system/health > health_check.json; then
    success "Health check completed"
else
    warn "Health check failed - backup may be from unhealthy state"
    echo '{"status": "failed", "error": "Could not connect to API"}' > health_check.json
fi

# 7. Create backup archive
cd ..
log "Creating backup archive..."
if command -v tar &> /dev/null; then
    tar -czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}/"
    ARCHIVE_SIZE=$(du -sh "${BACKUP_NAME}.tar.gz" | cut -f1)
    success "Backup archive created: ${BACKUP_NAME}.tar.gz (${ARCHIVE_SIZE})"
    
    # Cleanup uncompressed backup
    rm -rf "${BACKUP_NAME}/"
else
    warn "tar not available, keeping uncompressed backup directory"
fi

# 8. Cleanup old backups (keep last 7 days)
log "Cleaning up old backups..."
find . -name "wakedock_backup_*.tar.gz" -mtime +7 -delete 2>/dev/null || true
find . -type d -name "wakedock_backup_*" -mtime +7 -exec rm -rf {} + 2>/dev/null || true

# 9. Optional: Upload to cloud storage
if [[ "${BACKUP_UPLOAD:-false}" == "true" ]]; then
    log "Uploading backup to cloud storage..."
    
    if [[ -n "${AWS_S3_BUCKET:-}" ]]; then
        aws s3 cp "${BACKUP_NAME}.tar.gz" "s3://${AWS_S3_BUCKET}/wakedock-backups/"
        success "Backup uploaded to S3"
    elif [[ -n "${RSYNC_DESTINATION:-}" ]]; then
        rsync -av "${BACKUP_NAME}.tar.gz" "${RSYNC_DESTINATION}/"
        success "Backup uploaded via rsync"
    else
        warn "Cloud upload enabled but no destination configured"
    fi
fi

# 10. Generate backup report
cd ..
cat > "backup_report_${TIMESTAMP}.txt" << EOF
WakeDock Backup Report
=====================
Backup Name: ${BACKUP_NAME}
Date: $(date)
Status: SUCCESS

Contents:
- Database backup: ✓
- Configuration backup: ✓
- Volume backups: ✓
- Metadata: ✓
- Health check: ✓

Files:
$(ls -la "backups/${BACKUP_NAME}"* 2>/dev/null || echo "Archive not found")

Next Steps:
1. Verify backup integrity: ./scripts/restore.sh --verify "backups/${BACKUP_NAME}.tar.gz"
2. Test restore in development environment
3. Store backup securely offsite

For restore instructions, see: docs/deployment.md#backup-and-recovery
EOF

success "Backup completed successfully!"
success "Backup location: $(pwd)/backups/${BACKUP_NAME}.tar.gz"
success "Report: backup_report_${TIMESTAMP}.txt"

log "Backup Summary:"
echo "  - Database: $(ls -lh backups/${BACKUP_NAME}.tar.gz 2>/dev/null | awk '{print $5}' || echo 'N/A')"
echo "  - Total size: $(du -sh backups/${BACKUP_NAME}* 2>/dev/null | head -1 | cut -f1 || echo 'N/A')"
echo "  - Location: backups/${BACKUP_NAME}.tar.gz"

# Send notification if configured
if [[ -n "${BACKUP_WEBHOOK_URL:-}" ]]; then
    curl -X POST "${BACKUP_WEBHOOK_URL}" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"✅ WakeDock backup completed: ${BACKUP_NAME}\"}" \
        > /dev/null 2>&1 || warn "Failed to send notification"
fi

exit 0
