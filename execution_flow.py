#!/usr/bin/env python3
"""
=============================================================================
INTELLIGENT EXECUTION FLOW ANALYZER v3.0
=============================================================================
Analyse IA pour déterminer:
- Quels scripts sont des points d'entrée (à lancer en premier)
- L'ordre d'exécution logique
- Les dépendances d'appel entre scripts
- Génère un graphe hiérarchique organisé par niveaux d'exécution
=============================================================================
"""

import os
import re
import json
import hashlib
import time
import sys
import gc
import threading
import webbrowser
import psutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, Tuple
from pathlib import Path
from collections import defaultdict

# =============================================================================
# DÉPENDANCES
# =============================================================================

try:
    import networkx as nx
    from anthropic import Anthropic
    from pyvis.network import Network
except ImportError as e:
    print(f"❌ pip install networkx anthropic pyvis psutil")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass 
class Config:
    api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", "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"
))
    model: str = "claude-sonnet-4-20250514"
    root_dir: str = "/home/tor/Downloads/ids2"
    cache_file: str = "execution_flow_cache.json"
    output_html: str = "execution_flow.html"
    
    max_workers: int = 3
    chunk_size: int = 8
    gc_every_n_chunks: int = 2
    
    max_cpu_percent: float = 85.0
    max_ram_percent: float = 90.0
    check_interval: float = 1.0
    
    extensions: tuple = ('.py', '.sh', '.yml', '.yaml', '.service', '.bash')
    special_files: tuple = ('Dockerfile', 'Makefile', 'docker-compose.yml')
    exclude_dirs: Set[str] = field(default_factory=lambda: {
        'venv', '.venv', '.git', '__pycache__', 'node_modules',
        'site-packages', '.a', 'dist', 'build', '.tox', '.pytest_cache',
        '.mypy_cache', 'eggs', '.egg-info', 'lib', 'lib64'
    })
    
    auto_open: bool = True

# =============================================================================
# COULEURS
# =============================================================================

class C:
    H = '\033[95m'; B = '\033[94m'; C = '\033[96m'; G = '\033[92m'
    Y = '\033[93m'; R = '\033[91m'; E = '\033[0m'; BOLD = '\033[1m'; DIM = '\033[2m'

# =============================================================================
# LOGGER
# =============================================================================

class Log:
    _lock = threading.Lock()
    _start = time.time()
    
    @classmethod
    def _p(cls, icon, color, msg, indent=0):
        with cls._lock:
            t = datetime.now().strftime("%H:%M:%S")
            e = f"{time.time()-cls._start:.1f}s"
            print(f"{C.DIM}[{t}|{e:>6}]{C.E} {'  '*indent}{color}{icon}{C.E} {msg}")
    
    @classmethod
    def header(cls, msg):
        with cls._lock:
            print(f"\n{C.BOLD}{C.H}{'═'*65}{C.E}")
            print(f"{C.BOLD}{C.H}  {msg}{C.E}")
            print(f"{C.BOLD}{C.H}{'═'*65}{C.E}\n")
    
    @classmethod
    def info(cls, msg, i=0): cls._p("ℹ️ ", C.B, msg, i)
    @classmethod
    def ok(cls, msg, i=0): cls._p("✅", C.G, msg, i)
    @classmethod
    def warn(cls, msg, i=0): cls._p("⚠️ ", C.Y, msg, i)
    @classmethod
    def err(cls, msg, i=0): cls._p("❌", C.R, msg, i)
    @classmethod
    def ai(cls, msg, i=0): cls._p("🧠", C.C, msg, i)
    @classmethod
    def cache(cls, msg, i=0): cls._p("💾", C.DIM, msg, i)
    @classmethod
    def gc(cls, msg, i=0): cls._p("🗑️ ", C.DIM, msg, i)
    @classmethod
    def flow(cls, msg, i=0): cls._p("🔄", C.H, msg, i)
    
    @classmethod
    def monitor(cls, cpu, ram, active, total, phase):
        cpu_c = C.R if cpu > 80 else C.Y if cpu > 60 else C.G
        ram_c = C.R if ram > 85 else C.Y if ram > 70 else C.G
        bar = lambda p: '█' * int(p/10) + '░' * (10-int(p/10))
        with cls._lock:
            print(f"\r{C.DIM}[MON]{C.E} CPU:{cpu_c}{bar(cpu)}{cpu:5.1f}%{C.E} "
                  f"RAM:{ram_c}{bar(ram)}{ram:5.1f}%{C.E} "
                  f"[{C.B}{active}/{total}{C.E}] {C.C}{phase}{C.E}   ", end='', flush=True)

# =============================================================================
# RESOURCE MONITOR
# =============================================================================

class ResourceMonitor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._stop = threading.Event()
        self._throttle = threading.Event()
        self._stats = {'active': 0, 'total': 0, 'phase': 'init'}
        self._lock = threading.Lock()
    
    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
    
    def stop(self):
        self._stop.set()
        print()
    
    def update(self, active=None, total=None, phase=None):
        with self._lock:
            if active is not None: self._stats['active'] = active
            if total is not None: self._stats['total'] = total
            if phase is not None: self._stats['phase'] = phase
    
    def wait_if_needed(self):
        while self._throttle.is_set() and not self._stop.is_set():
            time.sleep(0.2)
    
    def _loop(self):
        while not self._stop.is_set():
            cpu = psutil.cpu_percent(interval=0.3)
            ram = psutil.virtual_memory().percent
            
            with self._lock:
                s = self._stats.copy()
            
            Log.monitor(cpu, ram, s['active'], s['total'], s['phase'])
            
            need_throttle = cpu > self.cfg.max_cpu_percent or ram > self.cfg.max_ram_percent
            if need_throttle and not self._throttle.is_set():
                print()
                Log.warn(f"Throttling ON")
                self._throttle.set()
                gc.collect()
            elif not need_throttle and self._throttle.is_set():
                print()
                Log.info(f"Throttling OFF")
                self._throttle.clear()
            
            time.sleep(self.cfg.check_interval)

# =============================================================================
# EXECUTION FLOW ANALYZER
# =============================================================================

class ExecutionFlowAnalyzer:
    def __init__(self, cfg: Config = None):
        self.cfg = cfg or Config()
        self.client = Anthropic(api_key=self.cfg.api_key)
        self.G = nx.DiGraph()
        self.cache = self._load_cache()
        self._lock = threading.Lock()
        
        # Métadonnées des fichiers
        self.file_meta: Dict[str, dict] = {}
        
        self.stats = {'total': 0, 'analyzed': 0, 'cached': 0, 'errors': 0}
        self.monitor = ResourceMonitor(self.cfg)
    
    def _load_cache(self) -> dict:
        p = Path(self.cfg.root_dir) / self.cfg.cache_file
        if p.exists():
            try:
                data = json.loads(p.read_text())
                Log.cache(f"Cache chargé: {len(data)} entrées")
                return data
            except: pass
        return {}
    
    def _save_cache(self):
        p = Path(self.cfg.root_dir) / self.cfg.cache_file
        try:
            p.write_text(json.dumps(self.cache, indent=2))
            Log.cache(f"Cache sauvé: {len(self.cache)} entrées")
        except Exception as e:
            Log.err(f"Erreur cache: {e}")
    
    def _hash(self, content: str) -> str:
        return hashlib.md5(content.encode()).hexdigest()
    
    def _scan(self) -> List[Path]:
        files = []
        root = Path(self.cfg.root_dir)
        
        for p in root.rglob('*'):
            if p.is_file():
                if any(ex in p.parts for ex in self.cfg.exclude_dirs):
                    continue
                if p.suffix in self.cfg.extensions or p.name in self.cfg.special_files:
                    files.append(p)
        
        return files
    
    def _analyze_file(self, filepath: Path) -> Optional[dict]:
        """Analyse un fichier pour déterminer son rôle et ses dépendances d'exécution."""
        name = filepath.name
        rel_path = filepath.relative_to(self.cfg.root_dir)
        
        try:
            content = filepath.read_text(errors='ignore')
        except Exception as e:
            Log.err(f"Lecture: {name} - {e}", 1)
            self.stats['errors'] += 1
            return None
        
        h = self._hash(content)
        
        # Cache hit?
        if name in self.cache and self.cache[name].get('hash') == h:
            Log.cache(f"Hit: {name}", 1)
            self.stats['cached'] += 1
            return self.cache[name]['data']
        
        self.monitor.wait_if_needed()
        
        Log.ai(f"Analyse: {name}", 1)
        
        prompt = f"""Analyze this file ({name}) from path "{rel_path}" and determine its EXECUTION role and dependencies.

Return ONLY valid JSON with this structure:
{{
    "role": "entry_point|library|config|test|utility|service|unknown",
    "description": "Brief description of what this file does",
    "execution_order": 1-100,
    "is_executable": true/false,
    "calls": [
        {{"file": "script.py", "method": "subprocess|import|source|exec", "when": "startup|runtime|conditional"}}
    ],
    "called_by": ["likely parent scripts that would call this"],
    "requires_before": ["files that MUST run before this one"],
    "category": "setup|core|test|deploy|monitor|util|config"
}}

RULES:
- "entry_point": Script meant to be run directly by user (main.py, run.sh, start_*, install_*)
- "library": Module imported by others, not run directly
- "config": Configuration file (yml, yaml, .env)
- "test": Test files
- "utility": Helper scripts
- "service": Background service/daemon
- execution_order: 1=first to run (setup), 100=last (cleanup)
- Only include LOCAL project files in calls/called_by
- Ignore stdlib and external packages

FILE CONTENT:
```
{content[:5000]}
```"""
        
        try:
            resp = self.client.messages.create(
                model=self.cfg.model,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw = resp.content[0].text
            match = re.search(r'\{[\s\S]*\}', raw)
            data = json.loads(match.group(0)) if match else {}
            
            # Valeurs par défaut
            data.setdefault('role', 'unknown')
            data.setdefault('description', '')
            data.setdefault('execution_order', 50)
            data.setdefault('is_executable', False)
            data.setdefault('calls', [])
            data.setdefault('called_by', [])
            data.setdefault('requires_before', [])
            data.setdefault('category', 'util')
            
            # Nettoyer calls
            clean_calls = []
            for c in data.get('calls', []):
                if isinstance(c, dict) and 'file' in c:
                    clean_calls.append({
                        'file': c['file'],
                        'method': c.get('method', 'unknown'),
                        'when': c.get('when', 'runtime')
                    })
            data['calls'] = clean_calls
            
            self.cache[name] = {'hash': h, 'data': data}
            self.stats['analyzed'] += 1
            
            role_icon = {'entry_point': '🚀', 'library': '📚', 'config': '⚙️', 
                        'test': '🧪', 'utility': '🔧', 'service': '🔄'}.get(data['role'], '📄')
            Log.ok(f"{role_icon} {data['role']} | order:{data['execution_order']} | calls:{len(clean_calls)}", 2)
            
            return data
            
        except Exception as e:
            Log.err(f"API: {name} - {e}", 1)
            self.stats['errors'] += 1
            return None
    
    def _process_file(self, filepath: Path):
        """Traite un fichier et ajoute au graphe."""
        result = self._analyze_file(filepath)
        if not result:
            return
        
        name = filepath.name
        
        with self._lock:
            self.file_meta[name] = result
            self.G.add_node(name)
            
            # Ajouter les edges pour les appels
            for call in result.get('calls', []):
                target = call['file']
                method = call.get('method', 'unknown')
                when = call.get('when', 'runtime')
                self.G.add_edge(name, target, method=method, when=when)
            
            # Ajouter les edges pour requires_before (dépendances inversées)
            for req in result.get('requires_before', []):
                self.G.add_edge(req, name, method='requires', when='before')
    
    def _compute_execution_levels(self) -> Dict[str, int]:
        """Calcule les niveaux d'exécution basés sur le tri topologique."""
        levels = {}
        
        try:
            # Tri topologique pour l'ordre d'exécution
            for level, nodes in enumerate(nx.topological_generations(self.G)):
                for node in nodes:
                    levels[node] = level
        except nx.NetworkXUnfeasible:
            # Cycle détecté, fallback sur execution_order
            Log.warn("Cycle détecté, utilisation de execution_order")
            for node in self.G.nodes():
                meta = self.file_meta.get(node, {})
                levels[node] = meta.get('execution_order', 50) // 10
        
        return levels
    
    def _identify_entry_points(self) -> List[str]:
        """Identifie les points d'entrée (scripts à lancer en premier)."""
        entry_points = []
        
        for node in self.G.nodes():
            meta = self.file_meta.get(node, {})
            
            # Critères pour être un entry point:
            # 1. Marqué comme entry_point par l'IA
            # 2. N'a pas de prédécesseurs (aucun script ne l'appelle)
            # 3. Est exécutable
            
            is_entry = meta.get('role') == 'entry_point'
            no_predecessors = self.G.in_degree(node) == 0
            is_executable = meta.get('is_executable', False)
            
            if is_entry or (no_predecessors and is_executable):
                entry_points.append(node)
        
        # Trier par execution_order
        entry_points.sort(key=lambda n: self.file_meta.get(n, {}).get('execution_order', 50))
        
        return entry_points
    
    def _generate_html(self) -> str:
        """Génère le HTML avec organisation hiérarchique."""
        G = self.G.copy()
        
        # Supprimer orphelins
        orphans = [n for n, d in G.degree() if d == 0]
        G.remove_nodes_from(orphans)
        
        if len(G.nodes()) == 0:
            Log.warn("Graphe vide")
            return ""
        
        # Calculer les niveaux
        levels = self._compute_execution_levels()
        entry_points = self._identify_entry_points()
        
        Log.flow(f"Entry points détectés: {', '.join(entry_points[:5])}")
        
        # Créer le réseau PyVis
        net = Network(
            height="900px", width="100%", directed=True,
            bgcolor="#0d1117", font_color="#c9d1d9",
            select_menu=True, filter_menu=True
        )
        
        # Couleurs par rôle
        role_colors = {
            'entry_point': '#00ff00',  # Vert vif - LANCER EN PREMIER
            'library': '#3572A5',       # Bleu Python
            'config': '#cb171e',        # Rouge
            'test': '#f1c40f',          # Jaune
            'utility': '#9b59b6',       # Violet
            'service': '#e67e22',       # Orange
            'unknown': '#8b949e'        # Gris
        }
        
        # Catégories pour le niveau Y
        category_y = {
            'setup': 0, 'config': 1, 'core': 2, 
            'util': 3, 'test': 4, 'deploy': 5, 'monitor': 6
        }
        
        # Ajouter les nodes
        for node in G.nodes():
            meta = self.file_meta.get(node, {})
            role = meta.get('role', 'unknown')
            desc = meta.get('description', 'No description')
            order = meta.get('execution_order', 50)
            category = meta.get('category', 'util')
            level = levels.get(node, 0)
            
            color = role_colors.get(role, '#8b949e')
            
            # Taille basée sur l'importance (entry points plus gros)
            size = 30 if role == 'entry_point' else 20 if role in ['library', 'service'] else 15
            
            # Position hiérarchique
            x = level * 200
            y = category_y.get(category, 3) * 100
            
            # Label avec ordre
            label = f"[{order}] {node}" if role == 'entry_point' else node
            
            # Tooltip détaillé
            tooltip = f"""
<b>📄 {node}</b><br>
<b>Role:</b> {role}<br>
<b>Category:</b> {category}<br>
<b>Execution Order:</b> {order}<br>
<b>Level:</b> {level}<br>
<hr>
<b>Description:</b><br>{desc}<br>
<hr>
<b>Calls:</b> {len(meta.get('calls', []))} scripts<br>
<b>Called by:</b> {G.in_degree(node)} scripts
            """.strip()
            
            # Bordure spéciale pour entry points
            border_width = 4 if role == 'entry_point' else 2
            
            net.add_node(
                node, 
                label=label,
                title=tooltip,
                color=color,
                size=size,
                x=x, y=y,
                borderWidth=border_width,
                font={'size': 12 if role == 'entry_point' else 10}
            )
        
        # Ajouter les edges avec couleurs selon le type
        method_colors = {
            'subprocess': '#ff6b6b',   # Rouge - exécution
            'exec': '#ff6b6b',
            'source': '#4ecdc4',       # Cyan - source bash
            'import': '#58a6ff',       # Bleu - import python
            'requires': '#f39c12',     # Orange - dépendance
            'unknown': '#8b949e'
        }
        
        for src, tgt, data in G.edges(data=True):
            method = data.get('method', 'unknown')
            when = data.get('when', 'runtime')
            
            color = method_colors.get(method, '#8b949e')
            
            # Style de ligne selon when
            dashes = when == 'conditional'
            
            net.add_edge(
                src, tgt,
                title=f"{src} → {tgt}<br>Method: {method}<br>When: {when}",
                color=color,
                arrows='to',
                dashes=dashes,
                width=2
            )
        
        # Configuration avec layout hiérarchique
        net.set_options('''
        {
            "nodes": {
                "shadow": true,
                "font": {"face": "monospace"}
            },
            "edges": {
                "smooth": {"type": "cubicBezier", "forceDirection": "horizontal"},
                "arrows": {"to": {"scaleFactor": 0.8}}
            },
            "layout": {
                "hierarchical": {
                    "enabled": true,
                    "direction": "LR",
                    "sortMethod": "directed",
                    "levelSeparation": 200,
                    "nodeSpacing": 100
                }
            },
            "physics": {
                "enabled": false
            },
            "interaction": {
                "hover": true,
                "navigationButtons": true,
                "keyboard": true
            }
        }
        ''')
        
        # Sauvegarder
        output_path = Path(self.cfg.root_dir) / self.cfg.output_html
        net.save_graph(str(output_path))
        
        # Ajouter une légende au HTML
        self._inject_legend(output_path, entry_points, levels)
        
        Log.ok(f"HTML généré: {len(G.nodes())} nodes, {len(G.edges())} edges")
        
        return str(output_path)
    
    def _inject_legend(self, html_path: Path, entry_points: List[str], levels: Dict[str, int]):
        """Injecte une légende et les infos d'exécution dans le HTML."""
        
        # Générer l'ordre d'exécution recommandé
        execution_order = []
        for node, level in sorted(levels.items(), key=lambda x: x[1]):
            meta = self.file_meta.get(node, {})
            if meta.get('is_executable', False) or meta.get('role') == 'entry_point':
                execution_order.append({
                    'name': node,
                    'level': level,
                    'order': meta.get('execution_order', 50),
                    'desc': meta.get('description', '')[:50]
                })
        
        legend_html = f'''
<div id="legend" style="
    position: fixed;
    top: 10px;
    left: 10px;
    background: rgba(13,17,23,0.95);
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 15px;
    font-family: monospace;
    font-size: 12px;
    color: #c9d1d9;
    max-width: 350px;
    max-height: 90vh;
    overflow-y: auto;
    z-index: 1000;
">
    <h3 style="color: #58a6ff; margin-top: 0;">🚀 Ordre d'Exécution</h3>
    
    <div style="margin-bottom: 15px;">
        <b style="color: #00ff00;">Points d'entrée (lancer en premier):</b>
        <ol style="margin: 5px 0; padding-left: 20px;">
            {"".join(f'<li style="color: #00ff00;">{ep}</li>' for ep in entry_points[:10])}
        </ol>
    </div>
    
    <hr style="border-color: #30363d;">
    
    <h4 style="color: #58a6ff;">📊 Légende des couleurs</h4>
    <div style="display: grid; grid-template-columns: 20px 1fr; gap: 5px; align-items: center;">
        <span style="background: #00ff00; width: 15px; height: 15px; border-radius: 50%;"></span>
        <span>Entry Point (🚀 lancer)</span>
        
        <span style="background: #3572A5; width: 15px; height: 15px; border-radius: 50%;"></span>
        <span>Library (📚 module)</span>
        
        <span style="background: #cb171e; width: 15px; height: 15px; border-radius: 50%;"></span>
        <span>Config (⚙️ config)</span>
        
        <span style="background: #f1c40f; width: 15px; height: 15px; border-radius: 50%;"></span>
        <span>Test (🧪 test)</span>
        
        <span style="background: #9b59b6; width: 15px; height: 15px; border-radius: 50%;"></span>
        <span>Utility (🔧 utilitaire)</span>
        
        <span style="background: #e67e22; width: 15px; height: 15px; border-radius: 50%;"></span>
        <span>Service (🔄 daemon)</span>
    </div>
    
    <hr style="border-color: #30363d;">
    
    <h4 style="color: #58a6ff;">➡️ Types de liens</h4>
    <div style="font-size: 11px;">
        <span style="color: #ff6b6b;">━━</span> subprocess/exec<br>
        <span style="color: #4ecdc4;">━━</span> source (bash)<br>
        <span style="color: #58a6ff;">━━</span> import (python)<br>
        <span style="color: #f39c12;">━━</span> requires<br>
        <span style="color: #8b949e;">- -</span> conditionnel
    </div>
    
    <hr style="border-color: #30363d;">
    
    <button onclick="document.getElementById('legend').style.display='none'" 
            style="background: #238636; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer;">
        Masquer
    </button>
</div>
'''
        
        # Lire et modifier le HTML
        content = html_path.read_text()
        content = content.replace('</body>', f'{legend_html}</body>')
        html_path.write_text(content)
    
    def run(self):
        """Lance l'analyse complète."""
        start = time.time()
        
        Log.header("🚀 EXECUTION FLOW ANALYZER v3.0")
        
        if not self.cfg.api_key:
            Log.err("Clé API non configurée!")
            Log.info("export ANTHROPIC_API_KEY='sk-ant-...'")
            return
        
        files = self._scan()
        self.stats['total'] = len(files)
        Log.ok(f"Fichiers trouvés: {len(files)}")
        
        if not files:
            return
        
        self.monitor.start()
        self.monitor.update(total=len(files))
        
        chunks = [files[i:i+self.cfg.chunk_size] for i in range(0, len(files), self.cfg.chunk_size)]
        Log.info(f"Traitement en {len(chunks)} chunks")
        
        Log.header("🧠 PHASE 1: Analyse des fichiers")
        
        processed = 0
        try:
            for chunk_idx, chunk in enumerate(chunks):
                self.monitor.update(phase=f"Chunk {chunk_idx+1}/{len(chunks)}")
                
                with ThreadPoolExecutor(max_workers=self.cfg.max_workers) as executor:
                    futures = {executor.submit(self._process_file, f): f for f in chunk}
                    
                    for future in as_completed(futures):
                        processed += 1
                        self.monitor.update(active=processed)
                        try:
                            future.result()
                        except Exception as e:
                            Log.err(f"Worker: {e}")
                
                if (chunk_idx + 1) % self.cfg.gc_every_n_chunks == 0:
                    collected = gc.collect()
                    print()
                    Log.gc(f"GC: {collected} objets")
        
        except KeyboardInterrupt:
            Log.warn("\n⚠️ Interruption...")
        
        finally:
            self.monitor.stop()
            self._save_cache()
            gc.collect()
        
        # Phase 2: Génération du graphe
        Log.header("🔄 PHASE 2: Génération du graphe hiérarchique")
        
        html_path = self._generate_html()
        
        # Afficher l'ordre d'exécution
        entry_points = self._identify_entry_points()
        if entry_points:
            Log.header("🎯 ORDRE D'EXÉCUTION RECOMMANDÉ")
            for i, ep in enumerate(entry_points, 1):
                meta = self.file_meta.get(ep, {})
                desc = meta.get('description', '')[:60]
                print(f"  {C.G}{i}.{C.E} {C.BOLD}{ep}{C.E}")
                if desc:
                    print(f"     {C.DIM}{desc}{C.E}")
        
        # Stats
        duration = time.time() - start
        Log.header("📊 STATISTIQUES")
        print(f"  📁 Total fichiers  : {C.B}{self.stats['total']}{C.E}")
        print(f"  🧠 Analysés        : {C.C}{self.stats['analyzed']}{C.E}")
        print(f"  💾 Depuis cache    : {C.G}{self.stats['cached']}{C.E}")
        print(f"  ❌ Erreurs         : {C.R}{self.stats['errors']}{C.E}")
        print(f"  🚀 Entry points    : {C.G}{len(entry_points)}{C.E}")
        print(f"  🔗 Nodes           : {C.B}{self.G.number_of_nodes()}{C.E}")
        print(f"  ➡️  Edges           : {C.B}{self.G.number_of_edges()}{C.E}")
        print(f"  ⏱️  Durée           : {C.Y}{duration:.1f}s{C.E}")
        print()
        
        if self.cfg.auto_open and html_path:
            Log.ok(f"🌐 Ouverture: {html_path}")
            webbrowser.open(f'file://{html_path}')

# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    
    p = argparse.ArgumentParser(
        description="Analyseur de flux d'exécution IA v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python3 execution_flow.py                # Analyse complète
  python3 execution_flow.py --open         # Ouvrir le HTML existant
  python3 execution_flow.py --clear        # Vider cache et relancer
  python3 execution_flow.py -w 2 -c 5      # Mode léger
        """
    )
    p.add_argument('-d', '--dir', default="/home/tor/Downloads/ids2", help='Répertoire')
    p.add_argument('-w', '--workers', type=int, default=3, help='Workers (défaut: 3)')
    p.add_argument('-c', '--chunk', type=int, default=8, help='Chunk size (défaut: 8)')
    p.add_argument('--cpu', type=float, default=85.0, help='Max CPU %%')
    p.add_argument('--ram', type=float, default=90.0, help='Max RAM %%')
    p.add_argument('-o', '--output', default='execution_flow.html', help='Output HTML')
    p.add_argument('-k', '--key', help='API key')
    p.add_argument('--no-open', action='store_true', help='Ne pas ouvrir navigateur')
    p.add_argument('--open', action='store_true', help='Ouvrir HTML existant')
    p.add_argument('--clear', action='store_true', help='Vider le cache')
    
    args = p.parse_args()
    
    html_path = Path(args.dir) / args.output
    cache_path = Path(args.dir) / "execution_flow_cache.json"
    
    if args.open:
        if html_path.exists():
            print(f"🌐 Ouverture: {html_path}")
            webbrowser.open(f'file://{html_path}')
        else:
            print(f"❌ Fichier non trouvé: {html_path}")
        return
    
    if args.clear and cache_path.exists():
        cache_path.unlink()
        print(f"🗑️ Cache supprimé")
    
    cfg = Config()
    cfg.root_dir = args.dir
    cfg.max_workers = args.workers
    cfg.chunk_size = args.chunk
    cfg.max_cpu_percent = args.cpu
    cfg.max_ram_percent = args.ram
    cfg.output_html = args.output
    cfg.auto_open = not args.no_open
    if args.key:
        cfg.api_key = args.key
    
    analyzer = ExecutionFlowAnalyzer(cfg)
    analyzer.run()

if __name__ == "__main__":
    main()
