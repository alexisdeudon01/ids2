#!/usr/bin/env bash
#
# Tailscale Setup Script - Installation et configuration
# Usage: ./tailscale_setup.sh [install|login|status|info]
#
set -euo pipefail

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  ${BLUE}$1${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}\n"
}

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_warn() { echo -e "${YELLOW}⚠${NC} $1"; }

# Détection de l'OS
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    elif [[ "$(uname)" == "Darwin" ]]; then
        OS="macos"
        VERSION=$(sw_vers -productVersion)
    else
        OS="unknown"
        VERSION="unknown"
    fi
    echo "$OS"
}

# Installation de Tailscale
install_tailscale() {
    print_header "Installation de Tailscale"
    
    local os=$(detect_os)
    print_info "Système détecté: $os"
    
    # Vérifier si déjà installé
    if command -v tailscale &> /dev/null; then
        local version=$(tailscale version | head -1)
        print_warn "Tailscale est déjà installé: $version"
        read -p "Voulez-vous réinstaller? (y/N): " reinstall
        if [[ ! "$reinstall" =~ ^[Yy]$ ]]; then
            return 0
        fi
    fi
    
    case "$os" in
        ubuntu|debian|raspbian)
            print_info "Installation via apt..."
            # Ajouter la clé GPG
            curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
            # Ajouter le repository
            curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list
            # Installer
            sudo apt-get update
            sudo apt-get install -y tailscale
            ;;
        fedora|centos|rhel)
            print_info "Installation via dnf..."
            sudo dnf config-manager --add-repo https://pkgs.tailscale.com/stable/fedora/tailscale.repo
            sudo dnf install -y tailscale
            ;;
        arch|manjaro)
            print_info "Installation via pacman..."
            sudo pacman -S tailscale
            ;;
        macos)
            print_info "Installation via Homebrew..."
            if ! command -v brew &> /dev/null; then
                print_error "Homebrew n'est pas installé. Installez-le d'abord."
                exit 1
            fi
            brew install tailscale
            ;;
        *)
            print_error "OS non supporté: $os"
            print_info "Visitez https://tailscale.com/download pour les instructions manuelles"
            exit 1
            ;;
    esac
    
    # Démarrer le service
    print_info "Démarrage du service tailscaled..."
    sudo systemctl enable --now tailscaled 2>/dev/null || true
    
    print_success "Tailscale installé avec succès!"
    echo ""
    print_info "Prochaine étape: ./tailscale_setup.sh login"
}

# Connexion à Tailscale
login_tailscale() {
    print_header "Connexion à Tailscale"
    
    if ! command -v tailscale &> /dev/null; then
        print_error "Tailscale n'est pas installé. Exécutez d'abord: ./tailscale_setup.sh install"
        exit 1
    fi
    
    # Vérifier si déjà connecté
    local status=$(tailscale status --json 2>/dev/null | jq -r '.BackendState // "Unknown"' 2>/dev/null || echo "Unknown")
    
    if [[ "$status" == "Running" ]]; then
        print_warn "Vous êtes déjà connecté à Tailscale"
        tailscale status
        echo ""
        read -p "Voulez-vous vous reconnecter? (y/N): " reconnect
        if [[ ! "$reconnect" =~ ^[Yy]$ ]]; then
            return 0
        fi
        sudo tailscale logout
    fi
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  ÉTAPES POUR CRÉER VOTRE TAILNET:${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  1. Si vous n'avez pas de compte Tailscale:"
    echo "     → Allez sur ${BLUE}https://login.tailscale.com/start${NC}"
    echo "     → Connectez-vous avec Google, Microsoft, ou un autre fournisseur"
    echo ""
    echo "  2. Une URL va s'afficher ci-dessous"
    echo "     → Ouvrez-la dans votre navigateur"
    echo "     → Autorisez l'appareil"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    read -p "Appuyez sur Entrée pour continuer..."
    
    # Lancer la connexion
    sudo tailscale up
    
    # Attendre la connexion
    sleep 2
    
    # Afficher le statut
    print_header "Connexion établie!"
    tailscale status
    
    echo ""
    local ip=$(tailscale ip -4 2>/dev/null || echo "Non disponible")
    print_success "Votre IP Tailscale: ${GREEN}$ip${NC}"
}

# Afficher le statut
show_status() {
    print_header "Statut Tailscale"
    
    if ! command -v tailscale &> /dev/null; then
        print_error "Tailscale n'est pas installé"
        exit 1
    fi
    
    # Statut du service
    echo -e "${BLUE}Service:${NC}"
    if systemctl is-active --quiet tailscaled 2>/dev/null; then
        print_success "tailscaled est en cours d'exécution"
    else
        print_error "tailscaled n'est pas en cours d'exécution"
    fi
    
    echo ""
    
    # Statut de la connexion
    echo -e "${BLUE}Connexion:${NC}"
    local backend_state=$(tailscale status --json 2>/dev/null | jq -r '.BackendState // "Unknown"' 2>/dev/null || echo "Unknown")
    
    case "$backend_state" in
        Running)
            print_success "Connecté au tailnet"
            ;;
        NeedsLogin)
            print_warn "Authentification requise - exécutez: ./tailscale_setup.sh login"
            ;;
        Stopped)
            print_error "Tailscale est arrêté"
            ;;
        *)
            print_warn "État: $backend_state"
            ;;
    esac
    
    echo ""
    
    # Appareils du réseau
    echo -e "${BLUE}Appareils sur le tailnet:${NC}"
    tailscale status 2>/dev/null || print_warn "Impossible d'obtenir le statut"
    
    echo ""
    
    # IP locale
    local ip=$(tailscale ip -4 2>/dev/null || echo "Non disponible")
    echo -e "${BLUE}Votre IP Tailscale:${NC} $ip"
}

# Afficher les informations complètes
show_info() {
    print_header "Informations Tailscale"
    
    if ! command -v tailscale &> /dev/null; then
        print_error "Tailscale n'est pas installé"
        exit 1
    fi
    
    # Version
    echo -e "${BLUE}Version:${NC}"
    tailscale version
    echo ""
    
    # IPs
    echo -e "${BLUE}Adresses IP:${NC}"
    echo "  IPv4: $(tailscale ip -4 2>/dev/null || echo 'Non disponible')"
    echo "  IPv6: $(tailscale ip -6 2>/dev/null || echo 'Non disponible')"
    echo ""
    
    # Nom DNS
    local dns_name=$(tailscale status --json 2>/dev/null | jq -r '.Self.DNSName // "Non disponible"' 2>/dev/null || echo "Non disponible")
    echo -e "${BLUE}Nom DNS MagicDNS:${NC} $dns_name"
    echo ""
    
    # Tailnet
    local tailnet=$(tailscale status --json 2>/dev/null | jq -r '.MagicDNSSuffix // "Non disponible"' 2>/dev/null || echo "Non disponible")
    echo -e "${BLUE}Tailnet:${NC} $tailnet"
    echo ""
    
    # Informations pour config.yaml
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  VALEURS POUR VOTRE CONFIGURATION:${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Ajoutez ces valeurs à votre configuration:"
    echo ""
    echo "  RASPBERRY_PI_TAILSCALE_IP: $(tailscale ip -4 2>/dev/null || echo 'À REMPLIR')"
    echo "  TAILSCALE_TAILNET: $tailnet"
    echo ""
    echo "  Pour obtenir une clé API Tailscale:"
    echo "  → ${BLUE}https://login.tailscale.com/admin/settings/keys${NC}"
    echo ""
    echo "  Pour créer un OAuth Client (recommandé pour CI/CD):"
    echo "  → ${BLUE}https://login.tailscale.com/admin/settings/oauth${NC}"
    echo ""
}

# Créer une clé d'authentification
create_authkey() {
    print_header "Création d'une clé d'authentification"
    
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  POUR CRÉER UNE CLÉ D'AUTH:${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  1. Allez sur: ${BLUE}https://login.tailscale.com/admin/settings/keys${NC}"
    echo ""
    echo "  2. Cliquez sur 'Generate auth key'"
    echo ""
    echo "  3. Options recommandées:"
    echo "     ☑ Reusable (pour CI/CD)"
    echo "     ☑ Ephemeral (les nœuds disparaissent après déconnexion)"
    echo "     ☐ Pre-authorized (optionnel)"
    echo ""
    echo "  4. Copiez la clé générée (commence par tskey-auth-...)"
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}  POUR CRÉER UN CLIENT OAUTH (RECOMMANDÉ POUR CI/CD):${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  1. Allez sur: ${BLUE}https://login.tailscale.com/admin/settings/oauth${NC}"
    echo ""
    echo "  2. Cliquez sur 'Generate OAuth client'"
    echo ""
    echo "  3. Sélectionnez les scopes:"
    echo "     ☑ devices:read"
    echo "     ☑ devices:write (si nécessaire)"
    echo ""
    echo "  4. Ajoutez un tag: ${GREEN}tag:ci${NC}"
    echo "     (Créez d'abord le tag dans Access Controls si nécessaire)"
    echo ""
    echo "  5. Notez:"
    echo "     - Client ID"
    echo "     - Client Secret"
    echo ""
}

# Tester la connectivité avec un autre appareil
test_connectivity() {
    print_header "Test de connectivité"
    
    if ! command -v tailscale &> /dev/null; then
        print_error "Tailscale n'est pas installé"
        exit 1
    fi
    
    # Lister les appareils
    echo -e "${BLUE}Appareils disponibles:${NC}"
    tailscale status
    echo ""
    
    # Demander l'IP à tester
    read -p "Entrez l'IP Tailscale à tester (ex: 100.64.x.x): " target_ip
    
    if [[ -z "$target_ip" ]]; then
        print_error "IP non fournie"
        exit 1
    fi
    
    echo ""
    print_info "Test de ping vers $target_ip..."
    
    if tailscale ping -c 3 "$target_ip"; then
        print_success "Connectivité OK!"
    else
        print_error "Échec de la connexion"
        echo ""
        print_info "Vérifiez que:"
        echo "  - L'appareil cible est connecté à Tailscale"
        echo "  - L'appareil cible est autorisé dans votre tailnet"
        echo "  - Il n'y a pas de règles ACL qui bloquent"
    fi
}

# Menu principal
show_help() {
    echo ""
    echo -e "${CYAN}Tailscale Setup Script${NC}"
    echo ""
    echo "Usage: $0 <commande>"
    echo ""
    echo "Commandes:"
    echo "  install     Installer Tailscale sur ce système"
    echo "  login       Se connecter à Tailscale (créer/rejoindre un tailnet)"
    echo "  status      Afficher le statut de la connexion"
    echo "  info        Afficher les informations détaillées"
    echo "  keys        Instructions pour créer des clés d'auth"
    echo "  test        Tester la connectivité avec un autre appareil"
    echo "  help        Afficher cette aide"
    echo ""
    echo "Workflow recommandé:"
    echo "  1. $0 install    # Installer Tailscale"
    echo "  2. $0 login      # Se connecter (crée le tailnet automatiquement)"
    echo "  3. $0 info       # Obtenir les infos pour la config"
    echo "  4. $0 test       # Tester la connectivité"
    echo ""
}

# Point d'entrée
case "${1:-help}" in
    install)
        install_tailscale
        ;;
    login)
        login_tailscale
        ;;
    status)
        show_status
        ;;
    info)
        show_info
        ;;
    keys)
        create_authkey
        ;;
    test)
        test_connectivity
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Commande inconnue: $1"
        show_help
        exit 1
        ;;
esac
