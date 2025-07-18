"""
Test simple pour valider les modèles de stacks
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from wakedock.models.stack import (
    StackType, 
    StackStatus, 
    StackInfo, 
    ContainerStackInfo,
    StackSummary
)

def test_stack_models():
    """Test des modèles de stacks"""
    print("Testing stack models...")
    
    # Test ContainerStackInfo
    container_info = ContainerStackInfo(
        container_id="test-container-id",
        container_name="test-container",
        image="nginx:latest",
        status="running",
        service_name="web"
    )
    
    print(f"Container info: {container_info.container_name} - {container_info.status}")
    
    # Test StackInfo
    stack_info = StackInfo(
        id="test-stack-id",
        name="test-stack",
        type=StackType.COMPOSE,
        status=StackStatus.RUNNING,
        created=datetime.now(),
        updated=datetime.now(),
        containers=[container_info],
        total_containers=1,
        running_containers=1,
        stopped_containers=0,
        error_containers=0
    )
    
    print(f"Stack info: {stack_info.name} - {stack_info.type.value} - {stack_info.status.value}")
    
    # Test StackSummary
    stack_summary = StackSummary(
        id=stack_info.id,
        name=stack_info.name,
        type=stack_info.type,
        status=stack_info.status,
        total_containers=stack_info.total_containers,
        running_containers=stack_info.running_containers,
        created=stack_info.created,
        updated=stack_info.updated
    )
    
    print(f"Stack summary: {stack_summary.name} - {stack_summary.total_containers} containers")
    print("✅ All stack models are working correctly!")

if __name__ == "__main__":
    test_stack_models()
