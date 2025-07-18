"""
Authentication service for user management and security operations
"""

import asyncio
import hashlib
import secrets
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

from wakedock.services.base_service import BaseService
from wakedock.core.logging import get_logger
from wakedock.core.exceptions import WakeDockException

logger = get_logger(__name__)


class AuthService(BaseService):
    """Service for authentication operations"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.config = config or {}
        self.password_reset_tokens: Dict[str, Dict[str, Any]] = {}
        self.login_attempts: Dict[str, Dict[str, Any]] = {}
        self.max_login_attempts = 5
        self.lockout_duration = 300  # 5 minutes
        self.token_expiry = 3600  # 1 hour
        
    async def initialize(self) -> bool:
        """Initialize the authentication service"""
        try:
            logger.info("Initializing Authentication Service")
            
            # Initialize password reset token cleanup
            asyncio.create_task(self._cleanup_expired_tokens())
            
            # Initialize login attempt cleanup
            asyncio.create_task(self._cleanup_login_attempts())
            
            self.is_initialized = True
            logger.info("Authentication Service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Authentication Service: {str(e)}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        try:
            health_status = {
                'service': 'AuthService',
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'components': {
                    'password_reset_tokens': len(self.password_reset_tokens),
                    'login_attempts': len(self.login_attempts),
                    'max_login_attempts': self.max_login_attempts,
                    'lockout_duration': self.lockout_duration
                }
            }
            
            return health_status
            
        except Exception as e:
            logger.error(f"Auth service health check failed: {str(e)}")
            return {
                'service': 'AuthService',
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def check_login_attempts(self, identifier: str) -> Dict[str, Any]:
        """Check login attempts for user/IP"""
        try:
            current_time = datetime.utcnow()
            
            if identifier not in self.login_attempts:
                return {
                    'allowed': True,
                    'attempts': 0,
                    'lockout_until': None,
                    'remaining_attempts': self.max_login_attempts
                }
            
            attempt_data = self.login_attempts[identifier]
            
            # Check if lockout period has expired
            if attempt_data['lockout_until'] and current_time > attempt_data['lockout_until']:
                # Reset attempts after lockout period
                del self.login_attempts[identifier]
                return {
                    'allowed': True,
                    'attempts': 0,
                    'lockout_until': None,
                    'remaining_attempts': self.max_login_attempts
                }
            
            # Check if currently locked out
            if attempt_data['lockout_until'] and current_time <= attempt_data['lockout_until']:
                return {
                    'allowed': False,
                    'attempts': attempt_data['attempts'],
                    'lockout_until': attempt_data['lockout_until'],
                    'remaining_attempts': 0
                }
            
            # Check if max attempts exceeded
            if attempt_data['attempts'] >= self.max_login_attempts:
                # Apply lockout
                lockout_until = current_time + timedelta(seconds=self.lockout_duration)
                attempt_data['lockout_until'] = lockout_until
                
                return {
                    'allowed': False,
                    'attempts': attempt_data['attempts'],
                    'lockout_until': lockout_until,
                    'remaining_attempts': 0
                }
            
            return {
                'allowed': True,
                'attempts': attempt_data['attempts'],
                'lockout_until': None,
                'remaining_attempts': self.max_login_attempts - attempt_data['attempts']
            }
            
        except Exception as e:
            logger.error(f"Error checking login attempts: {str(e)}")
            return {
                'allowed': True,
                'attempts': 0,
                'lockout_until': None,
                'remaining_attempts': self.max_login_attempts
            }
    
    async def record_login_attempt(self, identifier: str, success: bool) -> bool:
        """Record login attempt"""
        try:
            current_time = datetime.utcnow()
            
            if identifier not in self.login_attempts:
                self.login_attempts[identifier] = {
                    'attempts': 0,
                    'first_attempt': current_time,
                    'last_attempt': current_time,
                    'lockout_until': None
                }
            
            attempt_data = self.login_attempts[identifier]
            
            if success:
                # Reset attempts on successful login
                del self.login_attempts[identifier]
                logger.info(f"Login attempt recorded: {identifier} - SUCCESS")
            else:
                # Increment failed attempts
                attempt_data['attempts'] += 1
                attempt_data['last_attempt'] = current_time
                
                # Apply lockout if max attempts exceeded
                if attempt_data['attempts'] >= self.max_login_attempts:
                    attempt_data['lockout_until'] = current_time + timedelta(seconds=self.lockout_duration)
                    logger.warning(f"Account locked: {identifier} - {attempt_data['attempts']} failed attempts")
                
                logger.warning(f"Login attempt recorded: {identifier} - FAILED ({attempt_data['attempts']} attempts)")
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording login attempt: {str(e)}")
            return False
    
    async def generate_password_reset_token(self, user_id: str, email: str) -> str:
        """Generate password reset token"""
        try:
            # Generate secure token
            token = secrets.token_urlsafe(32)
            
            # Store token with expiry
            self.password_reset_tokens[token] = {
                'user_id': user_id,
                'email': email,
                'created_at': datetime.utcnow(),
                'expires_at': datetime.utcnow() + timedelta(seconds=self.token_expiry)
            }
            
            logger.info(f"Password reset token generated for user: {user_id}")
            return token
            
        except Exception as e:
            logger.error(f"Error generating password reset token: {str(e)}")
            raise WakeDockException("Failed to generate password reset token")
    
    async def verify_password_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify password reset token"""
        try:
            if token not in self.password_reset_tokens:
                logger.warning(f"Invalid password reset token: {token}")
                return None
            
            token_data = self.password_reset_tokens[token]
            current_time = datetime.utcnow()
            
            # Check if token has expired
            if current_time > token_data['expires_at']:
                logger.warning(f"Expired password reset token: {token}")
                del self.password_reset_tokens[token]
                return None
            
            logger.info(f"Valid password reset token verified: {token}")
            return token_data
            
        except Exception as e:
            logger.error(f"Error verifying password reset token: {str(e)}")
            return None
    
    async def consume_password_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Consume password reset token (use once)"""
        try:
            token_data = await self.verify_password_reset_token(token)
            if not token_data:
                return None
            
            # Remove token after use
            del self.password_reset_tokens[token]
            
            logger.info(f"Password reset token consumed: {token}")
            return token_data
            
        except Exception as e:
            logger.error(f"Error consuming password reset token: {str(e)}")
            return None
    
    async def send_password_reset_email(self, email: str, token: str) -> bool:
        """Send password reset email"""
        try:
            # Get email configuration
            smtp_config = self.config.get('smtp', {})
            if not smtp_config:
                logger.warning("SMTP configuration not found")
                return False
            
            # Create reset URL
            reset_url = f"{self.config.get('frontend_url', 'http://localhost:3000')}/reset-password?token={token}"
            
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = 'Password Reset Request - WakeDock'
            msg['From'] = smtp_config.get('from_email', 'noreply@wakedock.com')
            msg['To'] = email
            
            # HTML content
            html_content = f"""
            <html>
              <body>
                <h2>Password Reset Request</h2>
                <p>You requested a password reset for your WakeDock account.</p>
                <p>Click the link below to reset your password:</p>
                <p><a href="{reset_url}">Reset Password</a></p>
                <p>This link will expire in 1 hour.</p>
                <p>If you didn't request this, please ignore this email.</p>
                <br>
                <p>Best regards,<br>WakeDock Team</p>
              </body>
            </html>
            """
            
            # Text content
            text_content = f"""
            Password Reset Request
            
            You requested a password reset for your WakeDock account.
            
            Visit the link below to reset your password:
            {reset_url}
            
            This link will expire in 1 hour.
            
            If you didn't request this, please ignore this email.
            
            Best regards,
            WakeDock Team
            """
            
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            with smtplib.SMTP(smtp_config.get('host', 'localhost'), smtp_config.get('port', 587)) as server:
                if smtp_config.get('use_tls', True):
                    server.starttls()
                
                if smtp_config.get('username'):
                    server.login(smtp_config['username'], smtp_config['password'])
                
                server.send_message(msg)
            
            logger.info(f"Password reset email sent to: {email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending password reset email: {str(e)}")
            return False
    
    async def generate_secure_password(self, length: int = 12) -> str:
        """Generate secure random password"""
        try:
            # Character sets
            lowercase = 'abcdefghijklmnopqrstuvwxyz'
            uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            digits = '0123456789'
            special = '!@#$%^&*()_+-=[]{}|;:,.<>?'
            
            # Ensure at least one character from each set
            password = [
                secrets.choice(lowercase),
                secrets.choice(uppercase),
                secrets.choice(digits),
                secrets.choice(special)
            ]
            
            # Fill the rest with random characters
            all_chars = lowercase + uppercase + digits + special
            for _ in range(length - 4):
                password.append(secrets.choice(all_chars))
            
            # Shuffle the password
            secrets.SystemRandom().shuffle(password)
            
            return ''.join(password)
            
        except Exception as e:
            logger.error(f"Error generating secure password: {str(e)}")
            raise WakeDockException("Failed to generate secure password")
    
    async def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """Validate password strength"""
        try:
            score = 0
            feedback = []
            
            # Length check
            if len(password) >= 8:
                score += 1
            else:
                feedback.append("Password should be at least 8 characters long")
            
            if len(password) >= 12:
                score += 1
            
            # Character diversity
            if any(c.islower() for c in password):
                score += 1
            else:
                feedback.append("Password should contain lowercase letters")
            
            if any(c.isupper() for c in password):
                score += 1
            else:
                feedback.append("Password should contain uppercase letters")
            
            if any(c.isdigit() for c in password):
                score += 1
            else:
                feedback.append("Password should contain digits")
            
            if any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
                score += 1
            else:
                feedback.append("Password should contain special characters")
            
            # Common patterns
            common_patterns = ['password', '123456', 'qwerty', 'abc123', 'admin']
            if any(pattern in password.lower() for pattern in common_patterns):
                score -= 1
                feedback.append("Password should not contain common patterns")
            
            # Repeated characters
            if len(set(password)) < len(password) * 0.5:
                score -= 1
                feedback.append("Password should not have too many repeated characters")
            
            # Determine strength
            if score >= 5:
                strength = 'strong'
            elif score >= 3:
                strength = 'medium'
            else:
                strength = 'weak'
            
            return {
                'strength': strength,
                'score': max(0, score),
                'max_score': 6,
                'feedback': feedback,
                'is_valid': score >= 3
            }
            
        except Exception as e:
            logger.error(f"Error validating password strength: {str(e)}")
            return {
                'strength': 'unknown',
                'score': 0,
                'max_score': 6,
                'feedback': ['Unable to validate password strength'],
                'is_valid': False
            }
    
    async def audit_login_activity(self, user_id: str, action: str, details: Dict[str, Any] = None) -> bool:
        """Audit login activity"""
        try:
            audit_entry = {
                'user_id': user_id,
                'action': action,
                'timestamp': datetime.utcnow(),
                'details': details or {},
                'ip_address': details.get('ip_address') if details else None,
                'user_agent': details.get('user_agent') if details else None
            }
            
            # Log audit entry
            logger.info(f"Auth audit: {action} for user {user_id}", extra=audit_entry)
            
            # In a real implementation, you would store this in a database
            # For now, we'll just log it
            
            return True
            
        except Exception as e:
            logger.error(f"Error auditing login activity: {str(e)}")
            return False
    
    async def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics"""
        try:
            current_time = datetime.utcnow()
            
            # Active lockouts
            active_lockouts = 0
            recent_attempts = 0
            
            for identifier, attempt_data in self.login_attempts.items():
                if attempt_data['lockout_until'] and current_time <= attempt_data['lockout_until']:
                    active_lockouts += 1
                
                if current_time - attempt_data['last_attempt'] <= timedelta(hours=1):
                    recent_attempts += 1
            
            # Active password reset tokens
            active_tokens = 0
            for token, token_data in self.password_reset_tokens.items():
                if current_time <= token_data['expires_at']:
                    active_tokens += 1
            
            return {
                'active_lockouts': active_lockouts,
                'recent_login_attempts': recent_attempts,
                'active_password_reset_tokens': active_tokens,
                'total_login_attempts': len(self.login_attempts),
                'max_login_attempts': self.max_login_attempts,
                'lockout_duration': self.lockout_duration,
                'timestamp': current_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting security metrics: {str(e)}")
            return {
                'active_lockouts': 0,
                'recent_login_attempts': 0,
                'active_password_reset_tokens': 0,
                'total_login_attempts': 0,
                'max_login_attempts': self.max_login_attempts,
                'lockout_duration': self.lockout_duration,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _cleanup_expired_tokens(self):
        """Clean up expired password reset tokens"""
        while True:
            try:
                current_time = datetime.utcnow()
                expired_tokens = []
                
                for token, token_data in self.password_reset_tokens.items():
                    if current_time > token_data['expires_at']:
                        expired_tokens.append(token)
                
                for token in expired_tokens:
                    del self.password_reset_tokens[token]
                
                if expired_tokens:
                    logger.info(f"Cleaned up {len(expired_tokens)} expired password reset tokens")
                
                # Sleep for 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error cleaning up expired tokens: {str(e)}")
                await asyncio.sleep(300)
    
    async def _cleanup_login_attempts(self):
        """Clean up old login attempts"""
        while True:
            try:
                current_time = datetime.utcnow()
                expired_attempts = []
                
                for identifier, attempt_data in self.login_attempts.items():
                    # Clean up attempts older than 24 hours
                    if current_time - attempt_data['last_attempt'] > timedelta(hours=24):
                        expired_attempts.append(identifier)
                    # Clean up expired lockouts
                    elif (attempt_data['lockout_until'] and 
                          current_time > attempt_data['lockout_until'] + timedelta(hours=1)):
                        expired_attempts.append(identifier)
                
                for identifier in expired_attempts:
                    del self.login_attempts[identifier]
                
                if expired_attempts:
                    logger.info(f"Cleaned up {len(expired_attempts)} old login attempts")
                
                # Sleep for 1 hour
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error cleaning up login attempts: {str(e)}")
                await asyncio.sleep(3600)
