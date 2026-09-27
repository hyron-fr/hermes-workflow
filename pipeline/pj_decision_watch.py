#!/usr/bin/env python3
"""Câblage `/ok` — le runner qui fait exister la décision humaine en production.

POURQUOI CE MODULE EXISTE (issue #5, contrat de câblage « post-#4 »)
-------------------------------------------------------------------
Les slices 4 et 5 de l'issue #5 ont livré **le core pur** de décision
(`pipeline/pj_decision.py`) et **l'émetteur** des deux notifications
(`pipeline/pj_notify.py`). Les deux docs de composant consignent la même
asymétrie, verbatim : « aucun consommateur de production n'existe —
`grep -rn 'pj_decision'` hors module et hors `tests/` → 0 hit ». Le câblage
« appartient à la slice post-#4 ». Ce fichier **est** cette slice : sans lui,
`/ok` est une grammaire écrite que personne ne lit.

LE DESIGN EST DÉJÀ RATIFIÉ — CE MODULE NE DÉCIDE RIEN
-----------------------------------------------------
Il ne réimplémente ni la grammaire ni les notifications : il **appelle** les deux
modules versionnés et se limite aux **effets** (lire GitHub, écrire kanban,
commenter/fermer). Toute la logique de décision vit dans `pj_decision` ; tout le
texte des notifications vit dans `pj_notify`. C'est ce découpage qui rend ce
runner testable avec des seams, sans réseau ni board réel.

CYCLE D'UN TICK (0 LLM, déterministe)
-------------------------------------
1. lister les **enfants de décision** ouverts du dépôt (label `decision`) ;
2. pour chaque enfant : lire ses commentaires et les cartes qu'il désigne (ligne
   canonique `carte: <board>/<task_id>`), puis calculer une décision par
   commentaire via `pj_decision.decision_from_comment` ;
3. `effect == "unblock"` → `kanban comment` + `kanban unblock` sur la carte
   désignée, puis `pj_notify.notify_decision` (enfant notifié PUIS fermé,
   parent notifié, jamais fermé) ;
4. `effect == "comment"` → la décision n'a **rien** débloqué : on ne notifie
   pas un déblocage qui n'a pas eu lieu, mais on **trace** sur la carte (jamais
   d'échec silencieux) ;
5. `effect == "ignore"` → rien (un jeton cité, un commentaire déjà consommé, un
   jeton périmé par un re-blocage).

L'ÉTAT INTER-TICKS EST LA MÉMOIRE DE LA DÉDUP
--------------------------------------------
`seen_comment_ids` (anti-rejeu dans le round) et `notified` (anti-reboucle de
notification) sont persistés par enfant. `decision_key` porte déjà le commentaire
`/ok`, donc un re-blocage — qui produit un **nouveau** commentaire — redevient
décidable sans jamais rejouer l'ancien.

CONFIGURATION — comme `pj_escalate`, tout vient de l'environnement
------------------------------------------------------------------
Aucun identifiant ni chemin machine n'est codé ici (le dépôt est partagé). Les
variables sont lues par `decision_config()` et documentées dans `pipeline/README.md`.

Usage :
  pj_decision_watch.py [--dry-run] [--verbose] [--board B] [--repo R]
"""

import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

# Racine des boards kanban : constante module-level, surchargée par `monkeypatch`
# dans les tests (même convention que `pj_escalate.py` — demander une variable
# d'environnement pour ce qu'un monkeypatch fait proprement serait de la surface
# d'API gratuite).
KANBAN_ROOT = Path.home() / ".hermes" / "kanban" / "boards"

# Marqueur du commentaire de RE-BLOCAGE. Le design ratifié en fait le pivot de la
# péremption (`ctx['last_reopen_comment_id']`) et de la clé de notification
# (« un re-blocage produit un NOUVEAU commentaire ⇒ une NOUVELLE clé »), mais son
# FORMAT n'était fixé nulle part : personne ne l'écrivait. C'est le producteur
# ci-dessous qui le poste et le consommateur qui le relit — une seule grammaire,
# deux lecteurs, comme la ligne canonique.
REOPEN_MARKER = "🔁 **Re-blocage**"

# États d'issue GitHub tels que `gh` les rend. Seule une enfant FERMÉE peut être
# rouverte : une enfant ouverte attend déjà sa décision.
CLOSED_STATE = "CLOSED"

# Préfixe de convention des boards du pipeline (FIGÉ, même règle que pj_escalate).
BOARD_PREFIX = "pj-"

# Label qui marque un OBJET DE DÉCISION dans le pont (`bridge/gh_kanban_bridge.py`,
# `DECISION_LABEL`). C'est le même littéral, et c'est volontaire : le pont **exempte**
# de l'import ce qu'il voit porter ce label, donc un objet de décision n'est jamais
# transformé en tâche.
DECISION_LABEL = "decision"

# Ligne canonique portée par le corps de l'enfant : `carte: <board>/<task_id>` —
# le pendant de `ROOM:` côté room. Sa lecture à froid appartient à ce câblage
# (elle était explicitement hors périmètre des slices 4 et 5).
CARD_LINE_RE = re.compile(r"^[ \t]*carte[ \t]*:[ \t]*(?P<board>[A-Za-z0-9._-]+)[ \t]*/[ \t]*(?P<task>t_[0-9a-fA-F]+)[ \t]*$",
                          re.MULTILINE)

# Contrat de configuration : présence ET non-vacuité (même patron que pj_escalate).
REQUIRED_VARS = ("PJ_WATCH_ORG",)

GH_BIN_FALLBACKS = ("~/.local/bin/gh", "~/.hermes/bin/gh")


class ConfigError(ValueError):
    """Configuration refusée : le tick sort en rc=2, bruyamment, sans rien muter."""


def _resolve_bin(name: str, *candidates: str) -> str:
    """Résout un exécutable : PATH puis candidats VÉRIFIÉS.

    Ne jamais supposer que le PATH interactif est disponible : mesuré sur cette
    machine, le PATH d'un cron ne contient pas `~/.local/bin`, donc
    `subprocess.run(["gh", ...])` lève `FileNotFoundError` — un runner qui
    l'ignorerait serait INERTE en production tout en paraissant actif en session.
    Retourne la **chaîne vide** quand rien ne passe (jamais le nom nu, qui
    rendrait le binaire *truthy* et rendrait muet l'avertissement de l'appelant).
    """
    found = shutil.which(name)
    if found:
        return found
    for c in candidates:
        p = os.path.expanduser(c)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return ""


GH_BIN = _resolve_bin("gh", *GH_BIN_FALLBACKS)
HERMES_BIN = _resolve_bin("hermes", "~/.hermes/hermes-agent/venv/bin/hermes",
                          "~/.local/bin/hermes")


class WatchConfig:
    """Identifiants et chemins du runner — tous injectables, aucun codé en dur."""

    def __init__(self, *, org, repos, board, gh_bin, hermes_bin, state_dir):
        self.org = org
        self.repos = repos or []
        self.board = board
        self.gh_bin = gh_bin
        self.hermes_bin = hermes_bin
        self.state_dir = Path(state_dir)


def _text(env, name: str, default: str = "") -> str:
    """Valeur d'environnement, blancs de bord retirés. Jamais `None`."""
    raw = env.get(name)
    return (raw or "").strip() if isinstance(raw, str) or raw is None else str(raw).strip()


def decision_config(env=None) -> WatchConfig:
    """Construit la configuration depuis l'environnement (jamais codée en dur)."""
    env = os.environ if env is None else env
    return WatchConfig(
        org=_text(env, "PJ_WATCH_ORG"),
        repos=[r for r in _text(env, "PJ_WATCH_REPOS").split(",") if r.strip()],
        board=_text(env, "PJ_WATCH_BOARD"),
        gh_bin=_text(env, "PJ_WATCH_GH_BIN") or _resolve_bin("gh", *GH_BIN_FALLBACKS),
        hermes_bin=_text(env, "PJ_WATCH_HERMES_BIN") or HERMES_BIN,
        state_dir=_text(env, "PJ_WATCH_STATE_DIR") or str(Path.home() / ".hermes" / "state"),
    )


def validate_config(cfg: WatchConfig) -> None:
    """Refus bruyant : la configuration est l'objet REÇU, jamais l'environnement.

    Une valeur vide n'est jamais un identifiant : la laisser passer produirait une
    commande parfaitement valide syntaxiquement (`--repo /`) et un échec obscur plus
    loin. Lire `cfg` rend la validation injectable — même convention que
    `escalation_config`, qui lit EXCLUSIVEMENT le mapping reçu ; `main()` lui passe
    la config construite depuis l'environnement.
    """
    if not _text({"org": cfg.org}, "org"):
        raise ConfigError(
            "variable(s) requise(s) absente(s) ou vide(s) : " + ", ".join(REQUIRED_VARS)
            + " — renseigner le wrapper du cron (voir pipeline/README.md, §« Câblage /ok »)")
    if not cfg.repos:
        raise ConfigError("PJ_WATCH_REPOS vide : aucun dépôt à surveiller")


# --------------------------------------------------------------------------- état ---

def state_path(cfg: WatchConfig, repo: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", repo)
    return Path(cfg.state_dir) / f"pj_decision_watch_{slug}.json"


def load_state(cfg: WatchConfig, repo: str) -> dict:
    """État inter-ticks : `{issue: {"seen": [...], "notified": [...]}}`.

    Un état illisible est traité comme **vide** : le pire cas est de reconsommer
    des commentaires — ce que l'anti-rejeu de `pj_decision` (jeton périmé) et la
    clé de `pj_notify` amortissent — plutôt que de faire tomber le tick.
    """
    try:
        data = json.loads(state_path(cfg, repo).read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_state(cfg: WatchConfig, repo: str, state: dict) -> None:
    p = state_path(cfg, repo)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=1, sort_keys=True))


# ------------------------------------------------------------------- lecture GitHub ---

def _warn_once(msg: str, warned: set) -> None:
    """Un avertissement par message et par tick : une garde inerte est VISIBLE."""
    if msg in warned:
        return
    warned.add(msg)
    print(f"[watch] ⚠️ {msg}")


def list_decision_children(cfg: WatchConfig, repo: str, *, state: str = "open",
                           runner=subprocess.run) -> list[dict]:
    """Enfants de décision du dépôt (label `decision`), `open` par défaut.

    Tri-state sur les doutes, même contrat que `pj_escalate.issue_is_closed` : un
    `gh` indisponible ou une lecture refusée rendent `[]` **et avertissent** — on
    ne fait pas tomber le tick, mais on ne le rend pas muet non plus.
    """
    if not cfg.gh_bin:
        _warn_once("gh introuvable (PATH + candidats) — surveillance /ok INDISPONIBLE", set())
        return []
    try:
        r = runner([cfg.gh_bin, "issue", "list", "--repo", f"{cfg.org}/{repo}",
                    "--label", DECISION_LABEL, "--state", state,
                    "--json", "number,title,body,url,parent,state"],
                   capture_output=True, text=True, timeout=60)
    except Exception as exc:
        _warn_once(f"liste des enfants illisible : {type(exc).__name__} — surveillance /ok sautée", set())
        return []
    if r.returncode != 0:
        _warn_once(f"liste des enfants illisible : gh rc={r.returncode} — surveillance /ok sautée", set())
        return []
    try:
        out = json.loads(r.stdout or "[]")
    except Exception:
        _warn_once("liste des enfants illisible : sortie JSON invalide — surveillance /ok sautée", set())
        return []
    return out if isinstance(out, list) else []


def read_comments(cfg: WatchConfig, repo: str, number: int, *, runner=subprocess.run) -> list[dict]:
    """Commentaires d'une issue (jamais d'exception : un doute rend `[]`)."""
    if not cfg.gh_bin:
        return []
    try:
        r = runner([cfg.gh_bin, "issue", "view", str(number), "--repo", f"{cfg.org}/{repo}",
                    "--json", "comments"], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return []
        data = json.loads(r.stdout or "{}")
    except Exception:
        return []
    comments = data.get("comments") if isinstance(data, dict) else None
    return comments if isinstance(comments, list) else []


def _parent_of(child: dict) -> int | None:
    """Numéro du ticket parent d'un enfant de décision, ou None.

    Le pont fournit `parent` (sub-issue) ; on ne DEVINE jamais un parent : un
    enfant non rattaché reste sans parent, et la notification le dit alors au lieu
    d'inventer un lien.
    """
    p = child.get("parent") if isinstance(child, dict) else None
    if isinstance(p, dict):
        return p.get("number") if isinstance(p.get("number"), int) else None
    if isinstance(p, int):
        return p
    return None


def canonical_card(body: str) -> tuple[str, str] | None:
    """(board, task_id) de la ligne canonique `carte: <board>/<task_id>`.

    C'est le lien à froid enfant → carte : le corps de l'enfant le porte, le
    module de décision ne le lit pas (il travaille sur `card['issue']`). Ce
    câblage est donc le seul endroit où cette ligne est interprétée — une seule
    grammaire, un seul lecteur.
    """
    m = CARD_LINE_RE.search(body or "")
    if not m:
        return None
    return m.group("board"), m.group("task")


# ------------------------------------------------------------ producteur d'enfant ---

DECISION_LABEL_COLOR = "5319e7"
DECISION_LABEL_DESC = "Objet de décision humaine (issue enfant d'une carte bloquée)"


def ensure_decision_label(cfg: WatchConfig, repo: str, *, runner=subprocess.run) -> bool:
    """Garantit l'existence du label `decision` (idempotent).

    Nécessaire pour que la trappe ne mente pas : `gh issue create --label <inconnu>`
    échoue et l'enfant n'existe pas. Le message d'escalade proposerait alors un geste
    inapplicable — c'est exactement le défaut mesuré sur le gate de couverture
    (`ensure_mirror_label()` a la même raison d'être).
    """
    if not cfg.gh_bin:
        return False
    try:
        r = runner([cfg.gh_bin, "label", "create", DECISION_LABEL, "--repo", f"{cfg.org}/{repo}",
                    "--color", DECISION_LABEL_COLOR, "--description", DECISION_LABEL_DESC],
                   capture_output=True, text=True, timeout=60)
    except Exception:
        return False
    return r.returncode == 0 or "already exists" in (r.stderr or "")


def find_decision_child(cfg: WatchConfig, repo: str, parent: int, task_id: str, *,
                        runner=subprocess.run) -> dict | None:
    """Enfant de décision EXISTANTE pour une carte : `{number, state}`, ou None.

    Cherche parmi **tous** les états, pas seulement les ouvertes : c'est ce qui
    distingue « l'enfant attend déjà une décision » (RIEN à faire) de « l'enfant a
    été fermée par une décision, la carte a re-bloqué » (à rouvrir). Réduire la
    recherche aux ouvertes rendait la réouverture indécidable — et faisait poster un
    marqueur à chaque tick (mesuré en production).

    La comparaison se fait sur la ligne canonique : même grammaire que le
    consommateur, donc une création et une relecture ne peuvent pas diverger.
    """
    for child in list_decision_children(cfg, repo, state="all", runner=runner):
        loc = canonical_card(child.get("body") or "")
        if loc and loc[1] == task_id:
            n = child.get("number")
            return {"number": n, "state": (child.get("state") or "").upper(),
                    "task": task_id} if isinstance(n, int) else None
    return None


def create_decision_child(cfg: WatchConfig, repo: str, parent: int, board: str, task_id: str,
                          title: str, reason: str, *, runner=subprocess.run) -> int | None:
    """Crée l'enfant de décision d'une carte bloquée, rattachée à son ticket.

    `--parent <n>` fait de l'enfant une **sub-issue** : le pont sait alors lire
    `parent`, et le consommateur peut résoudre `ctx['parent_issue']` sans deviner.
    Le rattachement est donc un contrat de production, pas une décoration.
    """
    if not cfg.gh_bin:
        return None
    body = (
        f"**Point à statuer** sur la carte `{task_id}` (board `{board}`), "
        f"bloquée sur le ticket #{parent}.\n\n"
        f"Motif déclaré : {reason[:600] or '(non détaillé)'}\n\n"
        f"Le détail du constat est sur la carte : "
        f"`hermes kanban --board {board} show {task_id}`\n\n"
        f"**Pour trancher**, commentez cette issue avec le jeton `/ok` en **premier "
        f"élément** : la carte est débloquée et repart en file. Tout autre commentaire "
        f"est une demande d'éclaircissement et ne débloque rien.\n\n"
        f"carte: {board}/{task_id}\n"
    )
    try:
        r = runner([cfg.gh_bin, "issue", "create", "--repo", f"{cfg.org}/{repo}",
                    "--parent", str(parent), "--label", DECISION_LABEL,
                    "--title", title[:250], "--body", body],
                   capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    m = re.search(r"/issues/(\d+)", r.stdout or "")
    return int(m.group(1)) if m else None


def reopen_decision_child(cfg: WatchConfig, repo: str, number: int, task_id: str, reason: str, *,
                          runner=subprocess.run) -> bool:
    """Rouvre l'enfant d'un re-blocage ET y poste le marqueur.

    L'ordre compte : GitHub refuse `reopen` sur une issue déjà ouverte, donc le
    commentaire est posé **après**. C'est ce commentaire neuf qui porte le nouveau
    `last_reopen_comment_id` — sans lui, un `/ok` du round précédent refermerait
    l'enfant rouverte, et un `/ok` du nouveau round serait jugé périmé : dans les
    deux cas le blocage serait définitif.
    """
    if not cfg.gh_bin:
        return False
    try:
        r = runner([cfg.gh_bin, "issue", "reopen", str(number), "--repo", f"{cfg.org}/{repo}"],
                   capture_output=True, text=True, timeout=60)
        if r.returncode != 0 and "already" not in (r.stderr or "").lower():
            return False
        return gh_comment(cfg, repo, number,
                          f"{REOPEN_MARKER} — la carte `{task_id}` est bloquée de nouveau.\n\n"
                          f"Motif déclaré : {reason[:600] or '(non détaillé)'}\n\n"
                          f"Les jetons `/ok` antérieurs à ce commentaire ne valent plus : "
                          f"commenter à nouveau en premier élément.",
                          runner=runner)
    except Exception:
        return False


def ensure_decision_child(cfg: WatchConfig, repo: str, *, parent: int, board: str, task_id: str,
                          title: str, reason: str, runner=subprocess.run) -> dict:
    """Fait exister l'objet de décision d'une carte bloquée — UN par carte.

    L'ÉTAT DE L'ENFANT est la clé d'idempotence — une seule source de vérité, côté
    GitHub, partagée par tous les ticks. Trois issues, toutes explicites :

    - **aucune enfant** → `created` (premier blocage) ;
    - **enfant OUVERTE** → `waiting` : elle attend déjà une décision, on ne rouvre
      RIEN et on ne poste AUCUN marqueur. C'est le cas nominal d'un tick répété ;
    - **enfant FERMÉE** (une décision a été consommée) → `reopened` : la carte a
      re-bloqué, on rouvre la MÊME enfant et on y poste le marqueur.

    Un `event` de blocage dans la base n'est PAS une clé fiable : mesuré, des cartes
    bloquées (`t_618df8a6`) n'ont aucun événement `blocked` enregistré — s'y fier les
    re-signalait à chaque tick.
    """
    if not ensure_decision_label(cfg, repo, runner=runner):
        return {"child": None, "effect": "failed", "why": f"label {DECISION_LABEL} indisponible"}
    existing = find_decision_child(cfg, repo, parent, task_id, runner=runner)
    if existing is not None:
        if existing["state"] != CLOSED_STATE:
            return {"child": existing["number"], "effect": "waiting", "why": ""}
        ok = reopen_decision_child(cfg, repo, existing["number"], task_id, reason, runner=runner)
        return {"child": existing["number"], "effect": "reopened" if ok else "failed",
                "why": "" if ok else "réouverture/marquage refusé"}
    number = create_decision_child(cfg, repo, parent, board, task_id, title, reason, runner=runner)
    if number is None:
        return {"child": None, "effect": "failed", "why": "création refusée par gh"}
    return {"child": number, "effect": "created", "why": ""}


def decision_marker(board: str, task_id: str) -> str:
    """Ligne à ajouter (une seule fois) dans le message d'escalade : où décider."""
    return f"carte: {board}/{task_id}"


# ------------------------------------------------------------------------- effets ---

def gh_comment(cfg: WatchConfig, repo: str, issue: int, body: str, *, runner=subprocess.run) -> bool:
    """Commente une issue. `False` = refus, jamais une exception qui emporte le tick."""
    if not cfg.gh_bin:
        return False
    try:
        r = runner([cfg.gh_bin, "issue", "comment", str(issue), "--repo", f"{cfg.org}/{repo}",
                    "--body", body], capture_output=True, text=True, timeout=60)
    except Exception:
        return False
    return r.returncode == 0


def gh_close(cfg: WatchConfig, repo: str, issue: int, *, runner=subprocess.run) -> bool:
    """Ferme une issue (l'enfant de décision, sur décision acquise)."""
    if not cfg.gh_bin:
        return False
    try:
        r = runner([cfg.gh_bin, "issue", "close", str(issue), "--repo", f"{cfg.org}/{repo}"],
                   capture_output=True, text=True, timeout=60)
    except Exception:
        return False
    return r.returncode == 0


def kanban(board: str, *args: str, cfg: WatchConfig, runner=subprocess.run):
    """Appelle le CLI kanban (board explicite : le pointeur `current` n'est pas fiable)."""
    if not cfg.hermes_bin:
        raise ConfigError("binaire `hermes` introuvable (PATH + candidats)")
    return runner([cfg.hermes_bin, "kanban", "--board", board, *args],
                  capture_output=True, text=True, timeout=120)


def unblock_card(board: str, task_id: str, note: str, *, cfg: WatchConfig, runner=subprocess.run) -> bool:
    """Commente PUIS débloque la carte. L'ordre compte : le worker re-spawné relit
    tout le fil (carte + commentaires) et doit y trouver la décision."""
    try:
        kanban(board, "comment", task_id, note, cfg=cfg, runner=runner)
        r = kanban(board, "unblock", task_id, cfg=cfg, runner=runner)
    except Exception:
        return False
    return r.returncode == 0


def trace_card(board: str, task_id: str, message: str, *, cfg: WatchConfig, runner=subprocess.run) -> bool:
    """Trace un doute sur la carte. Un échec de trace ne doit pas emporter le tick."""
    try:
        r = kanban(board, "comment", task_id, message, cfg=cfg, runner=runner)
    except Exception:
        return False
    return r.returncode == 0


def card_status(board: str, task_id: str, *, cfg: WatchConfig) -> str | None:
    """Statut lu en base (lecture seule) — évite un appel CLI par carte."""
    db = KANBAN_ROOT / board / "kanban.db"
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(db)
        try:
            row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
        finally:
            conn.close()
    except Exception:
        return None
    return row[0] if row else None


def _issue_of(conn: sqlite3.Connection, task_id: str, board: str) -> int | None:
    """Numéro d'issue d'une carte, par sa clé d'idempotence puis par remontée des parents.

    La clé du pipeline encode `<prefixe>-…-<repo>-<issue>` ; les cartes créées hors
    pipeline n'en ont pas, donc on remonte les liens parents jusqu'à une carte clée
    ou jusqu'à un corps qui cite une URL d'issue. Repli : le `#N` du titre ou du corps.
    """
    seen: set[str] = set()
    queue = [task_id]
    while queue:
        tid = queue.pop(0)
        if tid in seen:
            continue
        seen.add(tid)
        row = conn.execute("SELECT idempotency_key, body, title FROM tasks WHERE id = ?",
                           (tid,)).fetchone()
        if row is None:
            continue
        key = row["idempotency_key"] or ""
        m = re.search(r"-(\d+)$", key)
        if m:
            return int(m.group(1))
        body = row["body"] or ""
        m = re.search(r"github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/(\d+)", body)
        if m:
            return int(m.group(1))
        for r in conn.execute("SELECT parent_id FROM task_links WHERE child_id = ?", (tid,)):
            queue.append(r["parent_id"])
    row = conn.execute("SELECT title, body FROM tasks WHERE id = ?", (task_id,)).fetchone()
    text = f"{row['title'] or ''}\n{row['body'] or ''}" if row else ""
    m = re.search(r"#(\d+)\b", text)
    return int(m.group(1)) if m else None


def _block_reason(conn: sqlite3.Connection, task_id: str) -> str:
    """Motif du dernier blocage (payload JSON), chaîne vide si illisible."""
    kinds = ("blocked", "block_loop_detected")
    q = ("SELECT payload FROM task_events WHERE task_id = ? AND kind IN ("
         + ",".join("?" * len(kinds)) + ") ORDER BY id DESC LIMIT 1")
    row = conn.execute(q, (task_id, *kinds)).fetchone()
    if row is None:
        return ""
    try:
        payload = json.loads(row["payload"] or "{}")
    except Exception:
        return ""
    return str(payload.get("reason") or payload.get("summary") or "").strip()


def block_event_id(conn: sqlite3.Connection, task_id: str) -> int | None:
    """Identifiant du DERNIER événement de blocage d'une carte, ou None.

    C'est la clé d'idempotence de la réouverture : `task_events.id` est strictement
    croissant, donc « le même blocage » est reconnaissable et un **nouveau** blocage
    (nouvel id) seul justifie un nouveau marqueur. `pj_escalate` utilise exactement
    cette clé pour sa propre dédup — même modèle, deux lecteurs.
    """
    kinds = ("blocked", "block_loop_detected")
    q = ("SELECT id FROM task_events WHERE task_id = ? AND kind IN ("
         + ",".join("?" * len(kinds)) + ") ORDER BY id DESC LIMIT 1")
    row = conn.execute(q, (task_id, *kinds)).fetchone()
    return int(row["id"]) if row else None


def blocked_cards(cfg: WatchConfig, board: str | None = None) -> list[dict]:
    """Cartes bloquées du board, avec l'issue de leur ticket et le motif du blocage.

    Lecture seule, jamais d'exception : un doute rend ce qu'on a pu lire. L'issue est
    RÉSOLUE, jamais devinée — une carte sans issue résoluble est écartée (le
    producteur ne peut pas rattacher une enfant à un ticket qu'il ne connaît pas) ;
    `pj_escalate` continue de l'escalader, c'est son rôle, pas celui du câblage.
    """
    board = board or cfg.board
    if not board:
        return []
    db = KANBAN_ROOT / board / "kanban.db"
    if not db.exists():
        return []
    out: list[dict] = []
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, title, status FROM tasks WHERE status IN ('blocked','triage') "
                "ORDER BY id").fetchall()
            for row in rows:
                issue = _issue_of(conn, row["id"], board)
                if issue is None:
                    continue
                out.append({"board": board, "task_id": row["id"], "title": row["title"] or row["id"],
                            "issue": issue, "reason": _block_reason(conn, row["id"]),
                            "event": block_event_id(conn, row["id"])})
        finally:
            conn.close()
    except Exception:
        return out
    return out


# ---------------------------------------------------------------------------- tick ---

def _load_sibling_module(name: str, *, extra_dirs=()) -> object:
    """Charge `pj_decision` / `pj_notify` — les modules voisins du câblage.

    La copie INSTALLÉE vit dans `~/.hermes/profiles/pj-master/scripts/`, où les
    modules frères ne sont pas forcément présents : mesuré en environnement de cron,
    un chargement strictement « à côté de moi » lève `FileNotFoundError` et le cron
    meurt à chaque tick. On cherche donc dans l'ordre :
      1. le répertoire du présent fichier (copie versionnée `pipeline/`) ;
      2. `PJ_WATCH_MODULES_DIR` (déploiement où l'on publie les modules ensemble) ;
      3. les voisins de la copie installée (même nom de fichier).
    L'échec est BRUYANT et NOMME les chemins essayés : un tick qui ne trouverait pas
    son core ne doit pas passer pour un tick sans rien à faire.
    """
    here = Path(__file__).resolve().parent
    candidates = [here]
    env_dir = os.environ.get("PJ_WATCH_MODULES_DIR")
    if env_dir:
        candidates.append(Path(os.path.expanduser(env_dir)))
    candidates.extend(Path(os.path.expanduser(d)) for d in extra_dirs)
    candidates.append(Path.home() / ".hermes" / "profiles" / "pj-master" / "scripts")
    for d in candidates:
        p = d / f"{name}.py"
        if p.is_file():
            spec = importlib.util.spec_from_file_location(name, str(p))
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise ConfigError(
        f"module {name}.py introuvable — chemins essayés : "
        + ", ".join(str(d / f"{name}.py") for d in candidates)
        + " (publier les modules avec pj_publish.py, ou poser PJ_WATCH_MODULES_DIR)")


def watch_repo(repo: str, *, cfg: WatchConfig, dry=False, verbose=False,
               runner=subprocess.run, decision_mod=None, notify_mod=None,
               post_discord=None) -> dict:
    """Un tick sur un dépôt : produire les objets de décision, lire les `/ok`, notifier.

    Les modules de décision et de notification sont injectés (défaut : les modules
    versionnés). C'est ce qui rend ce runner exerçable hors ligne, sur un banc,
    sans réseau ni board réel — la même propriété qui rend `pj_decision` et
    `pj_notify` falsifiables.
    """
    if decision_mod is None:
        decision_mod = _load_sibling_module("pj_decision")
    if notify_mod is None:
        notify_mod = _load_sibling_module("pj_notify")

    state = load_state(cfg, repo)
    # `state` porte deux familles de clés : les numéros d'issue (enfants, anti-rejeu
    # des jetons) et `__events__` (dédup de la PRODUCTION). La boucle ci-dessous
    # écrirait `state["__events__"]` comme un enfant et écraserait la clé — on la
    # garde donc de côté et on la repose avant la sauvegarde.
    state.pop("__events__", None)      # ancienne clé de dédup, remplacée par l'état GitHub
    # Forme STABLE : `children` est toujours présent, même vide. Un rapport dont la
    # forme dépend du chemin (la clé n'apparaît que si l'on a produit) oblige chaque
    # lecteur à se défendre par `.get()` — et un appelant qui l'oublie confond « rien
    # produit » avec « clé absente ».
    stats = {"repo": repo, "unblocked": [], "commented": [], "ignored": 0,
             "errors": [], "children": []}

    # PHASE 1 — PRODUIRE. Chaque carte bloquée doit avoir SON objet de décision, sans
    # quoi le `/ok` de l'humain n'a nulle part où être écrit : c'est le maillon qui
    # rend la décision atteignable (Option 1, issue #5). La création est idempotente
    # par la ligne canonique, donc un re-blocage rouvre la MÊME enfant.
    #
    # `--dry-run` n'écrit RIEN — ni carte, ni issue GitHub : il annonce ce qu'il
    # ferait. Une production non gardée ferait de `--dry-run` un mode destructeur,
    # c'est-à-dire l'inverse de sa promesse.
    if cfg.board:
        for card in blocked_cards(cfg):
            # L'idempotence est portée par l'ÉTAT DE L'ENFANT (créée/ouverte/fermée),
            # pas par une mémoire locale : un tick répété voit « enfant ouverte » et
            # ne poste rien. Une enfant ouverte qui attend sa décision n'est PAS un
            # objet à signaler — c'est l'état normal jusqu'à ce que l'humain réponde.
            if dry:
                existing = find_decision_child(cfg, repo, card["issue"], card["task_id"],
                                               runner=runner)
                effect = ("waiting" if existing and existing["state"] != CLOSED_STATE else
                          "would_reopen" if existing else "would_create")
                stats["children"].append({"task": card["task_id"],
                                          "child": existing["number"] if existing else None,
                                          "effect": effect})
                continue
            res = ensure_decision_child(cfg, repo, parent=card["issue"], board=card["board"],
                                        task_id=card["task_id"], title=card["title"],
                                        reason=card["reason"], runner=runner)
            if res["effect"] == "failed":
                stats["errors"].append({"task": card["task_id"], "why": res["why"],
                                        "parent": card["issue"]})
            elif res["effect"] in ("created", "reopened"):
                stats["children"].append({"task": card["task_id"], "child": res["child"],
                                          "effect": res["effect"]})
    children = list_decision_children(cfg, repo, runner=runner)
    for child in children:
        number = child.get("number")
        if not isinstance(number, int):
            continue
        slot = state.setdefault(str(number), {"seen": [], "notified": []})
        seen = set(slot.get("seen") or [])
        notified = set(slot.get("notified") or [])

        loc = canonical_card(child.get("body") or "")
        cards = []
        if loc:
            board, task_id = loc
            cards = [{"task_id": task_id, "board": board,
                      "status": card_status(board, task_id, cfg=cfg), "issue": number}]

        comments = read_comments(cfg, repo, number, runner=runner)
        # Le marqueur de re-blocage est RELU ici, et pas seulement écrit par le
        # producteur : c'est ce qui rend la péremption effective. Sans cette
        # relecture, `last_reopen_comment_id` resterait `None` et un `/ok` du round
        # précédent refermerait l'enfant rouverte (défaut que le design interdit).
        #
        # PRÉ-SCAN obligatoire : `last_reopen_comment_id` est une propriété de l'ÉTAT
        # de l'enfant, pas de la position dans la boucle. Les commentaires arrivent du
        # plus ancien au plus récent : calculer le marqueur au fil de l'eau jugerait
        # le `/ok` antérieur AVANT d'avoir vu le marqueur, et il débloquerait la carte
        # — exactement le défaut que la péremption doit empêcher.
        last_reopen = None
        for c in comments:
            if REOPEN_MARKER in (c.get("body") or ""):
                last_reopen = c.get("id")

        for comment in comments:
            ctx = {"issue": {"number": number, "state": "OPEN"},
                   "cards": cards, "seen_comment_ids": seen,
                   "last_reopen_comment_id": last_reopen,
                   "child_issue": {"number": number},
                   "parent_issue": _parent_of(child),
                   "decision_comment": comment, "notified": notified}
            decision = decision_mod.decision_from_comment(ctx, comment)
            cid = comment.get("id")
            effect = decision.get("effect")

            if verbose or dry:
                print(f"[watch] {repo}#{number} comment {cid}: effect={effect} "
                      f"task={decision.get('task_id')} note={decision.get('note')}")
            if effect == "ignore":
                stats["ignored"] += 1
                if cid is not None:
                    seen.add(cid)
                continue

            if dry:
                continue

            if effect == "unblock":
                board = decision.get("board") or (cards[0]["board"] if cards else "")
                task_id = decision.get("task_id") or ""
                note = (f"Décision humaine `/ok` reçue sur l'issue de décision #{number} "
                        f"(commentaire {cid}). La carte repart en file.")
                if board and task_id and unblock_card(board, task_id, note, cfg=cfg, runner=runner):
                    stats["unblocked"].append({"task": task_id, "board": board, "issue": number})
                    if post_discord:
                        post_discord(board, task_id, number, cid)
                    effects = {
                        "comment": lambda issue, body: gh_comment(cfg, repo, issue, body, runner=runner),
                        "close": lambda issue: gh_close(cfg, repo, issue, runner=runner),
                        "trace": lambda task, msg: trace_card(board, task, msg, cfg=cfg, runner=runner),
                    }
                    notify_mod.notify_decision(decision, ctx, effects)
                else:
                    # Un `/ok` sans cible exploitable ne doit JAMAIS être avalé : la carte
                    # concernée n'est pas forcément connue, mais le doute, lui, est
                    # actionnable par l'humain. On trace sur la carte si on en a une,
                    # sinon on rapporte l'échec nommé (jamais un succès inventé).
                    why = ("unblock refusé" if (board and task_id) else
                           "aucune carte cible : ligne canonique absente ou carte introuvable")
                    stats["errors"].append({"issue": number, "why": why,
                                            "task": task_id, "board": board})
                    if board and task_id:
                        trace_card(board, task_id,
                                   f"⚠️ `/ok` lu sur l'issue #{number} (commentaire {cid}) "
                                   f"mais l'opération a été REFUSÉE ({why}) : la carte reste "
                                   f"bloquée. Un humain doit reprendre la main.",
                                   cfg=cfg, runner=runner)
            else:                                   # effect == "comment"
                note = (f"Décision `/ok` lue sur l'issue #{number} (commentaire {cid}) : "
                        f"{decision.get('note')} — rien n'a été débloqué.")
                board = decision.get("board") or (cards[0]["board"] if cards else "")
                task_id = decision.get("task_id") or (cards[0]["task_id"] if cards else "")
                if board and task_id:
                    trace_card(board, task_id, note, cfg=cfg, runner=runner)
                # Comptée DANS TOUS LES CAS : une décision sans effet reste une décision
                # lue. La compter seulement quand une carte est traçable rendrait
                # silencieux le cas le plus grave — un `/ok` sur un enfant dont la ligne
                # canonique manque (carte introuvable) — et le doute disparaîtrait du
                # rapport du tick au lieu d'être remonté.
                stats["commented"].append({"issue": number, "note": decision.get("note"),
                                           "traced_on": task_id or None})

            if cid is not None:
                seen.add(cid)
            slot["seen"] = sorted(x for x in seen if isinstance(x, int))
            slot["notified"] = sorted(x for x in notified if isinstance(x, str))

    save_state(cfg, repo, state)
    return stats


def main(argv=None) -> int:
    """Entrée de production. rc=2 sur configuration refusée (rien n'est muté)."""
    args = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in args
    verbose = "--verbose" in args
    try:
        cfg = decision_config()
        validate_config(cfg)
    except ConfigError as exc:
        print(f"[watch] refus: {exc}", file=sys.stderr)
        return 2
    repos = list(cfg.repos)
    if "--repo" in args and args.index("--repo") + 1 < len(args):
        repos = [args[args.index("--repo") + 1]]
    total = 0
    for repo in repos:
        st = watch_repo(repo, cfg=cfg, dry=dry, verbose=verbose)
        n = len(st["unblocked"])
        total += n
        kids = st.get("children") or []
        if n or kids or st["errors"] or verbose:
            print(f"[watch] {repo}: {n} débloquée(s), {len(st['commented'])} tracée(s), "
                  f"{st['ignored']} ignorée(s), {len(kids)} objet(s) de décision"
                  + (f", erreurs={st['errors']}" if st["errors"] else ""))
            # Le dry-run ANNONCE ce qu'il ferait : sans cette ligne, un tick qui
            # produirait trois issues GitHub afficherait « 0 » et se lirait comme
            # « rien à faire » — l'inverse de la vérité.
            for k in kids:
                if dry:
                    print(f"[watch]   {k['effect']} : carte {k['task']}"
                          + (f" (enfant #{k['child']})" if k.get("child") else ""))
    if dry:
        print(f"[watch] DRY-RUN — {total} déblocage(s) auraient été appliqués")
    return 0


if __name__ == "__main__":
    sys.exit(main())
