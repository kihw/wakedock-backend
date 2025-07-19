"""
Service Management API for WakeDock v1.0.0

This module provides advanced service management capabilities including:
- Service creation from templates
- Docker Compose validation and management
- GitHub integration for containerized projects
- Advanced container orchestration
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer
import yaml
import json
import docker
import asyncio
import aiohttp
from pathlib import Path

from wakedock.core.database import get_database
from wakedock.core.security import get_current_user
from wakedock.core.docker_manager import DockerManager
from wakedock.database.models import User

# Initialize router
router = APIRouter(prefix="/api/v1/services", tags=["services"])
security = HTTPBearer()

# Pydantic models
class ServiceTemplate(BaseModel):
    id: str
    name: str
    description: str
    category: str
    icon: str
    ports: List[int]
    environment: Dict[str, str]
    volumes: List[str]
    networks: List[str]
    dependencies: List[str]
    docker_image: str
    docker_tag: str
    resources: Dict[str, str]
    health_check: Optional[Dict[str, Any]] = None

class ServiceConfig(BaseModel):
    template: ServiceTemplate
    custom_name: str
    ports: Dict[str, str]
    environment: Dict[str, str]
    volumes: Dict[str, str]
    networks: List[str]
    resources: Dict[str, str]

class DockerComposeValidationRequest(BaseModel):
    content: str
    env_file: Optional[str] = None

class DockerComposeValidationResponse(BaseModel):
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    services: Dict[str, Any]
    networks: Dict[str, Any]
    volumes: Dict[str, Any]

class GitHubRepository(BaseModel):
    id: int
    name: str
    full_name: str
    description: str
    html_url: str
    clone_url: str
    default_branch: str
    stargazers_count: int
    forks_count: int
    language: Optional[str]
    updated_at: datetime
    has_dockerfile: bool
    has_compose: bool
    topics: List[str]

class GitHubImportRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    service_name: str
    env_vars: Dict[str, str] = {}
    ports: Dict[str, str] = {}
    auto_webhook: bool = False

class DeploymentStatus(BaseModel):
    id: str
    service_name: str
    status: str
    repository: Optional[str] = None
    branch: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    logs: List[str] = []

# Service Templates
SERVICE_TEMPLATES = {
    "nginx": ServiceTemplate(
        id="nginx",
        name="NGINX",
        description="High-performance web server and reverse proxy",
        category="web",
        icon="server",
        ports=[80, 443],
        environment={"NGINX_HOST": "localhost", "NGINX_PORT": "80"},
        volumes=["/usr/share/nginx/html", "/etc/nginx/conf.d"],
        networks=["web"],
        dependencies=[],
        docker_image="nginx",
        docker_tag="alpine",
        resources={"cpu": "0.5", "memory": "128m"},
        health_check={
            "endpoint": "/health",
            "interval": "30s",
            "timeout": "5s",
            "retries": 3
        }
    ),
    "postgres": ServiceTemplate(
        id="postgres",
        name="PostgreSQL",
        description="Advanced open source relational database",
        category="database",
        icon="database",
        ports=[5432],
        environment={
            "POSTGRES_DB": "wakedock",
            "POSTGRES_USER": "wakedock",
            "POSTGRES_PASSWORD": "changeme"
        },
        volumes=["/var/lib/postgresql/data"],
        networks=["database"],
        dependencies=[],
        docker_image="postgres",
        docker_tag="15-alpine",
        resources={"cpu": "1.0", "memory": "512m"},
        health_check={
            "endpoint": "pg_isready",
            "interval": "10s",
            "timeout": "5s",
            "retries": 5
        }
    ),
    "redis": ServiceTemplate(
        id="redis",
        name="Redis",
        description="In-memory data structure store",
        category="cache",
        icon="database",
        ports=[6379],
        environment={"REDIS_PASSWORD": "changeme"},
        volumes=["/data"],
        networks=["cache"],
        dependencies=[],
        docker_image="redis",
        docker_tag="7-alpine",
        resources={"cpu": "0.5", "memory": "256m"},
        health_check={
            "endpoint": "redis-cli ping",
            "interval": "10s",
            "timeout": "3s",
            "retries": 3
        }
    ),
    "prometheus": ServiceTemplate(
        id="prometheus",
        name="Prometheus",
        description="Systems monitoring and alerting toolkit",
        category="monitoring",
        icon="monitor",
        ports=[9090],
        environment={"PROMETHEUS_RETENTION_TIME": "15d"},
        volumes=["/prometheus", "/etc/prometheus"],
        networks=["monitoring"],
        dependencies=[],
        docker_image="prom/prometheus",
        docker_tag="latest",
        resources={"cpu": "1.0", "memory": "1g"},
        health_check={
            "endpoint": "/-/healthy",
            "interval": "30s",
            "timeout": "10s",
            "retries": 3
        }
    )
}

# Dependency injection
async def get_docker_manager():
    """Get Docker manager instance"""
    return DockerManager()

# Endpoints

@router.get("/templates", response_model=List[ServiceTemplate])
async def get_service_templates():
    """Get all available service templates"""
    return list(SERVICE_TEMPLATES.values())

@router.get("/templates/{template_id}", response_model=ServiceTemplate)
async def get_service_template(template_id: str):
    """Get specific service template"""
    if template_id not in SERVICE_TEMPLATES:
        raise HTTPException(status_code=404, detail="Template not found")
    return SERVICE_TEMPLATES[template_id]

@router.post("/create")
async def create_service_from_template(
    config: ServiceConfig,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Create a new service from template"""
    try:
        # Validate configuration
        if not config.custom_name or len(config.custom_name) < 3:
            raise HTTPException(status_code=400, detail="Service name must be at least 3 characters long")
        
        # Check if service already exists
        existing_services = await docker_manager.list_services()
        if any(service.name == config.custom_name for service in existing_services):
            raise HTTPException(status_code=409, detail="Service with this name already exists")
        
        # Generate Docker Compose configuration
        compose_config = generate_docker_compose(config)
        
        # Save configuration
        config_path = Path(f"/tmp/{config.custom_name}-compose.yml")
        with open(config_path, 'w') as f:
            f.write(compose_config)
        
        # Deploy service in background
        deployment_id = f"deploy-{config.custom_name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        background_tasks.add_task(
            deploy_service_background,
            deployment_id,
            config_path,
            config.custom_name,
            current_user.id
        )
        
        return {
            "deployment_id": deployment_id,
            "service_name": config.custom_name,
            "status": "deploying",
            "message": "Service deployment started"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create service: {str(e)}")

@router.post("/compose/validate", response_model=DockerComposeValidationResponse)
async def validate_docker_compose(request: DockerComposeValidationRequest):
    """Validate Docker Compose configuration"""
    try:
        # Parse YAML
        compose_data = yaml.safe_load(request.content)
        
        errors = []
        warnings = []
        
        # Basic validation
        if not compose_data.get('version'):
            warnings.append("Missing version field")
        
        services = compose_data.get('services', {})
        if not services:
            errors.append("No services defined")
        
        # Service validation
        for service_name, service_config in services.items():
            if not service_config.get('image'):
                errors.append(f"Service '{service_name}' is missing image field")
            
            # Port validation
            ports = service_config.get('ports', [])
            for port in ports:
                if isinstance(port, str):
                    if not port.replace(':', '').replace('-', '').isdigit():
                        errors.append(f"Invalid port format '{port}' in service '{service_name}'")
            
            # Environment validation
            environment = service_config.get('environment', {})
            if isinstance(environment, list):
                for env in environment:
                    if '=' not in env:
                        warnings.append(f"Invalid environment variable format '{env}' in service '{service_name}'")
        
        return DockerComposeValidationResponse(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            services=services,
            networks=compose_data.get('networks', {}),
            volumes=compose_data.get('volumes', {})
        )
        
    except yaml.YAMLError as e:
        return DockerComposeValidationResponse(
            is_valid=False,
            errors=[f"YAML parsing error: {str(e)}"],
            warnings=[],
            services={},
            networks={},
            volumes={}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

@router.post("/compose/deploy")
async def deploy_docker_compose(
    request: DockerComposeValidationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Deploy Docker Compose configuration"""
    try:
        # First validate
        validation = await validate_docker_compose(request)
        if not validation.is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {validation.errors}")
        
        # Save compose file
        compose_path = Path(f"/tmp/compose-{datetime.now().strftime('%Y%m%d%H%M%S')}.yml")
        with open(compose_path, 'w') as f:
            f.write(request.content)
        
        # Deploy in background
        deployment_id = f"compose-deploy-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        background_tasks.add_task(
            deploy_compose_background,
            deployment_id,
            compose_path,
            current_user.id
        )
        
        return {
            "deployment_id": deployment_id,
            "status": "deploying",
            "message": "Docker Compose deployment started"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deployment failed: {str(e)}")

@router.post("/github/import")
async def import_github_repository(
    request: GitHubImportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Import and deploy from GitHub repository"""
    try:
        # Validate GitHub URL
        if not request.repo_url.startswith(('https://github.com/', 'git@github.com:')):
            raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
        
        # Parse repository info
        repo_parts = request.repo_url.replace('https://github.com/', '').replace('git@github.com:', '').replace('.git', '').split('/')
        if len(repo_parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid repository format")
        
        owner, repo_name = repo_parts
        
        # Clone repository and analyze
        deployment_id = f"github-import-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        background_tasks.add_task(
            import_github_repository_background,
            deployment_id,
            request.repo_url,
            request.branch,
            request.service_name,
            request.env_vars,
            request.ports,
            request.auto_webhook,
            current_user.id
        )
        
        return {
            "deployment_id": deployment_id,
            "service_name": request.service_name,
            "repository": f"{owner}/{repo_name}",
            "branch": request.branch,
            "status": "importing",
            "message": "GitHub repository import started"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@router.get("/github/repositories")
async def search_github_repositories(
    query: str = "",
    page: int = 1,
    per_page: int = 10,
    current_user: User = Depends(get_current_user)
):
    """Search GitHub repositories for containerized projects"""
    try:
        # This would integrate with GitHub API
        # For now, return mock data
        repositories = [
            {
                "id": 1,
                "name": "awesome-webapp",
                "full_name": "user/awesome-webapp",
                "description": "A modern web application built with React and Node.js",
                "html_url": "https://github.com/user/awesome-webapp",
                "clone_url": "https://github.com/user/awesome-webapp.git",
                "default_branch": "main",
                "stargazers_count": 142,
                "forks_count": 28,
                "language": "JavaScript",
                "updated_at": "2024-01-15T10:30:00Z",
                "has_dockerfile": True,
                "has_compose": True,
                "topics": ["react", "nodejs", "docker", "web-app"]
            },
            {
                "id": 2,
                "name": "microservice-api",
                "full_name": "user/microservice-api",
                "description": "RESTful API microservice with FastAPI and PostgreSQL",
                "html_url": "https://github.com/user/microservice-api",
                "clone_url": "https://github.com/user/microservice-api.git",
                "default_branch": "main",
                "stargazers_count": 89,
                "forks_count": 15,
                "language": "Python",
                "updated_at": "2024-01-14T16:45:00Z",
                "has_dockerfile": True,
                "has_compose": False,
                "topics": ["fastapi", "python", "microservice", "api"]
            }
        ]
        
        # Filter by query if provided
        if query:
            repositories = [
                repo for repo in repositories
                if query.lower() in repo["name"].lower() or 
                   query.lower() in repo["description"].lower() or
                   any(query.lower() in topic.lower() for topic in repo["topics"])
            ]
        
        # Pagination
        start = (page - 1) * per_page
        end = start + per_page
        
        return {
            "repositories": repositories[start:end],
            "total": len(repositories),
            "page": page,
            "per_page": per_page,
            "total_pages": (len(repositories) + per_page - 1) // per_page
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/deployments/{deployment_id}")
async def get_deployment_status(
    deployment_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get deployment status"""
    try:
        # This would fetch from database
        # For now, return mock status
        return {
            "id": deployment_id,
            "status": "running",
            "service_name": "test-service",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "logs": [
                "Starting deployment...",
                "Pulling Docker image...",
                "Creating container...",
                "Service started successfully"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get deployment status: {str(e)}")

@router.get("/deployments")
async def list_deployments(
    current_user: User = Depends(get_current_user)
):
    """List all deployments for current user"""
    try:
        # This would fetch from database
        return []
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list deployments: {str(e)}")

# Helper functions

def generate_docker_compose(config: ServiceConfig) -> str:
    """Generate Docker Compose YAML from service configuration"""
    template = config.template
    
    # Port mappings
    port_mappings = [f"{external}:{internal}" for internal, external in config.ports.items()]
    
    # Environment variables
    env_vars = [f"{key}={value}" for key, value in config.environment.items()]
    
    # Volume mappings
    volume_mappings = [f"{host}:{container}" for container, host in config.volumes.items()]
    
    # Generate compose structure
    compose_data = {
        "version": "3.8",
        "services": {
            config.custom_name: {
                "image": f"{template.docker_image}:{template.docker_tag}",
                "container_name": config.custom_name,
                "restart": "unless-stopped",
                "ports": port_mappings,
                "environment": env_vars,
                "volumes": volume_mappings,
                "networks": config.networks,
                "deploy": {
                    "resources": {
                        "limits": {
                            "cpus": config.resources["cpu"],
                            "memory": config.resources["memory"]
                        },
                        "reservations": {
                            "cpus": str(float(config.resources["cpu"]) / 2),
                            "memory": config.resources["memory"]
                        }
                    }
                }
            }
        },
        "networks": {network: {"external": True} for network in config.networks}
    }
    
    # Add health check if available
    if template.health_check:
        compose_data["services"][config.custom_name]["healthcheck"] = {
            "test": ["CMD", template.health_check["endpoint"]],
            "interval": template.health_check["interval"],
            "timeout": template.health_check["timeout"],
            "retries": template.health_check["retries"]
        }
    
    return yaml.dump(compose_data, default_flow_style=False)

async def deploy_service_background(
    deployment_id: str,
    config_path: Path,
    service_name: str,
    user_id: int
):
    """Background task for service deployment"""
    try:
        # This would implement actual deployment logic
        await asyncio.sleep(2)  # Simulate deployment time
        
        # Update deployment status in database
        print(f"Deployment {deployment_id} completed for service {service_name}")
        
    except Exception as e:
        print(f"Deployment {deployment_id} failed: {str(e)}")

async def deploy_compose_background(
    deployment_id: str,
    compose_path: Path,
    user_id: int
):
    """Background task for Docker Compose deployment"""
    try:
        # This would implement actual deployment logic
        await asyncio.sleep(3)  # Simulate deployment time
        
        # Update deployment status in database
        print(f"Compose deployment {deployment_id} completed")
        
    except Exception as e:
        print(f"Compose deployment {deployment_id} failed: {str(e)}")

async def import_github_repository_background(
    deployment_id: str,
    repo_url: str,
    branch: str,
    service_name: str,
    env_vars: Dict[str, str],
    ports: Dict[str, str],
    auto_webhook: bool,
    user_id: int
):
    """Background task for GitHub repository import"""
    try:
        # This would implement actual import and deployment logic
        await asyncio.sleep(5)  # Simulate import time
        
        # Update deployment status in database
        print(f"GitHub import {deployment_id} completed for {repo_url}")
        
    except Exception as e:
        print(f"GitHub import {deployment_id} failed: {str(e)}")
