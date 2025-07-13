"""Password hashing and verification utilities."""

from passlib.context import CryptContext
from passlib.hash import bcrypt


class PasswordManager:
    """Password hashing and verification manager."""
    
    def __init__(self):
        """Initialize password manager with bcrypt context."""
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def needs_update(self, hashed_password: str) -> bool:
        """Check if a password hash needs to be updated."""
        return self.pwd_context.needs_update(hashed_password)


# Global password manager instance
password_manager = PasswordManager()


def hash_password(password: str) -> str:
    """Hash a password."""
    return password_manager.hash_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password."""
    return password_manager.verify_password(plain_password, hashed_password)
