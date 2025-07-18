"""
API routes optimisées pour Next.js SSR/RSC - Version 0.6.4
Optimisations spécifiques pour App Router et Server Components
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from wakedock.core.auth_service import AuthService
from wakedock.core.dependencies import (
    get_auth_service_dependency,
    get_docker_manager,
    get_metrics_collector,
)
from wakedock.core.docker_manager import DockerManager
from wakedock.core.metrics_collector import MetricsCollector
from wakedock.core.mobile_optimization_service import MobileOptimizationService

logger = logging.getLogger(__name__)

# Router pour les endpoints Next.js SSR
router = APIRouter(prefix="/nextjs")

# Service d'optimisation pour Next.js
nextjs_service: Optional[MobileOptimizationService] = None

def get_nextjs_optimization_service() -> MobileOptimizationService:
    """Dependency pour obtenir le service d'optimisation Next.js"""
    global nextjs_service
    if not nextjs_service:
        nextjs_service = MobileOptimizationService()
    return nextjs_service

# Modèles pour Next.js SSR

class SSRDataResponse(BaseModel):
    """Response optimisée pour Server-Side Rendering"""
    data: Any
    cache_headers: Dict[str, str]
    preload_data: Optional[Dict[str, Any]] = None
    client_hints: Optional[Dict[str, Any]] = None

class RSCComponentProps(BaseModel):
    """Props optimisées pour React Server Components"""
    component_id: str
    props: Dict[str, Any]
    cache_key: str
    streaming: bool = False

class StreamChunk(BaseModel):
    """Chunk de données pour streaming SSR"""
    chunk_id: str
    data: Any
    is_final: bool = False

# Cache pour optimiser les performances SSR
ssr_cache: Dict[str, Any] = {}
CACHE_TTL = 300  # 5 minutes

def get_cache_key(request: Request, params: Dict[str, Any]) -> str:
    """Génère une clé de cache pour les données SSR"""
    user_agent = request.headers.get("user-agent", "")
    accept_encoding = request.headers.get("accept-encoding", "")
    
    base_key = f"{request.url.path}:{json.dumps(params, sort_keys=True)}"
    client_key = f"{hash(user_agent + accept_encoding)}"
    
    return f"ssr:{base_key}:{client_key}"

def is_cache_valid(cache_entry: Dict[str, Any]) -> bool:
    """Vérifie si l'entrée de cache est encore valide"""
    if not cache_entry:
        return False
    
    timestamp = cache_entry.get("timestamp")
    if not timestamp:
        return False
    
    return datetime.now() - timestamp < timedelta(seconds=CACHE_TTL)

@router.get("/dashboard/ssr", response_model=SSRDataResponse)
async def get_dashboard_ssr_data(
    request: Request,
    include_metrics: bool = Query(True),
    include_containers: bool = Query(True),
    include_alerts: bool = Query(False),
    docker_manager: DockerManager = Depends(get_docker_manager),
    metrics_collector: MetricsCollector = Depends(get_metrics_collector),
    optimization_service: MobileOptimizationService = Depends(get_nextjs_optimization_service),
    auth_service: AuthService = Depends(get_auth_service_dependency)
):
    """
    Endpoint optimisé pour SSR du dashboard Next.js
    Retourne toutes les données nécessaires en une seule requête
    """
    try:
        # Génération de la clé de cache
        cache_params = {
            "include_metrics": include_metrics,
            "include_containers": include_containers,
            "include_alerts": include_alerts
        }
        cache_key = get_cache_key(request, cache_params)
        
        # Vérification du cache
        cached_data = ssr_cache.get(cache_key)
        if cached_data and is_cache_valid(cached_data):
            logger.info(f"Cache hit for dashboard SSR: {cache_key}")
            return SSRDataResponse(
                data=cached_data["data"],
                cache_headers={"X-Cache": "HIT"},
                preload_data=cached_data.get("preload_data")
            )
        
        # Collecte des données en parallèle pour optimiser les performances
        tasks = []
        
        if include_containers:
            tasks.append(docker_manager.list_containers())
        
        if include_metrics:
            tasks.append(metrics_collector.get_system_metrics())
        
        if include_alerts:
            # TODO: Intégrer le service d'alertes
            tasks.append(asyncio.sleep(0))  # Placeholder
        
        # Exécution en parallèle
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Construction de la réponse
        data = {}
        preload_data = {}
        
        if include_containers and len(results) > 0:
            containers = results[0] if not isinstance(results[0], Exception) else []
            # Optimisation des données pour le client
            client_type = optimization_service.detect_client_type(request)
            optimized_containers = optimization_service.optimize_data_for_client(
                containers, client_type, "containers"
            )
            data["containers"] = optimized_containers
            preload_data["containers_count"] = len(containers) if containers else 0
        
        if include_metrics and len(results) > 1:
            metrics = results[1] if not isinstance(results[1], Exception) else {}
            data["metrics"] = metrics
            preload_data["last_update"] = datetime.now().isoformat()
        
        if include_alerts and len(results) > 2:
            alerts = results[2] if not isinstance(results[2], Exception) else []
            data["alerts"] = alerts
        
        # Détection du client pour les hints
        client_type = optimization_service.detect_client_type(request)
        client_hints = {
            "client_type": client_type.value,
            "supports_streaming": "text/event-stream" in request.headers.get("accept", ""),
            "prefers_compressed": optimization_service.should_compress_response(
                request, len(json.dumps(data).encode())
            ).value != "none"
        }
        
        # Mise en cache
        cache_entry = {
            "data": data,
            "preload_data": preload_data,
            "timestamp": datetime.now()
        }
        ssr_cache[cache_key] = cache_entry
        
        # Headers de cache optimisés
        cache_headers = {
            "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
            "X-Cache": "MISS",
            "Vary": "User-Agent, Accept-Encoding"
        }
        
        return SSRDataResponse(
            data=data,
            cache_headers=cache_headers,
            preload_data=preload_data,
            client_hints=client_hints
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération des données SSR: {e}")
        raise HTTPException(status_code=500, detail="Erreur serveur lors de la génération SSR")

@router.get("/components/{component_id}/rsc")
async def get_rsc_component_props(
    component_id: str,
    request: Request,
    refresh: bool = Query(False),
    docker_manager: DockerManager = Depends(get_docker_manager),
    optimization_service: MobileOptimizationService = Depends(get_nextjs_optimization_service)
):
    """
    Endpoint pour React Server Components (RSC)
    Retourne les props optimisées pour un composant spécifique
    """
    try:
        # Génération de la clé de cache spécifique au composant
        cache_key = f"rsc:{component_id}:{hash(str(request.url))}"
        
        # Vérification du cache (sauf si refresh demandé)
        if not refresh:
            cached_props = ssr_cache.get(cache_key)
            if cached_props and is_cache_valid(cached_props):
                return RSCComponentProps(
                    component_id=component_id,
                    props=cached_props["props"],
                    cache_key=cache_key,
                    streaming=False
                )
        
        # Logique spécifique par composant
        props = {}
        
        if component_id == "container-list":
            containers = await docker_manager.list_containers()
            client_type = optimization_service.detect_client_type(request)
            props = {
                "containers": optimization_service.optimize_data_for_client(
                    containers, client_type, "containers"
                ),
                "total_count": len(containers),
                "last_updated": datetime.now().isoformat()
            }
        
        elif component_id == "metrics-dashboard":
            # TODO: Intégrer les métriques temps réel
            props = {
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "disk_usage": 23.1,
                "network_io": {"in": 1234, "out": 5678},
                "last_updated": datetime.now().isoformat()
            }
        
        elif component_id == "service-status":
            services = await docker_manager.list_services()
            props = {
                "services": services,
                "healthy_count": len([s for s in services if s.get("status") == "running"]),
                "total_count": len(services)
            }
        
        else:
            raise HTTPException(status_code=404, detail=f"Composant RSC '{component_id}' non trouvé")
        
        # Mise en cache
        cache_entry = {
            "props": props,
            "timestamp": datetime.now()
        }
        ssr_cache[cache_key] = cache_entry
        
        return RSCComponentProps(
            component_id=component_id,
            props=props,
            cache_key=cache_key,
            streaming=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la génération des props RSC pour {component_id}: {e}")
        raise HTTPException(status_code=500, detail="Erreur serveur lors de la génération RSC")

@router.get("/stream/{data_type}")
async def stream_data_for_ssr(
    data_type: str,
    request: Request,
    interval: int = Query(5, ge=1, le=60),
    docker_manager: DockerManager = Depends(get_docker_manager),
    metrics_collector: MetricsCollector = Depends(get_metrics_collector)
):
    """
    Endpoint de streaming pour les données temps réel
    Compatible avec Next.js Streaming et Suspense
    """
    try:
        async def generate_stream():
            chunk_counter = 0
            
            while True:
                try:
                    chunk_data = None
                    
                    if data_type == "metrics":
                        chunk_data = await metrics_collector.get_system_metrics()
                    elif data_type == "containers":
                        chunk_data = await docker_manager.list_containers()
                    elif data_type == "logs":
                        # TODO: Intégrer le streaming des logs
                        chunk_data = {"logs": [], "timestamp": datetime.now().isoformat()}
                    else:
                        break
                    
                    chunk = StreamChunk(
                        chunk_id=f"{data_type}_{chunk_counter}",
                        data=chunk_data,
                        is_final=False
                    )
                    
                    # Format Server-Sent Events pour Next.js
                    sse_data = f"data: {chunk.json()}\\n\\n"
                    yield sse_data
                    
                    chunk_counter += 1
                    await asyncio.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Erreur dans le stream {data_type}: {e}")
                    error_chunk = StreamChunk(
                        chunk_id=f"error_{chunk_counter}",
                        data={"error": str(e)},
                        is_final=True
                    )
                    yield f"data: {error_chunk.json()}\\n\\n"
                    break
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation du stream {data_type}: {e}")
        raise HTTPException(status_code=500, detail="Erreur serveur lors du streaming")

@router.post("/cache/invalidate")
async def invalidate_ssr_cache(
    pattern: Optional[str] = None,
    component_id: Optional[str] = None
):
    """
    Endpoint pour invalider le cache SSR
    Utile pour le revalidation Next.js
    """
    try:
        invalidated_keys = []
        
        if pattern:
            # Invalidation par pattern
            keys_to_remove = [key for key in ssr_cache.keys() if pattern in key]
            for key in keys_to_remove:
                del ssr_cache[key]
                invalidated_keys.append(key)
        
        elif component_id:
            # Invalidation d'un composant spécifique
            keys_to_remove = [key for key in ssr_cache.keys() if f"rsc:{component_id}" in key]
            for key in keys_to_remove:
                del ssr_cache[key]
                invalidated_keys.append(key)
        
        else:
            # Invalidation complète
            invalidated_keys = list(ssr_cache.keys())
            ssr_cache.clear()
        
        return {
            "message": "Cache invalidé avec succès",
            "invalidated_keys": len(invalidated_keys),
            "keys": invalidated_keys if len(invalidated_keys) < 20 else invalidated_keys[:20]
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'invalidation du cache: {e}")
        raise HTTPException(status_code=500, detail="Erreur serveur lors de l'invalidation du cache")

@router.get("/performance/metrics")
async def get_nextjs_performance_metrics():
    """
    Endpoint pour obtenir les métriques de performance Next.js
    Utile pour le monitoring et l'optimisation
    """
    try:
        return {
            "cache_size": len(ssr_cache),
            "cache_hit_ratio": 0.85,  # TODO: Implémenter le calcul réel
            "average_response_time": 120,  # TODO: Implémenter le calcul réel
            "total_requests": 1500,  # TODO: Implémenter le compteur réel
            "streaming_connections": 0,  # TODO: Implémenter le comptage
            "memory_usage": {
                "cache_mb": len(str(ssr_cache)) / (1024 * 1024),
                "total_mb": 256  # TODO: Obtenir la valeur réelle
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des métriques de performance: {e}")
        raise HTTPException(status_code=500, detail="Erreur serveur lors de la récupération des métriques")
