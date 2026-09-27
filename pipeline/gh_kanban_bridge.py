#!/usr/bin/env python3
"""
Pont GitHub Issues <-> Kanban Hermes.

Expérience : hyron-fr/hermes-experiment

Deux directions, sans fichier d'état local (l'état est dérivé de GitHub
et du board kanban) :

  PULL  : issues ouvertes SANS label 'kanban' (déjà miroir d'une carte), 'triage'
          (parquée pour le drill) ni 'decision' (objet de décision, pas une tâche)
          -> cartes kanban (idempotency-key 'gh-issue-<n>' => pas de doublon au retry)
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
# Objet de DÉCISION (l'issue enfant d'une carte bloquée). Un objet de décision
# n'est pas une tâche : l'importer déclencherait un graphe complet t1..t5 + une
# room de délibération SOUS une carte de décision (mesuré : 6 cartes, 11 liens).
# `kanban` ne peut pas servir ici : il veut dire « déjà miroir d'une carte », le
# réutiliser réécrirait la trappe du gate sous un autre motif.
DECISION_LABEL = "decision"
# Échappatoire HUMAINE du gate de couverture : posée à la main sur une issue que
# `coverage_verdict` refuse, elle fait importer l'issue MALGRÉ le recouvrement
# (« nouvelle tâche assumée »). Le gate la lit AVANT le verdict. À ne pas
# confondre avec `kanban`, qui exclut l'issue (défaut mesuré de l'ancien texte).
IMPORT_OVERRIDE_LABEL = "pj-import"
IMPORT_OVERRIDE_LABEL_COLOR = "0e8a16"
MIRROR_LABEL_COLOR = "1d76db"
TRIAGE_LABEL_COLOR = "d93f0b"
BOT_GRACE_SECONDS = int(os.environ.get("BOT_GRACE_SECONDS", "600"))  # issues plus jeunes -> réservées au bot gh-triage
DRY_RUN = os.environ.get("DRY_RUN") == "1"
QUIET_IDLE = os.environ.get("BRIDGE_VERBOSE") != "1"

def _resolve_bin(name: str, *candidates: str) -> str:
    """Résout un exécutable : PATH puis emplacements connus.

    Ne JAMAIS se rabattre sur un chemin en dur (`/usr/bin/gh` n'existe pas sur ce
    poste — constaté : `FileNotFoundError` dans les subprocess alors que `gh` est
    dans `~/.local/bin`). Un cron/subprocess n'a pas le PATH interactif.
    """
    found = shutil.which(name)
    if found:
        return found
    for c in candidates:
        p = os.path.expanduser(c)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return name          # laissera remonter une erreur claire à l'usage


HERMES_BIN = _resolve_bin("hermes", "~/.local/bin/hermes",
                          "~/.hermes/hermes-agent/venv/bin/hermes")
GH_BIN = _resolve_bin("gh", "~/.local/bin/gh", "~/.hermes/bin/gh")

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


# --------------------------------------------------- renfo 1 : gate de couverture
#
# Une issue qui recouvre du travail DÉJÀ en vol (PR ouverte, issue ouverte avec
# graphe) ne doit PAS lancer un nouveau graphe : vécu sur dino-game — 3 issues
# (#4, #9, #10) pour un seul changement (le rendu des acteurs de #4), avec un
# graphe complet construit puis jeté pour #9.
#
# Le gate ne DÉCIDE pas : il rend le chevauchement VISIBLE et laisse l'humain
# trancher (rattacher à #N ou assumer une nouvelle tâche).

_REF_RE = re.compile(r"(?<!#)#(\d+)\b")
_URL_RE = re.compile(r"https?://\S+")
# La ligne d'import que `pull()` ajoute à la carte racine : seul ancrage fiable
# du numéro d'issue d'un graphe (le corps d'une carte peut citer n'importe quoi).
_IMPORT_URL_RE = re.compile(r"/issues/(\d+)")
# La ligne d'import que `pull()` écrit lui-même — préfixe EXACT, en tête de ligne.
# C'est le seul ancrage du numéro d'issue d'une carte racine : un corps de carte
# cite n'importe quoi (une autre issue en prose, une URL en exemple, le gabarit
# `Issue GitHub : …` du t6). Ancrer sur la LIGNE, jamais sur le premier `/issues/<n>`.
_IMPORT_LINE_PREFIX = "Importé depuis"
_IMPORT_LINE_RE = re.compile(r"^[ \t]*%s\b" % re.escape(_IMPORT_LINE_PREFIX))
# Titre du gabarit de graphe : « t1 worktree », « t3b doc-cadrage #5 », « t6 submitted #2 ».
_GRAPH_TITLE_RE = re.compile(r"^t\d+[a-z]?\b")
_STOPWORDS = {
    "le", "la", "les", "des", "de", "du", "un", "une", "et", "ou", "a", "au", "aux",
    "en", "pour", "sur", "par", "avec", "dans", "ce", "cette", "ces", "son", "sa",
    "ses", "est", "sont", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "améliorer", "ajouter", "corriger", "faire", "mettre", "jour",
}
TITLE_OVERLAP_THRESHOLD = 0.34


def issue_refs(text) -> set:
    """Numéros d'issues cités (`#4`) — hors URL, hors nombres nus (`600`, `x=848`)."""
    if not text:
        return set()
    cleaned = _URL_RE.sub(" ", str(text))
    return {int(m) for m in _REF_RE.findall(cleaned)}


def title_tokens(title) -> list:
    """Tokens significatifs d'un titre (minuscules, sans mots vides ni ponctuation)."""
    words = re.findall(r"[0-9a-zà-ÿ]+", str(title or "").lower())
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS]


def title_overlap(a, b) -> float:
    """Similarité de Jaccard entre deux ensembles de tokens de titre."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _parent_number(issue: dict, ctx: dict) -> int | None:
    """Numéro du parent d'une issue, lu d'où il est RÉELLEMENT disponible.

    Deux sources, dans cet ordre :
      1. `ctx['parents']` — la table pré-alimentée par l'appelant (une seule passe
         réseau, cf. `coverage_context()`) ;
      2. le repli sur `issue['parent']` — `gh issue list --json …,parent` rend
         `{"number": N, …}`, un DICT, pas un entier. Le lire comme un int donne
         `None` et l'exemption du parent est SILENCIEUSEMENT perdue (mesuré).
    """
    parents = ctx.get("parents")
    if isinstance(parents, dict):
        p = parents.get(int(issue.get("number") or 0))
        if p is not None:
            return int(p["number"]) if isinstance(p, dict) else int(p)
    raw = issue.get("parent")
    if isinstance(raw, dict):
        return int(raw["number"]) if raw.get("number") else None
    if raw:
        return int(raw)
    return None


def coverage_verdict(issue: dict, ctx: dict) -> dict:
    """Cette issue recouvre-t-elle du travail en vol ? (verdict + raison).

    ctx = {open_issues: {n}, open_pr_issues: {n}, graph_issues: {n}, titles: {n: str},
           parents: {n: parent|None}}

    L'exemption de l'enfant de décision est une **soustraction**, jamais un
    court-circuit : `overlaps = (refs | hits_titre) - {parent} - {self}`, bloqué si
    le reste est non vide. « parent ⇒ blocked=False » laisserait passer une enfant
    qui cite son parent ET une autre issue en vol.
    """
    n = int(issue.get("number") or 0)
    in_flight = set(ctx.get("open_pr_issues") or set()) | set(ctx.get("graph_issues") or set())
    parent = _parent_number(issue, ctx)
    # Soustraction AVANT toute passe (références ET titres) : l'exemption du parent
    # ne doit pas seulement écarter la référence textuelle, elle doit aussi empêcher
    # la passe de recouvrement de TITRE de le réintroduire (une enfant de décision
    # porte « Décision — carte … », un parent un titre quelconque : le garde-fou
    # reste, mais l'ordre est explicite).
    exempt = {n} | ({parent} if parent else set())
    in_flight -= exempt
    self_refs = exempt

    overlaps = sorted(issue_refs(issue.get("body")) & in_flight)

    # Recouvrement de titre : la référence explicite peut manquer (vécu #9 → #4).
    tokens = title_tokens(issue.get("title"))
    titles = ctx.get("titles") or {}
    for other in sorted(in_flight - set(overlaps)):
        if title_overlap(tokens, title_tokens(titles.get(other))) >= TITLE_OVERLAP_THRESHOLD:
            overlaps.append(other)
    overlaps = sorted(set(overlaps) - self_refs)

    if not overlaps:
        return {"blocked": False, "overlaps": [], "reason": ""}
    refs = ", ".join(f"#{o}" for o in overlaps)
    return {"blocked": True, "overlaps": overlaps,
            "reason": (f"recouvre du travail en vol : {refs} "
                       f"(PR ouverte / graphe déjà construit)")}


def closes_line(issue_number: int) -> str:
    """Ligne de fermeture NATIVE à mettre dans le body de la PR.

    Vérifié : la PR #7 de dino-game n'avait AUCUN `closingIssuesReferences` —
    GitHub ne la liait donc pas à l'issue #4 et la fermeture dépendait du seul pont.
    """
    return f"Closes #{int(issue_number)}"


def ensure_label(name: str, color: str, description: str) -> None:
    """Crée un label s'il n'existe pas (idempotent)."""
    r = subprocess.run(
        [GH_BIN, "label", "create", name, "--repo", GH_REPO,
         "--color", color, "--description", description],
        capture_output=True, text=True)
    if r.returncode != 0 and "already exists" not in r.stderr:
        # C2 — l'échec est BRUYANT : le nom du label ET le stderr de `gh` tracés,
        # puis l'exception remonte (jamais avalée) : le geste proposé par la trappe
        # ne doit jamais être une promesse en l'air.
        log(f"  ⛔ création du label '{name}' échouée : {(r.stderr or '').strip()[:200]}")
        raise RuntimeError(f"gh label create {name}\n{r.stderr.strip()}")


def ensure_mirror_label() -> None:
    """Crée le label miroir s'il n'existe pas (idempotent)."""
    ensure_label(MIRROR_LABEL, MIRROR_LABEL_COLOR,
                 "Issue miroir d'une carte kanban Hermes")


def ensure_import_override_label() -> None:
    """Crée le label d'échappatoire du gate s'il n'existe pas (idempotent).

    Nécessaire pour que la trappe ne mente pas : le texte corrigé propose de
    « poser le label `pj-import` », or `gh issue edit --add-label` sur un label
    INEXISTANT échoue (« could not add label: 'pj-import' not found ») et
    `gh issue create --label <inconnu>` ne crée rien. Mesuré : `pj-import` est
    absent de la liste des labels du dépôt — nommer une échappatoire inapplicable
    reproduirait le défaut d'origine sous un autre nom.
    """
    ensure_label(IMPORT_OVERRIDE_LABEL, IMPORT_OVERRIDE_LABEL_COLOR,
                 "Import forcé malgré le gate de couverture (décision humaine)")


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
    """Issues ouvertes, `parent` INCLUS.

    `parent` doit être demandé ici et pas dans une passe séparée : c'est le même
    appel réseau, et une passe supplémentaire par issue serait payée à chaque tick.
    """
    out = gh("issue", "list", "--repo", GH_REPO, "--state", "open",
             "--json", "number,title,body,url,labels,createdAt,parent")
    return json.loads(out) or []


def issue_has_label(issue: dict, label: str) -> bool:
    return any(l.get("name") == label for l in issue.get("labels") or [])


def issues_with_open_pr() -> set:
    """Numéros d'issues couvertes par une PR OUVERTE.

    Deux sources : le lien natif GitHub (`closingIssuesReferences`) ET la
    convention du pipeline (`feat/issue-<n>` dans la branche). La convention est
    nécessaire car toutes les PR du pipeline ne portent pas le lien natif —
    vérifié : la PR #7 de dino-game n'en avait aucun.
    """
    out = gh("pr", "list", "--repo", GH_REPO, "--state", "open",
             "--json", "number,headRefName,closingIssuesReferences") or "[]"
    found = set()
    for pr in json.loads(out) or []:
        refs = pr.get("closingIssuesReferences") or []
        found |= {int(r["number"]) for r in refs if r.get("number")}
        m = re.search(r"issue[-_/](\d+)", str(pr.get("headRefName") or ""))
        if m:
            found.add(int(m.group(1)))
    return found


def issues_with_graph() -> set:
    """Numéros d'issues ayant DÉJÀ un graphe déployé sur le board.

    ANCRAGE STRICT — deux sources seulement, jamais les `#N` libres du corps :
      (a) la ligne d'import que `pull()` ajoute à la carte racine,
          « Importé depuis …/issues/<n> » ;
      (b) le titre du gabarit de graphe, « t<n> … #N ».
    La version naïve ramassait TOUS les `#N` cités par une carte `t1…t6` : une
    carte `t6` parlant de « la PR #7 de <autre repo> » inscrivait un numéro
    d'issue INEXISTANT dans la liste des graphes (mesuré : [1, 2, 4, 5, 7] alors
    que `gh issue view 7` répond « Could not resolve »), et une future #7 de ce
    dépôt aurait été refusée à l'import sur un fantôme.
    """
    tasks = json.loads(kanban("list", "--json") or "[]")
    found = set()
    for t in tasks:
        body = str(t.get("body") or "")
        for line in body.splitlines():
            if "Importé depuis" in line:
                for m in _IMPORT_URL_RE.finditer(line):
                    found.add(int(m.group(1)))
        title = str(t.get("title") or "").strip()
        if _GRAPH_TITLE_RE.match(title):
            for m in re.finditer(r"#(\d+)", title):
                found.add(int(m.group(1)))
    return found


def open_issue_titles() -> dict:
    """{numéro: titre} des issues ouvertes — pour le recouvrement de titre."""
    return {int(i["number"]): i.get("title") or "" for i in list_open_issues()}


def issue_parents(issues: list[dict]) -> dict:
    """{numéro: numéro du parent | None} — lu depuis la MÊME liste d'issues.

    Aucune passe réseau supplémentaire : `list_open_issues()` demande déjà `parent`.
    """
    parents = {}
    for i in issues:
        raw = i.get("parent")
        if isinstance(raw, dict):
            parents[int(i["number"])] = int(raw["number"]) if raw.get("number") else None
        elif raw:
            parents[int(i["number"])] = int(raw)
        else:
            parents[int(i["number"])] = None
    return parents


def coverage_context(titles: dict, issues: list[dict] | None = None) -> dict:
    """Contexte du gate de couverture (une passe réseau, réutilisable).

    `issues` est la liste DÉJÀ chargée par l'appelant : la passer évite un second
    `gh issue list` et permet d'en dériver `parents` sans appel supplémentaire.
    """
    ctx = {"open_pr_issues": issues_with_open_pr(),
           "graph_issues": issues_with_graph(),
           "titles": titles}
    ctx["open_issues"] = set(titles)
    if issues is not None:
        ctx["parents"] = issue_parents(issues)
    return ctx


def _flag_covered_issue(issue: dict, verdict: dict) -> None:
    """Poste un commentaire sur l'issue pour rendre le chevauchement décidable.

    Le gate ne bloque pas silencieusement : l'humain est prévenu (commentaire
    GitHub + ligne de log), avec les deux issues possibles. Idempotent : le
    marqueur évite d'empiler des commentaires identiques à chaque tick.
    """
    marker = "<!-- pj-coverage-gate -->"
    n = str(issue["number"])
    existing = gh("issue", "view", n, "--repo", GH_REPO, "--json", "comments") or "{}"
    try:
        if any(marker in (c.get("body") or "")
               for c in (json.loads(existing).get("comments") or [])):
            return                      # déjà signalée : ne pas empiler
    except Exception:
        pass
    refs = ", ".join(f"#{o}" for o in verdict.get("overlaps") or [])
    body = (
        f"{marker}\n\n"
        f"## ⛔ Import suspendu — cette issue recouvre du travail en vol\n\n"
        f"{verdict.get('reason')}\n\n"
        f"**Décider :**\n"
        f"1. **Rattacher** au travail en vol ({refs}) — commenter ici la décision, "
        f"le pipeline poursuivra sur l'issue existante ;\n"
        f"2. **Nouvelle tâche assumée** — poser le label `{IMPORT_OVERRIDE_LABEL}` sur cette "
        f"issue ; le pont l'importera au tick suivant.\n\n"
        f"Rien n'est lancé tant que cette décision n'est pas prise."
    )
    r = subprocess.run([GH_BIN, "issue", "comment", str(issue["number"]),
                        "--repo", GH_REPO, "--body", body],
                       capture_output=True, text=True)
    if r.returncode != 0:
        log(f"  (commentaire de couverture non posté sur #{issue['number']}: "
            f"{(r.stderr or '').strip()[:120]})")


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
        # `decision` = objet de décision (l'issue enfant d'une carte bloquée) :
        # ce n'est PAS une tâche, son import déclencherait un graphe complet sous
        # une carte de décision. Écarté par le même prédicat, AVANT le gate.
        if MIRROR_LABEL in labels or TRIAGE_LABEL in labels or DECISION_LABEL in labels:
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

    # RENFO 1 — gate de couverture : une issue qui recouvre du travail en vol ne
    # lance PAS un nouveau graphe. On la signale et on la laisse en attente de
    # décision humaine (le label miroir n'est pas posé, donc elle reste visible).
    covered = []
    if to_import:
        try:
            titles = {int(i["number"]): i.get("title") or "" for i in issues}
            ctx = coverage_context(titles, issues)
            kept, covered = [], []
            for i in to_import:
                labels = {l.get("name") for l in (i.get("labels") or [])}
                if IMPORT_OVERRIDE_LABEL in labels:
                    # ÉCHAPPATOIRE RÉELLE : l'humain a assumé une nouvelle tâche.
                    # Le gate la RESPECTE — on le lit AVANT le verdict, sinon la
                    # trappe serait un mensonge autrement formulé (défaut mesuré).
                    log(f"  ↷ issue #{i['number']} importée malgré le gate "
                        f"(label '{IMPORT_OVERRIDE_LABEL}' posé à la main)")
                    kept.append((i, {"blocked": False, "overlaps": [], "reason": ""}))
                    continue
                v = coverage_verdict(i, ctx)
                (covered if v["blocked"] else kept).append((i, v))
            to_import = [i for i, _ in kept]
        except Exception as e:
            log(f"  gate de couverture indisponible ({type(e).__name__}: {e}) — pull sans gate")
            covered = []        # rien n'a été tranché sur ce tick : aucune trappe à poster

    # slice 2b — ORDRE (C1) : le label d'échappatoire est assuré AVANT le premier
    # commentaire de trappe du tick, et INDÉPENDAMMENT de `to_import`. La trappe
    # propose « poser le label `pj-import` » : si ce label n'existe pas, le geste est
    # inexécutable (`could not add label: 'pj-import' not found`). Mesuré : quand la
    # SEULE candidate du tick est couverte, `to_import` est vidé par le gate (L491),
    # donc l'ancien garde `if to_import and not DRY_RUN:` ne créait jamais le label
    # exactement dans le tick où la trappe parle.
    # Cas (a) : une trappe va être postée. Cas (b) : une issue sera importée.
    # Un seul appel de création d'échappatoire par tick (idempotent côté gh).
    if not DRY_RUN and (covered or to_import):
        if to_import:
            ensure_mirror_label()
        ensure_import_override_label()

    if covered:
        try:
            for i, v in covered:
                log(f"  ⛔ issue #{i['number']} NON importée — {v['reason']}. "
                    f"Décider : rattacher à {', '.join('#'+str(o) for o in v['overlaps'])} "
                    f"(commenter l'issue) ou assumer une nouvelle tâche "
                    f"(poser le label '{IMPORT_OVERRIDE_LABEL}' puis laisser le pont passer).")
                _flag_covered_issue(i, v)
        except Exception as e:
            # Le signalement du chevauchement ne doit pas emporter le tick (les imports
            # du même tick restent valides) — mais il est TRACÉ, jamais muet. La
            # création du label (C2) est HORS de ce `try` : elle ne peut pas être avalée.
            log(f"  signalement du chevauchement indisponible ({type(e).__name__}: {e})")

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
        if os.environ.get("PJ_IMPORT_TRIAGE") == "1":
            # Pipeline pj : la racine reste en triage ; le cron agent pj-master déploie
            # le mini-graphe t1..t5 + liens puis la promeut (elle attend le graphe).
            create_cmd.append("--triage")
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
    """Numéro d'issue GitHub lié à une carte — ANCRÉ sur la ligne d'import.

    Le champ idempotency_key n'est pas exposé dans l'API JSON kanban : on déduit
    le numéro de la ligne que `pull()` a ÉCRITE lui-même,
    « Importé depuis https://github.com/<repo>/issues/<n> ».

    La règle est ANCRÉE EN TÊTE DE LIGNE, jamais un `re.search` sur tout le body.
    Mesuré sur le board réel : un body peut citer une AUTRE issue avant sa propre
    ligne d'import (une issue en prose, le gabarit `Issue GitHub : …/issues/N` du
    t6, un exemple de sous-chaîne `/issues/5` ⊂ `/issues/40`), et le premier
    `/issues/<n>` du texte n'est alors pas le sien. Une carte `done` fermerait
    l'issue d'un autre — c'est le défaut que ce correctif ferme.

    Aucune ligne d'import ⇒ None : `push()` ignore la carte et ne ferme rien.
    """
    body = task.get("body") or ""
    for line in body.splitlines():
        if not _IMPORT_LINE_RE.match(line):
            continue
        m = re.search(r"github\.com/%s/issues/(\d+)" % re.escape(GH_REPO), line)
        if m:
            return int(m.group(1))
    return None


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
    """Issues ouvertes sans label 'kanban', 'triage' ni 'decision' — candidates au drill.

    Un objet de décision (`decision`) n'est pas une tâche : le même prédicat que
    `pull()` l'écarte, sinon le drill lui construirait un graphe complet.
    """
    issues = list_open_issues()
    fresh = [i for i in issues
             if not issue_has_label(i, MIRROR_LABEL)
             and not issue_has_label(i, TRIAGE_LABEL)
             and not issue_has_label(i, DECISION_LABEL)]
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