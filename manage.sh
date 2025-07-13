#!/bin/bash

# WakeDock Setup and Management Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}🐳 WakeDock Management Script${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_requirements() {
    print_header
    echo "Checking requirements..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
    
    print_success "Requirements check passed"
}

setup_env() {
    if [ ! -f .env ]; then
        print_warning ".env file not found"
        if [ -f .env.example ]; then
            echo "Copying .env.example to .env..."
            cp .env.example .env
            print_success "Created .env file from example"
            print_warning "Please edit .env file with your configuration"
        else
            print_error ".env.example not found"
            exit 1
        fi
    else
        print_success ".env file exists"
    fi
}

create_directories() {
    echo "Creating data directories..."
    
    # Source .env file
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
    fi
    
    # Create directories with defaults
    mkdir -p "${WAKEDOCK_DATA_DIR:-./data}"
    mkdir -p "${WAKEDOCK_CORE_DATA:-./data/wakedock-core}"
    mkdir -p "${WAKEDOCK_LOGS_DIR:-./data/logs}"
    mkdir -p "${WAKEDOCK_CONFIG_DIR:-./data/config}"
    mkdir -p "${CADDY_DATA_DIR:-./data/caddy-data}"
    mkdir -p "${CADDY_CONFIG_DIR:-./data/caddy-config}"
    mkdir -p "${DASHBOARD_DATA_DIR:-./data/dashboard}"
    mkdir -p "${POSTGRES_DATA_DIR:-./data/postgres}"
    mkdir -p "${REDIS_DATA_DIR:-./data/redis}"
    
    print_success "Data directories created"
}

build_images() {
    echo "Building Docker images..."
    docker-compose build
    print_success "Images built successfully"
}

start_dev() {
    echo "Starting WakeDock in development mode..."
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
    print_success "WakeDock development environment started"
    echo ""
    echo "Services available at:"
    echo "🌐 Dashboard: http://localhost:${DASHBOARD_PORT:-3000}"
    echo "🔧 API: http://localhost:${WAKEDOCK_CORE_PORT:-8000}"
    echo "⚙️  Caddy Admin: http://localhost:${CADDY_ADMIN_PORT:-2019}"
    echo "📊 PostgreSQL: localhost:${POSTGRES_PORT:-5432}"
    echo "🔴 Redis: localhost:${REDIS_PORT:-6379}"
}

start_prod() {
    echo "Starting WakeDock in production mode..."
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
    print_success "WakeDock production environment started"
    echo ""
    echo "Services available at:"
    echo "🌐 Dashboard: http://localhost:${DASHBOARD_PORT:-3000}"
    echo "🔧 API: http://localhost:${WAKEDOCK_CORE_PORT:-8000}"
}

stop_services() {
    echo "Stopping WakeDock services..."
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml down
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
    print_success "Services stopped"
}

show_logs() {
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f
}

show_status() {
    echo "WakeDock Services Status:"
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml ps
}

# Main script
case "$1" in
    "setup")
        check_requirements
        setup_env
        create_directories
        build_images
        print_success "WakeDock setup completed!"
        echo ""
        echo "Next steps:"
        echo "1. Edit .env file with your configuration"
        echo "2. Run './manage.sh dev' to start development environment"
        echo "3. Run './manage.sh prod' to start production environment"
        ;;
    "dev")
        check_requirements
        setup_env
        create_directories
        start_dev
        ;;
    "prod")
        check_requirements
        setup_env
        create_directories
        start_prod
        ;;
    "stop")
        stop_services
        ;;
    "logs")
        show_logs
        ;;
    "status")
        show_status
        ;;
    "build")
        build_images
        ;;
    "reset")
        print_warning "This will stop all services and remove all data!"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            stop_services
            docker-compose down -v
            sudo rm -rf ./data
            print_success "WakeDock reset completed"
        fi
        ;;
    *)
        print_header
        echo "Usage: $0 {setup|dev|prod|stop|logs|status|build|reset}"
        echo ""
        echo "Commands:"
        echo "  setup  - Initial setup (create .env, directories, build images)"
        echo "  dev    - Start development environment"
        echo "  prod   - Start production environment"
        echo "  stop   - Stop all services"
        echo "  logs   - Show logs (follow mode)"
        echo "  status - Show services status"
        echo "  build  - Build Docker images"
        echo "  reset  - Reset everything (destructive!)"
        echo ""
        echo "Examples:"
        echo "  $0 setup    # First time setup"
        echo "  $0 dev      # Start development"
        echo "  $0 logs     # View logs"
        echo "  $0 stop     # Stop services"
        ;;
esac
