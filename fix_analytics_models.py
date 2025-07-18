#!/usr/bin/env python3
"""
Script de correction rapide pour les modèles Analytics
"""

import sys
import re
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

print("🔧 CORRECTION RAPIDE DES MODÈLES ANALYTICS")
print("=" * 60)

# Lire le fichier analytics_models.py
analytics_file = Path("wakedock/models/analytics_models.py")

if analytics_file.exists():
    content = analytics_file.read_text()
    
    # Corrections nécessaires
    corrections = [
        # Remplacer Base par BaseModel pour les classes qui héritent de Base
        (r'class (\w+)\(Base, UUIDMixin, TimestampMixin\):', r'class \1(BaseModel, UUIDMixin):'),
        (r'class (\w+)\(Base, TimestampMixin\):', r'class \1(BaseModel):'),
        (r'class (\w+)\(Base, UUIDMixin\):', r'class \1(BaseModel, UUIDMixin):'),
        (r'class (\w+)\(Base\):', r'class \1(BaseModel):'),
        # Ajouter extend_existing à toutes les tables
        (r'(__tablename__ = [\'"][^\'\"]+[\'"])', r'\1\n    __table_args__ = {\'extend_existing\': True}'),
    ]
    
    original_content = content
    
    for pattern, replacement in corrections:
        content = re.sub(pattern, replacement, content)
    
    # Écrire le fichier corrigé
    if content != original_content:
        analytics_file.write_text(content)
        print("✅ Fichier analytics_models.py corrigé")
    else:
        print("ℹ️  Aucune correction nécessaire")
    
    print("\n📊 RÉSUMÉ DES CORRECTIONS:")
    print("- Remplacement de Base par BaseModel")
    print("- Ajout d'extend_existing pour éviter les conflits")
    print("- Correction des héritages de classes")
    
else:
    print("❌ Fichier analytics_models.py non trouvé")

print("\n" + "=" * 60)
print("🎉 CORRECTIONS TERMINÉES")
print("=" * 60)
