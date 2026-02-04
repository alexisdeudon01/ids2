#!/bin/bash
set -euo pipefail

echo "--- Configuration de l'environnement virtuel ---"

# Check python3 availability
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 command not found. Please install Python 3 first."
  exit 1
fi

# Check python3-venv module availability
if ! python3 -c "import venv" 2>/dev/null; then
  echo "❌ python3-venv module not available."
  echo "Install with: sudo apt-get install -y python3-venv"
  exit 1
fi

# 1. Se déplacer dans le répertoire du projet (use script directory)
cd "$(dirname "$0")" || exit 1

# 2. Créer l'environnement virtuel nommé 'venv'
python3 -m venv venv

echo "Environnement 'venv' créé."

# 3. Activer l'environnement (A faire manuellement ensuite)
echo "Pour activer l'environnement, utilisez la commande suivante :"
echo "source venv/bin/activate"

# 4. Installer les dépendances du projet (si vous avez un fichier requirements.txt)
if [ -f "requirements.txt" ]; then
    echo "Installation des dépendances depuis requirements.txt..."
    source venv/bin/activate
    pip install -r requirements.txt
    deactivate
    echo "Dépendances installées et désactivées."
else
    echo "Pas de fichier requirements.txt trouvé. Installez les librairies manuellement après activation."
fi

# 5. Ajouter 'venv' à .gitignore pour ne pas le versionner sur GitHub
echo "Ajout de 'venv/' au fichier .gitignore"
# Ensure .gitignore exists before appending
touch .gitignore
echo "venv/" >> .gitignore
sort -u .gitignore -o .gitignore # Supprime les doublons si 'venv/' était déjà là
