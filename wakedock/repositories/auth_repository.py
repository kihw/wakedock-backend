"""
Authentication repository for user management
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import bcrypt
import jwt
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from wakedock.repositories.base_repository import BaseRepository
from wakedock.models.auth import User, Role, Permission, UserSession
from wakedock.core.logging import get_logger
from wakedock.core.exceptions import WakeDockException

logger = get_logger(__name__)


class AuthRepository(BaseRepository[User]):
    """Repository for authentication operations"""
    
    def __init__(self, db_session):
        super().__init__(User, db_session)
        self.jwt_secret = "your-secret-key"  # Should be from config
        self.jwt_algorithm = "HS256"
        self.token_expire_hours = 24
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password"""
        try:
            # Get user with roles and permissions
            stmt = (
                select(User)
                .options(
                    selectinload(User.roles).selectinload(Role.permissions)
                )
                .where(
                    and_(
                        User.username == username,
                        User.is_active == True
                    )
                )
            )
            
            result = await self.db_session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"Authentication failed: User '{username}' not found")
                return None
            
            # Check password
            if not self._verify_password(password, user.password_hash):
                logger.warning(f"Authentication failed: Invalid password for user '{username}'")
                return None
            
            # Update last login
            user.last_login = datetime.utcnow()
            await self.db_session.commit()
            
            logger.info(f"User '{username}' authenticated successfully")
            return user
            
        except Exception as e:
            logger.error(f"Error authenticating user '{username}': {str(e)}")
            await self.db_session.rollback()
            return None
    
    async def create_user(self, username: str, email: str, password: str, 
                         first_name: str = None, last_name: str = None,
                         roles: List[str] = None) -> User:
        """Create new user"""
        try:
            # Check if user already exists
            existing_user = await self.get_by_username(username)
            if existing_user:
                raise WakeDockException(f"User '{username}' already exists")
            
            # Check if email already exists
            existing_email = await self.get_by_email(email)
            if existing_email:
                raise WakeDockException(f"Email '{email}' already exists")
            
            # Hash password
            password_hash = self._hash_password(password)
            
            # Create user
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                created_at=datetime.utcnow()
            )
            
            # Add roles if provided
            if roles:
                user_roles = []
                for role_name in roles:
                    role = await self.get_role_by_name(role_name)
                    if role:
                        user_roles.append(role)
                user.roles = user_roles
            
            # Save user
            user = await self.create(user)
            
            logger.info(f"User '{username}' created successfully")
            return user
            
        except Exception as e:
            logger.error(f"Error creating user '{username}': {str(e)}")
            await self.db_session.rollback()
            raise
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        try:
            stmt = (
                select(User)
                .options(
                    selectinload(User.roles).selectinload(Role.permissions)
                )
                .where(User.username == username)
            )
            
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting user by username '{username}': {str(e)}")
            return None
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        try:
            stmt = (
                select(User)
                .options(
                    selectinload(User.roles).selectinload(Role.permissions)
                )
                .where(User.email == email)
            )
            
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting user by email '{email}': {str(e)}")
            return None
    
    async def get_active_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """Get active users"""
        try:
            stmt = (
                select(User)
                .options(
                    selectinload(User.roles).selectinload(Role.permissions)
                )
                .where(User.is_active == True)
                .limit(limit)
                .offset(offset)
            )
            
            result = await self.db_session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting active users: {str(e)}")
            return []
    
    async def update_password(self, user_id: str, new_password: str) -> bool:
        """Update user password"""
        try:
            user = await self.get_by_id(user_id)
            if not user:
                return False
            
            # Hash new password
            password_hash = self._hash_password(new_password)
            
            # Update password
            user.password_hash = password_hash
            user.updated_at = datetime.utcnow()
            
            await self.db_session.commit()
            
            logger.info(f"Password updated for user '{user.username}'")
            return True
            
        except Exception as e:
            logger.error(f"Error updating password for user '{user_id}': {str(e)}")
            await self.db_session.rollback()
            return False
    
    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate user"""
        try:
            user = await self.get_by_id(user_id)
            if not user:
                return False
            
            user.is_active = False
            user.updated_at = datetime.utcnow()
            
            await self.db_session.commit()
            
            logger.info(f"User '{user.username}' deactivated")
            return True
            
        except Exception as e:
            logger.error(f"Error deactivating user '{user_id}': {str(e)}")
            await self.db_session.rollback()
            return False
    
    async def generate_token(self, user: User) -> str:
        """Generate JWT token for user"""
        try:
            payload = {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'roles': [role.name for role in user.roles] if user.roles else [],
                'permissions': [
                    permission.name 
                    for role in user.roles 
                    for permission in role.permissions
                ] if user.roles else [],
                'exp': datetime.utcnow() + timedelta(hours=self.token_expire_hours),
                'iat': datetime.utcnow()
            }
            
            token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
            
            # Store session
            await self.create_session(user.id, token)
            
            logger.info(f"Token generated for user '{user.username}'")
            return token
            
        except Exception as e:
            logger.error(f"Error generating token for user '{user.username}': {str(e)}")
            raise
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Check if session exists and is active
            session = await self.get_session_by_token(token)
            if not session or not session.is_active:
                logger.warning("Token verification failed: Session not found or inactive")
                return None
            
            # Check if user is still active
            user = await self.get_by_id(payload['user_id'])
            if not user or not user.is_active:
                logger.warning("Token verification failed: User not found or inactive")
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token verification failed: Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Token verification failed: Invalid token")
            return None
        except Exception as e:
            logger.error(f"Error verifying token: {str(e)}")
            return None
    
    async def create_session(self, user_id: str, token: str) -> UserSession:
        """Create user session"""
        try:
            session = UserSession(
                user_id=user_id,
                token=token,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=self.token_expire_hours),
                is_active=True
            )
            
            self.db_session.add(session)
            await self.db_session.commit()
            
            return session
            
        except Exception as e:
            logger.error(f"Error creating session for user '{user_id}': {str(e)}")
            await self.db_session.rollback()
            raise
    
    async def get_session_by_token(self, token: str) -> Optional[UserSession]:
        """Get session by token"""
        try:
            stmt = select(UserSession).where(UserSession.token == token)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting session by token: {str(e)}")
            return None
    
    async def revoke_session(self, token: str) -> bool:
        """Revoke user session"""
        try:
            session = await self.get_session_by_token(token)
            if not session:
                return False
            
            session.is_active = False
            session.updated_at = datetime.utcnow()
            
            await self.db_session.commit()
            
            logger.info("Session revoked")
            return True
            
        except Exception as e:
            logger.error(f"Error revoking session: {str(e)}")
            await self.db_session.rollback()
            return False
    
    async def revoke_all_user_sessions(self, user_id: str) -> bool:
        """Revoke all sessions for a user"""
        try:
            stmt = select(UserSession).where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True
                )
            )
            
            result = await self.db_session.execute(stmt)
            sessions = result.scalars().all()
            
            for session in sessions:
                session.is_active = False
                session.updated_at = datetime.utcnow()
            
            await self.db_session.commit()
            
            logger.info(f"All sessions revoked for user '{user_id}'")
            return True
            
        except Exception as e:
            logger.error(f"Error revoking all sessions for user '{user_id}': {str(e)}")
            await self.db_session.rollback()
            return False
    
    async def get_role_by_name(self, role_name: str) -> Optional[Role]:
        """Get role by name"""
        try:
            stmt = (
                select(Role)
                .options(selectinload(Role.permissions))
                .where(Role.name == role_name)
            )
            
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting role by name '{role_name}': {str(e)}")
            return None
    
    async def get_user_permissions(self, user_id: str) -> List[str]:
        """Get all permissions for a user"""
        try:
            user = await self.get_by_id(user_id)
            if not user or not user.roles:
                return []
            
            permissions = set()
            for role in user.roles:
                for permission in role.permissions:
                    permissions.add(permission.name)
            
            return list(permissions)
            
        except Exception as e:
            logger.error(f"Error getting user permissions for '{user_id}': {str(e)}")
            return []
    
    async def user_has_permission(self, user_id: str, permission_name: str) -> bool:
        """Check if user has specific permission"""
        try:
            permissions = await self.get_user_permissions(user_id)
            return permission_name in permissions
            
        except Exception as e:
            logger.error(f"Error checking permission '{permission_name}' for user '{user_id}': {str(e)}")
            return False
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    async def get_auth_stats(self) -> Dict[str, Any]:
        """Get authentication statistics"""
        try:
            # Total users
            total_users = await self.count()
            
            # Active users
            active_users_stmt = select(User).where(User.is_active == True)
            active_users_result = await self.db_session.execute(active_users_stmt)
            active_users = len(active_users_result.scalars().all())
            
            # Active sessions
            active_sessions_stmt = select(UserSession).where(
                and_(
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.utcnow()
                )
            )
            active_sessions_result = await self.db_session.execute(active_sessions_stmt)
            active_sessions = len(active_sessions_result.scalars().all())
            
            # Recent logins (last 24 hours)
            recent_login_time = datetime.utcnow() - timedelta(hours=24)
            recent_logins_stmt = select(User).where(
                and_(
                    User.last_login.isnot(None),
                    User.last_login > recent_login_time
                )
            )
            recent_logins_result = await self.db_session.execute(recent_logins_stmt)
            recent_logins = len(recent_logins_result.scalars().all())
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'inactive_users': total_users - active_users,
                'active_sessions': active_sessions,
                'recent_logins': recent_logins,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting auth stats: {str(e)}")
            return {
                'total_users': 0,
                'active_users': 0,
                'inactive_users': 0,
                'active_sessions': 0,
                'recent_logins': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
