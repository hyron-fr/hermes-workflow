#!/usr/bin/env python3
"""Escalade déterministe des blocages de cartes vers le thread Discord de l'issue.

PROBLÈME MESURÉ (2026-09-20) : une carte `blocked` de production (pj-dev/pj-doc/
pj-test) n'est remontée à AUCUN humain. Le gateway possède bien un notifier qui
traite `blocked`+`needs_input` comme un événement de réveil
(gateway/kanban_watchers_notifier.py, _WAKE_KINDS), mais il ne délivre QUE les
tâches présentes dans `kanban_notify_subs` — table vide sur tous les boards, car
`hermes kanban create` ne s'auto-abonne que depuis une session gateway, jamais
depuis un script/cron (or c'est un cron qui crée toutes les cartes du pipeline).
Résultat : 5 cartes bloquées, 0 message dans le thread. Les workers de production
n'ont d'ailleurs AUCUN outil Discord (toolset kanban/file/terminal/web/skills/
memory) : ils ne peuvent pas poster même s'ils le voulaient.

CORRECTIF (hors core — le core ~/.hermes/hermes-agent est un checkout upstream,
un patch y serait écrasé par `hermes update`) : ce keeper déterministe (0 LLM)
scanne les cartes qui attendent une décision humaine et poste UN message dans le
thread de l'issue, dédupliqué par (task_id, dernier event de blocage).

Pourquoi pas le notifier natif ? Il délivre TOUS les kinds terminaux
(`completed` incluse) : sur un graphe de 56 cartes cela noierait le thread sous
~56 messages « done », ce que l'humain a explicitement refusé (« ne pas
emboliser ce canal »). Ici : seules les cartes qui ATTENDENT une décision.

CONFIGURATION — tout vient de l'environnement, aucune valeur n'est codée ici
(tableau complet dans `pipeline/README.md`, §« Outil d'escalade ») :

  REQUISES      PJ_ESCALATE_CHANNEL_ID, PJ_ESCALATE_USER_ID, PJ_ESCALATE_GUILD_ID
  OPTIONNELLES  PJ_ESCALATE_REPOS_ROOT, PJ_ESCALATE_STATE_DIR, PJ_ESCALATE_THREAD_HELPER
                (défauts dérivés du répertoire personnel), PJ_ESCALATE_ORG
                (défaut `hyron-fr`).

Une requise ABSENTE **ou VIDE** arrête le tick bruyamment : `ConfigError`, message
sur la sortie d'erreur nommant la variable, code de sortie 2, aucun envoi, aucune
écriture d'état. Jamais de repli silencieux — une valeur vide n'est jamais un
identifiant (mesuré : `target=""` fait échouer le post, l'état n'avance pas, et le
même message est reposté toutes les 3 minutes, indéfiniment).

Les entrées-sorties (kanban SQLite, `gh`, Discord, fichiers d'état) passent par
des points d'injection (`runner`, `poster`, `conn_factory`), défaut = implémentation
réelle : le tick complet est exerçable sans réseau ni Discord.

Usage :
  pj_escalate.py [--board B] [--dry-run] [--verbose]
  PJ_BOARD=B pj_escalate.py            # un seul board
  pj_escalate.py                       # tous les boards pj-*
"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Racine des boards kanban : constante module-level. Surchargée par `monkeypatch`
# dans les tests (`m.KANBAN_ROOT = Path(tmp)`) — demander une variable
# d'environnement pour ce que le monkeypatch fait proprement serait de la surface
# d'API gratuite.
KANBAN_ROOT = Path.home() / ".hermes" / "kanban" / "boards"

# Convention de nommage des boards du pipeline : FIGÉE. Un préfixe paramétrable
# serait une variable sans emploi — « quels boards » se règle par `--board` ou par
# `PJ_BOARD`, qui existent déjà.
BOARD_PREFIX = "pj-"

# Organisation GitHub des dépôts du pipeline : OPTIONNELLE, défaut documenté
# (même patron que `GH_REPO` dans `gh_kanban_bridge.py`).
DEFAULT_ORG = "hyron-fr"

# Un blocage "à trancher" : l'humain (ou l'orchestrateur) doit décider quelque chose.
BLOCK_EVENT_KINDS = ("blocked", "block_loop_detected")
ESCALATABLE_STATUSES = ("blocked", "triage")
REASON_MAX = 700

# Contrat de configuration : présence ET non-vacuité. L'ordre fixe laquelle est
# nommée en premier quand plusieurs manquent.
REQUIRED_VARS = ("PJ_ESCALATE_CHANNEL_ID", "PJ_ESCALATE_USER_ID", "PJ_ESCALATE_GUILD_ID")

# Liste de convention : ces dépôts sont connus même quand la racine des repos
# n'est pas énumérable (elle est optionnelle). Elle décide ce que `resolve_issue`
# considère comme inconnu — d'où sa place dans ce fichier et non dans un défaut
# d'environnement.
KNOWN_REPO_NAMES = ("hermes-workflow", "kerios", "dino-game", "hermes-experiment")


class ConfigError(ValueError):
    """Refus explicite de configuration — `str(exc)` contient le nom de la variable.

    Distinct d'un `KeyError` : le message est destiné à l'humain qui lit la sortie
    d'erreur du cron, il nomme la variable fautive et il est émis SANS trace
    d'exception.
    """

    def __init__(self, variable: str, message: str) -> None:
        super().__init__(f"{message} : {variable}")
        self.variable = variable
        self.message = message


@dataclass(frozen=True)
class EscalationConfig:
    """Toute la configuration du tick, lue une fois dans l'environnement."""

    channel_id: str          # REQUIS — canal des threads d'issue (et cible de repli)
    user_id: str             # REQUIS — destinataire des décisions
    guild_id: str            # REQUIS — guilde Discord lue par le helper de threads
    repos_root: Path         # optionnel — racine des clones dev
    state_dir: Path          # optionnel — état de dédup, un fichier par board
    thread_helper: Path      # optionnel — chemin du helper `discord_thread.py`
    org: str                 # optionnel — organisation GitHub, défaut DEFAULT_ORG
    gh_bin: str = ""         # port `gh`, injectable : valeur résolue ou `""` (indisponible)


def _text(env, name: str) -> str:
    """Valeur nettoyée d'une variable : `None`, vide et blancs sont indiscernables."""
    return (env.get(name) or "").strip()


def escalation_config(env=None) -> EscalationConfig:
    """Construit la configuration depuis `env` (défaut : `os.environ`).

    Lit EXCLUSIVEMENT le mapping reçu : un appel avec un mapping explicite ne
    dépend donc pas de l'environnement du processus, et un `HOME` injecté déplace
    tous les défauts.
    """
    e = os.environ if env is None else env
    values = {}
    for name in REQUIRED_VARS:
        value = _text(e, name)
        if not value:
            raise ConfigError(name, "variable d'environnement requise absente ou vide")
        values[name] = value
    home = Path(_text(e, "HOME") or str(Path.home()))
    # `gh_bin` : le port est un CHAMP de configuration (injectable, testable) avant
    # d'être une variable d'environnement. `PJ_ESCALATE_GH_BIN` n'est consultée que
    # si le mapping la DÉFINIT — une valeur posée vide est donc un état légitime
    # (« garde indisponible »), distinct d'une absence de définition qui laisse la
    # résolution par candidats vérifiés faire son travail.
    gh_bin = e["PJ_ESCALATE_GH_BIN"] if "PJ_ESCALATE_GH_BIN" in e else GH_BIN
    return EscalationConfig(
        channel_id=values["PJ_ESCALATE_CHANNEL_ID"],
        user_id=values["PJ_ESCALATE_USER_ID"],
        guild_id=values["PJ_ESCALATE_GUILD_ID"],
        repos_root=Path(_text(e, "PJ_ESCALATE_REPOS_ROOT") or home / "pj-repos"),
        state_dir=Path(_text(e, "PJ_ESCALATE_STATE_DIR") or home / ".hermes" / "state"),
        thread_helper=Path(_text(e, "PJ_ESCALATE_THREAD_HELPER")
                           or home / ".hermes" / "scripts" / "discord_thread.py"),
        org=_text(e, "PJ_ESCALATE_ORG") or DEFAULT_ORG,
        gh_bin=str(gh_bin or ""),
    )


def validate_config(cfg: EscalationConfig) -> None:
    """Contrôle d'ÉCRITURE, une seule fois, avant tout scan de board.

    Un identifiant absent échoue déjà à la construction ; `STATE_DIR` non, lui :
    il échoue par board, DANS `save_state`, donc APRÈS que les boards A..D ont
    posté. Une sonde d'écriture (`mkdir` + fichier créé puis retiré) déplace
    l'échec au tout début du tick, quand rien n'a encore été posté.
    """
    try:
        cfg.state_dir.mkdir(parents=True, exist_ok=True)
        probe = cfg.state_dir / ".pj_escalate_write_probe"
        try:
            probe.write_text("")
        finally:
            probe.unlink()
    except OSError as exc:
        raise ConfigError("PJ_ESCALATE_STATE_DIR",
                          f"répertoire d'état non inscriptible ({exc.__class__.__name__})") from exc


def known_repos(cfg: EscalationConfig) -> list[str]:
    """Repos pj connus, du plus long au plus court (pour un match d'URL/key exact)."""
    repos = set()
    if cfg.repos_root.is_dir():
        for p in cfg.repos_root.iterdir():
            if p.is_dir():
                repos.add(p.name)
    repos.update(KNOWN_REPO_NAMES)
    return sorted(repos, key=len, reverse=True)


def resolve_issue(conn: sqlite3.Connection, task_id: str, repos: list[str],
                  board: str = "") -> tuple[str, int] | None:
    """(repo, issue) d'une carte, par idempotency_key puis par remontée des parents.

    Les clés du pipeline encodent `<prefixe>-…-<repo>-<issue>` (ex.
    `pj-dev-3-hermes-workflow-2`), mais certaines cartes (créées hors pipeline, par
    un worker après un blocage) n'ont ni clé ni lien : on remonte alors les parents
    jusqu'à une carte clée, puis jusqu'à une racine « Importé depuis …/issues/N ».
    Dernier recours : le repo déduit du nom du board (`pj-<repo>`) et un `#N`
    trouvé dans le titre/body — sans quoi l'escalade part dans le canal, signalée
    comme sans thread (jamais devinée en silence).
    """
    seen: set[str] = set()
    queue = [task_id]
    while queue:
        tid = queue.pop(0)
        if tid in seen:
            continue
        seen.add(tid)
        row = conn.execute(
            "SELECT idempotency_key, body, title FROM tasks WHERE id = ?", (tid,)
        ).fetchone()
        if row is None:
            continue
        key = row["idempotency_key"] or ""
        for repo in repos:
            m = re.search(re.escape(repo) + r"-(\d+)$", key)
            if m:
                return repo, int(m.group(1))
        body = row["body"] or ""
        m = re.search(r"github\.com/[A-Za-z0-9_.-]+/([A-Za-z0-9_.-]+)/issues/(\d+)", body)
        if m:
            return m.group(1), int(m.group(2))
        # la clé peut désigner le repo sans suffixe d'issue exploitable : on continue
        for repo in repos:
            if f"-{repo}-" in key:
                m2 = re.search(re.escape(repo) + r"-(\d+)", key)
                if m2:
                    return repo, int(m2.group(1))
        for r in conn.execute("SELECT parent_id FROM task_links WHERE child_id = ?", (tid,)):
            queue.append(r["parent_id"])
    # Repli : repo du board + numéro d'issue cité dans le titre/body de la carte.
    if board.startswith(BOARD_PREFIX):
        repo = board[len(BOARD_PREFIX):]
        if repo in repos:
            row = conn.execute("SELECT title, body FROM tasks WHERE id = ?", (task_id,)).fetchone()
            text = f"{row['title'] or ''}\n{row['body'] or ''}" if row else ""
            m = re.search(r"#(\d+)\b", text)
            if m:
                return repo, int(m.group(1))
    return None


def thread_index(cfg: EscalationConfig, *, runner=subprocess.run) -> dict[tuple[str, int], str]:
    """(repo, issue) -> thread_id, lu depuis les threads actifs du canal configuré."""
    out: dict[tuple[str, int], str] = {}
    try:
        r = runner(
            [sys.executable, str(cfg.thread_helper), "threads", cfg.channel_id, cfg.guild_id],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:
        print(f"[escalate] threads illisibles: {e}")
        return out
    if r.returncode != 0:
        print(f"[escalate] threads rc={r.returncode}: {r.stderr.strip()[:200]}")
        return out
    for line in r.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        tid, name = parts[0], parts[1]
        for repo in known_repos(cfg):
            m = re.match(re.escape(repo) + r"\s+#(\d+)\b", name)
            if m:
                out.setdefault((repo, int(m.group(1))), tid)
                break
    return out


def state_path(cfg: EscalationConfig, board: str) -> Path:
    """État de dédup PAR BOARD (un tick global ne doit pas republier un board déjà escaladé)."""
    return cfg.state_dir / f"pj_escalate_{board}.json"


def load_state(cfg: EscalationConfig, board: str) -> dict:
    try:
        return json.loads(state_path(cfg, board).read_text())
    except Exception:
        return {}


def save_state(cfg: EscalationConfig, board: str, state: dict) -> None:
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    state_path(cfg, board).write_text(json.dumps(state, indent=1, sort_keys=True))


def last_block_event(conn: sqlite3.Connection, task_id: str) -> tuple[int, str, str] | None:
    """(event_id, kind, reason) du dernier blocage d'une carte."""
    q = (
        "SELECT id, kind, payload FROM task_events WHERE task_id = ? AND kind IN ("
        + ",".join("?" * len(BLOCK_EVENT_KINDS))
        + ") ORDER BY id DESC LIMIT 1"
    )
    row = conn.execute(q, (task_id, *BLOCK_EVENT_KINDS)).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(row["payload"] or "{}")
    except Exception:
        payload = {}
    reason = str(payload.get("reason") or payload.get("summary") or "").strip()
    bkind = str(payload.get("kind") or row["kind"])
    return int(row["id"]), bkind, reason


def post(cfg: EscalationConfig, thread_id: str, message: str, *, runner=subprocess.run) -> bool:
    r = runner(
        [sys.executable, str(cfg.thread_helper), "send", thread_id, message],
        capture_output=True, text=True, timeout=60,
    )
    ok = r.returncode == 0 and "sent" in r.stdout
    if not ok:
        print(f"[escalate] envoi échoué rc={r.returncode}: {(r.stderr or r.stdout).strip()[:200]}")
    return ok


def build_message(cfg: EscalationConfig, board: str, task: dict, bkind: str, reason: str,
                  thread_id: str | None) -> str:
    head = "🔔 **Décision attendue**" if bkind in ("needs_input", "capability") else "🔔 **Blocage à trancher**"
    lines = [
        f"{head} — <@{cfg.user_id}>",
        f"`{task['id']}` · **{task['title']}** · `{task['assignee']}` · board `{board}`",
        f"Motif type `{bkind}` : {reason[:REASON_MAX]}" if reason else f"Motif type `{bkind}` (pas de raison détaillée)",
        f"↳ `hermes kanban --board {board} show {task['id']}`",
        "Le worker a écrit son constat sur la carte ; il attend un arbitrage humain pour repartir.",
    ]
    if thread_id is None:
        lines.insert(0, "_Pas de thread dédié trouvé pour ce ticket — escalade dans le canal._")
    msg = "\n".join(lines)
    return msg[:1990]


def _resolve_bin(name: str, *candidates: str) -> str:
    """Résout un exécutable : PATH puis emplacements connus.

    Ne JAMAIS se rabattre sur un chemin en dur — mais ne jamais supposer non plus
    que le PATH interactif est disponible : MESURÉ, le PATH d'un cron ne contient
    pas `~/.local/bin`, donc `subprocess.run(["gh", ...])` lève `FileNotFoundError`
    et un garde-fou qui l'ignore est INERTE EN PRODUCTION tout en paraissant actif
    en session interactive. C'est le pattern déjà appliqué par
    `gh_kanban_bridge._resolve_bin` (règle CONTRIBUTING : `shutil.which()` puis des
    candidats VÉRIFIÉS `isfile` + `X_OK`).

    Contrat de retour ÉPINGLÉ : **la chaîne vide** quand rien ne passe, jamais le
    nom nu. Le nom nu rend `GH_BIN` *truthy*, donc l'avertissement de
    `issue_is_closed` ne part pas, puis le `FileNotFoundError` est avalé par son
    `except Exception` — garde inerte ET muette. L'autre implémentation du dépôt
    (`gh_kanban_bridge._resolve_bin`) retourne le nom nu : c'est un contrat
    DIFFÉRENT, à ne pas importer ici.
    """
    found = shutil.which(name)
    if found:
        return found
    for c in candidates:
        p = os.path.expanduser(c)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return ""            # introuvable : l'appelant décide (jamais un chemin en dur)


GH_BIN = _resolve_bin("gh", "~/.local/bin/gh", "~/.hermes/bin/gh")


# --------------------------------------------------------------------------- garde ---
# États que `gh issue view --json state -q .state` peut rendre et qui sont DÉCIDABLES.
OPEN_STATE = "OPEN"
CLOSED_STATE = "CLOSED"
READABLE_STATES = (OPEN_STATE, CLOSED_STATE)

# TROIS chemins de doute (gh introuvable, rc != 0, exception) PLUS la sortie illisible :
# QUATRE avertissements DISTINCTS, un par chemin. `_warn_once` déduplique par message —
# réutiliser la même chaîne rendrait le deuxième chemin muet, et c'est précisément le
# défaut corrigé ici (mesuré sur la copie de production : `_warn_once` n'avait qu'UN seul
# appel, dans la branche `if not GH_BIN`, donc `rc != 0` et l'exception étaient muets).
WARN_GH_ABSENT = ("gh introuvable (PATH + candidats) — garde-fou d'état d'issue "
                  "INDISPONIBLE, escalade inchangée")
WARN_GH_RC = ("état d'issue illisible : gh issue view rc={rc} — état "
              "INDÉTERMINÉ, escalade inchangée")
WARN_GH_EXC = ("état d'issue illisible : gh issue view a levé {exc} — état "
               "INDÉTERMINÉ, escalade inchangée")
WARN_GH_UNREADABLE = ("état d'issue illisible : sortie {state!r} (ni OPEN ni CLOSED) — "
                      "état INDÉTERMINÉ, escalade inchangée")


def escalation_allowed(state: str) -> bool:
    """Décision PURE : l'état du ticket laisse-t-il partir l'escalade ?

    OPEN → `True`, `CLOSED` → `False`, **chaîne vide ou état inconnu → `True`** (un doute
    escalade : la garde ne doit jamais rendre une carte muette *par erreur*). Comparaison
    insensible à la casse et aux blancs de bord.

    Aucune entrée-sortie : ni réseau, ni sous-processus, ni système de fichiers — et
    **muette à dessein**. C'est ce qui rend la décision testable directement ; le chemin
    réseau vit dans `issue_is_closed`, qui l'appelle. L'avertissement de l'état
    INDÉTERMINÉ est émis par cette garde (l'appelante), seule à pouvoir nommer l'entité
    concernée — jamais par la décision elle-même.
    """
    return str(state or "").strip().upper() != CLOSED_STATE


def issue_is_closed(cfg: EscalationConfig, repo: str, issue: int, *,
                    runner=subprocess.run) -> bool:
    """True si le ticket est FERMÉ sur GitHub — la carte ne doit plus escalader.

    PROBLÈME MESURÉ (2026-09-20) : une carte `blocked` dont l'issue est CLOSE
    continuait d'être escaladée vers le thread de cette issue. Cas réel : le
    ticket #1 fermé par le pont le 19/09 à 23:40Z, puis DEUX cartes créées après
    (t_b8b63054 le 20/09 à 01:12, t_aae02fc8 le 20/09 à 07:53) ont été remontées
    dans SON thread — l'humain a reçu « Décision attendue » sur un ticket déjà
    terminé. Un ticket clos n'attend plus de décision : toute carte qui s'en
    réclame est soit orpheline, soit mal rattachée, et l'arbitrage appartient à
    l'orchestrateur (pj-master), pas à l'humain.

    TRI-ÉTAT rendu explicite : `OPEN` et `CLOSED` sont **muets** (l'un escalade, l'autre
    saute la carte comme traitée). Les chemins de doute — `gh` introuvable, `rc != 0`,
    exception du binaire, **sortie illisible** — avertissent **chacun nommément** sur la
    sortie standard et retournent `False` : on escalade, jamais muet par erreur. Une
    exception **ne se propage pas** (elle ferait tomber le tick entier, donc toutes les
    cartes suivantes).
    """
    if not cfg.gh_bin:
        _warn_once(WARN_GH_ABSENT)                # doute n° 1 — binaire indisponible
        return False
    try:
        r = runner(
            [cfg.gh_bin, "issue", "view", str(issue), "--repo", f"{cfg.org}/{repo}",
             "--json", "state", "-q", ".state"],
            capture_output=True, text=True, timeout=30,
        )
        rc, out = r.returncode, r.stdout
    except Exception as exc:                      # doute n° 2 — binaire non exécutable
        # Lecture du résultat DANS le `try` : un `runner` qui lève, qui rend un objet
        # inexploitable (`AttributeError` sur `returncode`) ou qui dépasse son délai
        # (`TimeoutExpired`) est un doute, pas une panne du tick — l'exception ne se
        # propage JAMAIS, sinon les cartes suivantes du même tick tombent avec elle.
        _warn_once(WARN_GH_EXC.format(exc=type(exc).__name__))
        return False
    if rc != 0:                                   # doute n° 3 — lecture refusée
        _warn_once(WARN_GH_RC.format(rc=rc))
        return False
    state = (out or "").strip().upper()
    if state not in READABLE_STATES:              # doute n° 4 — sortie illisible
        _warn_once(WARN_GH_UNREADABLE.format(state=state))
        return False
    return not escalation_allowed(state)


_WARNED: set[str] = set()


def _warn_once(msg: str) -> None:
    """Un avertissement par message et par tick : une garde inerte est VISIBLE, jamais muette.

    Dédup par **message** (set process-local, et le cron lance un process neuf à chaque
    tick). Conséquence pour les appelants : deux chemins de doute DIFFÉRENTS doivent
    passer deux chaînes DIFFÉRENTES, sinon le second est avalé — voir `WARN_GH_*`.
    """
    if msg in _WARNED:
        return
    _WARNED.add(msg)
    print(f"[escalate] ⚠️ {msg}")


def run(board: str, dry: bool = False, verbose: bool = False, *,
        cfg: EscalationConfig | None = None,
        runner=subprocess.run,
        poster=None,
        conn_factory=sqlite3.connect) -> dict:
    """Un tick complet sur un board.

    Points d'injection (défaut = implémentation réelle) : `runner` pour les
    sous-processus (`gh`, helper Discord), `poster` pour l'envoi, `conn_factory`
    pour la base kanban. Le tick est ainsi exerçable sans réseau, sans exécutable
    réel et sur une base de test.
    """
    if cfg is None:
        cfg = escalation_config()
    if poster is None:
        poster = lambda thread_id, message: post(cfg, thread_id, message, runner=runner)  # noqa: E731
    db = KANBAN_ROOT / board / "kanban.db"
    if not db.exists():
        return {"board": board, "skipped": "no db"}
    conn = conn_factory(db)
    conn.row_factory = sqlite3.Row
    repos = known_repos(cfg)
    threads = thread_index(cfg, runner=runner)
    state = {k: v for k, v in load_state(cfg, board).items() if k.startswith(board + ":")}
    stats = {"board": board, "escalated": [], "skipped": 0, "errors": []}

    statuses = ",".join("?" * len(ESCALATABLE_STATUSES))
    rows = conn.execute(
        f"SELECT id, title, assignee, status FROM tasks WHERE status IN ({statuses}) ORDER BY id",
        ESCALATABLE_STATUSES,
    ).fetchall()

    for task in rows:
        ev = last_block_event(conn, task["id"])
        if ev is None:
            stats["skipped"] += 1
            continue
        event_id, bkind, reason = ev
        key = f"{board}:{task['id']}"
        if int(state.get(key, 0)) >= event_id:
            stats["skipped"] += 1
            continue
        loc = resolve_issue(conn, task["id"], repos, board)
        thread_id = threads.get(loc) if loc else None
        # Un ticket CLOS n'attend plus aucune décision : on ne réveille pas
        # l'humain sur un sujet terminé (cf. issue_is_closed).
        if loc and issue_is_closed(cfg, loc[0], loc[1], runner=runner):
            stats.setdefault("closed_issue", []).append(
                {"task": task["id"], "issue": f"{loc[0]} #{loc[1]}"})
            if verbose or dry:
                print(f"[escalate] {task['id']} ({loc[0]} #{loc[1]}) SKIPPÉ : "
                      f"issue CLOSED — arbitrage orchestrateur, pas humain")
            state[key] = event_id          # traité : ne pas republier au tick suivant
            continue
        target = thread_id or cfg.channel_id
        label = f"{loc[0]} #{loc[1]}" if loc else "issue inconnue"
        if verbose or dry:
            print(f"[escalate] {task['id']} ({label}) status={task['status']} kind={bkind} "
                  f"ev={event_id} -> thread {target}")
        if dry:
            continue
        msg = build_message(cfg, board, task, bkind, reason, thread_id)
        if poster(target, msg):
            state[key] = event_id
            stats["escalated"].append({"task": task["id"], "issue": label, "event": event_id})
        else:
            stats["errors"].append(task["id"])
    save_state(cfg, board, state)
    conn.close()
    return stats


def main(argv=None) -> int:
    """Entrée de production. rc=2 sur configuration refusée (rien n'est muté)."""
    args = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in args
    verbose = "--verbose" in args
    board_arg = None
    if "--board" in args and args.index("--board") + 1 < len(args):
        board_arg = args[args.index("--board") + 1]
    try:
        cfg = escalation_config()
        validate_config(cfg)
    except ConfigError as exc:
        # Refus BRUYANT et SANS trace : le message nomme la variable, il est lu par
        # l'humain qui ouvre le fichier de sortie du cron.
        print(f"[escalate] refus: {exc}", file=sys.stderr)
        return 2
    board_env = os.environ.get("PJ_BOARD") or ""
    if board_arg:
        boards = [board_arg]
    elif board_env:
        boards = [board_env]
    elif KANBAN_ROOT.is_dir():
        boards = sorted(p.name for p in KANBAN_ROOT.iterdir()
                        if p.is_dir() and p.name.startswith(BOARD_PREFIX))
    else:
        boards = []
    total = 0
    for b in boards:
        st = run(b, dry, verbose, cfg=cfg)
        n = len(st.get("escalated", []))
        total += n
        if n or st.get("errors") or verbose:
            print(f"[escalate] {b}: {n} escalade(s), {st.get('skipped', 0)} déjà vue(s)"
                  + (f", erreurs={st['errors']}" if st.get("errors") else ""))
    if dry:
        print(f"[escalate] DRY-RUN — {total} escalade(s) auraient été postées")
    return 0


if __name__ == "__main__":
    sys.exit(main())
