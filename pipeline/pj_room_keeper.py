#!/usr/bin/env python3
"""pj_room_keeper — pj-master gère les rooms Bot Mode de bout en bout.

Cycle de vie, piloté par l'ÉTAT (déterministe, 0 LLM) :

    ensure (création) → ask (animation) → report (transcript → comment) → disband

Le keeper boucle sur les cartes du board qui portent le marqueur `ROOM: <room_id>`
dans leur body. Ce marqueur EST le lien room↔ticket : le board reste la source de
vérité, la room n'est qu'un canal de délibération.

Règles de sûreté :
  - on n'anime (ask) que si la room est vide ET la carte active ;
  - on ne reporte qu'UNE fois (marqueur `[room-report]` dans les commentaires) ;
  - on ne dissout JAMAIS une room dont la délibération n'a pas été reportée.

Usage :
  pj_room_keeper.py                    # tick complet (cron)
  pj_room_keeper.py --task <id>        # une carte précise
  pj_room_keeper.py --dry-run          # n'écrit rien
Env : PJ_BOARD (obligatoire), PJ_HERMES_BIN, PJ_ROOM_PY.
exit 0 = tick réussi (même sans action) ; 1 = erreur de configuration.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BOARD = os.environ.get("PJ_BOARD", "")
HERMES_BIN = os.environ.get("PJ_HERMES_BIN") or os.path.expanduser("~/.local/bin/hermes")
ROOM_PY = os.environ.get("PJ_ROOM_PY") or str(Path.home() / ".hermes" / "scripts" / "pj_room.py")
ROOM_MARKER = "ROOM:"
REPORT_MARKER = "[room-report]"
LIVELOCK_MARKER = "[room-livelock]"
LIVELOCK_THRESHOLD = 2  # doit rester aligné sur pj_room.LIVELOCK_THRESHOLD
# Un membre du roster (pour les mentions du message d'animation).
DEFAULT_MEMBERS = ("pj-doc", "pj-test", "pj-dev")


def log(msg: str) -> None:
    print(f"[pj-room-keeper] {msg}", flush=True)


def sh(*args: str) -> str:
    r = subprocess.run([HERMES_BIN, "kanban", "--board", BOARD, *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"kanban {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r.stdout


def room_marker(room_id: str) -> str:
    return f"{ROOM_MARKER} {room_id}"


def with_room_marker(body: str, room_id: str) -> str:
    """Ajoute le marqueur s'il est absent (idempotent : jamais de doublon)."""
    body = body or ""
    if room_from_body(body):
        return body
    return f"{body.rstrip()}\n\n{room_marker(room_id)}\n"


def room_from_body(body: str):
    """Extrait le room_id du marqueur `ROOM: ...`, où qu'il soit dans le body.

    Le marqueur peut être en fin de ligne ou noyé dans une ligne de texte : on
    cherche le motif n'importe où, pas seulement sur une ligne isolée.
    """
    m = re.search(r"ROOM:\s*(\S+)", body or "")
    if not m:
        return None
    rid = m.group(1).strip().strip("`")
    return rid or None


def is_reported(comments) -> bool:
    return any(REPORT_MARKER in (c.get("body") or "") for c in (comments or []))


def is_disbanded_error(msg: str) -> bool:
    """Vrai si l'erreur signifie « room_id retiré » (donc NON recréable).

    `create_room` refuse un id déjà dissous (`_is_retired` -> RoomConflictError) :
    c'est délibéré côté moteur — un id dissous ne doit jamais reprendre un
    historique. Le keeper doit donc ignorer cette room, pas réessayer en boucle.
    """
    m = str(msg or "").lower()
    return "disbanded room" in m or "retir" in m


def rooms_to_serve(cards):
    """[(room_id, task_id)] pour les cartes portant un marqueur ROOM exploitable."""
    out = []
    for card in cards or []:
        rid = room_from_body(card.get("body") or "")
        if rid and parse_room(rid):
            out.append((rid, card["id"]))
    return out


def parse_room(rid: str):
    m = re.fullmatch(r"pj-(.+)-issue-(\d+)", str(rid or ""))
    return (m.group(1), int(m.group(2))) if m else None


def decide(room_state: str, card_status: str, reported: bool):
    """Action à mener. None = rien à faire (tick muet).

    Toute la logique de sûreté est ici, testable sans base ni réseau.
    """
    finished = card_status in ("done", "archived")
    # GARDE-FOU ANTI-LIVELOCK : une room bloquée (defer en série, aucun progrès)
    # est coupée immédiatement — sinon la carte reste `running` indéfiniment et
    # aucune délibération ne rend la main. Prioritaire sur tout le reste.
    if room_state == "livelock":
        return "unblock"
    if room_state == "empty":
        # Room jamais animée : rien à préserver. Si la carte est finie (ex. room
        # créée après coup sur un ticket déjà clos), on libère le slot ; sinon on
        # n'anime que si la carte travaille.
        if finished:
            return "disband"
        return "ask" if card_status in ("running", "ready") else None
    if room_state == "pending":
        return None                      # délibération en cours : attendre
    if not reported:
        return "report"                  # terminée mais pas reportée : reporter d'abord
    return "disband" if finished else None


def run_room(repo: str, issue: int, action: str, text: str = "", members=()):
    args = [sys.executable, ROOM_PY, "--repo", repo, "--issue", str(issue), "--action", action]
    if text:
        args += ["--text", text]
    if members:
        args += ["--members", ",".join(members)]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"pj_room {action}: {(r.stdout or r.stderr).strip()[:300]}")
    out = json.loads(r.stdout)
    if out.get("status") == "error":
        raise RuntimeError(f"pj_room {action}: {out.get('detail')}")
    return out


def serve_card(room_id: str, task_id: str, dry: bool) -> str | None:
    """Déroule le cycle pour une carte. Retourne l'action menée, ou None."""
    parsed = parse_room(room_id)
    if not parsed:
        return None
    repo, issue = parsed
    show = json.loads(sh("show", task_id, "--json"))
    task = show.get("task") or show
    st = run_room(repo, issue, "status")
    if st.get("status") == "absent":
        if dry:
            log(f"{task_id}: room absente (dry-run)")
            return "ensure"
        try:
            run_room(repo, issue, "ensure")
        except RuntimeError as e:
            # Un room_id dissous est RETIRÉ DÉFINITIVEMENT (hosted_room_retired_ids) :
            # impossible de recréer la même room. On ne rejoue pas la délibération.
            if is_disbanded_error(str(e)):
                log(f"{task_id} [{room_id}]: room dissoute (id retiré, non recréable) — ignorée")
                return None
            raise
        st = run_room(repo, issue, "status")
    action = decide(room_state=st.get("state", "empty"),
                    card_status=str(task.get("status") or ""),
                    reported=is_reported(show.get("comments")))
    if action is None:
        return None
    if dry:
        log(f"{task_id} [{room_id}] -> {action} (dry-run)")
        return action

    if action == "ask":
        import importlib.util
        spec = importlib.util.spec_from_file_location("pj_room", ROOM_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        run_room(repo, issue, "ask", text=mod.build_ask_text(repo, issue, DEFAULT_MEMBERS),
                 members=DEFAULT_MEMBERS)
    elif action == "unblock":
        # Garde-fou : coupe la délibération bloquée (fence room.stop_requested).
        # Trace sur la carte — un arrêt automatique doit rester auditable.
        stopped = run_room(repo, issue, "stop")
        sh("comment", task_id, "\n".join([
            "[room-livelock] Délibération bloquée — arrêt automatique déclenché.",
            "",
            f"- Room : `{room_id}`",
            f"- Defer consécutifs en fin de journal : **{st.get('trailing_defers')}** "
            f"(seuil {LIVELOCK_THRESHOLD})",
            f"- Membres bloqués : {', '.join(st.get('stalled_members') or []) or '—'}",
            f"- Cause : contention multi-gateway sur le lease de la room "
            f"(`member_unavailable`)",
            "",
            "La délibération déjà produite reste dans le journal de la room et sera "
            "reportée au tick suivant. La carte n'est plus bloquée par cette room.",
        ]))
        log(f"{task_id} [{room_id}] LIVELOCK détecté "
            f"({st.get('trailing_defers')} defers) -> stop ({stopped.get('status')})")
        return "unblock"
    elif action == "report":
        tr = run_room(repo, issue, "transcript")
        lines = [f"{REPORT_MARKER} Room `{room_id}` — {tr.get('count', 0)} message(s).",
                 "", "## Délibération", ""]
        for m in tr.get("messages") or []:
            lines += [f"**@{m.get('from')}**", "", (m.get("text") or "").strip(), ""]
        sh("comment", task_id, "\n".join(lines))
    elif action == "disband":
        run_room(repo, issue, "disband")
    log(f"{task_id} [{room_id}] -> {action}")
    return action


def main() -> int:
    ap = argparse.ArgumentParser(prog="pj_room_keeper.py")
    ap.add_argument("--task", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not BOARD:
        log("PJ_BOARD manquant")
        return 1
    try:
        if a.task:
            show = json.loads(sh("show", a.task, "--json"))
            rid = room_from_body((show.get("task") or show).get("body") or "")
            if rid:
                serve_card(rid, a.task, a.dry_run)
            return 0
        cards = json.loads(sh("list", "--json")) or []
        served = 0
        for rid, tid in rooms_to_serve(cards):
            try:
                if serve_card(rid, tid, a.dry_run) is not None:
                    served += 1
            except Exception as e:
                log(f"ERREUR {tid} ({rid}): {e}")
        if not served and a.dry_run:
            log("tick muet (aucune room à servir)")
        return 0
    except Exception as e:
        log(f"ERREUR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
