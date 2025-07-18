"""
Système de cache intelligent pour optimisations mobiles - WakeDock v0.6.5
=========================================================================
Cache adaptatif basé sur le type de client et les patterns d'usage
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from wakedock.core.mobile_optimization_service import ClientType

logger = logging.getLogger(__name__)

class CacheStrategy(Enum):
    """Stratégies de cache disponibles"""
    AGGRESSIVE = "aggressive"    # Cache long pour mobile
    MODERATE = "moderate"       # Cache moyen pour tablet
    CONSERVATIVE = "conservative"  # Cache court pour desktop
    ADAPTIVE = "adaptive"       # Cache adaptatif selon l'usage

@dataclass
class CacheEntry:
    """Entrée de cache avec métadonnées"""
    key: str
    data: Any
    client_type: str
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    compression_ratio: float = 0.0
    original_size: int = 0
    compressed_size: int = 0

class MobileCacheManager:
    """
    Gestionnaire de cache intelligent pour optimisations mobiles
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_patterns: Dict[str, Dict[str, Any]] = {}
        self.client_preferences: Dict[str, Dict[str, Any]] = {}
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "cache_size": 0,
            "hit_ratio": 0.0,
            "memory_usage": 0,
            "evictions": 0
        }
    
    def get_cache_strategy(self, client_type: ClientType) -> CacheStrategy:
        """
        Retourne la stratégie de cache optimale pour le type de client
        """
        strategy_map = {
            ClientType.MOBILE: CacheStrategy.AGGRESSIVE,
            ClientType.TABLET: CacheStrategy.MODERATE,
            ClientType.DESKTOP: CacheStrategy.CONSERVATIVE,
            ClientType.PWA: CacheStrategy.ADAPTIVE
        }
        return strategy_map.get(client_type, CacheStrategy.MODERATE)
    
    def get_ttl_for_client(self, client_type: ClientType, data_type: str) -> int:
        """
        Retourne le TTL optimal selon le type de client et de données
        """
        # TTL de base par type de client
        base_ttl = {
            ClientType.MOBILE: 600,    # 10 minutes - cache agressif
            ClientType.TABLET: 300,    # 5 minutes - cache modéré
            ClientType.DESKTOP: 180,   # 3 minutes - cache conservateur
            ClientType.PWA: 900        # 15 minutes - cache très agressif
        }
        
        # Multiplicateurs par type de données
        data_multipliers = {
            "containers": 1.0,         # Données fréquemment mises à jour
            "logs": 0.5,              # Données très volatiles
            "metrics": 0.3,           # Données en temps réel
            "system": 2.0,            # Données stables
            "user_preferences": 5.0,   # Données très stables
            "static": 10.0            # Données statiques
        }
        
        client_ttl = base_ttl.get(client_type, self.default_ttl)
        multiplier = data_multipliers.get(data_type, 1.0)
        
        return int(client_ttl * multiplier)
    
    def generate_cache_key(self, endpoint: str, params: Dict[str, Any], client_type: ClientType) -> str:
        """
        Génère une clé de cache unique
        """
        # Trier les paramètres pour avoir une clé cohérente
        sorted_params = sorted(params.items()) if params else []
        params_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        
        return f"{client_type.value}:{endpoint}:{params_str}"
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Récupère une valeur du cache
        """
        self.stats["total_requests"] += 1
        
        if key not in self.cache:
            self.stats["cache_misses"] += 1
            return None
        
        entry = self.cache[key]
        
        # Vérifier l'expiration
        if datetime.now() > entry.expires_at:
            await self.delete(key)
            self.stats["cache_misses"] += 1
            return None
        
        # Mettre à jour les stats d'accès
        entry.access_count += 1
        entry.last_accessed = datetime.now()
        
        self.stats["cache_hits"] += 1
        self._update_hit_ratio()
        
        logger.debug(f"Cache hit pour la clé: {key}")
        return entry.data
    
    async def set(self, key: str, data: Any, client_type: ClientType, 
                 ttl: Optional[int] = None, data_type: str = "default") -> bool:
        """
        Stocke une valeur dans le cache
        """
        try:
            # Calculer le TTL
            if ttl is None:
                ttl = self.get_ttl_for_client(client_type, data_type)
            
            # Calculer la taille des données
            data_str = json.dumps(data, default=str)
            original_size = len(data_str.encode('utf-8'))
            
            # Comprimer si nécessaire
            compressed_size = original_size
            compression_ratio = 0.0
            
            if original_size > 1024:  # Comprimer si > 1KB
                import gzip
                compressed_data = gzip.compress(data_str.encode('utf-8'))
                compressed_size = len(compressed_data)
                compression_ratio = (1 - compressed_size / original_size) * 100
            
            # Créer l'entrée de cache
            entry = CacheEntry(
                key=key,
                data=data,
                client_type=client_type.value,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=ttl),
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=compression_ratio
            )
            
            # Vérifier la taille du cache
            if len(self.cache) >= self.max_size:
                await self._evict_least_recently_used()
            
            # Stocker l'entrée
            self.cache[key] = entry
            self.stats["cache_size"] = len(self.cache)
            
            # Mettre à jour les patterns d'accès
            self._update_access_patterns(key, client_type, data_type)
            
            logger.debug(f"Cache mis à jour pour la clé: {key} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise en cache: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Supprime une entrée du cache
        """
        if key in self.cache:
            del self.cache[key]
            self.stats["cache_size"] = len(self.cache)
            logger.debug(f"Entrée supprimée du cache: {key}")
            return True
        return False
    
    async def clear_by_client_type(self, client_type: ClientType):
        """
        Efface le cache pour un type de client spécifique
        """
        keys_to_delete = [
            key for key, entry in self.cache.items()
            if entry.client_type == client_type.value
        ]
        
        for key in keys_to_delete:
            await self.delete(key)
        
        logger.info(f"Cache effacé pour le type de client: {client_type.value}")
    
    async def clear_expired(self):
        """
        Efface les entrées expirées du cache
        """
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now > entry.expires_at
        ]
        
        for key in expired_keys:
            await self.delete(key)
        
        if expired_keys:
            logger.info(f"Suppression de {len(expired_keys)} entrées expirées")
    
    async def _evict_least_recently_used(self):
        """
        Supprime l'entrée la moins récemment utilisée
        """
        if not self.cache:
            return
        
        # Trouver l'entrée la moins récemment utilisée
        lru_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k].last_accessed or self.cache[k].created_at
        )
        
        await self.delete(lru_key)
        self.stats["evictions"] += 1
        logger.debug(f"Éviction LRU de la clé: {lru_key}")
    
    def _update_access_patterns(self, key: str, client_type: ClientType, data_type: str):
        """
        Met à jour les patterns d'accès pour l'optimisation adaptive
        """
        pattern_key = f"{client_type.value}:{data_type}"
        
        if pattern_key not in self.access_patterns:
            self.access_patterns[pattern_key] = {
                "access_count": 0,
                "last_access": datetime.now(),
                "avg_interval": 0,
                "data_type": data_type,
                "client_type": client_type.value
            }
        
        pattern = self.access_patterns[pattern_key]
        pattern["access_count"] += 1
        
        # Calculer l'intervalle moyen entre les accès
        if pattern["last_access"]:
            interval = (datetime.now() - pattern["last_access"]).total_seconds()
            pattern["avg_interval"] = (pattern["avg_interval"] + interval) / 2
        
        pattern["last_access"] = datetime.now()
    
    def _update_hit_ratio(self):
        """
        Met à jour le ratio de succès du cache
        """
        if self.stats["total_requests"] > 0:
            self.stats["hit_ratio"] = (
                self.stats["cache_hits"] / self.stats["total_requests"]
            ) * 100
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du cache
        """
        # Calculer l'utilisation mémoire
        memory_usage = sum(
            entry.compressed_size or entry.original_size
            for entry in self.cache.values()
        )
        
        self.stats["memory_usage"] = memory_usage
        
        return {
            **self.stats,
            "memory_usage_mb": memory_usage / (1024 * 1024),
            "cache_efficiency": self.stats["hit_ratio"],
            "avg_entry_size": memory_usage / len(self.cache) if self.cache else 0,
            "total_entries": len(self.cache),
            "access_patterns": len(self.access_patterns)
        }
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Retourne les informations détaillées du cache
        """
        return {
            "cache_entries": len(self.cache),
            "max_size": self.max_size,
            "default_ttl": self.default_ttl,
            "entries_by_client": {
                client_type.value: len([
                    e for e in self.cache.values()
                    if e.client_type == client_type.value
                ])
                for client_type in ClientType
            },
            "top_accessed_keys": sorted(
                [
                    {"key": k, "access_count": v.access_count}
                    for k, v in self.cache.items()
                ],
                key=lambda x: x["access_count"],
                reverse=True
            )[:10],
            "compression_stats": {
                "total_original_size": sum(e.original_size for e in self.cache.values()),
                "total_compressed_size": sum(e.compressed_size for e in self.cache.values()),
                "avg_compression_ratio": sum(e.compression_ratio for e in self.cache.values()) / len(self.cache) if self.cache else 0
            }
        }
    
    async def optimize_cache_adaptive(self):
        """
        Optimise le cache de manière adaptive selon les patterns d'usage
        """
        # Analyser les patterns d'accès
        for pattern_key, pattern in self.access_patterns.items():
            client_type_str, data_type = pattern_key.split(":", 1)
            client_type = ClientType(client_type_str)
            
            # Ajuster le TTL selon la fréquence d'accès
            if pattern["avg_interval"] > 0:
                # Si accès fréquent, augmenter le TTL
                if pattern["avg_interval"] < 60:  # Moins d'1 minute
                    new_ttl = self.get_ttl_for_client(client_type, data_type) * 1.5
                # Si accès rare, diminuer le TTL
                elif pattern["avg_interval"] > 600:  # Plus de 10 minutes
                    new_ttl = self.get_ttl_for_client(client_type, data_type) * 0.7
                else:
                    new_ttl = self.get_ttl_for_client(client_type, data_type)
                
                # Mettre à jour les préférences client
                self.client_preferences[pattern_key] = {
                    "optimized_ttl": new_ttl,
                    "usage_pattern": "frequent" if pattern["avg_interval"] < 60 else "rare",
                    "last_optimization": datetime.now()
                }
        
        logger.info("Optimisation adaptive du cache terminée")


# Instance globale du gestionnaire de cache
cache_manager: Optional[MobileCacheManager] = None

def get_mobile_cache_manager() -> MobileCacheManager:
    """
    Retourne l'instance globale du gestionnaire de cache mobile
    """
    global cache_manager
    if not cache_manager:
        cache_manager = MobileCacheManager()
    return cache_manager

async def cached_response(
    key: str,
    data_func: callable,
    client_type: ClientType,
    data_type: str = "default",
    ttl: Optional[int] = None
) -> Any:
    """
    Décorateur pour mettre en cache les réponses
    """
    manager = get_mobile_cache_manager()
    
    # Essayer de récupérer depuis le cache
    cached_data = await manager.get(key)
    if cached_data is not None:
        return cached_data
    
    # Générer les données si pas en cache
    data = await data_func() if asyncio.iscoroutinefunction(data_func) else data_func()
    
    # Mettre en cache
    await manager.set(key, data, client_type, ttl, data_type)
    
    return data
