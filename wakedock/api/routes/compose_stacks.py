"""
Routes API pour la gestion des stacks Docker Compose
"""
from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

from wakedock.core.compose_parser import ComposeParser, ComposeValidationError
from wakedock.core.compose_validator import ComposeValidator
from wakedock.core.compose_deployment import ComposeDeploymentManager, DeploymentResult, DeploymentStatus
from wakedock.core.env_manager import EnvManager
from wakedock.core.dependency_manager import DependencyManager
from wakedock.api.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/compose", tags=["docker-compose"])

# Modèles Pydantic

class ComposeStackCreate(BaseModel):
    """Modèle pour créer une stack Compose"""
    name: str = Field(..., description="Nom de la stack")
    compose_content: str = Field(..., description="Contenu du fichier docker-compose.yml")
    env_variables: Optional[Dict[str, str]] = Field(default={}, description="Variables d'environnement")
    env_file_content: Optional[str] = Field(default=None, description="Contenu du fichier .env")
    validate_only: bool = Field(default=False, description="Valider uniquement sans déployer")

class ComposeStackUpdate(BaseModel):
    """Modèle pour mettre à jour une stack Compose"""
    compose_content: Optional[str] = Field(default=None, description="Nouveau contenu docker-compose.yml")
    env_variables: Optional[Dict[str, str]] = Field(default=None, description="Nouvelles variables d'environnement")
    env_file_content: Optional[str] = Field(default=None, description="Nouveau contenu .env")

class ComposeValidationRequest(BaseModel):
    """Modèle pour valider une configuration Compose"""
    compose_content: str = Field(..., description="Contenu du fichier docker-compose.yml")
    env_variables: Optional[Dict[str, str]] = Field(default={}, description="Variables d'environnement")

class ComposeValidationResponse(BaseModel):
    """Réponse de validation Compose"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    services_count: int
    networks_count: int
    volumes_count: int
    dependencies_info: Optional[Dict[str, Any]] = None

class StackResponse(BaseModel):
    """Réponse pour une stack"""
    name: str
    status: str
    services: List[Dict[str, Any]]
    deployment_info: Optional[Dict[str, Any]] = None

class DeploymentResponse(BaseModel):
    """Réponse de déploiement"""
    success: bool
    status: str
    message: str
    services_deployed: List[str]
    services_failed: List[str]
    deployment_time: float
    logs: List[str]

# Dépendances

def get_compose_parser() -> ComposeParser:
    """Dépendance pour obtenir le parser Compose"""
    return ComposeParser()

def get_compose_validator() -> ComposeValidator:
    """Dépendance pour obtenir le validateur Compose"""
    return ComposeValidator()

def get_deployment_manager() -> ComposeDeploymentManager:
    """Dépendance pour obtenir le gestionnaire de déploiement"""
    return ComposeDeploymentManager()

def get_env_manager() -> EnvManager:
    """Dépendance pour obtenir le gestionnaire d'environnement"""
    return EnvManager()

def get_dependency_manager() -> DependencyManager:
    """Dépendance pour obtenir le gestionnaire de dépendances"""
    return DependencyManager()

# Routes

@router.post("/validate", response_model=ComposeValidationResponse)
async def validate_compose_configuration(
    request: ComposeValidationRequest,
    parser: ComposeParser = Depends(get_compose_parser),
    validator: ComposeValidator = Depends(get_compose_validator),
    dependency_manager: DependencyManager = Depends(get_dependency_manager),
    current_user = Depends(get_current_user)
):
    """
    Valide une configuration Docker Compose
    """
    try:
        # Parser la configuration
        compose = parser.parse_yaml_content(request.compose_content)
        
        # Valider la configuration
        is_valid, errors, warnings = validator.validate_compose(compose)
        
        # Analyser les dépendances
        dependencies_info = None
        try:
            dep_graph = dependency_manager.analyze_dependencies(compose)
            dep_valid, dep_errors = dependency_manager.validate_dependencies(dep_graph)
            
            if not dep_valid:
                errors.extend(dep_errors)
                is_valid = False
            
            dependencies_info = dependency_manager.get_dependency_report(dep_graph)
            
        except Exception as e:
            logger.warning(f"Erreur lors de l'analyse des dépendances: {e}")
            warnings.append(f"Analyse des dépendances échouée: {str(e)}")
        
        return ComposeValidationResponse(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            services_count=len(compose.services),
            networks_count=len(compose.networks) if compose.networks else 0,
            volumes_count=len(compose.volumes) if compose.volumes else 0,
            dependencies_info=dependencies_info
        )
        
    except ComposeValidationError as e:
        return ComposeValidationResponse(
            is_valid=False,
            errors=[str(e)],
            warnings=[],
            services_count=0,
            networks_count=0,
            volumes_count=0
        )
    except Exception as e:
        logger.error(f"Erreur lors de la validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de validation: {str(e)}"
        )

@router.post("/stacks", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_stack(
    stack: ComposeStackCreate,
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    current_user = Depends(get_current_user)
):
    """
    Crée et déploie une nouvelle stack Docker Compose
    """
    try:
        result = deployment_manager.deploy_stack(
            stack_name=stack.name,
            compose_content=stack.compose_content,
            env_variables=stack.env_variables,
            env_file_content=stack.env_file_content,
            validate_only=stack.validate_only
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
        
    except Exception as e:
        logger.error(f"Erreur lors de la création de la stack {stack.name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de déploiement: {str(e)}"
        )

@router.get("/stacks", response_model=List[StackResponse])
async def list_stacks(
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    current_user = Depends(get_current_user)
):
    """
    Liste toutes les stacks Docker Compose
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
            detail=f"Erreur de récupération: {str(e)}"
        )

@router.get("/stacks/{stack_name}", response_model=StackResponse)
async def get_stack(
    stack_name: str,
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    current_user = Depends(get_current_user)
):
    """
    Récupère les informations d'une stack spécifique
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

@router.put("/stacks/{stack_name}", response_model=DeploymentResponse)
async def update_stack(
    stack_name: str,
    update: ComposeStackUpdate,
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    current_user = Depends(get_current_user)
):
    """
    Met à jour une stack existante
    """
    try:
        # Vérifier que la stack existe
        stack_info = deployment_manager.get_stack_status(stack_name)
        if stack_info['status'] == 'not_found':
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stack {stack_name} non trouvée"
            )
        
        # Pour une mise à jour, on redéploie avec le nouveau contenu
        if update.compose_content:
            result = deployment_manager.deploy_stack(
                stack_name=stack_name,
                compose_content=update.compose_content,
                env_variables=update.env_variables,
                env_file_content=update.env_file_content,
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
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Aucune modification fournie"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la stack {stack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de mise à jour: {str(e)}"
        )

@router.post("/stacks/{stack_name}/stop", response_model=DeploymentResponse)
async def stop_stack(
    stack_name: str,
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    current_user = Depends(get_current_user)
):
    """
    Arrête une stack Docker Compose
    """
    try:
        result = deployment_manager.stop_stack(stack_name)
        
        return DeploymentResponse(
            success=result.success,
            status=result.status.value,
            message=result.message,
            services_deployed=result.services_deployed,
            services_failed=result.services_failed,
            deployment_time=result.deployment_time,
            logs=result.logs
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'arrêt de la stack {stack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'arrêt: {str(e)}"
        )

@router.delete("/stacks/{stack_name}")
async def remove_stack(
    stack_name: str,
    remove_volumes: bool = False,
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    current_user = Depends(get_current_user)
):
    """
    Supprime complètement une stack Docker Compose
    """
    try:
        success = deployment_manager.remove_stack(stack_name, remove_volumes=remove_volumes)
        
        if success:
            return {"message": f"Stack {stack_name} supprimée avec succès"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Échec de la suppression de la stack {stack_name}"
            )
        
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la stack {stack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de suppression: {str(e)}"
        )

@router.post("/stacks/upload", response_model=DeploymentResponse)
async def upload_and_deploy_stack(
    stack_name: str = Form(...),
    compose_file: UploadFile = File(..., description="Fichier docker-compose.yml"),
    env_file: Optional[UploadFile] = File(None, description="Fichier .env optionnel"),
    validate_only: bool = Form(False),
    deployment_manager: ComposeDeploymentManager = Depends(get_deployment_manager),
    current_user = Depends(get_current_user)
):
    """
    Upload et déploie une stack à partir de fichiers
    """
    try:
        # Lire le contenu du fichier compose
        compose_content = await compose_file.read()
        compose_content = compose_content.decode('utf-8')
        
        # Lire le fichier .env si fourni
        env_file_content = None
        if env_file:
            env_content = await env_file.read()
            env_file_content = env_content.decode('utf-8')
        
        # Déployer la stack
        result = deployment_manager.deploy_stack(
            stack_name=stack_name,
            compose_content=compose_content,
            env_file_content=env_file_content,
            validate_only=validate_only
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
        
    except Exception as e:
        logger.error(f"Erreur lors de l'upload de la stack {stack_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'upload: {str(e)}"
        )
