#!/usr/bin/env python3
"""
Script de correction pour les problèmes d'initialisation du cache
"""
import sys
import os

# Ajouter le chemin des sources
sys.path.append('/app/src')

try:
    from wakedock.infrastructure.cache.service import get_cache_service
    from wakedock.config import get_settings
    import asyncio
    
    async def fix_cache_initialization():
        """Corriger l'initialisation du cache"""
        print("🔧 Correction de l'initialisation du cache...")
        
        settings = get_settings()
        print(f"📋 Configuration Redis: {settings.redis.url}")
        
        # Obtenir le service de cache
        cache_service = get_cache_service()
        
        if not cache_service.is_initialized():
            print("🚀 Initialisation du service de cache...")
            await cache_service.initialize()
            print("✅ Cache initialisé avec succès")
        else:
            print("✅ Cache déjà initialisé")
        
        # Test du cache
        test_key = "test_cache_fix"
        test_value = "cache_working"
        
        print("🧪 Test du cache...")
        await cache_service.set(test_key, test_value, ttl=60)
        retrieved = await cache_service.get(test_key)
        
        if retrieved == test_value:
            print("✅ Test du cache réussi")
        else:
            print("❌ Test du cache échoué")
        
        # Nettoyer
        await cache_service.delete(test_key)
        print("🧹 Nettoyage terminé")
    
    if __name__ == "__main__":
        asyncio.run(fix_cache_initialization())
        
except ImportError as e:
    print(f"❌ Erreur d'import: {e}")
    print("Le module cache n'est pas disponible")
except Exception as e:
    print(f"❌ Erreur lors de la correction: {e}")
    import traceback
    traceback.print_exc()
