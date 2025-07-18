"""
Validation des configurations Docker Compose
"""
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wakedock.core.compose_parser import ComposeFile, ComposeService

logger = logging.getLogger(__name__)

class ComposeValidator:
    """Validateur pour les configurations Docker Compose"""
    
    # Ports réservés système
    RESERVED_PORTS = set(range(1, 1024))
    
    # Ports Docker couramment utilisés
    DOCKER_RESERVED_PORTS = {2375, 2376, 2377, 4789, 7946}
    
    # Variables d'environnement sensibles
    SENSITIVE_ENV_VARS = {
        'PASSWORD', 'SECRET', 'KEY', 'TOKEN', 'API_KEY', 'PRIVATE_KEY',
        'DATABASE_URL', 'DB_PASSWORD', 'REDIS_PASSWORD', 'JWT_SECRET'
    }
    
    # Images potentiellement dangereuses
    RISKY_IMAGES = {
        'alpine:latest', 'ubuntu:latest', 'centos:latest', 'debian:latest'
    }
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_compose(self, compose: ComposeFile) -> Tuple[bool, List[str], List[str]]:
        """
        Valide une configuration Docker Compose complète
        
        Args:
            compose: Configuration à valider
            
        Returns:
            Tuple (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        # Validation de la version
        self._validate_version(compose.version)
        
        # Validation des services
        self._validate_services(compose.services)
        
        # Validation des dépendances
        self._validate_dependencies(compose.services)
        
        # Validation des ports
        self._validate_ports(compose.services)
        
        # Validation des volumes
        self._validate_volumes(compose.services)
        
        # Validation des réseaux
        self._validate_networks(compose.networks, compose.services)
        
        # Validation de sécurité
        self._validate_security(compose.services)
        
        return len(self.errors) == 0, self.errors.copy(), self.warnings.copy()
    
    def _validate_version(self, version: str):
        """Valide la version Docker Compose"""
        if not version:
            self.errors.append("Version Docker Compose manquante")
            return
        
        # Versions obsolètes
        obsolete_versions = ['2.0', '2.1', '2.2', '2.3', '2.4']
        if version in obsolete_versions:
            self.warnings.append(f"Version Docker Compose obsolète: {version}")
        
        # Versions très anciennes
        if version.startswith('1.'):
            self.errors.append(f"Version Docker Compose non supportée: {version}")
        
        # Recommandation pour les dernières versions
        if version in ['3.0', '3.1', '3.2']:
            self.warnings.append(f"Version {version} est ancienne, considérez une mise à jour")
    
    def _validate_services(self, services: Dict[str, ComposeService]):
        """Valide les services individuellement"""
        if not services:
            self.errors.append("Aucun service défini")
            return
        
        for service_name, service in services.items():
            self._validate_service(service_name, service)
    
    def _validate_service(self, name: str, service: ComposeService):
        """Valide un service spécifique"""
        # Nom du service
        if not self._is_valid_service_name(name):
            self.errors.append(f"Nom de service invalide: {name}")
        
        # Image ou build requis
        if not service.image and not service.build:
            self.errors.append(f"Service {name}: image ou build requis")
        
        if service.image and service.build:
            self.warnings.append(f"Service {name}: image et build définis, build sera prioritaire")
        
        # Validation de l'image
        if service.image:
            self._validate_image(name, service.image)
        
        # Validation du build
        if service.build:
            self._validate_build(name, service.build)
        
        # Validation des variables d'environnement
        self._validate_environment(name, service.environment)
        
        # Validation de la politique de redémarrage
        self._validate_restart_policy(name, service.restart)
    
    def _validate_dependencies(self, services: Dict[str, ComposeService]):
        """Valide les dépendances entre services"""
        service_names = set(services.keys())
        
        for service_name, service in services.items():
            for dependency in service.depends_on:
                if dependency not in service_names:
                    self.errors.append(f"Service {service_name}: dépendance inexistante {dependency}")
        
        # Vérifier les cycles
        if self._has_circular_dependencies(services):
            self.errors.append("Dépendances circulaires détectées")
    
    def _validate_ports(self, services: Dict[str, ComposeService]):
        """Valide les ports exposés"""
        used_host_ports = set()
        
        for service_name, service in services.items():
            for port_mapping in service.ports:
                host_port = self._extract_host_port(port_mapping)
                if host_port:
                    # Vérifier les ports réservés
                    if host_port in self.RESERVED_PORTS:
                        self.warnings.append(
                            f"Service {service_name}: port système réservé {host_port}"
                        )
                    
                    if host_port in self.DOCKER_RESERVED_PORTS:
                        self.errors.append(
                            f"Service {service_name}: port Docker réservé {host_port}"
                        )
                    
                    # Vérifier les doublons
                    if host_port in used_host_ports:
                        self.errors.append(
                            f"Service {service_name}: port {host_port} déjà utilisé"
                        )
                    else:
                        used_host_ports.add(host_port)
    
    def _validate_volumes(self, services: Dict[str, ComposeService]):
        """Valide les volumes montés"""
        for service_name, service in services.items():
            for volume in service.volumes:
                self._validate_volume_mount(service_name, volume)
    
    def _validate_networks(self, networks: Dict[str, Any], services: Dict[str, ComposeService]):
        """Valide les réseaux"""
        # Collecter tous les réseaux utilisés par les services
        used_networks = set()
        for service in services.values():
            used_networks.update(service.networks)
        
        # Vérifier que tous les réseaux utilisés sont définis
        defined_networks = set(networks.keys()) if networks else set()
        undefined_networks = used_networks - defined_networks - {'default'}
        
        for network in undefined_networks:
            self.errors.append(f"Réseau {network} utilisé mais non défini")
    
    def _validate_security(self, services: Dict[str, ComposeService]):
        """Valide les aspects de sécurité"""
        for service_name, service in services.items():
            # Images avec tag latest
            if service.image and service.image.endswith(':latest'):
                self.warnings.append(
                    f"Service {service_name}: évitez le tag 'latest' en production"
                )
            
            # Images risquées
            if service.image in self.RISKY_IMAGES:
                self.warnings.append(
                    f"Service {service_name}: image de base générique {service.image}"
                )
            
            # Variables sensibles en clair
            for env_name, env_value in service.environment.items():
                if any(sensitive in env_name.upper() for sensitive in self.SENSITIVE_ENV_VARS):
                    if not env_value.startswith('$'):
                        self.warnings.append(
                            f"Service {service_name}: variable sensible {env_name} en clair"
                        )
            
            # Utilisateur root
            if service.user == 'root' or service.user == '0':
                self.warnings.append(
                    f"Service {service_name}: exécution en tant que root"
                )
            
            # Montage du socket Docker
            for volume in service.volumes:
                if '/var/run/docker.sock' in volume:
                    self.warnings.append(
                        f"Service {service_name}: montage du socket Docker (accès privilégié)"
                    )
    
    def _is_valid_service_name(self, name: str) -> bool:
        """Valide le nom d'un service"""
        if not name:
            return False
        
        # Doit commencer par une lettre ou un chiffre
        if not re.match(r'^[a-zA-Z0-9]', name):
            return False
        
        # Caractères autorisés: lettres, chiffres, tirets, underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return False
        
        # Longueur raisonnable
        if len(name) > 63:
            return False
        
        return True
    
    def _validate_image(self, service_name: str, image: str):
        """Valide une référence d'image"""
        if not image:
            return
        
        # Format de base: [registry/]namespace/repository[:tag]
        if not re.match(r'^[a-zA-Z0-9._/-]+(:([a-zA-Z0-9._-]+))?$', image):
            self.errors.append(f"Service {service_name}: format d'image invalide {image}")
        
        # Vérifier la longueur
        if len(image) > 255:
            self.errors.append(f"Service {service_name}: nom d'image trop long")
    
    def _validate_build(self, service_name: str, build_config: Any):
        """Valide la configuration de build"""
        if isinstance(build_config, str):
            # Build context simple
            if not Path(build_config).exists():
                self.warnings.append(
                    f"Service {service_name}: contexte de build {build_config} introuvable"
                )
        elif isinstance(build_config, dict):
            context = build_config.get('context', '.')
            if not Path(context).exists():
                self.warnings.append(
                    f"Service {service_name}: contexte de build {context} introuvable"
                )
            
            dockerfile = build_config.get('dockerfile')
            if dockerfile:
                dockerfile_path = Path(context) / dockerfile
                if not dockerfile_path.exists():
                    self.warnings.append(
                        f"Service {service_name}: Dockerfile {dockerfile} introuvable"
                    )
    
    def _validate_environment(self, service_name: str, environment: Dict[str, str]):
        """Valide les variables d'environnement"""
        for env_name, env_value in environment.items():
            # Nom de variable valide
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', env_name):
                self.errors.append(
                    f"Service {service_name}: nom de variable invalide {env_name}"
                )
            
            # Variables système importantes
            if env_name in ['PATH', 'HOME', 'USER']:
                self.warnings.append(
                    f"Service {service_name}: modification de variable système {env_name}"
                )
    
    def _validate_restart_policy(self, service_name: str, restart_policy: str):
        """Valide la politique de redémarrage"""
        valid_policies = ['no', 'always', 'on-failure', 'unless-stopped']
        
        if restart_policy not in valid_policies:
            # Vérifier le format on-failure:max-retries
            if not re.match(r'^on-failure:\d+$', restart_policy):
                self.errors.append(
                    f"Service {service_name}: politique de redémarrage invalide {restart_policy}"
                )
    
    def _extract_host_port(self, port_mapping: str) -> Optional[int]:
        """Extrait le port hôte d'un mapping de port"""
        try:
            # Formats: "8080:80", "127.0.0.1:8080:80", "8080"
            if ':' in port_mapping:
                parts = port_mapping.split(':')
                if len(parts) == 2:
                    return int(parts[0])
                elif len(parts) == 3:
                    return int(parts[1])
            else:
                return int(port_mapping)
        except (ValueError, IndexError):
            return None
    
    def _validate_volume_mount(self, service_name: str, volume: str):
        """Valide un montage de volume"""
        # Formats possibles:
        # - volume_name:/path
        # - /host/path:/container/path
        # - /host/path:/container/path:ro
        
        if ':' not in volume:
            # Volume sans mapping spécifique
            return
        
        parts = volume.split(':')
        if len(parts) < 2:
            self.errors.append(f"Service {service_name}: format de volume invalide {volume}")
            return
        
        source = parts[0]
        target = parts[1]
        
        # Vérifier le chemin de destination
        if not target.startswith('/'):
            self.errors.append(
                f"Service {service_name}: chemin de destination invalide {target}"
            )
        
        # Vérifier le chemin source (si c'est un chemin absolu)
        if source.startswith('/'):
            # Chemins sensibles
            sensitive_paths = ['/etc', '/var/run', '/sys', '/proc', '/dev']
            if any(source.startswith(path) for path in sensitive_paths):
                self.warnings.append(
                    f"Service {service_name}: montage de chemin sensible {source}"
                )
        
        # Vérifier les options (ro, rw, etc.)
        if len(parts) > 2:
            options = parts[2]
            valid_options = ['ro', 'rw', 'z', 'Z', 'consistent', 'cached', 'delegated']
            if options not in valid_options:
                self.warnings.append(
                    f"Service {service_name}: option de volume inconnue {options}"
                )
    
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
