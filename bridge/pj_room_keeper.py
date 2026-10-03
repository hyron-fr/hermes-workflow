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

# Racine du dépôt : résolue depuis ce fichier (aucun chemin absolu).
WORKFLOW_ROOT = Path(__file__).resolve().parents[1]

BOARD = os.environ.get("PJ_BOARD", "")
HERMES_BIN = os.environ.get("PJ_HERMES_BIN") or os.path.expanduser("~/.local/bin/hermes")
ROOM_PY = os.environ.get("PJ_ROOM_PY") or str(WORKFLOW_ROOT / "pipeline" / "pj_room.py")
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


# --- écrivain UNIQUE du titre du fil (#19, slice 4) ------------------------
# Le keeper devient le PORTEUR de l'écriture du nom : il lit l'état de la carte,
# compose le titre arbitré (formateur pur de la slice 3) et renomme AU PLUS une
# fois par fil et par fenêtre — Discord plafonne les `PATCH name` (la 3ᵉ rend
# 429, `retry_after` ≈ 600 s). Le renommage est AJOUTÉ après le traitement des
# rooms et reste best-effort : il ne conditionne aucune transition de carte.
STATES = ("startup", "in_progress", "blocked", "done")
TITLE_PRIORITY = ("blocked", "done", "in_progress", "startup")   # index 0 = max
TITLE_WINDOW = 600      # secondes : au plus un renommage par fil et par fenêtre
HUMAN_WAIT_KINDS = ("needs_input", "capability")
_STATE_BY_STATUS = {
    "todo": "startup",
    "running": "in_progress",
    "ready": "in_progress",
    "blocked": "blocked",
    "done": "done",
    "archived": "done",
}
DISCORD_HELPER = Path(os.environ.get("PJ_DISCORD_HELPER")
                      or (Path.home() / ".hermes" / "scripts" / "discord_thread.py"))
_ENGINE_DONE = False
_ENGINE_MOD = None


def _engine():
    """Charge `pipeline/engine.py` (formateur + lecteur du nom) — SEULE source.

    Import PARESSEUX et défensif : le keeper tourne sur l'interpréteur du cron,
    qui peut ne pas porter les dépendances du moteur (`yaml`, `langgraph`).
    L'échec est bénin : sans moteur aucun titre n'est écrit (best-effort) et les
    rooms restent servies. `PJ_ENGINE_PY` permet de nommer la copie déployée.
    """
    global _ENGINE_DONE, _ENGINE_MOD
    if _ENGINE_DONE:
        return _ENGINE_MOD
    _ENGINE_DONE = True
    import importlib.util
    chemin = Path(os.environ.get("PJ_ENGINE_PY")
                  or (WORKFLOW_ROOT / "pipeline" / "engine.py"))
    try:
        if str(chemin.parent) not in sys.path:
            sys.path.insert(0, str(chemin.parent))
        spec = importlib.util.spec_from_file_location("pj_keeper_engine", str(chemin))
        if spec is None or spec.loader is None:
            raise ImportError(f"module illisible: {chemin}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _ENGINE_MOD = mod
    except Exception as e:
        log(f"titre: moteur indisponible ({e.__class__.__name__}: {e}) — aucun titre ecrit")
        _ENGINE_MOD = None
    return _ENGINE_MOD


def _compose_name(project, ticket, title, state):
    """Nom arbitré du fil (formateur de la slice 3), ou None s'il est inatteignable."""
    eng = _engine()
    if eng is None:
        return None
    try:
        return eng.format_title(project, ticket, title, state)
    except Exception:
        return None


def resolve_thread(issue_number):
    """Fil Discord d'une issue — délégué au LECTEUR unique (slice 2, `engine`).

    `None` = fil non résolu : la carte est OMISE, jamais renommée à l'aveugle.
    Sans moteur (dépendances absentes) ou sans `ISSUE_CHANNEL` configuré, le
    keeper ne devine pas : il ne renomme que les fils qu'il a identifiés.
    """
    eng = _engine()
    if eng is None or not getattr(eng, "resolve_thread", None):
        return None
    try:
        return eng.resolve_thread(int(issue_number))
    except Exception:
        return None


def _issue_number_of(card):
    """Numéro d'issue d'une carte : champ explicite, sinon ancre de la ligne d'import.

    `list --json` ne porte pas `issue_number` : la carte réelle l'écrit dans son
    body (`Importé depuis …/issues/N`). On n'accepte que l'ancre d'import, jamais
    le premier `/issues/N` venu (une carte en cite souvent d'autres).
    """
    n = (card or {}).get("issue_number")
    if n is not None:
        try:
            return int(n)
        except (TypeError, ValueError):
            pass
    body = str((card or {}).get("body") or "")
    m = re.search(r"(?m)^\s*Import[^\n]*?github\.com/[^/\s]+/[^/\s]+/issues/(\d+)", body)
    if m is None:
        m = re.search(r"github\.com/[^/\s]+/[^/\s]+/issues/(\d+)", body)
    return int(m.group(1)) if m else None


def _discord_rename(thread_id, name):
    """Adaptateur d'écriture RÉEL du nom (helper Discord). Jamais appelé par un banc.

    Best-effort : un refus de l'API est rendu comme verdict, jamais propagé.
    """
    try:
        r = subprocess.run([sys.executable, str(DISCORD_HELPER), "rename",
                            str(thread_id), str(name)],
                           capture_output=True, text=True, timeout=60)
    except Exception as e:
        return {"ok": False, "retry_after": None,
                "detail": f"{e.__class__.__name__}: {e}"}
    if r.returncode == 0:
        return {"ok": True}
    detail = f"{r.stdout or ''}{r.stderr or ''}".strip()
    m = re.search(r"retry_after\D{0,10}([0-9]+(?:\.[0-9]+)?)", detail)
    return {"ok": False, "retry_after": float(m.group(1)) if m else None,
            "detail": detail[:300] or f"exit {r.returncode}"}


def title_book_path(path=None):
    """Fichier d'état du keeper portant la fenêtre de coalescence (un par board)."""
    if path is not None:
        return Path(path)
    base = Path(os.environ.get("PJ_KEEPER_STATE_DIR")
                or (Path.home() / ".hermes" / "state"))
    return base / f"pj_room_keeper_{BOARD or 'board'}_titles.json"


def load_title_book(path=None):
    """Livre de coalescence relu du disque. {} si absent ou illisible — NE LÈVE JAMAIS."""
    try:
        data = json.loads(Path(title_book_path(path)).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_title_book(book, path=None):
    """Écrit le livre (JSON lisible) ; crée le répertoire parent au besoin."""
    p = title_book_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(book or {}, ensure_ascii=False, indent=1, sort_keys=True),
                 encoding="utf-8")


def card_title_state(card):
    """État arbitré d'une carte, ou None si le statut est hors nomenclature.

    Une attente HUMAINE (`block_kind` needs_input / capability) porte ⚠ quel que
    soit le statut ; `dependency` n'attend PAS l'humain (elle repart seule), elle
    ne doit donc pas produire d'⚠ abusif. Aucun état inventé : un statut inconnu
    ne produit aucun titre.
    """
    card = card or {}
    if str(card.get("block_kind") or "") in HUMAN_WAIT_KINDS:
        return "blocked"
    if str(card.get("status") or "") == "blocked":
        return "blocked"
    return _STATE_BY_STATUS.get(str(card.get("status") or ""))


def best_title_state(states):
    """État le plus prioritaire de `states` (⚠ > 🛑 > ⚙️ > 🎬) ; None si vide."""
    if not states:
        return None
    for state in TITLE_PRIORITY:
        if state in states:
            return state
    return None


def _verdict(thread_id, action, state, ok, retry_after, detail):
    return {"thread_id": thread_id, "action": action, "state": state,
            "ok": ok, "retry_after": retry_after, "detail": detail}


def _sync_one(thread_id, state, name, write, book, now, window, dry):
    """Un fil : au plus une écriture par fenêtre, best-effort. NE LÈVE JAMAIS."""
    if not name:
        # Un nom vide est OMIS — jamais un placeholder — et ne consomme pas la fenêtre.
        return _verdict(thread_id, "skip", state, None, None, None)
    entry = book.setdefault(thread_id, {})
    ts = entry.get("ts")
    try:
        ts_f = float(ts) if ts is not None else None
    except (TypeError, ValueError):
        ts_f = None
    if ts_f is not None and entry.get("state") == state:
        # Le nom est déjà en place : réécrire consommerait le quota de renommage.
        return _verdict(thread_id, "skip", state, None, None, None)
    if ts_f is not None and now < ts_f + window:
        # État différent DANS la fenêtre : on mémorise le plus prioritaire, on différe.
        entry["pending"] = best_title_state([entry.get("pending"), state]) or state
        return _verdict(thread_id, "defer", state, None, None, None)
    if dry:
        return _verdict(thread_id, "rename", state, None, None, None)
    try:
        res = write(thread_id, name) or {}
        ok = res.get("ok") is True
        retry_after = res.get("retry_after")
        detail = res.get("detail")
    except Exception as e:
        ok, retry_after, detail = False, None, f"{e.__class__.__name__}: {e}"
    if ok:
        entry["ts"] = float(now)
        entry["state"] = state
        entry.pop("pending", None)          # le report est soldé
        return _verdict(thread_id, "rename", state, True, retry_after, detail)
    # Un refus ne date PAS un succès (le quota n'est pas consommé) -> reprise au tick suivant.
    entry["state"] = state
    entry.setdefault("failures", []).append(
        {"ts": float(now), "state": state, "retry_after": retry_after,
         "detail": str(detail or "")[:300]})
    return _verdict(thread_id, "rename", state, False, retry_after, detail)


def sync_titles(tickets, write, book, now, dry=False, window=TITLE_WINDOW):
    """Synchronise les titres : au plus UN renommage par fil et par fenêtre.

    `tickets` = [{"thread_id", "state", "name"}] ; `write` = adaptateur INJECTÉ
    `write(thread_id, name) -> dict` (succès ssi `ok is True`) ; `book` = livre de
    coalescence MUTÉ en place ; retour = un verdict par ticket, dans l'ordre.
    Deux cartes d'un même fil ne produisent qu'UNE écriture (l'état le plus
    prioritaire gagne). NE LÈVE JAMAIS : un refus ou une exception est tracé.
    """
    tix = list(tickets or [])
    out = [None] * len(tix)
    groupes, index = [], {}
    for i, brut in enumerate(tix):
        t = brut or {}
        tid, state = t.get("thread_id"), t.get("state")
        if not tid or state not in STATES or not t.get("name"):
            out[i] = _verdict(tid, "skip", state, None, None, None)
            continue
        if tid not in index:
            index[tid] = len(groupes)
            groupes.append([tid, t, []])
        g = groupes[index[tid]]
        if best_title_state([g[1]["state"], state]) != g[1]["state"]:
            g[1] = t
        g[2].append(i)
    for tid, t, idxs in groupes:
        try:
            v = _sync_one(tid, t["state"], t["name"], write, book, now, window, dry)
        except Exception as e:
            v = _verdict(tid, "skip", t.get("state"), False, None,
                         f"{e.__class__.__name__}: {e}")
        for i in idxs:
            out[i] = dict(v)
    return out


def tickets_for_titles(cards, board=""):
    """Fils à renommer, un ticket par carte résolue : [{thread_id, state, name}].

    Une carte SANS fil résolu (`resolve_thread` -> None) ou SANS état arbitré est
    OMISE : jamais de renommage à l'aveugle, jamais de placeholder.
    """
    out = []
    for card in cards or []:
        n = _issue_number_of(card)
        if n is None:
            continue
        state = card_title_state(card)
        if state is None:
            continue
        tid = resolve_thread(n)
        if not tid:
            continue
        project = (str((card or {}).get("repo") or "")
                   or (os.environ.get("GH_REPO") or "").rsplit("/", 1)[-1]
                   or board or BOARD or "board")
        name = _compose_name(project, n, str((card or {}).get("title") or ""), state)
        if not name:
            continue
        out.append({"thread_id": str(tid), "state": state, "name": name})
    return out


def sync_all_titles(cards, write, book, now=None, dry=False):
    """Câble `tickets_for_titles` + `sync_titles` sur les cartes du board.

    Best-effort : NE LÈVE JAMAIS (un refus de l'API ne tue pas le tick). Un fil
    partagé par plusieurs cartes ne reçoit qu'UNE écriture, celle de l'état le
    plus prioritaire.
    """
    if now is None:
        import time
        now = time.time()
    try:
        tickets = tickets_for_titles(cards, board=BOARD)
    except Exception as e:
        log(f"titre: cartes illisibles ({e.__class__.__name__}: {e}) — aucun titre ecrit")
        return []
    par_fil, ordre = {}, []
    for t in tickets:
        tid = t["thread_id"]
        if tid not in par_fil:
            par_fil[tid] = t
            ordre.append(tid)
        elif best_title_state([par_fil[tid]["state"], t["state"]]) != par_fil[tid]["state"]:
            par_fil[tid] = t
    return sync_titles([par_fil[k] for k in ordre], write, book, now, dry=dry)


def _sync_board_titles(cards, dry=False):
    """Renommage des titres — AJOUTÉ après le traitement des rooms, best-effort.

    Appelé en fin de cycle uniquement : aucune transition de room ou de carte n'en
    dépend (garde-fou de la slice 4). Le livre est persisté dans le fichier d'état
    du keeper : la fenêtre survit à un tick muet et à un redémarrage.
    """
    try:
        book = load_title_book()
        verdicts = sync_all_titles(cards, _discord_rename, book, dry=dry)
        if verdicts and not dry:
            save_title_book(book)
        for v in verdicts:
            if v.get("action") != "skip":
                log(f"titre {v.get('thread_id')} [{v.get('state')}] -> {v.get('action')}"
                    f"{' (refus)' if v.get('ok') is False else ''}")
    except Exception as e:
        log(f"ERREUR titre: {e}")


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
            card = show.get("task") or show
            rid = room_from_body(card.get("body") or "")
            if rid:
                serve_card(rid, a.task, a.dry_run)
            # Renommage AJOUTÉ après le traitement de la room : il ne conditionne
            # aucune transition (garde-fou slice 4).
            _sync_board_titles([card], a.dry_run)
            return 0
        cards = json.loads(sh("list", "--json")) or []
        served = 0
        for rid, tid in rooms_to_serve(cards):
            try:
                if serve_card(rid, tid, a.dry_run) is not None:
                    served += 1
            except Exception as e:
                log(f"ERREUR {tid} ({rid}): {e}")
        # Renommage AJOUTÉ en fin de cycle, après le traitement des rooms.
        _sync_board_titles(cards, a.dry_run)
        if not served and a.dry_run:
            log("tick muet (aucune room à servir)")
        return 0
    except Exception as e:
        log(f"ERREUR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
