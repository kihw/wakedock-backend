# 🏗️ Migration Architecture MVC - WakeDock Backend

## 📋 Vue d'ensemble de la migration

### 🎯 Objectif
Migrer l'architecture actuelle de `wakedock-backend/` vers une architecture MVC (Model-View-Controller) propre et maintenable.

### 📊 État actuel
- **Modèles (Models)** : ✅ Partiellement organisés dans `wakedock/models/`
- **Vues (Views)** : ❌ Mélangées avec les contrôleurs dans `wakedock/api/routes/`
- **Contrôleurs (Controllers)** : ❌ Logique métier dispersée dans `wakedock/core/` et `wakedock/api/routes/`

---

## 🚀 PHASE 1: Restructuration des dossiers

### 1.1 Création de la nouvelle structure MVC

```bash
# Créer la nouvelle structure de dossiers
mkdir -p wakedock/controllers/
mkdir -p wakedock/views/
mkdir -p wakedock/middleware/
mkdir -p wakedock/validators/
mkdir -p wakedock/serializers/
mkdir -p wakedock/repositories/
mkdir -p wakedock/services/
```

### 1.2 Organisation des dossiers selon MVC

```
wakedock/
├── models/                    # ✅ Modèles de données (SQLAlchemy)
│   ├── alerts.py
│   ├── audit.py
│   ├── user.py
│   └── ...
├── controllers/               # 🆕 Contrôleurs (logique métier)
│   ├── __init__.py
│   ├── base_controller.py
│   ├── auth_controller.py
│   ├── services_controller.py
│   ├── containers_controller.py
│   ├── alerts_controller.py
│   └── ...
├── views/                     # 🆕 Vues (sérialisation/responses)
│   ├── __init__.py
│   ├── base_view.py
│   ├── auth_views.py
│   ├── services_views.py
│   ├── containers_views.py
│   └── ...
├── repositories/              # 🆕 Couche d'accès aux données
│   ├── __init__.py
│   ├── base_repository.py
│   ├── user_repository.py
│   ├── services_repository.py
│   └── ...
├── services/                  # 🆕 Services métier (logique complexe)
│   ├── __init__.py
│   ├── auth_service.py
│   ├── docker_service.py
│   ├── monitoring_service.py
│   └── ...
├── validators/                # 🆕 Validateurs de données
│   ├── __init__.py
│   ├── auth_validators.py
│   ├── services_validators.py
│   └── ...
├── serializers/               # 🆕 Sérialiseurs (Pydantic)
│   ├── __init__.py
│   ├── auth_serializers.py
│   ├── services_serializers.py
│   └── ...
├── middleware/                # 🆕 Middleware centralisé
│   ├── __init__.py
│   ├── auth_middleware.py
│   ├── logging_middleware.py
│   └── ...
└── api/                       # 🔄 Routes (uniquement routing)
    ├── __init__.py
    ├── routes/
    │   ├── auth.py
    │   ├── services.py
    │   └── ...
    └── app.py
```

---

## 🔄 PHASE 2: Migration des Modèles (Models)

### 2.1 ✅ Modèles déjà organisés
- [x] `wakedock/models/user.py`
- [x] `wakedock/models/alerts.py`
- [x] `wakedock/models/audit.py`
- [x] `wakedock/models/cicd.py`
- [x] `wakedock/models/dashboard.py`
- [x] `wakedock/models/deployment.py`
- [x] `wakedock/models/environment.py`
- [x] `wakedock/models/notification.py`
- [x] `wakedock/models/security.py`
- [x] `wakedock/models/stack.py`
- [x] `wakedock/models/swarm.py`

### 2.2 ✨ Améliorations des modèles
- [ ] **Standardiser les modèles SQLAlchemy**
  - [ ] Ajouter des méthodes `__repr__` cohérentes
  - [ ] Standardiser les relationships
  - [ ] Ajouter des index pour les performances
  - [ ] Implémenter des méthodes de validation

- [ ] **Créer des modèles Pydantic correspondants**
  - [ ] `wakedock/serializers/user_serializers.py`
  - [ ] `wakedock/serializers/services_serializers.py`
  - [ ] `wakedock/serializers/containers_serializers.py`
  - [ ] `wakedock/serializers/alerts_serializers.py`

### 2.3 🔧 Exemple de structure de modèle
```python
# wakedock/models/service.py
from sqlalchemy import Column, String, Integer, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Service(Base):
    __tablename__ = 'services'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    status = Column(String, default='stopped')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Service(id={self.id}, name={self.name}, status={self.status})>"
```

---

## 🎮 PHASE 3: Création des Contrôleurs (Controllers)

### 3.1 🆕 Contrôleur de base
- [ ] **Créer `wakedock/controllers/base_controller.py`**
```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from wakedock.repositories.base_repository import BaseRepository

class BaseController(ABC):
    def __init__(self, repository: BaseRepository):
        self.repository = repository
    
    @abstractmethod
    async def get_all(self, **kwargs) -> List[Any]:
        pass
    
    @abstractmethod
    async def get_by_id(self, id: str) -> Any:
        pass
    
    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> Any:
        pass
    
    @abstractmethod
    async def update(self, id: str, data: Dict[str, Any]) -> Any:
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        pass
```

### 3.2 🔄 Migration des contrôleurs existants
- [ ] **Authentification**
  - [ ] Migrer `wakedock/core/auth_service.py` → `wakedock/controllers/auth_controller.py`
  - [ ] Extraire la logique de `wakedock/api/auth/routes.py`
  - [ ] Créer les méthodes: `login()`, `register()`, `logout()`, `refresh_token()`

- [ ] **Services Docker**
  - [ ] Migrer `wakedock/core/orchestrator.py` → `wakedock/controllers/services_controller.py`
  - [ ] Extraire la logique de `wakedock/api/routes/services.py`
  - [ ] Créer les méthodes: `list_services()`, `get_service()`, `create_service()`, `update_service()`, `delete_service()`, `start_service()`, `stop_service()`, `restart_service()`

- [ ] **Containers**
  - [ ] Migrer `wakedock/core/docker_manager.py` → `wakedock/controllers/containers_controller.py`
  - [ ] Extraire la logique de `wakedock/api/routes/containers.py`
  - [ ] Créer les méthodes: `list_containers()`, `get_container()`, `start_container()`, `stop_container()`, `restart_container()`

- [ ] **Alertes**
  - [ ] Migrer `wakedock/core/alerts_service.py` → `wakedock/controllers/alerts_controller.py`
  - [ ] Créer les méthodes: `create_alert()`, `get_alerts()`, `update_alert()`, `delete_alert()`

- [ ] **Analytics**
  - [ ] Migrer `wakedock/core/advanced_analytics.py` → `wakedock/controllers/analytics_controller.py`
  - [ ] Créer les méthodes: `get_metrics()`, `get_trends()`, `get_performance_data()`

- [ ] **Dashboard**
  - [ ] Migrer `wakedock/core/dashboard_service.py` → `wakedock/controllers/dashboard_controller.py`
  - [ ] Créer les méthodes: `get_dashboard_data()`, `update_layout()`, `create_widget()`

### 3.3 🔧 Exemple de contrôleur
```python
# wakedock/controllers/services_controller.py
from typing import List, Optional
from fastapi import HTTPException, status
from wakedock.controllers.base_controller import BaseController
from wakedock.repositories.services_repository import ServicesRepository
from wakedock.services.docker_service import DockerService
from wakedock.serializers.services_serializers import ServiceCreateSchema, ServiceUpdateSchema

class ServicesController(BaseController):
    def __init__(self, repository: ServicesRepository, docker_service: DockerService):
        super().__init__(repository)
        self.docker_service = docker_service
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Any]:
        return await self.repository.get_all(skip=skip, limit=limit)
    
    async def get_by_id(self, service_id: str) -> Any:
        service = await self.repository.get_by_id(service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service {service_id} not found"
            )
        return service
    
    async def create(self, data: ServiceCreateSchema) -> Any:
        # Validation métier
        await self._validate_service_creation(data)
        
        # Création du service
        service = await self.repository.create(data.dict())
        
        # Démarrage du container Docker
        await self.docker_service.create_container(service)
        
        return service
    
    async def start_service(self, service_id: str) -> Any:
        service = await self.get_by_id(service_id)
        await self.docker_service.start_container(service.container_id)
        return await self.repository.update(service_id, {"status": "running"})
    
    async def _validate_service_creation(self, data: ServiceCreateSchema):
        # Validation des ports
        if await self._port_in_use(data.port):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Port {data.port} already in use"
            )
```

---

## 👁️ PHASE 4: Création des Vues (Views)

### 4.1 🆕 Vues de base
- [ ] **Créer `wakedock/views/base_view.py`**
```python
from typing import Any, Dict, List, Optional
from fastapi import Response, status
from pydantic import BaseModel

class BaseView:
    @staticmethod
    def success_response(data: Any, message: str = "Success") -> Dict[str, Any]:
        return {
            "success": True,
            "data": data,
            "message": message
        }
    
    @staticmethod
    def error_response(message: str, details: Optional[Any] = None) -> Dict[str, Any]:
        return {
            "success": False,
            "error": message,
            "details": details
        }
    
    @staticmethod
    def paginated_response(items: List[Any], total: int, page: int, page_size: int) -> Dict[str, Any]:
        return {
            "success": True,
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
```

### 4.2 🔄 Création des vues spécialisées
- [ ] **Vues d'authentification**
  - [ ] `wakedock/views/auth_views.py`
  - [ ] Méthodes: `login_response()`, `register_response()`, `token_response()`

- [ ] **Vues des services**
  - [ ] `wakedock/views/services_views.py`
  - [ ] Méthodes: `service_list_response()`, `service_detail_response()`, `service_action_response()`

- [ ] **Vues des containers**
  - [ ] `wakedock/views/containers_views.py`
  - [ ] Méthodes: `container_list_response()`, `container_detail_response()`, `container_logs_response()`

- [ ] **Vues des alertes**
  - [ ] `wakedock/views/alerts_views.py`
  - [ ] Méthodes: `alert_list_response()`, `alert_detail_response()`

### 4.3 🔧 Exemple de vue
```python
# wakedock/views/services_views.py
from typing import List
from wakedock.views.base_view import BaseView
from wakedock.models.service import Service

class ServicesView(BaseView):
    @staticmethod
    def service_detail_response(service: Service) -> dict:
        return BaseView.success_response(
            data={
                "id": service.id,
                "name": service.name,
                "status": service.status,
                "created_at": service.created_at.isoformat(),
                "updated_at": service.updated_at.isoformat(),
                "ports": service.ports,
                "environment": service.environment
            }
        )
    
    @staticmethod
    def service_list_response(services: List[Service], total: int, page: int, page_size: int) -> dict:
        service_data = [
            {
                "id": service.id,
                "name": service.name,
                "status": service.status,
                "created_at": service.created_at.isoformat()
            }
            for service in services
        ]
        return BaseView.paginated_response(service_data, total, page, page_size)
```

---

## 🗄️ PHASE 5: Création des Repositories

### 5.1 🆕 Repository de base
- [ ] **Créer `wakedock/repositories/base_repository.py`**
```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

class BaseRepository(ABC):
    def __init__(self, session: AsyncSession, model):
        self.session = session
        self.model = model
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Any]:
        query = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_by_id(self, id: str) -> Optional[Any]:
        query = select(self.model).where(self.model.id == id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def create(self, data: Dict[str, Any]) -> Any:
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance
    
    async def update(self, id: str, data: Dict[str, Any]) -> Optional[Any]:
        query = update(self.model).where(self.model.id == id).values(**data)
        await self.session.execute(query)
        await self.session.commit()
        return await self.get_by_id(id)
    
    async def delete(self, id: str) -> bool:
        query = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(query)
        await self.session.commit()
        return result.rowcount > 0
```

### 5.2 🔄 Création des repositories spécialisés
- [ ] **Repository des utilisateurs**
  - [ ] `wakedock/repositories/user_repository.py`
  - [ ] Méthodes: `get_by_email()`, `get_by_username()`, `create_user()`, `update_password()`

- [ ] **Repository des services**
  - [ ] `wakedock/repositories/services_repository.py`
  - [ ] Méthodes: `get_by_name()`, `get_by_status()`, `get_by_stack_id()`

- [ ] **Repository des containers**
  - [ ] `wakedock/repositories/containers_repository.py`
  - [ ] Méthodes: `get_by_service_id()`, `get_by_image()`

- [ ] **Repository des alertes**
  - [ ] `wakedock/repositories/alerts_repository.py`
  - [ ] Méthodes: `get_by_user_id()`, `get_by_severity()`, `get_active_alerts()`

---

## 🛠️ PHASE 6: Création des Services

### 6.1 🔄 Migration des services existants
- [ ] **Service Docker**
  - [ ] Migrer `wakedock/core/orchestrator.py` → `wakedock/services/docker_service.py`
  - [ ] Nettoyer et simplifier l'interface

- [ ] **Service d'authentification**
  - [ ] Migrer `wakedock/core/auth_service.py` → `wakedock/services/auth_service.py`
  - [ ] Séparer la logique JWT des contrôleurs

- [ ] **Service de monitoring**
  - [ ] Migrer `wakedock/core/monitoring.py` → `wakedock/services/monitoring_service.py`
  - [ ] Optimiser les métriques

- [ ] **Service de logs**
  - [ ] Migrer `wakedock/core/log_collector.py` → `wakedock/services/logging_service.py`
  - [ ] Centraliser la collecte des logs

### 6.2 🆕 Nouveaux services
- [ ] **Service de validation**
  - [ ] `wakedock/services/validation_service.py`
  - [ ] Centraliser toutes les validations métier

- [ ] **Service de cache**
  - [ ] `wakedock/services/cache_service.py`
  - [ ] Optimiser les performances avec Redis

- [ ] **Service de notifications**
  - [ ] `wakedock/services/notification_service.py`
  - [ ] Gérer les notifications en temps réel

---

## 🛡️ PHASE 7: Middleware et Validateurs

### 7.1 🔄 Migration des middlewares existants
- [ ] **Middleware d'authentification**
  - [ ] Migrer `wakedock/core/auth_middleware.py` → `wakedock/middleware/auth_middleware.py`
  - [ ] Simplifier et optimiser

- [ ] **Middleware de logging**
  - [ ] Migrer `wakedock/core/middleware.py` → `wakedock/middleware/logging_middleware.py`
  - [ ] Standardiser les logs

- [ ] **Middleware de compression**
  - [ ] Migrer `wakedock/core/compression_middleware.py` → `wakedock/middleware/compression_middleware.py`

### 7.2 🆕 Nouveaux middlewares
- [ ] **Middleware de rate limiting**
  - [ ] `wakedock/middleware/rate_limit_middleware.py`
  - [ ] Protéger l'API contre les abus

- [ ] **Middleware de CORS**
  - [ ] `wakedock/middleware/cors_middleware.py`
  - [ ] Gérer les requêtes cross-origin

### 7.3 🆕 Validateurs
- [ ] **Validateurs d'authentification**
  - [ ] `wakedock/validators/auth_validators.py`
  - [ ] Valider les données d'inscription/connexion

- [ ] **Validateurs de services**
  - [ ] `wakedock/validators/services_validators.py`
  - [ ] Valider les configurations de services

---

## 📡 PHASE 8: Refactorisation des Routes

### 8.1 🔄 Simplification des routes
- [ ] **Routes d'authentification**
  - [ ] Refactoriser `wakedock/api/auth/routes.py`
  - [ ] Utiliser les nouveaux contrôleurs et vues

- [ ] **Routes des services**
  - [ ] Refactoriser `wakedock/api/routes/services.py`
  - [ ] Déléguer toute la logique aux contrôleurs

- [ ] **Routes des containers**
  - [ ] Refactoriser `wakedock/api/routes/containers.py`
  - [ ] Simplifier les handlers

### 8.2 🔧 Exemple de route refactorisée
```python
# wakedock/api/routes/services.py
from fastapi import APIRouter, Depends, HTTPException, status
from wakedock.controllers.services_controller import ServicesController
from wakedock.views.services_views import ServicesView
from wakedock.serializers.services_serializers import ServiceCreateSchema, ServiceUpdateSchema
from wakedock.middleware.auth_middleware import get_current_user

router = APIRouter()

@router.get("/services")
async def list_services(
    skip: int = 0,
    limit: int = 100,
    controller: ServicesController = Depends(),
    current_user = Depends(get_current_user)
):
    """Liste tous les services"""
    services = await controller.get_all(skip=skip, limit=limit)
    total = await controller.count()
    return ServicesView.service_list_response(services, total, skip // limit + 1, limit)

@router.post("/services", status_code=status.HTTP_201_CREATED)
async def create_service(
    service_data: ServiceCreateSchema,
    controller: ServicesController = Depends(),
    current_user = Depends(get_current_user)
):
    """Crée un nouveau service"""
    service = await controller.create(service_data)
    return ServicesView.service_detail_response(service)

@router.post("/services/{service_id}/start")
async def start_service(
    service_id: str,
    controller: ServicesController = Depends(),
    current_user = Depends(get_current_user)
):
    """Démarre un service"""
    service = await controller.start_service(service_id)
    return ServicesView.service_detail_response(service)
```

---

## 🧪 PHASE 9: Tests

### 9.1 🔄 Refactorisation des tests existants
- [ ] **Tests des contrôleurs**
  - [ ] Migrer `tests/test_models.py` → `tests/test_controllers/`
  - [ ] Créer des tests unitaires pour chaque contrôleur

- [ ] **Tests des repositories**
  - [ ] Créer `tests/test_repositories/`
  - [ ] Tester les requêtes de base de données

- [ ] **Tests des services**
  - [ ] Créer `tests/test_services/`
  - [ ] Tester la logique métier

### 9.2 🆕 Nouveaux tests
- [ ] **Tests d'intégration**
  - [ ] `tests/test_integration/`
  - [ ] Tester les flux complets

- [ ] **Tests des vues**
  - [ ] `tests/test_views/`
  - [ ] Tester les réponses JSON

- [ ] **Tests des validateurs**
  - [ ] `tests/test_validators/`
  - [ ] Tester les validations

---

## 🚀 PHASE 10: Déploiement et Optimisations

### 10.1 🔄 Mise à jour des configurations
- [ ] **Configuration Docker**
  - [ ] Mettre à jour `Dockerfile`
  - [ ] Optimiser les layers

- [ ] **Configuration de la base de données**
  - [ ] Mettre à jour `alembic.ini`
  - [ ] Créer les migrations pour les nouveaux modèles

- [ ] **Configuration des dépendances**
  - [ ] Mettre à jour `requirements.txt`
  - [ ] Ajouter les nouvelles dépendances

### 10.2 📊 Monitoring et métriques
- [ ] **Métriques de performance**
  - [ ] Ajouter des métriques pour chaque contrôleur
  - [ ] Surveiller les temps de réponse

- [ ] **Logs structurés**
  - [ ] Standardiser les logs dans tous les composants
  - [ ] Ajouter des identifiants de trace

### 10.3 🔧 Optimisations
- [ ] **Cache Redis**
  - [ ] Implémenter le cache au niveau des repositories
  - [ ] Optimiser les requêtes fréquentes

- [ ] **Pagination**
  - [ ] Standardiser la pagination dans tous les endpoints
  - [ ] Optimiser les requêtes avec des index

---

## 📚 DOCUMENTATION

### 📖 Documentation technique
- [ ] **Architecture MVC**
  - [ ] Créer `docs/architecture/mvc-guide.md`
  - [ ] Documenter les patterns utilisés

- [ ] **Guide des développeurs**
  - [ ] Créer `docs/developers/getting-started.md`
  - [ ] Documenter les conventions

- [ ] **API Documentation**
  - [ ] Mettre à jour la documentation Swagger
  - [ ] Ajouter des exemples d'utilisation

### 📝 Changelog
- [ ] **Changelog de migration**
  - [ ] Documenter tous les changements
  - [ ] Créer un guide de migration

---

## ⚠️ POINTS D'ATTENTION

### 🚨 Risques et mitigations
1. **Rupture de compatibilité**
   - Maintenir les anciennes interfaces pendant la migration
   - Créer des adaptateurs si nécessaire

2. **Performance**
   - Surveiller les performances pendant la migration
   - Optimiser les requêtes lentes

3. **Complexité**
   - Migrer par petites étapes
   - Tester chaque étape avant de passer à la suivante

### 🔄 Stratégie de migration
1. **Migration progressive**
   - Commencer par les composants les moins critiques
   - Maintenir la compatibilité pendant la transition

2. **Tests continus**
   - Exécuter les tests après chaque étape
   - Maintenir la couverture de tests

3. **Rollback plan**
   - Possibilité de revenir en arrière à chaque étape
   - Sauvegardes des configurations

---

## 📈 TIMELINE ESTIMÉ

### Phase 1-2: Structure et Modèles (1-2 jours)
- Création de la structure de dossiers
- Amélioration des modèles existants

### Phase 3-4: Contrôleurs et Vues (3-4 jours)
- Migration des contrôleurs
- Création des vues

### Phase 5-6: Repositories et Services (2-3 jours)
- Création des repositories
- Migration des services

### Phase 7-8: Middleware et Routes (2-3 jours)
- Migration des middlewares
- Refactorisation des routes

### Phase 9-10: Tests et Déploiement (2-3 jours)
- Refactorisation des tests
- Optimisations et déploiement

**Total estimé: 10-15 jours**

---

## ✅ VALIDATION

### Critères de réussite
- [ ] Architecture MVC claire et respectée
- [ ] Séparation des responsabilités
- [ ] Tests passants à 100%
- [ ] Performance maintenue ou améliorée
- [ ] Documentation complète
- [ ] Déploiement réussi

### Métriques de validation
- [ ] Temps de réponse API < 200ms
- [ ] Couverture de tests > 80%
- [ ] Zéro régression fonctionnelle
- [ ] Code quality score > 8/10

---

**🎯 Cette migration vers l'architecture MVC permettra une meilleure maintenabilité, une séparation claire des responsabilités et une évolutivité accrue du backend WakeDock.**
