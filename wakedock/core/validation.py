"""
Module de validation pour les containers Docker
"""
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Exception personnalisée pour les erreurs de validation"""

class ContainerValidator:
    """Classe pour valider les configurations de containers"""
    
    # Patterns de validation
    CONTAINER_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]+$')
    PORT_PATTERN = re.compile(r'^\d+(/tcp|/udp)?$')
    VOLUME_PATH_PATTERN = re.compile(r'^(/[^/ ]*)+/?$')
    ENV_VAR_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    
    # Ports réservés du système
    RESERVED_PORTS = set(range(1, 1024))
    
    # Variables d'environnement potentiellement dangereuses
    DANGEROUS_ENV_VARS = {
        'PATH', 'LD_LIBRARY_PATH', 'LD_PRELOAD', 'HOME', 'USER', 'ROOT'
    }
    
    @classmethod
    def validate_container_name(cls, name: str) -> Tuple[bool, Optional[str]]:
        """
        Valide le nom d'un container
        
        Args:
            name: Nom du container à valider
            
        Returns:
            Tuple (is_valid, error_message)
        """
        if not name:
            return False, "Le nom du container ne peut pas être vide"
        
        if len(name) < 2:
            return False, "Le nom du container doit contenir au moins 2 caractères"
        
        if len(name) > 253:
            return False, "Le nom du container ne peut pas dépasser 253 caractères"
        
        if not cls.CONTAINER_NAME_PATTERN.match(name):
            return False, "Le nom du container contient des caractères invalides. Utilisez uniquement a-z, A-Z, 0-9, _, ., -"
        
        if name.startswith('-') or name.endswith('-'):
            return False, "Le nom du container ne peut pas commencer ou finir par un tiret"
        
        if name.startswith('.') or name.endswith('.'):
            return False, "Le nom du container ne peut pas commencer ou finir par un point"
        
        return True, None
    
    @classmethod
    def validate_image_name(cls, image: str) -> Tuple[bool, Optional[str]]:
        """
        Valide le nom d'une image Docker
        
        Args:
            image: Nom de l'image à valider
            
        Returns:
            Tuple (is_valid, error_message)
        """
        if not image:
            return False, "Le nom de l'image ne peut pas être vide"
        
        # Séparer le registry, le nom et le tag
        parts = image.split('/')
        if len(parts) > 3:
            return False, "Format d'image invalide: trop de segments"
        
        # Vérifier le tag si présent
        if ':' in image:
            image_part, tag = image.rsplit(':', 1)
            if not tag or len(tag) > 128:
                return False, "Tag d'image invalide"
        
        return True, None
    
    @classmethod
    def validate_environment_variables(cls, env_vars: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Valide les variables d'environnement
        
        Args:
            env_vars: Dictionnaire des variables d'environnement
            
        Returns:
            Tuple (is_valid, list_of_errors)
        """
        errors = []
        
        if not env_vars:
            return True, []
        
        for var_name, var_value in env_vars.items():
            # Valider le nom de la variable
            if not cls.ENV_VAR_NAME_PATTERN.match(var_name):
                errors.append(f"Nom de variable d'environnement invalide: {var_name}")
                continue
            
            # Vérifier les variables dangereuses
            if var_name.upper() in cls.DANGEROUS_ENV_VARS:
                errors.append(f"Variable d'environnement potentiellement dangereuse: {var_name}")
            
            # Valider la valeur
            if var_value is None:
                errors.append(f"La valeur de la variable {var_name} ne peut pas être None")
                continue
            
            # Vérifier la longueur de la valeur
            if len(str(var_value)) > 32768:  # 32KB limit
                errors.append(f"La valeur de la variable {var_name} est trop longue (max 32KB)")
        
        return len(errors) == 0, errors
    
    @classmethod
    def validate_ports(cls, ports: Dict[str, int]) -> Tuple[bool, List[str]]:
        """
        Valide la configuration des ports
        
        Args:
            ports: Dictionnaire de mapping des ports (container_port: host_port)
            
        Returns:
            Tuple (is_valid, list_of_errors)
        """
        errors = []
        
        if not ports:
            return True, []
        
        used_host_ports = set()
        
        for container_port, host_port in ports.items():
            # Valider le port du container
            try:
                container_port_num = int(container_port.split('/')[0])
                if not (1 <= container_port_num <= 65535):
                    errors.append(f"Port container invalide: {container_port}")
            except (ValueError, IndexError):
                errors.append(f"Format de port container invalide: {container_port}")
                continue
            
            # Valider le port de l'hôte
            if not isinstance(host_port, int) or not (1 <= host_port <= 65535):
                errors.append(f"Port hôte invalide: {host_port}")
                continue
            
            # Vérifier les ports réservés pour l'hôte
            if host_port in cls.RESERVED_PORTS:
                errors.append(f"Port hôte réservé par le système: {host_port}")
            
            # Vérifier les doublons de ports hôte
            if host_port in used_host_ports:
                errors.append(f"Port hôte déjà utilisé: {host_port}")
            else:
                used_host_ports.add(host_port)
        
        return len(errors) == 0, errors
    
    @classmethod
    def validate_volumes(cls, volumes: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Valide la configuration des volumes
        
        Args:
            volumes: Dictionnaire de mapping des volumes (host_path: container_path)
            
        Returns:
            Tuple (is_valid, list_of_errors)
        """
        errors = []
        
        if not volumes:
            return True, []
        
        used_container_paths = set()
        
        for host_path, container_path in volumes.items():
            # Valider le chemin hôte
            if not host_path:
                errors.append("Chemin hôte ne peut pas être vide")
                continue
            
            # Valider le chemin container
            if not container_path:
                errors.append("Chemin container ne peut pas être vide")
                continue
            
            if not cls.VOLUME_PATH_PATTERN.match(container_path):
                errors.append(f"Chemin container invalide: {container_path}")
                continue
            
            # Vérifier les chemins système sensibles
            sensitive_paths = {'/etc', '/sys', '/proc', '/dev', '/root'}
            if any(container_path.startswith(path) for path in sensitive_paths):
                errors.append(f"Chemin container potentiellement dangereux: {container_path}")
            
            # Vérifier les doublons de chemins container
            if container_path in used_container_paths:
                errors.append(f"Chemin container déjà utilisé: {container_path}")
            else:
                used_container_paths.add(container_path)
        
        return len(errors) == 0, errors
    
    @classmethod
    def validate_restart_policy(cls, restart_policy: str) -> Tuple[bool, Optional[str]]:
        """
        Valide la politique de redémarrage
        
        Args:
            restart_policy: Politique de redémarrage
            
        Returns:
            Tuple (is_valid, error_message)
        """
        valid_policies = {
            'no', 'always', 'unless-stopped', 'on-failure'
        }
        
        if restart_policy not in valid_policies:
            return False, f"Politique de redémarrage invalide. Utilisez: {', '.join(valid_policies)}"
        
        return True, None
    
    @classmethod
    def validate_complete_container_config(
        cls,
        name: str,
        image: str,
        environment: Optional[Dict[str, str]] = None,
        ports: Optional[Dict[str, int]] = None,
        volumes: Optional[Dict[str, str]] = None,
        restart_policy: str = "no"
    ) -> Tuple[bool, List[str]]:
        """
        Valide une configuration complète de container
        
        Args:
            name: Nom du container
            image: Image Docker
            environment: Variables d'environnement
            ports: Configuration des ports
            volumes: Configuration des volumes
            restart_policy: Politique de redémarrage
            
        Returns:
            Tuple (is_valid, list_of_errors)
        """
        all_errors = []
        
        # Valider le nom
        is_valid, error = cls.validate_container_name(name)
        if not is_valid:
            all_errors.append(error)
        
        # Valider l'image
        is_valid, error = cls.validate_image_name(image)
        if not is_valid:
            all_errors.append(error)
        
        # Valider les variables d'environnement
        is_valid, errors = cls.validate_environment_variables(environment or {})
        if not is_valid:
            all_errors.extend(errors)
        
        # Valider les ports
        is_valid, errors = cls.validate_ports(ports or {})
        if not is_valid:
            all_errors.extend(errors)
        
        # Valider les volumes
        is_valid, errors = cls.validate_volumes(volumes or {})
        if not is_valid:
            all_errors.extend(errors)
        
        # Valider la politique de redémarrage
        is_valid, error = cls.validate_restart_policy(restart_policy)
        if not is_valid:
            all_errors.append(error)
        
        return len(all_errors) == 0, all_errors

def validate_container_config(**kwargs) -> None:
    """
    Fonction utilitaire pour valider une configuration de container
    Lève une ValidationError si la configuration est invalide
    
    Args:
        **kwargs: Configuration du container
        
    Raises:
        ValidationError: Si la configuration est invalide
    """
    is_valid, errors = ContainerValidator.validate_complete_container_config(**kwargs)
    
    if not is_valid:
        error_message = "Configuration de container invalide:\n" + "\n".join(f"- {error}" for error in errors)
        logger.error(error_message)
        raise ValidationError(error_message)
