# Documentation - Version 0.2.3 : Métriques et Analytics de Performance

## Vue d'ensemble

La version 0.2.3 introduit un système complet d'analytics avancé avec des capacités de prédiction et d'optimisation des ressources. Ce système analyse les tendances de performance des conteneurs Docker et génère des recommandations d'optimisation automatiques.

## Architecture du Système d'Analytics

### Service Principal : AdvancedAnalyticsService

Le service d'analytics avancé (`AdvancedAnalyticsService`) est le cœur du système qui :

- **Analyse les tendances** : Calcule les tendances de performance pour CPU, mémoire et réseau
- **Génère des prédictions** : Utilise des modèles de régression pour prédire les valeurs futures
- **Recommande des optimisations** : Propose des ajustements de ressources basés sur l'analyse
- **Produit des rapports** : Génère des rapports périodiques de performance

### Composants Clés

#### 1. Collecteur de Métriques Détaillées
```python
class AdvancedAnalyticsService:
    def __init__(self, metrics_collector: MetricsCollector, storage_path: str):
        self.metrics_collector = metrics_collector
        self.storage_path = Path(storage_path)
        # Configuration des seuils et modèles
```

#### 2. Analyseur de Tendances
- **Régression linéaire** pour déterminer les tendances
- **Calcul de corrélation** pour évaluer la fiabilité
- **Classification des directions** : croissante, décroissante, stable, volatile

#### 3. Moteur de Prédiction
- **Prédictions à court terme** : 1h, 6h, 24h
- **Niveaux de confiance** : élevé, moyen, faible
- **Modèles adaptatifs** basés sur les données historiques

#### 4. Générateur d'Optimisations
- **Recommandations CPU** : augmentation/diminution des limites
- **Optimisations mémoire** : ajustements préventifs
- **Suggestions réseau** : optimisation du trafic

## Types de Données

### PerformanceTrend
Représente une tendance de performance calculée :

```python
@dataclass
class PerformanceTrend:
    metric_type: str              # Type de métrique (cpu_percent, memory_percent, network_mbps)
    container_id: str             # ID du conteneur
    container_name: str           # Nom du conteneur
    service_name: Optional[str]   # Service associé
    
    # Analyse de tendance
    direction: TrendDirection     # Direction (increasing, decreasing, stable, volatile)
    slope: float                  # Pente de la tendance
    correlation: float            # Coefficient de corrélation R²
    
    # Statistiques
    current_value: float          # Valeur actuelle
    average_value: float          # Valeur moyenne
    min_value: float              # Valeur minimale
    max_value: float              # Valeur maximale
    std_deviation: float          # Écart-type
    
    # Prédictions
    predicted_1h: float           # Prédiction à 1 heure
    predicted_6h: float           # Prédiction à 6 heures  
    predicted_24h: float          # Prédiction à 24 heures
    confidence: PredictionConfidence  # Niveau de confiance
    
    # Métadonnées
    calculated_at: datetime       # Timestamp de calcul
    data_points: int              # Nombre de points de données
    time_range_hours: int         # Plage temporelle analysée
```

### ResourceOptimization
Recommandation d'optimisation des ressources :

```python
@dataclass
class ResourceOptimization:
    container_id: str             # ID du conteneur
    container_name: str           # Nom du conteneur
    service_name: Optional[str]   # Service associé
    
    # Type d'optimisation
    resource_type: str            # Ressource (cpu, memory, network)
    optimization_type: str        # Action (increase, decrease, optimize)
    
    # Recommandations
    current_limit: Optional[float]    # Limite actuelle
    recommended_limit: float          # Limite recommandée
    expected_improvement: float       # Amélioration attendue (%)
    
    # Justification
    reason: str                   # Explication de la recommandation
    impact_level: str             # Niveau d'impact (low, medium, high)
    confidence_score: float       # Score de confiance (0-1)
    
    created_at: datetime          # Timestamp de création
```

### PerformanceReport
Rapport de performance périodique :

```python
@dataclass
class PerformanceReport:
    report_id: str                # ID unique du rapport
    period_start: datetime        # Début de période
    period_end: datetime          # Fin de période
    
    # Résumé global
    total_containers: int         # Nombre total de conteneurs
    average_cpu: float            # CPU moyen
    average_memory: float         # Mémoire moyenne
    total_network_gb: float       # Trafic réseau total
    
    # Analyses détaillées
    top_cpu_consumers: List[Dict]         # Top consommateurs CPU
    top_memory_consumers: List[Dict]      # Top consommateurs mémoire
    problematic_containers: List[Dict]    # Conteneurs problématiques
    
    # Analytics
    trends: List[PerformanceTrend]           # Tendances calculées
    optimizations: List[ResourceOptimization] # Recommandations
    
    # Alertes
    alerts_summary: Dict[str, int]        # Résumé des alertes
    
    generated_at: datetime        # Timestamp de génération
```

## API Endpoints

### Statut et Configuration

#### GET /api/v1/analytics/status
Récupère le statut du service d'analytics.

**Response:**
```json
{
  "is_running": true,
  "trend_analysis_hours": 24,
  "prediction_model_points": 100,
  "volatility_threshold": 0.3,
  "correlation_threshold": 0.7,
  "storage_path": "/var/log/wakedock/analytics",
  "cached_models": 5
}
```

#### POST /api/v1/analytics/start
Démarre le service d'analytics.

#### POST /api/v1/analytics/stop
Arrête le service d'analytics.

#### PUT /api/v1/analytics/config
Met à jour la configuration du service.

**Request Body:**
```json
{
  "trend_analysis_hours": 48,
  "prediction_model_points": 150,
  "volatility_threshold": 0.4,
  "correlation_threshold": 0.8
}
```

### Tendances de Performance

#### GET /api/v1/analytics/trends
Récupère les tendances de performance avec filtres optionnels.

**Query Parameters:**
- `container_id` : Filtrer par conteneur
- `metric_type` : Type de métrique (cpu_percent, memory_percent, network_mbps)
- `direction` : Direction de tendance (increasing, decreasing, stable, volatile)
- `confidence` : Niveau de confiance (high, medium, low)
- `hours` : Période en heures (1-168)
- `limit` : Nombre maximum de résultats (1-1000)

**Response:**
```json
[
  {
    "metric_type": "cpu_percent",
    "container_id": "abc123",
    "container_name": "web-app",
    "service_name": "frontend",
    "direction": "increasing",
    "slope": 1.5,
    "correlation": 0.85,
    "current_value": 75.2,
    "average_value": 68.5,
    "min_value": 45.0,
    "max_value": 82.1,
    "std_deviation": 8.3,
    "predicted_1h": 77.8,
    "predicted_6h": 84.2,
    "predicted_24h": 95.6,
    "confidence": "high",
    "calculated_at": "2024-01-15T10:30:00Z",
    "data_points": 144,
    "time_range_hours": 24
  }
]
```

#### GET /api/v1/analytics/trends/{container_id}
Récupère toutes les tendances pour un conteneur spécifique.

### Recommandations d'Optimisation

#### GET /api/v1/analytics/optimizations
Récupère les recommandations d'optimisation avec filtres.

**Query Parameters:**
- `container_id` : Filtrer par conteneur
- `resource_type` : Type de ressource (cpu, memory, network)
- `optimization_type` : Type d'optimisation (increase, decrease, optimize)
- `impact_level` : Niveau d'impact (low, medium, high)
- `hours` : Période en heures
- `limit` : Nombre maximum de résultats

**Response:**
```json
[
  {
    "container_id": "abc123",
    "container_name": "web-app",
    "service_name": "frontend",
    "resource_type": "cpu",
    "optimization_type": "increase",
    "current_limit": 100.0,
    "recommended_limit": 150.0,
    "expected_improvement": 25.0,
    "reason": "CPU élevé (85.2%) avec tendance croissante",
    "impact_level": "high",
    "confidence_score": 0.85,
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

#### GET /api/v1/analytics/optimizations/{container_id}
Récupère toutes les optimisations pour un conteneur spécifique.

### Rapports de Performance

#### GET /api/v1/analytics/reports
Récupère les rapports de performance générés.

**Query Parameters:**
- `days` : Nombre de jours à récupérer (1-90)
- `limit` : Nombre maximum de rapports (1-200)

#### GET /api/v1/analytics/reports/{report_id}
Récupère un rapport spécifique par son ID.

#### POST /api/v1/analytics/reports/generate
Génère un nouveau rapport de performance.

**Query Parameters:**
- `period_hours` : Période du rapport en heures (1-168)

### Résumé Analytics

#### GET /api/v1/analytics/summary
Récupère un résumé des analytics pour le dashboard.

**Query Parameters:**
- `hours` : Période d'analyse (1-168)

**Response:**
```json
{
  "period_hours": 24,
  "summary": {
    "total_trends": 45,
    "total_optimizations": 12,
    "unique_containers": 8
  },
  "trends_by_direction": {
    "increasing": 18,
    "decreasing": 12,
    "stable": 10,
    "volatile": 5
  },
  "trends_by_confidence": {
    "high": 25,
    "medium": 15,
    "low": 5
  },
  "optimizations_by_type": {
    "increase": 8,
    "decrease": 3,
    "optimize": 1
  },
  "optimizations_by_impact": {
    "high": 5,
    "medium": 4,
    "low": 3
  },
  "top_problematic_containers": [
    {
      "container_id": "abc123",
      "container_name": "web-app",
      "service_name": "frontend",
      "issues_count": 2,
      "issues": [
        {
          "metric": "cpu_percent",
          "current_value": 85.2,
          "predicted_24h": 95.6
        },
        {
          "metric": "memory_percent",
          "current_value": 88.5,
          "predicted_24h": 92.1
        }
      ]
    }
  ],
  "generated_at": "2024-01-15T10:30:00Z"
}
```

## Interface Utilisateur

### Dashboard d'Analytics Avancé

Le composant React `AdvancedAnalyticsDashboard` fournit une interface complète avec :

#### 1. Vue d'ensemble
- **Cartes de statistiques** : Tendances actives, optimisations, conteneurs analysés
- **Graphiques de répartition** : Distribution des tendances et niveaux de confiance
- **Conteneurs problématiques** : Liste des conteneurs nécessitant une attention

#### 2. Onglet Tendances
- **Tableau détaillé** : Toutes les tendances avec métriques, directions, prédictions
- **Indicateurs visuels** : Icônes et couleurs pour les types de tendances
- **Filtrage avancé** : Par conteneur, métrique, direction, confiance

#### 3. Onglet Prédictions
- **Graphique linéaire** : Évolution des prédictions dans le temps
- **Analyse de corrélation** : Scatter plot pour visualiser la fiabilité
- **Comparaison temporelle** : Actuel vs prédictions 1h/6h/24h

#### 4. Onglet Optimisations
- **Recommandations détaillées** : Liste complète avec justifications
- **Informations sur l'impact** : Niveau d'impact et amélioration attendue
- **Actions suggérées** : Augmentation/diminution/optimisation des ressources

### Fonctionnalités Interactives

#### Filtrage et Navigation
- **Sélecteur de conteneur** : Filtre global par conteneur
- **Sélecteur de période** : 6h, 24h, 3j, 7j
- **Filtres avancés** : Panneau extensible avec critères multiples
- **Recherche en temps réel** : Mise à jour automatique des données

#### Actions Utilisateur
- **Actualisation manuelle** : Bouton de refresh
- **Export de données** : Téléchargement JSON des analytics
- **Configuration** : Modification des seuils et paramètres
- **Navigation par onglets** : Interface organisée et intuitive

## Algorithmes et Logique Métier

### Analyse de Tendances

#### 1. Régression Linéaire
```python
slope, intercept, r_value, p_value, std_err = stats.linregress(x_norm, y)
correlation = r_value ** 2
```

- **Normalisation des timestamps** : Base 0 pour stabilité
- **Calcul de pente** : Détermine la direction de la tendance
- **Coefficient de corrélation R²** : Mesure la qualité de l'ajustement

#### 2. Classification des Tendances
```python
def _determine_trend_direction(self, slope: float, correlation: float, std_dev: float):
    if correlation < 0.3:
        return TrendDirection.VOLATILE
    
    if abs(slope) < std_dev * self.volatility_threshold:
        return TrendDirection.STABLE
    
    if slope > 0.01:
        return TrendDirection.INCREASING
    elif slope < -0.01:
        return TrendDirection.DECREASING
    else:
        return TrendDirection.STABLE
```

#### 3. Prédictions Temporelles
```python
# Prédictions basées sur la régression linéaire
predicted_1h = slope * (current_time + 3600) + intercept
predicted_6h = slope * (current_time + 6*3600) + intercept
predicted_24h = slope * (current_time + 24*3600) + intercept

# Contraintes de validité
predicted_value = max(0, min(predicted_value, 100))  # Pour les pourcentages
```

### Génération d'Optimisations

#### 1. Optimisation CPU
```python
# CPU élevé avec tendance croissante
if (trend.average_value > 80 and 
    trend.direction == TrendDirection.INCREASING and
    trend.confidence in [PredictionConfidence.HIGH, PredictionConfidence.MEDIUM]):
    
    return ResourceOptimization(
        optimization_type='increase',
        recommended_limit=trend.current_value * 1.5,
        expected_improvement=25.0,
        impact_level='high'
    )
```

#### 2. Optimisation Mémoire
```python
# Mémoire critique avec risque de dépassement
if (trend.current_value > 85 and 
    trend.predicted_6h > 90 and
    trend.direction == TrendDirection.INCREASING):
    
    return ResourceOptimization(
        optimization_type='increase',
        recommended_limit=trend.current_value * 1.3,
        impact_level='high'
    )
```

#### 3. Score de Confiance
```python
def _determine_prediction_confidence(self, correlation: float, data_points: int, std_dev: float):
    confidence_score = 0
    confidence_score += min(correlation, 1.0) * 0.4        # 40% corrélation
    confidence_score += min(data_points / 100, 1.0) * 0.3  # 30% nb points
    confidence_score += max(0, 1.0 - min(std_dev / 50.0, 1.0)) * 0.3  # 30% stabilité
    
    if confidence_score >= 0.7:
        return PredictionConfidence.HIGH
    elif confidence_score >= 0.4:
        return PredictionConfidence.MEDIUM
    else:
        return PredictionConfidence.LOW
```

## Stockage et Persistance

### Format de Stockage

Les données sont stockées en format JSONL (JSON Lines) pour :
- **Performance** : Lecture/écriture séquentielle optimisée
- **Flexibilité** : Ajout facile de nouvelles données
- **Robustesse** : Corruption locale limitée

### Structure des Fichiers
```
/var/log/wakedock/analytics/
├── trends_2024-01-15.jsonl          # Tendances par jour
├── optimizations_2024-01-15.jsonl   # Optimisations par jour
└── reports_2024-01.jsonl            # Rapports par mois
```

### Rotation et Archivage

- **Tendances** : Fichiers journaliers, rétention 30 jours
- **Optimisations** : Fichiers journaliers, rétention 30 jours  
- **Rapports** : Fichiers mensuels, rétention 12 mois

## Configuration et Tuning

### Paramètres Principaux

```python
class AdvancedAnalyticsService:
    def __init__(self):
        self.trend_analysis_hours = 24          # Période d'analyse des tendances
        self.prediction_model_points = 100      # Points minimum pour prédictions
        self.volatility_threshold = 0.3         # Seuil de volatilité
        self.correlation_threshold = 0.7        # R² minimum pour confiance élevée
```

### Optimisation des Performances

#### 1. Seuils Adaptatifs
- **Ajustement automatique** selon l'historique
- **Apprentissage continu** des patterns
- **Personnalisation par service**

#### 2. Cache des Modèles
- **Réutilisation** des modèles de régression
- **Mise à jour périodique** des paramètres
- **Optimisation mémoire** avec LRU cache

#### 3. Parallélisation
```python
# Analyse parallèle par conteneur
async def _analyze_performance_trends(self):
    tasks = []
    for container_id, metrics in container_metrics.items():
        task = asyncio.create_task(self._analyze_container_trends(container_id, metrics))
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

## Tests et Validation

### Tests Unitaires

#### 1. Test des Algorithmes
```python
def test_determine_trend_direction(self, analytics_service):
    # Tendance croissante forte
    direction = analytics_service._determine_trend_direction(
        slope=2.0, correlation=0.8, std_dev=3.0
    )
    assert direction == TrendDirection.INCREASING
```

#### 2. Test des Prédictions
```python
def test_analyze_metric_trend(self, analytics_service, sample_metrics):
    trend = await analytics_service._analyze_metric_trend(
        container_metrics, 'cpu_percent', 'test_container_0'
    )
    
    assert trend.predicted_1h >= 0
    assert trend.predicted_24h >= 0
    assert isinstance(trend.confidence, PredictionConfidence)
```

#### 3. Test des Optimisations
```python
def test_cpu_optimization_analysis(self, analytics_service):
    optimization = analytics_service._analyze_cpu_optimization(high_cpu_trend)
    
    assert optimization.optimization_type == 'increase'
    assert optimization.expected_improvement > 0
    assert 'CPU élevé' in optimization.reason
```

### Tests d'Intégration

#### 1. Workflow Complet
```python
async def test_full_analytics_workflow(self):
    # Métriques -> Tendances -> Optimisations -> Rapports
    await service._analyze_performance_trends()
    await service._generate_optimization_recommendations()
    await service._generate_daily_report(datetime.utcnow())
```

#### 2. Tests API
```python
def test_get_performance_trends(self, mock_analytics_service):
    response = client.get("/api/v1/analytics/trends")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) >= 0
    assert all('metric_type' in trend for trend in data)
```

## Intégration et Déploiement

### Activation du Service

Le service d'analytics est automatiquement initialisé si le monitoring est activé :

```python
# main.py
if settings.monitoring.enabled:
    metrics_collector = MetricsCollector()
    analytics_service = AdvancedAnalyticsService(
        metrics_collector=metrics_collector,
        storage_path=str(Path(settings.wakedock.data_path) / "analytics")
    )
```

### Configuration Docker

Ajout des volumes pour la persistance :
```yaml
# docker-compose.yml
services:
  wakedock-backend:
    volumes:
      - analytics_data:/var/log/wakedock/analytics

volumes:
  analytics_data:
```

### Variables d'Environnement

```bash
# Configuration analytics
WAKEDOCK_ANALYTICS_ENABLED=true
WAKEDOCK_ANALYTICS_TREND_HOURS=24
WAKEDOCK_ANALYTICS_PREDICTION_POINTS=100
WAKEDOCK_ANALYTICS_VOLATILITY_THRESHOLD=0.3
WAKEDOCK_ANALYTICS_CORRELATION_THRESHOLD=0.7
```

## Monitoring et Observabilité

### Métriques Exposées

Le service expose ses propres métriques :
- **Nombre de tendances calculées** par période
- **Temps de calcul** des analyses
- **Taux de succès** des prédictions
- **Nombre d'optimisations** générées

### Logs Structurés

```python
logger.info("Analyse des tendances terminée", extra={
    "trends_calculated": len(trends),
    "containers_analyzed": len(container_metrics),
    "analysis_duration_ms": duration,
    "correlation_avg": avg_correlation
})
```

### Alertes Système

Alertes automatiques pour :
- **Échec d'analyse** répété
- **Dégradation des modèles** (corrélation < seuil)
- **Surcharge système** (temps de calcul élevé)
- **Erreurs de stockage** des données

## Roadmap et Évolutions

### Version 0.2.4 Prévue
- **Machine Learning avancé** : Modèles LSTM pour prédictions temporelles
- **Clustering automatique** : Groupement de conteneurs similaires
- **Recommandations proactives** : Actions automatiques d'optimisation
- **Dashboard temps réel** : Mise à jour live via WebSocket

### Améliorations Continues
- **Algorithmes adaptatifs** : Apprentissage des patterns spécifiques
- **Intégration Kubernetes** : Support des métriques K8s
- **API ML exposée** : Endpoints pour modèles personnalisés
- **Optimisation multi-niveaux** : Service, stack, infrastructure

Cette documentation complète couvre tous les aspects de la version 0.2.3, du système d'analytics avancé aux interfaces utilisateur, en passant par les algorithmes et les tests. Le système est conçu pour être extensible et s'adapter aux besoins évolutifs de l'infrastructure Docker.
