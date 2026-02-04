# Tailscale Network Monitor & Visualizer

## 📋 Description

Un système de monitoring et visualisation de réseau Tailscale mesh qui permet de :
- 🔍 Capturer l'état complet du réseau Tailscale
- 📡 Mesurer la latence en temps réel vers tous les nœuds
- 🎨 Visualiser le réseau de manière interactive
- 📊 Afficher des statistiques de santé du réseau

## 🚀 Fonctionnalités

### 1. **State Representation**
- Capture un snapshot "point-in-time" de tous les devices
- Inclut les IPs Tailscale, tags, et statuts

### 2. **Monitoring & Latency Measurement**
- Utilise `tailscale ping` pour mesurer la latence réelle
- Calcule la latence moyenne du mesh
- Identifie les nœuds en ligne vs hors ligne

### 3. **Visualisation Interactive**
- Génère un graphe HTML interactif avec **Pyvis**
- **Taille des nœuds inversement proportionnelle à la latence** :
  - ✅ Nœud plus **gros** = **latence plus faible** (meilleur)
  - ⚠️ Nœud plus **petit** = **latence plus élevée**
- **Couleurs** :
  - 🟢 Vert = En ligne
  - 🔴 Rouge = Hors ligne
- **Clic sur un nœud** → Ouvre la console Tailscale pour ce device
- **Hover** → Affiche les détails (OS, IP, tags, latence)

### 4. **Sécurité**
- Utilise `getpass` pour saisir l'API key (jamais affichée)
- Aucune clé API n'est loggée ou imprimée

## 📦 Dépendances

```bash
pip install pyvis networkx requests tailscale
```

Ou via `requirements.txt` du projet :
```bash
pip install -r requirements.txt
```

## 🔑 Prérequis

### 1. Tailscale API Key
Créez une clé API dans votre dashboard Tailscale :
- 🔗 https://login.tailscale.com/admin/settings/keys
- Sélectionnez "Generate API key"
- Donnez les permissions : **Read** sur **Devices**

### 2. Tailscale CLI
Le script utilise `tailscale ping` pour mesurer la latence :
```bash
# Linux
curl -fsSL https://tailscale.com/install.sh | sh

# macOS
brew install tailscale

# Vérifier
tailscale version
```

### 3. Authentification Tailscale
Assurez-vous que votre machine est connectée au tailnet :
```bash
tailscale up
tailscale status
```

## 🎯 Utilisation

### Lancement interactif
```bash
cd scripts/
python3 tailscale_network_monitor.py
```

Vous serez invité à saisir :
1. **Tailscale API Key** (saisie cachée)
2. **Tailnet Name** (ex: `example.com` ou `user@example.com`)

### Exemple de sortie
```
============================================================
🌐 TAILSCALE NETWORK MONITOR & VISUALIZER
============================================================

🔑 Enter Tailscale API Key: 
🏢 Enter Tailnet Name (e.g., example.com or user@example.com): mycompany.com

🔍 Fetching device list from Tailscale API...
✅ Found 5 nodes (4 online)

📊 Measuring network latency...
  📡 Pinging server-1 (100.64.0.1)... ✓ 12.5ms
  📡 Pinging desktop (100.64.0.2)... ✓ 8.3ms
  📡 Pinging rpi (100.64.0.3)... ✓ 23.1ms
  📡 Pinging laptop (100.64.0.4)... ✗ Timeout

✅ Average mesh latency: 14.63ms

🎨 Generating interactive network visualization...
✅ Interactive Network Health Map generated: 'tailscale_network_map.html'

📈 Network Statistics:
   Total Nodes: 5
   Online Nodes: 4
   Average Latency: 14.63ms

💡 Tip: Node size is inversely proportional to latency (bigger = faster)
💡 Click any node to open its Tailscale console page

✅ Monitoring cycle complete!
```

### Visualisation générée
Le script crée un fichier `tailscale_network_map.html` :
- Ouvrez-le dans votre navigateur
- **Interagissez** avec le graphe :
  - Zoom avec la molette
  - Drag & drop des nœuds
  - Hover pour voir les détails
  - Clic pour ouvrir la console Tailscale

## 📊 Interprétation du Graphe

### Taille des Nœuds
```
🔵 Gros nœud (40px)  → Latence très faible (<20ms)  → ⚡ Excellent
🔵 Moyen (30px)      → Latence moyenne (20-50ms)    → ✅ Bon
🔵 Petit (15px)      → Latence élevée (>50ms)       → ⚠️ À surveiller
```

### Couleurs des Nœuds
- 🟢 **Vert** : Device en ligne et accessible
- 🔴 **Rouge** : Device hors ligne

### Épaisseur des Liens
- **Lien épais** : Faible latence (bonne connexion)
- **Lien fin** : Latence élevée ou pas de données

## 🔧 Intégration dans l'automation

Le script peut être utilisé dans votre pipeline d'automation pour valider la connectivité du mesh :

```bash
# Exemple avec variables d'environnement
export TAILSCALE_API_KEY="tskey-api-..."
export TAILSCALE_TAILNET="yourname.ts.net"
python3 scripts/tailscale_monitor.py --output network_snapshot.html
```

## 🐛 Dépannage

### "Tailscale CLI not found"
```bash
# Installer Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
```

### "API Error: 401 Unauthorized"
- Vérifiez que votre API key est valide
- Assurez-vous qu'elle a les permissions **Read** sur **Devices**

### "Ping timeout"
- Vérifiez que votre machine est connectée au tailnet : `tailscale status`
- Certains nœuds peuvent avoir des firewalls qui bloquent ICMP

### Latence à -1ms
- Le nœud n'a pas répondu au ping
- Peut être hors ligne ou derrière un firewall strict

## 📚 Ressources

- [Tailscale API Documentation](https://tailscale.com/api)
- [Pyvis Documentation](https://pyvis.readthedocs.io/)
- [Tailscale Download](https://tailscale.com/download)

## 👨‍💻 Auteur

Développé pour le projet IDS avec Tailscale mesh networking.
