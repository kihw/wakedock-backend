"""
Gestionnaire des réseaux Docker
"""
import docker
from docker.errors import NotFound, APIError
from typing import List, Dict, Optional, Any, Tuple
import ipaddress
import re
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)

class NetworkConfig(BaseModel):
    """Configuration pour un réseau Docker"""
    name: str = Field(..., description="Nom du réseau")
    driver: str = Field(default="bridge", description="Driver du réseau")
    attachable: bool = Field(default=False, description="Si le réseau est attachable")
    internal: bool = Field(default=False, description="Si le réseau est interne")
    enable_ipv6: bool = Field(default=False, description="Activer IPv6")
    ipam_driver: Optional[str] = Field(default=None, description="Driver IPAM")
    ipam_config: Optional[List[Dict[str, str]]] = Field(default=None, description="Configuration IPAM")
    options: Optional[Dict[str, str]] = Field(default_factory=dict, description="Options du driver")
    labels: Optional[Dict[str, str]] = Field(default_factory=dict, description="Labels du réseau")
    
    @validator('name')
    def validate_name(cls, v):
        """Valide le nom du réseau"""
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$', v):
            raise ValueError(f"Nom de réseau invalide: {v}")
        if len(v) > 63:
            raise ValueError("Nom de réseau trop long (max 63 caractères)")
        return v
    
    @validator('driver')
    def validate_driver(cls, v):
        """Valide le driver du réseau"""
        valid_drivers = ['bridge', 'host', 'none', 'overlay', 'macvlan', 'ipvlan']
        if v not in valid_drivers:
            logger.warning(f"Driver de réseau non standard: {v}")
        return v

class NetworkInfo(BaseModel):
    """Informations sur un réseau Docker"""
    id: str
    name: str
    driver: str
    scope: str
    internal: bool
    attachable: bool
    enable_ipv6: bool
    ipam: Dict[str, Any]
    containers: Dict[str, Dict[str, Any]]
    options: Dict[str, str]
    labels: Dict[str, str]
    created: str

class NetworkValidationError(Exception):
    """Exception pour les erreurs de validation de réseau"""
    pass

class NetworkManager:
    """Gestionnaire des réseaux Docker"""
    
    # Réseaux système qui ne doivent pas être modifiés
    SYSTEM_NETWORKS = {'bridge', 'host', 'none'}
    
    # Plages d'adresses privées (RFC 1918)
    PRIVATE_RANGES = [
        ipaddress.IPv4Network('10.0.0.0/8'),
        ipaddress.IPv4Network('172.16.0.0/12'),
        ipaddress.IPv4Network('192.168.0.0/16'),
    ]
    
    def __init__(self):
        """Initialise la connexion au daemon Docker"""
        try:
            self.client = docker.from_env()
            # Test de connexion
            self.client.ping()
            logger.info("Connexion au daemon Docker établie pour les réseaux")
        except Exception as e:
            logger.error(f"Impossible de se connecter au daemon Docker: {e}")
            raise Exception(f"Erreur de connexion Docker: {e}")
    
    def list_networks(self, include_system: bool = False) -> List[NetworkInfo]:
        """
        Liste tous les réseaux Docker
        
        Args:
            include_system: Inclure les réseaux système
            
        Returns:
            Liste des réseaux
        """
        try:
            networks = self.client.networks.list()
            result = []
            
            for network in networks:
                # Filtrer les réseaux système si demandé
                if not include_system and network.name in self.SYSTEM_NETWORKS:
                    continue
                
                network_info = self._format_network_info(network)
                result.append(network_info)
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des réseaux: {e}")
            raise
    
    def get_network(self, network_id: str) -> Optional[NetworkInfo]:
        """
        Récupère un réseau spécifique
        
        Args:
            network_id: ID ou nom du réseau
            
        Returns:
            Informations du réseau ou None si introuvable
        """
        try:
            network = self.client.networks.get(network_id)
            return self._format_network_info(network)
        except NotFound:
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du réseau {network_id}: {e}")
            raise
    
    def create_network(self, config: NetworkConfig) -> NetworkInfo:
        """
        Crée un nouveau réseau Docker
        
        Args:
            config: Configuration du réseau
            
        Returns:
            Informations du réseau créé
            
        Raises:
            NetworkValidationError: Si la configuration est invalide
        """
        try:
            # Valider la configuration
            self._validate_network_config(config)
            
            # Vérifier si le réseau existe déjà
            if self._network_exists(config.name):
                raise NetworkValidationError(f"Le réseau {config.name} existe déjà")
            
            # Préparer les options IPAM
            ipam_config = None
            if config.ipam_config:
                ipam_config = docker.types.IPAMConfig(
                    driver=config.ipam_driver,
                    pool_configs=config.ipam_config
                )
            
            # Créer le réseau
            network = self.client.networks.create(
                name=config.name,
                driver=config.driver,
                attachable=config.attachable,
                internal=config.internal,
                enable_ipv6=config.enable_ipv6,
                ipam=ipam_config,
                options=config.options,
                labels=config.labels
            )
            
            logger.info(f"Réseau {config.name} créé avec succès")
            return self._format_network_info(network)
            
        except docker.errors.APIError as e:
            logger.error(f"Erreur API Docker lors de la création du réseau: {e}")
            raise NetworkValidationError(f"Erreur Docker: {e}")
        except Exception as e:
            logger.error(f"Erreur lors de la création du réseau {config.name}: {e}")
            raise
    
    def remove_network(self, network_id: str, force: bool = False) -> bool:
        """
        Supprime un réseau Docker
        
        Args:
            network_id: ID ou nom du réseau
            force: Forcer la suppression même si des containers sont connectés
            
        Returns:
            True si supprimé avec succès
            
        Raises:
            NetworkValidationError: Si le réseau ne peut pas être supprimé
        """
        try:
            network = self.client.networks.get(network_id)
            
            # Vérifier que ce n'est pas un réseau système
            if network.name in self.SYSTEM_NETWORKS:
                raise NetworkValidationError(f"Impossible de supprimer le réseau système {network.name}")
            
            # Vérifier les containers connectés
            network.reload()
            connected_containers = network.attrs.get('Containers', {})
            
            if connected_containers and not force:
                container_names = [info.get('Name', 'inconnu') for info in connected_containers.values()]
                raise NetworkValidationError(
                    f"Le réseau {network.name} est utilisé par des containers: {', '.join(container_names)}"
                )
            
            # Déconnecter tous les containers si force=True
            if force and connected_containers:
                for container_info in connected_containers.values():
                    container_name = container_info.get('Name')
                    if container_name:
                        try:
                            container = self.client.containers.get(container_name)
                            network.disconnect(container)
                            logger.info(f"Container {container_name} déconnecté du réseau {network.name}")
                        except Exception as e:
                            logger.warning(f"Impossible de déconnecter {container_name}: {e}")
            
            # Supprimer le réseau
            network.remove()
            logger.info(f"Réseau {network.name} supprimé")
            return True
            
        except NotFound:
            logger.warning(f"Réseau {network_id} non trouvé")
            return False
        except NetworkValidationError:
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du réseau {network_id}: {e}")
            raise
    
    def connect_container(self, network_id: str, container_id: str, 
                         aliases: Optional[List[str]] = None,
                         ipv4_address: Optional[str] = None,
                         ipv6_address: Optional[str] = None) -> bool:
        """
        Connecte un container à un réseau
        
        Args:
            network_id: ID ou nom du réseau
            container_id: ID ou nom du container
            aliases: Alias réseau pour le container
            ipv4_address: Adresse IPv4 spécifique
            ipv6_address: Adresse IPv6 spécifique
            
        Returns:
            True si connecté avec succès
        """
        try:
            network = self.client.networks.get(network_id)
            container = self.client.containers.get(container_id)
            
            # Vérifier si déjà connecté
            network.reload()
            connected_containers = network.attrs.get('Containers', {})
            if container.id in connected_containers:
                logger.info(f"Container {container.name} déjà connecté au réseau {network.name}")
                return True
            
            # Préparer la configuration de connexion
            connect_config = {}
            if aliases:
                connect_config['aliases'] = aliases
            if ipv4_address:
                self._validate_ip_address(ipv4_address, 4)
                connect_config['ipv4_address'] = ipv4_address
            if ipv6_address:
                self._validate_ip_address(ipv6_address, 6)
                connect_config['ipv6_address'] = ipv6_address
            
            # Connecter le container
            if connect_config:
                network.connect(container, **connect_config)
            else:
                network.connect(container)
            
            logger.info(f"Container {container.name} connecté au réseau {network.name}")
            return True
            
        except NotFound as e:
            logger.error(f"Réseau ou container non trouvé: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur lors de la connexion: {e}")
            raise
    
    def disconnect_container(self, network_id: str, container_id: str, force: bool = False) -> bool:
        """
        Déconnecte un container d'un réseau
        
        Args:
            network_id: ID ou nom du réseau
            container_id: ID ou nom du container
            force: Forcer la déconnexion
            
        Returns:
            True si déconnecté avec succès
        """
        try:
            network = self.client.networks.get(network_id)
            container = self.client.containers.get(container_id)
            
            network.disconnect(container, force=force)
            logger.info(f"Container {container.name} déconnecté du réseau {network.name}")
            return True
            
        except NotFound as e:
            logger.error(f"Réseau ou container non trouvé: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur lors de la déconnexion: {e}")
            raise
    
    def prune_networks(self) -> Dict[str, Any]:
        """
        Supprime les réseaux inutilisés
        
        Returns:
            Informations sur les réseaux supprimés
        """
        try:
            result = self.client.networks.prune()
            logger.info(f"Nettoyage des réseaux: {len(result.get('NetworksDeleted', []))} supprimés")
            return result
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des réseaux: {e}")
            raise
    
    def inspect_network_connectivity(self, network_id: str) -> Dict[str, Any]:
        """
        Analyse la connectivité d'un réseau
        
        Args:
            network_id: ID ou nom du réseau
            
        Returns:
            Informations sur la connectivité
        """
        try:
            network = self.client.networks.get(network_id)
            network.reload()
            
            attrs = network.attrs
            containers = attrs.get('Containers', {})
            
            connectivity_info = {
                'network_name': network.name,
                'network_id': network.id,
                'driver': attrs.get('Driver'),
                'scope': attrs.get('Scope'),
                'containers_count': len(containers),
                'containers': [],
                'ipam_config': attrs.get('IPAM', {}),
                'internal': attrs.get('Internal', False),
                'attachable': attrs.get('Attachable', False)
            }
            
            # Analyser chaque container connecté
            for container_id, container_info in containers.items():
                try:
                    container = self.client.containers.get(container_id)
                    connectivity_info['containers'].append({
                        'id': container_id,
                        'name': container_info.get('Name'),
                        'ipv4_address': container_info.get('IPv4Address'),
                        'ipv6_address': container_info.get('IPv6Address'),
                        'mac_address': container_info.get('MacAddress'),
                        'endpoint_id': container_info.get('EndpointID'),
                        'status': container.status
                    })
                except Exception as e:
                    logger.warning(f"Impossible d'analyser le container {container_id}: {e}")
            
            return connectivity_info
            
        except NotFound:
            return {'error': f'Réseau {network_id} non trouvé'}
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse du réseau {network_id}: {e}")
            raise
    
    def _format_network_info(self, network) -> NetworkInfo:
        """Formate les informations d'un réseau Docker"""
        attrs = network.attrs
        
        return NetworkInfo(
            id=network.id,
            name=network.name,
            driver=attrs.get('Driver', ''),
            scope=attrs.get('Scope', ''),
            internal=attrs.get('Internal', False),
            attachable=attrs.get('Attachable', False),
            enable_ipv6=attrs.get('EnableIPv6', False),
            ipam=attrs.get('IPAM', {}),
            containers=attrs.get('Containers', {}),
            options=attrs.get('Options', {}),
            labels=attrs.get('Labels', {}),
            created=attrs.get('Created', '')
        )
    
    def _validate_network_config(self, config: NetworkConfig):
        """Valide une configuration de réseau"""
        
        # Valider les adresses IPAM si spécifiées
        if config.ipam_config:
            for ipam_pool in config.ipam_config:
                subnet = ipam_pool.get('subnet')
                if subnet:
                    try:
                        network = ipaddress.ip_network(subnet, strict=False)
                        
                        # Vérifier que c'est une plage privée pour la sécurité
                        if not any(network.overlaps(private_range) for private_range in self.PRIVATE_RANGES):
                            logger.warning(f"Subnet {subnet} n'est pas dans une plage d'adresses privées")
                        
                    except ValueError as e:
                        raise NetworkValidationError(f"Subnet invalide {subnet}: {e}")
                
                gateway = ipam_pool.get('gateway')
                if gateway:
                    self._validate_ip_address(gateway, 4)
        
        # Valider les options spécifiques au driver
        if config.driver == 'macvlan':
            if 'parent' not in config.options:
                raise NetworkValidationError("Driver macvlan nécessite l'option 'parent'")
        
        elif config.driver == 'overlay':
            if not config.attachable:
                logger.info("Réseau overlay non attachable - seulement pour Docker Swarm")
    
    def _validate_ip_address(self, ip_address: str, version: int):
        """Valide une adresse IP"""
        try:
            if version == 4:
                ipaddress.IPv4Address(ip_address)
            elif version == 6:
                ipaddress.IPv6Address(ip_address)
            else:
                raise ValueError(f"Version IP invalide: {version}")
        except ValueError as e:
            raise NetworkValidationError(f"Adresse IP invalide {ip_address}: {e}")
    
    def _network_exists(self, name: str) -> bool:
        """Vérifie si un réseau existe"""
        try:
            self.client.networks.get(name)
            return True
        except NotFound:
            return False
        except Exception:
            return False
    
    def get_network_usage_report(self) -> Dict[str, Any]:
        """
        Génère un rapport d'utilisation des réseaux
        
        Returns:
            Rapport détaillé sur l'utilisation des réseaux
        """
        try:
            networks = self.list_networks(include_system=True)
            
            report = {
                'total_networks': len(networks),
                'system_networks': 0,
                'custom_networks': 0,
                'attached_containers': 0,
                'drivers_usage': {},
                'networks_details': [],
                'unused_networks': []
            }
            
            for network in networks:
                # Compter par type
                if network.name in self.SYSTEM_NETWORKS:
                    report['system_networks'] += 1
                else:
                    report['custom_networks'] += 1
                
                # Compter par driver
                driver = network.driver
                if driver not in report['drivers_usage']:
                    report['drivers_usage'][driver] = 0
                report['drivers_usage'][driver] += 1
                
                # Compter les containers
                containers_count = len(network.containers)
                report['attached_containers'] += containers_count
                
                # Détails du réseau
                network_detail = {
                    'name': network.name,
                    'driver': driver,
                    'containers_count': containers_count,
                    'internal': network.internal,
                    'attachable': network.attachable
                }
                report['networks_details'].append(network_detail)
                
                # Réseaux inutilisés
                if containers_count == 0 and network.name not in self.SYSTEM_NETWORKS:
                    report['unused_networks'].append(network.name)
            
            return report
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du rapport: {e}")
            raise
