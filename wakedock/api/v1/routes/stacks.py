"""
Routes API pour la gestion des stacks Docker
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from wakedock.api.auth.dependencies import get_current_user
from wakedock.core.docker_manager import DockerManager
from wakedock.core.stack_detection import StackDetectionService
from wakedock.models.stack import (
    ContainerStackInfo,
    StackDetectionRule,
    StackInfo,
    StackSummary,
    StackType
)

router = APIRouter(prefix="/stacks", tags=["stacks"])


class StackActionRequest(BaseModel):
    """Requête pour une action sur une stack"""
    action: str  # start, stop, restart, remove


class StackFilterRequest(BaseModel):
    """Filtres pour la recherche de stacks"""
    type: Optional[StackType] = None
    status: Optional[str] = None
    project_name: Optional[str] = None


# Dépendances
async def get_docker_manager() -> DockerManager:
    return DockerManager()


async def get_stack_detection_service(
    docker_manager: DockerManager = Depends(get_docker_manager)
) -> StackDetectionService:
    return StackDetectionService(docker_manager)


@router.get("/", response_model=List[StackSummary])
async def list_stacks(
    stack_service: StackDetectionService = Depends(get_stack_detection_service),
    current_user = Depends(get_current_user)
):
    """
    Récupérer la liste de toutes les stacks détectées
    """
    try:
        return stack_service.get_stacks_summary()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des stacks: {str(e)}"
        )


@router.get("/{stack_id}", response_model=StackInfo)
async def get_stack(
    stack_id: str,
    stack_service: StackDetectionService = Depends(get_stack_detection_service),
    current_user = Depends(get_current_user)
):
    """
    Récupérer les détails d'une stack spécifique
    """
    try:
        stack = stack_service.get_stack_by_id(stack_id)
        if not stack:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stack {stack_id} non trouvée"
            )
        return stack
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de la stack: {str(e)}"
        )


@router.get("/{stack_id}/containers", response_model=List[ContainerStackInfo])
async def get_stack_containers(
    stack_id: str,
    stack_service: StackDetectionService = Depends(get_stack_detection_service),
    current_user = Depends(get_current_user)
):
    """
    Récupérer tous les containers d'une stack spécifique
    """
    try:
        containers = stack_service.get_containers_by_stack(stack_id)
        if not containers:
            # Vérifier si la stack existe
            stack = stack_service.get_stack_by_id(stack_id)
            if not stack:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Stack {stack_id} non trouvée"
                )
        return containers
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des containers: {str(e)}"
        )


@router.post("/{stack_id}/action")
async def execute_stack_action(
    stack_id: str,
    action_request: StackActionRequest,
    stack_service: StackDetectionService = Depends(get_stack_detection_service),
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Exécuter une action sur tous les containers d'une stack
    """
    try:
        stack = stack_service.get_stack_by_id(stack_id)
        if not stack:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stack {stack_id} non trouvée"
            )
        
        action = action_request.action.lower()
        results = []
        
        for container_info in stack.containers:
            try:
                container = docker_manager.get_container(container_info.container_id)
                if not container:
                    results.append({
                        "container_id": container_info.container_id,
                        "container_name": container_info.container_name,
                        "success": False,
                        "message": "Container non trouvé"
                    })
                    continue
                
                if action == "start":
                    container.start()
                    message = "Container démarré"
                elif action == "stop":
                    container.stop()
                    message = "Container arrêté"
                elif action == "restart":
                    container.restart()
                    message = "Container redémarré"
                elif action == "remove":
                    container.remove()
                    message = "Container supprimé"
                else:
                    results.append({
                        "container_id": container_info.container_id,
                        "container_name": container_info.container_name,
                        "success": False,
                        "message": f"Action '{action}' non supportée"
                    })
                    continue
                
                results.append({
                    "container_id": container_info.container_id,
                    "container_name": container_info.container_name,
                    "success": True,
                    "message": message
                })
                
            except Exception as e:
                results.append({
                    "container_id": container_info.container_id,
                    "container_name": container_info.container_name,
                    "success": False,
                    "message": f"Erreur: {str(e)}"
                })
        
        return {
            "stack_id": stack_id,
            "stack_name": stack.name,
            "action": action,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'exécution de l'action: {str(e)}"
        )


@router.post("/filter", response_model=List[StackSummary])
async def filter_stacks(
    filter_request: StackFilterRequest,
    stack_service: StackDetectionService = Depends(get_stack_detection_service),
    current_user = Depends(get_current_user)
):
    """
    Filtrer les stacks selon des critères spécifiques
    """
    try:
        all_stacks = stack_service.get_stacks_summary()
        
        filtered_stacks = all_stacks
        
        if filter_request.type:
            filtered_stacks = [s for s in filtered_stacks if s.type == filter_request.type]
        
        if filter_request.status:
            filtered_stacks = [s for s in filtered_stacks if s.status == filter_request.status]
        
        if filter_request.project_name:
            filtered_stacks = [
                s for s in filtered_stacks 
                if s.project_name and filter_request.project_name in s.project_name
            ]
        
        return filtered_stacks
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du filtrage des stacks: {str(e)}"
        )


@router.get("/detection/rules", response_model=List[StackDetectionRule])
async def get_detection_rules(
    stack_service: StackDetectionService = Depends(get_stack_detection_service),
    current_user = Depends(get_current_user)
):
    """
    Récupérer toutes les règles de détection de stacks
    """
    try:
        return stack_service.get_detection_rules()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des règles: {str(e)}"
        )


@router.post("/detection/rules", response_model=StackDetectionRule)
async def add_detection_rule(
    rule: StackDetectionRule,
    stack_service: StackDetectionService = Depends(get_stack_detection_service),
    current_user = Depends(get_current_user)
):
    """
    Ajouter une nouvelle règle de détection de stacks
    """
    try:
        stack_service.add_detection_rule(rule)
        return rule
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'ajout de la règle: {str(e)}"
        )


@router.delete("/detection/rules/{rule_name}")
async def remove_detection_rule(
    rule_name: str,
    stack_service: StackDetectionService = Depends(get_stack_detection_service),
    current_user = Depends(get_current_user)
):
    """
    Supprimer une règle de détection de stacks
    """
    try:
        stack_service.remove_detection_rule(rule_name)
        return {"message": f"Règle {rule_name} supprimée avec succès"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression de la règle: {str(e)}"
        )


@router.get("/stats/overview")
async def get_stacks_overview(
    stack_service: StackDetectionService = Depends(get_stack_detection_service),
    current_user = Depends(get_current_user)
):
    """
    Récupérer un aperçu statistique des stacks
    """
    try:
        stacks = stack_service.get_stacks_summary()
        
        # Calculer les statistiques
        total_stacks = len(stacks)
        running_stacks = sum(1 for s in stacks if s.status == "running")
        stopped_stacks = sum(1 for s in stacks if s.status == "stopped")
        error_stacks = sum(1 for s in stacks if s.status == "error")
        
        total_containers = sum(s.total_containers for s in stacks)
        running_containers = sum(s.running_containers for s in stacks)
        
        # Grouper par type
        by_type = {}
        for stack in stacks:
            stack_type = stack.type.value
            if stack_type not in by_type:
                by_type[stack_type] = {
                    "count": 0,
                    "running": 0,
                    "stopped": 0,
                    "error": 0
                }
            by_type[stack_type]["count"] += 1
            if stack.status == "running":
                by_type[stack_type]["running"] += 1
            elif stack.status == "stopped":
                by_type[stack_type]["stopped"] += 1
            elif stack.status == "error":
                by_type[stack_type]["error"] += 1
        
        return {
            "total_stacks": total_stacks,
            "running_stacks": running_stacks,
            "stopped_stacks": stopped_stacks,
            "error_stacks": error_stacks,
            "total_containers": total_containers,
            "running_containers": running_containers,
            "by_type": by_type
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des statistiques: {str(e)}"
        )
