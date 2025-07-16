"""
Parseur et gestionnaire pour les fichiers Docker Compose
"""
import yaml
import re
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import logging
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

class ComposeService(BaseModel):
    """Modèle pour un service Docker Compose"""
    name: str
    image: Optional[str] = None
    build: Optional[Dict[str, Any]] = None
    ports: Optional[List[str]] = Field(default_factory=list)
    volumes: Optional[List[str]] = Field(default_factory=list)
    environment: Optional[Dict[str, str]] = Field(default_factory=dict)
    depends_on: Optional[List[str]] = Field(default_factory=list)
    networks: Optional[List[str]] = Field(default_factory=list)
    restart: Optional[str] = "no"
    command: Optional[str] = None
    entrypoint: Optional[str] = None
    working_dir: Optional[str] = None
    user: Optional[str] = None
    labels: Optional[Dict[str, str]] = Field(default_factory=dict)
    
    @validator('ports', pre=True)
    def validate_ports(cls, v):
        """Valide et normalise les ports"""
        if v is None:
            return []
        normalized = []
        for port in v:
            if isinstance(port, str):
                normalized.append(port)
            elif isinstance(port, int):
                normalized.append(str(port))
            elif isinstance(port, dict):
                # Format long: {target: 80, host_ip: "127.0.0.1", published: 8080}
                target = port.get('target', '')
                published = port.get('published', '')
                host_ip = port.get('host_ip', '')
                if host_ip:
                    normalized.append(f"{host_ip}:{published}:{target}")
                else:
                    normalized.append(f"{published}:{target}")
        return normalized

class ComposeNetwork(BaseModel):
    """Modèle pour un réseau Docker Compose"""
    name: str
    driver: Optional[str] = "bridge"
    external: Optional[bool] = False
    attachable: Optional[bool] = False
    ipam: Optional[Dict[str, Any]] = None
    labels: Optional[Dict[str, str]] = Field(default_factory=dict)

class ComposeVolume(BaseModel):
    """Modèle pour un volume Docker Compose"""
    name: str
    driver: Optional[str] = "local"
    external: Optional[bool] = False
    labels: Optional[Dict[str, str]] = Field(default_factory=dict)

class ComposeFile(BaseModel):
    """Modèle pour un fichier Docker Compose complet"""
    version: str
    services: Dict[str, ComposeService]
    networks: Optional[Dict[str, ComposeNetwork]] = Field(default_factory=dict)
    volumes: Optional[Dict[str, ComposeVolume]] = Field(default_factory=dict)
    
    @validator('version')
    def validate_version(cls, v):
        """Valide la version Docker Compose"""
        supported_versions = ['3.0', '3.1', '3.2', '3.3', '3.4', '3.5', '3.6', '3.7', '3.8', '3.9']
        if v not in supported_versions:
            logger.warning(f"Version Docker Compose non supportée ou obsolète: {v}")
        return v

class ComposeValidationError(Exception):
    """Exception pour les erreurs de validation Docker Compose"""
    pass

class ComposeParser:
    """Parseur pour les fichiers Docker Compose"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_file(self, file_path: str) -> ComposeFile:
        """
        Parse un fichier docker-compose.yml
        
        Args:
            file_path: Chemin vers le fichier docker-compose.yml
            
        Returns:
            ComposeFile: Configuration parsée
            
        Raises:
            ComposeValidationError: Si le fichier est invalide
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise ComposeValidationError(f"Fichier non trouvé: {file_path}")
            
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            return self._parse_compose_data(data)
            
        except yaml.YAMLError as e:
            raise ComposeValidationError(f"Erreur de syntaxe YAML: {e}")
        except Exception as e:
            raise ComposeValidationError(f"Erreur lors du parsing: {e}")
    
    def parse_yaml_content(self, yaml_content: str) -> ComposeFile:
        """
        Parse le contenu YAML d'un fichier Docker Compose
        
        Args:
            yaml_content: Contenu YAML en string
            
        Returns:
            ComposeFile: Configuration parsée
        """
        try:
            data = yaml.safe_load(yaml_content)
            return self._parse_compose_data(data)
        except yaml.YAMLError as e:
            raise ComposeValidationError(f"Erreur de syntaxe YAML: {e}")
    
    def _parse_compose_data(self, data: Dict[str, Any]) -> ComposeFile:
        """Parse les données de configuration Docker Compose"""
        if not isinstance(data, dict):
            raise ComposeValidationError("Le fichier doit contenir un objet YAML valide")
        
        # Vérifier la version
        version = data.get('version')
        if not version:
            raise ComposeValidationError("La version Docker Compose est requise")
        
        # Parser les services
        services_data = data.get('services', {})
        if not services_data:
            raise ComposeValidationError("Au moins un service doit être défini")
        
        services = {}
        for service_name, service_config in services_data.items():
            services[service_name] = self._parse_service(service_name, service_config)
        
        # Parser les réseaux
        networks = {}
        networks_data = data.get('networks', {})
        for network_name, network_config in networks_data.items():
            networks[network_name] = self._parse_network(network_name, network_config or {})
        
        # Parser les volumes
        volumes = {}
        volumes_data = data.get('volumes', {})
        for volume_name, volume_config in volumes_data.items():
            volumes[volume_name] = self._parse_volume(volume_name, volume_config or {})
        
        return ComposeFile(
            version=version,
            services=services,
            networks=networks,
            volumes=volumes
        )
    
    def _parse_service(self, name: str, config: Dict[str, Any]) -> ComposeService:
        """Parse la configuration d'un service"""
        if not isinstance(config, dict):
            raise ComposeValidationError(f"Configuration invalide pour le service {name}")
        
        # Traitement spécial pour l'environnement
        environment = self._parse_environment(config.get('environment', {}))
        
        # Traitement des dépendances
        depends_on = config.get('depends_on', [])
        if isinstance(depends_on, dict):
            depends_on = list(depends_on.keys())
        elif not isinstance(depends_on, list):
            depends_on = []
        
        # Traitement des réseaux
        networks = config.get('networks', [])
        if isinstance(networks, dict):
            networks = list(networks.keys())
        elif not isinstance(networks, list):
            networks = []
        
        return ComposeService(
            name=name,
            image=config.get('image'),
            build=config.get('build'),
            ports=config.get('ports', []),
            volumes=config.get('volumes', []),
            environment=environment,
            depends_on=depends_on,
            networks=networks,
            restart=config.get('restart', 'no'),
            command=config.get('command'),
            entrypoint=config.get('entrypoint'),
            working_dir=config.get('working_dir'),
            user=config.get('user'),
            labels=config.get('labels', {})
        )
    
    def _parse_environment(self, env_config: Any) -> Dict[str, str]:
        """Parse les variables d'environnement"""
        if env_config is None:
            return {}
        
        if isinstance(env_config, dict):
            return {k: str(v) for k, v in env_config.items()}
        
        if isinstance(env_config, list):
            env_dict = {}
            for item in env_config:
                if isinstance(item, str):
                    if '=' in item:
                        key, value = item.split('=', 1)
                        env_dict[key] = value
                    else:
                        env_dict[item] = ''
            return env_dict
        
        return {}
    
    def _parse_network(self, name: str, config: Dict[str, Any]) -> ComposeNetwork:
        """Parse la configuration d'un réseau"""
        return ComposeNetwork(
            name=name,
            driver=config.get('driver', 'bridge'),
            external=config.get('external', False),
            attachable=config.get('attachable', False),
            ipam=config.get('ipam'),
            labels=config.get('labels', {})
        )
    
    def _parse_volume(self, name: str, config: Dict[str, Any]) -> ComposeVolume:
        """Parse la configuration d'un volume"""
        return ComposeVolume(
            name=name,
            driver=config.get('driver', 'local'),
            external=config.get('external', False),
            labels=config.get('labels', {})
        )
    
    def validate_service_dependencies(self, compose: ComposeFile) -> List[str]:
        """
        Valide les dépendances entre services
        
        Returns:
            Liste des erreurs trouvées
        """
        errors = []
        service_names = set(compose.services.keys())
        
        for service_name, service in compose.services.items():
            for dependency in service.depends_on:
                if dependency not in service_names:
                    errors.append(f"Service {service_name} dépend de {dependency} qui n'existe pas")
        
        # Vérifier les cycles de dépendances
        if self._has_circular_dependencies(compose.services):
            errors.append("Dépendances circulaires détectées")
        
        return errors
    
    def _has_circular_dependencies(self, services: Dict[str, ComposeService]) -> bool:
        """Détecte les dépendances circulaires"""
        visited = set()
        rec_stack = set()
        
        def has_cycle(service_name: str) -> bool:
            if service_name in rec_stack:
                return True
            if service_name in visited:
                return False
            
            visited.add(service_name)
            rec_stack.add(service_name)
            
            service = services.get(service_name)
            if service:
                for dependency in service.depends_on:
                    if has_cycle(dependency):
                        return True
            
            rec_stack.remove(service_name)
            return False
        
        for service_name in services:
            if service_name not in visited:
                if has_cycle(service_name):
                    return True
        
        return False
    
    def extract_images(self, compose: ComposeFile) -> List[str]:
        """Extrait toutes les images utilisées dans le compose"""
        images = []
        for service in compose.services.values():
            if service.image:
                images.append(service.image)
        return list(set(images))
    
    def extract_ports(self, compose: ComposeFile) -> Dict[str, List[str]]:
        """Extrait tous les ports exposés par service"""
        ports = {}
        for service_name, service in compose.services.items():
            if service.ports:
                ports[service_name] = service.ports
        return ports
    
    def extract_volumes(self, compose: ComposeFile) -> Dict[str, List[str]]:
        """Extrait tous les volumes utilisés par service"""
        volumes = {}
        for service_name, service in compose.services.items():
            if service.volumes:
                volumes[service_name] = service.volumes
        return volumes
