#!/usr/bin/env python3
"""
=============================================================================
INTELLIGENT DEPENDENCY ANALYZER v2.1
=============================================================================
- Fix PyVis compatibility (no show_buttons)
- Chunked processing avec garbage collector
- Auto-open HTML dans navigateur
- Monitoring RAM/CPU avec throttling
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
from typing import List, Set, Optional
from pathlib import Path

# =============================================================================
# VÉRIFICATION DES DÉPENDANCES
# =============================================================================

try:
    import networkx as nx
    from anthropic import Anthropic
    from pyvis.network import Network
    import psutil
except ImportError as e:
    print(f"❌ Dépendance manquante: {e}")
    print(f"   pip install networkx anthropic pyvis psutil")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass 
class Config:
    api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", "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"))
    model: str = "claude-sonnet-4-20250514"
    root_dir: str = "/home/tor/Downloads/ids2"
    cache_file: str = "analysis_cache.json"
    output_html: str = "dependency_map_ai.html"
    
    # Threading & Chunking
    max_workers: int = 3
    chunk_size: int = 10
    gc_every_n_chunks: int = 2
    
    # Monitoring
    max_cpu_percent: float = 85.0
    max_ram_percent: float = 90.0
    check_interval: float = 1.0
    
    # Extensions
    extensions: tuple = ('.py', '.sh', '.yml', '.yaml', '.service', '.bash')
    special_files: tuple = ('Dockerfile', 'Makefile', 'docker-compose.yml')
    exclude_dirs: Set[str] = field(default_factory=lambda: {
        'venv', '.venv', '.git', '__pycache__', 'node_modules',
        'site-packages', '.a', 'dist', 'build', '.tox', '.pytest_cache',
        '.mypy_cache', 'eggs', '.egg-info', 'lib', 'lib64'
    })
    
    auto_open: bool = True
    live_update: bool = True

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
            print(f"\n{C.BOLD}{C.H}{'═'*60}{C.E}")
            print(f"{C.BOLD}{C.H}  {msg}{C.E}")
            print(f"{C.BOLD}{C.H}{'═'*60}{C.E}\n")
    
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
    def monitor(cls, cpu, ram, active, total, chunk):
        cpu_c = C.R if cpu > 80 else C.Y if cpu > 60 else C.G
        ram_c = C.R if ram > 85 else C.Y if ram > 70 else C.G
        bar = lambda p: '█' * int(p/10) + '░' * (10-int(p/10))
        with cls._lock:
            print(f"\r{C.DIM}[MON]{C.E} CPU:{cpu_c}{bar(cpu)}{cpu:5.1f}%{C.E} "
                  f"RAM:{ram_c}{bar(ram)}{ram:5.1f}%{C.E} "
                  f"[{C.B}{active}/{total}{C.E}] Chunk:{C.C}{chunk}{C.E}   ", end='', flush=True)

# =============================================================================
# RESOURCE MONITOR
# =============================================================================

class ResourceMonitor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._stop = threading.Event()
        self._throttle = threading.Event()
        self._stats = {'active': 0, 'total': 0, 'chunk': 0}
        self._lock = threading.Lock()
    
    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()
    
    def stop(self):
        self._stop.set()
        print()
    
    def update(self, active=None, total=None, chunk=None):
        with self._lock:
            if active is not None: self._stats['active'] = active
            if total is not None: self._stats['total'] = total
            if chunk is not None: self._stats['chunk'] = chunk
    
    def wait_if_needed(self):
        while self._throttle.is_set() and not self._stop.is_set():
            time.sleep(0.2)
    
    def _loop(self):
        while not self._stop.is_set():
            cpu = psutil.cpu_percent(interval=0.3)
            ram = psutil.virtual_memory().percent
            
            with self._lock:
                s = self._stats.copy()
            
            Log.monitor(cpu, ram, s['active'], s['total'], s['chunk'])
            
            need_throttle = cpu > self.cfg.max_cpu_percent or ram > self.cfg.max_ram_percent
            if need_throttle and not self._throttle.is_set():
                print()
                Log.warn(f"Throttling ON (CPU:{cpu:.0f}% RAM:{ram:.0f}%)")
                self._throttle.set()
                gc.collect()
            elif not need_throttle and self._throttle.is_set():
                print()
                Log.info(f"Throttling OFF")
                self._throttle.clear()
            
            time.sleep(self.cfg.check_interval)

# =============================================================================
# HTML GENERATOR (Fixed PyVis - NO show_buttons)
# =============================================================================

class HTMLGenerator:
    def __init__(self, cfg: Config, graph: nx.DiGraph):
        self.cfg = cfg
        self.G = graph
        self._lock = threading.Lock()
    
    def generate(self, final=False) -> str:
        with self._lock:
            G = self.G.copy()
            
            # Supprimer orphelins
            orphans = [n for n, d in G.degree() if d == 0]
            G.remove_nodes_from(orphans)
            
            if len(G.nodes()) == 0:
                return ""
            
            # PyVis avec select_menu et filter_menu (pas show_buttons!)
            net = Network(
                height="900px", width="100%", directed=True,
                bgcolor="#0d1117", font_color="#c9d1d9",
                select_menu=True,
                filter_menu=True
            )
            
            # Nodes avec couleurs
            for node in G.nodes():
                net.add_node(node, label=node, color=self._color(node), 
                            title=f"📄 {node}", font={'size': 12})
            
            # Edges
            for src, tgt, data in G.edges(data=True):
                label = data.get('label', '')
                net.add_edge(src, tgt, title=f"{src} → {tgt} ({label})", 
                            label=label, arrows='to')
            
            # Config via set_options (PAS show_buttons!)
            net.set_options('''
            {
                "nodes": {
                    "borderWidth": 2,
                    "shadow": true,
                    "font": {"face": "monospace"}
                },
                "edges": {
                    "color": {"color": "#58a6ff", "highlight": "#f78166"},
                    "smooth": {"type": "curvedCW", "roundness": 0.15},
                    "arrows": {"to": {"scaleFactor": 0.8}}
                },
                "physics": {
                    "forceAtlas2Based": {
                        "gravitationalConstant": -80,
                        "centralGravity": 0.01,
                        "springLength": 120,
                        "damping": 0.5
                    },
                    "solver": "forceAtlas2Based",
                    "stabilization": {"iterations": 150}
                },
                "interaction": {
                    "hover": true,
                    "navigationButtons": true,
                    "keyboard": true,
                    "tooltipDelay": 100
                }
            }
            ''')
            
            # Sauvegarder
            output_path = Path(self.cfg.root_dir) / self.cfg.output_html
            net.save_graph(str(output_path))
            
            status = "FINAL" if final else "UPDATE"
            print()
            Log.ok(f"HTML [{status}]: {len(G.nodes())} nodes, {len(G.edges())} edges → {output_path.name}")
            
            return str(output_path)
    
    def _color(self, filename: str) -> str:
        if filename.endswith('.py'): return '#3572A5'
        if filename.endswith(('.sh', '.bash')): return '#89e051'
        if filename.endswith(('.yml', '.yaml')): return '#cb171e'
        if filename.endswith('.service'): return '#ff7043'
        if 'Dockerfile' in filename: return '#2496ed'
        if 'Makefile' in filename: return '#427819'
        return '#8b949e'

# =============================================================================
# MAIN ANALYZER
# =============================================================================

class IntelligentAnalyzer:
    def __init__(self, cfg: Config = None):
        self.cfg = cfg or Config()
        self.client = Anthropic(api_key=self.cfg.api_key)
        self.G = nx.DiGraph()
        self.cache = self._load_cache()
        self._lock = threading.Lock()
        
        self.stats = {'total': 0, 'analyzed': 0, 'cached': 0, 'errors': 0}
        
        self.monitor = ResourceMonitor(self.cfg)
        self.html_gen = HTMLGenerator(self.cfg, self.G)
    
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
        name = filepath.name
        
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
        
        prompt = f"""Analyze this file ({name}) and identify LOCAL project file dependencies.
Return ONLY valid JSON: {{"deps": [{{"file": "name.ext", "type": "import|exec|source|copy"}}]}}

Rules:
- Only local project files, not stdlib or external packages
- Python: local imports, subprocess calls to .py/.sh
- Shell: source, bash, python3 calls
- YAML/Docker: file refs, COPY commands
- No deps? Return {{"deps": []}}

```
{content[:4000]}
```"""
        
        try:
            resp = self.client.messages.create(
                model=self.cfg.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw = resp.content[0].text
            match = re.search(r'\{[\s\S]*"deps"[\s\S]*\}', raw)
            data = json.loads(match.group(0)) if match else {"deps": []}
            
            data['deps'] = [
                {"file": d["file"], "type": d.get("type", "unknown")}
                for d in data.get("deps", []) if isinstance(d, dict) and "file" in d
            ]
            
            self.cache[name] = {'hash': h, 'data': data}
            self.stats['analyzed'] += 1
            
            if data['deps']:
                Log.ok(f"→ {len(data['deps'])} deps: {', '.join(d['file'] for d in data['deps'][:5])}", 2)
            
            return data
            
        except Exception as e:
            Log.err(f"API: {name} - {e}", 1)
            self.stats['errors'] += 1
            return {"deps": []}
    
    def _process_file(self, filepath: Path):
        result = self._analyze_file(filepath)
        if not result:
            return
        
        name = filepath.name
        with self._lock:
            self.G.add_node(name)
            for dep in result.get("deps", []):
                self.G.add_edge(name, dep["file"], label=dep["type"])
    
    def run(self):
        start = time.time()
        
        Log.header("🚀 INTELLIGENT ANALYZER v2.1")
        
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
        Log.info(f"Traitement en {len(chunks)} chunks de {self.cfg.chunk_size} fichiers")
        
        Log.header(f"🧠 ANALYSE ({self.cfg.max_workers} workers)")
        
        processed = 0
        html_path = ""
        
        try:
            for chunk_idx, chunk in enumerate(chunks):
                self.monitor.update(chunk=chunk_idx+1)
                
                with ThreadPoolExecutor(max_workers=self.cfg.max_workers) as executor:
                    futures = {executor.submit(self._process_file, f): f for f in chunk}
                    
                    for future in as_completed(futures):
                        processed += 1
                        self.monitor.update(active=processed)
                        
                        try:
                            future.result()
                        except Exception as e:
                            Log.err(f"Worker: {e}")
                
                # GC
                if (chunk_idx + 1) % self.cfg.gc_every_n_chunks == 0:
                    collected = gc.collect()
                    print()
                    Log.gc(f"GC: {collected} objets libérés")
                
                # Live HTML
                if self.cfg.live_update and (chunk_idx + 1) % 3 == 0:
                    self.html_gen.generate()
        
        except KeyboardInterrupt:
            Log.warn("\n⚠️ Interruption...")
        
        finally:
            self.monitor.stop()
            self._save_cache()
            gc.collect()
        
        # Final HTML
        html_path = self.html_gen.generate(final=True)
        
        # Stats
        duration = time.time() - start
        Log.header("📊 STATISTIQUES")
        print(f"  📁 Total fichiers  : {C.B}{self.stats['total']}{C.E}")
        print(f"  🧠 Analysés Claude : {C.C}{self.stats['analyzed']}{C.E}")
        print(f"  💾 Depuis cache    : {C.G}{self.stats['cached']}{C.E}")
        print(f"  ❌ Erreurs         : {C.R}{self.stats['errors']}{C.E}")
        print(f"  🔗 Nodes           : {C.B}{self.G.number_of_nodes()}{C.E}")
        print(f"  ➡️  Edges           : {C.B}{self.G.number_of_edges()}{C.E}")
        print(f"  ⏱️  Durée           : {C.Y}{duration:.1f}s{C.E}")
        print()
        
        # Auto open browser
        if self.cfg.auto_open and html_path:
            Log.ok(f"🌐 Ouverture navigateur: {html_path}")
            webbrowser.open(f'file://{html_path}')

# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    
    p = argparse.ArgumentParser(description="Analyseur IA de dépendances v2.1")
    p.add_argument('-d', '--dir', default="/home/tor/Downloads/ids2", help='Répertoire')
    p.add_argument('-w', '--workers', type=int, default=3, help='Workers (défaut: 3)')
    p.add_argument('-c', '--chunk', type=int, default=10, help='Chunk size (défaut: 10)')
    p.add_argument('--cpu', type=float, default=85.0, help='Max CPU %%')
    p.add_argument('--ram', type=float, default=90.0, help='Max RAM %%')
    p.add_argument('-o', '--output', default='dependency_map_ai.html', help='Output HTML')
    p.add_argument('-k', '--key', help='API key (ou ANTHROPIC_API_KEY)')
    p.add_argument('--no-open', action='store_true', help='Ne pas ouvrir navigateur')
    p.add_argument('--no-live', action='store_true', help='Pas de MAJ live')
    
    args = p.parse_args()
    
    cfg = Config()
    cfg.root_dir = args.dir
    cfg.max_workers = args.workers
    cfg.chunk_size = args.chunk
    cfg.max_cpu_percent = args.cpu
    cfg.max_ram_percent = args.ram
    cfg.output_html = args.output
    cfg.auto_open = not args.no_open
    cfg.live_update = not args.no_live
    if args.key:
        cfg.api_key = args.key
    
    analyzer = IntelligentAnalyzer(cfg)
    analyzer.run()

if __name__ == "__main__":
    main()
