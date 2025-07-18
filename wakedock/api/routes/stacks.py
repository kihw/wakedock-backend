"""
Routes API pour la gestion des stacks
Point d'entrée unifié pour l'API /api/v1/stacks
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from wakedock.api.auth.dependencies import get_current_user
from wakedock.api.routes.compose_stacks import (
    get_deployment_manager,
    StackResponse,
    DeploymentResponse,
    ComposeDeploymentManager
)
from wakedock.core.docker_client import DockerClient
from wakedock.core.dependencies import get_docker_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stacks", tags=["stacks"])

# Modèles pour les réponses d'overview
class StackStats(BaseModel):
    """Statistiques d'une stack"""
    total_containers: int = 0
    running_containers: int = 0
    stopped_containers: int = 0
    services_count: int = 0
    networks_count: int = 0
    volumes_count: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    
class StackOverview(BaseModel):
    """Vue d'ensemble des stacks"""
    total_stacks: int = 0
    running_stacks: int = 0
    stopped_stacks: int = 0
    error_stacks: int = 0
    total_services: int = 0
    total_containers: int = 0
    
class StackStatsResponse(BaseModel):
    """Réponse pour /stats/overview"""
    overview: StackOverview
    stacks: List[Dict[str, Any]]

# Routes principales

@router.get("/", response_model=List[StackResponse])
async def list_stacks(
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    current_user = Depends(get_current_user)
):
    """
    Liste toutes les stacks Docker Compose
    Endpoint: GET /api/v1/stacks
    """
    try:
        stacks = deployment_manager.list_stacks()
        
        return [
            StackResponse(
                name=stack['name'],
                status=stack['status'],
                services=stack.get('services', []),
                deployment_info=stack.get('deployment_info')
            )
            for stack in stacks
        ]
        
    except Exception as e:
        logger.error(f"Erreur lors de la liste des stacks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de récupération des stacks: {str(e)}"
        )

@router.get("/stats/overview", response_model=StackStatsResponse)
async def get_stacks_overview(
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    docker_client: DockerClient = Depends(get_docker_client),
    current_user = Depends(get_current_user)
):
    """
    Récupère les statistiques d'ensemble des stacks
    Endpoint: GET /api/v1/stacks/stats/overview
    """
    try:
        # Récupérer toutes les stacks
        stacks = deployment_manager.list_stacks()
        
        # Calculer les statistiques globales
        total_stacks = len(stacks)
        running_stacks = sum(1 for s in stacks if s['status'] == 'running')
        stopped_stacks = sum(1 for s in stacks if s['status'] == 'stopped')
        error_stacks = sum(1 for s in stacks if s['status'] == 'error')
        
        # Calculer les services et containers
        total_services = sum(len(s.get('services', [])) for s in stacks)
        total_containers = 0
        
        # Enrichir avec les informations Docker
        enhanced_stacks = []
        for stack in stacks:
            try:
                # Récupérer les containers pour cette stack
                containers = docker_client.list_containers(filters={
                    'label': f'com.docker.compose.project={stack["name"]}'
                })
                
                services = stack.get('services', [])
                running_containers = sum(1 for c in containers if c.status == 'running')
                stopped_containers = len(containers) - running_containers
                
                total_containers += len(containers)
                
                # Calculer les statistiques de la stack
                stack_stats = StackStats(
                    total_containers=len(containers),
                    running_containers=running_containers,
                    stopped_containers=stopped_containers,
                    services_count=len(services),
                    networks_count=stack.get('networks_count', 0),
                    volumes_count=stack.get('volumes_count', 0)
                )
                
                enhanced_stack = {
                    'name': stack['name'],
                    'status': stack['status'],
                    'services': services,
                    'containers': [
                        {
                            'id': c.id,
                            'name': c.name,
                            'status': c.status,
                            'image': c.attrs.get('Config', {}).get('Image', ''),
                            'created': c.attrs.get('Created', ''),
                            'ports': c.attrs.get('NetworkSettings', {}).get('Ports', {})
                        }
                        for c in containers
                    ],
                    'stats': stack_stats.dict(),
                    'deployment_info': stack.get('deployment_info')
                }
                
                enhanced_stacks.append(enhanced_stack)
                
            except Exception as e:
                logger.warning(f"Erreur lors de l'enrichissement de la stack {stack['name']}: {e}")
                # Garder les données de base en cas d'erreur
                enhanced_stacks.append({
                    'name': stack['name'],
                    'status': stack['status'],
                    'services': stack.get('services', []),
                    'containers': [],
                    'stats': StackStats().dict(),
                    'deployment_info': stack.get('deployment_info')
                })
        
        # Créer la réponse d'overview
        overview = StackOverview(
            total_stacks=total_stacks,
            running_stacks=running_stacks,
            stopped_stacks=stopped_stacks,
            error_stacks=error_stacks,
            total_services=total_services,
            total_containers=total_containers
        )
        
        return StackStatsResponse(
            overview=overview,
            stacks=enhanced_stacks
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de récupération des statistiques: {str(e)}"
        )

@router.get("/{stack_name}", response_model=StackResponse)
async def get_stack(
    stack_name: str,
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    current_user = Depends(get_current_user)
):
    """
    Récupère les informations d'une stack spécifique
    Endpoint: GET /api/v1/stacks/{stack_name}
    """
    try:
        stack_info = deployment_manager.get_stack_status(stack_name)
        
        if stack_info['status'] == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stack {stack_name} non trouvée"
            )
        
        return StackResponse(
            name=stack_info['name'],
            status=stack_info['status'],
            services=stack_info.get('services', []),
            deployment_info=stack_info.get('deployment_info')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la stack {stack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de récupération: {str(e)}"
        )

@router.post("/{stack_name}/action", response_model=DeploymentResponse)
async def execute_stack_action(
    stack_name: str,
    action: str,
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    current_user = Depends(get_current_user)
):
    """
    Exécute une action sur une stack (start, stop, restart, remove)
    Endpoint: POST /api/v1/stacks/{stack_name}/action
    """
    try:
        if action not in ['start', 'stop', 'restart', 'remove']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action non supportée: {action}"
            )
        
        if action == 'stop':
            result = deployment_manager.stop_stack(stack_name)
        elif action == 'remove':
            success = deployment_manager.remove_stack(stack_name)
            if success:
                return DeploymentResponse(
                    success=True,
                    status='removed',
                    message=f"Stack {stack_name} supprimée avec succès",
                    services_deployed=[],
                    services_failed=[],
                    deployment_time=0.0,
                    logs=[f"Stack {stack_name} removed successfully"]
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Échec de la suppression de la stack {stack_name}"
                )
        else:
            # Pour start et restart, on peut redéployer la stack
            stack_info = deployment_manager.get_stack_status(stack_name)
            if stack_info['status'] == 'not_found':
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Stack {stack_name} non trouvée"
                )
            
            # Redéployer avec la configuration existante
            result = deployment_manager.deploy_stack(
                stack_name=stack_name,
                compose_content=stack_info.get('compose_content', ''),
                validate_only=False
            )
        
        return DeploymentResponse(
            success=result.success,
            status=result.status.value,
            message=result.message,
            services_deployed=result.services_deployed,
            services_failed=result.services_failed,
            deployment_time=result.deployment_time,
            logs=result.logs
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de l'action {action} sur {stack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'exécution: {str(e)}"
        )

@router.get("/{stack_name}/logs")
async def get_stack_logs(
    stack_name: str,
    tail: int = 100,
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    current_user = Depends(get_current_user)
):
    """
    Récupère les logs d'une stack
    Endpoint: GET /api/v1/stacks/{stack_name}/logs
    """
    try:
        # Vérifier que la stack existe
        stack_info = deployment_manager.get_stack_status(stack_name)
        if stack_info['status'] == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stack {stack_name} non trouvée"
            )
        
        # Récupérer les logs via docker-compose
        logs = deployment_manager.get_stack_logs(stack_name, tail=tail)
        
        return {
            'stack_name': stack_name,
            'logs': logs,
            'tail': tail
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs de {stack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de récupération des logs: {str(e)}"
        )

@router.get("/{stack_name}/stats", response_model=StackStats)
async def get_stack_stats(
    stack_name: str,
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    docker_client: DockerClient = Depends(get_docker_client),
    current_user = Depends(get_current_user)
):
    """
    Récupère les statistiques détaillées d'une stack
    Endpoint: GET /api/v1/stacks/{stack_name}/stats
    """
    try:
        # Vérifier que la stack existe
        stack_info = deployment_manager.get_stack_status(stack_name)
        if stack_info['status'] == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stack {stack_name} non trouvée"
            )
        
        # Récupérer les containers de la stack
        containers = docker_client.list_containers(filters={
            'label': f'com.docker.compose.project={stack_name}'
        })
        
        services = stack_info.get('services', [])
        running_containers = sum(1 for c in containers if c.status == 'running')
        stopped_containers = len(containers) - running_containers
        
        # Calculer les statistiques de CPU et mémoire
        cpu_usage = 0.0
        memory_usage = 0.0
        
        for container in containers:
            try:
                stats = container.stats(stream=False)
                if stats:
                    # Calculer l'utilisation CPU (approximative)
                    cpu_usage += stats.get('cpu_percent', 0)
                    # Calculer l'utilisation mémoire (approximative)
                    memory_usage += stats.get('memory_percent', 0)
            except Exception as e:
                logger.debug(f"Erreur stats container {container.name}: {e}")
                continue
        
        return StackStats(
            total_containers=len(containers),
            running_containers=running_containers,
            stopped_containers=stopped_containers,
            services_count=len(services),
            networks_count=stack_info.get('networks_count', 0),
            volumes_count=stack_info.get('volumes_count', 0),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats de {stack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de récupération des statistiques: {str(e)}"
        )