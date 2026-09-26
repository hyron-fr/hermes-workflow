#!/usr/bin/env python3
"""pj_spawn_guard.py — garde-fou du pipeline pj : SEULS pj-master et pj-dev travaillent.

Contexte (vérifié dans la source Hermes)
----------------------------------------
`hermes_cli/kanban_decompose._resolve_profile_from_cfg` retombe sur
`get_active_profile_name()` quand `kanban.default_assignee` / `orchestrator_profile`
sont vides : c'est le profil qui EXÉCUTE le dispatcher (ex. `default`) qui
devient l'assignee des cartes. D'où des cartes créées/spawnées hors pipeline sur
les boards pj. La config seule ne suffit pas (elle se re-perd : autre gateway,
config recréée). Ce script est la barrière qui refuse le travail hors pipeline.

Deux points d'ancrage (le hook ne peut pas annuler un claim déjà consommé)
-------------------------------------------------------------------------
1. `on_kanban_dispatch_tick` — tiré APRÈS `_dispatch_tick_lock` relâché (donc
   blocage sans risque de deadlock). Il **bloque** toute carte hors-pipeline du
   board : elle ne sera pas claimée au tick suivant.
2. `kanban_task_claimed` — tiré avant le spawn du worker, sous verrou : on y
   signale la carte (commentaire `[gate] fail`). L'effet dur vient de (1), qui a
   lieu un tick plus tôt ; (2) couvre la carte créée entre-temps.

Règles
------
  boards concernés   : slug commençant par `pj` (ou PJ_BOARDS, séparés par virgule)
  assignees admis    : `pj-master`, `pj-dev`, `pj-doc`, `pj-test` (ou PJ_ALLOWED_ASSIGNEES)
  hors pipeline      : toute autre assignee (default, vide, ...)
Statuts examinés : triage, todo, ready, running, scheduled, blocked, review.

Usage (hooks, stdin JSON) : kanban_task_claimed | on_kanban_dispatch_tick
Test manuel :
  echo '{"extra":{"task_id":"t_x","board":"pj-dino-game","assignee":"default"}}' | python3 pj_spawn_guard.py
  echo '{"board":"pj-dino-game"}' | python3 pj_spawn_guard.py
"""

import json
import os
import shutil
import subprocess
import sys

HERMES_BIN = shutil.which("hermes") or os.path.expanduser(
    "~/.hermes/hermes-agent/venv/bin/hermes")

DEFAULT_BOARD_PREFIX = "pj"
DEFAULT_ALLOWED = "pj-master,pj-dev,pj-doc,pj-test"
ACTIVE_STATUSES = ("triage", "todo", "ready", "running", "scheduled", "blocked", "review")
BLOCK_REASON = (
    "hors pipeline pj : assignee non autorisé (seuls pj-master et pj-dev opèrent "
    "sur les boards pj). Réassigner via le cycle issue GitHub -> pont -> t1..t6."
)


def allowed_assignees() -> set[str]:
    env = os.environ.get("PJ_ALLOWED_ASSIGNEES", "").strip()
    return {a.strip() for a in (env or DEFAULT_ALLOWED).split(",") if a.strip()}


def allowed_boards() -> list[str]:
    env = os.environ.get("PJ_BOARDS", "").strip()
    return [b.strip() for b in env.split(",") if b.strip()]


def board_is_pj(board: str) -> bool:
    explicit = allowed_boards()
    if explicit:
        return board in explicit
    return (board or "").startswith(DEFAULT_BOARD_PREFIX)


def kanban(board: str, *args: str, timeout: int = 60):
    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/.local/bin:") + env.get("PATH", "")
    return subprocess.run([HERMES_BIN, "kanban", "--board", board, *args],
                          capture_output=True, text=True, env=env, timeout=timeout)


def list_tasks(board: str) -> list[dict]:
    r = kanban(board, "list", "--json", timeout=45)
    if r.returncode != 0:
        return []
    try:
        return json.loads(r.stdout or "[]")
    except Exception:
        return []


def offenders(board: str, allowed: set[str]) -> list[dict]:
    return [t for t in list_tasks(board)
            if t.get("status") in ACTIVE_STATUSES
            and (t.get("assignee") or "").strip() not in allowed]


def on_dispatch_tick(board: str) -> int:
    """Bloque les cartes hors-pipeline (hors verrou de dispatch)."""
    allowed = allowed_assignees()
    bad = offenders(board, allowed)
    if not bad:
        return 0
    for t in bad:
        tid = t.get("id")
        who = (t.get("assignee") or "(vide)").strip()
        kanban(board, "comment", tid,
               f"[gate] fail: assignee `{who}` hors pipeline pj sur {board}. "
               f"Autorisés : {sorted(allowed)}.")
        r = kanban(board, "block", tid, BLOCK_REASON)
        print(json.dumps({
            "hook": "on_kanban_dispatch_tick", "board": board,
            "task_id": tid, "assignee": who,
            "action": "blocked" if r.returncode == 0 else "block-failed",
        }))
    return 0


def on_task_claimed(board: str, task_id: str, assignee: str) -> int:
    """Signale (et tente de neutraliser) une carte hors-pipeline au moment du claim."""
    allowed = allowed_assignees()
    if (assignee or "").strip() in allowed:
        return 0
    who = (assignee or "(vide)").strip()
    reason = (f"[gate] fail: assignee `{who}` hors pipeline pj sur {board}. "
              f"Autorisés : {sorted(allowed)}. {BLOCK_REASON}")
    kanban(board, "comment", task_id, reason)
    kanban(board, "block", task_id, BLOCK_REASON)
    print(json.dumps({
        "hook": "kanban_task_claimed", "board": board,
        "task_id": task_id, "assignee": who, "action": "signalled+blocked",
    }))
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    event = payload.get("hook_event_name") or payload.get("event") or ""
    extra = payload.get("extra") or {}
    board = (extra.get("board") or payload.get("board") or "").strip()

    if not board_is_pj(board):
        return 0

    if event == "on_kanban_dispatch_tick" or (not event and not extra.get("task_id")):
        return on_dispatch_tick(board)
    return on_task_claimed(board, extra.get("task_id") or "", extra.get("assignee") or "")


if __name__ == "__main__":
    sys.exit(main())