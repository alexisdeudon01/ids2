#!/usr/bin/env python3
"""
=============================================================================
PROJECT MANAGER - Script unifié de gestion de projet
=============================================================================
Combine quatre fonctionnalités :
1. Détection et installation des dépendances Python (requirements.txt)
2. Vérification des logiciels système (docker, git, etc.)
3. Exécution hiérarchique des scripts selon leurs dépendances
4. Génération d'un graphe HTML interactif des dépendances
=============================================================================
"""

import os
import re
import subprocess
import sys
import shutil
import argparse
import json
from datetime import datetime

# --- CONFIGURATION ---
PROJECT_DIR = "."
EXCLUDE_DIRS = {'venv', '.git', '__pycache__', 'node_modules', 'site-packages', 
                'bin', 'lib', 'include', 'dist', 'build'}
EXTENSIONS = ('.sh', '.py', '.bash')

# Scripts à ignorer (ce script lui-même + utilitaires)
IGNORED_SCRIPTS = {
    "project_manager.py", "run_all_dependencies.py", "graph_interactif.py",
    "generate_graph.py", "generate_auto_graph.py", "w.py", "h.py", 
    "identify_deps.py", "manage_deps.py", "kl.py"
}

# Modules Python standard à ignorer
STANDARD_LIBS = {
    'os', 'sys', 're', 'json', 'logging', 'unittest', 'pytest', 'subprocess',
    'argparse', 'pathlib', 'collections', 'itertools', 'functools', 'typing',
    'datetime', 'time', 'random', 'math', 'io', 'shutil', 'glob', 'tempfile',
    'threading', 'multiprocessing', 'socket', 'http', 'urllib', 'email',
    'html', 'xml', 'csv', 'hashlib', 'base64', 'pickle', 'copy', 'pprint',
    'traceback', 'warnings', 'contextlib', 'abc', 'dataclasses', 'enum',
    'secrets', 'statistics', 'decimal', 'fractions', 'struct', 'codecs',
    'locale', 'gettext', 'textwrap', 'difflib', 'string', 'operator',
    'inspect', 'dis', 'ast', 'types', 'weakref', 'gc', 'atexit', 'signal',
    'errno', 'ctypes', 'platform', 'configparser', 'zipfile', 'tarfile',
    'gzip', 'bz2', 'lzma', 'sqlite3', 'dbm', 'shelve', 'queue', 'sched',
    'select', 'selectors', 'asyncio', 'concurrent', 'uuid', 'getpass'
}

# Logiciels système à vérifier
REQUIRED_SYSTEM_COMMANDS = ["python3", "pip", "git"]
OPTIONAL_SYSTEM_COMMANDS = ["docker", "docker-compose", "graphviz", "dot"]

# Préfixes de modules locaux à ignorer
LOCAL_MODULE_PREFIXES = ['ids', 'webapp', 'app', 'src', 'tests', 'test']


# =============================================================================
# UTILITAIRES
# =============================================================================

def print_header(title):
    """Affiche un en-tête formaté."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_section(title):
    """Affiche un titre de section."""
    print(f"\n--- {title} ---")


def get_project_files(extensions=('.py',), exclude_scripts=None):
    """Récupère les fichiers du projet en ignorant les dossiers exclus."""
    if exclude_scripts is None:
        exclude_scripts = IGNORED_SCRIPTS
    
    file_list = []
    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
        for f in files:
            if f.endswith(extensions) and f not in exclude_scripts:
                file_list.append(os.path.join(root, f))
    return [os.path.relpath(f, PROJECT_DIR) for f in file_list]


# =============================================================================
# 1. DÉTECTION ET INSTALLATION DES DÉPENDANCES PYTHON
# =============================================================================

def extract_imports_from_file(file_path):
    """Extrait les imports externes d'un fichier Python."""
    external_imports = set()
    pattern = re.compile(r'^\s*(?:from|import)\s+([a-zA-Z0-9_]+)', re.MULTILINE)
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            matches = pattern.findall(content)
            for match in matches:
                if match in sys.builtin_module_names:
                    continue
                if match in STANDARD_LIBS:
                    continue
                if any(match.startswith(prefix) for prefix in LOCAL_MODULE_PREFIXES):
                    continue
                external_imports.add(match)
    except Exception as e:
        print(f"  ⚠ Erreur lecture {file_path}: {e}")
    
    return external_imports


def detect_python_dependencies():
    """Détecte toutes les dépendances Python du projet."""
    print_section("Analyse des imports Python")
    
    all_files = get_project_files(extensions=('.py',))
    all_imports = set()
    
    print(f"  Fichiers analysés: {len(all_files)}")
    
    for file_path in all_files:
        imports = extract_imports_from_file(file_path)
        if imports:
            all_imports.update(imports)
    
    return sorted(list(all_imports))


def generate_requirements(dependencies, output_file="requirements.txt"):
    """Génère le fichier requirements.txt."""
    print_section(f"Génération de {output_file}")
    
    if not dependencies:
        print("  Aucune dépendance externe détectée.")
        return False
    
    with open(output_file, 'w') as f:
        for dep in dependencies:
            f.write(f"{dep}\n")
    
    print(f"  ✅ {len(dependencies)} dépendances écrites dans {output_file}")
    for dep in dependencies:
        print(f"     - {dep}")
    
    return True


def install_requirements(requirements_file="requirements.txt"):
    """Installe les dépendances depuis requirements.txt."""
    print_section("Installation des dépendances Python")
    
    if not os.path.exists(requirements_file):
        print(f"  ⚠ Fichier {requirements_file} non trouvé.")
        return False
    
    in_venv = os.environ.get('VIRTUAL_ENV') is not None
    if not in_venv:
        print("  ⚠ Environnement virtuel non actif.")
        print("  Activez-le avec: source venv/bin/activate")
        response = input("  Continuer l'installation globale ? (o/N): ")
        if response.lower() != 'o':
            return False
    
    try:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', requirements_file],
            check=True
        )
        print("  ✅ Dépendances installées avec succès.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Erreur lors de l'installation: {e}")
        return False


def manage_python_deps(install=False):
    """Gestion complète des dépendances Python."""
    print_header("GESTION DES DÉPENDANCES PYTHON")
    
    deps = detect_python_dependencies()
    
    if generate_requirements(deps):
        if install:
            install_requirements()
    
    return deps


# =============================================================================
# 2. VÉRIFICATION DES LOGICIELS SYSTÈME
# =============================================================================

def check_command_exists(command):
    """Vérifie si une commande système existe."""
    return shutil.which(command) is not None


def check_system_dependencies():
    """Vérifie les dépendances système (docker, git, etc.)."""
    print_header("VÉRIFICATION DES LOGICIELS SYSTÈME")
    
    all_ok = True
    
    print_section("Logiciels requis")
    for cmd in REQUIRED_SYSTEM_COMMANDS:
        if check_command_exists(cmd):
            version = get_command_version(cmd)
            print(f"  ✅ {cmd}: {version}")
        else:
            print(f"  ❌ {cmd}: NON INSTALLÉ")
            all_ok = False
    
    print_section("Logiciels optionnels")
    for cmd in OPTIONAL_SYSTEM_COMMANDS:
        if check_command_exists(cmd):
            version = get_command_version(cmd)
            print(f"  ✅ {cmd}: {version}")
        else:
            print(f"  ⚠ {cmd}: non installé (optionnel)")
    
    print_section("Environnement Python")
    venv = os.environ.get('VIRTUAL_ENV')
    if venv:
        print(f"  ✅ venv actif: {venv}")
    else:
        print("  ⚠ Aucun environnement virtuel actif")
    
    print(f"  Python: {sys.version}")
    
    return all_ok


def get_command_version(command):
    """Essaie d'obtenir la version d'une commande."""
    version_flags = ['--version', '-V', '-v', 'version']
    
    for flag in version_flags:
        try:
            result = subprocess.run(
                [command, flag],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout.strip() or result.stderr.strip()
            if output:
                return output.split('\n')[0][:50]
        except:
            continue
    
    return "installé"


# =============================================================================
# 3. EXÉCUTION HIÉRARCHIQUE DES SCRIPTS
# =============================================================================

def find_script_dependencies(file_path, all_scripts_basenames):
    """Trouve les dépendances d'un script vers d'autres scripts."""
    deps = set()
    pattern = re.compile(r'([\w\d_-]+\.(?:sh|py|bash))')
    
    try:
        with open(os.path.join(PROJECT_DIR, file_path), 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                matches = pattern.findall(line)
                for m in matches:
                    if m in all_scripts_basenames and m != os.path.basename(file_path):
                        deps.add(m)
    except:
        pass
    
    return list(deps)


def execute_script(script_path):
    """Exécute un script et capture le résultat."""
    print(f"\n  🚀 Exécution de {script_path}")
    
    env = os.environ.copy()
    project_root_abs = os.path.abspath(PROJECT_DIR)
    env['PYTHONPATH'] = project_root_abs + ":" + env.get('PYTHONPATH', '')
    
    try:
        if script_path.endswith('.sh') or script_path.endswith('.bash'):
            command = ['bash', script_path]
        elif script_path.endswith('.py'):
            command = [sys.executable, script_path]
        else:
            print(f"     ❌ Format non supporté: {script_path}")
            return False
        
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            env=env
        )
        print(f"     ✅ SUCCESS")
        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')[-5:]
            for line in lines:
                print(f"        {line}")
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"     ❌ ÉCHEC (code {e.returncode})")
        if e.stderr:
            for line in e.stderr.strip().split('\n')[-5:]:
                print(f"        {line}")
        return False
    except FileNotFoundError:
        print(f"     ❌ Fichier non trouvé")
        return False


def build_dependency_graph():
    """Construit le graphe de dépendances et retourne les données."""
    all_scripts_paths = get_project_files(extensions=EXTENSIONS)
    all_scripts_basenames = {os.path.basename(f): f for f in all_scripts_paths}
    
    nodes = []
    edges = []
    
    for script_path in all_scripts_paths:
        script_name = os.path.basename(script_path)
        script_dir = os.path.dirname(script_path) or "racine"
        
        # Déterminer le type de fichier
        if script_name.endswith('.py'):
            file_type = 'python'
        elif script_name.endswith('.sh') or script_name.endswith('.bash'):
            file_type = 'bash'
        else:
            file_type = 'other'
        
        # Compter les lignes
        try:
            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                line_count = len(f.readlines())
        except:
            line_count = 0
        
        nodes.append({
            'id': script_name,
            'path': script_path,
            'dir': script_dir,
            'type': file_type,
            'lines': line_count
        })
        
        deps = find_script_dependencies(script_path, all_scripts_basenames.keys())
        for dep in deps:
            edges.append({
                'source': script_name,
                'target': dep
            })
    
    return nodes, edges, all_scripts_basenames


def run_scripts_hierarchically(dry_run=False):
    """Exécute les scripts dans l'ordre topologique des dépendances."""
    print_header("EXÉCUTION HIÉRARCHIQUE DES SCRIPTS")
    
    try:
        import networkx as nx
    except ImportError:
        print("  ❌ networkx non installé. Installez-le avec: pip install networkx")
        return False
    
    print_section("Analyse des dépendances entre scripts")
    
    nodes, edges, all_scripts_basenames = build_dependency_graph()
    
    print(f"  Scripts trouvés: {len(nodes)}")
    
    G = nx.DiGraph()
    for node in nodes:
        G.add_node(node['id'])
    for edge in edges:
        G.add_edge(edge['source'], edge['target'])
        print(f"     {edge['source']} → {edge['target']}")
    
    try:
        execution_order = list(nx.topological_sort(G))
    except nx.NetworkXUnfeasible:
        print("  ❌ Dépendance circulaire détectée!")
        return False
    
    execution_order = list(reversed(execution_order))
    execution_paths = [all_scripts_basenames[name] for name in execution_order if name in all_scripts_basenames]
    
    print_section(f"Ordre d'exécution ({len(execution_paths)} scripts)")
    for i, script in enumerate(execution_order, 1):
        print(f"  {i}. {script}")
    
    if dry_run:
        print("\n  [Mode dry-run: aucune exécution]")
        return True
    
    print_section("Exécution")
    for script_path in execution_paths:
        if not execute_script(script_path):
            print(f"\n  ❌ Processus arrêté suite à l'échec de {script_path}")
            return False
    
    print("\n  ✅ Toutes les exécutions terminées avec succès!")
    return True


# =============================================================================
# 4. GÉNÉRATION DU GRAPHE HTML INTERACTIF
# =============================================================================

def generate_interactive_graph(output_file="dependency_graph.html"):
    """Génère un graphe HTML interactif des dépendances."""
    print_header("GÉNÉRATION DU GRAPHE INTERACTIF")
    
    nodes, edges, _ = build_dependency_graph()
    
    print(f"  Nodes: {len(nodes)}, Edges: {len(edges)}")
    
    # Calculer les positions avec un layout simple ou utiliser networkx si disponible
    positions = calculate_positions(nodes, edges)
    
    # Préparer les données pour le graphe
    nodes_data = []
    for i, node in enumerate(nodes):
        pos = positions.get(node['id'], {'x': 100 + (i % 5) * 200, 'y': 100 + (i // 5) * 150})
        nodes_data.append({
            **node,
            'x': pos['x'],
            'y': pos['y']
        })
    
    # Générer le HTML
    html_content = generate_html_template(nodes_data, edges)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"  ✅ Graphe généré: {output_file}")
    print(f"  Ouvrez le fichier dans votre navigateur pour visualiser les dépendances.")
    
    return output_file


def calculate_positions(nodes, edges):
    """Calcule les positions des nœuds pour le graphe."""
    positions = {}
    
    try:
        import networkx as nx
        
        G = nx.DiGraph()
        for node in nodes:
            G.add_node(node['id'])
        for edge in edges:
            G.add_edge(edge['source'], edge['target'])
        
        # Utiliser un layout hiérarchique si possible
        try:
            # Essayer le layout multipartite basé sur les niveaux topologiques
            for layer, nodes_in_layer in enumerate(nx.topological_generations(G)):
                for node in nodes_in_layer:
                    G.nodes[node]['layer'] = layer
            pos = nx.multipartite_layout(G, subset_key='layer', scale=400)
        except:
            # Fallback sur spring layout
            pos = nx.spring_layout(G, k=3, iterations=50, scale=400)
        
        for node_id, (x, y) in pos.items():
            positions[node_id] = {
                'x': float(x) + 500,
                'y': float(y) + 400
            }
    except ImportError:
        # Layout simple sans networkx
        for i, node in enumerate(nodes):
            positions[node['id']] = {
                'x': 150 + (i % 6) * 180,
                'y': 100 + (i // 6) * 140
            }
    
    return positions


def generate_html_template(nodes, edges):
    """Génère le template HTML complet avec JavaScript interactif."""
    
    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
    node_count = len(nodes)
    
    html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Graphe des Dépendances - Project Manager</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #e0e0e0;
        }}
        
        .header {{
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            text-align: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .header h1 {{
            font-size: 1.8em;
            color: #00d4ff;
            margin-bottom: 10px;
        }}
        
        .header .stats {{
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
        }}
        
        .stat {{
            background: rgba(255, 255, 255, 0.1);
            padding: 8px 20px;
            border-radius: 20px;
            font-size: 0.9em;
        }}
        
        .stat span {{
            color: #00d4ff;
            font-weight: bold;
        }}
        
        .container {{
            display: flex;
            height: calc(100vh - 100px);
        }}
        
        .sidebar {{
            width: 320px;
            background: rgba(0, 0, 0, 0.4);
            padding: 20px;
            overflow-y: auto;
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .sidebar h2 {{
            color: #00d4ff;
            font-size: 1.1em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        }}
        
        .legend {{
            margin-bottom: 25px;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 8px 0;
            font-size: 0.85em;
        }}
        
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 10px;
            border: 2px solid rgba(255, 255, 255, 0.3);
        }}
        
        .legend-color.python {{ background: #3776ab; }}
        .legend-color.bash {{ background: #4eaa25; }}
        .legend-color.other {{ background: #ff6b6b; }}
        
        .controls {{
            margin-bottom: 25px;
        }}
        
        .control-group {{
            margin-bottom: 15px;
        }}
        
        .control-group label {{
            display: block;
            margin-bottom: 5px;
            font-size: 0.85em;
            color: #aaa;
        }}
        
        .control-group input[type="text"] {{
            width: 100%;
            padding: 8px 12px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 5px;
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 0.9em;
        }}
        
        .control-group input[type="text"]:focus {{
            outline: none;
            border-color: #00d4ff;
        }}
        
        .btn {{
            padding: 8px 16px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.85em;
            margin-right: 8px;
            margin-bottom: 8px;
            transition: all 0.2s;
        }}
        
        .btn-primary {{
            background: #00d4ff;
            color: #000;
        }}
        
        .btn-secondary {{
            background: rgba(255, 255, 255, 0.2);
            color: #fff;
        }}
        
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 212, 255, 0.3);
        }}
        
        .node-list {{
            max-height: 300px;
            overflow-y: auto;
        }}
        
        .node-item {{
            padding: 10px;
            margin: 5px 0;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.2s;
            border-left: 3px solid transparent;
        }}
        
        .node-item:hover {{
            background: rgba(255, 255, 255, 0.1);
        }}
        
        .node-item.python {{ border-left-color: #3776ab; }}
        .node-item.bash {{ border-left-color: #4eaa25; }}
        .node-item.other {{ border-left-color: #ff6b6b; }}
        
        .node-item .name {{
            font-weight: bold;
            font-size: 0.9em;
        }}
        
        .node-item .path {{
            font-size: 0.75em;
            color: #888;
            margin-top: 3px;
        }}
        
        .graph-container {{
            flex: 1;
            position: relative;
            overflow: hidden;
        }}
        
        #graph {{
            width: 100%;
            height: 100%;
        }}
        
        .tooltip {{
            position: absolute;
            background: rgba(0, 0, 0, 0.9);
            border: 1px solid #00d4ff;
            border-radius: 8px;
            padding: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
            z-index: 1000;
            max-width: 300px;
        }}
        
        .tooltip.visible {{
            opacity: 1;
        }}
        
        .tooltip h3 {{
            color: #00d4ff;
            margin-bottom: 8px;
            font-size: 1em;
        }}
        
        .tooltip p {{
            margin: 4px 0;
            font-size: 0.85em;
        }}
        
        .tooltip .label {{
            color: #888;
        }}
        
        .info-panel {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.7);
            padding: 15px;
            border-radius: 8px;
            font-size: 0.8em;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .info-panel p {{
            margin: 5px 0;
        }}
        
        .info-panel kbd {{
            background: rgba(255, 255, 255, 0.2);
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔗 Graphe des Dépendances</h1>
        <div class="stats">
            <div class="stat">Scripts: <span id="node-count">0</span></div>
            <div class="stat">Dépendances: <span id="edge-count">0</span></div>
            <div class="stat">Généré: <span>{timestamp}</span></div>
        </div>
    </div>
    
    <div class="container">
        <div class="sidebar">
            <div class="legend">
                <h2>📊 Légende</h2>
                <div class="legend-item">
                    <div class="legend-color python"></div>
                    <span>Python (.py)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color bash"></div>
                    <span>Bash (.sh, .bash)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color other"></div>
                    <span>Autre</span>
                </div>
            </div>
            
            <div class="controls">
                <h2>🎛️ Contrôles</h2>
                <div class="control-group">
                    <label>Rechercher un script:</label>
                    <input type="text" id="search" placeholder="Nom du fichier...">
                </div>
                <div class="control-group">
                    <button class="btn btn-primary" onclick="resetView()">🔄 Reset Vue</button>
                    <button class="btn btn-secondary" onclick="togglePhysics()">⚡ Physics</button>
                </div>
                <div class="control-group">
                    <button class="btn btn-secondary" onclick="filterByType('python')">Python</button>
                    <button class="btn btn-secondary" onclick="filterByType('bash')">Bash</button>
                    <button class="btn btn-secondary" onclick="filterByType('all')">Tous</button>
                </div>
            </div>
            
            <div class="node-list-container">
                <h2>📁 Scripts ({node_count})</h2>
                <div class="node-list" id="node-list"></div>
            </div>
        </div>
        
        <div class="graph-container">
            <canvas id="graph"></canvas>
            <div class="tooltip" id="tooltip"></div>
            <div class="info-panel">
                <p><kbd>Clic</kbd> Sélectionner un nœud</p>
                <p><kbd>Glisser</kbd> Déplacer un nœud</p>
                <p><kbd>Molette</kbd> Zoomer</p>
                <p><kbd>Clic + Glisser</kbd> sur fond: Déplacer la vue</p>
            </div>
        </div>
    </div>
    
    <script>
        // Données du graphe
        const nodesData = {nodes_json};
        const edgesData = {edges_json};
        
        // Configuration
        const config = {{
            nodeRadius: 25,
            colors: {{
                python: '#3776ab',
                bash: '#4eaa25',
                other: '#ff6b6b',
                edge: 'rgba(255, 255, 255, 0.3)',
                edgeHighlight: '#00d4ff',
                text: '#ffffff',
                background: '#1a1a2e'
            }},
            physics: true
        }};
        
        // État
        let nodes = [];
        let edges = [];
        let selectedNode = null;
        let hoveredNode = null;
        let draggedNode = null;
        let offset = {{ x: 0, y: 0 }};
        let scale = 1;
        let panStart = null;
        let viewOffset = {{ x: 0, y: 0 }};
        
        // Canvas setup
        const canvas = document.getElementById('graph');
        const ctx = canvas.getContext('2d');
        const tooltip = document.getElementById('tooltip');
        
        function initGraph() {{
            // Initialiser les nœuds
            nodes = nodesData.map(n => ({{
                ...n,
                vx: 0,
                vy: 0,
                visible: true
            }}));
            
            // Initialiser les arêtes
            edges = edgesData.map(e => ({{
                source: nodes.find(n => n.id === e.source),
                target: nodes.find(n => n.id === e.target)
            }})).filter(e => e.source && e.target);
            
            // Mettre à jour les stats
            document.getElementById('node-count').textContent = nodes.length;
            document.getElementById('edge-count').textContent = edges.length;
            
            // Remplir la liste des nœuds
            const nodeList = document.getElementById('node-list');
            nodeList.innerHTML = nodes.map(n => `
                <div class="node-item ${{n.type}}" onclick="focusNode('${{n.id}}')">
                    <div class="name">${{n.id}}</div>
                    <div class="path">${{n.path}} (${{n.lines}} lignes)</div>
                </div>
            `).join('');
            
            resizeCanvas();
            animate();
        }}
        
        function resizeCanvas() {{
            const container = canvas.parentElement;
            canvas.width = container.clientWidth;
            canvas.height = container.clientHeight;
        }}
        
        function getNodeColor(type) {{
            return config.colors[type] || config.colors.other;
        }}
        
        function drawArrow(fromX, fromY, toX, toY, color) {{
            const headLength = 12;
            const dx = toX - fromX;
            const dy = toY - fromY;
            const angle = Math.atan2(dy, dx);
            
            // Ajuster pour s'arrêter au bord du nœud
            const dist = Math.sqrt(dx * dx + dy * dy);
            const nodeRadius = config.nodeRadius * scale;
            const ratio = (dist - nodeRadius) / dist;
            const endX = fromX + dx * ratio;
            const endY = fromY + dy * ratio;
            
            ctx.beginPath();
            ctx.moveTo(fromX, fromY);
            ctx.lineTo(endX, endY);
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // Flèche
            ctx.beginPath();
            ctx.moveTo(endX, endY);
            ctx.lineTo(
                endX - headLength * Math.cos(angle - Math.PI / 6),
                endY - headLength * Math.sin(angle - Math.PI / 6)
            );
            ctx.lineTo(
                endX - headLength * Math.cos(angle + Math.PI / 6),
                endY - headLength * Math.sin(angle + Math.PI / 6)
            );
            ctx.closePath();
            ctx.fillStyle = color;
            ctx.fill();
        }}
        
        function draw() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            ctx.save();
            ctx.translate(viewOffset.x, viewOffset.y);
            ctx.scale(scale, scale);
            
            // Dessiner les arêtes
            edges.forEach(edge => {{
                if (!edge.source.visible || !edge.target.visible) return;
                
                const isHighlighted = 
                    (selectedNode && (edge.source.id === selectedNode.id || edge.target.id === selectedNode.id)) ||
                    (hoveredNode && (edge.source.id === hoveredNode.id || edge.target.id === hoveredNode.id));
                
                const color = isHighlighted ? config.colors.edgeHighlight : config.colors.edge;
                drawArrow(edge.source.x, edge.source.y, edge.target.x, edge.target.y, color);
            }});
            
            // Dessiner les nœuds
            nodes.forEach(node => {{
                if (!node.visible) return;
                
                const isSelected = selectedNode && selectedNode.id === node.id;
                const isHovered = hoveredNode && hoveredNode.id === node.id;
                const radius = config.nodeRadius;
                
                // Ombre
                if (isSelected || isHovered) {{
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, radius + 8, 0, Math.PI * 2);
                    ctx.fillStyle = 'rgba(0, 212, 255, 0.3)';
                    ctx.fill();
                }}
                
                // Cercle principal
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
                ctx.fillStyle = getNodeColor(node.type);
                ctx.fill();
                
                if (isSelected) {{
                    ctx.strokeStyle = '#00d4ff';
                    ctx.lineWidth = 3;
                    ctx.stroke();
                }}
                
                // Texte
                ctx.fillStyle = config.colors.text;
                ctx.font = 'bold 11px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                
                // Tronquer le nom si trop long
                let displayName = node.id;
                if (displayName.length > 12) {{
                    displayName = displayName.substring(0, 10) + '...';
                }}
                ctx.fillText(displayName, node.x, node.y);
            }});
            
            ctx.restore();
        }}
        
        function applyPhysics() {{
            if (!config.physics) return;
            
            const repulsion = 5000;
            const attraction = 0.01;
            const damping = 0.9;
            
            // Répulsion entre tous les nœuds
            nodes.forEach(node1 => {{
                if (!node1.visible) return;
                nodes.forEach(node2 => {{
                    if (node1 === node2 || !node2.visible) return;
                    
                    const dx = node1.x - node2.x;
                    const dy = node1.y - node2.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    
                    const force = repulsion / (dist * dist);
                    node1.vx += (dx / dist) * force;
                    node1.vy += (dy / dist) * force;
                }});
            }});
            
            // Attraction le long des arêtes
            edges.forEach(edge => {{
                if (!edge.source.visible || !edge.target.visible) return;
                
                const dx = edge.target.x - edge.source.x;
                const dy = edge.target.y - edge.source.y;
                
                edge.source.vx += dx * attraction;
                edge.source.vy += dy * attraction;
                edge.target.vx -= dx * attraction;
                edge.target.vy -= dy * attraction;
            }});
            
            // Centrer
            const centerX = canvas.width / 2 / scale - viewOffset.x / scale;
            const centerY = canvas.height / 2 / scale - viewOffset.y / scale;
            
            nodes.forEach(node => {{
                if (!node.visible || node === draggedNode) return;
                
                node.vx += (centerX - node.x) * 0.001;
                node.vy += (centerY - node.y) * 0.001;
                
                node.vx *= damping;
                node.vy *= damping;
                
                node.x += node.vx;
                node.y += node.vy;
            }});
        }}
        
        function animate() {{
            applyPhysics();
            draw();
            requestAnimationFrame(animate);
        }}
        
        function getNodeAtPosition(x, y) {{
            const transformedX = (x - viewOffset.x) / scale;
            const transformedY = (y - viewOffset.y) / scale;
            
            for (let i = nodes.length - 1; i >= 0; i--) {{
                const node = nodes[i];
                if (!node.visible) continue;
                
                const dx = transformedX - node.x;
                const dy = transformedY - node.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                
                if (dist <= config.nodeRadius) {{
                    return node;
                }}
            }}
            return null;
        }}
        
        function showTooltip(node, x, y) {{
            const deps = edges.filter(e => e.source.id === node.id).map(e => e.target.id);
            const usedBy = edges.filter(e => e.target.id === node.id).map(e => e.source.id);
            
            tooltip.innerHTML = `
                <h3>${{node.id}}</h3>
                <p><span class="label">Chemin:</span> ${{node.path}}</p>
                <p><span class="label">Type:</span> ${{node.type}}</p>
                <p><span class="label">Lignes:</span> ${{node.lines}}</p>
                <p><span class="label">Dépend de:</span> ${{deps.length ? deps.join(', ') : 'aucun'}}</p>
                <p><span class="label">Utilisé par:</span> ${{usedBy.length ? usedBy.join(', ') : 'aucun'}}</p>
            `;
            
            tooltip.style.left = (x + 15) + 'px';
            tooltip.style.top = (y + 15) + 'px';
            tooltip.classList.add('visible');
        }}
        
        function hideTooltip() {{
            tooltip.classList.remove('visible');
        }}
        
        // Event listeners
        canvas.addEventListener('mousedown', (e) => {{
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const node = getNodeAtPosition(x, y);
            
            if (node) {{
                draggedNode = node;
                selectedNode = node;
                offset.x = (x - viewOffset.x) / scale - node.x;
                offset.y = (y - viewOffset.y) / scale - node.y;
            }} else {{
                panStart = {{ x: e.clientX, y: e.clientY }};
            }}
        }});
        
        canvas.addEventListener('mousemove', (e) => {{
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            if (draggedNode) {{
                draggedNode.x = (x - viewOffset.x) / scale - offset.x;
                draggedNode.y = (y - viewOffset.y) / scale - offset.y;
                draggedNode.vx = 0;
                draggedNode.vy = 0;
            }} else if (panStart) {{
                viewOffset.x += e.clientX - panStart.x;
                viewOffset.y += e.clientY - panStart.y;
                panStart = {{ x: e.clientX, y: e.clientY }};
            }} else {{
                const node = getNodeAtPosition(x, y);
                hoveredNode = node;
                
                if (node) {{
                    canvas.style.cursor = 'pointer';
                    showTooltip(node, e.clientX, e.clientY);
                }} else {{
                    canvas.style.cursor = 'default';
                    hideTooltip();
                }}
            }}
        }});
        
        canvas.addEventListener('mouseup', () => {{
            draggedNode = null;
            panStart = null;
        }});
        
        canvas.addEventListener('wheel', (e) => {{
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            scale *= delta;
            scale = Math.max(0.2, Math.min(3, scale));
        }});
        
        // Recherche
        document.getElementById('search').addEventListener('input', (e) => {{
            const query = e.target.value.toLowerCase();
            nodes.forEach(node => {{
                node.visible = node.id.toLowerCase().includes(query) || 
                              node.path.toLowerCase().includes(query);
            }});
        }});
        
        // Fonctions globales
        window.resetView = function() {{
            scale = 1;
            viewOffset = {{ x: 0, y: 0 }};
            nodes.forEach(n => n.visible = true);
            document.getElementById('search').value = '';
        }};
        
        window.togglePhysics = function() {{
            config.physics = !config.physics;
        }};
        
        window.filterByType = function(type) {{
            nodes.forEach(node => {{
                node.visible = type === 'all' || node.type === type;
            }});
        }};
        
        window.focusNode = function(id) {{
            const node = nodes.find(n => n.id === id);
            if (node) {{
                selectedNode = node;
                viewOffset.x = canvas.width / 2 - node.x * scale;
                viewOffset.y = canvas.height / 2 - node.y * scale;
            }}
        }};
        
        // Initialisation
        window.addEventListener('resize', resizeCanvas);
        initGraph();
    </script>
</body>
</html>
'''
    
    return html


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Gestionnaire de projet unifié",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  python project_manager.py --all              # Tout faire
  python project_manager.py --deps             # Détecter les dépendances Python
  python project_manager.py --deps --install   # Détecter et installer
  python project_manager.py --check            # Vérifier les logiciels système
  python project_manager.py --run              # Exécuter les scripts
  python project_manager.py --run --dry        # Voir l'ordre sans exécuter
  python project_manager.py --graph            # Générer le graphe HTML interactif
        """
    )
    
    parser.add_argument('--all', action='store_true',
                        help='Exécuter toutes les vérifications et actions')
    parser.add_argument('--deps', action='store_true',
                        help='Détecter les dépendances Python et générer requirements.txt')
    parser.add_argument('--install', action='store_true',
                        help='Installer les dépendances (avec --deps)')
    parser.add_argument('--check', action='store_true',
                        help='Vérifier les logiciels système')
    parser.add_argument('--run', action='store_true',
                        help='Exécuter les scripts dans l\'ordre hiérarchique')
    parser.add_argument('--dry', action='store_true',
                        help='Mode simulation (avec --run)')
    parser.add_argument('--graph', action='store_true',
                        help='Générer un graphe HTML interactif des dépendances')
    parser.add_argument('-o', '--output', default='dependency_graph.html',
                        help='Nom du fichier HTML de sortie (défaut: dependency_graph.html)')
    
    args = parser.parse_args()
    
    # Si aucun argument, afficher l'aide
    if not any([args.all, args.deps, args.check, args.run, args.graph]):
        parser.print_help()
        return
    
    print_header("PROJECT MANAGER")
    print(f"  Répertoire: {os.path.abspath(PROJECT_DIR)}")
    
    success = True
    
    if args.all or args.check:
        if not check_system_dependencies():
            success = False
    
    if args.all or args.deps:
        manage_python_deps(install=args.install or args.all)
    
    if args.all or args.graph:
        generate_interactive_graph(args.output)
    
    if args.all or args.run:
        if not run_scripts_hierarchically(dry_run=args.dry):
            success = False
    
    print_header("TERMINÉ")
    if success:
        print("  ✅ Toutes les opérations ont réussi")
    else:
        print("  ⚠ Certaines opérations ont échoué")
        sys.exit(1)


if __name__ == "__main__":
    main()
