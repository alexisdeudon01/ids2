#!/usr/bin/env python3
"""
=============================================================================
WORKFLOW ANALYZER & FSM GENERATOR v4.0
=============================================================================
- Analyse IA complète de chaque fichier
- Classification par workflows (1 entry point = 1 workflow)
- Détection des bugs potentiels et problèmes de séquence
- Génération de Final State Machine (FSM)
- Proposition d'un script unifié
- HTML multi-onglets avec visualisation live
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
from typing import List, Set, Dict, Optional, Tuple, Any
from pathlib import Path
from collections import defaultdict
import textwrap

# =============================================================================
# DÉPENDANCES
# =============================================================================

try:
    import networkx as nx
    from anthropic import Anthropic
except ImportError as e:
    print(f"❌ pip install networkx anthropic psutil")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass 
class Config:
    api_key: str = "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"
    model: str = "claude-sonnet-4-20250514"
    root_dir: str = "/home/tor/Downloads/ids2"
    cache_file: str = "workflow_analysis_cache.json"
    output_html: str = "workflow_analysis.html"
    
    max_workers: int = 3
    chunk_size: int = 6
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
# COULEURS TERMINAL
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
            print(f"\n{C.BOLD}{C.H}{'═'*70}{C.E}")
            print(f"{C.BOLD}{C.H}  {msg}{C.E}")
            print(f"{C.BOLD}{C.H}{'═'*70}{C.E}\n")
    
    @classmethod
    def section(cls, msg):
        with cls._lock:
            print(f"\n{C.BOLD}{C.C}── {msg} ──{C.E}\n")
    
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
    def bug(cls, msg, i=0): cls._p("🐛", C.R, msg, i)
    @classmethod
    def fsm(cls, msg, i=0): cls._p("⚙️ ", C.H, msg, i)
    
    @classmethod
    def monitor(cls, cpu, ram, active, total, phase):
        cpu_c = C.R if cpu > 80 else C.Y if cpu > 60 else C.G
        ram_c = C.R if ram > 85 else C.Y if ram > 70 else C.G
        bar = lambda p: '█' * int(p/10) + '░' * (10-int(p/10))
        with cls._lock:
            print(f"\r{C.DIM}[MON]{C.E} CPU:{cpu_c}{bar(cpu)}{cpu:5.1f}%{C.E} "
                  f"RAM:{ram_c}{bar(ram)}{ram:5.1f}%{C.E} "
                  f"[{C.B}{active}/{total}{C.E}] {C.C}{phase[:20]}{C.E}   ", end='', flush=True)

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
# WORKFLOW ANALYZER
# =============================================================================

class WorkflowAnalyzer:
    def __init__(self, cfg: Config = None):
        self.cfg = cfg or Config()
        self.client = Anthropic(api_key=self.cfg.api_key)
        self.G = nx.DiGraph()
        self.cache = self._load_cache()
        self._lock = threading.Lock()
        
        # Données d'analyse
        self.file_meta: Dict[str, dict] = {}
        self.workflows: Dict[str, dict] = {}  # entry_point -> workflow data
        self.orphans: List[str] = []
        self.bugs: List[dict] = []
        self.fsm_states: List[dict] = []
        
        self.stats = {'total': 0, 'analyzed': 0, 'cached': 0, 'errors': 0}
        self.monitor = ResourceMonitor(self.cfg)
    
    # =========================================================================
    # CACHE
    # =========================================================================
    
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
    
    # =========================================================================
    # SCAN
    # =========================================================================
    
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
    
    # =========================================================================
    # ANALYSE IA APPROFONDIE
    # =========================================================================
    
    def _analyze_file(self, filepath: Path) -> Optional[dict]:
        """Analyse approfondie d'un fichier avec Claude."""
        name = filepath.name
        rel_path = str(filepath.relative_to(self.cfg.root_dir))
        
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
        
        prompt = f"""Analyze this file ({name}) from path "{rel_path}" in EXTREME DETAIL.

Return ONLY valid JSON with this EXACT structure:
{{
    "role": "entry_point|library|config|test|utility|service|orphan",
    "description": "What this file does in 1-2 sentences",
    "purpose": "Why this file exists in the project",
    "execution_order": 1-100,
    "is_executable": true/false,
    "is_standalone": true/false,
    
    "calls": [
        {{"file": "script.py", "method": "subprocess|import|source|exec|call", "when": "startup|runtime|conditional|error", "line": 123, "critical": true/false}}
    ],
    
    "called_by_likely": ["parent scripts that probably call this"],
    "requires_before": ["files that MUST run before this"],
    "produces_after": ["files this enables to run after"],
    
    "category": "setup|install|config|core|api|db|test|deploy|monitor|cleanup|util",
    
    "inputs": ["what this script needs: files, env vars, services"],
    "outputs": ["what this script produces: files, services, state changes"],
    
    "potential_bugs": [
        {{"type": "missing_dependency|race_condition|no_error_handling|hardcoded_path|missing_env|circular_call|dead_code|unreachable", "description": "what could go wrong", "severity": "critical|high|medium|low", "line": 123, "suggestion": "how to fix"}}
    ],
    
    "fsm_state": {{
        "state_name": "INSTALLING|CONFIGURING|RUNNING|TESTING|etc",
        "preconditions": ["what must be true before"],
        "postconditions": ["what will be true after"],
        "can_fail": true/false,
        "on_failure": "retry|skip|abort|fallback",
        "timeout_seconds": 60
    }}
}}

ANALYSIS RULES:
- entry_point: Script user runs directly (main.py, run.sh, install_*, start_*)
- orphan: File that nothing calls AND calls nothing useful
- execution_order: 1=first (setup/install), 50=middle (core), 100=last (cleanup)
- Be VERY thorough about potential_bugs - look for real issues
- For FSM: think about what state the system is in before/after this script

LOOK FOR THESE BUG PATTERNS:
1. Missing error handling (no try/catch, no set -e in bash)
2. Hardcoded paths that might not exist
3. Missing environment variables
4. Race conditions (parallel execution issues)
5. Circular dependencies
6. Files called but don't exist
7. Dead code / unreachable branches
8. Missing imports
9. Undefined variables
10. Resource leaks (files not closed, connections not released)

FILE CONTENT:
```
{content[:6000]}
```"""
        
        try:
            resp = self.client.messages.create(
                model=self.cfg.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw = resp.content[0].text
            match = re.search(r'\{[\s\S]*\}', raw)
            data = json.loads(match.group(0)) if match else {}
            
            # Valeurs par défaut
            defaults = {
                'role': 'unknown', 'description': '', 'purpose': '',
                'execution_order': 50, 'is_executable': False, 'is_standalone': False,
                'calls': [], 'called_by_likely': [], 'requires_before': [], 'produces_after': [],
                'category': 'util', 'inputs': [], 'outputs': [],
                'potential_bugs': [], 'fsm_state': {}
            }
            for k, v in defaults.items():
                data.setdefault(k, v)
            
            # Nettoyer calls
            clean_calls = []
            for c in data.get('calls', []):
                if isinstance(c, dict) and 'file' in c:
                    clean_calls.append({
                        'file': c['file'],
                        'method': c.get('method', 'unknown'),
                        'when': c.get('when', 'runtime'),
                        'line': c.get('line', 0),
                        'critical': c.get('critical', False)
                    })
            data['calls'] = clean_calls
            
            self.cache[name] = {'hash': h, 'data': data}
            self.stats['analyzed'] += 1
            
            # Log résumé
            bugs_count = len(data.get('potential_bugs', []))
            calls_count = len(clean_calls)
            role = data.get('role', 'unknown')
            
            icon = {'entry_point': '🚀', 'library': '📚', 'orphan': '👻', 
                   'config': '⚙️', 'test': '🧪', 'utility': '🔧', 'service': '🔄'}.get(role, '📄')
            
            bug_str = f" | {C.R}🐛{bugs_count} bugs{C.E}" if bugs_count > 0 else ""
            Log.ok(f"{icon} {role} | calls:{calls_count}{bug_str}", 2)
            
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
            self.G.add_node(name, **result)
            
            # Ajouter les edges
            for call in result.get('calls', []):
                target = call['file']
                self.G.add_edge(name, target, **call)
            
            # Collecter les bugs
            for bug in result.get('potential_bugs', []):
                bug['file'] = name
                self.bugs.append(bug)
    
    # =========================================================================
    # ANALYSE DES WORKFLOWS
    # =========================================================================
    
    def _build_workflows(self):
        """Construit les workflows à partir des entry points."""
        Log.section("Construction des workflows")
        
        # Identifier les entry points
        entry_points = []
        for node in self.G.nodes():
            meta = self.file_meta.get(node, {})
            role = meta.get('role', '')
            in_degree = self.G.in_degree(node)
            is_exec = meta.get('is_executable', False)
            
            if role == 'entry_point' or (in_degree == 0 and is_exec):
                entry_points.append(node)
        
        # Trier par execution_order
        entry_points.sort(key=lambda n: self.file_meta.get(n, {}).get('execution_order', 50))
        
        Log.info(f"Entry points trouvés: {len(entry_points)}")
        
        # Pour chaque entry point, construire son workflow
        assigned_nodes = set()
        
        for ep in entry_points:
            workflow = self._trace_workflow(ep)
            self.workflows[ep] = workflow
            assigned_nodes.update(workflow['nodes'])
            
            Log.ok(f"Workflow '{ep}': {len(workflow['nodes'])} scripts, {len(workflow['sequence'])} étapes")
        
        # Identifier les orphelins
        all_nodes = set(self.G.nodes())
        self.orphans = list(all_nodes - assigned_nodes)
        
        # Vérifier si les orphelins sont vraiment orphelins
        real_orphans = []
        for orph in self.orphans:
            meta = self.file_meta.get(orph, {})
            if meta.get('role') == 'orphan' or (self.G.in_degree(orph) == 0 and self.G.out_degree(orph) == 0):
                real_orphans.append(orph)
        
        self.orphans = real_orphans
        
        if self.orphans:
            Log.warn(f"Orphelins détectés: {len(self.orphans)}")
    
    def _trace_workflow(self, entry_point: str) -> dict:
        """Trace le workflow complet à partir d'un entry point."""
        visited = set()
        sequence = []
        nodes = set()
        
        def dfs(node, depth=0):
            if node in visited or node not in self.G:
                return
            visited.add(node)
            nodes.add(node)
            
            meta = self.file_meta.get(node, {})
            sequence.append({
                'node': node,
                'depth': depth,
                'order': meta.get('execution_order', 50),
                'category': meta.get('category', 'util'),
                'description': meta.get('description', ''),
                'fsm_state': meta.get('fsm_state', {})
            })
            
            # Suivre les appels
            for _, target, data in self.G.out_edges(node, data=True):
                dfs(target, depth + 1)
        
        dfs(entry_point)
        
        # Trier la séquence par ordre d'exécution
        sequence.sort(key=lambda x: (x['depth'], x['order']))
        
        return {
            'entry_point': entry_point,
            'nodes': nodes,
            'sequence': sequence,
            'meta': self.file_meta.get(entry_point, {})
        }
    
    # =========================================================================
    # GÉNÉRATION FSM
    # =========================================================================
    
    def _generate_fsm(self):
        """Génère la Final State Machine globale."""
        Log.section("Génération de la FSM")
        
        states = []
        transitions = []
        
        # État initial
        states.append({
            'id': 'START',
            'name': 'Démarrage',
            'type': 'initial',
            'description': 'Point de départ du système'
        })
        
        # Collecter tous les états FSM des fichiers
        all_fsm_states = {}
        for node, meta in self.file_meta.items():
            fsm = meta.get('fsm_state', {})
            if fsm:
                state_name = fsm.get('state_name', node.upper().replace('.', '_'))
                all_fsm_states[node] = {
                    'id': state_name,
                    'name': node,
                    'type': 'normal',
                    'description': meta.get('description', ''),
                    'preconditions': fsm.get('preconditions', []),
                    'postconditions': fsm.get('postconditions', []),
                    'can_fail': fsm.get('can_fail', True),
                    'on_failure': fsm.get('on_failure', 'abort'),
                    'timeout': fsm.get('timeout_seconds', 60),
                    'category': meta.get('category', 'util'),
                    'order': meta.get('execution_order', 50)
                }
        
        # Trier par ordre d'exécution
        sorted_states = sorted(all_fsm_states.items(), key=lambda x: x[1]['order'])
        
        # Créer les états et transitions
        prev_state = 'START'
        for node, state in sorted_states:
            if self.file_meta.get(node, {}).get('is_executable', False):
                states.append(state)
                
                # Transition depuis l'état précédent
                transitions.append({
                    'from': prev_state,
                    'to': state['id'],
                    'trigger': f"run_{node}",
                    'condition': ' AND '.join(state['preconditions'][:2]) if state['preconditions'] else 'true'
                })
                
                # Transition d'échec
                if state['can_fail']:
                    transitions.append({
                        'from': state['id'],
                        'to': 'ERROR' if state['on_failure'] == 'abort' else prev_state,
                        'trigger': 'on_error',
                        'condition': 'execution_failed'
                    })
                
                prev_state = state['id']
        
        # État final
        states.append({
            'id': 'END',
            'name': 'Terminé',
            'type': 'final',
            'description': 'Exécution complète'
        })
        
        transitions.append({
            'from': prev_state,
            'to': 'END',
            'trigger': 'complete',
            'condition': 'all_success'
        })
        
        # État erreur
        states.append({
            'id': 'ERROR',
            'name': 'Erreur',
            'type': 'error',
            'description': 'Une erreur critique est survenue'
        })
        
        self.fsm_states = states
        self.fsm_transitions = transitions
        
        Log.fsm(f"FSM générée: {len(states)} états, {len(transitions)} transitions")
    
    # =========================================================================
    # GÉNÉRATION DU SCRIPT UNIFIÉ
    # =========================================================================
    
    def _generate_unified_script(self) -> str:
        """Génère un script unifié qui exécute tout dans le bon ordre."""
        
        # Collecter tous les scripts exécutables dans l'ordre
        all_executables = []
        for wf_name, wf in self.workflows.items():
            for step in wf['sequence']:
                node = step['node']
                meta = self.file_meta.get(node, {})
                if meta.get('is_executable', False) and node not in [s['node'] for s in all_executables]:
                    all_executables.append({
                        'node': node,
                        'order': meta.get('execution_order', 50),
                        'category': meta.get('category', 'util'),
                        'description': meta.get('description', ''),
                        'inputs': meta.get('inputs', []),
                        'outputs': meta.get('outputs', []),
                        'can_fail': meta.get('fsm_state', {}).get('can_fail', True),
                        'on_failure': meta.get('fsm_state', {}).get('on_failure', 'abort'),
                        'timeout': meta.get('fsm_state', {}).get('timeout_seconds', 300)
                    })
        
        # Trier
        all_executables.sort(key=lambda x: x['order'])
        
        # Générer le script
        script = '''#!/usr/bin/env python3
"""
=============================================================================
UNIFIED EXECUTION SCRIPT - Auto-generated by Workflow Analyzer
=============================================================================
Ce script exécute tous les scripts du projet dans l'ordre optimal.
Généré le: {timestamp}
=============================================================================
"""

import os
import sys
import subprocess
import time
import signal
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, List, Callable
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('unified_execution.log')
    ]
)
log = logging.getLogger(__name__)

# =============================================================================
# FSM STATES
# =============================================================================

class State(Enum):
    START = auto()
    {states_enum}
    SUCCESS = auto()
    ERROR = auto()

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class StepConfig:
    name: str
    script: str
    state: State
    description: str
    timeout: int = 300
    can_fail: bool = True
    on_failure: str = "abort"  # abort, skip, retry
    max_retries: int = 3
    inputs: List[str] = None
    outputs: List[str] = None

EXECUTION_STEPS: List[StepConfig] = [
{steps_config}
]

# =============================================================================
# EXECUTOR
# =============================================================================

class UnifiedExecutor:
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir).resolve()
        self.current_state = State.START
        self.execution_log: List[dict] = []
        self.start_time = time.time()
        
    def _run_script(self, step: StepConfig) -> bool:
        """Exécute un script avec gestion des erreurs et timeout."""
        script_path = self.project_dir / step.script
        
        if not script_path.exists():
            log.warning(f"Script non trouvé: {{step.script}}")
            return step.on_failure == "skip"
        
        log.info(f"▶ Exécution: {{step.script}}")
        log.info(f"  Description: {{step.description}}")
        
        # Préparer la commande
        if step.script.endswith('.py'):
            cmd = [sys.executable, str(script_path)]
        elif step.script.endswith(('.sh', '.bash')):
            cmd = ['bash', str(script_path)]
        else:
            cmd = [str(script_path)]
        
        # Exécuter avec timeout
        retries = 0
        while retries <= step.max_retries:
            try:
                start = time.time()
                result = subprocess.run(
                    cmd,
                    cwd=str(self.project_dir),
                    timeout=step.timeout,
                    capture_output=True,
                    text=True,
                    env={{**os.environ, 'PYTHONPATH': str(self.project_dir)}}
                )
                duration = time.time() - start
                
                if result.returncode == 0:
                    log.info(f"  ✅ Succès en {{duration:.1f}}s")
                    self.execution_log.append({{
                        'step': step.name,
                        'status': 'success',
                        'duration': duration
                    }})
                    return True
                else:
                    log.error(f"  ❌ Échec (code {{result.returncode}})")
                    if result.stderr:
                        log.error(f"  Erreur: {{result.stderr[:500]}}")
                    
                    if step.on_failure == "retry" and retries < step.max_retries:
                        retries += 1
                        log.info(f"  🔄 Retry {{retries}}/{{step.max_retries}}...")
                        time.sleep(2)
                        continue
                    elif step.on_failure == "skip":
                        log.warning(f"  ⏭️ Skip (non critique)")
                        return True
                    else:
                        return False
                        
            except subprocess.TimeoutExpired:
                log.error(f"  ⏰ Timeout après {{step.timeout}}s")
                if step.on_failure == "skip":
                    return True
                return False
            except Exception as e:
                log.error(f"  💥 Exception: {{e}}")
                return False
        
        return False
    
    def run(self, start_from: Optional[str] = None, dry_run: bool = False) -> bool:
        """Exécute tous les steps dans l'ordre."""
        log.info("=" * 60)
        log.info("UNIFIED EXECUTION - START")
        log.info(f"Project: {{self.project_dir}}")
        log.info(f"Steps: {{len(EXECUTION_STEPS)}}")
        log.info("=" * 60)
        
        started = start_from is None
        
        for i, step in enumerate(EXECUTION_STEPS, 1):
            if not started:
                if step.script == start_from:
                    started = True
                else:
                    continue
            
            log.info(f"\\n[{{i}}/{{len(EXECUTION_STEPS)}}] {{step.state.name}}")
            
            if dry_run:
                log.info(f"  [DRY-RUN] Would execute: {{step.script}}")
                continue
            
            self.current_state = step.state
            
            if not self._run_script(step):
                log.error(f"\\n💀 EXECUTION FAILED at step: {{step.name}}")
                self.current_state = State.ERROR
                self._print_summary()
                return False
        
        self.current_state = State.SUCCESS
        log.info("\\n" + "=" * 60)
        log.info("✨ ALL STEPS COMPLETED SUCCESSFULLY")
        log.info("=" * 60)
        
        self._print_summary()
        return True
    
    def _print_summary(self):
        """Affiche le résumé d'exécution."""
        duration = time.time() - self.start_time
        log.info(f"\\n📊 SUMMARY")
        log.info(f"  Total duration: {{duration:.1f}}s")
        log.info(f"  Final state: {{self.current_state.name}}")
        log.info(f"  Steps executed: {{len(self.execution_log)}}")
        
        success = sum(1 for l in self.execution_log if l['status'] == 'success')
        log.info(f"  Successful: {{success}}/{{len(self.execution_log)}}")

# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Unified Execution Script")
    parser.add_argument('--dry-run', action='store_true', help='Simulation sans exécution')
    parser.add_argument('--start-from', type=str, help='Démarrer à partir de ce script')
    parser.add_argument('--list', action='store_true', help='Lister les étapes')
    parser.add_argument('-d', '--dir', default='.', help='Répertoire du projet')
    
    args = parser.parse_args()
    
    if args.list:
        print("\\n📋 ÉTAPES D'EXÉCUTION:\\n")
        for i, step in enumerate(EXECUTION_STEPS, 1):
            print(f"  {{i:2d}}. [{{step.state.name:15s}}] {{step.script}}")
            print(f"      {{step.description}}")
        return
    
    executor = UnifiedExecutor(args.dir)
    success = executor.run(start_from=args.start_from, dry_run=args.dry_run)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
'''
        
        # Générer les enums des états
        states_enum = '\n    '.join([
            f"{s['node'].upper().replace('.', '_').replace('-', '_')} = auto()" 
            for s in all_executables
        ])
        
        # Générer la config des steps
        steps_config = []
        for s in all_executables:
            state_name = s['node'].upper().replace('.', '_').replace('-', '_')
            steps_config.append(f'''    StepConfig(
        name="{s['node']}",
        script="{s['node']}",
        state=State.{state_name},
        description="{s['description'][:100].replace('"', "'")}",
        timeout={s['timeout']},
        can_fail={s['can_fail']},
        on_failure="{s['on_failure']}",
        inputs={s['inputs'][:3] if s['inputs'] else []},
        outputs={s['outputs'][:3] if s['outputs'] else []}
    ),''')
        
        script = script.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            states_enum=states_enum,
            steps_config='\n'.join(steps_config)
        )
        
        return script
    
    # =========================================================================
    # GÉNÉRATION HTML
    # =========================================================================
    
    def _generate_html(self, live=False) -> str:
        """Génère le HTML multi-onglets."""
        
        # Données pour le HTML
        workflows_data = []
        for wf_name, wf in self.workflows.items():
            workflows_data.append({
                'name': wf_name,
                'nodes': list(wf['nodes']),
                'sequence': wf['sequence'],
                'meta': wf['meta']
            })
        
        bugs_by_severity = defaultdict(list)
        for bug in self.bugs:
            bugs_by_severity[bug.get('severity', 'medium')].append(bug)
        
        # Générer le script unifié
        unified_script = self._generate_unified_script()
        
        html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Workflow Analysis - {Path(self.cfg.root_dir).name}</title>
    {"<meta http-equiv='refresh' content='5'>" if live else ""}
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            min-height: 100vh;
        }}
        
        .header {{
            background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
            padding: 20px 30px;
            border-bottom: 1px solid #30363d;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .header h1 {{
            color: #58a6ff;
            font-size: 1.5em;
        }}
        
        .header .stats {{
            display: flex;
            gap: 20px;
        }}
        
        .stat {{
            background: #21262d;
            padding: 8px 15px;
            border-radius: 6px;
            font-size: 0.85em;
        }}
        
        .stat span {{ color: #58a6ff; font-weight: bold; }}
        .stat.bugs span {{ color: #f85149; }}
        .stat.ok span {{ color: #3fb950; }}
        
        /* Tabs */
        .tabs {{
            display: flex;
            background: #161b22;
            border-bottom: 1px solid #30363d;
            padding: 0 20px;
            overflow-x: auto;
        }}
        
        .tab {{
            padding: 12px 20px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            color: #8b949e;
            font-size: 0.9em;
            white-space: nowrap;
            transition: all 0.2s;
        }}
        
        .tab:hover {{ color: #c9d1d9; background: #21262d; }}
        .tab.active {{ color: #58a6ff; border-bottom-color: #58a6ff; }}
        .tab.bugs {{ color: #f85149; }}
        .tab.fsm {{ color: #a371f7; }}
        .tab.unified {{ color: #3fb950; }}
        
        /* Tab content */
        .tab-content {{
            display: none;
            padding: 20px;
            max-height: calc(100vh - 150px);
            overflow-y: auto;
        }}
        
        .tab-content.active {{ display: block; }}
        
        /* Workflow view */
        .workflow-header {{
            background: #161b22;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        
        .workflow-header h2 {{
            color: #3fb950;
            margin-bottom: 10px;
        }}
        
        .workflow-header p {{
            color: #8b949e;
            font-size: 0.9em;
        }}
        
        .sequence {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        
        .step {{
            display: flex;
            align-items: stretch;
            gap: 15px;
        }}
        
        .step-number {{
            width: 40px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        
        .step-number .num {{
            width: 30px;
            height: 30px;
            background: #238636;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.85em;
        }}
        
        .step-number .line {{
            flex: 1;
            width: 2px;
            background: #30363d;
            margin-top: 5px;
        }}
        
        .step-card {{
            flex: 1;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 15px;
        }}
        
        .step-card h3 {{
            color: #58a6ff;
            font-size: 1em;
            margin-bottom: 5px;
        }}
        
        .step-card .desc {{
            color: #8b949e;
            font-size: 0.85em;
        }}
        
        .step-card .meta {{
            display: flex;
            gap: 10px;
            margin-top: 10px;
            flex-wrap: wrap;
        }}
        
        .step-card .tag {{
            background: #21262d;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75em;
        }}
        
        .step-card .tag.cat {{ color: #a371f7; }}
        .step-card .tag.order {{ color: #f0883e; }}
        
        /* Bugs view */
        .bug-list {{
            display: flex;
            flex-direction: column;
            gap: 15px;
        }}
        
        .bug-card {{
            background: #161b22;
            border-left: 4px solid #f85149;
            padding: 15px;
            border-radius: 0 8px 8px 0;
        }}
        
        .bug-card.high {{ border-left-color: #f85149; }}
        .bug-card.medium {{ border-left-color: #f0883e; }}
        .bug-card.low {{ border-left-color: #3fb950; }}
        
        .bug-card h4 {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
        }}
        
        .bug-card .severity {{
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
        }}
        
        .bug-card .severity.critical {{ background: #f85149; color: white; }}
        .bug-card .severity.high {{ background: #da3633; color: white; }}
        .bug-card .severity.medium {{ background: #f0883e; color: black; }}
        .bug-card .severity.low {{ background: #3fb950; color: black; }}
        
        .bug-card .file {{
            color: #58a6ff;
            font-family: monospace;
        }}
        
        .bug-card .suggestion {{
            background: #1c2128;
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 0.85em;
            color: #3fb950;
        }}
        
        /* FSM view */
        .fsm-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
        }}
        
        .fsm-state {{
            background: #161b22;
            border: 2px solid #30363d;
            border-radius: 12px;
            padding: 15px;
            min-width: 200px;
        }}
        
        .fsm-state.initial {{ border-color: #3fb950; }}
        .fsm-state.final {{ border-color: #a371f7; }}
        .fsm-state.error {{ border-color: #f85149; }}
        
        .fsm-state h4 {{ color: #58a6ff; margin-bottom: 5px; }}
        .fsm-state p {{ font-size: 0.8em; color: #8b949e; }}
        
        /* Orphans */
        .orphan-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        
        .orphan {{
            background: #21262d;
            padding: 8px 15px;
            border-radius: 6px;
            border: 1px dashed #484f58;
            color: #8b949e;
        }}
        
        /* Code view */
        .code-container {{
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .code-header {{
            background: #161b22;
            padding: 10px 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .code-header button {{
            background: #238636;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 6px;
            cursor: pointer;
        }}
        
        .code-header button:hover {{ background: #2ea043; }}
        
        pre {{
            padding: 15px;
            overflow-x: auto;
            font-family: 'Fira Code', monospace;
            font-size: 0.85em;
            line-height: 1.5;
        }}
        
        /* Live indicator */
        .live-indicator {{
            position: fixed;
            top: 10px;
            right: 10px;
            background: #238636;
            color: white;
            padding: 10px 15px;
            border-radius: 6px;
            font-size: 0.85em;
            animation: pulse 2s infinite;
            z-index: 1000;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.7; }}
        }}
    </style>
</head>
<body>
    {f'<div class="live-indicator">🔄 Analyse en cours... (refresh auto)</div>' if live else ''}
    
    <div class="header">
        <h1>🔄 Workflow Analysis - {Path(self.cfg.root_dir).name}</h1>
        <div class="stats">
            <div class="stat">Fichiers: <span>{len(self.file_meta)}</span></div>
            <div class="stat ok">Workflows: <span>{len(self.workflows)}</span></div>
            <div class="stat bugs">Bugs: <span>{len(self.bugs)}</span></div>
            <div class="stat">Orphelins: <span>{len(self.orphans)}</span></div>
        </div>
    </div>
    
    <div class="tabs">
        <div class="tab active" onclick="showTab('overview')">📊 Vue d'ensemble</div>
        {''.join(f'<div class="tab" onclick="showTab(\'wf-{i}\')">{wf["name"][:20]}</div>' for i, wf in enumerate(workflows_data))}
        <div class="tab bugs" onclick="showTab('bugs')">🐛 Bugs ({len(self.bugs)})</div>
        <div class="tab fsm" onclick="showTab('fsm')">⚙️ FSM</div>
        <div class="tab" onclick="showTab('orphans')">👻 Orphelins ({len(self.orphans)})</div>
        <div class="tab unified" onclick="showTab('unified')">📜 Script Unifié</div>
    </div>
    
    <!-- Overview Tab -->
    <div id="overview" class="tab-content active">
        <h2 style="color: #58a6ff; margin-bottom: 20px;">🎯 Ordre d'Exécution Recommandé</h2>
        
        <div class="sequence">
        {''.join(self._render_overview_step(i, wf) for i, wf in enumerate(workflows_data, 1))}
        </div>
    </div>
    
    <!-- Workflow Tabs -->
    {''.join(self._render_workflow_tab(i, wf) for i, wf in enumerate(workflows_data))}
    
    <!-- Bugs Tab -->
    <div id="bugs" class="tab-content">
        <h2 style="color: #f85149; margin-bottom: 20px;">🐛 Problèmes Détectés</h2>
        
        {self._render_bugs_section('critical', '💀 Critiques', bugs_by_severity.get('critical', []))}
        {self._render_bugs_section('high', '🔴 Élevés', bugs_by_severity.get('high', []))}
        {self._render_bugs_section('medium', '🟠 Moyens', bugs_by_severity.get('medium', []))}
        {self._render_bugs_section('low', '🟢 Faibles', bugs_by_severity.get('low', []))}
    </div>
    
    <!-- FSM Tab -->
    <div id="fsm" class="tab-content">
        <h2 style="color: #a371f7; margin-bottom: 20px;">⚙️ Final State Machine</h2>
        <div class="fsm-container">
            {self._render_fsm_states()}
        </div>
    </div>
    
    <!-- Orphans Tab -->
    <div id="orphans" class="tab-content">
        <h2 style="color: #8b949e; margin-bottom: 20px;">👻 Scripts Orphelins</h2>
        <p style="margin-bottom: 15px; color: #8b949e;">Ces fichiers ne sont appelés par aucun workflow et n'appellent rien d'utile.</p>
        <div class="orphan-list">
            {''.join(f'<div class="orphan">{o}</div>' for o in self.orphans) if self.orphans else '<p>Aucun orphelin détecté ✨</p>'}
        </div>
    </div>
    
    <!-- Unified Script Tab -->
    <div id="unified" class="tab-content">
        <h2 style="color: #3fb950; margin-bottom: 20px;">📜 Script d'Exécution Unifié</h2>
        <p style="margin-bottom: 15px; color: #8b949e;">Ce script exécute automatiquement tous les workflows dans l'ordre optimal.</p>
        
        <div class="code-container">
            <div class="code-header">
                <span>unified_executor.py</span>
                <button onclick="copyCode()">📋 Copier</button>
            </div>
            <pre id="unified-code">{self._escape_html(unified_script)}</pre>
        </div>
    </div>
    
    <script>
        function showTab(tabId) {{
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            
            // Show selected
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }}
        
        function copyCode() {{
            const code = document.getElementById('unified-code').textContent;
            navigator.clipboard.writeText(code).then(() => {{
                alert('Code copié!');
            }});
        }}
    </script>
</body>
</html>
'''
        
        output_path = Path(self.cfg.root_dir) / self.cfg.output_html
        output_path.write_text(html)
        
        # Aussi sauvegarder le script unifié
        unified_path = Path(self.cfg.root_dir) / "unified_executor.py"
        unified_path.write_text(unified_script)
        
        status = "LIVE" if live else "FINAL"
        Log.ok(f"HTML [{status}]: {output_path.name}")
        
        if not live:
            Log.ok(f"Script unifié: {unified_path.name}")
        
        return str(output_path)
    
    def _escape_html(self, text: str) -> str:
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    def _render_overview_step(self, num: int, wf: dict) -> str:
        meta = wf.get('meta', {})
        return f'''
        <div class="step">
            <div class="step-number">
                <div class="num">{num}</div>
                <div class="line"></div>
            </div>
            <div class="step-card">
                <h3>🚀 {wf['name']}</h3>
                <div class="desc">{meta.get('description', 'Pas de description')}</div>
                <div class="meta">
                    <span class="tag cat">{meta.get('category', 'util')}</span>
                    <span class="tag order">Order: {meta.get('execution_order', 50)}</span>
                    <span class="tag">{len(wf['nodes'])} scripts</span>
                </div>
            </div>
        </div>
        '''
    
    def _render_workflow_tab(self, idx: int, wf: dict) -> str:
        steps_html = ''
        for i, step in enumerate(wf['sequence'], 1):
            steps_html += f'''
            <div class="step">
                <div class="step-number">
                    <div class="num">{i}</div>
                    <div class="line"></div>
                </div>
                <div class="step-card">
                    <h3>{step['node']}</h3>
                    <div class="desc">{step.get('description', '')}</div>
                    <div class="meta">
                        <span class="tag cat">{step.get('category', 'util')}</span>
                        <span class="tag order">Order: {step.get('order', 50)}</span>
                        <span class="tag">Depth: {step.get('depth', 0)}</span>
                    </div>
                </div>
            </div>
            '''
        
        return f'''
        <div id="wf-{idx}" class="tab-content">
            <div class="workflow-header">
                <h2>🚀 Workflow: {wf['name']}</h2>
                <p>{wf['meta'].get('description', '')}</p>
            </div>
            <div class="sequence">{steps_html}</div>
        </div>
        '''
    
    def _render_bugs_section(self, severity: str, title: str, bugs: list) -> str:
        if not bugs:
            return ''
        
        bugs_html = ''
        for bug in bugs:
            bugs_html += f'''
            <div class="bug-card {severity}">
                <h4>
                    <span class="severity {severity}">{severity.upper()}</span>
                    <span class="file">{bug.get('file', 'unknown')}</span>
                    {f"(ligne {bug.get('line', '?')})" if bug.get('line') else ''}
                </h4>
                <p><strong>Type:</strong> {bug.get('type', 'unknown')}</p>
                <p>{bug.get('description', '')}</p>
                {f'<div class="suggestion">💡 {bug.get("suggestion", "")}</div>' if bug.get('suggestion') else ''}
            </div>
            '''
        
        return f'''
        <h3 style="color: #{'f85149' if severity in ['critical', 'high'] else 'f0883e' if severity == 'medium' else '3fb950'}; margin: 20px 0 10px;">{title}</h3>
        <div class="bug-list">{bugs_html}</div>
        '''
    
    def _render_fsm_states(self) -> str:
        if not hasattr(self, 'fsm_states'):
            return '<p>FSM non générée</p>'
        
        html = ''
        for state in self.fsm_states:
            state_type = state.get('type', 'normal')
            html += f'''
            <div class="fsm-state {state_type}">
                <h4>{"🟢" if state_type == "initial" else "🔴" if state_type == "error" else "🟣" if state_type == "final" else "⚪"} {state['id']}</h4>
                <p><strong>{state['name']}</strong></p>
                <p style="font-size: 0.75em; margin-top: 5px;">{state.get('description', '')[:80]}</p>
            </div>
            '''
        return html
    
    # =========================================================================
    # RUN
    # =========================================================================
    
    def run(self):
        """Lance l'analyse complète."""
        start = time.time()
        
        Log.header("🔄 WORKFLOW ANALYZER v4.0")
        
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
        
        # Phase 1: Analyse IA
        Log.header("🧠 PHASE 1: Analyse IA approfondie")
        
        html_path = self._generate_html(live=True)
        if self.cfg.auto_open:
            Log.ok(f"🌐 Ouverture navigateur")
            webbrowser.open(f'file://{html_path}')
        
        processed = 0
        try:
            for chunk_idx, chunk in enumerate(chunks):
                self.monitor.update(phase=f"Analyse {chunk_idx+1}/{len(chunks)}")
                
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
                    gc.collect()
                
                if (chunk_idx + 1) % 2 == 0:
                    print()
                    self._build_workflows()
                    self._generate_html(live=True)
        
        except KeyboardInterrupt:
            Log.warn("\n⚠️ Interruption...")
        
        finally:
            self.monitor.stop()
            self._save_cache()
        
        # Phase 2: Construction workflows
        Log.header("🔄 PHASE 2: Construction des Workflows")
        self._build_workflows()
        
        # Phase 3: Génération FSM
        Log.header("⚙️ PHASE 3: Génération FSM")
        self._generate_fsm()
        
        # Phase 4: HTML final
        Log.header("📊 PHASE 4: Génération HTML final")
        html_path = self._generate_html(live=False)
        
        # Stats
        duration = time.time() - start
        Log.header("📊 STATISTIQUES FINALES")
        print(f"  📁 Fichiers analysés : {C.B}{self.stats['total']}{C.E}")
        print(f"  🧠 Via Claude        : {C.C}{self.stats['analyzed']}{C.E}")
        print(f"  💾 Depuis cache      : {C.G}{self.stats['cached']}{C.E}")
        print(f"  ❌ Erreurs           : {C.R}{self.stats['errors']}{C.E}")
        print(f"  🚀 Workflows         : {C.G}{len(self.workflows)}{C.E}")
        print(f"  🐛 Bugs détectés     : {C.R}{len(self.bugs)}{C.E}")
        print(f"  👻 Orphelins         : {C.Y}{len(self.orphans)}{C.E}")
        print(f"  ⏱️  Durée             : {C.Y}{duration:.1f}s{C.E}")
        print()
        
        Log.ok(f"✨ Terminé! Rafraîchissez le navigateur.")
        Log.info(f"   HTML: {html_path}")
        Log.info(f"   Script unifié: unified_executor.py")

# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse
    
    p = argparse.ArgumentParser(description="Workflow Analyzer v4.0")
    p.add_argument('-d', '--dir', default="/home/tor/Downloads/ids2", help='Répertoire')
    p.add_argument('-w', '--workers', type=int, default=3, help='Workers')
    p.add_argument('-c', '--chunk', type=int, default=6, help='Chunk size')
    p.add_argument('--cpu', type=float, default=85.0, help='Max CPU %%')
    p.add_argument('--ram', type=float, default=90.0, help='Max RAM %%')
    p.add_argument('-o', '--output', default='workflow_analysis.html', help='Output')
    p.add_argument('-k', '--key', help='API key')
    p.add_argument('--no-open', action='store_true', help='Ne pas ouvrir navigateur')
    p.add_argument('--open', action='store_true', help='Ouvrir HTML existant')
    p.add_argument('--clear', action='store_true', help='Vider le cache')
    
    args = p.parse_args()
    
    html_path = Path(args.dir) / args.output
    cache_path = Path(args.dir) / "workflow_analysis_cache.json"
    
    if args.open:
        if html_path.exists():
            print(f"🌐 Ouverture: {html_path}")
            webbrowser.open(f'file://{html_path}')
        else:
            print(f"❌ Non trouvé: {html_path}")
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
    
    analyzer = WorkflowAnalyzer(cfg)
    analyzer.run()

if __name__ == "__main__":
    main()
