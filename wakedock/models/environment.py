"""
Modèles de base de données pour la gestion des environnements
"""
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship
from wakedock.database.database import Base


class Environment(Base):
    """
    Modèle pour les environnements de déploiement (dev/staging/prod)
    """
    __tablename__ = "environments"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    type = Column(String(50), nullable=False)  # development, staging, production, testing
    status = Column(String(50), nullable=False, default="active")  # active, inactive, maintenance, error
    
    # Configuration
    description = Column(Text, nullable=True)
    config = Column(JSON, nullable=False, default=dict)  # Configuration spécifique à l'environnement
    
    # Santé et monitoring
    health_score = Column(Float, nullable=False, default=1.0)  # Score entre 0 et 1
    last_deployment = Column(DateTime, nullable=True)
    last_health_check = Column(DateTime, nullable=True)
    
    # Paramètres de déploiement
    auto_deploy = Column(Boolean, default=False, nullable=False)
    require_approval = Column(Boolean, default=True, nullable=False)
    rollback_on_failure = Column(Boolean, default=True, nullable=False)
    
    # Métriques de performance
    average_response_time = Column(Float, nullable=True)
    error_rate = Column(Float, nullable=True)
    uptime_percentage = Column(Float, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relations
    creator = relationship("User", back_populates="environments")
    variables = relationship("EnvironmentVariable", back_populates="environment", cascade="all, delete-orphan")
    configs = relationship("EnvironmentConfig", back_populates="environment", cascade="all, delete-orphan")
    health_records = relationship("EnvironmentHealth", back_populates="environment", cascade="all, delete-orphan")
    promotions_source = relationship("BuildPromotion", foreign_keys="BuildPromotion.source_environment_id", back_populates="source_env")
    promotions_target = relationship("BuildPromotion", foreign_keys="BuildPromotion.target_environment_id", back_populates="target_env")


class EnvironmentVariable(Base):
    """
    Modèle pour les variables d'environnement
    """
    __tablename__ = "environment_variables"
    
    id = Column(Integer, primary_key=True, index=True)
    environment_id = Column(Integer, ForeignKey("environments.id"), nullable=False)
    
    # Variable
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)
    is_secret = Column(Boolean, default=False, nullable=False)  # Variable sensible
    is_encrypted = Column(Boolean, default=False, nullable=False)  # Valeur chiffrée
    
    # Métadonnées
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)  # database, api, security, etc.
    
    # Version et historique
    version = Column(Integer, default=1, nullable=False)
    previous_value = Column(Text, nullable=True)  # Valeur précédente pour rollback
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relations
    environment = relationship("Environment", back_populates="variables")
    creator = relationship("User", back_populates="environment_variables")


class EnvironmentConfig(Base):
    """
    Modèle pour les configurations d'environnement
    """
    __tablename__ = "environment_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    environment_id = Column(Integer, ForeignKey("environments.id"), nullable=False)
    
    # Configuration
    config_type = Column(String(100), nullable=False)  # deployment, monitoring, security, etc.
    name = Column(String(255), nullable=False)
    value = Column(JSON, nullable=False)
    
    # Métadonnées
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=0, nullable=False)  # Ordre d'application
    
    # Validation
    schema = Column(JSON, nullable=True)  # Schéma de validation
    validation_rules = Column(JSON, nullable=True)  # Règles de validation
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relations
    environment = relationship("Environment", back_populates="configs")
    creator = relationship("User", back_populates="environment_configs")


class BuildPromotion(Base):
    """
    Modèle pour les promotions de builds entre environnements
    """
    __tablename__ = "build_promotions"
    
    id = Column(Integer, primary_key=True, index=True)
    build_id = Column(String(255), nullable=False, index=True)
    
    # Environnements
    source_environment = Column(String(100), nullable=False)  # Nom de l'environnement source
    target_environment = Column(String(100), nullable=False)  # Nom de l'environnement cible
    source_environment_id = Column(Integer, ForeignKey("environments.id"), nullable=True)
    target_environment_id = Column(Integer, ForeignKey("environments.id"), nullable=True)
    
    # Type et statut de promotion
    promotion_type = Column(String(50), nullable=False)  # manual, automatic, scheduled, rollback
    status = Column(String(50), nullable=False, default="pending")  # pending, approved, rejected, in_progress, completed, failed
    
    # Approbations
    approvals_required = Column(Integer, default=0, nullable=False)
    approvals_received = Column(Integer, default=0, nullable=False)
    
    # Configuration du déploiement
    deployment_config = Column(JSON, nullable=True)  # Configuration spécifique au déploiement
    rollback_config = Column(JSON, nullable=True)   # Configuration de rollback
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    
    # Résultats
    deployment_logs = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    rollback_logs = Column(Text, nullable=True)
    
    # Métriques
    deployment_duration = Column(Integer, nullable=True)  # Durée en secondes
    tests_passed = Column(Integer, nullable=True)
    tests_failed = Column(Integer, nullable=True)
    
    # Audit
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relations
    creator = relationship("User", foreign_keys=[created_by], back_populates="build_promotions_created")
    approver = relationship("User", foreign_keys=[approved_by], back_populates="build_promotions_approved")
    source_env = relationship("Environment", foreign_keys=[source_environment_id], back_populates="promotions_source")
    target_env = relationship("Environment", foreign_keys=[target_environment_id], back_populates="promotions_target")
    approvals = relationship("PromotionApproval", back_populates="promotion", cascade="all, delete-orphan")
    rules = relationship("PromotionRule", back_populates="promotion", cascade="all, delete-orphan")


class PromotionApproval(Base):
    """
    Modèle pour les approbations de promotions
    """
    __tablename__ = "promotion_approvals"
    
    id = Column(Integer, primary_key=True, index=True)
    promotion_id = Column(Integer, ForeignKey("build_promotions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Approbation
    approved = Column(Boolean, nullable=False)  # True = approuvé, False = rejeté
    comment = Column(Text, nullable=True)
    conditions = Column(JSON, nullable=True)  # Conditions d'approbation
    
    # Métadonnées
    approval_level = Column(String(50), nullable=True)  # manager, senior, admin
    is_final = Column(Boolean, default=False, nullable=False)  # Approbation finale
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relations
    promotion = relationship("BuildPromotion", back_populates="approvals")
    user = relationship("User", back_populates="promotion_approvals")


class PromotionRule(Base):
    """
    Modèle pour les règles de promotion
    """
    __tablename__ = "promotion_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    promotion_id = Column(Integer, ForeignKey("build_promotions.id"), nullable=True)
    
    # Règle
    name = Column(String(255), nullable=False)
    rule_type = Column(String(100), nullable=False)  # health_check, test_coverage, security_scan, etc.
    condition = Column(JSON, nullable=False)  # Condition à vérifier
    
    # Configuration
    is_blocking = Column(Boolean, default=True, nullable=False)  # Bloque la promotion si non respectée
    priority = Column(Integer, default=0, nullable=False)
    timeout_seconds = Column(Integer, nullable=True)
    
    # Résultats
    status = Column(String(50), nullable=True)  # passed, failed, skipped, pending
    result = Column(JSON, nullable=True)  # Résultat détaillé
    checked_at = Column(DateTime, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    promotion = relationship("BuildPromotion", back_populates="rules")


class EnvironmentHealth(Base):
    """
    Modèle pour le monitoring de santé des environnements
    """
    __tablename__ = "environment_health"
    
    id = Column(Integer, primary_key=True, index=True)
    environment_id = Column(Integer, ForeignKey("environments.id"), nullable=False)
    
    # Santé globale
    health_score = Column(Float, nullable=False)  # Score entre 0 et 1
    status = Column(String(50), nullable=False)  # healthy, degraded, unhealthy, down
    
    # Métriques détaillées
    metrics = Column(JSON, nullable=False, default=dict)  # Métriques spécifiques
    
    # Métriques de performance
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    network_latency = Column(Float, nullable=True)
    
    # Métriques applicatives
    response_time = Column(Float, nullable=True)
    throughput = Column(Float, nullable=True)
    error_rate = Column(Float, nullable=True)
    active_connections = Column(Integer, nullable=True)
    
    # Services
    services_total = Column(Integer, nullable=True)
    services_healthy = Column(Integer, nullable=True)
    services_degraded = Column(Integer, nullable=True)
    services_down = Column(Integer, nullable=True)
    
    # Alertes
    alerts_active = Column(Integer, nullable=True)
    alerts_critical = Column(Integer, nullable=True)
    last_alert = Column(DateTime, nullable=True)
    
    # Disponibilité
    uptime_seconds = Column(Integer, nullable=True)
    downtime_seconds = Column(Integer, nullable=True)
    
    # Audit
    checked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    checker_type = Column(String(50), nullable=True)  # automated, manual, external
    
    # Relations
    environment = relationship("Environment", back_populates="health_records")


class DeploymentPromotion(Base):
    """
    Modèle pour l'historique des promotions de déploiements
    """
    __tablename__ = "deployment_promotions"
    
    id = Column(Integer, primary_key=True, index=True)
    promotion_id = Column(Integer, ForeignKey("build_promotions.id"), nullable=False)
    
    # Déploiement
    deployment_id = Column(String(255), nullable=False)
    version = Column(String(100), nullable=False)
    commit_sha = Column(String(40), nullable=True)
    branch = Column(String(255), nullable=True)
    
    # Configuration
    deployment_strategy = Column(String(50), nullable=False, default="rolling")  # rolling, blue_green, canary
    rollback_strategy = Column(String(50), nullable=False, default="immediate")
    
    # Résultats
    success = Column(Boolean, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    instances_deployed = Column(Integer, nullable=True)
    instances_failed = Column(Integer, nullable=True)
    
    # Logs et diagnostics
    deployment_logs = Column(Text, nullable=True)
    error_logs = Column(Text, nullable=True)
    performance_metrics = Column(JSON, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Relations
    promotion = relationship("BuildPromotion")


class EnvironmentTemplate(Base):
    """
    Modèle pour les templates d'environnements
    """
    __tablename__ = "environment_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Template
    environment_type = Column(String(50), nullable=False)
    default_config = Column(JSON, nullable=False, default=dict)
    default_variables = Column(JSON, nullable=False, default=dict)
    
    # Règles et validations
    promotion_rules = Column(JSON, nullable=False, default=dict)
    validation_schema = Column(JSON, nullable=True)
    
    # Configuration
    is_active = Column(Boolean, default=True, nullable=False)
    is_system_template = Column(Boolean, default=False, nullable=False)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relations
    creator = relationship("User", back_populates="environment_templates")
