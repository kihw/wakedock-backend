"""
Service de gestion des profils utilisateur et préférences
Extension du système d'authentification pour la personnalisation
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from wakedock.logging import get_logger
from wakedock.models.user import AuditLog, User

logger = get_logger(__name__)


class UserProfileService:
    """
    Service de gestion des profils utilisateur et préférences
    """
    
    def __init__(self):
        self.supported_themes = ["light", "dark", "auto", "high-contrast"]
        self.supported_languages = ["fr", "en", "es", "de", "it"]
        self.supported_timezones = [
            "UTC", "Europe/Paris", "Europe/London", "America/New_York", 
            "America/Los_Angeles", "Asia/Tokyo", "Asia/Shanghai", "Australia/Sydney"
        ]
        
        logger.info("UserProfileService initialisé")
    
    def get_user_profile(self, user_id: int, db: Session) -> Optional[Dict[str, Any]]:
        """
        Récupère le profil complet d'un utilisateur
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return None
            
            # Récupérer les permissions
            permissions = user.get_permissions()
            
            # Récupérer les statistiques d'activité récente
            activity_stats = self._get_activity_stats(user_id, db)
            
            profile = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "is_verified": user.is_verified,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "last_login": user.last_login,
                "password_changed_at": user.password_changed_at,
                
                # Préférences
                "preferences": {
                    "theme": user.theme_preference,
                    "language": user.language_preference,
                    "timezone": user.timezone
                },
                
                # Sécurité
                "security": {
                    "failed_login_attempts": user.failed_login_attempts,
                    "is_locked": user.is_locked,
                    "account_locked_until": user.account_locked_until,
                    "password_age_days": (datetime.utcnow() - user.password_changed_at).days if user.password_changed_at else None
                },
                
                # Permissions et rôles
                "permissions": permissions,
                "roles": [{"id": ur.role.id, "name": ur.role.name, "description": ur.role.description} 
                         for ur in user.roles if ur.role.is_active],
                
                # Statistiques d'activité
                "activity": activity_stats
            }
            
            logger.debug(f"Profil récupéré pour l'utilisateur {user.username}")
            return profile
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du profil {user_id}: {e}")
            return None
    
    def update_user_profile(self, user_id: int, profile_data: Dict[str, Any], db: Session) -> bool:
        """
        Met à jour le profil d'un utilisateur
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                logger.warning(f"Utilisateur {user_id} non trouvé pour mise à jour du profil")
                return False
            
            # Sauvegarder les anciennes valeurs pour l'audit
            old_values = {
                "full_name": user.full_name,
                "email": user.email,
                "theme_preference": user.theme_preference,
                "language_preference": user.language_preference,
                "timezone": user.timezone
            }
            
            # Mettre à jour les champs autorisés
            updated_fields = []
            
            if "full_name" in profile_data:
                user.full_name = profile_data["full_name"]
                updated_fields.append("full_name")
            
            if "email" in profile_data:
                # Vérifier que l'email n'existe pas déjà
                existing_user = db.query(User).filter(
                    User.email == profile_data["email"], 
                    User.id != user_id
                ).first()
                
                if existing_user:
                    logger.warning(f"Tentative d'utilisation d'un email déjà existant: {profile_data['email']}")
                    return False
                
                user.email = profile_data["email"]
                user.is_verified = False  # Re-vérification nécessaire
                updated_fields.append("email")
            
            # Mettre à jour les préférences
            if "preferences" in profile_data:
                prefs = profile_data["preferences"]
                
                if "theme" in prefs and prefs["theme"] in self.supported_themes:
                    user.theme_preference = prefs["theme"]
                    updated_fields.append("theme")
                
                if "language" in prefs and prefs["language"] in self.supported_languages:
                    user.language_preference = prefs["language"]
                    updated_fields.append("language")
                
                if "timezone" in prefs and prefs["timezone"] in self.supported_timezones:
                    user.timezone = prefs["timezone"]
                    updated_fields.append("timezone")
            
            user.updated_at = datetime.utcnow()
            db.commit()
            
            # Créer un log d'audit
            self._log_profile_update(user, updated_fields, old_values, db)
            
            logger.info(f"Profil mis à jour pour l'utilisateur {user.username}: {updated_fields}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du profil {user_id}: {e}")
            db.rollback()
            return False
    
    def update_user_preferences(self, user_id: int, preferences: Dict[str, Any], db: Session) -> bool:
        """
        Met à jour uniquement les préférences d'un utilisateur
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return False
            
            updated = False
            
            if "theme" in preferences and preferences["theme"] in self.supported_themes:
                user.theme_preference = preferences["theme"]
                updated = True
            
            if "language" in preferences and preferences["language"] in self.supported_languages:
                user.language_preference = preferences["language"]
                updated = True
            
            if "timezone" in preferences and preferences["timezone"] in self.supported_timezones:
                user.timezone = preferences["timezone"]
                updated = True
            
            if updated:
                user.updated_at = datetime.utcnow()
                db.commit()
                
                logger.info(f"Préférences mises à jour pour l'utilisateur {user.username}")
            
            return updated
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des préférences {user_id}: {e}")
            db.rollback()
            return False
    
    def get_user_activity_history(self, user_id: int, db: Session, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Récupère l'historique d'activité d'un utilisateur
        """
        try:
            activities = db.query(AuditLog).filter(
                AuditLog.user_id == user_id
            ).order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()
            
            activity_list = []
            for activity in activities:
                activity_list.append({
                    "id": activity.id,
                    "action": activity.action,
                    "resource_type": activity.resource_type,
                    "resource_id": activity.resource_id,
                    "details": activity.details,
                    "ip_address": activity.ip_address,
                    "user_agent": activity.user_agent,
                    "success": activity.success,
                    "error_message": activity.error_message,
                    "created_at": activity.created_at
                })
            
            return activity_list
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'historique {user_id}: {e}")
            return []
    
    def get_user_security_info(self, user_id: int, db: Session) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations de sécurité d'un utilisateur
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return None
            
            # Statistiques de sécurité récentes
            recent_activities = db.query(AuditLog).filter(
                AuditLog.user_id == user_id,
                AuditLog.created_at >= datetime.utcnow() - timedelta(days=30)
            ).count()
            
            failed_logins_recent = db.query(AuditLog).filter(
                AuditLog.user_id == user_id,
                AuditLog.action == "login_failed",
                AuditLog.created_at >= datetime.utcnow() - timedelta(days=7)
            ).count()
            
            security_info = {
                "password_age_days": (datetime.utcnow() - user.password_changed_at).days if user.password_changed_at else None,
                "failed_login_attempts": user.failed_login_attempts,
                "is_account_locked": user.is_locked,
                "account_locked_until": user.account_locked_until,
                "is_verified": user.is_verified,
                "recent_activities_count": recent_activities,
                "failed_logins_week": failed_logins_recent,
                "last_login": user.last_login,
                "created_at": user.created_at
            }
            
            return security_info
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des infos de sécurité {user_id}: {e}")
            return None
    
    def validate_profile_data(self, profile_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Valide les données de profil utilisateur
        """
        errors = {}
        
        # Validation de l'email
        if "email" in profile_data:
            email = profile_data["email"]
            if not email or "@" not in email:
                errors.setdefault("email", []).append("Format d'email invalide")
            elif len(email) > 255:
                errors.setdefault("email", []).append("Email trop long (max 255 caractères)")
        
        # Validation du nom complet
        if "full_name" in profile_data:
            full_name = profile_data["full_name"]
            if full_name and len(full_name) > 255:
                errors.setdefault("full_name", []).append("Nom trop long (max 255 caractères)")
        
        # Validation des préférences
        if "preferences" in profile_data:
            prefs = profile_data["preferences"]
            
            if "theme" in prefs and prefs["theme"] not in self.supported_themes:
                errors.setdefault("theme", []).append(f"Thème non supporté. Options: {self.supported_themes}")
            
            if "language" in prefs and prefs["language"] not in self.supported_languages:
                errors.setdefault("language", []).append(f"Langue non supportée. Options: {self.supported_languages}")
            
            if "timezone" in prefs and prefs["timezone"] not in self.supported_timezones:
                errors.setdefault("timezone", []).append(f"Fuseau horaire non supporté. Options: {self.supported_timezones}")
        
        return errors
    
    def get_available_preferences(self) -> Dict[str, List[str]]:
        """
        Retourne les options disponibles pour les préférences
        """
        return {
            "themes": self.supported_themes,
            "languages": self.supported_languages,
            "timezones": self.supported_timezones
        }
    
    def _get_activity_stats(self, user_id: int, db: Session) -> Dict[str, Any]:
        """
        Calcule les statistiques d'activité d'un utilisateur
        """
        try:
            # Activités des 30 derniers jours
            recent_activities = db.query(AuditLog).filter(
                AuditLog.user_id == user_id,
                AuditLog.created_at >= datetime.utcnow() - timedelta(days=30)
            ).count()
            
            # Dernière activité
            last_activity = db.query(AuditLog).filter(
                AuditLog.user_id == user_id
            ).order_by(desc(AuditLog.created_at)).first()
            
            # Activités par type
            login_count = db.query(AuditLog).filter(
                AuditLog.user_id == user_id,
                AuditLog.action == "login",
                AuditLog.created_at >= datetime.utcnow() - timedelta(days=30)
            ).count()
            
            return {
                "recent_activities": recent_activities,
                "last_activity": last_activity.created_at if last_activity else None,
                "last_activity_action": last_activity.action if last_activity else None,
                "login_count_month": login_count
            }
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul des statistiques d'activité {user_id}: {e}")
            return {}
    
    def _log_profile_update(self, user: User, updated_fields: List[str], old_values: Dict[str, Any], db: Session):
        """
        Enregistre la mise à jour du profil dans les logs d'audit
        """
        try:
            details = {
                "updated_fields": updated_fields,
                "old_values": {field: old_values.get(field) for field in updated_fields}
            }
            
            audit_log = AuditLog(
                user_id=user.id,
                action="profile_updated",
                details=str(details),
                success=True
            )
            
            db.add(audit_log)
            db.commit()
            
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de l'audit de mise à jour du profil: {e}")


# Instance globale du service
_user_profile_service: UserProfileService = None

def get_user_profile_service() -> UserProfileService:
    """
    Dépendance FastAPI pour obtenir le service de profils utilisateur
    """
    global _user_profile_service
    
    if _user_profile_service is None:
        _user_profile_service = UserProfileService()
    
    return _user_profile_service
