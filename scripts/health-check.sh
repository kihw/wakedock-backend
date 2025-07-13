#!/bin/bash

# WakeDock Health Check Script
# Comprehensive health monitoring for all WakeDock components

set -euo pipefail

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
TIMEOUT=30
ALERT_THRESHOLD=3
WEBHOOK_URL="${HEALTH_WEBHOOK_URL:-}"
EMAIL_ALERT="${HEALTH_EMAIL_ALERT:-}"

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
Usage: $0 [OPTIONS]

Comprehensive health check for WakeDock services.

OPTIONS:
    --timeout SECONDS   Timeout for health checks (default: 30)
    --alert-threshold N Number of failures before alerting (default: 3)
    --webhook URL       Webhook URL for notifications
    --email EMAIL       Email address for alerts
    --continuous        Run continuously with 60s intervals
    --quiet             Suppress success messages
    --json              Output results in JSON format
    --help              Show this help message

EXAMPLES:
    $0                                    # Single health check
    $0 --continuous                       # Continuous monitoring
    $0 --json > health-status.json       # JSON output
    $0 --webhook https://hooks.slack.com/... # With notifications

EOF
}

# Global variables
CONTINUOUS=false
QUIET=false
JSON_OUTPUT=false
FAILURE_COUNT=0
LAST_CHECK_TIME=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --alert-threshold)
            ALERT_THRESHOLD="$2"
            shift 2
            ;;
        --webhook)
            WEBHOOK_URL="$2"
            shift 2
            ;;
        --email)
            EMAIL_ALERT="$2"
            shift 2
            ;;
        --continuous)
            CONTINUOUS=true
            shift
            ;;
        --quiet)
            QUIET=true
            shift
            ;;
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Check if running on Windows (Git Bash/WSL)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    COMPOSE_CMD="docker-compose"
elif command -v wsl.exe &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Health check results storage
declare -A HEALTH_RESULTS
declare -A SERVICE_STATUS
declare -A RESPONSE_TIMES

# Individual health check functions
check_docker_daemon() {
    local start_time=$(date +%s.%N)
    
    if docker info >/dev/null 2>&1; then
        HEALTH_RESULTS["docker"]="healthy"
        local end_time=$(date +%s.%N)
        RESPONSE_TIMES["docker"]=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
        return 0
    else
        HEALTH_RESULTS["docker"]="unhealthy"
        RESPONSE_TIMES["docker"]="timeout"
        return 1
    fi
}

check_database() {
    local start_time=$(date +%s.%N)
    
    if timeout "$TIMEOUT" $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T db pg_isready -U wakedock >/dev/null 2>&1; then
        # Test actual connection
        if timeout "$TIMEOUT" $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T db psql -U wakedock -d wakedock -c "SELECT 1;" >/dev/null 2>&1; then
            HEALTH_RESULTS["database"]="healthy"
            local end_time=$(date +%s.%N)
            RESPONSE_TIMES["database"]=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
            return 0
        fi
    fi
    
    HEALTH_RESULTS["database"]="unhealthy"
    RESPONSE_TIMES["database"]="timeout"
    return 1
}

check_api() {
    local start_time=$(date +%s.%N)
    local api_url="http://localhost:8000"
    
    # Check if API is accessible via docker network
    if timeout "$TIMEOUT" $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T caddy wget -q -O- --timeout="$TIMEOUT" http://api:8000/api/v1/system/health >/dev/null 2>&1; then
        HEALTH_RESULTS["api"]="healthy"
        local end_time=$(date +%s.%N)
        RESPONSE_TIMES["api"]=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
        return 0
    elif timeout "$TIMEOUT" curl -sf "$api_url/api/v1/system/health" >/dev/null 2>&1; then
        HEALTH_RESULTS["api"]="healthy"
        local end_time=$(date +%s.%N)
        RESPONSE_TIMES["api"]=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
        return 0
    else
        HEALTH_RESULTS["api"]="unhealthy"
        RESPONSE_TIMES["api"]="timeout"
        return 1
    fi
}

check_caddy() {
    local start_time=$(date +%s.%N)
    local caddy_admin="http://localhost:2019"
    
    if timeout "$TIMEOUT" curl -sf "$caddy_admin/config/" >/dev/null 2>&1; then
        HEALTH_RESULTS["caddy"]="healthy"
        local end_time=$(date +%s.%N)
        RESPONSE_TIMES["caddy"]=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
        return 0
    else
        HEALTH_RESULTS["caddy"]="unhealthy"
        RESPONSE_TIMES["caddy"]="timeout"
        return 1
    fi
}

check_dashboard() {
    local start_time=$(date +%s.%N)
    local dashboard_url="http://localhost:3000"
    
    if timeout "$TIMEOUT" curl -sf "$dashboard_url" >/dev/null 2>&1; then
        HEALTH_RESULTS["dashboard"]="healthy"
        local end_time=$(date +%s.%N)
        RESPONSE_TIMES["dashboard"]=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
        return 0
    else
        HEALTH_RESULTS["dashboard"]="unhealthy"
        RESPONSE_TIMES["dashboard"]="timeout"
        return 1
    fi
}

check_redis() {
    local start_time=$(date +%s.%N)
    
    if timeout "$TIMEOUT" $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T redis redis-cli ping >/dev/null 2>&1; then
        HEALTH_RESULTS["redis"]="healthy"
        local end_time=$(date +%s.%N)
        RESPONSE_TIMES["redis"]=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
        return 0
    else
        HEALTH_RESULTS["redis"]="unhealthy"
        RESPONSE_TIMES["redis"]="timeout"
        return 1
    fi
}

check_containers() {
    local services=("api" "db" "caddy" "dashboard" "redis")
    
    for service in "${services[@]}"; do
        local status=$($COMPOSE_CMD -f "$COMPOSE_FILE" ps -q "$service" 2>/dev/null | xargs docker inspect --format='{{.State.Status}}' 2>/dev/null || echo "not_found")
        SERVICE_STATUS["$service"]="$status"
    done
}

check_system_resources() {
    # Check disk space
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ "$disk_usage" -gt 90 ]]; then
        HEALTH_RESULTS["disk_space"]="critical"
    elif [[ "$disk_usage" -gt 80 ]]; then
        HEALTH_RESULTS["disk_space"]="warning"
    else
        HEALTH_RESULTS["disk_space"]="healthy"
    fi
    
    # Check memory usage
    local memory_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    if [[ "$memory_usage" -gt 90 ]]; then
        HEALTH_RESULTS["memory"]="critical"
    elif [[ "$memory_usage" -gt 80 ]]; then
        HEALTH_RESULTS["memory"]="warning"
    else
        HEALTH_RESULTS["memory"]="healthy"
    fi
    
    # Check load average
    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    local cpu_cores=$(nproc)
    local load_percent=$(echo "scale=0; $load_avg * 100 / $cpu_cores" | bc -l 2>/dev/null || echo "0")
    
    if [[ "$load_percent" -gt 90 ]]; then
        HEALTH_RESULTS["load"]="critical"
    elif [[ "$load_percent" -gt 70 ]]; then
        HEALTH_RESULTS["load"]="warning"
    else
        HEALTH_RESULTS["load"]="healthy"
    fi
}

# Run all health checks
run_health_checks() {
    LAST_CHECK_TIME=$(date -Iseconds)
    
    if [[ "$QUIET" != "true" && "$JSON_OUTPUT" != "true" ]]; then
        log "Running comprehensive health checks..."
    fi
    
    # Check container status first
    check_containers
    
    # Run individual health checks
    check_docker_daemon
    check_database
    check_api
    check_caddy
    check_dashboard
    check_redis
    
    # Check system resources
    check_system_resources
}

# Generate health report
generate_report() {
    local overall_status="healthy"
    local failed_checks=0
    local warning_checks=0
    
    # Determine overall status
    for service in "${!HEALTH_RESULTS[@]}"; do
        case "${HEALTH_RESULTS[$service]}" in
            "unhealthy"|"critical")
                overall_status="unhealthy"
                ((failed_checks++))
                ;;
            "warning")
                if [[ "$overall_status" != "unhealthy" ]]; then
                    overall_status="warning"
                fi
                ((warning_checks++))
                ;;
        esac
    done
    
    if [[ "$JSON_OUTPUT" == "true" ]]; then
        generate_json_report "$overall_status" "$failed_checks" "$warning_checks"
    else
        generate_text_report "$overall_status" "$failed_checks" "$warning_checks"
    fi
    
    # Update failure count for alerting
    if [[ "$overall_status" == "unhealthy" ]]; then
        ((FAILURE_COUNT++))
    else
        FAILURE_COUNT=0
    fi
    
    return $failed_checks
}

generate_json_report() {
    local overall_status="$1"
    local failed_checks="$2"
    local warning_checks="$3"
    
    cat << EOF
{
    "timestamp": "$LAST_CHECK_TIME",
    "overall_status": "$overall_status",
    "failed_checks": $failed_checks,
    "warning_checks": $warning_checks,
    "services": {
EOF
    
    local first=true
    for service in "${!HEALTH_RESULTS[@]}"; do
        if [[ "$first" != "true" ]]; then
            echo ","
        fi
        first=false
        
        local response_time="${RESPONSE_TIMES[$service]:-0}"
        echo -n "        \"$service\": {\"status\": \"${HEALTH_RESULTS[$service]}\", \"response_time\": \"$response_time\"}"
    done
    
    echo ""
    echo "    },"
    echo "    \"containers\": {"
    
    first=true
    for service in "${!SERVICE_STATUS[@]}"; do
        if [[ "$first" != "true" ]]; then
            echo ","
        fi
        first=false
        echo -n "        \"$service\": \"${SERVICE_STATUS[$service]}\""
    done
    
    echo ""
    echo "    }"
    echo "}"
}

generate_text_report() {
    local overall_status="$1"
    local failed_checks="$2"
    local warning_checks="$3"
    
    if [[ "$QUIET" == "true" ]]; then
        if [[ "$overall_status" != "healthy" ]]; then
            echo "UNHEALTHY: $failed_checks failed, $warning_checks warnings"
        fi
        return
    fi
    
    echo
    echo "=========================="
    echo "WakeDock Health Report"
    echo "=========================="
    echo "Timestamp: $LAST_CHECK_TIME"
    echo "Overall Status: $overall_status"
    echo
    
    echo "Service Health:"
    echo "---------------"
    for service in docker database api caddy dashboard redis disk_space memory load; do
        if [[ -n "${HEALTH_RESULTS[$service]:-}" ]]; then
            local status="${HEALTH_RESULTS[$service]}"
            local response_time="${RESPONSE_TIMES[$service]:-N/A}"
            
            case "$status" in
                "healthy")
                    if [[ "$response_time" != "N/A" && "$response_time" != "0" ]]; then
                        printf "  %-12s: %s ✅ (%.3fs)\n" "$service" "$status" "$response_time"
                    else
                        printf "  %-12s: %s ✅\n" "$service" "$status"
                    fi
                    ;;
                "warning")
                    printf "  %-12s: %s ⚠️\n" "$service" "$status"
                    ;;
                *)
                    printf "  %-12s: %s ❌\n" "$service" "$status"
                    ;;
            esac
        fi
    done
    
    echo
    echo "Container Status:"
    echo "-----------------"
    for service in "${!SERVICE_STATUS[@]}"; do
        local status="${SERVICE_STATUS[$service]}"
        case "$status" in
            "running")
                printf "  %-12s: %s ✅\n" "$service" "$status"
                ;;
            "not_found")
                printf "  %-12s: %s ❓\n" "$service" "$status"
                ;;
            *)
                printf "  %-12s: %s ❌\n" "$service" "$status"
                ;;
        esac
    done
    
    if [[ "$failed_checks" -gt 0 || "$warning_checks" -gt 0 ]]; then
        echo
        echo "Summary: $failed_checks failed checks, $warning_checks warnings"
    else
        echo
        success "All systems healthy! 🎉"
    fi
    
    echo "=========================="
}

# Send notifications
send_notifications() {
    local overall_status="$1"
    local failed_checks="$2"
    
    if [[ "$overall_status" != "unhealthy" ]] || [[ "$FAILURE_COUNT" -lt "$ALERT_THRESHOLD" ]]; then
        return 0
    fi
    
    local message="🚨 WakeDock Health Alert: $failed_checks services are unhealthy"
    local detailed_message="Health check failed with $failed_checks unhealthy services:\n"
    
    for service in "${!HEALTH_RESULTS[@]}"; do
        if [[ "${HEALTH_RESULTS[$service]}" == "unhealthy" ]]; then
            detailed_message+="\n- $service: ${HEALTH_RESULTS[$service]}"
        fi
    done
    
    # Send webhook notification
    if [[ -n "$WEBHOOK_URL" ]]; then
        curl -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"text\": \"$message\", \"attachments\": [{\"text\": \"$(echo -e "$detailed_message")\"}]}" \
            >/dev/null 2>&1 || warn "Failed to send webhook notification"
    fi
    
    # Send email notification
    if [[ -n "$EMAIL_ALERT" ]] && command -v mail >/dev/null 2>&1; then
        echo -e "$detailed_message" | mail -s "WakeDock Health Alert" "$EMAIL_ALERT" || warn "Failed to send email notification"
    fi
}

# Main execution
main() {
    if [[ "$CONTINUOUS" == "true" ]]; then
        log "Starting continuous health monitoring..."
        
        while true; do
            run_health_checks
            local exit_code=0
            generate_report || exit_code=$?
            
            if [[ $exit_code -gt 0 ]]; then
                send_notifications "${HEALTH_RESULTS[*]}" "$exit_code"
            fi
            
            sleep 60
        done
    else
        run_health_checks
        local exit_code=0
        generate_report || exit_code=$?
        
        if [[ $exit_code -gt 0 ]]; then
            send_notifications "${HEALTH_RESULTS[*]}" "$exit_code"
        fi
        
        exit $exit_code
    fi
}

# Execute main function
main
