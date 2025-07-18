"""
Middleware de compression automatique pour WakeDock v0.6.5
=========================================================
Compression intelligente des réponses API selon le type de client
"""

import gzip
import logging
from typing import Callable, Dict, Any
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from wakedock.core.mobile_optimization_service import MobileOptimizationService, CompressionType

logger = logging.getLogger(__name__)

class CompressionMiddleware(BaseHTTPMiddleware):
    """
    Middleware de compression automatique pour optimiser les réponses
    selon le type de client (mobile, desktop, PWA)
    """
    
    def __init__(self, app, compression_level: int = 6, min_size: int = 1024):
        super().__init__(app)
        self.compression_level = compression_level
        self.min_size = min_size
        self.mobile_service = MobileOptimizationService()
        self.stats = {
            "total_requests": 0,
            "compressed_responses": 0,
            "bytes_saved": 0,
            "compression_ratio": 0.0
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Traite la requête et compresse la réponse si nécessaire
        """
        # Incrémenter les stats
        self.stats["total_requests"] += 1
        
        # Détecter le type de client
        client_type = self.mobile_service.detect_client_type(request)
        
        # Traiter la requête
        response = await call_next(request)
        
        # Vérifier si la compression est nécessaire
        if self._should_compress(request, response):
            response = await self._compress_response(request, response, client_type)
        
        # Ajouter des headers informatifs
        response.headers["X-Client-Type"] = client_type.value
        response.headers["X-WakeDock-Version"] = "0.6.5"
        
        return response
    
    def _should_compress(self, request: Request, response: Response) -> bool:
        """
        Détermine si la réponse doit être compressée
        """
        # Vérifier les headers d'acceptation
        accept_encoding = request.headers.get("accept-encoding", "").lower()
        if "gzip" not in accept_encoding:
            return False
        
        # Vérifier le type de contenu
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith(("application/json", "text/", "application/javascript")):
            return False
        
        # Vérifier si déjà compressé
        if "content-encoding" in response.headers:
            return False
        
        # Vérifier la taille minimum
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) < self.min_size:
            return False
        
        return True
    
    async def _compress_response(self, request: Request, response: Response, client_type) -> Response:
        """
        Compresse la réponse selon le type de client
        """
        try:
            # Obtenir le contenu de la réponse
            if hasattr(response, 'body'):
                content = response.body
            else:
                # Pour les responses streaming
                content = b""
                async for chunk in response.body_iterator:
                    content += chunk
            
            if isinstance(content, str):
                content = content.encode('utf-8')
            
            original_size = len(content)
            
            # Compresser avec gzip
            compressed_content = gzip.compress(content, compresslevel=self.compression_level)
            compressed_size = len(compressed_content)
            
            # Calculer les stats
            bytes_saved = original_size - compressed_size
            compression_ratio = (bytes_saved / original_size) * 100 if original_size > 0 else 0
            
            # Mettre à jour les statistiques
            self.stats["compressed_responses"] += 1
            self.stats["bytes_saved"] += bytes_saved
            self.stats["compression_ratio"] = (
                self.stats["bytes_saved"] / 
                (self.stats["total_requests"] * 1024)  # Estimation moyenne
            ) * 100
            
            # Créer la nouvelle réponse compressée
            compressed_response = Response(
                content=compressed_content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
            
            # Ajouter les headers de compression
            compressed_response.headers["content-encoding"] = "gzip"
            compressed_response.headers["content-length"] = str(compressed_size)
            compressed_response.headers["x-original-size"] = str(original_size)
            compressed_response.headers["x-compression-ratio"] = f"{compression_ratio:.1f}%"
            compressed_response.headers["x-bytes-saved"] = str(bytes_saved)
            
            logger.info(
                f"Compression appliquée: {original_size} -> {compressed_size} bytes "
                f"({compression_ratio:.1f}% économisé) pour client {client_type.value}"
            )
            
            return compressed_response
            
        except Exception as e:
            logger.error(f"Erreur lors de la compression: {e}")
            # Retourner la réponse originale en cas d'erreur
            return response
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de compression
        """
        return {
            "total_requests": self.stats["total_requests"],
            "compressed_responses": self.stats["compressed_responses"],
            "compression_rate": (
                self.stats["compressed_responses"] / self.stats["total_requests"] * 100
                if self.stats["total_requests"] > 0 else 0
            ),
            "bytes_saved": self.stats["bytes_saved"],
            "average_compression_ratio": self.stats["compression_ratio"],
            "compression_level": self.compression_level,
            "min_size": self.min_size
        }
    
    def reset_stats(self):
        """
        Remet à zéro les statistiques
        """
        self.stats = {
            "total_requests": 0,
            "compressed_responses": 0,
            "bytes_saved": 0,
            "compression_ratio": 0.0
        }


class MobileOptimizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware d'optimisation spécifique pour les clients mobiles
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.mobile_service = MobileOptimizationService()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Optimise la réponse selon le type de client mobile
        """
        # Détecter le type de client
        client_type = self.mobile_service.detect_client_type(request)
        
        # Ajouter le type de client à la requête
        request.state.client_type = client_type
        
        # Traiter la requête
        response = await call_next(request)
        
        # Optimiser la réponse pour les clients mobiles
        if client_type.value in ["mobile", "pwa"]:
            response = await self._optimize_mobile_response(request, response, client_type)
        
        return response
    
    async def _optimize_mobile_response(self, request: Request, response: Response, client_type) -> Response:
        """
        Optimise la réponse pour les clients mobiles
        """
        try:
            # Ajouter des headers d'optimisation mobile
            response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutes
            response.headers["X-Mobile-Optimized"] = "true"
            response.headers["X-PWA-Cache"] = "enabled" if client_type.value == "pwa" else "disabled"
            
            # Pour les PWA, ajouter des headers spécifiques
            if client_type.value == "pwa":
                response.headers["Service-Worker-Allowed"] = "/"
                response.headers["X-Offline-Support"] = "enabled"
            
            # Optimiser pour les connexions lentes
            if client_type.value == "mobile":
                response.headers["X-Data-Saver"] = "enabled"
                response.headers["X-Reduced-Data"] = "true"
            
            logger.info(f"Optimisation mobile appliquée pour client {client_type.value}")
            
            return response
            
        except Exception as e:
            logger.error(f"Erreur lors de l'optimisation mobile: {e}")
            return response


# Fonction utilitaire pour ajouter les middlewares à l'application
def add_compression_middleware(app, compression_level: int = 6, min_size: int = 1024):
    """
    Ajoute le middleware de compression à l'application FastAPI
    """
    app.add_middleware(CompressionMiddleware, compression_level=compression_level, min_size=min_size)
    logger.info(f"Middleware de compression ajouté (niveau: {compression_level}, taille min: {min_size})")

def add_mobile_optimization_middleware(app):
    """
    Ajoute le middleware d'optimisation mobile à l'application FastAPI
    """
    app.add_middleware(MobileOptimizationMiddleware)
    logger.info("Middleware d'optimisation mobile ajouté")

def add_all_optimization_middlewares(app, compression_level: int = 6, min_size: int = 1024):
    """
    Ajoute tous les middlewares d'optimisation à l'application FastAPI
    """
    add_mobile_optimization_middleware(app)  # Ajouter en premier
    add_compression_middleware(app, compression_level, min_size)  # Ajouter en second
    logger.info("Tous les middlewares d'optimisation ajoutés")
