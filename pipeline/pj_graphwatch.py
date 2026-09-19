#!/usr/bin/env python3
"""pj_graphwatch — construit le graphe de développement d'une issue, DÉTERMINISTEMENT.

Remplace la création de graphe par LLM (source de dérives : cartes fantômes,
assignees hors pipeline, liens inverses). Lit le `slices.json` écrit par t5, puis crée
toutes les cartes et tous les liens.

QUI CRÉE `t6` : le worker **t5** (carte `t6 submitted #<n>`, assignee `pj-master`,
`--parent <t5>`). `find_submitted_cards()` ne réagit qu'à cette carte EXISTANTE, et le
plan RÉUTILISE son id au lieu d'en créer une seconde : sinon la carte créée par t5
resterait sans enfant (donc re-sélectionnée à chaque tick) et chaque tick reconstruirait
un graphe en double.

CONTRAT DE WORKSPACE — un seul worktree par issue (c'est lui qui rend le peer
programming possible) :

  * le chemin du worktree partagé est soit déclaré par `slices.json` (`worktree_path`,
    optionnel : relatif à l'anchor ou absolu — c'est ainsi qu'on ADOPTE un worktree déjà
    matérialisé, ex. `.worktrees/t_109333ba` créé par t1), soit déduit du nom canonique
    `<anchor>/.worktrees/<branche, '/' -> '-'>` ;
  * TOUTES les cartes de slice ET `worktree-mk` déclarent le MÊME chemin de worktree et
    la MÊME branche. C'est le **dispatcher** qui matérialise le worktree (une fois, à la
    première carte dispatchée) ; les cartes suivantes le réutilisent
    (`_resolve_worktree_workspace` : `actual_branch == branch_name` => retour direct).
    Déclarer `worktree:<anchor>` (le dépôt nu) faisait viser à chaque carte
    `.worktrees/<son propre id>` sur la même branche => `fatal: '<branche>' is already
    used by worktree at '…'` => `spawn_failed` => auto_block ;
  * `worktree-mk` ne crée donc PLUS de worktree : il VÉRIFIE (branche courante == branche
    attendue) et publie la clé `worktree` sur le blackboard de la racine ;
  * si la branche visée est déjà tenue par un worktree d'un chemin DIFFÉRENT, le plan
    échoue explicitement (`WorktreeConflict`) AVANT toute création de carte — jamais de
    `spawn_failed` silencieux.

Topologie produite (sens : `link <parent> <enfant>` = l'enfant attend le parent) :

  t5 -> t6                               (t6 est créée par t5, pas par ce script)
  t5 -> worktree-mk                      (le worktree partagé est vérifié après le GO)
  pour chaque slice k :
    worktree-mk -> test-k  ┐  PARALLÈLE, même worktree, même branche
    worktree-mk -> dev-k   ┘  (peer programming : RED ∥ GREEN)
    {test-k, dev-k} -> conv-k            (boucle de convergence)
    conv-k -> doc-k
    conv-j -> {test-k, dev-k} si j ∈ depends_on
  {worktree-mk, conv-k, doc-k, doc-review} -> t6    (ANTI-DEADLOCK :
      la PR attend TOUTES les cartes de production — t6 n'est jamais en amont d'elles)
  t6 -> worktree-rm                      (post-merge : nettoyage du worktree)
  worktree-rm -> doc-memory              (alimentation Hindsight)
  {t6, doc-memory} -> racine             (le pont ferme l'issue)

⚠️ Le sens est ÉPINGLÉ par `check_topology()` (appelée par `build_plan_checked`, donc avant
toute création de carte) : un commentaire ne suffit pas — l'erreur historique était
exactement un commentaire « anti-deadlock » contredisant le code (`link t6 <production>`
fait ATTENDRE la production, donc `t6` devenait `ready` dès `t5` done et ouvrait la PR
avant que la moindre slice n'existe).

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


class WorktreeConflict(RuntimeError):
    """La branche de l'issue est tenue par un worktree autre que celui déclaré."""


def log(msg: str) -> None:
    print(f"[pj-graph] {msg}")


def sh(*args: str, timeout: int = 120):
    cmd = [HERMES_BIN, "kanban", "--board", BOARD, *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def _wt_path(branch: str) -> str:
    """Nom de répertoire canonique d'une branche (`wt/issue-8` -> `wt-issue-8`)."""
    return branch.replace("/", "-")


def shared_worktree_path(doc: dict, anchor: str) -> str:
    """Chemin ABSOLU du worktree partagé de l'issue.

    `worktree_path` (optionnel) permet d'ADOPTER un worktree déjà matérialisé ; sans lui
    on retombe sur le nom canonique `<anchor>/.worktrees/<branche>`.
    """
    raw = str(doc.get("worktree_path") or "").strip()
    if not raw:
        return f"{anchor}/.worktrees/{_wt_path(str(doc.get('branch') or ''))}"
    if raw.startswith("~"):
        raise ValueError(
            "worktree_path ne peut pas commencer par '~' : chemin explicite attendu")
    if raw == "/":
        raise ValueError("worktree_path ne peut pas être la racine '/'")
    if ".." in Path(raw).parts:
        raise ValueError(f"worktree_path {raw!r} contient '..' (sortie de l'anchor interdite)")
    return raw if raw.startswith("/") else os.path.normpath(f"{anchor}/{raw}")


def parse_worktrees(porcelain: str) -> dict:
    """{branche -> chemin} depuis la sortie de `git worktree list --porcelain`."""
    holders, cur = {}, None
    for line in (porcelain or "").splitlines():
        if line.startswith("worktree "):
            cur = line.split(" ", 1)[1].strip()
        elif line.startswith("branch ") and cur:
            ref = line.split(" ", 1)[1].strip()
            if ref.startswith("refs/heads/"):
                holders[ref[len("refs/heads/"):]] = cur
    return holders


def worktree_holders(anchor: str) -> dict:
    """{branche -> chemin} des worktrees du dépôt `anchor` (lecture seule)."""
    r = subprocess.run(["git", "-C", anchor, "worktree", "list", "--porcelain"],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise WorktreeConflict(
            f"`git worktree list` impossible dans {anchor!r} "
            f"({(r.stderr or r.stdout).strip()[:200]}) — anchor absent ou non-git")
    return parse_worktrees(r.stdout)


def _same_path(a: str, b: str) -> bool:
    return os.path.realpath(a) == os.path.realpath(b)


def preflight_worktree(plan: dict, holders=None) -> None:
    """Vérifie le contrat de worktree AVANT toute création de carte.

    Trois cas : aucun worktree ne tient la branche (le dispatcher matérialisera) => OK ;
    le chemin déclaré tient DÉJÀ la branche (adoption) => OK ; un AUTRE chemin la tient
    => `WorktreeConflict` nommant la branche, le worktree fautif et le remède.
    """
    wt = plan["worktree"]
    holders = worktree_holders(wt["anchor"]) if holders is None else holders
    holder = holders.get(wt["branch"])
    if holder is None or _same_path(holder, wt["path"]):
        return
    remedy = os.path.relpath(holder, wt["anchor"])
    raise WorktreeConflict(
        f"branche {wt['branch']!r} déjà tenue par le worktree {holder!r}, alors que le "
        f"plan déclare {wt['path']!r}. Remède : ajouter \"worktree_path\": \"{remedy}\" "
        f"au slices.json (adoption du worktree existant), ou choisir une autre branche. "
        f"AUCUNE carte n'a été créée.")


def build_plan(doc: dict, t5_id: str, board: str, root_id: str) -> dict:
    """Plan pur (testable) : {"cards": [...], "links": [[parent, child], ...], "worktree": {...}}."""
    repo = doc["repo"]
    anchor = f"{ANCHOR_ROOT}/{repo}"
    branch = doc["branch"]
    issue = doc["issue"]
    shared = shared_worktree_path(doc, anchor)
    shared_rel = os.path.relpath(shared, anchor)
    wt_workspace = f"worktree:{shared}"

    cards = [
        {"key": "t6", "title": f"t6 submitted #{issue}", "assignee": "pj-master",
         "workspace": "scratch", "branch": None, "parents": [t5_id],
         "body": (f"Ouvrir la PR de l'issue #{issue} ({repo}) une fois toutes les cartes "
                  f"de convergence et de doc done. Vérifier les conclusions de checks CI "
                  f"vertes sur le head SHA exact, poster l'URL de la PR en commentaire de "
                  f"cette carte, de l'issue et sur Discord. Ne jamais merger.\n\n"
                  f"**LIEN NATIF OBLIGATOIRE** : le body de la PR doit contenir la ligne "
                  f"`Closes #{issue}` (sans elle, GitHub ne rattache PAS la PR à l'issue — "
                  f"constaté sur la PR #7 de dino-game : `closingIssuesReferences` vide — et "
                  f"la fermeture ne dépend plus que du pont, donc toute issue ouverte "
                  f"sur le même sujet repart en graphe neuf).")},
        {"key": "worktree-mk", "title": f"worktree-mk #{issue} : vérifier le worktree partagé",
         "assignee": "pj-dev", "workspace": wt_workspace, "branch": branch,
         "parents": [t5_id],
         "body": (f"Worktree PARTAGÉ de l'issue #{issue} ({repo}) : `{shared}` sur la branche "
                  f"`{branch}` (base `dev`).\n"
                  f"Le dispatcher l'a DÉJÀ matérialisé pour cette carte : ne rien créer ici "
                  f"(la branche `{branch}` est déjà tenue, toute création échouerait en "
                  f"`fatal: '{branch}' is already used by worktree`).\n"
                  f"VÉRIFIER : `git -C {shared} rev-parse --abbrev-ref HEAD` doit renvoyer "
                  f"`{branch}`, puis `git -C {anchor} worktree list`.\n"
                  f"Puis POSTER sur le blackboard de la racine la clé `worktree` = "
                  f"{{\"path\": \"{shared}\", \"branch\": \"{branch}\", \"base\": \"dev\"}} "
                  f"(commentaire `[swarm:blackboard] {{\"key\": \"worktree\", \"value\": {{...}}}}`).\n"
                  f"Toutes les cartes de slice partagent CE worktree : elles déclarent le même "
                  f"workspace ET la même branche. Coller la sortie de `git worktree list` en "
                  f"commentaire de cette carte.")},
        {"key": "worktree-rm", "title": f"worktree-rm #{issue} : nettoyer le worktree",
         "assignee": "pj-dev", "workspace": "scratch", "branch": None, "parents": ["t6"],
         "body": (f"POST-MERGE uniquement : la PR de l'issue #{issue} doit être MERGED "
                  f"(`gh pr view <url> --json state` == MERGED). Vérifier que tous les commits "
                  f"de `{branch}` sont dans dev (`git merge-base --is-ancestor origin/{branch} "
                  f"origin/dev`), puis :\n"
                  f"`git -C {anchor} worktree list` (le worktree partagé `{shared_rel}` doit "
                  f"être sur `{branch}` et AUCUNE carte de slice ne doit encore le tenir) ;\n"
                  f"`git -C {anchor} worktree remove {shared_rel} --force`\n"
                  f"`git -C {anchor} branch -D {branch}` et suppression de la branche distante.\n"
                  f"Poster `git worktree list` en commentaire. Si du travail n'est pas mergé, ou "
                  f"au moindre doute (carte de slice encore active) : `kanban_block` au lieu de "
                  f"supprimer.")},
    ]

    for s in doc["slices"]:
        k = s["k"]
        par = s["parallel"]
        upstream = [f"conv-{d}" for d in (s.get("depends_on") or [])]
        both = ["worktree-mk"] + upstream
        cards.append({"key": f"test-{k}", "title": par["test"]["title"],
                      "assignee": "pj-test", "workspace": wt_workspace,
                      "branch": branch, "parents": list(both),
                      "body": par["test"]["body"]})
        cards.append({"key": f"dev-{k}", "title": par["dev"]["title"],
                      "assignee": "pj-dev", "workspace": wt_workspace,
                      "branch": branch, "parents": list(both),
                      "body": par["dev"]["body"]})
        cards.append({"key": f"conv-{k}", "title": s["convergence"]["title"],
                      "assignee": "pj-test", "workspace": wt_workspace,
                      "branch": branch, "parents": [f"test-{k}", f"dev-{k}"],
                      "body": s["convergence"]["body"]})
        cards.append({"key": f"doc-{k}", "title": s["doc"]["title"],
                      "assignee": "pj-doc", "workspace": wt_workspace,
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
    # ANTI-DEADLOCK : les cartes de production sont PARENTS de t6 — `link <key> t6` fait
    # ATTENDRE t6 (donc la PR) jusqu'à ce que `<production>` soit done. Le sens inverse
    # (`link t6 <key>`) ferait attendre la PRODUCTION et rendrait t6 `ready` dès que t5 est
    # done : la PR partirait avec zéro slice. Sens épinglé par `check_topology()`.
    for key in conv_keys + doc_keys + ["worktree-mk", "doc-review"]:
        links.append([key, "t6"])
    # Chaîne finale : PR -> nettoyage -> mémoire -> fermeture de l'issue.
    links.append(["t6", "worktree-rm"])
    links.append(["worktree-rm", "doc-memory"])
    links.append(["t6", root_id])
    links.append(["doc-memory", root_id])
    return {"cards": cards, "links": links,
            "worktree": {"path": shared, "branch": branch, "anchor": anchor,
                         "repo": repo, "issue": issue}}


def check_topology(plan: dict, t5_id: str = "", root_id: str = "") -> None:
    """Épingle le SENS des liens du plan ; lève `ValueError` si la topologie est fausse.

    Contrat vérifié (sens : `link <parent> <enfant>` ⇒ l'enfant attend le parent) :

      * `t6` a exactement `t5` (+ la racine quand elle est connue) pour parents : c'est un
        point de CONVERGENCE, jamais un prérequis de la production ;
      * les cartes de production (`worktree-mk`, `conv-k`, `doc-k`, `doc-review`) sont
        PARENTS de `t6` — sinon la PR s'ouvre avant que les slices n'existent ;
      * `t6` n'est parent d'AUCUNE carte de production (l'inverse exact du défaut) ;
      * `t6 -> worktree-rm -> doc-memory` et `{t6, doc-memory} -> racine` restent en aval ;
      * `worktree-mk` est en amont de toutes les cartes de slice.

    Un commentaire ne suffit pas : c'est précisément un commentaire « anti-deadlock »
    contredisant le code qui a laissé passer l'inversion.
    """
    cards = {c["key"]: c for c in plan["cards"]}
    slice_cards = [k for k in cards if k.startswith(("test-", "dev-"))]
    # cartes de PRODUCTION : leur done doit être un prérequis de la PR (t6).
    # `doc-memory` est volontairement EXCLUE : elle tourne POST-MERGE (après la PR).
    producers = [k for k in cards
                 if k.startswith("conv-")
                 or (k.startswith("doc-") and k[len("doc-"):].isdigit())] \
        + ["worktree-mk", "doc-review"]
    errs = []

    # parents effectifs = parents déclarés à la création (--parent) + liens (parent -> enfant)
    parents_of = {k: set(c.get("parents") or []) for k, c in cards.items()}
    children_of = {}
    for parent, child in plan["links"]:
        parents_of.setdefault(child, set()).add(parent)
        children_of.setdefault(parent, set()).add(child)

    # 1) t6 est un point de CONVERGENCE : il attend t5 ET toutes les cartes de production,
    #    et rien d'autre. (Les liens `producer -> t6` REPASSENT t6 en `todo` si besoin :
    #    `link_tasks` fait `UPDATE tasks SET status='todo' WHERE status='ready'`.)
    t6_parents = parents_of.get("t6", set())
    if t5_id and t5_id not in t6_parents:
        errs.append(f"t6 n'attend pas t5 ('{t5_id}')")
    extra = t6_parents - set(producers) - ({t5_id} if t5_id else set())
    if extra:
        errs.append(f"t6 a des parents inattendus {sorted(extra)} (attendu t5 + production)")
    # 2) AUCUNE carte de production ne doit attendre t6 (le défaut historique)
    for key in producers + slice_cards:
        if "t6" in parents_of.get(key, set()):
            errs.append(f"{key} attend t6 : t6 doit être en AVAL de la production")
    # 3) ANTI-DEADLOCK : chaque carte de production est PARENT de t6
    for key in producers:
        if key not in parents_of.get("t6", set()):
            errs.append(f"{key} n'est pas parent de t6 : la PR ne l'attendrait pas")
    # 4) t6 ne doit être ancêtre d'aucune carte de production
    for key in producers + slice_cards:
        if key in children_of.get("t6", set()):
            errs.append(f"t6 -> {key} : la production serait en aval de la PR")
    # 5) chaîne finale : t6 -> worktree-rm -> doc-memory -> racine
    for edge in (["t6", "worktree-rm"], ["worktree-rm", "doc-memory"]):
        if edge not in [list(e) for e in plan["links"]]:
            errs.append(f"lien manquant {edge[0]} -> {edge[1]}")
    if root_id:
        for edge in (["t6", root_id], ["doc-memory", root_id]):
            if edge not in [list(e) for e in plan["links"]]:
                errs.append(f"lien manquant {edge[0]} -> {edge[1]}")
    # 6) worktree-mk en amont de toutes les cartes de slice
    for key in slice_cards:
        if "worktree-mk" not in parents_of.get(key, set()):
            errs.append(f"{key} n'attend pas worktree-mk")
    if errs:
        raise ValueError("topologie du plan invalide : " + " ; ".join(errs))


def build_plan_checked(doc: dict, t5_id: str, board: str, root_id: str, holders=None) -> dict:
    """`build_plan` + préflight du worktree + épinglage de la topologie.

    Deux refus AVANT toute création de carte :
      * `WorktreeConflict` si la branche de l'issue est tenue par un worktree d'un autre
        chemin (`preflight_worktree`) ;
      * `ValueError` si le SENS des liens est faux (`check_topology`) — l'inversion
        historique rendait `t6` `ready` dès `t5` done, donc la PR partait sans slices.

    `holders` (dict branche->chemin) est injectable pour les sondes ; `None` => lecture
    réelle du dépôt.
    """
    plan = build_plan(doc, t5_id=t5_id, board=board, root_id=root_id)
    check_topology(plan, t5_id=t5_id, root_id=root_id)
    preflight_worktree(plan, holders=holders)
    return plan


def find_submitted_cards() -> list:
    """Cartes 't6 submitted' actives sans enfants (graphe pas encore construit).

    `t6 submitted #<n>` est créée par le worker **t5** (assignee `pj-master`,
    `--parent <t5>`) ; ce script ne fait que COMPLÉTER le graphe en dessous d'elle
    (il réutilise son id, voir `main`). C'est aussi ce qui rend les ticks idempotents :
    dès que la carte a des enfants, elle n'est plus sélectionnée.
    """
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
        t5_id = str(parents[0]) if parents else ""
        root = _find_root(issue)
        if not root:
            log(f"t6 {t6['id']}: racine introuvable — skip")
            continue

        try:
            plan = build_plan_checked(doc, t5_id=t5_id, board=BOARD, root_id=root)
        except (WorktreeConflict, ValueError) as e:
            # Échec EXPLICITE avant toute création : rien en base, aucun auto_block.
            log(f"t6 {t6['id']} (issue #{issue}) : PLAN REFUSÉ — {e}")
            return 1
        if DRY:
            print(json.dumps(plan, indent=2))
            return 0

        # t6 est créée par t5 : on RÉUTILISE son id au lieu d'en créer une seconde.
        # (Sinon la carte de t5 resterait sans enfant => re-sélectionnée à chaque tick
        #  => un graphe en double par tick.)
        ids = {"t6": t6["id"]} if t6.get("id") else {}
        for c in plan["cards"]:
            if c["key"] in ids:
                continue
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
        # t6 est écrite par t5 : la consigne de PR (portée par le plan) est postée en
        # commentaire pour que le worker `pj-master` l'ait même si le body de t5 est sec.
        t6_body = next((c["body"] for c in plan["cards"] if c["key"] == "t6"), "")
        if t6_body:
            sh("comment", ids["t6"], "[graphe] Consigne t6 : " + t6_body)
        sh("comment", root, "Graphe de dev construit : "
           + ", ".join(f"{k}={v}" for k, v in ids.items()))
        log(f"issue #{issue} ({doc['repo']}) : graphe construit ({len(ids)} cartes), "
            f"worktree partagé {plan['worktree']['path']}")
        acted += 1
    if not acted and VERBOSE:
        log("rien à faire")
    return 0


if __name__ == "__main__":
    sys.exit(main())
