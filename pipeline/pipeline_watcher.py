#!/usr/bin/env python3
"""
Watcher pipeline kanban — exécute le workflow YAML sur les cartes workflow-driven.

Conforme au design Hermes : les cartes workflow-driven sont assignées à une
lane NON-spawnable (assignee 'pipeline', qui n'est pas un profil Hermes). Le
dispatcher Hermes les laisse en 'ready' (skipped_nonspawnable) ; ce watcher
externe (pattern du pont gh_kanban_bridge.py) les récupère, exécute le
pipeline de façon déterministe, puis complète la carte.

  PULL  : cartes 'ready' avec workflow_template_id non nul -> claim + run
          pipeline/engine.py + kanban complete.

Usage :
  pipeline_watcher.py run

Variables d'environnement :
  KANBAN_BOARD     board kanban                (défaut: hermes-experiment)
  PIPELINE_REPO    repo contenant pipeline/    (défaut: ${HOME}/hermes-experiment)
  DRY_RUN          1 = afficher sans exécuter les écritures
  WATCHER_VERBOSE  1 = loguer même les ticks sans action (défaut: silencieux)

Mode silencieux (défaut) : stdout ne sort que si une action a réellement eu
lieu — conçu pour un cron `--no-agent` où stdout vide = tick muet.
"""

import json
import os
import re
import shutil
import subprocess
import sys

KANBAN_BOARD = os.environ.get("KANBAN_BOARD", "hermes-experiment")
PIPELINE_REPO = os.environ.get("PIPELINE_REPO") or os.path.expandvars("${HOME}/hermes-experiment")
DRY_RUN = os.environ.get("DRY_RUN") == "1"
QUIET_IDLE = os.environ.get("WATCHER_VERBOSE") != "1"

HERMES_BIN = shutil.which("hermes") or os.path.expanduser(
    "~/.hermes/hermes-agent/venv/bin/hermes")

_buf: list[str] = []


def log(msg: str) -> None:
    if QUIET_IDLE:
        _buf.append(msg)
    else:
        print(f"[pipeline-watcher] {msg}")


def flush_logs() -> None:
    """En mode silencieux, n'imprime que les lignes d'action."""
    if not QUIET_IDLE:
        return
    action_re = re.compile(r"claim|pipeline|complétée|terminé")
    actions = [l for l in _buf if action_re.search(l)]
    if actions:
        for a in actions:
            print(f"[pipeline-watcher] {a}")


def kanban(*args: str) -> str:
    r = subprocess.run(
        [HERMES_BIN, "kanban", "--board", KANBAN_BOARD, *args],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(f"kanban {' '.join(args)} -> exit {r.returncode}\n{r.stderr.strip()[:500]}")
    return r.stdout


def list_workflow_ready() -> list[dict]:
    """Cartes 'ready' avec un workflow_template_id non nul."""
    out = kanban("list", "--json")
    tasks = json.loads(out) or []
    return [t for t in tasks
            if t.get("status") == "ready" and t.get("workflow_template_id")]


def run_pipeline(task: dict) -> dict:
    """Exécute pipeline/engine.py run workflows/<id>.yaml <task> --board."""
    wf = task["workflow_template_id"]
    task_id = task["id"]
    wf_path = os.path.join(PIPELINE_REPO, "workflows", f"{wf}.yaml")
    if not os.path.exists(wf_path):
        raise RuntimeError(f"workflow introuvable: {wf_path}")
    cmd = [
        sys.executable, os.path.join(PIPELINE_REPO, "pipeline", "engine.py"),
        "run", wf_path, task_id, "--board", KANBAN_BOARD,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600,
                       cwd=PIPELINE_REPO)
    if r.returncode != 0:
        raise RuntimeError(f"pipeline -> exit {r.returncode}\n{r.stderr.strip()[:800]}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": True, "raw": r.stdout[:500]}


def run() -> None:
    tasks = list_workflow_ready()
    log(f"run: {len(tasks)} carte(s) workflow-driven prête(s)")
    for t in tasks:
        task_id = t["id"]
        wf = t["workflow_template_id"]
        title = (t.get("title") or "")[:60]
        # Claim atomique : si un autre watcher l'a déjà prise, on passe.
        try:
            kanban("claim", task_id)
        except RuntimeError as e:
            log(f"  ⏭️  {task_id} non claimable (déjà prise ?): {str(e)[:80]}")
            continue
        log(f"  ▶️  claim {task_id} '{title}' (workflow={wf})")
        if DRY_RUN:
            continue
        try:
            result = run_pipeline(t)
            ok = result.get("ok", False)
            summary = f"Workflow {wf} terminé (pipeline)"
            if not ok:
                summary = f"Workflow {wf} échoué: {result.get('error', '?')}"
            kanban("complete", task_id, "--result", summary)
            log(f"  ✅ complétée {task_id} (ok={ok})")
        except RuntimeError as e:
            log(f"  ❌ {task_id} pipeline échoué: {str(e)[:200]}")
            # Ne pas bloquer : la carte reste running, le prochain tick retente
            # (le claim expire au TTL). On la laisse telle quelle.


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "run"
    if action != "run":
        sys.exit(f"usage: {sys.argv[0]} run")
    log(f"board={KANBAN_BOARD} repo={PIPELINE_REPO}"
        + (" [DRY RUN]" if DRY_RUN else ""))
    try:
        run()
    finally:
        flush_logs()


if __name__ == "__main__":
    main()
