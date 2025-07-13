"""Docker fixtures and test containers for WakeDock integration tests."""

import pytest
import docker
import time
from typing import Generator, Dict, Any
from docker.models.containers import Container


@pytest.fixture(scope="session")
def docker_client():
    """Create a Docker client for tests."""
    try:
        client = docker.from_env()
        # Test connection
        client.ping()
        return client
    except Exception as e:
        pytest.skip(f"Docker not available: {e}")


@pytest.fixture
def nginx_container(docker_client) -> Generator[Container, None, None]:
    """Create a test nginx container."""
    container = None
    try:
        container = docker_client.containers.run(
            "nginx:alpine",
            detach=True,
            ports={"80/tcp": None},  # Random port
            name="wakedock-test-nginx",
            remove=True
        )
        
        # Wait for container to be ready
        time.sleep(2)
        container.reload()
        
        yield container
        
    except Exception as e:
        pytest.fail(f"Failed to create nginx container: {e}")
    finally:
        if container:
            try:
                container.stop()
            except Exception:
                pass


@pytest.fixture
def redis_container(docker_client) -> Generator[Container, None, None]:
    """Create a test Redis container."""
    container = None
    try:
        container = docker_client.containers.run(
            "redis:alpine",
            detach=True,
            ports={"6379/tcp": None},
            name="wakedock-test-redis",
            remove=True
        )
        
        # Wait for Redis to be ready
        time.sleep(3)
        container.reload()
        
        yield container
        
    except Exception as e:
        pytest.fail(f"Failed to create Redis container: {e}")
    finally:
        if container:
            try:
                container.stop()
            except Exception:
                pass


@pytest.fixture
def postgres_container(docker_client) -> Generator[Container, None, None]:
    """Create a test PostgreSQL container."""
    container = None
    try:
        container = docker_client.containers.run(
            "postgres:alpine",
            detach=True,
            ports={"5432/tcp": None},
            environment={
                "POSTGRES_DB": "testdb",
                "POSTGRES_USER": "testuser", 
                "POSTGRES_PASSWORD": "testpass"
            },
            name="wakedock-test-postgres",
            remove=True
        )
        
        # Wait for PostgreSQL to be ready
        time.sleep(5)
        container.reload()
        
        yield container
        
    except Exception as e:
        pytest.fail(f"Failed to create PostgreSQL container: {e}")
    finally:
        if container:
            try:
                container.stop()
            except Exception:
                pass


@pytest.fixture
def sample_docker_services(docker_client) -> Generator[list[Container], None, None]:
    """Create multiple test containers for service management tests."""
    containers = []
    try:
        # Create multiple test services
        for i in range(3):
            container = docker_client.containers.run(
                "nginx:alpine",
                detach=True,
                ports={"80/tcp": None},
                name=f"wakedock-test-service-{i}",
                labels={"wakedock.managed": "true", "wakedock.test": "true"},
                remove=True
            )
            containers.append(container)
        
        # Wait for all containers to be ready
        time.sleep(3)
        for container in containers:
            container.reload()
        
        yield containers
        
    except Exception as e:
        pytest.fail(f"Failed to create test services: {e}")
    finally:
        for container in containers:
            try:
                container.stop()
            except Exception:
                pass


def get_container_port(container: Container, internal_port: int) -> int:
    """Get the external port mapping for a container port."""
    container.reload()
    port_info = container.attrs["NetworkSettings"]["Ports"].get(f"{internal_port}/tcp")
    if port_info and len(port_info) > 0:
        return int(port_info[0]["HostPort"])
    raise ValueError(f"Port {internal_port} not mapped")


def wait_for_container_health(container: Container, timeout: int = 30) -> bool:
    """Wait for a container to become healthy."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        container.reload()
        status = container.status
        if status == "running":
            return True
        elif status in ["exited", "dead"]:
            return False
        time.sleep(1)
    return False


@pytest.fixture
def container_utilities():
    """Provide utility functions for container management in tests."""
    return {
        "get_port": get_container_port,
        "wait_healthy": wait_for_container_health
    }
