#!/bin/bash

echo "--- Configuration de l'environnement virtuel ---"

# 1. Se déplacer dans le répertoire du projet
#cd /home/tor/Downloads/ids2

# 2. Créer l'environnement virtuel nommé 'venv'
# Assurez-vous d'avoir 'python3-venv' installé si nécessaire (sudo apt install python3-venv)
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
echo "venv/" >> .gitignore
sort -u .gitignore -o .gitignore # Supprime les doublons si 'venv/' était déjà là
