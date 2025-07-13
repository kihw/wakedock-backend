"""Database management CLI commands for WakeDock."""

import click
from alembic import command
from alembic.config import Config
from pathlib import Path

from wakedock.database.database import init_database, db_manager


@click.group()
def db():
    """Database management commands."""
    pass


@db.command()
def init():
    """Initialize the database."""
    click.echo("Initializing database...")
    try:
        init_database()
        click.echo("✅ Database initialized successfully!")
    except Exception as e:
        click.echo(f"❌ Failed to initialize database: {e}")


@db.command()
def create_migration():
    """Create a new migration."""
    click.echo("Creating migration...")
    try:
        alembic_cfg = Config("alembic.ini")
        command.revision(alembic_cfg, autogenerate=True, message="Auto-generated migration")
        click.echo("✅ Migration created successfully!")
    except Exception as e:
        click.echo(f"❌ Failed to create migration: {e}")


@db.command()
def migrate():
    """Run database migrations."""
    click.echo("Running migrations...")
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        click.echo("✅ Migrations completed successfully!")
    except Exception as e:
        click.echo(f"❌ Failed to run migrations: {e}")


@db.command()
def reset():
    """Reset the database (drop and recreate)."""
    if click.confirm("This will delete all data. Continue?"):
        click.echo("Resetting database...")
        try:
            db_manager.initialize()
            db_manager.drop_tables()
            db_manager.create_tables()
            click.echo("✅ Database reset successfully!")
        except Exception as e:
            click.echo(f"❌ Failed to reset database: {e}")


if __name__ == "__main__":
    db()
