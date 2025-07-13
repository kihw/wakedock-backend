#!/usr/bin/env python3
"""
Script d'initialisation de la base de données WakeDock
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le dossier parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from wakedock.database.database import init_database
from wakedock.config import get_settings


async def init_db():
    """Initialise la base de données"""
    settings = get_settings()
    print("🔄 Initialisation de la base de données...")
    
    await init_database()
    print("✅ Base de données initialisée avec succès!")


if __name__ == "__main__":
    asyncio.run(init_db())
