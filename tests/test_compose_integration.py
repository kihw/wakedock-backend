"""
Tests d'intégration pour le système Docker Compose
"""
import pytest
import tempfile
import os
from pathlib import Path
import yaml

# Exemple simple sans dépendances circulaires
SIMPLE_COMPOSE = """
version: '3.8'

services:
  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=testdb

  web:
    image: nginx:alpine
    depends_on:
      - db
    ports:
      - "80:80"
"""

SAMPLE_ENV = """
# Configuration de base
NGINX_HOST=localhost
DB_NAME=production_db
DB_USER=admin
DB_PASSWORD=secure_password_123

# Configuration avancée
DEBUG=false
LOG_LEVEL=info
"""

def test_compose_parser_basic():
    """Test basique du parser Docker Compose"""
    import sys
    sys.path.insert(0, '/Docker/code/wakedock-env/wakedock-backend')
    
    try:
        from wakedock.core.compose_parser import ComposeParser
        
        # Créer un fichier temporaire
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(SIMPLE_COMPOSE)
            compose_file = f.name
        
        try:
            # Parser le fichier
            parser = ComposeParser()
            compose_data = parser.parse_file(compose_file)
            
            # Vérifications basiques
            assert compose_data is not None
            assert hasattr(compose_data, 'services')
            assert 'web' in compose_data.services
            assert 'db' in compose_data.services
            
            print("✅ Test du parser Compose réussi")
            return True
            
        finally:
            os.unlink(compose_file)
            
    except Exception as e:
        print(f"❌ Erreur lors du test du parser: {e}")
        return False

def test_env_manager_basic():
    """Test basique du gestionnaire de fichiers .env"""
    import sys
    sys.path.insert(0, '/Docker/code/wakedock-env/wakedock-backend')
    
    try:
        from wakedock.core.env_manager import EnvManager
        
        # Créer un fichier .env temporaire
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(SAMPLE_ENV)
            env_file = f.name
        
        try:
            # Charger le fichier
            manager = EnvManager()
            env_data = manager.load_env_file(env_file)
            
            # Vérifications basiques
            assert env_data is not None
            assert 'NGINX_HOST' in env_data.variables
            assert env_data.variables['NGINX_HOST'].value == 'localhost'
            assert env_data.variables['DB_NAME'].value == 'production_db'
            
            print("✅ Test du gestionnaire .env réussi")
            return True
            
        finally:
            os.unlink(env_file)
            
    except Exception as e:
        print(f"❌ Erreur lors du test du gestionnaire .env: {e}")
        return False

def test_dependency_manager_basic():
    """Test basique du gestionnaire de dépendances"""
    import sys
    sys.path.insert(0, '/Docker/code/wakedock-env/wakedock-backend')
    
    try:
        from wakedock.core.dependency_manager import DependencyManager
        from wakedock.core.compose_parser import ComposeParser
        
        # Créer un fichier temporaire avec le compose
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(SIMPLE_COMPOSE)
            compose_file = f.name
        
        try:
            # Parser le fichier d'abord
            parser = ComposeParser()
            compose_data = parser.parse_file(compose_file)
            
            # Analyser les dépendances
            manager = DependencyManager()
            graph = manager.analyze_dependencies(compose_data)
            startup_order = graph.get_startup_order()
            
            # Vérifications
            assert len(startup_order) >= 1
            # db devrait être avant web dans l'ordre de démarrage
            assert 'db' in startup_order
            assert 'web' in startup_order
            db_index = startup_order.index('db')
            web_index = startup_order.index('web')
            assert db_index < web_index
            
            print("✅ Test du gestionnaire de dépendances réussi")
            return True
            
        finally:
            os.unlink(compose_file)
        
    except Exception as e:
        print(f"❌ Erreur lors du test du gestionnaire de dépendances: {e}")
        return False

def run_all_tests():
    """Exécuter tous les tests"""
    print("🧪 Démarrage des tests d'intégration Docker Compose...")
    
    tests = [
        test_compose_parser_basic,
        test_env_manager_basic,
        test_dependency_manager_basic
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Erreur lors de l'exécution du test {test.__name__}: {e}")
            failed += 1
    
    print(f"\n📊 Résultats des tests:")
    print(f"✅ Réussis: {passed}")
    print(f"❌ Échoués: {failed}")
    print(f"📈 Total: {passed + failed}")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
