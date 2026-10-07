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


def _marker() -> str:
    """Marqueur de déduplication du bloc Description (slice 5) — chargé du moteur.

    Délègue à `engine.DESCRIPTION_MARKER` ; lève si le moteur est indisponible
    (jamais de marqueur inventé : sans moteur, aucun bloc Description n'est écrit).
    """
    eng = _engine()
    if eng is None:
        raise RuntimeError("moteur indisponible — marqueur Description introuvable")
    return eng.DESCRIPTION_MARKER


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


# --- bloc Description épinglé (#19, slice 5) --------------------------------
# Le keeper est l'écrivain UNIQUE du bloc Description (arbitrage 2b) :
#   - jamais le champ `topic` (Discord le rejette en silence) ;
#   - jamais un second message Description (idempotence par marqueur) ;
#   - best-effort : un échec de lecture de source ne tue pas le tick.
# Les sources (issue_url, branch, pr_url) sont INJECTÉES par le test ; en
# production elles viennent de `gh issue view`, `slices.json`, `gh pr list`.

def build_description_for_card(card, *, issue_url=None, branch=None,
                                pr_url=None, log=None,
                                specs_reader=None, pr_reader=None,
                                issue_url_lookup=None):
    """Assemble les sources d'une carte puis compose le bloc Description.

    Retourne {"lines": [...], "log": [...]} ou None si aucune source ne se
    résout (jamais de bloc vide, jamais de placeholder).
    """
    log_list: list[str] = []
    # `log_list.append` est lié AVANT la boucle d'émission : la rappeler pendant
    # l'itération (`logger = log or log_list.append` puis `for entry in log_list:
    # logger(entry)`) rallonge la liste qu'on parcourt — boucle infinie qui mange
    # toute la RAM du cgroup (mesuré : OOM-kill à 4 GiB après 45 s). Toute la
    # journalisation passe donc par un helper qui itère sur un INSTANTANÉ.
    logger = log

    def _emit(entries):
        """Émet `entries` sans journaliser l'émission elle-même.

        Le collecteur par défaut est `log_list` : y écrire depuis la boucle
        d'émission est le défaut corrigé ici.
        """
        for entry in entries:
            if logger is not None:
                logger(entry)

    # Résolution de l'URL de l'issue (ancre).
    if issue_url is None:
        issue_url = _issue_url_from_card(card, issue_url_lookup, log_list)
    # Résolution de la branche.
    if branch is None:
        branch = _resolve_branch(card, specs_reader, log_list)
    # Résolution de l'URL de la PR.
    if pr_url is None:
        pr_url = _resolve_pr_url(branch, pr_reader, log_list)

    # Si aucune source ne se résout : aucun bloc (jamais de placeholder).
    if not issue_url and not branch and not pr_url:
        _emit(list(log_list))          # instantané : rien ne peut s'y ajouter
        return None

    lines = []
    lines.append(_marker())
    if issue_url:
        lines.append(f"**Issue** : {issue_url}")
    if branch:
        lines.append(f"**Branche** : `{branch}`")
    if pr_url:
        lines.append(f"**PR** : {pr_url}")

    # Journalisation bruyante des sources absentes.
    if not issue_url:
        log_list.append("issue: non resolue — issue_url absent")
    if not branch:
        log_list.append("branche: non resolue — specs/<n>/slices.json absent ou cle 'branch' absente")
    if not pr_url:
        log_list.append("PR: non resolue — aucune PR ouverte pour cette branche")

    _emit(list(log_list))

    return {"lines": lines, "log": list(log_list)}


def _issue_url_from_card(card, issue_url_lookup, log_list: list[str]):
    """Déduit l'URL d'issue du body de la carte ou via issue_url_lookup."""
    # Ancre « Importé depuis …/issues/N »
    body = str((card or {}).get("body") or "")
    m = re.search(r"github\.com/[^/\s]+/[^/\s]+/issues/(\d+)", body)
    if m:
        return f"https://github.com/{_gh_repo()}/issues/{m.group(1)}"
    # Repli : champ issue_number + lookup
    n = _issue_number_of(card)
    if n is not None and issue_url_lookup:
        try:
            url = issue_url_lookup(n)
            if url:
                return url
            log_list.append(f"issue: lookup a renvoyé None pour n={n}")
        except Exception as e:
            log_list.append(f"issue: lookup a levé {e.__class__.__name__}: {e}")
    return None


def _gh_repo() -> str:
    return (os.environ.get("GH_REPO") or "").rsplit("/", 1)[-1] or "hermes-workflow"


def _resolve_branch(card, specs_reader, log_list: list[str]):
    """Lecteur de specs/<n>/slices.json (clé 'branch') — injecté."""
    n = _issue_number_of(card)
    if n is None:
        log_list.append("branche: non resolue — numero d'issue introuvable dans la carte")
        return None
    if specs_reader is None:
        log_list.append("branche: non resolue — specs_reader absent")
        return None
    try:
        data = specs_reader(n)
    except Exception as e:
        log_list.append(f"branche: erreur specs_reader {e.__class__.__name__}: {e}")
        return None
    if isinstance(data, dict):
        return data.get("branch") or None
    return None


def _resolve_pr_url(branch, pr_reader, log_list: list[str]):
    """Lecteur de `gh pr list --head <branche> --json url` — injecté."""
    if not branch:
        log_list.append("PR: non resolue — aucune branche pour chercher la PR")
        return None
    if pr_reader is None:
        log_list.append("PR: non resolue — pr_reader absent")
        return None
    try:
        result = pr_reader(branch)
    except Exception as e:
        log_list.append(f"PR: erreur pr_reader (gh) {e.__class__.__name__}: {e}")
        return None
    return result or None


def sync_description(cards, *, fetch_messages, write_message, log=None):
    """Écrivain du bloc Description (best-effort, NE LÈVE JAMAIS).

    Pour chaque carte :
      1. résout le fil Discord via `thread_lookup` (injectable) ;
      2. compose le bloc via `build_description_for_card` ;
      3. si le fil porte déjà le marqueur `[description]` → ÉDITE le message ;
      4. sinon → POSTE un nouveau message et l'ÉPINGLE ;
      5. retourne un verdict par carte :
         {"card_id", "thread_id", "action": "post"|"edit", "ok": bool, "pinned": bool}
    Une carte sans fil résolu est omise (verdict thread_id=None, ok=None).
    """
    log = log or print
    verdicts = []
    for card in cards:
        card_id = card.get("id", "?")
        issue_n = _issue_number_of(card)
        thread_id = None
        if issue_n is not None:
            try:
                thread_id = thread_lookup(issue_n)
            except Exception:
                thread_id = None
        if not thread_id:
            verdicts.append({"card_id": card_id, "thread_id": None,
                             "action": None, "ok": None, "pinned": None})
            continue

        # Compose le bloc (best-effort).
        try:
            built = build_description_for_card(card, log=log)
        except Exception as e:
            log(f"description: erreur build_description_for_card {card_id}: {e}")
            verdicts.append({"card_id": card_id, "thread_id": thread_id,
                             "action": None, "ok": False, "pinned": False})
            continue
        if built is None:
            verdicts.append({"card_id": card_id, "thread_id": thread_id,
                             "action": None, "ok": None, "pinned": None})
            continue
        content = "\n".join(built["lines"])

        # Lit les messages du fil pour trouver le marqueur.
        try:
            msgs = fetch_messages(thread_id) or []
        except Exception as e:
            log(f"description: erreur fetch_messages {card_id}: {e}")
            verdicts.append({"card_id": card_id, "thread_id": thread_id,
                             "action": "post", "ok": False, "pinned": False})
            continue
        existing = next(
            (m for m in msgs if _marker() in (m.get("content") or "")),
            None,
        )
        action = "edit" if existing else "post"
        edit_id = existing["id"] if existing else None
        pinned = False
        try:
            res = write_message(thread_id, content, edit_id=edit_id)
        except Exception as e:
            log(f"description: erreur write_message {card_id}: {e}")
            res = {"ok": False, "id": None}
        ok = res.get("ok") is True
        # Épingler (best-effort, le helper discord_thread.py gère la pin).
        if ok:
            try:
                msg_id = res.get("id") or (existing and existing["id"])
                if msg_id:
                    _discord_pin(thread_id, msg_id)
                    pinned = True
            except Exception as e:
                log(f"description: pin échoué {card_id}: {e}")
                pinned = False
        verdicts.append({"card_id": card_id, "thread_id": thread_id,
                         "action": action, "ok": ok, "pinned": pinned})
    return verdicts


def _discord_pin(thread_id, message_id):
    """Épingle un message dans un thread via le helper Discord (best-effort)."""
    r = subprocess.run(
        [sys.executable, str(DISCORD_HELPER), "pin",
         str(thread_id), str(message_id)],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(f"pin {message_id}: {r.stderr.strip()[:200]}")
    return r.stdout.strip()


def thread_lookup(issue_number):
    """Résolveur de fil Discord pour un numéro d'issue (injectable en test).

    En production, délègue à `engine.resolve_thread` si disponible.
    """
    eng = _engine()
    if eng is not None and hasattr(eng, "resolve_thread"):
        try:
            return eng.resolve_thread(int(issue_number))
        except Exception:
            return None
    return None


def sync_all_descriptions(cards, *, fetch_messages, write_message, log=None,
                          specs_reader=None, pr_reader=None,
                          issue_url_lookup=None):
    """Câble `build_description_for_card` + `sync_description` — best-effort.

    NE LÈVE JAMAIS : un lecteur de source qui lève est capturé et tracé ;
    le tick suivant continue. Retour : liste de verdicts (une par carte).
    """
    log = log or print
    verdicts = []
    for card in cards:
        card_id = card.get("id", "?")
        thread_id = None
        try:
            issue_n = _issue_number_of(card)
            if issue_n is not None:
                thread_id = thread_lookup(issue_n)
        except Exception as e:
            log(f"desc-all: erreur resolution fil {card_id}: {e}")
        if not thread_id:
            verdicts.append({"card_id": card_id, "thread_id": None,
                             "action": None, "ok": None, "pinned": None})
            continue
        # Build le bloc pour cette carte.
        try:
            built = build_description_for_card(
                card,
                specs_reader=specs_reader,
                pr_reader=pr_reader,
                issue_url_lookup=issue_url_lookup,
                log=log,
            )
        except Exception as e:
            log(f"desc-all: erreur build {card_id}: {e}")
            verdicts.append({"card_id": card_id, "thread_id": thread_id,
                             "action": None, "ok": False, "pinned": False})
            continue
        if built is None:
            verdicts.append({"card_id": card_id, "thread_id": thread_id,
                             "action": None, "ok": None, "pinned": None})
            continue
        content = "\n".join(built["lines"])
        # Détection du marqueur pour post vs edit.
        try:
            msgs = fetch_messages(thread_id) or []
        except Exception as e:
            log(f"desc-all: erreur fetch {card_id}: {e}")
            verdicts.append({"card_id": card_id, "thread_id": thread_id,
                             "action": "post", "ok": False, "pinned": False})
            continue
        existing = next(
            (m for m in msgs if _marker() in (m.get("content") or "")),
            None,
        )
        action = "edit" if existing else "post"
        edit_id = existing["id"] if existing else None
        pinned = False
        try:
            res = write_message(thread_id, content, edit_id=edit_id)
        except Exception as e:
            log(f"desc-all: erreur write {card_id}: {e}")
            res = {"ok": False, "id": None}
        ok = res.get("ok") is True
        if ok:
            try:
                msg_id = res.get("id") or (existing and existing["id"])
                if msg_id:
                    _discord_pin(thread_id, msg_id)
                    pinned = True
            except Exception as e:
                log(f"desc-all: pin échoué {card_id}: {e}")
        verdicts.append({"card_id": card_id, "thread_id": thread_id,
                         "action": action, "ok": ok, "pinned": pinned})
    return verdicts


def _sync_board_descriptions(cards, dry=False):
    """Ajouté en fin de cycle keeper : écrit/actualise le bloc Description.

    Best-effort : ne conditionne aucune transition. Les sources réelles sont
    les adaptateurs de production (gh, slices.json). Un échec est loggé.
    """
    import time
    now = time.time()
    # Adaptateurs réels (best-effort).
    def _fetch_messages(tid):
        r = subprocess.run(
            [sys.executable, str(DISCORD_HELPER), "messages", str(tid)],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:200])
        import json as _json
        data = _json.loads(r.stdout)
        return data if isinstance(data, list) else []

    def _write_message(tid, content, *, edit_id=None):
        cmd = [sys.executable, str(DISCORD_HELPER), "upsert-desc", str(tid)]
        if edit_id:
            cmd += ["--edit-id", str(edit_id)]
        cmd.append(content)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {"ok": False, "id": None}
        return {"ok": True, "id": r.stdout.strip() or None}

    try:
        verdicts = sync_all_descriptions(
            cards,
            fetch_messages=_fetch_messages,
            write_message=_write_message,
            specs_reader=_prod_specs_reader,
            pr_reader=_prod_pr_reader,
            issue_url_lookup=_prod_issue_url_lookup,
            log=print,
        )
        for v in verdicts:
            if v.get("action") not in (None, "skip"):
                log(f"desc {v.get('card_id')} [{v.get('action')}] "
                    f"ok={v.get('ok')} pinned={v.get('pinned')}")
    except Exception as e:
        log(f"ERREUR desc: {e}")


def _prod_specs_reader(issue_number):
    """Lecteur de specs/<n>/slices.json (production, best-effort)."""
    import json as _json
    p = WORKFLOW_ROOT / "specs" / str(issue_number) / "slices.json"
    if not p.is_file():
        raise FileNotFoundError(f"specs/{issue_number}/slices.json introuvable")
    return _json.loads(p.read_text())


def _prod_pr_reader(branch):
    """`gh pr list --head <branche> --json url` (production, best-effort)."""
    import json as _json
    repo = os.environ.get("GH_REPO", "")
    if not repo:
        return None
    r = subprocess.run(
        [GH_BIN if (GH_BIN := os.environ.get("GH_BIN", "/usr/bin/gh")) else "/usr/bin/gh",
         "pr", "list", "--repo", repo, "--head", branch, "--json", "url"],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(f"gh pr list: {r.stderr.strip()[:200]}")
    data = _json.loads(r.stdout or "[]")
    return data[0]["url"] if data else None


def _prod_issue_url_lookup(issue_number):
    """`gh issue view N --json url` (production, best-effort)."""
    import json as _json
    repo = os.environ.get("GH_REPO", "")
    if not repo:
        return None
    r = subprocess.run(
        ["/usr/bin/gh", "issue", "view", str(issue_number),
         "--repo", repo, "--json", "url"],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        return None
    data = _json.loads(r.stdout or "{}")
    return data.get("url")


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
