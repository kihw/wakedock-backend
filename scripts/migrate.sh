#!/bin/bash

# WakeDock Database Migration Script
# Handles database schema migrations and upgrades

set -euo pipefail

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
MIGRATION_DIR="src/wakedock/database/migrations"

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
Usage: $0 [COMMAND] [OPTIONS]

Database migration management for WakeDock.

COMMANDS:
    init            Initialize database with schema
    upgrade         Run pending migrations
    downgrade       Rollback last migration
    status          Show migration status
    create NAME     Create new migration file
    history         Show migration history
    backup          Backup database before migration
    help            Show this help message

OPTIONS:
    --force         Force operation without confirmation
    --dry-run       Show what would be done without executing
    --compose-file  Specify docker-compose file (default: docker-compose.prod.yml)

EXAMPLES:
    $0 init
    $0 upgrade
    $0 create add_user_preferences
    $0 status
    $0 backup && $0 upgrade

EOF
}

# Check if running on Windows (Git Bash/WSL)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    COMPOSE_CMD="docker-compose"
elif command -v wsl.exe &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Parse command line arguments
COMMAND=""
FORCE=false
DRY_RUN=false
MIGRATION_NAME=""

while [[ $# -gt 0 ]]; do
    case $1 in
        init|upgrade|downgrade|status|create|history|backup|help)
            COMMAND="$1"
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --compose-file)
            COMPOSE_FILE="$2"
            shift 2
            ;;
        -*)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            if [[ "$COMMAND" == "create" && -z "$MIGRATION_NAME" ]]; then
                MIGRATION_NAME="$1"
            else
                error "Unknown argument: $1"
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$COMMAND" ]]; then
    error "Command is required"
    usage
    exit 1
fi

if [[ "$COMMAND" == "help" ]]; then
    usage
    exit 0
fi

# Check if database service is running
check_database() {
    log "Checking database connection..."
    
    if ! $COMPOSE_CMD -f "$COMPOSE_FILE" ps | grep -q "db.*Up"; then
        error "Database service is not running. Please start it first:"
        echo "  $COMPOSE_CMD -f $COMPOSE_FILE up -d db"
        exit 1
    fi
    
    # Test connection
    if ! $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T db pg_isready -U wakedock >/dev/null 2>&1; then
        error "Cannot connect to database"
        exit 1
    fi
    
    success "Database connection OK"
}

# Initialize database
init_database() {
    log "Initializing database..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would initialize database with initial schema"
        return 0
    fi
    
    # Check if database already exists
    local tables_count=$($COMPOSE_CMD -f "$COMPOSE_FILE" exec -T db psql -U wakedock -d wakedock -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' \n' || echo "0")
    
    if [[ "$tables_count" -gt 0 ]] && [[ "$FORCE" != "true" ]]; then
        warn "Database already contains $tables_count tables"
        read -p "Are you sure you want to reinitialize? This will drop all data! (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log "Initialization cancelled"
            return 0
        fi
    fi
    
    # Run database initialization via CLI
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T api python -m wakedock.database.cli init; then
        success "Database initialized successfully"
    else
        error "Failed to initialize database"
        exit 1
    fi
}

# Upgrade database
upgrade_database() {
    log "Running database migrations..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would run pending migrations"
        # Show pending migrations
        show_pending_migrations
        return 0
    fi
    
    # Create backup before migration
    if [[ "$FORCE" != "true" ]]; then
        log "Creating backup before migration..."
        ./scripts/backup.sh --database-only || warn "Backup failed, but continuing with migration"
    fi
    
    # Run Alembic upgrade
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T api alembic upgrade head; then
        success "Database migrations completed"
        
        # Show current status
        show_migration_status
    else
        error "Migration failed"
        exit 1
    fi
}

# Downgrade database
downgrade_database() {
    log "Rolling back last migration..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would rollback the last migration"
        return 0
    fi
    
    if [[ "$FORCE" != "true" ]]; then
        warn "⚠️  This will rollback the last database migration and may cause data loss!"
        read -p "Are you sure you want to continue? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
            log "Rollback cancelled"
            return 0
        fi
    fi
    
    # Create backup before rollback
    log "Creating backup before rollback..."
    ./scripts/backup.sh --database-only || warn "Backup failed, but continuing with rollback"
    
    # Run Alembic downgrade
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T api alembic downgrade -1; then
        success "Migration rolled back successfully"
        show_migration_status
    else
        error "Rollback failed"
        exit 1
    fi
}

# Show migration status
show_migration_status() {
    log "Current migration status:"
    
    # Show current revision
    local current_revision=$($COMPOSE_CMD -f "$COMPOSE_FILE" exec -T api alembic current 2>/dev/null | head -1 || echo "unknown")
    log "Current revision: $current_revision"
    
    # Show pending migrations
    show_pending_migrations
}

# Show pending migrations
show_pending_migrations() {
    local pending=$($COMPOSE_CMD -f "$COMPOSE_FILE" exec -T api alembic heads 2>/dev/null || echo "")
    
    if [[ -n "$pending" ]]; then
        log "Pending migrations:"
        echo "$pending"
    else
        success "No pending migrations"
    fi
}

# Show migration history
show_migration_history() {
    log "Migration history:"
    
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T api alembic history --verbose; then
        success "Migration history displayed"
    else
        error "Failed to retrieve migration history"
        exit 1
    fi
}

# Create new migration
create_migration() {
    if [[ -z "$MIGRATION_NAME" ]]; then
        error "Migration name is required for create command"
        usage
        exit 1
    fi
    
    log "Creating new migration: $MIGRATION_NAME"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would create migration: $MIGRATION_NAME"
        return 0
    fi
    
    # Generate migration with Alembic
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T api alembic revision --autogenerate -m "$MIGRATION_NAME"; then
        success "Migration created: $MIGRATION_NAME"
        
        # Show the created file
        local migration_file=$($COMPOSE_CMD -f "$COMPOSE_FILE" exec -T api find /app/src/wakedock/database/migrations/versions -name "*.py" -newer /tmp/migration_marker 2>/dev/null | head -1 || echo "")
        if [[ -n "$migration_file" ]]; then
            log "Migration file: $migration_file"
            warn "Please review the generated migration before applying it"
        fi
    else
        error "Failed to create migration"
        exit 1
    fi
}

# Backup database
backup_database() {
    log "Creating database backup..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would create database backup"
        return 0
    fi
    
    local backup_file="db_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    if $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T db pg_dump -U wakedock wakedock > "$backup_file"; then
        success "Database backup created: $backup_file"
        
        # Compress backup
        gzip "$backup_file"
        success "Backup compressed: ${backup_file}.gz"
    else
        error "Failed to create database backup"
        exit 1
    fi
}

# Validate migrations
validate_migrations() {
    log "Validating migration files..."
    
    # Check migration directory exists
    if [[ ! -d "$MIGRATION_DIR" ]]; then
        error "Migration directory not found: $MIGRATION_DIR"
        exit 1
    fi
    
    # Check Alembic configuration
    if [[ ! -f "alembic.ini" ]]; then
        error "Alembic configuration not found: alembic.ini"
        exit 1
    fi
    
    # Validate migration syntax
    local migration_errors=0
    for migration_file in "$MIGRATION_DIR"/versions/*.py; do
        if [[ -f "$migration_file" ]]; then
            if ! python3 -m py_compile "$migration_file" 2>/dev/null; then
                error "Syntax error in migration: $(basename "$migration_file")"
                ((migration_errors++))
            fi
        fi
    done
    
    if [[ $migration_errors -eq 0 ]]; then
        success "All migration files are valid"
    else
        error "Found $migration_errors migration files with syntax errors"
        exit 1
    fi
}

# Main execution
main() {
    case "$COMMAND" in
        init)
            check_database
            init_database
            ;;
        upgrade)
            check_database
            validate_migrations
            upgrade_database
            ;;
        downgrade)
            check_database
            downgrade_database
            ;;
        status)
            check_database
            show_migration_status
            ;;
        create)
            check_database
            create_migration
            ;;
        history)
            check_database
            show_migration_history
            ;;
        backup)
            check_database
            backup_database
            ;;
        *)
            error "Unknown command: $COMMAND"
            usage
            exit 1
            ;;
    esac
}

# Execute main function
main

exit 0
