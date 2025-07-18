"""
Gestionnaire de déploiement pour les stacks Docker Compose
"""
import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from wakedock.core.compose_parser import ComposeParser
from wakedock.core.compose_validator import ComposeValidator
from wakedock.core.dependency_manager import DependencyManager
from wakedock.core.env_manager import EnvManager

logger = logging.getLogger(__name__)

class DeploymentStatus(Enum):
    """États de déploiement"""
    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"
    UPDATING = "updating"

@dataclass
class DeploymentResult:
    """Résultat d'un déploiement"""
    success: bool
    status: DeploymentStatus
    message: str
    services_deployed: List[str]
    services_failed: List[str]
    deployment_time: float
    logs: List[str]

class ComposeDeploymentManager:
    """Gestionnaire de déploiement Docker Compose"""
    
    def __init__(self, work_dir: str = "/tmp/wakedock_deployments"):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        self.parser = ComposeParser()
        self.validator = ComposeValidator()
        self.env_manager = EnvManager()
        self.dependency_manager = DependencyManager()
        
        self.logger = logging.getLogger(__name__)
        
        # États des déploiements actifs
        self.active_deployments: Dict[str, Dict[str, Any]] = {}
    
    def deploy_stack(self, 
                    stack_name: str,
                    compose_content: str,
                    env_variables: Optional[Dict[str, str]] = None,
                    env_file_content: Optional[str] = None,
                    validate_only: bool = False) -> DeploymentResult:
        """
        Déploie une stack Docker Compose
        
        Args:
            stack_name: Nom de la stack
            compose_content: Contenu du fichier docker-compose.yml
            env_variables: Variables d'environnement additionnelles
            env_file_content: Contenu du fichier .env
            validate_only: Si True, ne fait que valider sans déployer
            
        Returns:
            DeploymentResult: Résultat du déploiement
        """
        start_time = time.time()
        deployment_logs = []
        
        try:
            self.logger.info(f"Début du déploiement de la stack {stack_name}")
            deployment_logs.append(f"Début du déploiement de {stack_name}")
            
            # Créer un répertoire de travail pour cette stack
            stack_dir = self.work_dir / stack_name
            stack_dir.mkdir(parents=True, exist_ok=True)
            
            # Parser et valider la configuration
            compose = self.parser.parse_yaml_content(compose_content)
            is_valid, errors, warnings = self.validator.validate_compose(compose)
            
            if not is_valid:
                return DeploymentResult(
                    success=False,
                    status=DeploymentStatus.FAILED,
                    message=f"Validation échouée: {'; '.join(errors)}",
                    services_deployed=[],
                    services_failed=list(compose.services.keys()),
                    deployment_time=time.time() - start_time,
                    logs=deployment_logs + [f"Erreurs: {errors}"]
                )
            
            if warnings:
                self.logger.warning(f"Avertissements pour {stack_name}: {warnings}")
                deployment_logs.append(f"Avertissements: {warnings}")
            
            # Analyser les dépendances
            dep_graph = self.dependency_manager.analyze_dependencies(compose)
            dep_valid, dep_errors = self.dependency_manager.validate_dependencies(dep_graph)
            
            if not dep_valid:
                return DeploymentResult(
                    success=False,
                    status=DeploymentStatus.FAILED,
                    message=f"Dépendances invalides: {'; '.join(dep_errors)}",
                    services_deployed=[],
                    services_failed=list(compose.services.keys()),
                    deployment_time=time.time() - start_time,
                    logs=deployment_logs + [f"Erreurs de dépendances: {dep_errors}"]
                )
            
            if validate_only:
                return DeploymentResult(
                    success=True,
                    status=DeploymentStatus.PENDING,
                    message="Validation réussie",
                    services_deployed=[],
                    services_failed=[],
                    deployment_time=time.time() - start_time,
                    logs=deployment_logs + ["Validation uniquement - pas de déploiement"]
                )
            
            # Préparer les fichiers
            self._prepare_deployment_files(stack_dir, compose_content, env_variables, env_file_content)
            
            # Marquer le déploiement comme actif
            self.active_deployments[stack_name] = {
                'status': DeploymentStatus.DEPLOYING,
                'start_time': start_time,
                'services': list(compose.services.keys())
            }
            
            # Déployer selon l'ordre des dépendances
            parallel_groups = self.dependency_manager.optimize_startup_order(dep_graph)
            services_deployed = []
            services_failed = []
            
            for group in parallel_groups:
                group_result = self._deploy_service_group(stack_name, stack_dir, group)
                services_deployed.extend(group_result['deployed'])
                services_failed.extend(group_result['failed'])
                deployment_logs.extend(group_result['logs'])
                
                if group_result['failed']:
                    # Arrêter le déploiement en cas d'échec
                    break
            
            # Vérifier le résultat final
            success = len(services_failed) == 0
            status = DeploymentStatus.RUNNING if success else DeploymentStatus.FAILED
            
            # Mettre à jour l'état
            self.active_deployments[stack_name]['status'] = status
            
            return DeploymentResult(
                success=success,
                status=status,
                message="Déploiement réussi" if success else f"Échec de {len(services_failed)} services",
                services_deployed=services_deployed,
                services_failed=services_failed,
                deployment_time=time.time() - start_time,
                logs=deployment_logs
            )
            
        except Exception as e:
            self.logger.error(f"Erreur lors du déploiement de {stack_name}: {e}")
            
            # Nettoyer en cas d'erreur
            if stack_name in self.active_deployments:
                self.active_deployments[stack_name]['status'] = DeploymentStatus.FAILED
            
            return DeploymentResult(
                success=False,
                status=DeploymentStatus.FAILED,
                message=f"Erreur de déploiement: {str(e)}",
                services_deployed=[],
                services_failed=[],
                deployment_time=time.time() - start_time,
                logs=deployment_logs + [f"Exception: {str(e)}"]
            )
    
    def stop_stack(self, stack_name: str) -> DeploymentResult:
        """
        Arrête une stack Docker Compose
        
        Args:
            stack_name: Nom de la stack à arrêter
            
        Returns:
            DeploymentResult: Résultat de l'arrêt
        """
        start_time = time.time()
        deployment_logs = []
        
        try:
            self.logger.info(f"Arrêt de la stack {stack_name}")
            deployment_logs.append(f"Début de l'arrêt de {stack_name}")
            
            stack_dir = self.work_dir / stack_name
            if not stack_dir.exists():
                return DeploymentResult(
                    success=False,
                    status=DeploymentStatus.FAILED,
                    message=f"Stack {stack_name} introuvable",
                    services_deployed=[],
                    services_failed=[],
                    deployment_time=time.time() - start_time,
                    logs=deployment_logs
                )
            
            # Exécuter docker-compose down
            result = self._run_compose_command(stack_dir, ["down", "--remove-orphans"])
            
            if result.returncode == 0:
                # Marquer comme arrêté
                if stack_name in self.active_deployments:
                    self.active_deployments[stack_name]['status'] = DeploymentStatus.STOPPED
                
                return DeploymentResult(
                    success=True,
                    status=DeploymentStatus.STOPPED,
                    message="Stack arrêtée avec succès",
                    services_deployed=[],
                    services_failed=[],
                    deployment_time=time.time() - start_time,
                    logs=deployment_logs + [result.stdout.decode()]
                )
            else:
                return DeploymentResult(
                    success=False,
                    status=DeploymentStatus.FAILED,
                    message="Échec de l'arrêt de la stack",
                    services_deployed=[],
                    services_failed=[],
                    deployment_time=time.time() - start_time,
                    logs=deployment_logs + [result.stderr.decode()]
                )
                
        except Exception as e:
            self.logger.error(f"Erreur lors de l'arrêt de {stack_name}: {e}")
            return DeploymentResult(
                success=False,
                status=DeploymentStatus.FAILED,
                message=f"Erreur d'arrêt: {str(e)}",
                services_deployed=[],
                services_failed=[],
                deployment_time=time.time() - start_time,
                logs=deployment_logs + [f"Exception: {str(e)}"]
            )
    
    def remove_stack(self, stack_name: str, remove_volumes: bool = False) -> bool:
        """
        Supprime complètement une stack
        
        Args:
            stack_name: Nom de la stack
            remove_volumes: Supprimer aussi les volumes
            
        Returns:
            bool: Succès de la suppression
        """
        try:
            # Arrêter d'abord la stack
            self.stop_stack(stack_name)
            
            # Supprimer les volumes si demandé
            if remove_volumes:
                stack_dir = self.work_dir / stack_name
                if stack_dir.exists():
                    self._run_compose_command(stack_dir, ["down", "-v"])
            
            # Supprimer le répertoire de travail
            stack_dir = self.work_dir / stack_name
            if stack_dir.exists():
                shutil.rmtree(stack_dir)
            
            # Supprimer de la liste des déploiements actifs
            if stack_name in self.active_deployments:
                del self.active_deployments[stack_name]
            
            self.logger.info(f"Stack {stack_name} supprimée")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la suppression de {stack_name}: {e}")
            return False
    
    def get_stack_status(self, stack_name: str) -> Dict[str, Any]:
        """
        Récupère le statut d'une stack
        
        Args:
            stack_name: Nom de la stack
            
        Returns:
            Dict: Informations sur le statut
        """
        try:
            stack_dir = self.work_dir / stack_name
            if not stack_dir.exists():
                return {
                    'name': stack_name,
                    'status': 'not_found',
                    'services': []
                }
            
            # Exécuter docker-compose ps
            result = self._run_compose_command(stack_dir, ["ps", "--format", "json"])
            
            if result.returncode == 0:
                # Parser le JSON de sortie
                try:
                    services_info = []
                    for line in result.stdout.decode().strip().split('\n'):
                        if line:
                            service_info = json.loads(line)
                            services_info.append(service_info)
                    
                    return {
                        'name': stack_name,
                        'status': self.active_deployments.get(stack_name, {}).get('status', 'unknown'),
                        'services': services_info,
                        'deployment_info': self.active_deployments.get(stack_name, {})
                    }
                except json.JSONDecodeError:
                    # Fallback pour les anciennes versions de docker-compose
                    return {
                        'name': stack_name,
                        'status': 'running',
                        'services': [],
                        'raw_output': result.stdout.decode()
                    }
            else:
                return {
                    'name': stack_name,
                    'status': 'error',
                    'error': result.stderr.decode()
                }
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération du statut de {stack_name}: {e}")
            return {
                'name': stack_name,
                'status': 'error',
                'error': str(e)
            }
    
    def list_stacks(self) -> List[Dict[str, Any]]:
        """
        Liste toutes les stacks déployées
        
        Returns:
            List: Liste des stacks avec leurs informations
        """
        stacks = []
        
        try:
            for stack_name in os.listdir(self.work_dir):
                stack_path = self.work_dir / stack_name
                if stack_path.is_dir():
                    status_info = self.get_stack_status(stack_name)
                    stacks.append(status_info)
        except Exception as e:
            self.logger.error(f"Erreur lors de la liste des stacks: {e}")
        
        return stacks
    
    def _prepare_deployment_files(self, stack_dir: Path, compose_content: str,
                                env_variables: Optional[Dict[str, str]] = None,
                                env_file_content: Optional[str] = None):
        """Prépare les fichiers nécessaires au déploiement"""
        
        # Écrire le fichier docker-compose.yml
        compose_file = stack_dir / "docker-compose.yml"
        with open(compose_file, 'w', encoding='utf-8') as f:
            f.write(compose_content)
        
        # Préparer le fichier .env
        env_file_path = stack_dir / ".env"
        
        if env_file_content:
            # Utiliser le contenu .env fourni
            with open(env_file_path, 'w', encoding='utf-8') as f:
                f.write(env_file_content)
        elif env_variables:
            # Créer un fichier .env à partir des variables
            self.env_manager.create_env_file(str(env_file_path), env_variables)
        else:
            # Créer un fichier .env minimal
            with open(env_file_path, 'w', encoding='utf-8') as f:
                f.write("# Variables d'environnement générées automatiquement\n")
                f.write(f"COMPOSE_PROJECT_NAME={stack_dir.name}\n")
    
    def _deploy_service_group(self, stack_name: str, stack_dir: Path, 
                            services: List[str]) -> Dict[str, Any]:
        """Déploie un groupe de services en parallèle"""
        
        deployed = []
        failed = []
        logs = []
        
        try:
            # Pour l'instant, on déploie tous les services d'un coup
            # On pourrait optimiser en déployant service par service
            
            self.logger.info(f"Déploiement du groupe de services: {services}")
            logs.append(f"Déploiement de {len(services)} services: {', '.join(services)}")
            
            # Exécuter docker-compose up pour ces services
            services_args = []
            for service in services:
                services_args.append(service)
            
            result = self._run_compose_command(
                stack_dir, 
                ["up", "-d", "--no-build"] + services_args
            )
            
            if result.returncode == 0:
                deployed.extend(services)
                logs.append(f"Services déployés avec succès: {', '.join(services)}")
            else:
                failed.extend(services)
                logs.append(f"Échec du déploiement: {result.stderr.decode()}")
                
        except Exception as e:
            failed.extend(services)
            logs.append(f"Exception lors du déploiement: {str(e)}")
        
        return {
            'deployed': deployed,
            'failed': failed,
            'logs': logs
        }
    
    def _run_compose_command(self, stack_dir: Path, command: List[str]) -> subprocess.CompletedProcess:
        """Exécute une commande docker-compose"""
        
        # Déterminer la commande docker-compose à utiliser
        compose_cmd = self._get_compose_command()
        
        full_command = compose_cmd + command
        
        self.logger.debug(f"Exécution: {' '.join(full_command)} dans {stack_dir}")
        
        return subprocess.run(
            full_command,
            cwd=stack_dir,
            capture_output=True,
            timeout=300  # 5 minutes de timeout
        )
    
    def _get_compose_command(self) -> List[str]:
        """Détermine la commande docker-compose à utiliser"""
        
        # Essayer docker compose (nouvelle syntaxe)
        try:
            result = subprocess.run(['docker', 'compose', 'version'], 
                                  capture_output=True, timeout=10)
            if result.returncode == 0:
                return ['docker', 'compose']
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Fallback vers docker-compose
        try:
            result = subprocess.run(['docker-compose', '--version'], 
                                  capture_output=True, timeout=10)
            if result.returncode == 0:
                return ['docker-compose']
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Si aucune commande ne fonctionne, utiliser docker compose par défaut
        self.logger.warning("Aucune commande docker-compose détectée, utilisation de 'docker compose'")
        return ['docker', 'compose']
