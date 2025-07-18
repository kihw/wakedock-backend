"""
Modèles pour la gestion des stacks Docker
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class StackType(str, Enum):
    """Types de stacks supportés"""
    COMPOSE = "compose"
    SWARM = "swarm"
    KUBERNETES = "kubernetes"
    STANDALONE = "standalone"
    CUSTOM = "custom"


class StackStatus(str, Enum):
    """États possibles d'une stack"""
    RUNNING = "running"
    STOPPED = "stopped"
    STARTING = "starting"
    STOPPING = "stopping"
    ERROR = "error"
    UNKNOWN = "unknown"


class ContainerStackInfo(BaseModel):
    """Informations sur l'appartenance d'un container à une stack"""
    container_id: str
    container_name: str
    image: str
    status: str
    ports: Optional[Dict[str, Any]] = None
    environment: Optional[Dict[str, str]] = None
    labels: Optional[Dict[str, str]] = None
    depends_on: Optional[List[str]] = None
    service_name: Optional[str] = None
    replica_number: Optional[int] = None


class StackInfo(BaseModel):
    """Informations complètes sur une stack"""
    id: str = Field(..., description="Identifiant unique de la stack")
    name: str = Field(..., description="Nom de la stack")
    type: StackType = Field(..., description="Type de stack")
    status: StackStatus = Field(..., description="État de la stack")
    created: datetime = Field(..., description="Date de création")
    updated: datetime = Field(..., description="Date de dernière mise à jour")
    
    # Containers appartenant à cette stack
    containers: List[ContainerStackInfo] = Field(default_factory=list, description="Containers de la stack")
    
    # Métadonnées
    project_name: Optional[str] = None
    compose_file: Optional[str] = None
    working_dir: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
    
    # Statistiques
    total_containers: int = 0
    running_containers: int = 0
    stopped_containers: int = 0
    error_containers: int = 0
    
    # Configuration
    environment: Optional[Dict[str, str]] = None
    networks: Optional[List[str]] = None
    volumes: Optional[List[str]] = None


class StackDetectionRule(BaseModel):
    """Règle de détection pour identifier les stacks"""
    name: str = Field(..., description="Nom de la règle")
    description: Optional[str] = None
    enabled: bool = True
    
    # Critères de détection
    label_patterns: Optional[Dict[str, str]] = None  # Patterns pour les labels
    name_patterns: Optional[List[str]] = None  # Patterns pour les noms
    image_patterns: Optional[List[str]] = None  # Patterns pour les images
    network_patterns: Optional[List[str]] = None  # Patterns pour les réseaux
    
    # Action à effectuer
    stack_type: StackType = StackType.CUSTOM
    group_by: str = "label"  # "label", "name", "network", "compose"
    group_key: str = "com.docker.compose.project"
    
    # Priorité (plus élevée = plus prioritaire)
    priority: int = 0


class StackSummary(BaseModel):
    """Résumé d'une stack pour les listes"""
    id: str
    name: str
    type: StackType
    status: StackStatus
    total_containers: int
    running_containers: int
    created: datetime
    updated: datetime
    project_name: Optional[str] = None
    labels: Optional[Dict[str, str]] = None
