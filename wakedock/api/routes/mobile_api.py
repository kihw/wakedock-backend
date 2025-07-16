"""
API routes optimisées pour clients mobiles - Version 0.2.6
"""
import json
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Response, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from wakedock.core.mobile_optimization_service import (
    MobileOptimizationService, 
    ClientType, 
    CompressionType
)

logger = logging.getLogger(__name__)

# Router pour les endpoints mobile
router = APIRouter(prefix="/mobile")

# Instance globale du service d'optimisation mobile
mobile_service: Optional[MobileOptimizationService] = None

def get_mobile_service() -> MobileOptimizationService:
    """Dependency pour obtenir le service d'optimisation mobile"""
    global mobile_service
    if not mobile_service:
        mobile_service = MobileOptimizationService()
    return mobile_service

# Modèles Pydantic pour les réponses

class ClientInfoResponse(BaseModel):
    """Informations sur le client détecté"""
    client_type: str
    compression_support: bool
    optimal_format: Dict[str, Any]
    recommendations: Dict[str, Any]

class PreferencesRequest(BaseModel):
    """Requête pour mise à jour des préférences"""
    theme: Optional[str] = Field(None, regex="^(light|dark|auto)$")
    layout: Optional[str] = Field(None, regex="^(default|compact|minimal)$")
    notifications: Optional[Dict[str, Any]] = None
    data_usage: Optional[Dict[str, Any]] = None

class OptimizedContainersResponse(BaseModel):
    """Réponse optimisée pour la liste des conteneurs"""
    containers: list
    total_count: int
    client_type: str
    compression_applied: bool
    response_size: str

class OptimizedLogsResponse(BaseModel):
    """Réponse optimisée pour les logs"""
    logs: list
    total_count: int
    truncated: bool
    client_type: str
    compression_applied: bool

class CompressionStatsResponse(BaseModel):
    """Statistiques de compression"""
    total_requests: int
    compressed_responses: int
    compression_ratio: float
    bandwidth_saved: int
    cache_size: int
    active_clients: int

# Middleware pour détection client et optimisation
async def optimize_response_middleware(
    request: Request,
    response: Response,
    service: MobileOptimizationService = Depends(get_mobile_service)
):
    """
    Middleware pour optimiser automatiquement les réponses
    """
    # Détecter le type de client
    client_type = service.detect_client_type(request)
    
    # Ajouter des headers informatifs
    response.headers["X-Client-Type"] = client_type.value
    response.headers["X-Optimized-Response"] = "true"
    
    return response

@router.get("/client-info", response_model=ClientInfoResponse)
async def get_client_info(
    request: Request,
    service: MobileOptimizationService = Depends(get_mobile_service)
):
    """Analyse le client et retourne les informations d'optimisation"""
    try:
        client_type = service.detect_client_type(request)
        
        # Vérifier le support de compression
        accept_encoding = request.headers.get("accept-encoding", "").lower()
        compression_support = "gzip" in accept_encoding or "br" in accept_encoding
        
        # Obtenir les formats optimaux pour ce client
        optimal_formats = {
            "containers": service.get_optimal_response_format(client_type, "containers"),
            "logs": service.get_optimal_response_format(client_type, "logs"),
            "metrics": service.get_optimal_response_format(client_type, "metrics")
        }
        
        # Recommandations basées sur le type de client
        recommendations = {
            "enable_compression": compression_support,
            "use_pagination": client_type in [ClientType.MOBILE, ClientType.PWA],
            "reduce_polling": client_type == ClientType.MOBILE,
            "enable_offline": client_type == ClientType.PWA,
            "lazy_loading": True
        }
        
        return ClientInfoResponse(
            client_type=client_type.value,
            compression_support=compression_support,
            optimal_format=optimal_formats,
            recommendations=recommendations
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse du client: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'analyse du client")

@router.get("/containers", response_model=OptimizedContainersResponse)
async def get_optimized_containers(
    request: Request,
    response: Response,
    limit: Optional[int] = Query(None, description="Limite personnalisée"),
    include_details: Optional[bool] = Query(None, description="Inclure les détails"),
    service: MobileOptimizationService = Depends(get_mobile_service)
):
    """Récupère la liste des conteneurs optimisée pour le client"""
    try:
        client_type = service.detect_client_type(request)
        
        # Simuler des données de conteneurs (à remplacer par vraies données)
        containers_data = [
            {
                "id": f"container_{i}",
                "name": f"app-{i}",
                "status": "running" if i % 2 == 0 else "stopped",
                "cpu_percent": 15.5 + i * 2,
                "memory_usage": 128 + i * 32,
                "network": {"in": 1024 * i, "out": 2048 * i},
                "disk": {"read": 512 * i, "write": 256 * i},
                "created": "2025-07-16T10:00:00Z",
                "image": f"nginx:{i}.0",
                "ports": [f"808{i}:80"]
            }
            for i in range(1, 101)  # Simuler 100 conteneurs
        ]
        
        # Optimiser les données pour le client
        optimized_data = service.optimize_data_for_client(
            containers_data, client_type, "containers"
        )
        
        # Appliquer limite personnalisée si fournie
        if limit:
            optimized_data = optimized_data[:limit]
        
        # Préparer la réponse JSON
        response_data = {
            "containers": optimized_data,
            "total_count": len(containers_data),
            "client_type": client_type.value,
            "compression_applied": False,
            "response_size": "0 KB"
        }
        
        # Convertir en JSON pour calculer la taille
        json_data = json.dumps(response_data).encode('utf-8')
        original_size = len(json_data)
        
        # Vérifier si compression nécessaire
        compression_type = service.should_compress_response(request, original_size)
        
        if compression_type != CompressionType.NONE:
            compressed_data = service.compress_response(json_data, compression_type)
            response_data["compression_applied"] = True
            
            # Définir les headers de compression
            if compression_type == CompressionType.GZIP:
                response.headers["content-encoding"] = "gzip"
            elif compression_type == CompressionType.BROTLI:
                response.headers["content-encoding"] = "br"
                
            # Retourner réponse compressée
            return Response(
                content=compressed_data,
                media_type="application/json",
                headers=dict(response.headers)
            )
        
        # Mettre à jour la taille dans la réponse
        response_data["response_size"] = f"{original_size / 1024:.1f} KB"
        
        return response_data
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des conteneurs optimisés: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des données")

@router.get("/logs", response_model=OptimizedLogsResponse)
async def get_optimized_logs(
    request: Request,
    response: Response,
    container_id: Optional[str] = Query(None, description="ID du conteneur"),
    level: Optional[str] = Query(None, description="Niveau de log"),
    limit: Optional[int] = Query(None, description="Limite personnalisée"),
    service: MobileOptimizationService = Depends(get_mobile_service)
):
    """Récupère les logs optimisés pour le client"""
    try:
        client_type = service.detect_client_type(request)
        
        # Simuler des données de logs
        logs_data = [
            {
                "timestamp": f"2025-07-16T10:{i:02d}:00Z",
                "level": ["INFO", "WARN", "ERROR", "DEBUG"][i % 4],
                "message": f"Message de log numéro {i} avec des détails sur l'opération effectuée dans le conteneur. " * (3 if i % 5 == 0 else 1),
                "container": container_id or f"container_{i % 10}",
                "source": "app",
                "thread": f"thread-{i % 4}",
                "file": f"app.py:{100 + i}",
                "function": "process_request"
            }
            for i in range(1, 501)  # Simuler 500 logs
        ]
        
        # Filtrer par niveau si spécifié
        if level:
            logs_data = [log for log in logs_data if log["level"].lower() == level.lower()]
        
        # Filtrer par conteneur si spécifié
        if container_id:
            logs_data = [log for log in logs_data if log["container"] == container_id]
        
        # Optimiser les données pour le client
        optimized_logs = service.optimize_data_for_client(
            logs_data, client_type, "logs"
        )
        
        # Appliquer limite personnalisée si fournie
        if limit:
            optimized_logs = optimized_logs[:limit]
        
        # Vérifier si des logs ont été tronqués
        format_config = service.get_optimal_response_format(client_type, "logs")
        truncated = (
            "truncate_message" in format_config and 
            format_config["truncate_message"] and
            any("..." in log.get("message", "") for log in optimized_logs)
        )
        
        response_data = {
            "logs": optimized_logs,
            "total_count": len(logs_data),
            "truncated": truncated,
            "client_type": client_type.value,
            "compression_applied": False
        }
        
        # Compression si nécessaire
        json_data = json.dumps(response_data).encode('utf-8')
        compression_type = service.should_compress_response(request, len(json_data))
        
        if compression_type != CompressionType.NONE:
            compressed_data = service.compress_response(json_data, compression_type)
            response_data["compression_applied"] = True
            
            if compression_type == CompressionType.GZIP:
                response.headers["content-encoding"] = "gzip"
            elif compression_type == CompressionType.BROTLI:
                response.headers["content-encoding"] = "br"
                
            return Response(
                content=compressed_data,
                media_type="application/json",
                headers=dict(response.headers)
            )
        
        return response_data
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs optimisés: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des logs")

@router.get("/preferences/{user_id}")
async def get_user_preferences(
    user_id: str,
    service: MobileOptimizationService = Depends(get_mobile_service)
):
    """Récupère les préférences utilisateur"""
    try:
        preferences = service.get_user_preferences(user_id)
        return {"user_id": user_id, "preferences": preferences}
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des préférences: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des préférences")

@router.put("/preferences/{user_id}")
async def update_user_preferences(
    user_id: str,
    request: PreferencesRequest,
    service: MobileOptimizationService = Depends(get_mobile_service)
):
    """Met à jour les préférences utilisateur"""
    try:
        # Convertir la requête en dictionnaire, en excluant les valeurs None
        preferences_data = {
            k: v for k, v in request.dict().items() 
            if v is not None
        }
        
        success = service.update_user_preferences(user_id, preferences_data)
        
        if success:
            updated_preferences = service.get_user_preferences(user_id)
            return {
                "success": True,
                "user_id": user_id,
                "preferences": updated_preferences
            }
        else:
            raise HTTPException(status_code=500, detail="Échec de la mise à jour des préférences")
            
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des préférences: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour des préférences")

@router.get("/stats/compression", response_model=CompressionStatsResponse)
async def get_compression_stats(
    service: MobileOptimizationService = Depends(get_mobile_service)
):
    """Récupère les statistiques de compression"""
    try:
        stats = service.get_compression_stats()
        return CompressionStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des statistiques")

@router.delete("/cache/clear")
async def clear_mobile_cache(
    service: MobileOptimizationService = Depends(get_mobile_service)
):
    """Vide le cache mobile"""
    try:
        cleared_count = service.clear_cache()
        return {
            "success": True,
            "message": "Cache vidé avec succès",
            "cleared_entries": cleared_count
        }
    except Exception as e:
        logger.error(f"Erreur lors du vidage du cache: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors du vidage du cache")

@router.get("/health")
async def mobile_api_health(
    service: MobileOptimizationService = Depends(get_mobile_service)
):
    """État de santé de l'API mobile"""
    try:
        stats = service.get_compression_stats()
        return {
            "status": "healthy",
            "service": "mobile-optimization",
            "version": "0.2.6",
            "stats": {
                "total_requests": stats["total_requests"],
                "compression_ratio": f"{stats['compression_ratio']:.2%}",
                "active_clients": stats["active_clients"]
            },
            "features": {
                "compression": True,
                "client_detection": True,
                "data_optimization": True,
                "preferences": True
            }
        }
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de santé: {e}")
        raise HTTPException(status_code=500, detail="Erreur du service")

# Route de test pour développement
@router.get("/test/simulate-client")
async def simulate_client_type(
    client_type: str = Query(..., description="Type de client à simuler"),
    request: Request = None,
    service: MobileOptimizationService = Depends(get_mobile_service)
):
    """Simule un type de client pour tests"""
    try:
        # Simuler différents types de clients
        client_types = {
            "mobile": ClientType.MOBILE,
            "tablet": ClientType.TABLET,
            "desktop": ClientType.DESKTOP,
            "pwa": ClientType.PWA
        }
        
        if client_type not in client_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Type de client invalide. Types supportés: {list(client_types.keys())}"
            )
        
        simulated_type = client_types[client_type]
        
        # Obtenir les formats optimaux pour ce type
        formats = {
            "containers": service.get_optimal_response_format(simulated_type, "containers"),
            "logs": service.get_optimal_response_format(simulated_type, "logs"),
            "metrics": service.get_optimal_response_format(simulated_type, "metrics")
        }
        
        return {
            "simulated_client": client_type,
            "optimal_formats": formats,
            "message": f"Simulation du client {client_type} réussie"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la simulation: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la simulation")
