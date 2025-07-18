"""
Gestionnaire pour les fichiers .env dynamiques
"""
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

class EnvVariable(BaseModel):
    """Modèle pour une variable d'environnement"""
    name: str
    value: str
    description: Optional[str] = None
    is_secret: bool = False
    is_required: bool = True
    default_value: Optional[str] = None
    
    @validator('name')
    def validate_name(cls, v):
        """Valide le nom de la variable"""
        if not re.match(r'^[A-Z][A-Z0-9_]*$', v):
            raise ValueError(f"Nom de variable invalide: {v}")
        return v

class EnvFile(BaseModel):
    """Modèle pour un fichier .env"""
    path: str
    variables: Dict[str, EnvVariable]
    comments: List[str] = Field(default_factory=list)
    
    def get_variable(self, name: str) -> Optional[EnvVariable]:
        """Récupère une variable par nom"""
        return self.variables.get(name)
    
    def set_variable(self, name: str, value: str, **kwargs):
        """Définit une variable"""
        self.variables[name] = EnvVariable(name=name, value=value, **kwargs)
    
    def remove_variable(self, name: str):
        """Supprime une variable"""
        if name in self.variables:
            del self.variables[name]

class EnvManager:
    """Gestionnaire pour les fichiers .env"""
    
    # Variables sensibles qui ne doivent pas être loggées
    SENSITIVE_PATTERNS = [
        r'.*PASSWORD.*', r'.*SECRET.*', r'.*KEY.*', r'.*TOKEN.*',
        r'.*API_KEY.*', r'.*PRIVATE_KEY.*', r'.*CREDENTIAL.*'
    ]
    
    # Variables système importantes
    SYSTEM_VARS = {'PATH', 'HOME', 'USER', 'SHELL', 'TERM'}
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
    
    def load_env_file(self, file_path: str) -> EnvFile:
        """
        Charge un fichier .env
        
        Args:
            file_path: Chemin vers le fichier .env
            
        Returns:
            EnvFile: Fichier .env chargé
            
        Raises:
            FileNotFoundError: Si le fichier n'existe pas
            ValueError: Si le fichier est mal formaté
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Fichier .env non trouvé: {file_path}")
        
        variables = {}
        comments = []
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Ignorer les lignes vides
                    if not line:
                        continue
                    
                    # Collecter les commentaires
                    if line.startswith('#'):
                        comments.append(line)
                        continue
                    
                    # Parser les variables
                    var = self._parse_env_line(line, line_num)
                    if var:
                        variables[var.name] = var
            
            return EnvFile(
                path=str(path),
                variables=variables,
                comments=comments
            )
            
        except Exception as e:
            raise ValueError(f"Erreur lors du chargement de {file_path}: {e}")
    
    def save_env_file(self, env_file: EnvFile, backup: bool = True):
        """
        Sauvegarde un fichier .env
        
        Args:
            env_file: Fichier .env à sauvegarder
            backup: Créer une sauvegarde avant modification
        """
        path = Path(env_file.path)
        
        # Créer une sauvegarde si demandé
        if backup and path.exists():
            backup_path = path.with_suffix(f'.env.backup')
            backup_path.write_text(path.read_text())
            self.logger.info(f"Sauvegarde créée: {backup_path}")
        
        # Générer le contenu
        content_lines = []
        
        # Ajouter les commentaires en en-tête
        for comment in env_file.comments:
            content_lines.append(comment)
        
        if env_file.comments:
            content_lines.append('')  # Ligne vide après les commentaires
        
        # Ajouter les variables
        for var in env_file.variables.values():
            if var.description:
                content_lines.append(f"# {var.description}")
            
            if var.is_secret:
                content_lines.append(f"# ATTENTION: Variable sensible")
            
            content_lines.append(f"{var.name}={var.value}")
            content_lines.append('')  # Ligne vide après chaque variable
        
        # Écrire le fichier
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content_lines))
            
            self.logger.info(f"Fichier .env sauvegardé: {path}")
            
        except Exception as e:
            raise ValueError(f"Erreur lors de la sauvegarde de {path}: {e}")
    
    def create_env_file(self, file_path: str, variables: Dict[str, str] = None) -> EnvFile:
        """
        Crée un nouveau fichier .env
        
        Args:
            file_path: Chemin du nouveau fichier
            variables: Variables initiales
            
        Returns:
            EnvFile: Nouveau fichier .env
        """
        path = Path(file_path)
        
        # Créer le répertoire parent si nécessaire
        path.parent.mkdir(parents=True, exist_ok=True)
        
        env_vars = {}
        if variables:
            for name, value in variables.items():
                env_vars[name] = EnvVariable(
                    name=name,
                    value=value,
                    is_secret=self._is_sensitive_variable(name)
                )
        
        env_file = EnvFile(
            path=str(path),
            variables=env_vars,
            comments=[
                "# Configuration WakeDock",
                f"# Généré automatiquement le {Path().ctime()}",
                "# Modifiez avec précaution"
            ]
        )
        
        self.save_env_file(env_file, backup=False)
        return env_file
    
    def merge_env_files(self, *env_files: EnvFile) -> EnvFile:
        """
        Fusionne plusieurs fichiers .env
        
        Args:
            env_files: Fichiers .env à fusionner
            
        Returns:
            EnvFile: Fichier .env fusionné
        """
        if not env_files:
            raise ValueError("Au moins un fichier .env requis")
        
        merged_variables = {}
        merged_comments = []
        
        for env_file in env_files:
            # Fusionner les commentaires
            merged_comments.extend(env_file.comments)
            
            # Fusionner les variables (les dernières écrasent les premières)
            merged_variables.update(env_file.variables)
        
        return EnvFile(
            path="merged.env",
            variables=merged_variables,
            comments=list(set(merged_comments))  # Supprimer les doublons
        )
    
    def validate_env_file(self, env_file: EnvFile) -> Tuple[bool, List[str], List[str]]:
        """
        Valide un fichier .env
        
        Returns:
            Tuple (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        for var in env_file.variables.values():
            # Vérifier les noms de variables
            if not re.match(r'^[A-Z][A-Z0-9_]*$', var.name):
                errors.append(f"Nom de variable invalide: {var.name}")
            
            # Vérifier les variables système
            if var.name in self.SYSTEM_VARS:
                warnings.append(f"Modification de variable système: {var.name}")
            
            # Vérifier les variables sensibles
            if self._is_sensitive_variable(var.name) and not var.is_secret:
                warnings.append(f"Variable sensible non marquée: {var.name}")
            
            # Vérifier les valeurs vides pour les variables requises
            if var.is_required and not var.value:
                errors.append(f"Variable requise vide: {var.name}")
            
            # Vérifier les valeurs suspectes
            if self._has_suspicious_value(var.value):
                warnings.append(f"Valeur suspecte pour {var.name}")
        
        return len(errors) == 0, errors, warnings
    
    def substitute_variables(self, text: str, env_file: EnvFile) -> str:
        """
        Substitue les variables d'environnement dans un texte
        
        Args:
            text: Texte avec des variables ${VAR} ou $VAR
            env_file: Fichier .env contenant les variables
            
        Returns:
            Texte avec variables substituées
        """
        result = text
        
        # Substitution des variables ${VAR}
        def replace_bracketed(match):
            var_name = match.group(1)
            var = env_file.get_variable(var_name)
            if var:
                return var.value
            # Essayer les variables d'environnement système
            return os.environ.get(var_name, match.group(0))
        
        result = re.sub(r'\$\{([A-Z_][A-Z0-9_]*)\}', replace_bracketed, result)
        
        # Substitution des variables $VAR
        def replace_simple(match):
            var_name = match.group(1)
            var = env_file.get_variable(var_name)
            if var:
                return var.value
            return os.environ.get(var_name, match.group(0))
        
        result = re.sub(r'\$([A-Z_][A-Z0-9_]*)', replace_simple, result)
        
        return result
    
    def get_environment_diff(self, env_file1: EnvFile, env_file2: EnvFile) -> Dict[str, Any]:
        """
        Compare deux fichiers .env et retourne les différences
        
        Returns:
            Dict avec 'added', 'removed', 'modified'
        """
        vars1 = set(env_file1.variables.keys())
        vars2 = set(env_file2.variables.keys())
        
        added = vars2 - vars1
        removed = vars1 - vars2
        common = vars1 & vars2
        
        modified = []
        for var_name in common:
            var1 = env_file1.variables[var_name]
            var2 = env_file2.variables[var_name]
            if var1.value != var2.value:
                modified.append({
                    'name': var_name,
                    'old_value': var1.value if not var1.is_secret else '***',
                    'new_value': var2.value if not var2.is_secret else '***'
                })
        
        return {
            'added': list(added),
            'removed': list(removed),
            'modified': modified
        }
    
    def generate_env_template(self, services: List[str]) -> EnvFile:
        """
        Génère un template .env basé sur une liste de services
        
        Args:
            services: Liste des noms de services
            
        Returns:
            EnvFile: Template .env
        """
        variables = {}
        
        # Variables communes
        common_vars = {
            'COMPOSE_PROJECT_NAME': 'wakedock',
            'COMPOSE_FILE': 'docker-compose.yml',
            'WAKEDOCK_ENV': 'development',
            'WAKEDOCK_DEBUG': 'false',
            'WAKEDOCK_LOG_LEVEL': 'INFO'
        }
        
        for name, value in common_vars.items():
            variables[name] = EnvVariable(
                name=name,
                value=value,
                description=f"Configuration pour {name.lower()}"
            )
        
        # Variables spécifiques par service
        service_vars = {
            'postgres': {
                'POSTGRES_DB': 'wakedock',
                'POSTGRES_USER': 'wakedock',
                'POSTGRES_PASSWORD': 'change_me',
                'POSTGRES_HOST': 'postgres',
                'POSTGRES_PORT': '5432'
            },
            'redis': {
                'REDIS_URL': 'redis://redis:6379/0',
                'REDIS_PASSWORD': ''
            },
            'nginx': {
                'NGINX_HOST': 'localhost',
                'NGINX_PORT': '80'
            }
        }
        
        for service in services:
            if service in service_vars:
                for name, value in service_vars[service].items():
                    variables[name] = EnvVariable(
                        name=name,
                        value=value,
                        description=f"Configuration pour le service {service}",
                        is_secret='PASSWORD' in name or 'SECRET' in name
                    )
        
        return EnvFile(
            path=".env.template",
            variables=variables,
            comments=[
                "# Template de configuration WakeDock",
                "# Copiez ce fichier vers .env et modifiez les valeurs",
                "# Variables sensibles marquées avec ATTENTION"
            ]
        )
    
    def _parse_env_line(self, line: str, line_num: int) -> Optional[EnvVariable]:
        """Parse une ligne de fichier .env"""
        # Format: KEY=value ou KEY="value" ou KEY='value'
        match = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$', line)
        if not match:
            self.logger.warning(f"Ligne {line_num} ignorée: format invalide")
            return None
        
        name = match.group(1)
        value = match.group(2)
        
        # Supprimer les guillemets si présents
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        
        return EnvVariable(
            name=name,
            value=value,
            is_secret=self._is_sensitive_variable(name)
        )
    
    def _is_sensitive_variable(self, name: str) -> bool:
        """Détermine si une variable est sensible"""
        name_upper = name.upper()
        return any(re.match(pattern, name_upper) for pattern in self.SENSITIVE_PATTERNS)
    
    def _has_suspicious_value(self, value: str) -> bool:
        """Détecte les valeurs suspectes"""
        suspicious_patterns = [
            r'^(password|secret|key|token)$',  # Valeurs génériques
            r'^(admin|test|demo|example)$',    # Valeurs de test
            r'^(123456|password123|admin123)$'  # Mots de passe faibles
        ]
        
        value_lower = value.lower()
        return any(re.match(pattern, value_lower) for pattern in suspicious_patterns)
