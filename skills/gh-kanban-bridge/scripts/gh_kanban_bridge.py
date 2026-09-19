#!/usr/bin/env python3
"""
Pont GitHub Issues <-> Kanban Hermes.

Expérience : hyron-fr/hermes-experiment

Deux directions, sans fichier d'état local (l'état est dérivé de GitHub
et du board kanban) :

  PULL  : issues ouvertes SANS label 'kanban' -> cartes kanban
          (idempotency-key 'gh-issue-<n>' => pas de doublon au retry)
  PUSH  : cartes kanban 'done' liées à une issue GitHub encore ouverte
          -> l'issue est fermée avec un commentaire citant la tâche
          et le résumé du handoff du worker.

Usage :
  gh_kanban_bridge.py pull
  gh_kanban_bridge.py push
  gh_kanban_bridge.py sync      (pull puis push)

Variables d'environnement :
  GH_REPO          dépôt cible                 (défaut: hyron-fr/hermes-experiment)
  KANBAN_BOARD     board kanban                (défaut: hermes-experiment)
  KANBAN_ASSIGNEE  profil assigné aux cartes   (défaut: default)
  DRY_RUN          1 = afficher sans exécuter les écritures
  BRIDGE_VERBOSE   1 = loguer même les ticks sans action (défaut: silencieux)

Mode silencieux (défaut) : stdout ne sort que si une action a réellement
eu lieu — conçu pour un cron `--no-agent` où stdout vide = tick muet.
"""

import json
import os
import re
import shutil
import subprocess
import sys

GH_REPO = os.environ.get("GH_REPO", "hyron-fr/hermes-experiment")
KANBAN_BOARD = os.environ.get("KANBAN_BOARD", "hermes-experiment")
KANBAN_ASSIGNEE = os.environ.get("KANBAN_ASSIGNEE", "default")
MIRROR_LABEL = "kanban"
TRIAGE_LABEL = "triage"
MIRROR_LABEL_COLOR = "1d76db"
TRIAGE_LABEL_COLOR = "d93f0b"
BOT_GRACE_SECONDS = 600  # issues plus jeunes -> réservées au bot gh-triage
DRY_RUN = os.environ.get("DRY_RUN") == "1"
QUIET_IDLE = os.environ.get("BRIDGE_VERBOSE") != "1"

HERMES_BIN = shutil.which("hermes") or os.path.expanduser(
    "~/.hermes/hermes-agent/venv/bin/hermes")
GH_BIN = shutil.which("gh") or "/usr/bin/gh"

_buf: list[str] = []


def log(msg: str) -> None:
    if QUIET_IDLE:
        _buf.append(msg)
    else:
        print(f"[bridge] {msg}")


def flush_logs() -> None:
    """En mode silencieux, n'imprime que l'en-tête + les lignes d'action."""
    if not QUIET_IDLE:
        return
    action_re = re.compile(r"carte créée|labellisée|fermeture issue|issue #\d+ fermée")
    actions = [l for l in _buf if action_re.search(l)]
    if actions:
        header = next((l for l in _buf if l.startswith("repo=")), None)
        if header:
            print(f"[bridge] {header}")
        for a in actions:
            print(f"[bridge] {a}")


def ensure_mirror_label() -> None:
    """Crée le label miroir s'il n'existe pas (idempotent)."""
    r = subprocess.run(
        [GH_BIN, "label", "create", MIRROR_LABEL, "--repo", GH_REPO,
         "--color", MIRROR_LABEL_COLOR,
         "--description", "Issue miroir d'une carte kanban Hermes"],
        capture_output=True, text=True)
    if r.returncode != 0 and "already exists" not in r.stderr:
        raise RuntimeError(f"gh label create {MIRROR_LABEL}\n{r.stderr.strip()}")


def sh(cmd: list[str]) -> str:
    """Run a command, return stdout, raise with stderr on failure."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n-> exit {r.returncode}\n{r.stderr.strip()}")
    return r.stdout


def gh(*args: str) -> str:
    return sh([GH_BIN, *args])


def kanban(*args: str) -> str:
    return sh([HERMES_BIN, "kanban", "--board", KANBAN_BOARD, *args])


# ---------------------------------------------------------------- pull

def list_open_issues() -> list[dict]:
    out = gh("issue", "list", "--repo", GH_REPO, "--state", "open",
             "--json", "number,title,body,url,labels,createdAt")
    return json.loads(out) or []


def issue_has_label(issue: dict, label: str) -> bool:
    return any(l.get("name") == label for l in issue.get("labels") or [])


def check_no_rogue_cards() -> None:
    """Garde-fou : alerte si une carte active n'est pas passée par le cycle
    issue→drill→go (pas de ligne 'Importé depuis' dans son body).
    Le pont ne la supprime pas automatiquement — il la signale."""
    tasks = json.loads(kanban("list", "--json") or "[]")
    rogue = [t for t in tasks
             if t.get("status") in ("ready", "running")
             and "Importé depuis" not in (t.get("body") or "")]
    for t in rogue:
        log(f"  ⚠️ CARTE HORS PONT: {t['id']} '{(t.get('title') or '')[:60]}' "
            f"(status={t.get('status')}) — non issue du cycle issue→drill→go. "
            f"Examiner: hermes kanban --board {KANBAN_BOARD} show {t['id']}")


def pull() -> None:
    issues = list_open_issues()
    # Le label 'triage' protège une issue en cours de drill par le bot
    # Discord gh-triage : elle ne doit PAS être importée en carte sans "go".
    # De plus, une issue récente (< 10 min) reste au bot : il a la priorité
    # (thread + drill) ; le pont n'agit qu'en filet de sécurité si le bot
    # n'a rien fait après 10 minutes.
    import time as _t
    now = _t.time()
    fresh_bypass = []
    to_import = []
    for i in issues:
        labels = {l.get("name") for l in (i.get("labels") or [])}
        if MIRROR_LABEL in labels or TRIAGE_LABEL in labels:
            continue
        from datetime import datetime, timezone
        created_at = i.get("createdAt") or ""
        try:
            age_s = now - datetime.fromisoformat(
                created_at.replace("Z", "+00:00")).timestamp()
        except Exception:
            age_s = 1e9  # date illisible -> éligible immédiatement
        if age_s < BOT_GRACE_SECONDS:
            fresh_bypass.append(i["number"])
            continue
        to_import.append(i)
    log(f"pull: {len(issues)} issue(s) ouverte(s), {len(to_import)} à importer"
        + (f", {len(fresh_bypass)} laissée(s) au bot gh-triage" if fresh_bypass else ""))
    if to_import and not DRY_RUN:
        ensure_mirror_label()

    for issue in to_import:
        n = issue["number"]
        key = f"gh-issue-{n}"
        body = (issue.get("body") or "").strip() or "(corps vide)"
        title = issue["title"].strip()

        create_cmd = ["create", title,
                      "--body", f"{body}\n\n—\nImporté depuis {issue['url']}",
                      "--assignee", KANBAN_ASSIGNEE,
                      "--idempotency-key", key,
                      "--json"]
        log(f"  issue #{n} -> carte kanban (key={key})")
        if DRY_RUN:
            continue
        out = json.loads(kanban(*create_cmd))
        task_id = out.get("id")
        log(f"    carte créée/récupérée: {task_id}")

        # Marque l'issue comme miroir + renvoie vers la carte.
        gh("issue", "edit", str(n), "--repo", GH_REPO, "--add-label", MIRROR_LABEL)
        gh("issue", "comment", str(n), "--repo", GH_REPO,
           "--body", f"🔀 Importée dans le kanban Hermes (board `{KANBAN_BOARD}`) "
                     f"comme tâche `{task_id}` (idempotency-key `{key}`).\n"
                     f"La carte sera traitée par le profil `@{KANBAN_ASSIGNEE}`; "
                     f"cette issue sera fermée automatiquement quand la carte passe en `done`.")
        log(f"    issue #{n} labellisée '{MIRROR_LABEL}' + commentée")


# ---------------------------------------------------------------- push

def list_tasks() -> list[dict]:
    out = kanban("list", "--json")
    return json.loads(out) or []


def issue_number_of(task: dict) -> int | None:
    """Numéro d'issue GitHub lié à une carte.

    Le champ idempotency_key n'est pas exposé dans l'API JSON kanban :
    on déduit le numéro depuis l'URL d'import que le pull a ajoutée au
    body ('Importé depuis https://github.com/<repo>/issues/<n>').
    """
    m = re.search(r"github\.com/%s/issues/(\d+)" % re.escape(GH_REPO),
                  task.get("body") or "")
    return int(m.group(1)) if m else None


def push() -> None:
    tasks = list_tasks()
    done_bridge = []
    for t in tasks:
        if t.get("status") != "done":
            continue
        n = issue_number_of(t)
        if n is not None:
            t["_issue"] = n
            done_bridge.append(t)
    log(f"push: {len(tasks)} carte(s), {len(done_bridge)} carte(s) done issue(s) du pont")

    for t in done_bridge:
        n = t["_issue"]
        task_id = t["id"]

        # L'issue est-elle encore ouverte ?
        state = gh("issue", "view", str(n), "--repo", GH_REPO, "--json", "state")
        if json.loads(state)["state"] != "OPEN":
            log(f"  tâche {task_id} -> issue #{n} déjà fermée, skip")
            continue

        # Récupère le résumé du dernier run terminé (handoff du worker).
        summary = ""
        try:
            runs = json.loads(kanban("runs", task_id, "--json"))
            completed = [r for r in runs if r.get("outcome") == "completed"]
            if completed:
                summary = (completed[-1].get("summary") or "").strip()
        except Exception as e:  # runs --json indisponible ? on ferme quand même
            log(f"    (runs non lus: {e})")

        log(f"  tâche {task_id} -> fermeture issue #{n}")
        if DRY_RUN:
            continue
        body = (f"✅ Tâche kanban `{task_id}` terminée (board `{KANBAN_BOARD}`).\n\n"
                f"**Résumé du worker :**\n\n{summary or '(pas de résumé)'}")
        gh("issue", "close", str(n), "--repo", GH_REPO, "--comment", body)
        kanban("comment", task_id, f"Issue #{n} fermée sur GitHub (push du pont).",
               "--author", "gh-bridge")
        log(f"    issue #{n} fermée")


# ---------------------------------------------------------------- count
# Compteur de cartes actives (non-done) sur le board — alimente le badge
# du README. Le board est un SQLite local (single-host) sans endpoint
# public : le badge est donc un instantané, régénéré par cette commande.

def cmd_count() -> None:
    tasks = list_tasks()
    active = [t for t in tasks if t.get("status") != "done"]
    print(json.dumps({"total": len(tasks), "active": len(active)},
                     ensure_ascii=False))


# ---------------------------------------------------------------- stats
# Résumé de l'état du board + du miroir GitHub, pour un humain ou un bot.
# Format par défaut : texte lisible (c'est un "résumé"). `--json` pour la
# consommation machine (même philosophie que `count`/`new`).

def cmd_stats() -> None:
    tasks = list_tasks()
    by_status: dict[str, int] = {}
    for t in tasks:
        by_status[t.get("status") or "?"] = by_status.get(t.get("status") or "?", 0) + 1

    # Issues GitHub (toutes, pour le ratio importé/fermé).
    issues = json.loads(gh("issue", "list", "--repo", GH_REPO, "--state", "all",
                           "--json", "number,state,labels")) or []
    open_issues = [i for i in issues if i.get("state") == "OPEN"]
    closed_issues = [i for i in issues if i.get("state") == "CLOSED"]

    # Santé du pont : cartes done dont l'issue est encore ouverte (push en
    # attente) et issues ouvertes sans carte (pull en attente).
    done_pending_push = []
    for t in tasks:
        if t.get("status") != "done":
            continue
        n = issue_number_of(t)
        if n is not None and any(i["number"] == n and i.get("state") == "OPEN"
                                 for i in issues):
            done_pending_push.append((t["id"], n))

    imported_numbers = {issue_number_of(t) for t in tasks}
    open_pending_pull = [i["number"] for i in open_issues
                         if i["number"] not in imported_numbers]

    data = {
        "board": KANBAN_BOARD,
        "repo": GH_REPO,
        "cards": {"total": len(tasks), "by_status": by_status},
        "issues": {"total": len(issues),
                   "open": len(open_issues),
                   "closed": len(closed_issues)},
        "bridge": {
            "done_pending_push": [{"task": tid, "issue": n}
                                  for tid, n in done_pending_push],
            "open_pending_pull": open_pending_pull,
        },
    }

    if "--json" in sys.argv:
        print(json.dumps(data, ensure_ascii=False, indent=1))
        return

    status_line = ", ".join(f"{k}={v}" for k, v in sorted(by_status.items()))
    print(f"board {KANBAN_BOARD} — {len(tasks)} carte(s) [{status_line}]")
    print(f"repo  {GH_REPO} — {len(issues)} issue(s) "
          f"({len(open_issues)} ouverte(s), {len(closed_issues)} fermée(s))")
    if done_pending_push:
        print("push en attente (carte done, issue encore ouverte) :")
        for tid, n in done_pending_push:
            print(f"  - {tid} -> issue #{n}")
    if open_pending_pull:
        print("pull en attente (issue ouverte sans carte) : "
              + ", ".join(f"#{n}" for n in open_pending_pull))
    if not done_pending_push and not open_pending_pull:
        print("pont à jour : aucune action en attente")


# ---------------------------------------------------------------- new
# Sous-commande pour le bot gh-triage : liste les issues à driller.

def cmd_new() -> None:
    """Issues ouvertes sans label 'kanban' ni 'triage' — candidates au drill."""
    issues = list_open_issues()
    fresh = [i for i in issues
             if not issue_has_label(i, MIRROR_LABEL)
             and not issue_has_label(i, TRIAGE_LABEL)]
    print(json.dumps([{"number": i["number"], "title": i["title"],
                       "url": i["url"], "body": (i.get("body") or "")[:1500]}
                      for i in fresh], indent=1, ensure_ascii=False))


# ---------------------------------------------------------------- main

def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if action == "new":
        cmd_new()
        return
    if action == "count":
        cmd_count()
        return
    if action == "stats":
        cmd_stats()
        return
    if action not in ("pull", "push", "sync"):
        sys.exit(f"usage: {sys.argv[0]} pull|push|sync|new|count|stats")
    log(f"repo={GH_REPO} board={KANBAN_BOARD} assignee={KANBAN_ASSIGNEE}"
        + (" [DRY RUN]" if DRY_RUN else ""))
    try:
        if action in ("pull", "sync"):
            pull()
        if action in ("push", "sync"):
            push()
        if action == "sync":
            check_no_rogue_cards()
        log("terminé")
    finally:
        flush_logs()


if __name__ == "__main__":
    main()