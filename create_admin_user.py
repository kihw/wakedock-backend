#!/usr/bin/env python3
"""
Script to create default admin user if no users exist
"""
import os
import sys
import time
import secrets
import string
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

# Add src to path
sys.path.insert(0, '/app/src')

def generate_secure_password(length: int = 16) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

def wait_for_database(database_url: str, max_retries: int = 30):
    """Wait for database to be ready"""
    engine = create_engine(database_url)
    
    for attempt in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
            return engine
        except OperationalError as e:
            print(f"⏳ Database not ready (attempt {attempt + 1}/{max_retries}): {e}")
            time.sleep(2)
    
    raise Exception(f"❌ Database not available after {max_retries} attempts")

def create_admin_user():
    """Create default admin user if no users exist"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        return False
    
    try:
        # Wait for database and create engine
        engine = wait_for_database(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Import after database is ready
        from wakedock.database.models import User
        from wakedock.api.auth.password import hash_password
        
        db = SessionLocal()
        
        try:
            # Check if any users exist
            user_count = db.query(User).count()
            
            if user_count > 0:
                print(f"ℹ️  Users already exist in database ({user_count} users found)")
                return True
            
            print("🔧 No users found, creating default admin user...")
            
            # Generate secure random password
            admin_password = generate_secure_password(20)
            hashed_password = hash_password(admin_password)
            
            admin_user = User(
                username='admin',
                email='admin@wakedock.local',
                hashed_password=hashed_password,
                full_name='System Administrator',
                role='admin',
                is_active=True,
                is_verified=True
            )
            
            db.add(admin_user)
            db.commit()
            
            print("✅ Default admin user created successfully:")
            print("   Username: admin")
            print(f"   Password: {admin_password}")
            print("   Email: admin@wakedock.local")
            print("   Role: admin")
            print("⚠️  IMPORTANT: Save this password securely! It won't be displayed again.")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating admin user: {e}")
            db.rollback()
            return False
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

if __name__ == "__main__":
    success = create_admin_user()
    sys.exit(0 if success else 1)