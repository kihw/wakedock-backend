"""
Modèles de base de données pour la gestion Docker Swarm
"""
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship
from wakedock.database.database import Base


class SwarmCluster(Base):
    """
    Modèle pour les clusters Docker Swarm
    """
    __tablename__ = "swarm_clusters"
    
    id = Column(Integer, primary_key=True, index=True)
    cluster_id = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="active")  # active, inactive, error
    
    # Configuration du cluster
    manager_token = Column(Text, nullable=True)  # Token pour rejoindre comme manager
    worker_token = Column(Text, nullable=True)   # Token pour rejoindre comme worker
    advertise_addr = Column(String(255), nullable=True)
    listen_addr = Column(String(255), nullable=True)
    
    # Métadonnées
    labels = Column(JSON, nullable=False, default=dict)
    config = Column(JSON, nullable=False, default=dict)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relations
    creator = relationship("User", back_populates="swarm_clusters")
    nodes = relationship("SwarmNode", back_populates="cluster", cascade="all, delete-orphan")
    services = relationship("SwarmService", back_populates="cluster", cascade="all, delete-orphan")
    networks = relationship("SwarmNetwork", back_populates="cluster", cascade="all, delete-orphan")
    secrets = relationship("SwarmSecret", back_populates="cluster", cascade="all, delete-orphan")
    configs = relationship("SwarmConfig", back_populates="cluster", cascade="all, delete-orphan")
    stacks = relationship("SwarmStack", back_populates="cluster", cascade="all, delete-orphan")
    load_balancers = relationship("SwarmLoadBalancer", back_populates="cluster", cascade="all, delete-orphan")


class SwarmNode(Base):
    """
    Modèle pour les nœuds d'un cluster Swarm
    """
    __tablename__ = "swarm_nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String(255), unique=True, index=True, nullable=False)
    cluster_id = Column(String(255), ForeignKey("swarm_clusters.cluster_id"), nullable=False)
    
    # Informations du nœud
    hostname = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # manager, worker
    status = Column(String(20), nullable=False)  # ready, down, unknown
    availability = Column(String(20), nullable=False)  # active, pause, drain
    is_leader = Column(Boolean, default=False, nullable=False)
    
    # Spécifications hardware
    cpu_cores = Column(Integer, nullable=False)
    memory_bytes = Column(Integer, nullable=False)
    
    # Configuration
    labels = Column(JSON, nullable=False, default=dict)
    engine_version = Column(String(100), nullable=True)
    platform_os = Column(String(50), nullable=True)
    platform_arch = Column(String(50), nullable=True)
    
    # Métriques
    last_heartbeat = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    
    # Audit
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    cluster = relationship("SwarmCluster", back_populates="nodes")
    service_replicas = relationship("SwarmServiceReplica", back_populates="node", cascade="all, delete-orphan")


class SwarmService(Base):
    """
    Modèle pour les services Swarm
    """
    __tablename__ = "swarm_services"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(String(255), unique=True, index=True, nullable=False)
    cluster_id = Column(String(255), ForeignKey("swarm_clusters.cluster_id"), nullable=True)
    
    # Configuration de base
    name = Column(String(255), nullable=False)
    image = Column(String(500), nullable=False)
    mode = Column(String(20), nullable=False)  # replicated, global
    
    # Configuration des répliques
    replicas_desired = Column(Integer, nullable=False, default=1)
    replicas_running = Column(Integer, nullable=False, default=0)
    replicas_ready = Column(Integer, nullable=False, default=0)
    
    # Configuration réseau et ports
    ports = Column(JSON, nullable=False, default=list)  # Liste des mappings de ports
    networks = Column(JSON, nullable=False, default=list)  # Liste des réseaux
    
    # Configuration de placement
    constraints = Column(JSON, nullable=False, default=list)  # Contraintes de placement
    preferences = Column(JSON, nullable=False, default=list)  # Préférences de placement
    
    # Configuration de l'environnement
    env_vars = Column(JSON, nullable=False, default=dict)  # Variables d'environnement
    secrets = Column(JSON, nullable=False, default=list)   # Secrets montés
    configs = Column(JSON, nullable=False, default=list)   # Configs montés
    
    # Configuration des ressources
    resources = Column(JSON, nullable=False, default=dict)  # Limites et réservations
    
    # Configuration de redémarrage et mise à jour
    restart_policy = Column(JSON, nullable=False, default=dict)
    update_config = Column(JSON, nullable=False, default=dict)
    rollback_config = Column(JSON, nullable=False, default=dict)
    
    # Health check
    health_check = Column(JSON, nullable=True)
    
    # Métadonnées
    labels = Column(JSON, nullable=False, default=dict)
    status = Column(String(50), nullable=False, default="running")  # running, failed, updating
    
    # Monitoring
    last_health_check = Column(DateTime, nullable=True)
    health_status = Column(String(20), nullable=True)  # healthy, unhealthy, starting
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relations
    cluster = relationship("SwarmCluster", back_populates="services")
    creator = relationship("User", back_populates="swarm_services")
    replicas = relationship("SwarmServiceReplica", back_populates="service", cascade="all, delete-orphan")
    health_checks = relationship("ServiceHealthCheck", back_populates="service", cascade="all, delete-orphan")


class SwarmServiceReplica(Base):
    """
    Modèle pour les répliques de services Swarm
    """
    __tablename__ = "swarm_service_replicas"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(255), unique=True, index=True, nullable=False)
    service_id = Column(String(255), ForeignKey("swarm_services.service_id"), nullable=False)
    node_id = Column(String(255), ForeignKey("swarm_nodes.node_id"), nullable=False)
    
    # Informations de la tâche
    slot = Column(Integer, nullable=True)  # Slot pour les services replicated
    container_id = Column(String(255), nullable=True)
    image = Column(String(500), nullable=False)
    
    # État de la réplique
    state = Column(String(20), nullable=False)  # running, failed, starting, shutdown
    desired_state = Column(String(20), nullable=False)  # running, shutdown
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    service = relationship("SwarmService", back_populates="replicas")
    node = relationship("SwarmNode", back_populates="service_replicas")


class SwarmNetwork(Base):
    """
    Modèle pour les réseaux Swarm
    """
    __tablename__ = "swarm_networks"
    
    id = Column(Integer, primary_key=True, index=True)
    network_id = Column(String(255), unique=True, index=True, nullable=False)
    cluster_id = Column(String(255), ForeignKey("swarm_clusters.cluster_id"), nullable=False)
    
    # Configuration réseau
    name = Column(String(255), nullable=False)
    driver = Column(String(50), nullable=False, default="overlay")
    scope = Column(String(20), nullable=False, default="swarm")
    
    # Configuration IP
    subnet = Column(String(50), nullable=True)
    gateway = Column(String(50), nullable=True)
    ip_range = Column(String(50), nullable=True)
    
    # Options et configuration
    options = Column(JSON, nullable=False, default=dict)
    labels = Column(JSON, nullable=False, default=dict)
    attachable = Column(Boolean, default=False, nullable=False)
    encrypted = Column(Boolean, default=False, nullable=False)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relations
    cluster = relationship("SwarmCluster", back_populates="networks")
    creator = relationship("User", back_populates="swarm_networks")


class SwarmSecret(Base):
    """
    Modèle pour les secrets Swarm
    """
    __tablename__ = "swarm_secrets"
    
    id = Column(Integer, primary_key=True, index=True)
    secret_id = Column(String(255), unique=True, index=True, nullable=False)
    cluster_id = Column(String(255), ForeignKey("swarm_clusters.cluster_id"), nullable=False)
    
    # Configuration du secret
    name = Column(String(255), nullable=False)
    data_encrypted = Column(Text, nullable=False)  # Données chiffrées
    
    # Configuration de montage
    target_path = Column(String(500), nullable=True)  # Chemin de montage dans le conteneur
    uid = Column(String(10), nullable=True)
    gid = Column(String(10), nullable=True)
    mode = Column(String(10), nullable=True)
    
    # Métadonnées
    labels = Column(JSON, nullable=False, default=dict)
    driver_name = Column(String(100), nullable=True)
    driver_options = Column(JSON, nullable=False, default=dict)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relations
    cluster = relationship("SwarmCluster", back_populates="secrets")
    creator = relationship("User", back_populates="swarm_secrets")


class SwarmConfig(Base):
    """
    Modèle pour les configurations Swarm
    """
    __tablename__ = "swarm_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(String(255), unique=True, index=True, nullable=False)
    cluster_id = Column(String(255), ForeignKey("swarm_clusters.cluster_id"), nullable=False)
    
    # Configuration
    name = Column(String(255), nullable=False)
    data = Column(Text, nullable=False)  # Données de configuration
    
    # Configuration de montage
    target_path = Column(String(500), nullable=True)  # Chemin de montage dans le conteneur
    uid = Column(String(10), nullable=True)
    gid = Column(String(10), nullable=True)
    mode = Column(String(10), nullable=True)
    
    # Métadonnées
    labels = Column(JSON, nullable=False, default=dict)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relations
    cluster = relationship("SwarmCluster", back_populates="configs")
    creator = relationship("User", back_populates="swarm_configs")


class SwarmStack(Base):
    """
    Modèle pour les stacks Docker Compose sur Swarm
    """
    __tablename__ = "swarm_stacks"
    
    id = Column(Integer, primary_key=True, index=True)
    stack_id = Column(String(255), unique=True, index=True, nullable=False)
    cluster_id = Column(String(255), ForeignKey("swarm_clusters.cluster_id"), nullable=False)
    
    # Configuration de la stack
    name = Column(String(255), nullable=False)
    compose_file = Column(Text, nullable=False)  # Contenu du docker-compose.yml
    
    # État de la stack
    status = Column(String(50), nullable=False, default="deployed")  # deployed, failed, updating
    services_count = Column(Integer, nullable=False, default=0)
    
    # Configuration de déploiement
    env_vars = Column(JSON, nullable=False, default=dict)
    
    # Métadonnées
    labels = Column(JSON, nullable=False, default=dict)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deployed_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relations
    cluster = relationship("SwarmCluster", back_populates="stacks")
    creator = relationship("User", back_populates="swarm_stacks")


class SwarmLoadBalancer(Base):
    """
    Modèle pour les load balancers Swarm
    """
    __tablename__ = "swarm_load_balancers"
    
    id = Column(Integer, primary_key=True, index=True)
    lb_id = Column(String(255), unique=True, index=True, nullable=False)
    cluster_id = Column(String(255), ForeignKey("swarm_clusters.cluster_id"), nullable=False)
    
    # Configuration du load balancer
    name = Column(String(255), nullable=False)
    algorithm = Column(String(50), nullable=False, default="round_robin")  # round_robin, least_conn, ip_hash
    
    # Configuration frontend
    frontend_port = Column(Integer, nullable=False)
    frontend_protocol = Column(String(20), nullable=False, default="http")  # http, https, tcp
    
    # Configuration backend
    backend_services = Column(JSON, nullable=False, default=list)  # Liste des services backend
    health_check_path = Column(String(500), nullable=True)
    health_check_interval = Column(Integer, nullable=False, default=30)
    
    # Configuration SSL/TLS
    ssl_enabled = Column(Boolean, default=False, nullable=False)
    ssl_cert_path = Column(String(500), nullable=True)
    ssl_key_path = Column(String(500), nullable=True)
    
    # Configuration avancée
    sticky_sessions = Column(Boolean, default=False, nullable=False)
    timeout_connect = Column(Integer, nullable=False, default=5)
    timeout_client = Column(Integer, nullable=False, default=30)
    timeout_server = Column(Integer, nullable=False, default=30)
    
    # État et métriques
    status = Column(String(50), nullable=False, default="active")  # active, inactive, error
    connections_total = Column(Integer, nullable=False, default=0)
    requests_per_second = Column(Float, nullable=False, default=0.0)
    
    # Métadonnées
    labels = Column(JSON, nullable=False, default=dict)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relations
    cluster = relationship("SwarmCluster", back_populates="load_balancers")
    creator = relationship("User", back_populates="swarm_load_balancers")


class ServiceHealthCheck(Base):
    """
    Modèle pour les health checks des services
    """
    __tablename__ = "service_health_checks"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(String(255), ForeignKey("swarm_services.service_id"), nullable=False)
    
    # Configuration du health check
    check_type = Column(String(20), nullable=False)  # http, tcp, exec
    endpoint = Column(String(500), nullable=True)  # URL ou commande
    interval_seconds = Column(Integer, nullable=False, default=30)
    timeout_seconds = Column(Integer, nullable=False, default=10)
    retries = Column(Integer, nullable=False, default=3)
    start_period_seconds = Column(Integer, nullable=False, default=60)
    
    # Résultats du dernier check
    last_check_at = Column(DateTime, nullable=True)
    last_status = Column(String(20), nullable=True)  # healthy, unhealthy, starting
    last_response_time_ms = Column(Integer, nullable=True)
    last_error_message = Column(Text, nullable=True)
    
    # Statistiques
    consecutive_failures = Column(Integer, nullable=False, default=0)
    total_checks = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=1.0)
    
    # Configuration
    enabled = Column(Boolean, default=True, nullable=False)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    service = relationship("SwarmService", back_populates="health_checks")
