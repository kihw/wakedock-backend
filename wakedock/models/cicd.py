"""
Modèles de base de données pour le système CI/CD avec GitHub Actions
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class GitHubIntegration(Base):
    """
    Modèle pour les intégrations GitHub Actions
    """
    __tablename__ = "github_integrations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    repository = Column(String(255), nullable=False)  # owner/repo
    workflow_file = Column(String(255), nullable=False)  # .github/workflows/deploy.yml
    branch = Column(String(100), nullable=False, default="main")
    
    # Configuration de déploiement
    environment = Column(String(50), nullable=False, default="development")  # development, staging, production
    auto_deploy = Column(Boolean, nullable=False, default=False)
    security_checks = Column(Boolean, nullable=False, default=True)
    required_approvals = Column(Integer, nullable=False, default=0)
    timeout_minutes = Column(Integer, nullable=False, default=30)
    
    # Configuration complète stockée en JSON
    configuration = Column(JSON, nullable=True)
    
    # Secrets et variables d'environnement (chiffrés)
    secrets = Column(JSON, nullable=True)  # Secrets chiffrés
    variables = Column(JSON, nullable=True)  # Variables d'environnement
    
    # Métadonnées
    webhook_url = Column(String(500), nullable=True)
    webhook_secret = Column(String(255), nullable=True)  # Hash du secret
    last_webhook = Column(DateTime, nullable=True)
    
    # État
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    creator = relationship("User", back_populates="github_integrations")
    builds = relationship("CIBuild", back_populates="integration")
    deployments = relationship("Deployment", back_populates="integration")
    
    # Index composites
    __table_args__ = (
        Index('idx_github_repo_workflow', 'repository', 'workflow_file'),
        Index('idx_github_active', 'is_active', 'created_at'),
    )

class CIBuild(Base):
    """
    Modèle pour les builds CI/CD
    """
    __tablename__ = "ci_builds"
    
    id = Column(Integer, primary_key=True, index=True)
    build_id = Column(String(255), unique=True, index=True, nullable=False)
    integration_id = Column(Integer, ForeignKey("github_integrations.id"), nullable=False)
    
    # Informations du build
    branch = Column(String(100), nullable=False)
    commit_sha = Column(String(40), nullable=False)
    commit_message = Column(Text, nullable=True)
    author = Column(String(255), nullable=True)
    
    # État du build
    status = Column(String(20), index=True, nullable=False, default="pending")  # pending, in_progress, success, failure, cancelled
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_manual = Column(Boolean, nullable=False, default=False)
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Résultats et logs
    logs_url = Column(String(500), nullable=True)
    artifacts_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Rapports de tests et sécurité
    test_results = Column(JSON, nullable=True)
    security_report = Column(JSON, nullable=True)
    performance_metrics = Column(JSON, nullable=True)
    
    # Métadonnées
    environment_variables = Column(JSON, nullable=True)
    build_metadata = Column(JSON, nullable=True)
    
    # Relations
    integration = relationship("GitHubIntegration", back_populates="builds")
    triggered_by_user = relationship("User", back_populates="triggered_builds")
    deployments = relationship("Deployment", back_populates="build")
    
    # Index composites
    __table_args__ = (
        Index('idx_builds_integration_status', 'integration_id', 'status'),
        Index('idx_builds_created_status', 'created_at', 'status'),
        Index('idx_builds_branch_sha', 'branch', 'commit_sha'),
    )

class Deployment(Base):
    """
    Modèle pour les déploiements
    """
    __tablename__ = "deployments"
    
    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(String(255), unique=True, index=True, nullable=False)
    integration_id = Column(Integer, ForeignKey("github_integrations.id"), nullable=False)
    build_id = Column(String(255), ForeignKey("ci_builds.build_id"), nullable=True)
    
    # Informations de déploiement
    environment = Column(String(50), nullable=False)  # development, staging, production
    version = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    
    # État du déploiement
    status = Column(String(20), index=True, nullable=False, default="pending")  # pending, in_progress, success, failure, rolled_back
    deployed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # URLs et services
    deployment_url = Column(String(500), nullable=True)
    health_check_url = Column(String(500), nullable=True)
    rollback_url = Column(String(500), nullable=True)
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Métriques post-déploiement
    health_checks = Column(JSON, nullable=True)
    performance_metrics = Column(JSON, nullable=True)
    rollback_plan = Column(JSON, nullable=True)
    
    # Métadonnées
    deployment_metadata = Column(JSON, nullable=True)
    
    # Relations
    integration = relationship("GitHubIntegration", back_populates="deployments")
    build = relationship("CIBuild", back_populates="deployments")
    deployer = relationship("User", back_populates="deployments")
    
    # Index composites
    __table_args__ = (
        Index('idx_deployments_env_status', 'environment', 'status'),
        Index('idx_deployments_integration_env', 'integration_id', 'environment'),
    )

class Pipeline(Base):
    """
    Modèle pour les pipelines CI/CD complets
    """
    __tablename__ = "pipelines"
    
    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    
    # Configuration du pipeline
    stages = Column(JSON, nullable=False)  # Liste des étapes
    triggers = Column(JSON, nullable=True)  # Conditions de déclenchement
    approvals = Column(JSON, nullable=True)  # Workflow d'approbation
    
    # Relations avec les intégrations
    integrations = Column(JSON, nullable=True)  # Liste des integration_ids
    
    # État du pipeline
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    creator = relationship("User", back_populates="pipelines")

class Secret(Base):
    """
    Modèle pour la gestion sécurisée des secrets
    """
    __tablename__ = "secrets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Valeur chiffrée
    encrypted_value = Column(Text, nullable=False)
    salt = Column(String(255), nullable=False)
    
    # Portée et permissions
    scope = Column(String(50), nullable=False, default="integration")  # global, integration, environment
    scope_id = Column(Integer, nullable=True)  # ID de l'intégration/environnement
    
    # Métadonnées de sécurité
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    accessed_count = Column(Integer, nullable=False, default=0)
    last_accessed = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # État
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    creator = relationship("User", back_populates="secrets")
    
    # Index composites
    __table_args__ = (
        Index('idx_secrets_scope', 'scope', 'scope_id'),
        Index('idx_secrets_active', 'is_active', 'expires_at'),
    )

class WebhookEvent(Base):
    """
    Modèle pour l'historique des événements webhook
    """
    __tablename__ = "webhook_events"
    
    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("github_integrations.id"), nullable=False)
    
    # Informations de l'événement
    event_type = Column(String(50), index=True, nullable=False)
    repository = Column(String(255), nullable=False)
    branch = Column(String(100), nullable=True)
    commit_sha = Column(String(40), nullable=True)
    author = Column(String(255), nullable=True)
    
    # Payload et métadonnées
    payload = Column(JSON, nullable=False)
    headers = Column(JSON, nullable=True)
    source_ip = Column(String(45), nullable=True)
    
    # Traitement
    processed = Column(Boolean, nullable=False, default=False)
    processing_result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    received_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)
    
    # Relations
    integration = relationship("GitHubIntegration")
    
    # Index composites
    __table_args__ = (
        Index('idx_webhooks_integration_type', 'integration_id', 'event_type'),
        Index('idx_webhooks_received', 'received_at', 'processed'),
    )

class CIMetrics(Base):
    """
    Modèle pour les métriques CI/CD calculées périodiquement
    """
    __tablename__ = "ci_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_type = Column(String(50), index=True, nullable=False)  # daily, weekly, monthly
    metric_date = Column(DateTime, index=True, nullable=False)
    
    # Métriques de build
    total_builds = Column(Integer, nullable=False, default=0)
    successful_builds = Column(Integer, nullable=False, default=0)
    failed_builds = Column(Integer, nullable=False, default=0)
    cancelled_builds = Column(Integer, nullable=False, default=0)
    
    # Métriques de timing
    average_build_time = Column(Integer, nullable=False, default=0)  # en secondes
    median_build_time = Column(Integer, nullable=False, default=0)
    max_build_time = Column(Integer, nullable=False, default=0)
    
    # Métriques de déploiement
    total_deployments = Column(Integer, nullable=False, default=0)
    successful_deployments = Column(Integer, nullable=False, default=0)
    failed_deployments = Column(Integer, nullable=False, default=0)
    
    # Métriques détaillées (JSON)
    builds_by_integration = Column(JSON, nullable=True)
    builds_by_branch = Column(JSON, nullable=True)
    failure_reasons = Column(JSON, nullable=True)
    performance_trends = Column(JSON, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Index composites
    __table_args__ = (
        Index('idx_ci_metrics_type_date', 'metric_type', 'metric_date'),
    )

# Extensions du modèle User pour les relations CI/CD
def extend_user_model():
    """
    Fonction pour étendre le modèle User avec les relations CI/CD
    À appeler après l'import du modèle User existant
    """
    try:
        from wakedock.database.models import User

        # Ajouter les relations si elles n'existent pas déjà
        if not hasattr(User, 'github_integrations'):
            User.github_integrations = relationship("GitHubIntegration", back_populates="creator")
        
        if not hasattr(User, 'triggered_builds'):
            User.triggered_builds = relationship("CIBuild", back_populates="triggered_by_user")
        
        if not hasattr(User, 'deployments'):
            User.deployments = relationship("Deployment", back_populates="deployer")
        
        if not hasattr(User, 'pipelines'):
            User.pipelines = relationship("Pipeline", back_populates="creator")
        
        if not hasattr(User, 'secrets'):
            User.secrets = relationship("Secret", back_populates="creator")
            
    except ImportError:
        # Le modèle User n'existe pas encore ou n'est pas accessible
        pass
