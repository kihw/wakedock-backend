"""
Middleware optimisé pour Next.js SSR/RSC - Version 0.6.4
Optimisations spécifiques pour les performances avec App Router
"""
import gzip
import time
from typing import Callable, Dict, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import logging

logger = logging.getLogger(__name__)

class NextJSOptimizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware spécialement optimisé pour les interactions avec Next.js
    """
    
    def __init__(self, app, config: Optional[Dict] = None):
        super().__init__(app)
        self.config = config or {}
        self.compression_threshold = self.config.get('compression_threshold', 1024)
        self.cache_control_default = self.config.get('cache_control', 'public, max-age=60')
        
        # Métriques de performance
        self.request_count = 0
        self.total_response_time = 0.0
        self.cache_hits = 0
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Détection des requêtes Next.js SSR
        is_ssr_request = self._is_ssr_request(request)
        is_api_request = request.url.path.startswith('/api/')
        
        # Pre-processing pour les requêtes SSR
        if is_ssr_request:
            request.state.nextjs_ssr = True
            request.state.start_time = start_time
        
        # Traitement de la requête
        try:
            response = await call_next(request)
            
            # Post-processing pour optimiser la réponse
            if is_ssr_request:
                response = await self._optimize_ssr_response(request, response)
            elif is_api_request:
                response = await self._optimize_api_response(request, response)
            
            # Ajout des headers de performance
            response = self._add_performance_headers(request, response, start_time)
            
            # Métriques
            self._update_metrics(start_time)
            
            return response
            
        except Exception as e:
            logger.error(f"Erreur dans NextJSOptimizationMiddleware: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "Erreur serveur interne"},
                headers=self._get_error_headers()
            )
    
    def _is_ssr_request(self, request: Request) -> bool:
        """Détecte si c'est une requête SSR de Next.js"""
        user_agent = request.headers.get('user-agent', '').lower()
        
        # Détection des requêtes Next.js
        nextjs_indicators = [
            'next.js',
            'nextjs',
            request.headers.get('x-nextjs-page'),
            request.headers.get('x-middleware-request-id')
        ]
        
        # Détection des endpoints SSR
        ssr_paths = [
            '/nextjs/',
            '/dashboard/ssr',
            '/components/',
            '/stream/'
        ]
        
        return (
            any(indicator for indicator in nextjs_indicators if indicator) or
            any(path in request.url.path for path in ssr_paths) or
            'rsc' in request.url.path.lower()
        )
    
    async def _optimize_ssr_response(self, request: Request, response: Response) -> Response:
        """Optimise les réponses pour SSR Next.js"""
        
        # Headers spécifiques SSR
        ssr_headers = {
            'X-SSR-Optimized': 'true',
            'X-Next-Cache': 'HIT' if hasattr(request.state, 'cache_hit') else 'MISS',
            'Vary': 'User-Agent, Accept-Encoding, Accept',
        }
        
        # Cache Control optimisé pour SSR
        if request.url.path.startswith('/nextjs/dashboard'):
            ssr_headers['Cache-Control'] = 'public, max-age=60, stale-while-revalidate=300'
        elif '/rsc' in request.url.path:
            ssr_headers['Cache-Control'] = 'public, max-age=300, stale-while-revalidate=600'
        elif '/stream/' in request.url.path:
            ssr_headers['Cache-Control'] = 'no-cache, no-store'
            ssr_headers['Connection'] = 'keep-alive'
        
        # Compression pour les réponses importantes
        if hasattr(response, 'body') and len(response.body) > self.compression_threshold:
            if 'gzip' in request.headers.get('accept-encoding', ''):
                compressed_body = gzip.compress(response.body)
                response.body = compressed_body
                ssr_headers['Content-Encoding'] = 'gzip'
                ssr_headers['Content-Length'] = str(len(compressed_body))
        
        # Application des headers
        for key, value in ssr_headers.items():
            response.headers[key] = value
        
        return response
    
    async def _optimize_api_response(self, request: Request, response: Response) -> Response:
        """Optimise les réponses API pour Next.js"""
        
        api_headers = {
            'X-API-Version': '0.6.4',
            'Access-Control-Allow-Origin': '*',  # TODO: Configurer selon l'environnement
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
        }
        
        # CORS préflights
        if request.method == 'OPTIONS':
            api_headers['Access-Control-Max-Age'] = '86400'
        
        # Cache pour les données statiques
        if request.method == 'GET' and '/static/' in request.url.path:
            api_headers['Cache-Control'] = 'public, max-age=86400, immutable'
        
        # Application des headers
        for key, value in api_headers.items():
            response.headers[key] = value
        
        return response
    
    def _add_performance_headers(self, request: Request, response: Response, start_time: float) -> Response:
        """Ajoute les headers de performance"""
        
        response_time = time.time() - start_time
        
        performance_headers = {
            'X-Response-Time': f"{response_time:.3f}s",
            'X-Request-ID': getattr(request.state, 'request_id', 'unknown'),
            'X-Server-Timing': f"total;dur={response_time * 1000:.1f}",
        }
        
        # Informations de cache
        if hasattr(request.state, 'cache_hit'):
            performance_headers['X-Cache-Status'] = 'HIT'
            self.cache_hits += 1
        else:
            performance_headers['X-Cache-Status'] = 'MISS'
        
        # Warnings de performance
        if response_time > 1.0:
            performance_headers['X-Performance-Warning'] = 'slow-response'
            logger.warning(f"Réponse lente détectée: {response_time:.3f}s pour {request.url.path}")
        
        # Application des headers
        for key, value in performance_headers.items():
            response.headers[key] = value
        
        return response
    
    def _get_error_headers(self) -> Dict[str, str]:
        """Headers pour les réponses d'erreur"""
        return {
            'X-Error-Middleware': 'NextJSOptimization',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Content-Type': 'application/json'
        }
    
    def _update_metrics(self, start_time: float):
        """Met à jour les métriques de performance"""
        response_time = time.time() - start_time
        self.request_count += 1
        self.total_response_time += response_time
    
    def get_performance_stats(self) -> Dict[str, float]:
        """Retourne les statistiques de performance du middleware"""
        if self.request_count == 0:
            return {
                'total_requests': 0,
                'average_response_time': 0.0,
                'cache_hit_ratio': 0.0,
            }
        
        return {
            'total_requests': self.request_count,
            'average_response_time': self.total_response_time / self.request_count,
            'cache_hit_ratio': self.cache_hits / self.request_count,
            'total_cache_hits': self.cache_hits,
        }


class StreamingOptimizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour optimiser le streaming vers Next.js
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.active_streams = 0
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        
        # Détection des requêtes de streaming
        is_streaming = (
            '/stream/' in request.url.path or
            'text/event-stream' in request.headers.get('accept', '') or
            'application/x-ndjson' in request.headers.get('accept', '')
        )
        
        if is_streaming:
            self.active_streams += 1
            request.state.is_streaming = True
        
        try:
            response = await call_next(request)
            
            if is_streaming:
                response = self._optimize_streaming_response(response)
            
            return response
            
        except Exception as e:
            logger.error(f"Erreur dans StreamingOptimizationMiddleware: {e}")
            raise
            
        finally:
            if is_streaming:
                self.active_streams -= 1
    
    def _optimize_streaming_response(self, response: Response) -> Response:
        """Optimise les réponses de streaming"""
        
        # Headers pour le streaming optimisé
        streaming_headers = {
            'X-Accel-Buffering': 'no',  # Nginx
            'Cache-Control': 'no-cache, no-store',
            'Connection': 'keep-alive',
            'Keep-Alive': 'timeout=300, max=1000',
            'X-Content-Type-Options': 'nosniff',
        }
        
        # Configuration spécifique selon le type de streaming
        if hasattr(response, 'media_type'):
            if response.media_type == 'text/event-stream':
                streaming_headers.update({
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Cache-Control',
                    'Access-Control-Expose-Headers': 'X-Stream-ID',
                })
        
        # Application des headers
        for key, value in streaming_headers.items():
            response.headers[key] = value
        
        return response
    
    def get_streaming_stats(self) -> Dict[str, int]:
        """Retourne les statistiques de streaming"""
        return {
            'active_streams': self.active_streams,
        }
