"""
Script d'initialisation des données d'authentification par défaut
"""

import asyncio
from datetime import datetime
from sqlalchemy.orm import Session

from wakedock.core.database import get_db
from wakedock.core.auth_service import get_auth_service
from wakedock.models.user import User, Role, Permission, UserRole, RolePermission
from wakedock.core.logging import logger


def create_default_permissions(db: Session) -> dict:
    """
    Crée les permissions par défaut du système
    """
    permissions = [
        # Containers
        {"name": "containers:read", "description": "Voir les containers", "category": "containers"},
        {"name": "containers:create", "description": "Créer des containers", "category": "containers"},
        {"name": "containers:update", "description": "Modifier des containers", "category": "containers"},
        {"name": "containers:delete", "description": "Supprimer des containers", "category": "containers"},
        {"name": "containers:start", "description": "Démarrer des containers", "category": "containers"},
        {"name": "containers:stop", "description": "Arrêter des containers", "category": "containers"},
        {"name": "containers:restart", "description": "Redémarrer des containers", "category": "containers"},
        {"name": "containers:logs", "description": "Voir les logs des containers", "category": "containers"},
        
        # Services
        {"name": "services:read", "description": "Voir les services", "category": "services"},
        {"name": "services:create", "description": "Créer des services", "category": "services"},
        {"name": "services:update", "description": "Modifier des services", "category": "services"},
        {"name": "services:delete", "description": "Supprimer des services", "category": "services"},
        {"name": "services:deploy", "description": "Déployer des services", "category": "services"},
        
        # Images
        {"name": "images:read", "description": "Voir les images", "category": "images"},
        {"name": "images:create", "description": "Créer/Build des images", "category": "images"},
        {"name": "images:delete", "description": "Supprimer des images", "category": "images"},
        {"name": "images:pull", "description": "Télécharger des images", "category": "images"},
        {"name": "images:push", "description": "Publier des images", "category": "images"},
        
        # Monitoring
        {"name": "monitoring:read", "description": "Voir les métriques", "category": "monitoring"},
        {"name": "monitoring:configure", "description": "Configurer le monitoring", "category": "monitoring"},
        {"name": "monitoring:alerts", "description": "Gérer les alertes", "category": "monitoring"},
        
        # Logs
        {"name": "logs:read", "description": "Voir les logs", "category": "logs"},
        {"name": "logs:export", "description": "Exporter les logs", "category": "logs"},
        {"name": "logs:configure", "description": "Configurer les logs", "category": "logs"},
        
        # System
        {"name": "system:read", "description": "Voir les infos système", "category": "system"},
        {"name": "system:configure", "description": "Configurer le système", "category": "system"},
        {"name": "system:maintenance", "description": "Maintenance système", "category": "system"},
        
        # Users & Roles
        {"name": "users:read", "description": "Voir les utilisateurs", "category": "users"},
        {"name": "users:create", "description": "Créer des utilisateurs", "category": "users"},
        {"name": "users:update", "description": "Modifier des utilisateurs", "category": "users"},
        {"name": "users:delete", "description": "Supprimer des utilisateurs", "category": "users"},
        {"name": "roles:read", "description": "Voir les rôles", "category": "users"},
        {"name": "roles:create", "description": "Créer des rôles", "category": "users"},
        {"name": "roles:update", "description": "Modifier des rôles", "category": "users"},
        {"name": "roles:delete", "description": "Supprimer des rôles", "category": "users"},
        
        # Audit
        {"name": "audit:read", "description": "Voir les logs d'audit", "category": "audit"},
        {"name": "audit:export", "description": "Exporter les logs d'audit", "category": "audit"},
    ]
    
    created_permissions = {}
    
    for perm_data in permissions:
        # Vérifier si la permission existe déjà
        existing_perm = db.query(Permission).filter(Permission.name == perm_data["name"]).first()
        
        if not existing_perm:
            permission = Permission(**perm_data)
            db.add(permission)
            db.flush()  # Pour obtenir l'ID
            created_permissions[perm_data["name"]] = permission
            logger.info(f"Permission créée: {perm_data['name']}")
        else:
            created_permissions[perm_data["name"]] = existing_perm
    
    db.commit()
    return created_permissions


def create_default_roles(db: Session, permissions: dict) -> dict:
    """
    Crée les rôles par défaut du système
    """
    roles_config = [
        {
            "name": "admin",
            "description": "Administrateur système avec tous les droits",
            "is_system_role": True,
            "permissions": list(permissions.keys())  # Toutes les permissions
        },
        {
            "name": "developer",
            "description": "Développeur avec droits de gestion des containers et services",
            "is_system_role": True,
            "permissions": [
                # Containers
                "containers:read", "containers:create", "containers:update", "containers:delete",
                "containers:start", "containers:stop", "containers:restart", "containers:logs",
                # Services
                "services:read", "services:create", "services:update", "services:delete", "services:deploy",
                # Images
                "images:read", "images:create", "images:delete", "images:pull", "images:push",
                # Monitoring et Logs
                "monitoring:read", "logs:read", "logs:export",
                # System (lecture seule)
                "system:read"
            ]
        },
        {
            "name": "viewer",
            "description": "Utilisateur en lecture seule",
            "is_system_role": True,
            "permissions": [
                "containers:read", "containers:logs",
                "services:read",
                "images:read",
                "monitoring:read",
                "logs:read",
                "system:read"
            ]
        },
        {
            "name": "operator",
            "description": "Opérateur avec droits de gestion des containers",
            "is_system_role": True,
            "permissions": [
                # Containers
                "containers:read", "containers:start", "containers:stop", "containers:restart", "containers:logs",
                # Services
                "services:read", "services:deploy",
                # Images
                "images:read", "images:pull",
                # Monitoring et Logs
                "monitoring:read", "monitoring:alerts",
                "logs:read", "logs:export",
                # System
                "system:read"
            ]
        }
    ]
    
    created_roles = {}
    
    for role_config in roles_config:
        # Vérifier si le rôle existe déjà
        existing_role = db.query(Role).filter(Role.name == role_config["name"]).first()
        
        if not existing_role:
            # Créer le rôle
            role = Role(
                name=role_config["name"],
                description=role_config["description"],
                is_system_role=role_config["is_system_role"]
            )
            db.add(role)
            db.flush()
            
            # Ajouter les permissions
            for perm_name in role_config["permissions"]:
                if perm_name in permissions:
                    role_permission = RolePermission(
                        role_id=role.id,
                        permission_id=permissions[perm_name].id
                    )
                    db.add(role_permission)
            
            created_roles[role_config["name"]] = role
            logger.info(f"Rôle créé: {role_config['name']} avec {len(role_config['permissions'])} permissions")
        else:
            created_roles[role_config["name"]] = existing_role
    
    db.commit()
    return created_roles


def create_admin_user(db: Session, roles: dict):
    """
    Crée l'utilisateur administrateur par défaut
    """
    auth_service = get_auth_service()
    
    # Vérifier si l'admin existe déjà
    existing_admin = db.query(User).filter(User.username == "admin").first()
    
    if not existing_admin:
        # Créer l'utilisateur admin
        admin_user = User(
            username="admin",
            email="admin@wakedock.local",
            full_name="Administrateur WakeDock",
            hashed_password=auth_service.hash_password("admin123"),  # Mot de passe temporaire
            is_active=True,
            is_superuser=True,
            is_verified=True,
            theme_preference="dark",
            language_preference="fr"
        )
        
        db.add(admin_user)
        db.flush()
        
        # Assigner le rôle admin
        if "admin" in roles:
            user_role = UserRole(
                user_id=admin_user.id,
                role_id=roles["admin"].id
            )
            db.add(user_role)
        
        db.commit()
        
        logger.warning("Utilisateur admin créé avec mot de passe temporaire 'admin123'")
        logger.warning("CHANGEZ IMMÉDIATEMENT CE MOT DE PASSE EN PRODUCTION!")
        
        return admin_user
    else:
        logger.info("Utilisateur admin existe déjà")
        return existing_admin


def initialize_auth_system():
    """
    Initialise le système d'authentification avec les données par défaut
    """
    logger.info("Initialisation du système d'authentification...")
    
    # Obtenir une session de base de données
    db = next(get_db())
    
    try:
        # 1. Créer les permissions par défaut
        logger.info("Création des permissions par défaut...")
        permissions = create_default_permissions(db)
        
        # 2. Créer les rôles par défaut
        logger.info("Création des rôles par défaut...")
        roles = create_default_roles(db, permissions)
        
        # 3. Créer l'utilisateur admin
        logger.info("Création de l'utilisateur administrateur...")
        admin_user = create_admin_user(db, roles)
        
        logger.info("Système d'authentification initialisé avec succès!")
        logger.info(f"Permissions créées: {len(permissions)}")
        logger.info(f"Rôles créés: {len(roles)}")
        logger.info(f"Utilisateur admin: {admin_user.username}")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    initialize_auth_system()
