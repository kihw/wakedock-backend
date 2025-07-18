"""
Service pour la détection et gestion des stacks Docker
"""
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from docker.models.containers import Container
from docker.models.networks import Network

from wakedock.core.docker_manager import DockerManager
from wakedock.models.stack import (
    ContainerStackInfo, 
    StackDetectionRule, 
    StackInfo, 
    StackStatus, 
    StackSummary, 
    StackType
)


class StackDetectionService:
    """Service pour détecter et catégoriser les containers par stacks"""
    
    def __init__(self, docker_manager: DockerManager):
        self.docker_manager = docker_manager
        self.detection_rules = self._initialize_default_rules()
    
    def _initialize_default_rules(self) -> List[StackDetectionRule]:
        """Initialise les règles de détection par défaut"""
        return [
            # Règle pour Docker Compose
            StackDetectionRule(
                name="docker_compose",
                description="Détecte les stacks Docker Compose",
                label_patterns={"com.docker.compose.project": ".*"},
                stack_type=StackType.COMPOSE,
                group_by="label",
                group_key="com.docker.compose.project",
                priority=100
            ),
            
            # Règle pour Docker Swarm
            StackDetectionRule(
                name="docker_swarm",
                description="Détecte les services Docker Swarm",
                label_patterns={"com.docker.swarm.service.name": ".*"},
                stack_type=StackType.SWARM,
                group_by="label",
                group_key="com.docker.swarm.service.name",
                priority=90
            ),
            
            # Règle pour Kubernetes
            StackDetectionRule(
                name="kubernetes",
                description="Détecte les pods Kubernetes",
                label_patterns={"io.kubernetes.pod.name": ".*"},
                stack_type=StackType.KUBERNETES,
                group_by="label",
                group_key="io.kubernetes.pod.namespace",
                priority=80
            ),
            
            # Règle pour les patterns de noms
            StackDetectionRule(
                name="name_pattern",
                description="Groupe par préfixe de nom",
                name_patterns=[r"^([a-zA-Z0-9_-]+)_.*", r"^([a-zA-Z0-9_-]+)-.*"],
                stack_type=StackType.CUSTOM,
                group_by="name",
                group_key="name_prefix",
                priority=20
            ),
            
            # Règle pour les réseaux partagés
            StackDetectionRule(
                name="shared_network",
                description="Groupe par réseau partagé",
                stack_type=StackType.CUSTOM,
                group_by="network",
                group_key="network_name",
                priority=10
            )
        ]
    
    def detect_stacks(self, containers: Optional[List[Container]] = None) -> List[StackInfo]:
        """Détecte toutes les stacks à partir des containers"""
        if containers is None:
            containers = self.docker_manager.list_containers(all=True)
        
        # Grouper les containers par stack
        stack_groups = self._group_containers_by_stack(containers)
        
        # Créer les objets StackInfo
        stacks = []
        for stack_id, (stack_name, stack_type, container_list) in stack_groups.items():
            stack_info = self._create_stack_info(
                stack_id=stack_id,
                stack_name=stack_name,
                stack_type=stack_type,
                containers=container_list
            )
            stacks.append(stack_info)
        
        return sorted(stacks, key=lambda s: s.name)
    
    def _group_containers_by_stack(self, containers: List[Container]) -> Dict[str, Tuple[str, StackType, List[Container]]]:
        """Groupe les containers par stack selon les règles de détection"""
        stack_groups = defaultdict(list)
        container_assignments = {}  # container_id -> (stack_id, rule_priority)
        
        # Trier les règles par priorité (plus élevée en premier)
        sorted_rules = sorted(self.detection_rules, key=lambda r: r.priority, reverse=True)
        
        for container in containers:
            best_assignment = None
            best_priority = -1
            
            for rule in sorted_rules:
                if not rule.enabled:
                    continue
                
                assignment = self._apply_detection_rule(container, rule)
                if assignment and rule.priority > best_priority:
                    best_assignment = assignment
                    best_priority = rule.priority
            
            if best_assignment:
                stack_id, stack_name, stack_type = best_assignment
                container_assignments[container.id] = (stack_id, best_priority)
                stack_groups[stack_id].append((stack_name, stack_type, container))
        
        # Réorganiser pour le format de retour
        result = {}
        for stack_id, container_data in stack_groups.items():
            if container_data:
                # Utiliser les données du premier container pour le nom et type
                stack_name = container_data[0][0]
                stack_type = container_data[0][1]
                containers_list = [data[2] for data in container_data]
                result[stack_id] = (stack_name, stack_type, containers_list)
        
        return result
    
    def _apply_detection_rule(self, container: Container, rule: StackDetectionRule) -> Optional[Tuple[str, str, StackType]]:
        """Applique une règle de détection à un container"""
        labels = container.labels or {}
        
        # Vérifier les patterns de labels
        if rule.label_patterns:
            for label_key, pattern in rule.label_patterns.items():
                if label_key in labels:
                    if re.match(pattern, labels[label_key]):
                        if rule.group_by == "label":
                            stack_value = labels.get(rule.group_key, "unknown")
                            return f"{rule.stack_type.value}_{stack_value}", stack_value, rule.stack_type
        
        # Vérifier les patterns de noms
        if rule.name_patterns:
            container_name = container.name.lstrip('/')
            for pattern in rule.name_patterns:
                match = re.match(pattern, container_name)
                if match:
                    if rule.group_by == "name":
                        stack_name = match.group(1)
                        return f"{rule.stack_type.value}_{stack_name}", stack_name, rule.stack_type
        
        # Vérifier les patterns d'images
        if rule.image_patterns:
            image_name = container.image.tags[0] if container.image.tags else container.image.id
            for pattern in rule.image_patterns:
                if re.match(pattern, image_name):
                    stack_name = re.match(pattern, image_name).group(1) if "(" in pattern else "custom"
                    return f"{rule.stack_type.value}_{stack_name}", stack_name, rule.stack_type
        
        # Vérifier les réseaux partagés
        if rule.group_by == "network":
            networks = list(container.attrs.get('NetworkSettings', {}).get('Networks', {}).keys())
            if networks:
                # Utiliser le premier réseau non-bridge
                network_name = next((n for n in networks if n != 'bridge'), networks[0])
                if network_name and network_name != 'bridge':
                    return f"{rule.stack_type.value}_{network_name}", network_name, rule.stack_type
        
        return None
    
    def _create_stack_info(self, stack_id: str, stack_name: str, stack_type: StackType, containers: List[Container]) -> StackInfo:
        """Crée un objet StackInfo à partir d'un groupe de containers"""
        now = datetime.now()
        
        # Analyser les containers
        container_infos = []
        status_counts = defaultdict(int)
        all_labels = {}
        all_networks = set()
        all_volumes = set()
        earliest_created = now
        
        for container in containers:
            # Informations du container
            container_info = ContainerStackInfo(
                container_id=container.id,
                container_name=container.name.lstrip('/'),
                image=container.image.tags[0] if container.image.tags else container.image.id,
                status=container.status,
                ports=container.ports,
                environment=dict(
                    env.split('=', 1) for env in container.attrs['Config']['Env'] 
                    if '=' in env
                ) if container.attrs['Config']['Env'] else {},
                labels=container.labels,
                service_name=container.labels.get('com.docker.compose.service') if container.labels else None
            )
            container_infos.append(container_info)
            
            # Compter les status
            status_counts[container.status] += 1
            
            # Collecter les métadonnées
            if container.labels:
                all_labels.update(container.labels)
            
            # Collecter les réseaux
            networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
            all_networks.update(networks.keys())
            
            # Collecter les volumes
            mounts = container.attrs.get('Mounts', [])
            for mount in mounts:
                if mount.get('Type') == 'volume':
                    all_volumes.add(mount.get('Name', ''))
            
            # Trouver la date de création la plus ancienne
            created_str = container.attrs.get('Created', '')
            if created_str:
                try:
                    created = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                    if created < earliest_created:
                        earliest_created = created
                except ValueError:
                    pass
        
        # Déterminer le status global de la stack
        stack_status = self._determine_stack_status(status_counts)
        
        # Extraire les informations spécifiques au type de stack
        project_name = None
        compose_file = None
        working_dir = None
        
        if stack_type == StackType.COMPOSE:
            project_name = all_labels.get('com.docker.compose.project')
            compose_file = all_labels.get('com.docker.compose.project.config_files')
            working_dir = all_labels.get('com.docker.compose.project.working_dir')
        
        return StackInfo(
            id=stack_id,
            name=stack_name,
            type=stack_type,
            status=stack_status,
            created=earliest_created,
            updated=now,
            containers=container_infos,
            project_name=project_name,
            compose_file=compose_file,
            working_dir=working_dir,
            labels=all_labels,
            total_containers=len(containers),
            running_containers=status_counts.get('running', 0),
            stopped_containers=status_counts.get('exited', 0) + status_counts.get('stopped', 0),
            error_containers=status_counts.get('error', 0),
            networks=list(all_networks) if all_networks else None,
            volumes=list(all_volumes) if all_volumes else None
        )
    
    def _determine_stack_status(self, status_counts: Dict[str, int]) -> StackStatus:
        """Détermine le status global d'une stack basé sur les status des containers"""
        if status_counts.get('running', 0) > 0:
            if status_counts.get('exited', 0) > 0 or status_counts.get('stopped', 0) > 0:
                return StackStatus.ERROR  # Certains containers sont arrêtés
            return StackStatus.RUNNING
        elif status_counts.get('exited', 0) > 0 or status_counts.get('stopped', 0) > 0:
            return StackStatus.STOPPED
        elif status_counts.get('restarting', 0) > 0:
            return StackStatus.STARTING
        else:
            return StackStatus.UNKNOWN
    
    def get_stack_by_id(self, stack_id: str) -> Optional[StackInfo]:
        """Récupère une stack spécifique par son ID"""
        stacks = self.detect_stacks()
        return next((stack for stack in stacks if stack.id == stack_id), None)
    
    def get_stacks_summary(self) -> List[StackSummary]:
        """Récupère un résumé de toutes les stacks"""
        stacks = self.detect_stacks()
        return [
            StackSummary(
                id=stack.id,
                name=stack.name,
                type=stack.type,
                status=stack.status,
                total_containers=stack.total_containers,
                running_containers=stack.running_containers,
                created=stack.created,
                updated=stack.updated,
                project_name=stack.project_name,
                labels=stack.labels
            )
            for stack in stacks
        ]
    
    def get_containers_by_stack(self, stack_id: str) -> List[ContainerStackInfo]:
        """Récupère tous les containers d'une stack spécifique"""
        stack = self.get_stack_by_id(stack_id)
        return stack.containers if stack else []
    
    def add_detection_rule(self, rule: StackDetectionRule):
        """Ajoute une nouvelle règle de détection"""
        self.detection_rules.append(rule)
        # Trier par priorité
        self.detection_rules.sort(key=lambda r: r.priority, reverse=True)
    
    def remove_detection_rule(self, rule_name: str):
        """Supprime une règle de détection"""
        self.detection_rules = [r for r in self.detection_rules if r.name != rule_name]
    
    def get_detection_rules(self) -> List[StackDetectionRule]:
        """Récupère toutes les règles de détection"""
        return self.detection_rules.copy()
