# 🚀 WakeDock Backend
 
> **FastAPI Docker Management API** - Backend service for WakeDock platform with PostgreSQL, Redis, and async operations.

## 📋 Overview

WakeDock Backend is a high-performance FastAPI application that provides Docker container management capabilities through a RESTful API. It serves as the core backend service for the WakeDock platform.

## 🏗️ Architecture

- **Framework**: FastAPI 0.104+ with async/await
- **Language**: Python 3.11 with strict type hints
- **Database**: PostgreSQL 15+ with SQLAlchemy 2.0 async ORM
- **Cache**: Redis 5.0+ for sessions and caching
- **Authentication**: JWT with rotation and security features
- **API Documentation**: Auto-generated OpenAPI/Swagger
- **Container**: Multi-stage Docker build with security best practices

## 🚀 Quick Start

### Prerequisites
- Docker 20.10+
- Python 3.11+ (for local development)

### Docker Build
```bash
# Clone the repository
git clone https://github.com/kihw/wakedock-backend.git
cd wakedock-backend

# Build the Docker image
docker build -t wakedock-backend .

# Run the container
docker run -p 5000:5000 \
  -e DATABASE_URL=postgresql://user:pass@localhost:5432/wakedock \
  -e REDIS_URL=redis://localhost:6379/0 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  wakedock-backend
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql://user:pass@localhost:5432/wakedock
export REDIS_URL=redis://localhost:6379/0

# Run the development server
python -m wakedock.main
# or
uvicorn wakedock.main:app --reload --port 5000
```

## 🌐 API Endpoints

The backend exposes RESTful endpoints on port **5000**:

- **Health Check**: `GET /api/v1/health`
- **Authentication**: `POST /api/v1/auth/login`
- **Docker Services**: `GET /api/v1/services`
- **Container Management**: `POST /api/v1/services/{id}/start`
- **WebSocket**: `WS /ws` for real-time updates

### API Documentation
- **Swagger UI**: http://localhost:5000/docs
- **ReDoc**: http://localhost:5000/redoc
- **OpenAPI JSON**: http://localhost:5000/openapi.json

## 🔒 Security Features

- **JWT Authentication** with automatic token rotation
- **Rate Limiting** on sensitive endpoints
- **Input Validation** with Pydantic models
- **SQL Injection Protection** via SQLAlchemy ORM
- **CORS Configuration** for cross-origin requests
- **Non-root Container** execution
- **Docker Socket** permission management

## 📊 Configuration

Configuration is handled through environment variables:

```bash
# Core Settings
WAKEDOCK_DEBUG=false
WAKEDOCK_LOG_LEVEL=info
WAKEDOCK_CONFIG_PATH=/app/config/config.yml

# Database
DATABASE_URL=postgresql://user:pass@host:5432/wakedock

# Cache
REDIS_URL=redis://host:6379/0

# Security
JWT_SECRET_KEY=your-secret-key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Docker
DOCKER_SOCKET_PATH=/var/run/docker.sock

# Monitoring
PROMETHEUS_ENABLED=true
MONITORING_ENABLED=true
```

## 🧪 Testing

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run unit tests
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run all tests with coverage
pytest tests/ --cov=wakedock --cov-report=html

# Type checking
mypy wakedock/

# Code quality
flake8 wakedock/
black wakedock/
isort wakedock/
```

## 📁 Project Structure

```
wakedock-backend/
├── wakedock/                    # Main application package
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entry point
│   ├── config.py                # Configuration management
│   ├── api/                     # API routes and middleware
│   │   ├── v1/                  # API version 1
│   │   ├── middleware/          # Custom middleware
│   │   └── dependencies/        # Dependency injection
│   ├── core/                    # Core functionality
│   │   ├── database.py          # Database configuration
│   │   ├── security.py          # Security utilities
│   │   └── redis.py             # Redis configuration
│   ├── models/                  # SQLAlchemy models
│   │   ├── base.py              # Base model class
│   │   ├── user.py              # User model
│   │   └── service.py           # Service model
│   ├── schemas/                 # Pydantic schemas
│   │   ├── user.py              # User schemas
│   │   └── service.py           # Service schemas
│   ├── services/                # Business logic
│   │   ├── docker_service.py    # Docker operations
│   │   ├── user_service.py      # User management
│   │   └── auth_service.py      # Authentication
│   └── utils/                   # Utilities
│       ├── docker_client.py     # Docker client wrapper
│       └── logging.py           # Logging configuration
├── tests/                       # Test suite
├── alembic/                     # Database migrations
├── Dockerfile                   # Multi-stage Docker build
├── requirements.txt             # Python dependencies
├── requirements-prod.txt        # Production dependencies
├── health_check.py              # Health check script
└── docker-entrypoint.sh         # Container entrypoint
```

## 🔄 Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Check migration status
alembic current

# Migration history
alembic history
```

## 📈 Monitoring & Metrics

- **Health Checks**: Built-in health endpoint with dependency validation
- **Prometheus Metrics**: Application and business metrics
- **Structured Logging**: JSON logs with correlation IDs
- **Performance Monitoring**: Request timing and resource usage
- **Docker Events**: Real-time container event streaming

## 🐳 Production Deployment

### Multi-stage Docker Build
The Dockerfile uses a multi-stage build for optimal security and size:

1. **Builder Stage**: Installs dependencies in virtual environment
2. **Production Stage**: Minimal runtime with non-root user

### Environment Variables
```bash
# Production settings
ENV=production
WORKERS=4
LOG_LEVEL=warning

# Security
JWT_SECRET_KEY=generate-secure-key
CORS_ORIGINS=https://your-domain.com

# Database connection pooling
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=0
```

## 🤝 Integration with Main Platform

This backend is designed to work with the WakeDock platform:

- **Main Repository**: [wakedock](https://github.com/kihw/wakedock)
- **Frontend**: [wakedock-frontend](https://github.com/kihw/wakedock-frontend)

### Docker Compose Integration
The main platform uses this backend via Docker Compose:

```yaml
services:
  wakedock-backend:
    build:
      context: https://github.com/kihw/wakedock-backend.git
      dockerfile: Dockerfile
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://...
```

## 📚 API Documentation

### Core Endpoints

#### Health Check
```http
GET /api/v1/health
Response: {
  "status": "healthy",
  "timestamp": "2025-07-13T19:15:00Z",
  "version": "1.0.0",
  "database": "connected",
  "redis": "connected",
  "docker": "connected"
}
```

#### Authentication
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}

Response: {
  "access_token": "...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### Services Management
```http
GET /api/v1/services
Authorization: Bearer <token>

Response: [
  {
    "id": "container-id",
    "name": "my-service",
    "status": "running",
    "image": "nginx:latest",
    "ports": [{"host": 80, "container": 80}],
    "created_at": "2025-07-13T19:15:00Z"
  }
]
```

## 🔧 Development Guidelines

### Code Style
- **Type Hints**: Required on all functions and methods
- **Async/Await**: Mandatory for I/O operations
- **Pydantic Models**: Strict validation for all data
- **Error Handling**: Centralized exception handling
- **Logging**: Structured logging with context

### Example Function
```python
async def create_service(
    service_data: ServiceCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session)
) -> ServiceResponse:
    """Create a new Docker service."""
    try:
        # Business logic here
        service = await service_repository.create(db, service_data)
        return ServiceResponse.from_orm(service)
    except DockerException as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create service: {e}"
        )
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## 🐛 Issues & Support

- **Bug Reports**: [GitHub Issues](https://github.com/kihw/wakedock-backend/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/kihw/wakedock-backend/discussions)
- **Documentation**: [WakeDock Docs](https://github.com/kihw/wakedock/docs)

---

**Built with ❤️ for the Docker community**