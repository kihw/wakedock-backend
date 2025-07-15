"""
Gestionnaire Docker pour WakeDock
Gère les interactions avec l'API Docker
"""
import docker
from docker.errors import NotFound, APIError, ImageNotFound
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime
from wakedock.core.validation import validate_container_config, ValidationError

logger = logging.getLogger(__name__)

class DockerManager:
    """Gestionnaire principal pour les opérations Docker"""
    
    def __init__(self):
        """Initialise la connexion au daemon Docker"""
        try:
            self.client = docker.from_env()
            # Test de connexion
            self.client.ping()
            logger.info("Connexion au daemon Docker établie")
        except Exception as e:
            logger.error(f"Impossible de se connecter au daemon Docker: {e}")
            raise Exception(f"Erreur de connexion Docker: {e}")
    
    def list_containers(self, all: bool = False) -> List[docker.models.containers.Container]:
        """
        Liste tous les containers
        
        Args:
            all: Si True, inclut les containers arrêtés
            
        Returns:
            Liste des containers
        """
        try:
            return self.client.containers.list(all=all)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des containers: {e}")
            raise
    
    def get_container(self, container_id: str) -> Optional[docker.models.containers.Container]:
        """
        Récupère un container spécifique
        
        Args:
            container_id: ID ou nom du container
            
        Returns:
            Container ou None si non trouvé
        """
        try:
            return self.client.containers.get(container_id)
        except NotFound:
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du container {container_id}: {e}")
            raise
    
    def create_container(
        self,
        name: str,
        image: str,
        environment: Optional[Dict[str, str]] = None,
        ports: Optional[Dict[str, int]] = None,
        volumes: Optional[Dict[str, str]] = None,
        command: Optional[str] = None,
        working_dir: Optional[str] = None,
        restart_policy: str = "no"
    ) -> docker.models.containers.Container:
        """
        Crée un nouveau container
        
        Args:
            name: Nom du container
            image: Image Docker à utiliser
            environment: Variables d'environnement
            ports: Mapping des ports
            volumes: Volumes à monter
            command: Commande à exécuter
            working_dir: Répertoire de travail
            restart_policy: Politique de redémarrage
            
        Returns:
            Container créé
            
        Raises:
            ValidationError: Si la configuration est invalide
        """
        try:
            # Valider la configuration avant création
            validate_container_config(
                name=name,
                image=image,
                environment=environment,
                ports=ports,
                volumes=volumes,
                restart_policy=restart_policy
            )
            
            # Vérifier si l'image existe localement, sinon la télécharger
            try:
                self.client.images.get(image)
            except ImageNotFound:
                logger.info(f"Image {image} non trouvée localement, téléchargement en cours...")
                self.client.images.pull(image)
            
            # Préparer la configuration du container
            container_config = {
                "name": name,
                "image": image,
                "detach": True,
                "environment": environment or {},
                "restart_policy": {"Name": restart_policy}
            }
            
            # Ajouter la commande si spécifiée
            if command:
                container_config["command"] = command
            
            # Ajouter le répertoire de travail si spécifié
            if working_dir:
                container_config["working_dir"] = working_dir
            
            # Configurer les ports
            if ports:
                container_config["ports"] = ports
            
            # Configurer les volumes
            if volumes:
                container_config["volumes"] = volumes
            
            container = self.client.containers.create(**container_config)
            logger.info(f"Container {name} créé avec l'ID {container.id}")
            
            return container
            
        except ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la création du container {name}: {e}")
            raise
    
    def start_container(self, container_id: str) -> None:
        """
        Démarre un container
        
        Args:
            container_id: ID ou nom du container
        """
        try:
            container = self.get_container(container_id)
            if not container:
                raise NotFound(f"Container {container_id} non trouvé")
            
            container.start()
            logger.info(f"Container {container_id} démarré")
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage du container {container_id}: {e}")
            raise
    
    def stop_container(self, container_id: str, timeout: int = 10) -> None:
        """
        Arrête un container
        
        Args:
            container_id: ID ou nom du container
            timeout: Timeout en secondes avant kill forcé
        """
        try:
            container = self.get_container(container_id)
            if not container:
                raise NotFound(f"Container {container_id} non trouvé")
            
            container.stop(timeout=timeout)
            logger.info(f"Container {container_id} arrêté")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'arrêt du container {container_id}: {e}")
            raise
    
    def restart_container(self, container_id: str, timeout: int = 10) -> None:
        """
        Redémarre un container
        
        Args:
            container_id: ID ou nom du container
            timeout: Timeout en secondes
        """
        try:
            container = self.get_container(container_id)
            if not container:
                raise NotFound(f"Container {container_id} non trouvé")
            
            container.restart(timeout=timeout)
            logger.info(f"Container {container_id} redémarré")
            
        except Exception as e:
            logger.error(f"Erreur lors du redémarrage du container {container_id}: {e}")
            raise
    
    def remove_container(self, container_id: str, force: bool = False) -> None:
        """
        Supprime un container
        
        Args:
            container_id: ID ou nom du container
            force: Force la suppression même si le container est en cours d'exécution
        """
        try:
            container = self.get_container(container_id)
            if not container:
                raise NotFound(f"Container {container_id} non trouvé")
            
            container.remove(force=force)
            logger.info(f"Container {container_id} supprimé")
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du container {container_id}: {e}")
            raise
    
    def update_container(self, container_id: str, updates: Dict[str, Any]) -> docker.models.containers.Container:
        """
        Met à jour un container (nécessite souvent un redémarrage)
        
        Args:
            container_id: ID ou nom du container
            updates: Dictionnaire des mises à jour
            
        Returns:
            Container mis à jour
        """
        try:
            container = self.get_container(container_id)
            if not container:
                raise NotFound(f"Container {container_id} non trouvé")
            
            # Pour l'instant, on ne peut que renommer un container en cours d'exécution
            if "name" in updates:
                container.rename(updates["name"])
                logger.info(f"Container {container_id} renommé en {updates['name']}")
            
            # Recharger les informations du container
            container.reload()
            return container
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du container {container_id}: {e}")
            raise
    
    def get_container_logs(self, container_id: str, tail: int = 100, follow: bool = False) -> str:
        """
        Récupère les logs d'un container
        
        Args:
            container_id: ID ou nom du container
            tail: Nombre de lignes à récupérer
            follow: Mode streaming des logs
            
        Returns:
            Logs du container
        """
        try:
            container = self.get_container(container_id)
            if not container:
                raise NotFound(f"Container {container_id} non trouvé")
            
            logs = container.logs(tail=tail, follow=follow, timestamps=True)
            return logs.decode('utf-8') if isinstance(logs, bytes) else logs
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des logs du container {container_id}: {e}")
            raise
    
    def list_images(self, all: bool = False) -> List[docker.models.images.Image]:
        """
        Liste toutes les images Docker
        
        Args:
            all: Si True, inclut les images intermediaires
            
        Returns:
            Liste des images
        """
        try:
            return self.client.images.list(all=all)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des images: {e}")
            raise
    
    def pull_image(self, image: str, tag: str = "latest") -> docker.models.images.Image:
        """
        Télécharge une image Docker
        
        Args:
            image: Nom de l'image
            tag: Tag de l'image
            
        Returns:
            Image téléchargée
        """
        try:
            full_image = f"{image}:{tag}"
            image_obj = self.client.images.pull(image, tag=tag)
            logger.info(f"Image {full_image} téléchargée")
            return image_obj
            
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement de l'image {image}:{tag}: {e}")
            raise
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Récupère les informations système Docker
        
        Returns:
            Informations système
        """
        try:
            return self.client.info()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des informations système: {e}")
            raise
