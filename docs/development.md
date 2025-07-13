# Développement WakeDock Backend

## Installation

1. Installer les dépendances :
```bash
pip install -r requirements-dev.txt
```

2. Configurer la base de données :
```bash
python scripts/init_db.py
```

3. Ajouter des données de test :
```bash
python scripts/seed_data.py
```

## Lancement

### Mode développement
```bash
python -m wakedock.main
```

### Avec uvicorn
```bash
uvicorn wakedock.main:app --reload --host 0.0.0.0 --port 8000
```

## Tests

### Tests unitaires
```bash
pytest tests/unit/
```

### Tests d'intégration
```bash
pytest tests/integration/
```

### Tous les tests
```bash
pytest
```

## Base de données

### Créer une migration
```bash
alembic revision --autogenerate -m "Description"
```

### Appliquer les migrations
```bash
alembic upgrade head
```

## Structure

```
wakedock/
├── api/           # Routes API et authentification
├── core/          # Services principaux (Caddy, orchestrateur)
├── database/      # Modèles et gestion BDD
├── security/      # Validation et sécurité
└── utils/         # Utilitaires
```
