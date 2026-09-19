#!/usr/bin/env python3
"""pj_graphwatch — construit le graphe de développement d'une issue, DÉTERMINISTEMENT.

Remplace la création de graphe par LLM (source de dérives : cartes fantômes,
assignees hors pipeline, liens inverses). Lit le `slices.json` écrit par t5, puis crée
toutes les cartes et tous les liens.

Topologie produite (sens : `link <parent> <enfant>` = l'enfant attend le parent) :

  t5 -> t6
  t6 -> worktree-mk                      (crée le worktree, poste chemin+branche)
  pour chaque slice k :
    worktree-mk -> test-k  ┐  PARALLÈLE, même worktree, même branche
    worktree-mk -> dev-k   ┘  (peer programming : RED ∥ GREEN)
    {test-k, dev-k} -> conv-k            (boucle de convergence)
    conv-k -> doc-k
    conv-j -> {test-k, dev-k} si j ∈ depends_on
  {conv-k, doc-k, doc-review, worktree-mk} -> t6    (ANTI-DEADLOCK)
  t6 -> worktree-rm                      (post-merge : nettoyage du worktree)
  worktree-rm -> doc-memory              (alimentation Hindsight)
  {t6, doc-memory} -> racine             (le pont ferme l'issue)

Usage (cron no-agent, stdout vide = tick muet) :
  pj_graphwatch.py run
Variables : PJ_BOARD (obligatoire), PJ_VERBOSE=1, PJ_DRY_RUN=1
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERMES_BIN = os.environ.get("PJ_HERMES_BIN") or os.path.expanduser(
    "~/.hermes/hermes-agent/venv/bin/hermes")
BOARD = os.environ.get("PJ_BOARD", "")
VERBOSE = os.environ.get("PJ_VERBOSE") == "1"
DRY = os.environ.get("PJ_DRY_RUN") == "1"
SPECS_ROOT = Path.home() / ".hermes" / "kanban" / "boards"
ANCHOR_ROOT = "${HOME}/pj-repos"
IMPORT_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/issues/(\d+)")


def log(msg: str) -> None:
    print(f"[pj-graph] {msg}")


def sh(*args: str, timeout: int = 120):
    cmd = [HERMES_BIN, "kanban", "--board", BOARD, *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def _wt_path(branch: str) -> str:
    return branch.replace("/", "-")


def build_plan(doc: dict, t5_id: str, board: str, root_id: str) -> dict:
    """Plan pur (testable) : {"cards": [...], "links": [[parent, child], ...]}."""
    repo = doc["repo"]
    anchor = f"{ANCHOR_ROOT}/{repo}"
    branch = doc["branch"]
    issue = doc["issue"]
    wt_name = _wt_path(branch)

    cards = [
        {"key": "t6", "title": f"t6 submitted #{issue}", "assignee": "pj-master",
         "workspace": "scratch", "branch": None, "parents": [t5_id],
         "body": (f"Ouvrir la PR de l'issue #{issue} ({repo}) une fois toutes les cartes "
                  f"de convergence et de doc done. Vérifier les conclusions de checks CI "
                  f"vertes sur le head SHA exact, poster l'URL de la PR en commentaire de "
                  f"cette carte, de l'issue et sur Discord. Ne jamais merger.")},
        {"key": "worktree-mk", "title": f"worktree-mk #{issue} : créer le worktree",
         "assignee": "pj-dev", "workspace": f"worktree:{anchor}", "branch": branch,
         "parents": ["t6"],
         "body": (f"Créer le worktree de travail de l'issue #{issue} ({repo}) sur la branche "
                  f"`{branch}` (base `dev`) :\n"
                  f"`git -C {anchor} fetch origin && git -C {anchor} worktree add "
                  f".worktrees/{wt_name} -b {branch} origin/dev`\n"
                  f"Puis POSTER sur le blackboard de la racine la clé `worktree` = "
                  f"{{\"path\": \"{anchor}/.worktrees/{wt_name}\", \"branch\": \"{branch}\", "
                  f"\"base\": \"dev\"}} (commentaire `[swarm:blackboard] "
                  f"{{\"key\": \"worktree\", \"value\": {{...}}}}`).\n"
                  f"Toutes les cartes de slice partagent CE worktree : elles déclarent le même "
                  f"workspace ET la même branche. Prouver avec `git worktree list` en commentaire.")},
        {"key": "worktree-rm", "title": f"worktree-rm #{issue} : nettoyer le worktree",
         "assignee": "pj-dev", "workspace": "scratch", "branch": None, "parents": ["t6"],
         "body": (f"POST-MERGE uniquement : la PR de l'issue #{issue} doit être MERGED "
                  f"(`gh pr view <url> --json state` == MERGED). Vérifier que tous les commits "
                  f"de `{branch}` sont dans dev (`git merge-base --is-ancestor origin/{branch} "
                  f"origin/dev`), puis :\n"
                  f"`git -C {anchor} worktree remove .worktrees/{wt_name} --force`\n"
                  f"`git -C {anchor} branch -D {branch}` et suppression de la branche distante.\n"
                  f"Poster `git worktree list` en commentaire. Si du travail n'est pas mergé : "
                  f"`kanban_block` au lieu de supprimer.")},
    ]

    for s in doc["slices"]:
        k = s["k"]
        par = s["parallel"]
        upstream = [f"conv-{d}" for d in (s.get("depends_on") or [])]
        both = ["worktree-mk"] + upstream
        cards.append({"key": f"test-{k}", "title": par["test"]["title"],
                      "assignee": "pj-test", "workspace": f"worktree:{anchor}",
                      "branch": branch, "parents": list(both),
                      "body": par["test"]["body"]})
        cards.append({"key": f"dev-{k}", "title": par["dev"]["title"],
                      "assignee": "pj-dev", "workspace": f"worktree:{anchor}",
                      "branch": branch, "parents": list(both),
                      "body": par["dev"]["body"]})
        cards.append({"key": f"conv-{k}", "title": s["convergence"]["title"],
                      "assignee": "pj-test", "workspace": f"worktree:{anchor}",
                      "branch": branch, "parents": [f"test-{k}", f"dev-{k}"],
                      "body": s["convergence"]["body"]})
        cards.append({"key": f"doc-{k}", "title": s["doc"]["title"],
                      "assignee": "pj-doc", "workspace": f"worktree:{anchor}",
                      "branch": branch, "parents": [f"conv-{k}"],
                      "body": s["doc"]["body"]})

    conv_keys = [f"conv-{s['k']}" for s in doc["slices"]]
    doc_keys = [f"doc-{s['k']}" for s in doc["slices"]]

    cards.append({"key": "doc-review", "title": f"doc-review #{issue}",
                  "assignee": "pj-doc", "workspace": "scratch", "branch": None,
                  "parents": doc_keys,
                  "body": (f"Review de cohérence pour l'issue #{issue} ({repo}) : "
                           f"(1) le code livré respecte l'objectif de l'issue ; (2) le vault "
                           f"docs/ est cohérent avec le code (composants, ADR, features) ; "
                           f"(3) aucune note orpheline ni lien mort. Preuve : "
                           f"`python3 <hermes-workflow>/pipeline/pj_docs_lint.py {anchor}` doit sortir "
                           f"exit 0. Poster le verdict en commentaire ; en cas d'écart, "
                           f"`kanban_block` avec la liste précise.")})
    cards.append({"key": "doc-memory", "title": f"doc-memory #{issue}",
                  "assignee": "pj-doc", "workspace": "scratch", "branch": None,
                  "parents": ["worktree-rm"],
                  "body": (f"POST-MERGE (après worktree-rm). Alimenter Hindsight (banque pj, "
                           f"tags project:{repo}, doc:<path>, issue:{issue}) avec les notes du "
                           f"vault docs/ :\n"
                           f"`python3 <hermes-workflow>/pipeline/pj_docs_memory.py --repo {anchor} "
                           f"--issue {issue}`\n"
                           f"Poster le compte d'envois (envoyés/inchangés/échecs) en commentaire.")})

    links = []
    # Anti-deadlock : les cartes de production sont PARENTS de t6.
    for key in conv_keys + doc_keys + ["worktree-mk", "doc-review"]:
        links.append(["t6", key])
    # Chaîne finale : PR -> nettoyage -> mémoire -> fermeture de l'issue.
    links.append(["t6", "worktree-rm"])
    links.append(["worktree-rm", "doc-memory"])
    links.append(["t6", root_id])
    links.append(["doc-memory", root_id])
    return {"cards": cards, "links": links}


def find_submitted_cards() -> list:
    """Cartes 't6 submitted' actives sans enfants (graphe pas encore construit)."""
    out = json.loads(sh("list", "--json") or "[]")
    found = []
    for t in out:
        title = (t.get("title") or "").strip()
        if not re.match(r"^t6 submitted\b", title, re.I):
            continue
        if t.get("status") not in ("todo", "ready"):
            continue
        show = json.loads(sh("show", t["id"], "--json"))
        if show.get("children"):
            continue
        found.append((t, show))
    return found


def specs_path(issue: int) -> Path:
    return SPECS_ROOT / BOARD / "specs" / str(issue) / "slices.json"


def _find_root(issue: int) -> str:
    """Racine = carte dont le body cite l'URL d'import de l'issue."""
    for cand in json.loads(sh("list", "--json") or "[]"):
        if f"/issues/{issue}" in (cand.get("body") or ""):
            return cand["id"]
    return ""


def main() -> int:
    if not BOARD:
        log("PJ_BOARD manquant")
        return 1
    acted = 0
    for t6, show in find_submitted_cards():
        blob = (t6.get("body") or "") + "\n" + json.dumps(show.get("comments", []), default=str)
        m = IMPORT_RE.search(blob)
        if not m:
            continue
        issue = int(m.group(3))
        sp = specs_path(issue)
        if not sp.exists():
            log(f"t6 {t6['id']}: slices.json absent ({sp}) — t5 doit le produire")
            continue
        try:
            doc = json.loads(sp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            log(f"t6 {t6['id']}: slices.json invalide ({e}) — request-changes sur t5")
            continue

        parents = [p.get("id") if isinstance(p, dict) else p for p in (show.get("parents") or [])]
        t5_id = parents[0] if parents else ""
        root = _find_root(issue)
        if not root:
            log(f"t6 {t6['id']}: racine introuvable — skip")
            continue

        plan = build_plan(doc, t5_id=t5_id, board=BOARD, root_id=root)
        if DRY:
            print(json.dumps(plan, indent=2))
            return 0

        ids = {}
        for c in plan["cards"]:
            args = ["create", c["title"], "--assignee", c["assignee"],
                    "--body", c["body"], "--workspace", c["workspace"],
                    "--idempotency-key", f"pj-{c['key']}-{doc['repo']}-{issue}", "--json"]
            if c.get("branch"):
                args += ["--branch", c["branch"]]
            for p in c["parents"]:
                args += ["--parent", ids.get(p, p)]
            ids[c["key"]] = json.loads(sh(*args))["id"]
        for parent, child in plan["links"]:
            sh("link", ids.get(parent, parent), ids.get(child, child))
        sh("comment", root, "Graphe de dev construit : "
           + ", ".join(f"{k}={v}" for k, v in ids.items()))
        log(f"issue #{issue} ({doc['repo']}) : graphe construit ({len(ids)} cartes)")
        acted += 1
    if not acted and VERBOSE:
        log("rien à faire")
    return 0


if __name__ == "__main__":
    sys.exit(main())
