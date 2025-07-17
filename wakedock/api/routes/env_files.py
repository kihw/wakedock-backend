"""
Routes API pour la gestion des fichiers .env
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from wakedock.api.auth.dependencies import get_current_user
from wakedock.core.env_manager import EnvFile, EnvManager, EnvVariable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/env", tags=["environment"])

# Modèles Pydantic

class EnvVariableRequest(BaseModel):
    """Modèle pour une variable d'environnement"""
    name: str = Field(..., description="Nom de la variable")
    value: str = Field(..., description="Valeur de la variable")
    description: Optional[str] = Field(default=None, description="Description de la variable")
    is_secret: bool = Field(default=False, description="Si la variable est sensible")
    is_required: bool = Field(default=True, description="Si la variable est requise")

class EnvFileRequest(BaseModel):
    """Modèle pour créer/modifier un fichier .env"""
    variables: Dict[str, EnvVariableRequest] = Field(..., description="Variables d'environnement")
    comments: List[str] = Field(default=[], description="Commentaires du fichier")

class EnvFileResponse(BaseModel):
    """Réponse pour un fichier .env"""
    path: str
    variables: Dict[str, Dict[str, Any]]
    comments: List[str]
    validation_result: Optional[Dict[str, Any]] = None

class EnvValidationResponse(BaseModel):
    """Réponse de validation d'un fichier .env"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    variables_count: int
    secret_variables_count: int

class EnvTemplateRequest(BaseModel):
    """Modèle pour générer un template .env"""
    services: List[str] = Field(..., description="Liste des services pour le template")

class EnvDiffResponse(BaseModel):
    """Réponse de comparaison entre fichiers .env"""
    added: List[str]
    removed: List[str]
    modified: List[Dict[str, str]]

class EnvSubstitutionRequest(BaseModel):
    """Modèle pour la substitution de variables"""
    text: str = Field(..., description="Texte avec variables à substituer")
    variables: Dict[str, str] = Field(..., description="Variables d'environnement")

# Dépendances

def get_env_manager() -> EnvManager:
    """Dépendance pour obtenir le gestionnaire d'environnement"""
    return EnvManager()

# Routes

@router.post("/validate", response_model=EnvValidationResponse)
async def validate_env_variables(
    request: EnvFileRequest,
    env_manager: EnvManager = Depends(get_env_manager),
    current_user = Depends(get_current_user)
):
    """
    Valide des variables d'environnement
    """
    try:
        # Créer un objet EnvFile temporaire
        variables = {}
        for name, var_req in request.variables.items():
            variables[name] = EnvVariable(
                name=name,
                value=var_req.value,
                description=var_req.description,
                is_secret=var_req.is_secret,
                is_required=var_req.is_required
            )
        
        env_file = EnvFile(
            path="validation.env",
            variables=variables,
            comments=request.comments
        )
        
        # Valider
        is_valid, errors, warnings = env_manager.validate_env_file(env_file)
        
        # Compter les variables sensibles
        secret_count = sum(1 for var in variables.values() if var.is_secret)
        
        return EnvValidationResponse(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            variables_count=len(variables),
            secret_variables_count=secret_count
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la validation des variables d'environnement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de validation: {str(e)}"
        )

@router.post("/files", response_model=EnvFileResponse, status_code=status.HTTP_201_CREATED)
async def create_env_file(
    file_path: str,
    request: EnvFileRequest,
    env_manager: EnvManager = Depends(get_env_manager),
    current_user = Depends(get_current_user)
):
    """
    Crée un nouveau fichier .env
    """
    try:
        # Convertir les variables
        variables = {
            name: var_req.value 
            for name, var_req in request.variables.items()
        }
        
        # Créer le fichier
        env_file = env_manager.create_env_file(file_path, variables)
        
        # Ajouter les commentaires et métadonnées
        for name, var_req in request.variables.items():
            if name in env_file.variables:
                env_file.variables[name].description = var_req.description
                env_file.variables[name].is_secret = var_req.is_secret
                env_file.variables[name].is_required = var_req.is_required
        
        env_file.comments = request.comments
        
        # Sauvegarder avec les métadonnées
        env_manager.save_env_file(env_file, backup=False)
        
        # Valider le fichier créé
        is_valid, errors, warnings = env_manager.validate_env_file(env_file)
        
        return EnvFileResponse(
            path=env_file.path,
            variables={
                name: {
                    'value': var.value if not var.is_secret else '***',
                    'description': var.description,
                    'is_secret': var.is_secret,
                    'is_required': var.is_required
                }
                for name, var in env_file.variables.items()
            },
            comments=env_file.comments,
            validation_result={
                'is_valid': is_valid,
                'errors': errors,
                'warnings': warnings
            }
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la création du fichier .env {file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de création: {str(e)}"
        )

@router.get("/files/{file_path:path}", response_model=EnvFileResponse)
async def get_env_file(
    file_path: str,
    env_manager: EnvManager = Depends(get_env_manager),
    current_user = Depends(get_current_user)
):
    """
    Récupère un fichier .env existant
    """
    try:
        env_file = env_manager.load_env_file(file_path)
        
        # Valider le fichier
        is_valid, errors, warnings = env_manager.validate_env_file(env_file)
        
        return EnvFileResponse(
            path=env_file.path,
            variables={
                name: {
                    'value': var.value if not var.is_secret else '***',
                    'description': var.description,
                    'is_secret': var.is_secret,
                    'is_required': var.is_required
                }
                for name, var in env_file.variables.items()
            },
            comments=env_file.comments,
            validation_result={
                'is_valid': is_valid,
                'errors': errors,
                'warnings': warnings
            }
        )
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fichier .env {file_path} non trouvé"
        )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du fichier .env {file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de récupération: {str(e)}"
        )

@router.put("/files/{file_path:path}", response_model=EnvFileResponse)
async def update_env_file(
    file_path: str,
    request: EnvFileRequest,
    env_manager: EnvManager = Depends(get_env_manager),
    current_user = Depends(get_current_user)
):
    """
    Met à jour un fichier .env existant
    """
    try:
        # Charger le fichier existant
        try:
            env_file = env_manager.load_env_file(file_path)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fichier .env {file_path} non trouvé"
            )
        
        # Mettre à jour les variables
        env_file.variables.clear()
        for name, var_req in request.variables.items():
            env_file.variables[name] = EnvVariable(
                name=name,
                value=var_req.value,
                description=var_req.description,
                is_secret=var_req.is_secret,
                is_required=var_req.is_required
            )
        
        # Mettre à jour les commentaires
        env_file.comments = request.comments
        
        # Sauvegarder avec backup
        env_manager.save_env_file(env_file, backup=True)
        
        # Valider le fichier mis à jour
        is_valid, errors, warnings = env_manager.validate_env_file(env_file)
        
        return EnvFileResponse(
            path=env_file.path,
            variables={
                name: {
                    'value': var.value if not var.is_secret else '***',
                    'description': var.description,
                    'is_secret': var.is_secret,
                    'is_required': var.is_required
                }
                for name, var in env_file.variables.items()
            },
            comments=env_file.comments,
            validation_result={
                'is_valid': is_valid,
                'errors': errors,
                'warnings': warnings
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du fichier .env {file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de mise à jour: {str(e)}"
        )

@router.delete("/files/{file_path:path}")
async def delete_env_file(
    file_path: str,
    current_user = Depends(get_current_user)
):
    """
    Supprime un fichier .env
    """
    try:
        from pathlib import Path
        
        file_obj = Path(file_path)
        if not file_obj.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fichier .env {file_path} non trouvé"
            )
        
        # Créer une sauvegarde avant suppression
        backup_path = file_obj.with_suffix('.env.deleted')
        file_obj.rename(backup_path)
        
        return {"message": f"Fichier .env {file_path} supprimé (sauvegarde: {backup_path})"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du fichier .env {file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de suppression: {str(e)}"
        )

@router.post("/template", response_model=EnvFileResponse)
async def generate_env_template(
    request: EnvTemplateRequest,
    env_manager: EnvManager = Depends(get_env_manager),
    current_user = Depends(get_current_user)
):
    """
    Génère un template .env basé sur des services
    """
    try:
        env_file = env_manager.generate_env_template(request.services)
        
        return EnvFileResponse(
            path=env_file.path,
            variables={
                name: {
                    'value': var.value,
                    'description': var.description,
                    'is_secret': var.is_secret,
                    'is_required': var.is_required
                }
                for name, var in env_file.variables.items()
            },
            comments=env_file.comments
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de génération: {str(e)}"
        )

@router.post("/merge", response_model=EnvFileResponse)
async def merge_env_files(
    file_paths: List[str],
    env_manager: EnvManager = Depends(get_env_manager),
    current_user = Depends(get_current_user)
):
    """
    Fusionne plusieurs fichiers .env
    """
    try:
        if not file_paths:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Au moins un fichier .env requis"
            )
        
        # Charger tous les fichiers
        env_files = []
        for file_path in file_paths:
            try:
                env_file = env_manager.load_env_file(file_path)
                env_files.append(env_file)
            except FileNotFoundError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Fichier .env {file_path} non trouvé"
                )
        
        # Fusionner
        merged_env = env_manager.merge_env_files(*env_files)
        
        return EnvFileResponse(
            path=merged_env.path,
            variables={
                name: {
                    'value': var.value if not var.is_secret else '***',
                    'description': var.description,
                    'is_secret': var.is_secret,
                    'is_required': var.is_required
                }
                for name, var in merged_env.variables.items()
            },
            comments=merged_env.comments
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la fusion des fichiers .env: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de fusion: {str(e)}"
        )

@router.post("/diff", response_model=EnvDiffResponse)
async def compare_env_files(
    file_path1: str,
    file_path2: str,
    env_manager: EnvManager = Depends(get_env_manager),
    current_user = Depends(get_current_user)
):
    """
    Compare deux fichiers .env
    """
    try:
        # Charger les deux fichiers
        try:
            env_file1 = env_manager.load_env_file(file_path1)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fichier .env {file_path1} non trouvé"
            )
        
        try:
            env_file2 = env_manager.load_env_file(file_path2)
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fichier .env {file_path2} non trouvé"
            )
        
        # Comparer
        diff = env_manager.get_environment_diff(env_file1, env_file2)
        
        return EnvDiffResponse(
            added=diff['added'],
            removed=diff['removed'],
            modified=diff['modified']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la comparaison des fichiers .env: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de comparaison: {str(e)}"
        )

@router.post("/substitute")
async def substitute_variables(
    request: EnvSubstitutionRequest,
    env_manager: EnvManager = Depends(get_env_manager),
    current_user = Depends(get_current_user)
):
    """
    Substitue les variables d'environnement dans un texte
    """
    try:
        # Créer un fichier .env temporaire
        variables = {}
        for name, value in request.variables.items():
            variables[name] = EnvVariable(name=name, value=value)
        
        env_file = EnvFile(
            path="temp.env",
            variables=variables
        )
        
        # Effectuer la substitution
        result = env_manager.substitute_variables(request.text, env_file)
        
        return {"result": result}
        
    except Exception as e:
        logger.error(f"Erreur lors de la substitution de variables: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de substitution: {str(e)}"
        )
