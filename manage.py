#!/usr/bin/env python3
"""
Development and production runner for WakeDock
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def run_development():
    """Run WakeDock in development mode"""
    print("🚀 Starting WakeDock in development mode...")
    
    # Set development environment
    os.environ.setdefault("WAKEDOCK_CONFIG_PATH", "config/config.yml")
    
    from wakedock.main import main
    await main()

async def run_production():
    """Run WakeDock in production mode"""
    print("🚀 Starting WakeDock in production mode...")
    
    # Set production environment
    os.environ.setdefault("WAKEDOCK_CONFIG_PATH", "config/config.yml")
    
    from wakedock.main import main
    await main()

def run_migrations():
    """Run database migrations"""
    import subprocess
    print("📊 Running database migrations...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], check=True, capture_output=True, text=True)
        print("✅ Database migrations completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration failed: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False

def create_migration(message: str):
    """Create a new migration"""
    import subprocess
    print(f"📝 Creating migration: {message}")
    try:
        result = subprocess.run([
            sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", message
        ], check=True, capture_output=True, text=True)
        print("✅ Migration created successfully")
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration creation failed: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False

def run_tests():
    """Run test suite"""
    import subprocess
    print("🧪 Running test suite...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", "tests/", "-v"
        ], check=True)
        print("✅ All tests passed!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Some tests failed")
        return False

def check_health():
    """Check system health"""
    print("🏥 Checking WakeDock health...")
    
    # Run component tests
    import subprocess
    try:
        result = subprocess.run([
            sys.executable, "test_components.py"
        ], check=True, capture_output=True, text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print("❌ Health check failed")
        print(e.stdout)
        return False

def init_database():
    """Initialize database with default data"""
    print("🗄️ Initializing database...")
    
    try:
        from wakedock.database.database import init_database
        init_database()
        print("✅ Database initialized successfully")
        
        # Run migrations
        if run_migrations():
            print("✅ Database is ready")
            return True
        else:
            return False
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="WakeDock Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Run commands
    subparsers.add_parser("dev", help="Run in development mode")
    subparsers.add_parser("prod", help="Run in production mode") 
    subparsers.add_parser("start", help="Start WakeDock (alias for dev)")
    
    # Database commands
    db_parser = subparsers.add_parser("migrate", help="Run database migrations")
    
    migration_parser = subparsers.add_parser("migration", help="Create new migration")
    migration_parser.add_argument("message", help="Migration message")
    
    subparsers.add_parser("init-db", help="Initialize database")
    
    # Testing and health
    subparsers.add_parser("test", help="Run test suite")
    subparsers.add_parser("health", help="Check system health")
    
    args = parser.parse_args()
    
    if args.command in ["dev", "start"]:
        asyncio.run(run_development())
    elif args.command == "prod":
        asyncio.run(run_production())
    elif args.command == "migrate":
        success = run_migrations()
        sys.exit(0 if success else 1)
    elif args.command == "migration":
        success = create_migration(args.message)
        sys.exit(0 if success else 1)
    elif args.command == "init-db":
        success = init_database()
        sys.exit(0 if success else 1)
    elif args.command == "test":
        success = run_tests()
        sys.exit(0 if success else 1)
    elif args.command == "health":
        success = check_health()
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        print("\n💡 Quick start:")
        print("  python manage.py dev     # Start development server")
        print("  python manage.py init-db # Initialize database")
        print("  python manage.py health  # Check system health")

if __name__ == "__main__":
    main()
