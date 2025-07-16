"""
Gestionnaire des dépendances entre services Docker Compose
"""
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, deque
from wakedock.core.compose_parser import ComposeFile, ComposeService
import logging

logger = logging.getLogger(__name__)

class DependencyType(Enum):
    """Types de dépendances entre services"""
    DEPENDS_ON = "depends_on"
    NETWORK = "network"
    VOLUME = "volume"
    LINK = "link"
    EXTERNAL_LINK = "external_link"

@dataclass
class ServiceDependency:
    """Représente une dépendance entre services"""
    source: str  # Service qui dépend
    target: str  # Service dont dépend source
    dependency_type: DependencyType
    is_required: bool = True
    condition: Optional[str] = None  # service_healthy, service_started, etc.

class DependencyGraph:
    """Graphe des dépendances entre services"""
    
    def __init__(self):
        self.nodes: Set[str] = set()
        self.edges: Dict[str, List[Tuple[str, Dict[str, Any]]]] = defaultdict(list)
        self.dependencies: List[ServiceDependency] = []
    
    def add_service(self, service_name: str):
        """Ajoute un service au graphe"""
        self.nodes.add(service_name)
    
    def add_dependency(self, dependency: ServiceDependency):
        """Ajoute une dépendance au graphe"""
        self.dependencies.append(dependency)
        edge_data = {
            'dependency_type': dependency.dependency_type.value,
            'condition': dependency.condition,
            'is_required': dependency.is_required
        }
        self.edges[dependency.source].append((dependency.target, edge_data))
    
    def get_dependencies(self, service_name: str) -> List[str]:
        """Récupère les dépendances directes d'un service"""
        return [target for target, _ in self.edges.get(service_name, [])]
    
    def get_dependents(self, service_name: str) -> List[str]:
        """Récupère les services qui dépendent de ce service"""
        dependents = []
        for source, targets in self.edges.items():
            for target, _ in targets:
                if target == service_name:
                    dependents.append(source)
        return dependents
    
    def get_startup_order(self) -> List[str]:
        """Calcule l'ordre de démarrage des services"""
        try:
            return self._topological_sort()
        except DependencyError as e:
            raise e
    
    def get_shutdown_order(self) -> List[str]:
        """Calcule l'ordre d'arrêt des services (inverse du démarrage)"""
        return list(reversed(self.get_startup_order()))
    
    def has_circular_dependencies(self) -> bool:
        """Vérifie s'il y a des dépendances circulaires"""
        try:
            self._topological_sort()
            return False
        except DependencyError:
            return True
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """Trouve toutes les dépendances circulaires"""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]):
            if node in rec_stack:
                # Cycle trouvé
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return
            
            if node in visited:
                return
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for target, _ in self.edges.get(node, []):
                dfs(target, path.copy())
            
            rec_stack.remove(node)
        
        for node in self.nodes:
            if node not in visited:
                dfs(node, [])
        
        return cycles
    
    def get_isolated_services(self) -> List[str]:
        """Trouve les services sans dépendances"""
        isolated = []
        for service in self.nodes:
            has_incoming = any(service in [t for t, _ in targets] 
                             for targets in self.edges.values())
            has_outgoing = bool(self.edges.get(service))
            
            if not has_incoming and not has_outgoing:
                isolated.append(service)
        return isolated
    
    def get_critical_services(self) -> List[str]:
        """Trouve les services critiques (beaucoup de dépendants)"""
        dependents_count = defaultdict(int)
        
        for targets in self.edges.values():
            for target, _ in targets:
                dependents_count[target] += 1
        
        critical = []
        for service, count in dependents_count.items():
            if count >= 3:  # Seuil configurable
                critical.append(service)
        
        return critical
    
    def _topological_sort(self) -> List[str]:
        """Implémentation du tri topologique (algorithme de Kahn)"""
        # Calculer les degrés d'entrée
        in_degree = {node: 0 for node in self.nodes}
        
        for targets in self.edges.values():
            for target, _ in targets:
                in_degree[target] += 1
        
        # Queue des nœuds sans dépendances
        queue = deque([node for node in self.nodes if in_degree[node] == 0])
        result = []
        
        while queue:
            node = queue.popleft()
            result.append(node)
            
            # Supprimer les arêtes sortantes
            for target, _ in self.edges.get(node, []):
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)
        
        # Vérifier s'il y a des cycles
        if len(result) != len(self.nodes):
            raise DependencyError("Dépendances circulaires détectées")
        
        return result

class DependencyError(Exception):
    """Exception pour les erreurs de dépendances"""
    pass

class DependencyManager:
    """Gestionnaire des dépendances de services"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_dependencies(self, compose: ComposeFile) -> DependencyGraph:
        """
        Analyse les dépendances d'un fichier Docker Compose
        
        Args:
            compose: Configuration Docker Compose
            
        Returns:
            DependencyGraph: Graphe des dépendances
        """
        graph = DependencyGraph()
        
        # Ajouter tous les services
        for service_name in compose.services:
            graph.add_service(service_name)
        
        # Analyser les dépendances de chaque service
        for service_name, service in compose.services.items():
            self._analyze_service_dependencies(service_name, service, graph, compose)
        
        return graph
    
    def _analyze_service_dependencies(self, service_name: str, service: ComposeService, 
                                    graph: DependencyGraph, compose: ComposeFile):
        """Analyse les dépendances d'un service spécifique"""
        
        # Dépendances explicites (depends_on)
        for dep_service in service.depends_on:
            dependency = ServiceDependency(
                source=service_name,
                target=dep_service,
                dependency_type=DependencyType.DEPENDS_ON,
                is_required=True
            )
            graph.add_dependency(dependency)
        
        # Dépendances via volumes partagés
        self._analyze_volume_dependencies(service_name, service, graph, compose)
        
        # Dépendances via réseaux
        self._analyze_network_dependencies(service_name, service, graph, compose)
    
    def _analyze_volume_dependencies(self, service_name: str, service: ComposeService,
                                   graph: DependencyGraph, compose: ComposeFile):
        """Analyse les dépendances via volumes partagés"""
        service_volumes = set()
        
        # Collecter les volumes de ce service
        for volume in service.volumes:
            if ':' in volume:
                parts = volume.split(':')
                volume_name = parts[0]
                # Si c'est un volume nommé (pas un chemin absolu)
                if not volume_name.startswith('/'):
                    service_volumes.add(volume_name)
        
        # Chercher d'autres services utilisant les mêmes volumes
        for other_service_name, other_service in compose.services.items():
            if other_service_name == service_name:
                continue
            
            for volume in other_service.volumes:
                if ':' in volume:
                    parts = volume.split(':')
                    volume_name = parts[0]
                    if not volume_name.startswith('/') and volume_name in service_volumes:
                        # Dépendance via volume partagé
                        dependency = ServiceDependency(
                            source=service_name,
                            target=other_service_name,
                            dependency_type=DependencyType.VOLUME,
                            is_required=False
                        )
                        graph.add_dependency(dependency)
    
    def _analyze_network_dependencies(self, service_name: str, service: ComposeService,
                                    graph: DependencyGraph, compose: ComposeFile):
        """Analyse les dépendances via réseaux partagés"""
        service_networks = set(service.networks) if service.networks else set()
        
        # Si pas de réseau spécifié, utilise le réseau par défaut
        if not service_networks:
            service_networks.add('default')
        
        # Chercher d'autres services sur les mêmes réseaux
        for other_service_name, other_service in compose.services.items():
            if other_service_name == service_name:
                continue
            
            other_networks = set(other_service.networks) if other_service.networks else {'default'}
            
            # Si les services partagent au moins un réseau
            if service_networks & other_networks:
                dependency = ServiceDependency(
                    source=service_name,
                    target=other_service_name,
                    dependency_type=DependencyType.NETWORK,
                    is_required=False
                )
                graph.add_dependency(dependency)
    
    def validate_dependencies(self, graph: DependencyGraph) -> Tuple[bool, List[str]]:
        """
        Valide les dépendances d'un graphe
        
        Returns:
            Tuple (is_valid, errors)
        """
        errors = []
        
        # Vérifier les cycles
        if graph.has_circular_dependencies():
            cycles = graph.find_circular_dependencies()
            for cycle in cycles:
                cycle_str = " -> ".join(cycle + [cycle[0]])
                errors.append(f"Dépendance circulaire détectée: {cycle_str}")
        
        # Vérifier les services orphelins critiques
        isolated = graph.get_isolated_services()
        if len(isolated) > len(graph.graph.nodes()) * 0.5:  # Plus de 50% isolés
            errors.append("Trop de services isolés, vérifiez les dépendances")
        
        # Vérifier les dépendances vers des services inexistants
        for dependency in graph.dependencies:
            if dependency.target not in graph.nodes:
                errors.append(f"Service {dependency.source} dépend de {dependency.target} qui n'existe pas")
        
        return len(errors) == 0, errors
    
    def optimize_startup_order(self, graph: DependencyGraph) -> List[List[str]]:
        """
        Optimise l'ordre de démarrage en groupes parallèles
        
        Returns:
            Liste de groupes de services pouvant démarrer en parallèle
        """
        try:
            # Grouper par niveaux topologiques
            levels = []
            remaining_nodes = set(graph.nodes)
            remaining_edges = dict(graph.edges)
            
            while remaining_nodes:
                # Calculer les degrés d'entrée pour les nœuds restants
                in_degree = {node: 0 for node in remaining_nodes}
                
                for source, targets in remaining_edges.items():
                    if source in remaining_nodes:
                        for target, _ in targets:
                            if target in remaining_nodes:
                                in_degree[target] += 1
                
                # Trouver les nœuds sans dépendances
                current_level = [node for node in remaining_nodes 
                               if in_degree[node] == 0]
                
                if not current_level:
                    # Il y a un cycle
                    break
                
                levels.append(current_level)
                
                # Supprimer ces nœuds
                for node in current_level:
                    remaining_nodes.remove(node)
                    if node in remaining_edges:
                        del remaining_edges[node]
            
            return levels
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'optimisation: {e}")
            # Fallback: ordre séquentiel
            return [[service] for service in graph.get_startup_order()]
    
    def get_dependency_report(self, graph: DependencyGraph) -> Dict[str, Any]:
        """
        Génère un rapport détaillé des dépendances
        
        Returns:
            Rapport structuré des dépendances
        """
        report = {
            'services_count': len(graph.nodes),
            'dependencies_count': len(graph.dependencies),
            'has_cycles': graph.has_circular_dependencies(),
            'cycles': graph.find_circular_dependencies(),
            'isolated_services': graph.get_isolated_services(),
            'critical_services': graph.get_critical_services(),
            'startup_order': graph.get_startup_order(),
            'shutdown_order': graph.get_shutdown_order(),
            'parallel_groups': self.optimize_startup_order(graph),
            'dependency_types': {},
            'service_details': {}
        }
        
        # Compter par type de dépendance
        for dep in graph.dependencies:
            dep_type = dep.dependency_type.value
            if dep_type not in report['dependency_types']:
                report['dependency_types'][dep_type] = 0
            report['dependency_types'][dep_type] += 1
        
        # Détails par service
        for service in graph.nodes:
            dependencies = graph.get_dependencies(service)
            dependents = graph.get_dependents(service)
            
            report['service_details'][service] = {
                'dependencies': dependencies,
                'dependents': dependents,
                'dependency_count': len(dependencies),
                'dependent_count': len(dependents),
                'is_isolated': service in report['isolated_services'],
                'is_critical': service in report['critical_services']
            }
        
        return report
    
    def suggest_optimizations(self, graph: DependencyGraph) -> List[str]:
        """
        Suggère des optimisations pour les dépendances
        
        Returns:
            Liste de suggestions d'optimisation
        """
        suggestions = []
        
        # Services critiques
        critical = graph.get_critical_services()
        if critical:
            suggestions.append(
                f"Services critiques détectés ({', '.join(critical)}). "
                "Considérez la haute disponibilité et les health checks."
            )
        
        # Services isolés
        isolated = graph.get_isolated_services()
        if isolated:
            suggestions.append(
                f"Services isolés ({', '.join(isolated)}). "
                "Vérifiez s'ils ont besoin de dépendances explicites."
            )
        
        # Cycles
        if graph.has_circular_dependencies():
            cycles = graph.find_circular_dependencies()
            suggestions.append(
                f"Dépendances circulaires détectées. "
                f"Refactorisez pour éliminer les cycles: {cycles}"
            )
        
        # Optimisation du parallélisme
        parallel_groups = self.optimize_startup_order(graph)
        max_parallel = max(len(group) for group in parallel_groups) if parallel_groups else 0
        total_services = len(graph.nodes)
        
        if max_parallel < total_services * 0.3:  # Moins de 30% en parallèle
            suggestions.append(
                "Faible parallélisme détecté. "
                "Considérez réduire les dépendances pour améliorer les performances de démarrage."
            )
        
        return suggestions
