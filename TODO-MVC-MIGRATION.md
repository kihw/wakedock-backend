# 🏗️ TODO - Migration Architecture MVC pour WakeDock Backend

## 📋 Vue d'ensemble de la Migration

**Objectif** : Migrer l'architecture actuelle de wakedock-backend vers une architecture MVC (Model-View-Controller) claire et maintenable.

**Durée estimée** : 2-3 semaines (sprint de refactoring)

**Impact** : Amélioration de la maintenabilité, séparation des responsabilités, facilitation des tests

---

## 🎯 Architecture Cible MVC

```
wakedock-backend/
├── wakedock/
│   ├── models/              # 📦 MODEL - Entités métier et logique domaine
│   │   ├── domain/          # Modèles du domaine métier
│   │   ├── entities/        # Entités SQLAlchemy
│   │   └── repositories/    # Accès aux données
│   ├── controllers/         # 🎮 CONTROLLER - Logique applicative
│   │   ├── api/             # Contrôleurs API REST
│   │   ├── services/        # Services métier
│   │   └── handlers/        # Gestionnaires d'événements
│   ├── views/               # 🖥️ VIEW - Présentation des données
│   │   ├── serializers/     # Sérialisation Pydantic
│   │   ├── responses/       # Formats de réponse
│   │   └── validators/      # Validation des entrées
│   ├── infrastructure/      # 🔧 INFRASTRUCTURE - Services techniques
│   │   ├── database/        # Configuration BDD
│   │   ├── cache/           # Configuration Redis
│   │   ├── security/        # Sécurité et auth
│   │   └── docker/          # Client Docker
│   └── application/         # 🚀 APPLICATION - Configuration app
│       ├── config/          # Configuration
│       ├── middleware/      # Middleware
│       └── routing/         # Routes et dépendances
```

---

## 🔧 Phase 1 : Préparation et Planification

### ✅ Tâches Préliminaires

- [ ] **Audit Architecture Actuelle**
  - [ ] Mapper tous les fichiers existants
  - [ ] Identifier les dépendances inter-modules
  - [ ] Documenter les points d'entrée critiques
  - [ ] Analyser les tests existants

- [ ] **Configuration Environnement**
  - [ ] Créer branche `refactor/mvc-architecture`
  - [ ] Sauvegarder architecture actuelle
  - [ ] Préparer scripts de migration
  - [ ] Configurer tests de non-régression

- [ ] **Planification Détaillée**
  - [ ] Définir ordre de migration par module
  - [ ] Identifier les dépendances critiques
  - [ ] Planifier les phases de validation
  - [ ] Préparer documentation technique

---

## 📦 Phase 2 : Migration des MODELS

### 🎯 Objectif : Séparer les modèles de données et la logique métier

#### 2.1 Création Structure Models

- [ ] **Créer `models/domain/`** - Modèles métier purs
  ```python
  # models/domain/service.py
  from dataclasses import dataclass
  from typing import List, Optional
  from enum import Enum
  
  class ServiceStatus(Enum):
      RUNNING = "running"
      STOPPED = "stopped"
      STARTING = "starting"
      
  @dataclass
  class Service:
      id: str
      name: str
      image: str
      status: ServiceStatus
      ports: List[int]
      environment: dict
      
      def is_healthy(self) -> bool:
          return self.status == ServiceStatus.RUNNING
  ```

- [ ] **Créer `models/entities/`** - Entités SQLAlchemy
  ```python
  # models/entities/service_entity.py
  from sqlalchemy import Column, String, Integer, JSON
  from wakedock.infrastructure.database import Base
  
  class ServiceEntity(Base):
      __tablename__ = "services"
      
      id = Column(String, primary_key=True)
      name = Column(String, unique=True, nullable=False)
      image = Column(String, nullable=False)
      status = Column(String, nullable=False)
      ports = Column(JSON)
      environment = Column(JSON)
  ```

- [ ] **Créer `models/repositories/`** - Accès aux données
  ```python
  # models/repositories/service_repository.py
  from abc import ABC, abstractmethod
  from typing import List, Optional
  from wakedock.models.domain.service import Service
  
  class ServiceRepository(ABC):
      @abstractmethod
      async def find_by_id(self, service_id: str) -> Optional[Service]:
          pass
      
      @abstractmethod
      async def find_all(self) -> List[Service]:
          pass
      
      @abstractmethod
      async def save(self, service: Service) -> Service:
          pass
  ```

#### 2.2 Migration des Modèles Existants

- [ ] **Migrer `models/user.py`** vers structure MVC
  - [ ] Créer `models/domain/user.py`
  - [ ] Créer `models/entities/user_entity.py`
  - [ ] Créer `models/repositories/user_repository.py`
  - [ ] Mettre à jour les imports

- [ ] **Migrer `models/dashboard.py`** vers structure MVC
  - [ ] Créer `models/domain/dashboard.py`
  - [ ] Créer `models/entities/dashboard_entity.py`
  - [ ] Créer `models/repositories/dashboard_repository.py`

- [ ] **Migrer `models/notification.py`** vers structure MVC
  - [ ] Créer `models/domain/notification.py`
  - [ ] Créer `models/entities/notification_entity.py`
  - [ ] Créer `models/repositories/notification_repository.py`

- [ ] **Migrer autres modèles** (alerts, audit, cicd, etc.)
  - [ ] Suivre le même pattern pour chaque modèle
  - [ ] Maintenir cohérence architecturale

#### 2.3 Validation Phase Models

- [ ] **Tests Models**
  - [ ] Tests unitaires pour modèles domaine
  - [ ] Tests d'intégration pour repositories
  - [ ] Tests de mapping entities <-> domain

- [ ] **Validation Migration**
  - [ ] Vérifier que tous les imports sont mis à jour
  - [ ] Exécuter suite de tests complète
  - [ ] Valider performance base de données

---

## 🎮 Phase 3 : Migration des CONTROLLERS

### 🎯 Objectif : Séparer logique applicative et présentation

#### 3.1 Création Structure Controllers

- [ ] **Créer `controllers/api/`** - Contrôleurs API
  ```python
  # controllers/api/service_controller.py
  from fastapi import APIRouter, Depends, HTTPException
  from wakedock.controllers.services.service_application_service import ServiceApplicationService
  from wakedock.views.serializers.service_serializer import ServiceResponse
  
  router = APIRouter()
  
  @router.get("/services/{service_id}", response_model=ServiceResponse)
  async def get_service(
      service_id: str,
      service_app: ServiceApplicationService = Depends()
  ):
      service = await service_app.get_service_by_id(service_id)
      if not service:
          raise HTTPException(status_code=404, detail="Service not found")
      return ServiceResponse.from_domain(service)
  ```

- [ ] **Créer `controllers/services/`** - Services applicatifs
  ```python
  # controllers/services/service_application_service.py
  from wakedock.models.domain.service import Service
  from wakedock.models.repositories.service_repository import ServiceRepository
  from wakedock.infrastructure.docker.docker_client import DockerClient
  
  class ServiceApplicationService:
      def __init__(
          self,
          service_repo: ServiceRepository,
          docker_client: DockerClient
      ):
          self.service_repo = service_repo
          self.docker_client = docker_client
      
      async def get_service_by_id(self, service_id: str) -> Service:
          # Logique applicative pure
          service = await self.service_repo.find_by_id(service_id)
          if service:
              # Enrichir avec données Docker
              docker_info = await self.docker_client.get_container_info(service_id)
              service.status = docker_info.status
          return service
  ```

#### 3.2 Migration des Routes Existantes

- [ ] **Migrer `api/routes/services.py`**
  - [ ] Créer `controllers/api/service_controller.py`
  - [ ] Créer `controllers/services/service_application_service.py`
  - [ ] Migrer logique métier vers service applicatif
  - [ ] Simplifier contrôleur API

- [ ] **Migrer `api/routes/containers.py`**
  - [ ] Créer `controllers/api/container_controller.py`
  - [ ] Créer `controllers/services/container_application_service.py`
  - [ ] Séparer logique Docker de logique API

- [ ] **Migrer `api/routes/dashboard_api.py`**
  - [ ] Créer `controllers/api/dashboard_controller.py`
  - [ ] Créer `controllers/services/dashboard_application_service.py`
  - [ ] Migrer logique métier complexe

- [ ] **Migrer autres routes API**
  - [ ] `health.py` → `health_controller.py`
  - [ ] `alerts.py` → `alerts_controller.py`
  - [ ] `notification_api.py` → `notification_controller.py`
  - [ ] Etc.

#### 3.3 Refactoring Core Services

- [ ] **Migrer `core/` vers `controllers/services/`**
  - [ ] `core/docker_manager.py` → `controllers/services/docker_application_service.py`
  - [ ] `core/orchestrator.py` → `controllers/services/orchestration_service.py`
  - [ ] `core/monitoring.py` → `controllers/services/monitoring_service.py`

- [ ] **Séparer préoccupations**
  - [ ] Logique métier → services applicatifs
  - [ ] Logique technique → infrastructure
  - [ ] Validation → views/validators

#### 3.4 Validation Phase Controllers

- [ ] **Tests Controllers**
  - [ ] Tests unitaires pour services applicatifs
  - [ ] Tests d'intégration pour contrôleurs API
  - [ ] Mocks pour dépendances externes

- [ ] **Validation Migration**
  - [ ] Vérifier séparation des responsabilités
  - [ ] Valider injection de dépendances
  - [ ] Tester performance endpoints

---

## 🖥️ Phase 4 : Migration des VIEWS

### 🎯 Objectif : Standardiser présentation et validation des données

#### 4.1 Création Structure Views

- [ ] **Créer `views/serializers/`** - Sérialisation Pydantic
  ```python
  # views/serializers/service_serializer.py
  from pydantic import BaseModel, Field
  from typing import List, Optional
  from wakedock.models.domain.service import Service, ServiceStatus
  
  class ServiceResponse(BaseModel):
      id: str
      name: str
      image: str
      status: ServiceStatus
      ports: List[int]
      environment: dict
      is_healthy: bool = Field(alias="healthy")
      
      @classmethod
      def from_domain(cls, service: Service) -> "ServiceResponse":
          return cls(
              id=service.id,
              name=service.name,
              image=service.image,
              status=service.status,
              ports=service.ports,
              environment=service.environment,
              healthy=service.is_healthy()
          )
  ```

- [ ] **Créer `views/requests/`** - Modèles de requêtes
  ```python
  # views/requests/service_request.py
  from pydantic import BaseModel, Field, validator
  from typing import List, Dict
  
  class CreateServiceRequest(BaseModel):
      name: str = Field(..., min_length=1, max_length=100)
      image: str = Field(..., min_length=1)
      ports: List[int] = Field(default_factory=list)
      environment: Dict[str, str] = Field(default_factory=dict)
      
      @validator('name')
      def validate_name(cls, v):
          if not v.isalnum():
              raise ValueError('Name must be alphanumeric')
          return v
  ```

- [ ] **Créer `views/validators/`** - Validation métier
  ```python
  # views/validators/service_validator.py
  from wakedock.models.domain.service import Service
  from wakedock.infrastructure.docker.docker_client import DockerClient
  
  class ServiceValidator:
      def __init__(self, docker_client: DockerClient):
          self.docker_client = docker_client
      
      async def validate_image_exists(self, image: str) -> bool:
          return await self.docker_client.image_exists(image)
      
      async def validate_ports_available(self, ports: List[int]) -> bool:
          return await self.docker_client.check_ports_available(ports)
  ```

#### 4.2 Migration des Schémas Existants

- [ ] **Migrer `schemas/` vers `views/serializers/`**
  - [ ] `schemas/user.py` → `views/serializers/user_serializer.py`
  - [ ] `schemas/service.py` → `views/serializers/service_serializer.py`
  - [ ] Standardiser format de sérialisation

- [ ] **Créer modèles de requêtes**
  - [ ] Extraire validation des contrôleurs
  - [ ] Créer modèles Pydantic pour chaque endpoint
  - [ ] Ajouter validation métier

#### 4.3 Validation Phase Views

- [ ] **Tests Views**
  - [ ] Tests de sérialisation
  - [ ] Tests de validation
  - [ ] Tests de mapping domain → response

---

## 🔧 Phase 5 : Migration INFRASTRUCTURE

### 🎯 Objectif : Isoler services techniques et configuration

#### 5.1 Création Structure Infrastructure

- [ ] **Créer `infrastructure/database/`**
  ```python
  # infrastructure/database/connection.py
  from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
  from sqlalchemy.orm import sessionmaker
  
  class DatabaseConnection:
      def __init__(self, database_url: str):
          self.engine = create_async_engine(database_url)
          self.session_factory = sessionmaker(
              bind=self.engine,
              class_=AsyncSession,
              expire_on_commit=False
          )
      
      async def get_session(self) -> AsyncSession:
          async with self.session_factory() as session:
              yield session
  ```

- [ ] **Créer `infrastructure/docker/`**
  ```python
  # infrastructure/docker/docker_client.py
  import docker
  from typing import List, Optional
  
  class DockerClient:
      def __init__(self):
          self.client = docker.from_env()
      
      async def get_container_info(self, container_id: str) -> dict:
          # Logique technique Docker
          pass
      
      async def start_container(self, container_id: str) -> bool:
          # Logique technique Docker
          pass
  ```

- [ ] **Créer `infrastructure/cache/`**
  ```python
  # infrastructure/cache/redis_client.py
  import redis.asyncio as redis
  
  class RedisClient:
      def __init__(self, redis_url: str):
          self.client = redis.from_url(redis_url)
      
      async def get(self, key: str) -> Optional[str]:
          return await self.client.get(key)
      
      async def set(self, key: str, value: str, expire: int = None) -> bool:
          return await self.client.set(key, value, ex=expire)
  ```

#### 5.2 Migration des Services Techniques

- [ ] **Migrer `database/` vers `infrastructure/database/`**
  - [ ] Migrer configuration base de données
  - [ ] Migrer migrations Alembic
  - [ ] Migrer repositories concrets

- [ ] **Migrer `core/` techniques vers `infrastructure/`**
  - [ ] `core/cache.py` → `infrastructure/cache/redis_client.py`
  - [ ] `core/security.py` → `infrastructure/security/auth_service.py`
  - [ ] Services techniques uniquement

#### 5.3 Validation Phase Infrastructure

- [ ] **Tests Infrastructure**
  - [ ] Tests d'intégration base de données
  - [ ] Tests d'intégration Redis
  - [ ] Tests d'intégration Docker

---

## 🚀 Phase 6 : Migration APPLICATION

### 🎯 Objectif : Configurer et assembler l'application

#### 6.1 Création Structure Application

- [ ] **Créer `application/config/`**
  ```python
  # application/config/settings.py
  from pydantic import BaseSettings
  
  class Settings(BaseSettings):
      database_url: str
      redis_url: str
      jwt_secret: str
      
      class Config:
          env_file = ".env"
  ```

- [ ] **Créer `application/routing/`**
  ```python
  # application/routing/api_router.py
  from fastapi import APIRouter
  from wakedock.controllers.api.service_controller import router as service_router
  
  api_router = APIRouter()
  api_router.include_router(service_router, prefix="/services")
  ```

- [ ] **Créer `application/dependencies/`**
  ```python
  # application/dependencies/container.py
  from dependency_injector import containers, providers
  
  class Container(containers.DeclarativeContainer):
      config = providers.Configuration()
      
      # Infrastructure
      database = providers.Singleton(
          DatabaseConnection,
          database_url=config.database.url
      )
      
      # Repositories
      service_repository = providers.Factory(
          ServiceRepository,
          session=database.provided.get_session
      )
      
      # Services
      service_application_service = providers.Factory(
          ServiceApplicationService,
          service_repo=service_repository
      )
  ```

#### 6.2 Migration Configuration Application

- [ ] **Migrer `main.py`**
  - [ ] Utiliser nouveau système de routing
  - [ ] Intégrer container d'injection de dépendances
  - [ ] Simplifier configuration

- [ ] **Migrer `api/app.py`**
  - [ ] Refactorer factory d'application
  - [ ] Utiliser nouvelles routes
  - [ ] Intégrer middleware

#### 6.3 Validation Phase Application

- [ ] **Tests Application**
  - [ ] Tests de démarrage application
  - [ ] Tests d'intégration complète
  - [ ] Tests de performance

---

## 🧪 Phase 7 : Tests et Validation

### 7.1 Tests Unitaires

- [ ] **Tests Models**
  - [ ] Tests domaine métier
  - [ ] Tests repositories
  - [ ] Tests mapping entities

- [ ] **Tests Controllers**
  - [ ] Tests services applicatifs
  - [ ] Tests contrôleurs API
  - [ ] Tests avec mocks

- [ ] **Tests Views**
  - [ ] Tests sérialisation
  - [ ] Tests validation
  - [ ] Tests mapping

### 7.2 Tests d'Intégration

- [ ] **Tests End-to-End**
  - [ ] Tests API complètes
  - [ ] Tests base de données
  - [ ] Tests Docker

- [ ] **Tests Performance**
  - [ ] Benchmarks endpoints
  - [ ] Tests charge
  - [ ] Profiling mémoire

### 7.3 Validation Migration

- [ ] **Validation Fonctionnelle**
  - [ ] Toutes les fonctionnalités existantes marchent
  - [ ] Pas de régression
  - [ ] Performance maintenue

- [ ] **Validation Architecturale**
  - [ ] Respect des principes MVC
  - [ ] Séparation des responsabilités
  - [ ] Injection de dépendances

---

## 📚 Phase 8 : Documentation et Finalisation

### 8.1 Documentation

- [ ] **Documentation Architecture**
  - [ ] Diagramme architecture MVC
  - [ ] Guide développeur
  - [ ] Patterns utilisés

- [ ] **Documentation API**
  - [ ] Mise à jour OpenAPI
  - [ ] Exemples d'utilisation
  - [ ] Guide migration

### 8.2 Finalisation

- [ ] **Nettoyage**
  - [ ] Suppression ancien code
  - [ ] Nettoyage imports
  - [ ] Optimisation

- [ ] **Déploiement**
  - [ ] Mise à jour docker-compose
  - [ ] Tests déploiement
  - [ ] Monitoring

---

## 🎯 Critères de Succès

### ✅ Architecture

- [ ] **Séparation claire** Models / Views / Controllers
- [ ] **Injection de dépendances** fonctionnelle
- [ ] **Testabilité** améliorée (>80% couverture)
- [ ] **Maintenabilité** simplifiée

### ✅ Performance

- [ ] **Aucune régression** performance
- [ ] **Temps de réponse** maintenus
- [ ] **Consommation mémoire** optimisée

### ✅ Fonctionnel

- [ ] **Toutes les APIs** fonctionnelles
- [ ] **Compatibilité** frontend maintenue
- [ ] **Pas de breaking changes**

---

## 🚨 Risques et Mitigation

### 🔴 Risques Identifiés

1. **Régression fonctionnelle** - Tests complets à chaque étape
2. **Performance dégradée** - Benchmarks avant/après
3. **Complexité migration** - Migration progressive par module
4. **Dépendances circulaires** - Graphe de dépendances strict

### 🟢 Stratégies de Mitigation

1. **Branches séparées** pour chaque phase
2. **Tests automatisés** à chaque commit
3. **Rollback rapide** si problème
4. **Validation continue** avec équipe

---

## 📅 Planning Indicatif

| Phase | Durée | Tâches Principales |
|-------|-------|-------------------|
| 1. Préparation | 2 jours | Audit, planification, configuration |
| 2. Models | 4 jours | Migration modèles, repositories, tests |
| 3. Controllers | 5 jours | Migration routes, services, logique |
| 4. Views | 3 jours | Sérialisation, validation, présentation |
| 5. Infrastructure | 3 jours | Services techniques, configuration |
| 6. Application | 2 jours | Assembly, routing, dépendances |
| 7. Tests | 3 jours | Tests complets, validation |
| 8. Documentation | 1 jour | Documentation, finalisation |

**Total** : ~3 semaines (23 jours)

---

## 🎯 Points d'Attention

### 🔍 Coordination Multi-Repo

- [ ] **Synchronisation** avec wakedock-frontend
- [ ] **Validation** via docker-compose WakeDock/
- [ ] **Tests d'intégration** full-stack

### 🔧 Respect Instructions Root

- [ ] **Déploiement centralisé** depuis WakeDock/
- [ ] **Versioning synchronisé** avec scripts
- [ ] **Tests complets** via IP publique

### 📊 Monitoring Migration

- [ ] **Métriques** avant/après migration
- [ ] **Logs** détaillés du processus
- [ ] **Alertes** en cas de problème

---

**🎯 Objectif Final** : Une architecture MVC propre, maintenable et performante pour wakedock-backend, respectant les principes SOLID et facilitant les futures évolutions.
