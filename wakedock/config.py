"""
Configuration management for WakeDock
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseSettings, Field
from pydantic_settings import BaseSettings as PydanticBaseSettings
import yaml


class LoggingSettings(BaseSettings):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "/app/logs/wakedock.log"
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5


class WakeDockSettings(BaseSettings):
    domain: str = "localhost"
    admin_password: str = "admin123"
    secret_key: str = "change-this-secret-key-in-production"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    data_path: str = "/app/data"


class CaddySettings(BaseSettings):
    api_endpoint: str = "http://caddy:2019"
    config_path: str = "/etc/caddy/Caddyfile"
    admin_api_key: str = ""


class DatabaseSettings(BaseSettings):
    url: str = "sqlite:///./data/wakedock.db"


class MonitoringSettings(BaseSettings):
    enabled: bool = True
    metrics_retention: str = "7d"
    collect_interval: int = 30
    endpoints: List[str] = ["/health", "/metrics"]


class LoadingPageSettings(BaseSettings):
    title: str = "Starting {service_name}..."
    message: str = "Please wait while we wake up your service"
    theme: str = "dark"
    custom_css: Optional[str] = None
    estimated_time: int = 30


class AutoShutdownSettings(BaseSettings):
    inactive_minutes: int = 30
    cpu_threshold: float = 5.0
    memory_threshold: int = 100  # MB
    check_interval: int = 300  # seconds
    grace_period: int = 60  # seconds


class HealthCheckSettings(BaseSettings):
    enabled: bool = True
    endpoint: str = "/health"
    timeout: int = 30
    retries: int = 3
    interval: int = 10


class ServiceSettings(BaseSettings):
    name: str
    subdomain: str
    docker_image: Optional[str] = None
    docker_compose: Optional[str] = None
    ports: List[str] = []
    environment: dict = {}
    auto_shutdown: AutoShutdownSettings = AutoShutdownSettings()
    loading_page: LoadingPageSettings = LoadingPageSettings()
    health_check: HealthCheckSettings = HealthCheckSettings()
    startup_script: Optional[str] = None


class Settings(PydanticBaseSettings):
    wakedock: WakeDockSettings = WakeDockSettings()
    caddy: CaddySettings = CaddySettings()
    database: DatabaseSettings = DatabaseSettings()
    monitoring: MonitoringSettings = MonitoringSettings()
    logging: LoggingSettings = LoggingSettings()
    services: List[ServiceSettings] = []

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"


def load_config_from_yaml(config_path: str) -> dict:
    """Load configuration from YAML file"""
    if not Path(config_path).exists():
        return {}
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f) or {}


def get_settings() -> Settings:
    """Get application settings"""
    config_path = os.getenv("WAKEDOCK_CONFIG_PATH", "config/config.yml")
    
    # Load from YAML file
    yaml_config = load_config_from_yaml(config_path)
    
    # Create settings instance
    settings = Settings(**yaml_config)
    
    return settings
