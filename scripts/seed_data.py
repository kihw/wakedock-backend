#!/usr/bin/env python3
"""
Script de seeding des données de test
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le dossier parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from wakedock.database.database import get_db_session
from wakedock.database.models import User, Organization


async def seed_data():
    """Ajoute des données de test"""
    print("🌱 Seeding des données de test...")
    
    async with get_db_session() as session:
        # Créer un utilisateur admin de test
        admin_user = User(
            username="admin",
            email="admin@wakedock.local",
            is_active=True,
            is_superuser=True
        )
        admin_user.set_password("admin123")
        
        session.add(admin_user)
        await session.commit()
    
    print("✅ Données de test ajoutées avec succès!")


if __name__ == "__main__":
    asyncio.run(seed_data())
