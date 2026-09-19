#!/usr/bin/env python3
"""
gate_hook.py — gate déterministe déclenché par le hook kanban_task_claimed.

Un worker LLM (spawné par le dispatcher) est précédé d'un gate déterministe :
ce script tourne SYNCHRONEMENT dans le dispatcher, juste avant le spawn du
worker (le hook kanban_task_claimed est synchrone, pas dans
_HOOK_TIMEOUT_BOUNDED_HOOKS). Il exécute le gate défini pour la carte et
écrit le verdict en commentaire structuré `[gate] pass|fail: ...`. Le worker
LLM, spawné juste après, lit ce commentaire via kanban_show et agit en
conséquence (continue si pass, bloque/retry si fail).

Le "résultat influence la suite" se fait via le commentaire que le worker
lit — PAS via le exit code (kanban_task_claimed est un observer, son exit
code est ignoré par le dispatcher).

Gate résolu pour une carte :
  1. Si la carte a un `workflow_template_id`, on charge workflows/<id>.yaml,
     on prend la première étape `deterministic` (ou l'étape `gate` avec une
     `command`), on exécute la commande rendue. Verdict = exit code.
  2. Sinon, gate par défaut : pass (aucune contrainte).

Usage (via hook, stdin JSON) :
  kanban_task_claimed -> python3 gate_hook.py

Test manuel :
  echo '{"hook_event_name":"kanban_task_claimed","extra":{"task_id":"t_xxx","board":"hermes-experiment"}}' | python3 gate_hook.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERMES_BIN = shutil.which("hermes") or os.path.expanduser(
    "~/.hermes/hermes-agent/venv/bin/hermes")
PIPELINE_REPO = os.environ.get("PIPELINE_REPO", "${HOME}/hermes-experiment")
DEFAULT_BOARD = os.environ.get("KANBAN_BOARD", "hermes-experiment")
GATE_COMMENT_PREFIX = "[gate] "


def kanban(*args: str, board: str = DEFAULT_BOARD) -> str:
    r = subprocess.run(
        [HERMES_BIN, "kanban", "--board", board, *args],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"kanban {' '.join(args)} -> exit {r.returncode}\n{r.stderr.strip()[:500]}")
    return r.stdout


def get_task(task_id: str, board: str) -> dict:
    out = kanban("show", task_id, "--json", board=board)
    data = json.loads(out)
    if isinstance(data, dict) and "task" in data and isinstance(data["task"], dict):
        data = data["task"]
    return data


def render(template: str, ctx: dict) -> str:
    """Substitue {{ticket.*}} / {{board}} — inconnues laissées littérales."""
    def repl(m):
        key = m.group(1).strip()
        parts = key.split(".")
        val = ctx
        for p in parts:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                return m.group(0)
        return str(val)
    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", repl, template)


def load_workflow(wf_id: str) -> dict | None:
    """Charge workflows/<id>.yaml depuis le repo pipeline."""
    import yaml
    path = Path(PIPELINE_REPO) / "workflows" / f"{wf_id}.yaml"
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text())


def find_gate_command(wf: dict) -> str | None:
    """Première étape deterministic (command) ou gate avec command."""
    for step in wf.get("steps", []):
        stype = step.get("type", "agentic")
        if stype == "deterministic" and step.get("command"):
            return step["command"]
        if stype == "gate" and step.get("command"):
            return step["command"]
    return None


def run_gate(task: dict, board: str) -> tuple[bool, str]:
    """Exécute le gate de la carte. Retourne (pass, message)."""
    wf_id = task.get("workflow_template_id")
    if not wf_id:
        return True, "aucun workflow_template_id — gate par défaut pass"

    wf = load_workflow(wf_id)
    if wf is None:
        return False, f"workflow {wf_id} introuvable dans {PIPELINE_REPO}/workflows/"

    cmd = find_gate_command(wf)
    if cmd is None:
        return True, f"workflow {wf_id}: aucune étape deterministic/gate avec command — pass"

    ctx = {
        "ticket": {
            "id": task.get("id", ""),
            "title": task.get("title", ""),
            "body": task.get("body", ""),
        },
        "board": board,
    }
    rendered = render(cmd, ctx)
    try:
        r = subprocess.run(
            ["bash", "-c", rendered], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return False, f"gate timeout (>60s): {rendered}"
    if r.returncode == 0:
        return True, f"gate ok: {rendered}"
    return False, f"gate fail (exit {r.returncode}): {rendered}\n{r.stderr.strip()[:300]}"


def main() -> int:
    # Lire le payload stdin (JSON) fourni par le shell hook.
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}

    extra = payload.get("extra", {}) or {}
    task_id = extra.get("task_id") or payload.get("task_id")
    board = extra.get("board") or payload.get("board") or DEFAULT_BOARD

    if not task_id:
        # Payload synthétique de `hermes hooks test` peut ne pas porter task_id.
        print("gate_hook: pas de task_id dans le payload — rien à faire")
        return 0

    try:
        task = get_task(task_id, board)
    except Exception as exc:
        print(f"gate_hook: carte {task_id} illisible: {exc}")
        return 0

    # Ne gate que les cartes non-terminales (ready/running) — pas les done.
    if task.get("status") in ("done", "archived", "failed", "cancelled"):
        print(f"gate_hook: carte {task_id} {task.get('status')} — skip")
        return 0

    passed, message = run_gate(task, board)
    verdict = "pass" if passed else "fail"
    comment = f"{GATE_COMMENT_PREFIX}{verdict}: {message}"

    try:
        kanban("comment", task_id, comment, board=board)
        print(f"gate_hook: {task_id} -> {verdict}")
    except Exception as exc:
        print(f"gate_hook: échec écriture commentaire {task_id}: {exc}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
