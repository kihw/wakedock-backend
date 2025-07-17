"""
Service d'optimisation pour clients mobiles - Version 0.2.6
"""
import gzip
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

from fastapi import Request

logger = logging.getLogger(__name__)

class ClientType(Enum):
    """Types de clients supportés"""
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    PWA = "pwa"

class CompressionType(Enum):
    """Types de compression supportés"""
    NONE = "none"
    GZIP = "gzip"
    BROTLI = "brotli"

class MobileOptimizationService:
    """
    Service d'optimisation pour les clients mobiles et PWA
    """
    
    def __init__(self):
        self.response_cache = {}
        self.client_preferences = {}
        self.compression_stats = {
            "total_requests": 0,
            "compressed_responses": 0,
            "compression_ratio": 0.0,
            "bandwidth_saved": 0
        }
        
    def detect_client_type(self, request: Request) -> ClientType:
        """
        Détecte le type de client basé sur les headers
        """
        user_agent = request.headers.get("user-agent", "").lower()
        
        # Détection PWA
        if "pwa" in user_agent or request.headers.get("sec-fetch-mode") == "navigate":
            return ClientType.PWA
            
        # Détection mobile
        mobile_indicators = [
            "mobile", "android", "iphone", "ipad", "blackberry",
            "windows phone", "opera mini", "mobile safari"
        ]
        
        if any(indicator in user_agent for indicator in mobile_indicators):
            # Différencier mobile et tablet
            if "tablet" in user_agent or "ipad" in user_agent:
                return ClientType.TABLET
            return ClientType.MOBILE
            
        return ClientType.DESKTOP
    
    def get_optimal_response_format(self, client_type: ClientType, data_type: str) -> Dict[str, Any]:
        """
        Retourne le format de réponse optimal selon le type de client
        """
        formats = {
            ClientType.MOBILE: {
                "containers": {
                    "fields": ["id", "name", "status", "cpu_percent", "memory_usage"],
                    "limit": 20,
                    "include_details": False
                },
                "logs": {
                    "fields": ["timestamp", "level", "message"],
                    "limit": 50,
                    "truncate_message": 100
                },
                "metrics": {
                    "fields": ["timestamp", "cpu", "memory"],
                    "aggregation": "5m",
                    "limit": 100
                }
            },
            ClientType.TABLET: {
                "containers": {
                    "fields": ["id", "name", "status", "cpu_percent", "memory_usage", "network"],
                    "limit": 50,
                    "include_details": True
                },
                "logs": {
                    "fields": ["timestamp", "level", "message", "container"],
                    "limit": 100,
                    "truncate_message": 200
                },
                "metrics": {
                    "fields": ["timestamp", "cpu", "memory", "network", "disk"],
                    "aggregation": "1m",
                    "limit": 200
                }
            },
            ClientType.DESKTOP: {
                "containers": {
                    "fields": "all",
                    "limit": 100,
                    "include_details": True
                },
                "logs": {
                    "fields": "all",
                    "limit": 500,
                    "truncate_message": None
                },
                "metrics": {
                    "fields": "all",
                    "aggregation": "30s",
                    "limit": 1000
                }
            },
            ClientType.PWA: {
                "containers": {
                    "fields": ["id", "name", "status", "cpu_percent", "memory_usage"],
                    "limit": 30,
                    "include_details": False,
                    "cache_ttl": 60
                },
                "logs": {
                    "fields": ["timestamp", "level", "message"],
                    "limit": 75,
                    "truncate_message": 150,
                    "cache_ttl": 30
                },
                "metrics": {
                    "fields": ["timestamp", "cpu", "memory"],
                    "aggregation": "2m",
                    "limit": 150,
                    "cache_ttl": 120
                }
            }
        }
        
        return formats.get(client_type, formats[ClientType.DESKTOP]).get(data_type, {})
    
    def optimize_data_for_client(self, data: Any, client_type: ClientType, data_type: str) -> Any:
        """
        Optimise les données selon le type de client
        """
        format_config = self.get_optimal_response_format(client_type, data_type)
        
        if isinstance(data, list):
            # Limiter le nombre d'éléments
            if "limit" in format_config:
                data = data[:format_config["limit"]]
            
            # Filtrer les champs pour chaque élément
            if "fields" in format_config and format_config["fields"] != "all":
                data = [self._filter_fields(item, format_config["fields"]) for item in data]
                
        elif isinstance(data, dict):
            # Filtrer les champs pour un objet unique
            if "fields" in format_config and format_config["fields"] != "all":
                data = self._filter_fields(data, format_config["fields"])
        
        # Traitement spécifique par type de données
        if data_type == "logs":
            data = self._optimize_logs(data, format_config)
        elif data_type == "metrics":
            data = self._optimize_metrics(data, format_config)
            
        return data
    
    def _filter_fields(self, item: Dict[str, Any], allowed_fields: List[str]) -> Dict[str, Any]:
        """
        Filtre les champs d'un dictionnaire
        """
        return {field: item.get(field) for field in allowed_fields if field in item}
    
    def _optimize_logs(self, logs: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Optimise les logs pour mobile
        """
        if not isinstance(logs, list):
            return logs
            
        for log in logs:
            # Tronquer les messages longs
            if "truncate_message" in config and config["truncate_message"]:
                if "message" in log and len(log["message"]) > config["truncate_message"]:
                    log["message"] = log["message"][:config["truncate_message"]] + "..."
            
            # Simplifier le timestamp pour mobile
            if "timestamp" in log:
                try:
                    timestamp = datetime.fromisoformat(log["timestamp"].replace('Z', '+00:00'))
                    log["timestamp"] = timestamp.strftime("%H:%M:%S")
                except:
                    pass
                    
        return logs
    
    def _optimize_metrics(self, metrics: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Optimise les métriques pour mobile
        """
        if not isinstance(metrics, list):
            return metrics
            
        # Agrégation des données si configurée
        if "aggregation" in config:
            metrics = self._aggregate_metrics(metrics, config["aggregation"])
            
        return metrics
    
    def _aggregate_metrics(self, metrics: List[Dict[str, Any]], interval: str) -> List[Dict[str, Any]]:
        """
        Agrège les métriques selon l'intervalle spécifié
        """
        # Implémentation simplifiée - grouper par intervalle de temps
        interval_seconds = {
            "30s": 30,
            "1m": 60,
            "2m": 120,
            "5m": 300
        }.get(interval, 60)
        
        if not metrics:
            return metrics
            
        # Grouper les métriques par intervalles
        aggregated = {}
        for metric in metrics:
            try:
                timestamp = datetime.fromisoformat(metric["timestamp"].replace('Z', '+00:00'))
                # Arrondir au plus proche intervalle
                interval_key = timestamp.replace(
                    second=(timestamp.second // interval_seconds) * interval_seconds,
                    microsecond=0
                )
                
                if interval_key not in aggregated:
                    aggregated[interval_key] = {
                        "timestamp": interval_key.isoformat(),
                        "cpu": [],
                        "memory": [],
                        "network": [],
                        "disk": []
                    }
                
                # Ajouter les valeurs pour moyennage
                for field in ["cpu", "memory", "network", "disk"]:
                    if field in metric:
                        aggregated[interval_key][field].append(metric[field])
                        
            except Exception as e:
                logger.warning(f"Erreur lors de l'agrégation de métrique: {e}")
                continue
        
        # Calculer les moyennes
        result = []
        for interval_key, data in sorted(aggregated.items()):
            metric = {"timestamp": data["timestamp"]}
            for field in ["cpu", "memory", "network", "disk"]:
                if data[field]:
                    metric[field] = sum(data[field]) / len(data[field])
            result.append(metric)
            
        return result
    
    def should_compress_response(self, request: Request, data_size: int) -> CompressionType:
        """
        Détermine si la réponse doit être compressée
        """
        # Seuil minimum pour compression (1KB)
        if data_size < 1024:
            return CompressionType.NONE
            
        accept_encoding = request.headers.get("accept-encoding", "").lower()
        
        # Préférer brotli si supporté et disponible
        if "br" in accept_encoding:
            return CompressionType.BROTLI
        elif "gzip" in accept_encoding:
            return CompressionType.GZIP
            
        return CompressionType.NONE
    
    def compress_response(self, data: bytes, compression_type: CompressionType) -> bytes:
        """
        Compresse la réponse selon le type spécifié
        """
        original_size = len(data)
        
        try:
            if compression_type == CompressionType.GZIP:
                compressed_data = gzip.compress(data)
            elif compression_type == CompressionType.BROTLI:
                try:
                    import brotli
                    compressed_data = brotli.compress(data)
                except ImportError:
                    logger.warning("Brotli non disponible, utilisation de gzip")
                    compressed_data = gzip.compress(data)
            else:
                return data
                
            # Mise à jour des statistiques
            self.compression_stats["total_requests"] += 1
            self.compression_stats["compressed_responses"] += 1
            
            compressed_size = len(compressed_data)
            if original_size > 0:
                ratio = 1 - (compressed_size / original_size)
                self.compression_stats["compression_ratio"] = (
                    self.compression_stats["compression_ratio"] * 0.9 + ratio * 0.1
                )
                self.compression_stats["bandwidth_saved"] += original_size - compressed_size
                
            return compressed_data
            
        except Exception as e:
            logger.error(f"Erreur lors de la compression: {e}")
            return data
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Récupère les préférences utilisateur
        """
        return self.client_preferences.get(user_id, {
            "theme": "auto",
            "layout": "default",
            "notifications": {
                "push_enabled": True,
                "email_enabled": True,
                "severity_threshold": "medium"
            },
            "data_usage": {
                "compress_images": True,
                "reduce_animations": False,
                "offline_mode": False
            }
        })
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """
        Met à jour les préférences utilisateur
        """
        try:
            current_prefs = self.get_user_preferences(user_id)
            current_prefs.update(preferences)
            self.client_preferences[user_id] = current_prefs
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des préférences: {e}")
            return False
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de compression
        """
        return {
            **self.compression_stats,
            "cache_size": len(self.response_cache),
            "active_clients": len(self.client_preferences)
        }
    
    def clear_cache(self) -> int:
        """
        Vide le cache de réponses
        """
        count = len(self.response_cache)
        self.response_cache.clear()
        return count
    
    async def start(self):
        """
        Démarre le service d'optimisation mobile
        """
        logger.info("Service d'optimisation mobile démarré")
        
    async def stop(self):
        """
        Arrête le service d'optimisation mobile
        """
        self.response_cache.clear()
        logger.info("Service d'optimisation mobile arrêté")
