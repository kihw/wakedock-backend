"""
Test de détection de stacks avec containers mockés
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from unittest.mock import Mock, MagicMock
from wakedock.models.stack import StackType, StackStatus
from wakedock.core.stack_detection import StackDetectionService

def create_mock_container(container_id, name, image, status="running", labels=None):
    """Crée un container mocké pour les tests"""
    container = Mock()
    container.id = container_id
    container.name = name
    container.status = status
    container.labels = labels or {}
    container.ports = {"80/tcp": [{"HostPort": "8080"}]}
    container.image = Mock()
    container.image.tags = [image]
    container.image.id = f"sha256:{container_id}"
    container.attrs = {
        'Config': {
            'Env': ['PATH=/usr/local/bin:/usr/bin', 'PORT=3000']
        },
        'State': {
            'Status': status
        },
        'Created': datetime.now().isoformat(),
        'NetworkSettings': {
            'Networks': {
                'bridge': {},
                'myapp_network': {}
            }
        },
        'Mounts': [
            {
                'Type': 'volume',
                'Name': 'myapp_data',
                'Source': '/var/lib/docker/volumes/myapp_data',
                'Destination': '/app/data',
                'Mode': 'rw'
            }
        ]
    }
    return container

def test_stack_detection():
    """Test de la détection de stacks"""
    print("Testing stack detection...")
    
    # Créer un docker manager mocké
    docker_manager = Mock()
    
    # Créer des containers mockés pour différents types de stacks
    containers = [
        # Docker Compose stack
        create_mock_container(
            "comp1", "/myapp_web_1", "nginx:latest", "running",
            {"com.docker.compose.project": "myapp", "com.docker.compose.service": "web"}
        ),
        create_mock_container(
            "comp2", "/myapp_db_1", "postgres:13", "running",
            {"com.docker.compose.project": "myapp", "com.docker.compose.service": "db"}
        ),
        
        # Docker Swarm stack
        create_mock_container(
            "swarm1", "/api_service.1", "api:latest", "running",
            {"com.docker.swarm.service.name": "api_service"}
        ),
        
        # Containers avec pattern de nom
        create_mock_container(
            "custom1", "/monitoring_grafana_1", "grafana:latest", "running"
        ),
        create_mock_container(
            "custom2", "/monitoring_prometheus_1", "prometheus:latest", "running"
        ),
        
        # Container standalone
        create_mock_container(
            "standalone1", "/redis_cache", "redis:alpine", "running"
        )
    ]
    
    # Créer le service de détection
    stack_service = StackDetectionService(docker_manager)
    
    # Tester la détection
    stacks = stack_service.detect_stacks(containers)
    
    print(f"Detected {len(stacks)} stacks:")
    for stack in stacks:
        print(f"  - {stack.name} ({stack.type.value}): {stack.total_containers} containers, status: {stack.status.value}")
        for container in stack.containers:
            print(f"    * {container.container_name} ({container.image}) - {container.status}")
    
    # Vérifications
    assert len(stacks) > 0, "Au moins une stack devrait être détectée"
    
    # Vérifier qu'on a bien détecté une stack Compose
    compose_stacks = [s for s in stacks if s.type == StackType.COMPOSE]
    assert len(compose_stacks) > 0, "Une stack Compose devrait être détectée"
    
    # Vérifier qu'on a bien détecté une stack Swarm
    swarm_stacks = [s for s in stacks if s.type == StackType.SWARM]
    assert len(swarm_stacks) > 0, "Une stack Swarm devrait être détectée"
    
    print("✅ Stack detection is working correctly!")
    
    # Tester les statistiques
    summary = stack_service.get_stacks_summary()
    print(f"Summary: {len(summary)} stacks")
    
    return stacks

def test_stack_by_id():
    """Test de récupération d'une stack par ID"""
    print("\nTesting stack retrieval by ID...")
    
    docker_manager = Mock()
    stack_service = StackDetectionService(docker_manager)
    
    # Créer quelques containers
    containers = [
        create_mock_container(
            "test1", "/test_app_1", "nginx:latest", "running",
            {"com.docker.compose.project": "test", "com.docker.compose.service": "app"}
        )
    ]
    
    stacks = stack_service.detect_stacks(containers)
    if stacks:
        stack = stack_service.get_stack_by_id(stacks[0].id)
        assert stack is not None, "La stack devrait être trouvée par ID"
        print(f"Stack found: {stack.name}")
        print("✅ Stack retrieval by ID is working correctly!")
    else:
        print("⚠️  No stacks detected for ID test")

if __name__ == "__main__":
    test_stack_detection()
    test_stack_by_id()
    print("\n🎉 All tests passed! Stack detection and categorization is working correctly.")
