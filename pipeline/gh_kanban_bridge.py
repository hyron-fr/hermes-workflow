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


def coverage_verdict(issue: dict, ctx: dict) -> dict:
    """Cette issue recouvre-t-elle du travail en vol ? (verdict + raison).

    ctx = {open_issues: {n}, open_pr_issues: {n}, graph_issues: {n}, titles: {n: str}}
    """
    n = int(issue.get("number") or 0)
    in_flight = set(ctx.get("open_pr_issues") or set()) | set(ctx.get("graph_issues") or set())
    in_flight.discard(n)                      # une issue ne se recouvre pas elle-même

    overlaps = sorted(issue_refs(issue.get("body")) & in_flight)

    # Recouvrement de titre : la référence explicite peut manquer (vécu #9 → #4).
    tokens = title_tokens(issue.get("title"))
    titles = ctx.get("titles") or {}
    for other in sorted(in_flight - set(overlaps)):
        if title_overlap(tokens, title_tokens(titles.get(other))) >= TITLE_OVERLAP_THRESHOLD:
            overlaps.append(other)
    overlaps = sorted(set(overlaps))

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

    Détection par les cartes : la racine d'un graphe porte la ligne
    « Importé depuis .../issues/<n> », ou à défaut un titre « #<n> ».
    """
    tasks = json.loads(kanban("list", "--json") or "[]")
    found = set()
    for t in tasks:
        if t.get("title", "").startswith(("t1 ", "t2 ", "t3 ", "t4 ", "t5 ", "t3b", "t6 ")):
            for m in re.finditer(r"#(\d+)", str(t.get("body") or "") + str(t.get("title") or "")):
                found.add(int(m.group(1)))
        body = t.get("body") or ""
        for m in re.finditer(r"/issues/(\d+)", body):
            found.add(int(m.group(1)))
    return found


def open_issue_titles() -> dict:
    """{numéro: titre} des issues ouvertes — pour le recouvrement de titre."""
    return {int(i["number"]): i.get("title") or "" for i in list_open_issues()}


def coverage_context(titles: dict) -> dict:
    """Contexte du gate de couverture (une passe réseau, réutilisable)."""
    ctx = {"open_pr_issues": issues_with_open_pr(),
           "graph_issues": issues_with_graph(),
           "titles": titles}
    ctx["open_issues"] = set(titles)
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
        f"2. **Nouvelle tâche assumée** — poser le label `{MIRROR_LABEL}` sur cette "
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

    # RENFO 1 — gate de couverture : une issue qui recouvre du travail en vol ne
    # lance PAS un nouveau graphe. On la signale et on la laisse en attente de
    # décision humaine (le label miroir n'est pas posé, donc elle reste visible).
    if to_import:
        try:
            titles = {int(i["number"]): i.get("title") or "" for i in issues}
            ctx = coverage_context(titles)
            kept, covered = [], []
            for i in to_import:
                v = coverage_verdict(i, ctx)
                (covered if v["blocked"] else kept).append((i, v))
            for i, v in covered:
                log(f"  ⛔ issue #{i['number']} NON importée — {v['reason']}. "
                    f"Décider : rattacher à {', '.join('#'+str(o) for o in v['overlaps'])} "
                    f"(commenter l'issue) ou assumer une nouvelle tâche "
                    f"(poser le label '{MIRROR_LABEL}' puis laisser le pont passer).")
                _flag_covered_issue(i, v)
            to_import = [i for i, _ in kept]
        except Exception as e:
            log(f"  gate de couverture indisponible ({type(e).__name__}: {e}) — pull sans gate")

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