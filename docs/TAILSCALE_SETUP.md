# Guide de Configuration Tailscale

Ce guide vous accompagne dans la création et configuration de votre réseau Tailscale (tailnet) pour le projet IDS.

## Qu'est-ce que Tailscale ?

**Tailscale** est un VPN mesh basé sur WireGuard qui permet de connecter vos appareils de manière sécurisée, peu importe où ils se trouvent.

**Tailnet** = votre réseau privé Tailscale (l'ensemble de vos appareils connectés).

```
┌─────────────────────────────────────────────────────────────┐
│                      VOTRE TAILNET                          │
│                                                             │
│   💻 PC Local  ←─────────→  🍓 Raspberry Pi                │
│        ↑           VPN           ↑                          │
│        │         chiffré         │                          │
│        ↓                         ↓                          │
│   🤖 Automatisation  ←────→  ☁️ Cloud                      │
│                                                             │
│   Tous sur IPs privées: 100.x.x.x                          │
└─────────────────────────────────────────────────────────────┘
```

## Étape 1: Installation

### Sur votre PC (Linux/Ubuntu)

```bash
# Utiliser le script fourni
./scripts/tailscale_setup.sh install

# Ou manuellement
curl -fsSL https://tailscale.com/install.sh | sh
```

### Sur Raspberry Pi

```bash
# Même commande
curl -fsSL https://tailscale.com/install.sh | sh
sudo systemctl enable --now tailscaled
```

### Sur macOS

```bash
brew install tailscale
```

## Étape 2: Connexion et Création du Tailnet

```bash
# Sur chaque machine
./scripts/tailscale_setup.sh login
# ou
sudo tailscale up
```

Une URL s'affichera. Ouvrez-la dans votre navigateur pour :
1. **Créer un compte** (si vous n'en avez pas) via Google, Microsoft, ou un autre fournisseur
2. **Autoriser l'appareil** à rejoindre votre tailnet

Le tailnet est créé automatiquement avec votre premier appareil !

## Étape 3: Vérification

```bash
# Vérifier le statut
./scripts/tailscale_setup.sh status

# Ou avec le script Python
python scripts/tailscale_verify.py

# Voir tous les appareils
tailscale status
```

## Étape 4: Configuration CI/CD

### Créer un Client OAuth (Recommandé)

1. Allez sur https://login.tailscale.com/admin/settings/oauth
2. Cliquez **"Generate OAuth client"**
3. Sélectionnez les scopes :
   - ✅ `devices:read`
   - ✅ `devices:write` (optionnel)
4. **Important**: Ajoutez le tag `tag:ci`
5. Notez le **Client ID** et **Client Secret**

### Créer un Tag (si nécessaire)

1. Allez sur https://login.tailscale.com/admin/acls
2. Ajoutez dans la section `tagOwners` :

```json
{
  "tagOwners": {
    "tag:ci": ["autogroup:admin"]
  }
}
```

### Créer une API Key

1. Allez sur https://login.tailscale.com/admin/settings/keys
2. Cliquez **"Generate API key"**
3. Notez la clé (commence par `tskey-api-...`)

## Étape 5: Configurer les variables d’environnement

Définissez ces variables (dans votre shell, fichier `.env`, ou gestionnaire de secrets) :

| Variable | Description | Exemple |
|----------|-------------|---------|
| `TAILSCALE_TAILNET` | Nom de votre tailnet | `example.com` |
| `TAILSCALE_API_KEY` | Clé API | `tskey-api-xxx` |
| `TAILSCALE_OAUTH_CLIENT_ID` | OAuth Client ID | `kxxx` |
| `TAILSCALE_OAUTH_CLIENT_SECRET` | OAuth Secret | `tskey-client-xxx` |
| `RASPBERRY_PI_TAILSCALE_IP` | IP du Pi dans Tailscale | `100.64.x.x` |

## Commandes Utiles

```bash
# Statut complet
tailscale status

# Votre IP Tailscale
tailscale ip -4

# Ping un appareil
tailscale ping 100.64.x.x

# Informations détaillées
tailscale status --json | jq

# Nom DNS de votre tailnet
tailscale status --json | jq -r '.MagicDNSSuffix'

# Se déconnecter
sudo tailscale logout

# Redémarrer
sudo systemctl restart tailscaled
```

## Dépannage

### "NeedsLogin" ou "Non connecté"

```bash
sudo tailscale up
```

### Service non démarré

```bash
sudo systemctl start tailscaled
sudo systemctl enable tailscaled
```

### Appareil non autorisé

1. Allez sur https://login.tailscale.com/admin/machines
2. Trouvez l'appareil et cliquez **"Authorize"**

### Ping échoue

1. Vérifiez que l'appareil cible est en ligne
2. Vérifiez les ACLs sur https://login.tailscale.com/admin/acls
3. Essayez `tailscale ping --verbose IP`

## Architecture du Projet avec Tailscale

```
Runner d’automatisation (optionnel)
        │
        │ (OAuth: tag:ci)
        ▼
   ┌─────────┐
   │ Tailnet │
   └─────────┘
        │
        │ (100.64.x.x)
        ▼
  Raspberry Pi
   - Reçoit le déploiement
   - Exécute l'agent IDS
```

## Scripts Disponibles

| Script | Description |
|--------|-------------|
| `scripts/tailscale_setup.sh` | Installation et configuration |
| `scripts/tailscale_verify.py` | Vérification complète |
| `scripts/tailnet_monitor.py` | Visualisation du réseau |

## Liens Utiles

- [Documentation Tailscale](https://tailscale.com/kb/)
- [Console Admin](https://login.tailscale.com/admin)
- [ACLs et Politiques](https://tailscale.com/kb/1018/acls/)
- [OAuth Clients](https://tailscale.com/kb/1215/oauth-clients/)
