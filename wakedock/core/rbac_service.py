"""
Service de gestion des rôles et permissions (RBAC)
Implémentation avancée pour la version 0.3.3
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from wakedock.core.database import get_database
from wakedock.models.user import (
    AuditLog,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)


class RBACService:
    """
    Service complet de gestion des rôles et permissions
    """
    
    def __init__(self):
        """Initialise le service RBAC"""
        self.logger = logger
        
        # Définition des rôles système par défaut
        self.default_roles = {
            "admin": {
                "description": "Administrateur avec tous les droits",
                "is_system_role": True,
                "permissions": [
                    # Système
                    "system.admin", "system.read", "system.write",
                    "system.config", "system.backup", "system.restore",
                    
                    # Utilisateurs
                    "users.create", "users.read", "users.update", "users.delete",
                    "users.manage_roles", "users.reset_password",
                    
                    # Conteneurs
                    "containers.create", "containers.read", "containers.update", "containers.delete",
                    "containers.start", "containers.stop", "containers.restart", "containers.logs",
                    "containers.exec", "containers.inspect", "containers.stats",
                    
                    # Images
                    "images.create", "images.read", "images.delete", "images.pull", "images.push",
                    
                    # Réseaux
                    "networks.create", "networks.read", "networks.delete",
                    
                    # Volumes
                    "volumes.create", "volumes.read", "volumes.delete",
                    
                    # Monitoring
                    "monitoring.read", "monitoring.configure", "monitoring.alerts",
                    
                    # Logs
                    "logs.read", "logs.export", "logs.configure",
                    
                    # Audit
                    "audit.read", "audit.export",
                    
                    # CI/CD
                    "cicd.create", "cicd.read", "cicd.update", "cicd.delete",
                    "cicd.execute", "cicd.configure",
                    
                    # Auto Deployment
                    "auto_deployment.create", "auto_deployment.read", "auto_deployment.update", "auto_deployment.delete",
                    "auto_deployment.trigger", "auto_deployment.rollback",
                    
                    # Docker Swarm
                    "swarm.cluster.create", "swarm.cluster.read", "swarm.cluster.update", "swarm.cluster.delete",
                    "swarm.node.create", "swarm.node.read", "swarm.node.update", "swarm.node.delete", "swarm.node.leave",
                    "swarm.service.create", "swarm.service.read", "swarm.service.update", "swarm.service.delete",
                    "swarm.service.scale", "swarm.service.rollback",
                    "swarm.network.create", "swarm.network.read", "swarm.network.delete",
                    "swarm.secret.create", "swarm.secret.read", "swarm.secret.update", "swarm.secret.delete",
                    "swarm.config.create", "swarm.config.read", "swarm.config.update", "swarm.config.delete",
                    "swarm.stack.deploy", "swarm.stack.read", "swarm.stack.update", "swarm.stack.remove",
                    "swarm.load_balancer.create", "swarm.load_balancer.read", "swarm.load_balancer.update", "swarm.load_balancer.delete",
                    
                    # Environnements (gestion complète)
                    "environments.create", "environments.read", "environments.update", "environments.delete",
                    "environments.variables.read", "environments.variables.update",
                    "environments.health.read", "environments.health.check",
                    "environments.deploy", "environments.promote.dev", "environments.promote.staging", 
                    "environments.promote.production", "environments.promotion.approve"
                ]
            },
            "developer": {
                "description": "Développeur avec droits de déploiement",
                "is_system_role": True,
                "permissions": [
                    # Conteneurs (lecture et gestion limitée)
                    "containers.create", "containers.read", "containers.update",
                    "containers.start", "containers.stop", "containers.restart", "containers.logs",
                    "containers.inspect", "containers.stats",
                    
                    # Images
                    "images.create", "images.read", "images.pull", "images.push",
                    
                    # Réseaux (lecture)
                    "networks.read",
                    
                    # Volumes (lecture et création)
                    "volumes.create", "volumes.read",
                    
                    # Monitoring
                    "monitoring.read",
                    
                    # Logs
                    "logs.read", "logs.export",
                    
                    # Environnements (développeur - dev/staging uniquement)
                    "environments.create", "environments.read", "environments.update",
                    "environments.variables.read", "environments.variables.update",
                    "environments.health.read", "environments.deploy",
                    "environments.promote.dev", "environments.promote.staging",
                    
                    # Profile
                    "profile.read", "profile.update"
                ]
            },
            "operator": {
                "description": "Opérateur avec droits de monitoring",
                "is_system_role": True,
                "permissions": [
                    # Conteneurs (lecture et actions de base)
                    "containers.read", "containers.start", "containers.stop", 
                    "containers.restart", "containers.logs", "containers.stats",
                    
                    # Images (lecture)
                    "images.read",
                    
                    # Réseaux (lecture)
                    "networks.read",
                    
                    # Volumes (lecture)
                    "volumes.read",
                    
                    # Monitoring
                    "monitoring.read", "monitoring.alerts",
                    
                    # Logs
                    "logs.read", "logs.export",
                    
                    # Environnements (opérateur - déploiement et promotion)
                    "environments.read", "environments.deploy", 
                    "environments.promote.dev", "environments.promote.staging",
                    "environments.health.read", "environments.health.check",
                    
                    # Profile
                    "profile.read", "profile.update"
                ]
            },
            "viewer": {
                "description": "Visualisateur avec droits de lecture seule",
                "is_system_role": True,
                "permissions": [
                    # Conteneurs (lecture seule)
                    "containers.read", "containers.logs", "containers.stats",
                    
                    # Images (lecture)
                    "images.read",
                    
                    # Réseaux (lecture)
                    "networks.read",
                    
                    # Volumes (lecture)
                    "volumes.read",
                    
                    # Monitoring (lecture)
                    "monitoring.read",
                    
                    # Logs (lecture)
                    "logs.read",
                    
                    # Environnements (lecture)
                    "environments.read", "environments.health.read",
                    
                    # Profile
                    "profile.read", "profile.update"
                ]
            }
        }
        
        # Catégories de permissions pour l'organisation
        self.permission_categories = {
            "system": "Administration système",
            "users": "Gestion des utilisateurs",
            "containers": "Gestion des conteneurs",
            "images": "Gestion des images",
            "networks": "Gestion des réseaux",
            "volumes": "Gestion des volumes",
            "monitoring": "Surveillance et métriques",
            "logs": "Gestion des logs",
            "audit": "Audit et sécurité",
            "profile": "Gestion du profil",
            "environments": "Gestion des environnements"
        }

    async def initialize_default_roles_and_permissions(self) -> None:
        """
        Initialise les rôles et permissions par défaut au démarrage
        """
        try:
            db = next(get_database())
            
            # Créer toutes les permissions
            await self._create_default_permissions(db)
            
            # Créer les rôles par défaut
            for role_name, role_data in self.default_roles.items():
                await self._create_or_update_role(db, role_name, role_data)
            
            db.commit()
            self.logger.info("Rôles et permissions par défaut initialisés avec succès")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation RBAC: {e}")
            db.rollback()
        finally:
            db.close()

    async def _create_default_permissions(self, db: Session) -> None:
        """Crée toutes les permissions par défaut"""
        all_permissions = set()
        
        # Collecter toutes les permissions de tous les rôles
        for role_data in self.default_roles.values():
            all_permissions.update(role_data["permissions"])
        
        # Créer chaque permission si elle n'existe pas
        for perm_name in all_permissions:
            existing_perm = db.query(Permission).filter(Permission.name == perm_name).first()
            
            if not existing_perm:
                # Extraire la catégorie du nom de permission
                category = perm_name.split('.')[0] if '.' in perm_name else 'general'
                
                permission = Permission(
                    name=perm_name,
                    description=self._generate_permission_description(perm_name),
                    category=category,
                    is_active=True
                )
                
                db.add(permission)
                self.logger.debug(f"Permission créée: {perm_name}")

    async def _create_or_update_role(self, db: Session, role_name: str, role_data: Dict) -> None:
        """Crée ou met à jour un rôle avec ses permissions"""
        # Chercher le rôle existant
        role = db.query(Role).filter(Role.name == role_name).first()
        
        if not role:
            # Créer nouveau rôle
            role = Role(
                name=role_name,
                description=role_data["description"],
                is_system_role=role_data.get("is_system_role", False),
                is_active=True
            )
            db.add(role)
            db.flush()  # Pour obtenir l'ID
            self.logger.info(f"Rôle créé: {role_name}")
        else:
            # Mettre à jour si nécessaire
            role.description = role_data["description"]
            role.is_system_role = role_data.get("is_system_role", False)
            self.logger.debug(f"Rôle mis à jour: {role_name}")
        
        # Gérer les permissions du rôle
        await self._assign_permissions_to_role(db, role, role_data["permissions"])

    async def _assign_permissions_to_role(self, db: Session, role: Role, permission_names: List[str]) -> None:
        """Assigne les permissions à un rôle"""
        # Supprimer les anciennes associations
        db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
        
        # Ajouter les nouvelles permissions
        for perm_name in permission_names:
            permission = db.query(Permission).filter(Permission.name == perm_name).first()
            
            if permission:
                role_perm = RolePermission(
                    role_id=role.id,
                    permission_id=permission.id,
                    assigned_at=datetime.utcnow()
                )
                db.add(role_perm)

    def _generate_permission_description(self, perm_name: str) -> str:
        """Génère une description pour une permission"""
        parts = perm_name.split('.')
        if len(parts) >= 2:
            category, action = parts[0], parts[1]
            
            action_labels = {
                'create': 'Créer',
                'read': 'Lire',
                'update': 'Modifier',
                'delete': 'Supprimer',
                'start': 'Démarrer',
                'stop': 'Arrêter',
                'restart': 'Redémarrer',
                'logs': 'Consulter les logs',
                'exec': 'Exécuter des commandes',
                'inspect': 'Inspecter',
                'stats': 'Voir les statistiques',
                'pull': 'Télécharger',
                'push': 'Publier',
                'configure': 'Configurer',
                'alerts': 'Gérer les alertes',
                'export': 'Exporter',
                'admin': 'Administration complète',
                'manage_roles': 'Gérer les rôles',
                'reset_password': 'Réinitialiser les mots de passe',
                'backup': 'Sauvegarder',
                'restore': 'Restaurer'
            }
            
            category_labels = self.permission_categories.get(category, category)
            action_label = action_labels.get(action, action)
            
            return f"{action_label} - {category_labels}"
        
        return perm_name

    # ========== Gestion des Utilisateurs et Rôles ==========

    async def assign_role_to_user(self, user_id: int, role_id: int, assigned_by_id: Optional[int] = None, 
                                 expires_at: Optional[datetime] = None) -> bool:
        """
        Assigne un rôle à un utilisateur
        """
        try:
            db = next(get_database())
            
            # Vérifier que l'utilisateur et le rôle existent
            user = db.query(User).filter(User.id == user_id).first()
            role = db.query(Role).filter(Role.id == role_id, Role.is_active == True).first()
            
            if not user or not role:
                return False
            
            # Vérifier si l'association existe déjà
            existing = db.query(UserRole).filter(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id
            ).first()
            
            if existing:
                # Mettre à jour la date d'expiration si fournie
                if expires_at:
                    existing.expires_at = expires_at
                    db.commit()
                return True
            
            # Créer nouvelle association
            user_role = UserRole(
                user_id=user_id,
                role_id=role_id,
                assigned_by=assigned_by_id,
                expires_at=expires_at,
                assigned_at=datetime.utcnow()
            )
            
            db.add(user_role)
            db.commit()
            
            # Audit log
            await self._log_audit_action(
                db, assigned_by_id, "assign_role",
                f"Rôle {role.name} assigné à l'utilisateur {user.username}",
                resource_type="user_role",
                resource_id=f"{user_id}:{role_id}",
                success=True
            )
            
            self.logger.info(f"Rôle {role.name} assigné à l'utilisateur {user.username}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'assignation du rôle: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    async def remove_role_from_user(self, user_id: int, role_id: int, removed_by_id: Optional[int] = None) -> bool:
        """
        Retire un rôle d'un utilisateur
        """
        try:
            db = next(get_database())
            
            # Chercher l'association
            user_role = db.query(UserRole).filter(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id
            ).first()
            
            if not user_role:
                return False
            
            # Récupérer les infos pour l'audit
            user = db.query(User).filter(User.id == user_id).first()
            role = db.query(Role).filter(Role.id == role_id).first()
            
            # Supprimer l'association
            db.delete(user_role)
            db.commit()
            
            # Audit log
            await self._log_audit_action(
                db, removed_by_id, "remove_role",
                f"Rôle {role.name} retiré de l'utilisateur {user.username}",
                resource_type="user_role",
                resource_id=f"{user_id}:{role_id}",
                success=True
            )
            
            self.logger.info(f"Rôle {role.name} retiré de l'utilisateur {user.username}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la suppression du rôle: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    async def get_user_permissions(self, user_id: int) -> List[str]:
        """
        Récupère toutes les permissions effectives d'un utilisateur
        """
        try:
            db = next(get_database())
            
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return []
            
            return user.get_permissions()
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des permissions: {e}")
            return []
        finally:
            db.close()

    async def check_user_permission(self, user_id: int, permission: str) -> bool:
        """
        Vérifie si un utilisateur a une permission spécifique
        """
        permissions = await self.get_user_permissions(user_id)
        
        # Vérification directe
        if permission in permissions:
            return True
        
        # Vérification des permissions admin (wildcard)
        if "system.admin" in permissions:
            return True
        
        # Vérification des permissions par catégorie
        if '.' in permission:
            category = permission.split('.')[0]
            if f"{category}.admin" in permissions:
                return True
        
        return False

    # ========== Gestion des Rôles ==========

    async def create_role(self, name: str, description: str, permissions: List[str], 
                         created_by_id: Optional[int] = None) -> Optional[Role]:
        """
        Crée un nouveau rôle personnalisé
        """
        try:
            db = next(get_database())
            
            # Vérifier que le nom n'existe pas déjà
            existing = db.query(Role).filter(Role.name == name).first()
            if existing:
                return None
            
            # Créer le rôle
            role = Role(
                name=name,
                description=description,
                is_system_role=False,
                is_active=True,
                created_at=datetime.utcnow()
            )
            
            db.add(role)
            db.flush()  # Pour obtenir l'ID
            
            # Assigner les permissions
            await self._assign_permissions_to_role(db, role, permissions)
            
            db.commit()
            
            # Audit log
            await self._log_audit_action(
                db, created_by_id, "create_role",
                f"Rôle {name} créé avec {len(permissions)} permissions",
                resource_type="role",
                resource_id=str(role.id),
                success=True
            )
            
            self.logger.info(f"Rôle créé: {name}")
            return role
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la création du rôle: {e}")
            db.rollback()
            return None
        finally:
            db.close()

    async def get_all_roles(self) -> List[Dict[str, Any]]:
        """
        Récupère tous les rôles avec leurs permissions
        """
        try:
            db = next(get_database())
            
            roles = db.query(Role).filter(Role.is_active == True).all()
            
            result = []
            for role in roles:
                permissions = [rp.permission.name for rp in role.permissions if rp.permission.is_active]
                user_count = db.query(UserRole).filter(UserRole.role_id == role.id).count()
                
                result.append({
                    "id": role.id,
                    "name": role.name,
                    "description": role.description,
                    "is_system_role": role.is_system_role,
                    "permissions": permissions,
                    "user_count": user_count,
                    "created_at": role.created_at.isoformat(),
                    "updated_at": role.updated_at.isoformat()
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des rôles: {e}")
            return []
        finally:
            db.close()

    async def get_all_permissions(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Récupère toutes les permissions organisées par catégorie
        """
        try:
            db = next(get_database())
            
            permissions = db.query(Permission).filter(Permission.is_active == True).all()
            
            result = {}
            for perm in permissions:
                category = perm.category
                if category not in result:
                    result[category] = []
                
                result[category].append({
                    "id": perm.id,
                    "name": perm.name,
                    "description": perm.description,
                    "module": perm.module
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des permissions: {e}")
            return {}
        finally:
            db.close()

    # ========== Audit et Logs ==========

    async def _log_audit_action(self, db: Session, user_id: Optional[int], action: str, 
                               details: str, resource_type: Optional[str] = None,
                               resource_id: Optional[str] = None, success: bool = True,
                               error_message: Optional[str] = None, ip_address: Optional[str] = None,
                               user_agent: Optional[str] = None) -> None:
        """
        Enregistre une action d'audit
        """
        try:
            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                success=success,
                error_message=error_message,
                ip_address=ip_address,
                user_agent=user_agent,
                created_at=datetime.utcnow()
            )
            
            db.add(audit_log)
            # Pas de commit ici car cette méthode est appelée dans d'autres transactions
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enregistrement de l'audit: {e}")

    async def get_audit_logs(self, user_id: Optional[int] = None, action: Optional[str] = None,
                           start_date: Optional[datetime] = None, end_date: Optional[datetime] = None,
                           page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """
        Récupère les logs d'audit avec filtres et pagination
        """
        try:
            db = next(get_database())
            
            # Construire la requête
            query = db.query(AuditLog)
            
            # Filtres
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            
            if action:
                query = query.filter(AuditLog.action == action)
            
            if start_date:
                query = query.filter(AuditLog.created_at >= start_date)
            
            if end_date:
                query = query.filter(AuditLog.created_at <= end_date)
            
            # Tri par date décroissante
            query = query.order_by(AuditLog.created_at.desc())
            
            # Pagination
            total = query.count()
            offset = (page - 1) * per_page
            logs = query.offset(offset).limit(per_page).all()
            
            # Formater les résultats
            result_logs = []
            for log in logs:
                result_logs.append({
                    "id": log.id,
                    "user_id": log.user_id,
                    "username": log.user.username if log.user else None,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "details": log.details,
                    "success": log.success,
                    "error_message": log.error_message,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "created_at": log.created_at.isoformat()
                })
            
            return {
                "logs": result_logs,
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page
            }
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des logs d'audit: {e}")
            return {"logs": [], "total": 0, "page": page, "per_page": per_page, "pages": 0}
        finally:
            db.close()

    # ========== Cleanup et Maintenance ==========

    async def cleanup_expired_role_assignments(self) -> int:
        """
        Nettoie les assignations de rôles expirées
        """
        try:
            db = next(get_database())
            
            expired_assignments = db.query(UserRole).filter(
                UserRole.expires_at != None,
                UserRole.expires_at < datetime.utcnow()
            ).all()
            
            count = len(expired_assignments)
            
            for assignment in expired_assignments:
                db.delete(assignment)
            
            db.commit()
            
            if count > 0:
                self.logger.info(f"Suppression de {count} assignations de rôles expirées")
            
            return count
            
        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage des rôles expirés: {e}")
            db.rollback()
            return 0
        finally:
            db.close()


# Instance globale du service
_rbac_service: Optional[RBACService] = None

def get_rbac_service() -> RBACService:
    """
    Récupère l'instance du service RBAC
    """
    global _rbac_service
    
    if _rbac_service is None:
        _rbac_service = RBACService()
    
    return _rbac_service
