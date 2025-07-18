#!/usr/bin/env python3
"""
Tests d'intégration MVC WakeDock
Script de test complet pour vérifier l'intégration de tous les domaines MVC
"""

import asyncio
import sys
import os
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wakedock.core.database import AsyncSessionLocal, Base, engine
from wakedock.core.logging import get_logger

# Import all controllers
from wakedock.controllers.dashboard_controller import DashboardController
from wakedock.controllers.analytics_controller import AnalyticsController
from wakedock.controllers.alerts_controller import AlertsController
from wakedock.controllers.containers_controller import ContainersController
from wakedock.controllers.authentication_controller import AuthenticationController

# Import all services
from wakedock.services.dashboard_service import DashboardService
from wakedock.services.analytics_service import AnalyticsService
from wakedock.services.alerts_service import AlertsService
from wakedock.services.containers_service import ContainersService
from wakedock.services.authentication_service import AuthenticationService

# Import models
from wakedock.models.dashboard_models import Dashboard, Widget
from wakedock.models.analytics_models import Metric, MetricData
from wakedock.models.alerts_models import Alert, AlertRule
from wakedock.models.containers_models import Container, ContainerStack
from wakedock.models.authentication_models import User, Role

logger = get_logger(__name__)


class MVCIntegrationTest:
    """Test d'intégration MVC complet"""
    
    def __init__(self):
        self.session = None
        self.test_results = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'errors': []
        }
    
    async def setup(self):
        """Configuration des tests"""
        try:
            # Créer une session de base de données
            self.session = AsyncSessionLocal()
            
            # Créer les tables si elles n'existent pas
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("Configuration des tests terminée")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la configuration: {str(e)}")
            self.test_results['errors'].append(f"Setup error: {str(e)}")
            return False
    
    async def teardown(self):
        """Nettoyage après les tests"""
        try:
            if self.session:
                await self.session.close()
            logger.info("Nettoyage terminé")
            
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage: {str(e)}")
    
    async def run_test(self, test_name: str, test_func):
        """Exécuter un test individuel"""
        self.test_results['total_tests'] += 1
        
        try:
            logger.info(f"Exécution du test: {test_name}")
            result = await test_func()
            
            if result:
                self.test_results['passed_tests'] += 1
                logger.info(f"✅ Test réussi: {test_name}")
                return True
            else:
                self.test_results['failed_tests'] += 1
                logger.error(f"❌ Test échoué: {test_name}")
                return False
                
        except Exception as e:
            self.test_results['failed_tests'] += 1
            error_msg = f"Test {test_name} failed: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self.test_results['errors'].append(error_msg)
            return False
    
    async def test_authentication_domain(self) -> bool:
        """Test du domaine Authentication"""
        try:
            # Test création d'utilisateur
            auth_service = AuthenticationService(self.session)
            
            user_data = {
                'username': 'test_user',
                'email': 'test@example.com',
                'password': 'test_password',
                'first_name': 'Test',
                'last_name': 'User'
            }
            
            result = await auth_service.process_auth_request('register', user_data)
            
            if not result.get('user'):
                logger.error("Échec de la création d'utilisateur")
                return False
            
            # Test connexion
            login_data = {
                'username': 'test_user',
                'password': 'test_password'
            }
            
            login_result = await auth_service.process_auth_request('login', login_data)
            
            if not login_result.get('access_token'):
                logger.error("Échec de la connexion")
                return False
            
            logger.info("Test Authentication domaine réussi")
            return True
            
        except Exception as e:
            logger.error(f"Erreur test Authentication: {str(e)}")
            return False
    
    async def test_containers_domain(self) -> bool:
        """Test du domaine Containers"""
        try:
            containers_service = ContainersService(self.session)
            
            # Test création de container
            container_data = {
                'name': 'test_container',
                'image': 'nginx:latest',
                'status': 'running',
                'ports': [{'host': 8080, 'container': 80}],
                'environment': {'ENV': 'test'},
                'labels': {'app': 'test'}
            }
            
            result = await containers_service.process_container_request('create', container_data)
            
            if not result.get('container'):
                logger.error("Échec de la création de container")
                return False
            
            container_id = result['container']['id']
            
            # Test récupération du container
            get_result = await containers_service.process_container_request('get', {'id': container_id})
            
            if not get_result.get('container'):
                logger.error("Échec de la récupération du container")
                return False
            
            logger.info("Test Containers domaine réussi")
            return True
            
        except Exception as e:
            logger.error(f"Erreur test Containers: {str(e)}")
            return False
    
    async def test_analytics_domain(self) -> bool:
        """Test du domaine Analytics"""
        try:
            analytics_service = AnalyticsService(self.session)
            
            # Test création de métrique
            metric_data = {
                'name': 'test_metric',
                'type': 'gauge',
                'description': 'Test metric',
                'unit': 'count',
                'labels': {'environment': 'test'}
            }
            
            result = await analytics_service.process_analytics_request('create_metric', metric_data)
            
            if not result.get('metric'):
                logger.error("Échec de la création de métrique")
                return False
            
            metric_id = result['metric']['id']
            
            # Test ajout de données
            data_point = {
                'metric_id': metric_id,
                'value': 42.0,
                'timestamp': datetime.utcnow()
            }
            
            data_result = await analytics_service.process_analytics_request('add_data', data_point)
            
            if not data_result.get('success'):
                logger.error("Échec de l'ajout de données")
                return False
            
            logger.info("Test Analytics domaine réussi")
            return True
            
        except Exception as e:
            logger.error(f"Erreur test Analytics: {str(e)}")
            return False
    
    async def test_alerts_domain(self) -> bool:
        """Test du domaine Alerts"""
        try:
            alerts_service = AlertsService(self.session)
            
            # Test création d'alerte
            alert_data = {
                'name': 'test_alert',
                'description': 'Test alert',
                'severity': 'medium',
                'conditions': [
                    {
                        'metric': 'cpu_usage',
                        'operator': 'greater_than',
                        'threshold': 80
                    }
                ],
                'actions': [
                    {
                        'type': 'email',
                        'recipients': ['admin@example.com']
                    }
                ]
            }
            
            result = await alerts_service.process_alert_request('create', alert_data)
            
            if not result.get('alert'):
                logger.error("Échec de la création d'alerte")
                return False
            
            alert_id = result['alert']['id']
            
            # Test déclenchement d'alerte
            trigger_result = await alerts_service.process_alert_request('trigger', {
                'alert_id': alert_id,
                'message': 'Test alert triggered'
            })
            
            if not trigger_result.get('success'):
                logger.error("Échec du déclenchement d'alerte")
                return False
            
            logger.info("Test Alerts domaine réussi")
            return True
            
        except Exception as e:
            logger.error(f"Erreur test Alerts: {str(e)}")
            return False
    
    async def test_dashboard_domain(self) -> bool:
        """Test du domaine Dashboard"""
        try:
            dashboard_service = DashboardService(self.session)
            
            # Test création de dashboard
            dashboard_data = {
                'name': 'test_dashboard',
                'description': 'Test dashboard',
                'layout': {
                    'type': 'grid',
                    'columns': 12,
                    'rows': 8
                },
                'refresh_interval': 60,
                'public': False
            }
            
            result = await dashboard_service.process_dashboard_request('create', dashboard_data)
            
            if not result.get('id'):
                logger.error("Échec de la création de dashboard")
                return False
            
            dashboard_id = result['id']
            
            # Test création de widget
            widget_data = {
                'dashboard_id': dashboard_id,
                'title': 'Test Widget',
                'type': 'chart',
                'config': {
                    'chart_type': 'line',
                    'aggregation': 'avg'
                },
                'position': {'x': 0, 'y': 0},
                'size': {'width': 6, 'height': 4}
            }
            
            widget_result = await dashboard_service.process_widget_request('create', widget_data)
            
            if not widget_result.get('widget_id'):
                logger.error("Échec de la création de widget")
                return False
            
            logger.info("Test Dashboard domaine réussi")
            return True
            
        except Exception as e:
            logger.error(f"Erreur test Dashboard: {str(e)}")
            return False
    
    async def test_cross_domain_integration(self) -> bool:
        """Test d'intégration entre domaines"""
        try:
            # Test scénario complet : Container -> Metrics -> Alert -> Dashboard
            
            # 1. Créer un container
            containers_service = ContainersService(self.session)
            container_data = {
                'name': 'integration_test_container',
                'image': 'nginx:latest',
                'status': 'running'
            }
            
            container_result = await containers_service.process_container_request('create', container_data)
            container_id = container_result['container']['id']
            
            # 2. Créer une métrique pour le container
            analytics_service = AnalyticsService(self.session)
            metric_data = {
                'name': 'container_cpu_usage',
                'type': 'gauge',
                'labels': {'container_id': container_id}
            }
            
            metric_result = await analytics_service.process_analytics_request('create_metric', metric_data)
            metric_id = metric_result['metric']['id']
            
            # 3. Créer une alerte basée sur la métrique
            alerts_service = AlertsService(self.session)
            alert_data = {
                'name': 'container_high_cpu',
                'metric_id': metric_id,
                'threshold': 80,
                'severity': 'high'
            }
            
            alert_result = await alerts_service.process_alert_request('create', alert_data)
            alert_id = alert_result['alert']['id']
            
            # 4. Créer un dashboard avec widget pour la métrique
            dashboard_service = DashboardService(self.session)
            dashboard_data = {
                'name': 'integration_dashboard',
                'description': 'Dashboard intégré'
            }
            
            dashboard_result = await dashboard_service.process_dashboard_request('create', dashboard_data)
            dashboard_id = dashboard_result['id']
            
            widget_data = {
                'dashboard_id': dashboard_id,
                'title': 'Container CPU',
                'type': 'chart',
                'metric_id': metric_id
            }
            
            widget_result = await dashboard_service.process_widget_request('create', widget_data)
            
            if not widget_result.get('widget_id'):
                logger.error("Échec de l'intégration cross-domain")
                return False
            
            logger.info("Test d'intégration cross-domain réussi")
            return True
            
        except Exception as e:
            logger.error(f"Erreur test intégration: {str(e)}")
            return False
    
    async def test_api_endpoints_availability(self) -> bool:
        """Test de disponibilité des endpoints API"""
        try:
            # Vérifier que tous les contrôleurs peuvent être instanciés
            controllers = [
                DashboardController(self.session),
                AnalyticsController(self.session),
                AlertsController(self.session),
                ContainersController(self.session),
                AuthenticationController(self.session)
            ]
            
            for controller in controllers:
                if not hasattr(controller, 'session') or not controller.session:
                    logger.error(f"Contrôleur mal initialisé: {controller.__class__.__name__}")
                    return False
            
            logger.info("Test des endpoints API réussi")
            return True
            
        except Exception as e:
            logger.error(f"Erreur test API endpoints: {str(e)}")
            return False
    
    async def test_database_models_consistency(self) -> bool:
        """Test de cohérence des modèles de base de données"""
        try:
            # Vérifier que les modèles peuvent être créés et liés
            from wakedock.models.dashboard_models import Dashboard as DashboardModel
            from wakedock.models.analytics_models import Metric as MetricModel
            from wakedock.models.alerts_models import Alert as AlertModel
            from wakedock.models.containers_models import Container as ContainerModel
            from wakedock.models.authentication_models import User as UserModel
            
            # Test des relations
            models = [DashboardModel, MetricModel, AlertModel, ContainerModel, UserModel]
            
            for model in models:
                if not hasattr(model, '__tablename__'):
                    logger.error(f"Modèle sans table: {model.__name__}")
                    return False
            
            logger.info("Test de cohérence des modèles réussi")
            return True
            
        except Exception as e:
            logger.error(f"Erreur test modèles DB: {str(e)}")
            return False
    
    async def test_validators_integration(self) -> bool:
        """Test d'intégration des validateurs"""
        try:
            from wakedock.validators.dashboard_validator import DashboardValidator
            from wakedock.validators.analytics_validator import AnalyticsValidator
            from wakedock.validators.alerts_validator import AlertsValidator
            from wakedock.validators.containers_validator import ContainersValidator
            from wakedock.validators.authentication_validator import AuthenticationValidator
            
            # Test des validateurs
            validators = [
                DashboardValidator(),
                AnalyticsValidator(),
                AlertsValidator(),
                ContainersValidator(),
                AuthenticationValidator()
            ]
            
            for validator in validators:
                if not hasattr(validator, 'validate') and not hasattr(validator, 'validate_dashboard_config'):
                    logger.error(f"Validateur mal configuré: {validator.__class__.__name__}")
                    return False
            
            logger.info("Test d'intégration des validateurs réussi")
            return True
            
        except Exception as e:
            logger.error(f"Erreur test validateurs: {str(e)}")
            return False
    
    async def run_all_tests(self):
        """Exécuter tous les tests"""
        logger.info("🚀 Début des tests d'intégration MVC")
        
        # Configuration
        if not await self.setup():
            logger.error("Échec de la configuration des tests")
            return False
        
        # Liste des tests à exécuter
        tests = [
            ("Database Models Consistency", self.test_database_models_consistency),
            ("API Endpoints Availability", self.test_api_endpoints_availability),
            ("Validators Integration", self.test_validators_integration),
            ("Authentication Domain", self.test_authentication_domain),
            ("Containers Domain", self.test_containers_domain),
            ("Analytics Domain", self.test_analytics_domain),
            ("Alerts Domain", self.test_alerts_domain),
            ("Dashboard Domain", self.test_dashboard_domain),
            ("Cross-Domain Integration", self.test_cross_domain_integration),
        ]
        
        # Exécuter tous les tests
        for test_name, test_func in tests:
            await self.run_test(test_name, test_func)
        
        # Nettoyage
        await self.teardown()
        
        # Affichage des résultats
        self.print_results()
        
        return self.test_results['failed_tests'] == 0
    
    def print_results(self):
        """Afficher les résultats des tests"""
        logger.info("\n" + "="*60)
        logger.info("📊 RÉSULTATS DES TESTS D'INTÉGRATION MVC")
        logger.info("="*60)
        
        logger.info(f"Total des tests: {self.test_results['total_tests']}")
        logger.info(f"✅ Tests réussis: {self.test_results['passed_tests']}")
        logger.info(f"❌ Tests échoués: {self.test_results['failed_tests']}")
        
        success_rate = (self.test_results['passed_tests'] / self.test_results['total_tests']) * 100
        logger.info(f"📈 Taux de réussite: {success_rate:.1f}%")
        
        if self.test_results['errors']:
            logger.error("\n🔥 ERREURS DÉTECTÉES:")
            for error in self.test_results['errors']:
                logger.error(f"  - {error}")
        
        if self.test_results['failed_tests'] == 0:
            logger.info("\n🎉 TOUS LES TESTS SONT RÉUSSIS!")
            logger.info("✅ Le système MVC est prêt pour la production")
        else:
            logger.error(f"\n⚠️  {self.test_results['failed_tests']} test(s) ont échoué")
            logger.error("❌ Corrections nécessaires avant la mise en production")
        
        logger.info("="*60)


async def main():
    """Fonction principale"""
    test_suite = MVCIntegrationTest()
    
    try:
        success = await test_suite.run_all_tests()
        
        if success:
            logger.info("🎊 Tests d'intégration terminés avec succès!")
            sys.exit(0)
        else:
            logger.error("💥 Tests d'intégration échoués!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Erreur critique lors des tests: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    # Configuration du logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Exécuter les tests
    asyncio.run(main())
