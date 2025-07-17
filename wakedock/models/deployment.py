"""
WakeDock - Modèles de données pour déploiement automatique
=========================================================

Modèles SQLAlchemy pour gérer:
- Configurations de déploiement automatique depuis repositories Git
- Historique complet des déploiements avec métriques
- Gestion secrets chiffrés pour containers
- Monitoring santé containers déployés
- Métriques performance et sécurité

Relations:
- AutoDeployment -> DeploymentHistory (1:N) : Historique déploiements
- AutoDeployment -> DeploymentSecret (1:N) : Secrets chiffrés
- DeploymentHistory -> DeploymentMetrics (1:N) : Métriques détaillées
- DeploymentHistory -> ContainerHealth (1:N) : Monitoring santé

Sécurité:
- Secrets chiffrés avec Fernet (AES)
- Audit trail complet avec utilisateurs
- Isolation par utilisateur avec RBAC
- Validation données sensibles

Auteur: WakeDock Development Team
Version: 0.4.2
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from wakedock.models.base import Base


class AutoDeployment(Base):
    """Configuration de déploiement automatique depuis repositories Git"""
    
    __tablename__ = "auto_deployments"
    
    # Identifiants
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Configuration de base
    name = Column(String(100), nullable=False)  # Nom unique par utilisateur
    repository_url = Column(String(500), nullable=False)  # URL Git repository
    branch = Column(String(100), nullable=False, default="main")
    dockerfile_path = Column(String(200), default="Dockerfile")  # Chemin relatif Dockerfile
    
    # Configuration déploiement
    auto_deploy = Column(Boolean, default=True)  # Déploiement automatique sur push
    environment = Column(String(50), default="development")  # dev/staging/prod
    container_config = Column(JSON, default=dict)  # Configuration container JSON
    
    # État et métadonnées
    status = Column(String(50), default="configured")  # configured/deploying/deployed/failed
    current_container_id = Column(String(100), nullable=True)  # Container Docker actuel
    last_deployed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relations
    user = relationship("User", back_populates="auto_deployments")
    deployment_histories = relationship("DeploymentHistory", back_populates="deployment", 
                                      cascade="all, delete-orphan", order_by="DeploymentHistory.started_at.desc()")
    secrets = relationship("DeploymentSecret", back_populates="deployment", 
                          cascade="all, delete-orphan")
    
    # Contraintes
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='uq_user_deployment_name'),
        Index('idx_auto_deployments_status', 'status'),
        Index('idx_auto_deployments_environment', 'environment'),
        Index('idx_auto_deployments_last_deployed', 'last_deployed_at'),
    )
    
    def __repr__(self):
        return f"<AutoDeployment(id={self.id}, name='{self.name}', status='{self.status}')>"
    
    @property
    def is_deployable(self) -> bool:
        """Vérifier si déploiement peut être déclenché"""
        return self.status not in ["deploying", "building"]
    
    @property
    def latest_deployment(self) -> Optional['DeploymentHistory']:
        """Récupérer dernier déploiement"""
        return self.deployment_histories[0] if self.deployment_histories else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir en dictionnaire pour API"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "repository_url": self.repository_url,
            "branch": self.branch,
            "dockerfile_path": self.dockerfile_path,
            "auto_deploy": self.auto_deploy,
            "environment": self.environment,
            "container_config": self.container_config,
            "status": self.status,
            "current_container_id": self.current_container_id,
            "last_deployed_at": self.last_deployed_at.isoformat() if self.last_deployed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_deployable": self.is_deployable
        }

class DeploymentHistory(Base):
    """Historique des déploiements avec logs et métadonnées"""
    
    __tablename__ = "deployment_history"
    
    # Identifiants
    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, ForeignKey("auto_deployments.id"), nullable=False, index=True)
    
    # Informations déploiement
    commit_sha = Column(String(40), nullable=False)  # SHA commit Git déployé
    trigger_type = Column(String(50), nullable=False)  # manual/webhook/scheduled
    triggered_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # État et timing
    status = Column(String(50), default="pending")  # pending/building/deploying/success/failed/cancelled/timeout
    started_at = Column(DateTime, default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Logs et résultats
    logs = Column(Text, default="")  # Logs complets du déploiement
    result_data = Column(JSON, default=dict)  # Données résultat (container_id, image, etc.)
    error_message = Column(Text, nullable=True)  # Message d'erreur si échec
    
    # Relations
    deployment = relationship("AutoDeployment", back_populates="deployment_histories")
    triggered_by_user = relationship("User", foreign_keys=[triggered_by])
    metrics = relationship("DeploymentMetrics", back_populates="history", 
                          cascade="all, delete-orphan")
    health_checks = relationship("ContainerHealth", back_populates="deployment_history", 
                                cascade="all, delete-orphan")
    
    # Index pour performance
    __table_args__ = (
        Index('idx_deployment_history_status', 'status'),
        Index('idx_deployment_history_started', 'started_at'),
        Index('idx_deployment_history_trigger', 'trigger_type'),
    )
    
    def __repr__(self):
        return f"<DeploymentHistory(id={self.id}, deployment_id={self.deployment_id}, status='{self.status}')>"
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculer durée déploiement en secondes"""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_completed(self) -> bool:
        """Vérifier si déploiement terminé"""
        return self.status in ["success", "failed", "cancelled", "timeout"]
    
    @property
    def is_successful(self) -> bool:
        """Vérifier si déploiement réussi"""
        return self.status == "success"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir en dictionnaire pour API"""
        return {
            "id": self.id,
            "deployment_id": self.deployment_id,
            "commit_sha": self.commit_sha,
            "trigger_type": self.trigger_type,
            "triggered_by": self.triggered_by,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "logs": self.logs,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "is_completed": self.is_completed,
            "is_successful": self.is_successful
        }

class DeploymentSecret(Base):
    """Secrets chiffrés pour containers déployés"""
    
    __tablename__ = "deployment_secrets"
    
    # Identifiants
    id = Column(Integer, primary_key=True, index=True)
    deployment_id = Column(Integer, ForeignKey("auto_deployments.id"), nullable=False, index=True)
    
    # Secret data
    key = Column(String(100), nullable=False)  # Nom variable environnement
    encrypted_value = Column(Text, nullable=False)  # Valeur chiffrée
    description = Column(String(200), nullable=True)  # Description optionnelle
    
    # Métadonnées
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    last_used_at = Column(DateTime, nullable=True)  # Dernière utilisation
    
    # Relations
    deployment = relationship("AutoDeployment", back_populates="secrets")
    created_by_user = relationship("User")
    
    # Contraintes uniques
    __table_args__ = (
        UniqueConstraint('deployment_id', 'key', name='uq_deployment_secret_key'),
        Index('idx_deployment_secrets_key', 'key'),
    )
    
    def __repr__(self):
        return f"<DeploymentSecret(id={self.id}, deployment_id={self.deployment_id}, key='{self.key}')>"
    
    def to_dict(self, include_value: bool = False) -> Dict[str, Any]:
        """Convertir en dictionnaire (sans valeur par défaut)"""
        data = {
            "id": self.id,
            "deployment_id": self.deployment_id,
            "key": self.key,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None
        }
        
        # Ne jamais inclure valeur chiffrée dans API standard
        if include_value:
            data["encrypted_value"] = self.encrypted_value
            
        return data

class DeploymentMetrics(Base):
    """Métriques détaillées des déploiements"""
    
    __tablename__ = "deployment_metrics"
    
    # Identifiants
    id = Column(Integer, primary_key=True, index=True)
    history_id = Column(Integer, ForeignKey("deployment_history.id"), nullable=False, index=True)
    
    # Métriques timing
    deployment_time = Column(Float, default=0)  # Temps total déploiement (secondes)
    build_time = Column(Float, default=0)  # Temps construction image
    health_check_time = Column(Float, default=0)  # Temps health checks
    
    # Métriques taille et ressources
    image_size = Column(Integer, default=0)  # Taille image Docker (bytes)
    container_memory_usage = Column(Integer, default=0)  # Utilisation mémoire (bytes)
    container_cpu_usage = Column(Float, default=0)  # Utilisation CPU (%)
    
    # Métriques sécurité et qualité
    security_score = Column(Integer, default=0)  # Score sécurité (0-100)
    vulnerabilities_count = Column(Integer, default=0)  # Nombre vulnérabilités
    health_checks_passed = Column(Integer, default=0)  # Nombre health checks réussis
    health_checks_total = Column(Integer, default=0)  # Nombre total health checks
    
    # Métriques opérationnelles
    rollback_performed = Column(Boolean, default=False)  # Rollback effectué
    retry_count = Column(Integer, default=0)  # Nombre tentatives
    queue_wait_time = Column(Float, default=0)  # Temps attente queue (secondes)
    
    # Timestamp
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relations
    history = relationship("DeploymentHistory", back_populates="metrics")
    
    # Index pour analytics
    __table_args__ = (
        Index('idx_deployment_metrics_deployment_time', 'deployment_time'),
        Index('idx_deployment_metrics_security_score', 'security_score'),
        Index('idx_deployment_metrics_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<DeploymentMetrics(id={self.id}, history_id={self.history_id}, deployment_time={self.deployment_time})>"
    
    @property
    def health_check_success_rate(self) -> float:
        """Calculer taux succès health checks"""
        if self.health_checks_total > 0:
            return (self.health_checks_passed / self.health_checks_total) * 100
        return 0
    
    @property
    def performance_score(self) -> int:
        """Calculer score performance basé sur timing"""
        # Score basé sur temps déploiement (rapide = meilleur)
        if self.deployment_time <= 300:  # 5 minutes
            return 100
        elif self.deployment_time <= 600:  # 10 minutes
            return 80
        elif self.deployment_time <= 1200:  # 20 minutes
            return 60
        elif self.deployment_time <= 1800:  # 30 minutes
            return 40
        else:
            return 20
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir en dictionnaire pour API"""
        return {
            "id": self.id,
            "history_id": self.history_id,
            "deployment_time": self.deployment_time,
            "build_time": self.build_time,
            "health_check_time": self.health_check_time,
            "image_size": self.image_size,
            "container_memory_usage": self.container_memory_usage,
            "container_cpu_usage": self.container_cpu_usage,
            "security_score": self.security_score,
            "vulnerabilities_count": self.vulnerabilities_count,
            "health_checks_passed": self.health_checks_passed,
            "health_checks_total": self.health_checks_total,
            "health_check_success_rate": self.health_check_success_rate,
            "performance_score": self.performance_score,
            "rollback_performed": self.rollback_performed,
            "retry_count": self.retry_count,
            "queue_wait_time": self.queue_wait_time,
            "created_at": self.created_at.isoformat()
        }

class ContainerHealth(Base):
    """Monitoring santé containers déployés"""
    
    __tablename__ = "container_health"
    
    # Identifiants
    id = Column(Integer, primary_key=True, index=True)
    deployment_history_id = Column(Integer, ForeignKey("deployment_history.id"), nullable=False, index=True)
    container_id = Column(String(100), nullable=False, index=True)  # ID Docker container
    
    # Informations santé
    check_type = Column(String(50), nullable=False)  # startup/liveness/readiness/custom
    status = Column(String(20), nullable=False)  # healthy/unhealthy/unknown
    response_time = Column(Float, nullable=True)  # Temps réponse check (ms)
    
    # Détails check
    check_url = Column(String(200), nullable=True)  # URL health check HTTP
    expected_status = Column(Integer, nullable=True)  # Code HTTP attendu
    actual_status = Column(Integer, nullable=True)  # Code HTTP reçu
    error_message = Column(Text, nullable=True)  # Message erreur si échec
    
    # Métriques système
    cpu_usage = Column(Float, nullable=True)  # Utilisation CPU (%)
    memory_usage = Column(Integer, nullable=True)  # Utilisation mémoire (bytes)
    network_rx = Column(Integer, default=0)  # Octets reçus
    network_tx = Column(Integer, default=0)  # Octets transmis
    
    # Timestamp
    checked_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relations
    deployment_history = relationship("DeploymentHistory", back_populates="health_checks")
    
    # Index pour monitoring
    __table_args__ = (
        Index('idx_container_health_status', 'status'),
        Index('idx_container_health_checked', 'checked_at'),
        Index('idx_container_health_container', 'container_id'),
        Index('idx_container_health_check_type', 'check_type'),
    )
    
    def __repr__(self):
        return f"<ContainerHealth(id={self.id}, container_id='{self.container_id}', status='{self.status}')>"
    
    @property
    def is_healthy(self) -> bool:
        """Vérifier si check indique santé OK"""
        return self.status == "healthy"
    
    @property
    def memory_usage_mb(self) -> Optional[float]:
        """Utilisation mémoire en MB"""
        if self.memory_usage:
            return self.memory_usage / (1024 * 1024)
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir en dictionnaire pour API"""
        return {
            "id": self.id,
            "deployment_history_id": self.deployment_history_id,
            "container_id": self.container_id,
            "check_type": self.check_type,
            "status": self.status,
            "response_time": self.response_time,
            "check_url": self.check_url,
            "expected_status": self.expected_status,
            "actual_status": self.actual_status,
            "error_message": self.error_message,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "memory_usage_mb": self.memory_usage_mb,
            "network_rx": self.network_rx,
            "network_tx": self.network_tx,
            "checked_at": self.checked_at.isoformat(),
            "is_healthy": self.is_healthy
        }

class DeploymentConfig(Base):
    """Configuration globale pour déploiements automatiques"""
    
    __tablename__ = "deployment_config"
    
    # Identifiants
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Configuration déploiement
    max_concurrent_deployments = Column(Integer, default=3)  # Limite déploiements parallèles
    default_timeout = Column(Integer, default=1800)  # Timeout par défaut (secondes)
    auto_rollback = Column(Boolean, default=True)  # Rollback automatique si échec
    health_check_enabled = Column(Boolean, default=True)  # Health checks activés
    
    # Configuration sécurité
    security_scan_enabled = Column(Boolean, default=True)  # Scan sécurité images
    min_security_score = Column(Integer, default=70)  # Score sécurité minimum
    allowed_registries = Column(JSON, default=list)  # Registries autorisés
    blocked_ports = Column(JSON, default=list)  # Ports bloqués
    
    # Configuration ressources
    max_cpu_limit = Column(Float, default=2.0)  # Limite CPU par container
    max_memory_limit = Column(String(20), default="2G")  # Limite mémoire
    default_network = Column(String(50), default="wakedock-network")
    
    # Configuration notifications
    notify_on_success = Column(Boolean, default=False)
    notify_on_failure = Column(Boolean, default=True)
    notification_webhook = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relations
    user = relationship("User")
    
    # Contraintes
    __table_args__ = (
        UniqueConstraint('user_id', name='uq_user_deployment_config'),
    )
    
    def __repr__(self):
        return f"<DeploymentConfig(id={self.id}, user_id={self.user_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir en dictionnaire pour API"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "max_concurrent_deployments": self.max_concurrent_deployments,
            "default_timeout": self.default_timeout,
            "auto_rollback": self.auto_rollback,
            "health_check_enabled": self.health_check_enabled,
            "security_scan_enabled": self.security_scan_enabled,
            "min_security_score": self.min_security_score,
            "allowed_registries": self.allowed_registries,
            "blocked_ports": self.blocked_ports,
            "max_cpu_limit": self.max_cpu_limit,
            "max_memory_limit": self.max_memory_limit,
            "default_network": self.default_network,
            "notify_on_success": self.notify_on_success,
            "notify_on_failure": self.notify_on_failure,
            "notification_webhook": self.notification_webhook,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

# Ajouter relations inverses au modèle User (si nécessaire)
# Note: Ces relations seront ajoutées au modèle User existant

def add_deployment_relations_to_user():
    """
    Fonction helper pour ajouter relations déploiement au modèle User existant.
    À appeler après import du modèle User.
    """
    from wakedock.models.user import User

    # Ajouter relations si pas déjà présentes
    if not hasattr(User, 'auto_deployments'):
        User.auto_deployments = relationship("AutoDeployment", back_populates="user", 
                                           cascade="all, delete-orphan")
    
    if not hasattr(User, 'deployment_config'):
        User.deployment_config = relationship("DeploymentConfig", uselist=False, 
                                            cascade="all, delete-orphan")

# Classes utilitaires pour analytics et rapports

class DeploymentAnalytics:
    """Classe utilitaire pour calculer analytics de déploiement"""
    
    @staticmethod
    def calculate_success_rate(deployments: List[DeploymentHistory]) -> float:
        """Calculer taux de succès"""
        if not deployments:
            return 0
        successful = len([d for d in deployments if d.is_successful])
        return (successful / len(deployments)) * 100
    
    @staticmethod
    def calculate_average_deployment_time(deployments: List[DeploymentHistory]) -> float:
        """Calculer temps moyen de déploiement"""
        completed = [d for d in deployments if d.duration_seconds is not None]
        if not completed:
            return 0
        return sum(d.duration_seconds for d in completed) / len(completed)
    
    @staticmethod
    def get_deployment_trends(deployments: List[DeploymentHistory], days: int = 30) -> Dict[str, Any]:
        """Analyser tendances de déploiement"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        recent_deployments = [d for d in deployments if d.started_at >= cutoff_date]
        
        return {
            "total_deployments": len(recent_deployments),
            "success_rate": DeploymentAnalytics.calculate_success_rate(recent_deployments),
            "average_time": DeploymentAnalytics.calculate_average_deployment_time(recent_deployments),
            "rollback_count": len([d for d in recent_deployments if any(m.rollback_performed for m in d.metrics)]),
            "most_active_day": DeploymentAnalytics._get_most_active_day(recent_deployments),
            "period_days": days
        }
    
    @staticmethod
    def _get_most_active_day(deployments: List[DeploymentHistory]) -> str:
        """Trouver jour le plus actif"""
        if not deployments:
            return "none"
        
        day_counts = {}
        for deployment in deployments:
            day = deployment.started_at.strftime('%A')
            day_counts[day] = day_counts.get(day, 0) + 1
        
        return max(day_counts.items(), key=lambda x: x[1])[0] if day_counts else "none"

# Configuration modèle pour migrations Alembic
__all__ = [
    "AutoDeployment", 
    "DeploymentHistory", 
    "DeploymentSecret", 
    "DeploymentMetrics", 
    "ContainerHealth",
    "DeploymentConfig",
    "DeploymentAnalytics",
    "add_deployment_relations_to_user"
]
