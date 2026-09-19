#!/usr/bin/env python3
"""Déployeur de pipeline pj : transforme une carte racine 'triage' importée par le pont
en mini-graphe t1..t5 + liens, puis la promeut (elle attend le graphe, pattern decompose).

Le graphe est MÉCANIQUE (mêmes 5 cartes par issue) : ce script est déterministe,
pas de LLM. Le cron agent pj-master n'est utilisé que pour la suite (grill-me, draft,
validate, PR) — les workers de ces cartes font le travail intelligent.

Usage (cron no-agent, stdout vide = tick muet) :
  pj_pipeline_deployer.py run

Variables :
  PJ_BOARD         board kanban cible (défaut: déduit du repo si PJ_REPO donné)
  PJ_REPO          slug repo (example-repo | hermes-experiment) pour l'anchor worktree
  PJ_ASSIGNEE      worker des cartes t1..t5 (défaut: pj-master)
  PJ_VERBOSE       1 = loguer tous les ticks
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Racine du dépôt : résolue depuis ce fichier (aucun chemin absolu).
WORKFLOW_ROOT = Path(__file__).resolve().parents[1]

HERMES_BIN = os.environ.get("PJ_HERMES_BIN") or os.path.expanduser(
    "~/.hermes/hermes-agent/venv/bin/hermes")
BOARD = os.environ.get("PJ_BOARD", "")
ASSIGNEE = os.environ.get("PJ_ASSIGNEE", "pj-master")
VERBOSE = os.environ.get("PJ_VERBOSE") == "1"
ANCHORS = {
    "example-repo": "${HOME}/pj-repos/example-repo",
    "hermes-experiment": "${HOME}/pj-repos/hermes-experiment",
}
# repo déduit de la ligne "Importé depuis https://github.com/hyron-fr/<repo>/issues/N"
IMPORT_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/issues/(\d+)")


def log(msg: str) -> None:
    print(f"[pj-deploy] {msg}")


def sh(*args: str) -> str:
    cmd = [HERMES_BIN, "kanban", "--board", BOARD, *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def deploy(root: dict) -> bool:
    """Crée t1..t5 + liens pour une racine triage ; retourne True si déployée."""
    body = root.get("body") or ""
    m = IMPORT_RE.search(body)
    if not m:
        log(f"racine {root['id']}: pas d'URL d'import GitHub dans le body — ignorée")
        return False
    owner, repo, n = m.groups()
    issue_n = int(n)
    anchor = ANCHORS.get(repo)
    if anchor is None:
        # Anchor dynamique : le clone posé par pj-repo-watch phase B.
        candidate = os.path.join("${HOME}/pj-repos", repo)
        anchor = candidate if os.path.isdir(candidate) else None
    if anchor is None:
        log(f"racine {root['id']}: repo {repo} sans anchor (phase B en attente) — ignorée")
        return False

    # Idempotence : si des enfants existent déjà, ne pas re-déployer.
    show = json.loads(sh("show", root["id"], "--json"))
    if show.get("children"):
        log(f"racine {root['id']}: enfants déjà présents — skip")
        return False

    # Room Bot Mode dédiée au TICKET (une room par ticket, room_id déterministe).
    # Déterministe et non bloquante : le board reste la source de vérité, la room
    # n'est qu'un canal de délibération. Un échec ne doit jamais bloquer le graphe.
    _ensure_room(repo, issue_n)

    def create(title: str, extra: list) -> str:
        out = json.loads(sh(
            "create", title,
            "--assignee", ASSIGNEE,
            "--idempotency-key", extra[1],
            "--json",
            *extra[0],
        ))
        return out["id"]

    # t1..t3 indépendantes (parents = racine), t4 attend t1+t2+t3, t5 attend t4.
    t1 = create("t1 worktree", (
        ["--workspace", f"worktree:{anchor}",
         "--body", f"Créer le worktree de l'issue #{issue_n} ({repo}), base dev, "
                   f"et poster chemin+branche en commentaire."],
        f"pj-t1-{repo}-{issue_n}"))
    t2 = create("t2 mémoire projet", (
        ["--body", f"hindsight_recall/reflect banque pj, tags project:{repo}, issue:{issue_n}. "
                   "Résumer les mémoires du projet en commentaire de cette carte."],
        f"pj-t2-{repo}-{issue_n}"))
    t3 = create("t3 grill-me", (
        ["--body", T3_BODY_TEMPLATE.format(issue_n=issue_n, repo=repo)],
        f"pj-t3-{repo}-{issue_n}"))
    # t3b : cadrage architectural (pj-doc) — alimente t4 avec le positionnement dans
    # l'architecture existante (SDD/DDD/TDD/hexagonal, croisement infra/fonctionnel/code).
    t3b = create("t3b doc-cadrage", (
        ["--assignee", "pj-doc",
         "--body", f"Positionner l'issue #{issue_n} ({repo}) dans l'architecture ACTUELLE. "
                   "Croisement infrastructure / fonctionnel / code : où l'évolution s'implante, "
                   "quelles frontières elle traverse. Lecture SDD (la spec est la source de "
                   "vérité), DDD (agrégats, entités, value objects, domain events), TDD (quels "
                   "contrats deviennent testables), hexagonal (le core reste pur). "
                   f"Livrable : docs/architecture/context/issue-{issue_n}.md (frontmatter "
                   "type=context, status=draft, tags=[...]) référencé depuis "
                   "docs/architecture/README.md, PLUS un commentaire de cette carte résumant le "
                   "cadre exact et les composants impactés. S'appuie sur t1 (worktree) et "
                   "t2 (mémoire). Preuve : `python3 $WORKFLOW_ROOT/pipeline/pj_docs_lint.py "
                   f"${HOME}/pj-repos/{repo}` sort exit 0."],
        f"pj-t3b-{repo}-{issue_n}"))
    t4 = create("t4 draft spec", (
        ["--body", f"1er jet de spec + sous-tâches pour l'issue #{issue_n}, à partir "
                   "des handoffs t1/t2/t3. Débattre de la spec dans la room dédiée "
                   f"(room_id `{_room_id(repo, issue_n)}`) : l'animation et le report du "
                   "transcript sont pris en charge par pj_room_keeper (cron pj-master). "
                   "Questions ouvertes → nouvelle carte grill-me.\n\n"
                   "**VERDICT DE t3 À REPRENDRE (renfo 2)** : lis `PROTOTYPE:` / "
                   "`AMBIGU:` / `ARTEFACT:` dans le handoff de t3. Si `PROTOTYPE: oui`, "
                   "le `slices.json` (écrit par t5 au GO) doit contenir une **slice 0 "
                   "`preview`** en tête, productrice du seul `ARTEFACT:` désigné et "
                   "PARENT de toutes les slices de production — elle se valide au gate "
                   "humain AVANT que le moindre développement de masse ne parte. "
                   "Si `PROTOTYPE: non`, pas de slice preview : le graphe est normal.\n\n"
                   f"ROOM: {_room_id(repo, issue_n)}"],
        f"pj-t4-{repo}-{issue_n}"))
    t5 = create("t5 validate", (
        ["--body", f"Mettre à jour l'issue #{issue_n} (gh issue edit --body), notifier "
                   "Discord, demander validation humaine, kanban_block jusqu'au go. "
                   "Au go : créer t6 submitted + sous-tâches dev (règle ANTI-DEADLOCK "
                   "du SOUL) puis kanban_complete.\n\n"
                   "**GATE PROTOTYPE (renfo 2)** — si t3 a rendu `PROTOTYPE: oui`, le GO "
                   "humain porte D'ABORD sur l'artefact (`ARTEFACT:` de t3), PAS sur la "
                   "spec : l'artefact doit exister ET être validé par l'humain avant "
                   "d'écrire `slices.json`. Joins-le au message de validation (lien ou "
                   "pièce jointe) — un artefact invisible n'est pas un artefact validé. "
                   "Si `PROTOTYPE: non`, gate normal (aucun prototype à exiger)."],
        f"pj-t5-{repo}-{issue_n}"))

    # Sens des liens : `link <parent> <child>` = l'enfant attend le parent.
    # t4 enfants de t1,t2,t3,t3b ; t5 enfant de t4 ; racine enfant de chaque t_i
    # (pattern decompose : la racine se réveille quand tout le graphe est done).
    sh("link", t1, t4)
    sh("link", t2, t4)
    sh("link", t3, t4)
    sh("link", t3b, t4)          # le cadrage architectural alimente la spec
    sh("link", t4, t5)
    for tid in (t1, t2, t3, t3b, t4, t5):
        sh("link", tid, root["id"])

    # Commentaire de déploiement + sortie de triage (specify_triage_task :
    # triage -> todo SANS LLM, le gating parent s'applique ensuite).
    sh("comment", root["id"],
       f"Pipeline déployé : t1={t1} t2={t2} t3={t3} t3b={t3b} t4={t4} t5={t5}. "
       f"La racine attend la fin du graphe (t1..t5 + t3b parents).")
    _promote_triage(root["id"])
    log(f"racine {root['id']} (issue #{issue_n}, {repo}) déployée : "
        f"t1={t1} t2={t2} t3={t3} t3b={t3b} t4={t4} t5={t5}")
    return True


def _promote_triage(task_id: str) -> None:
    """triage -> todo via specify_triage_task (mécanique, aucun LLM)."""
    code = (
        "import sys; sys.path.insert(0, "
        + repr(os.path.expanduser("~/.hermes/hermes-agent"))
        + ")\n"
        "from hermes_cli import kanban_db_connect as kbc\n"
        "from hermes_cli import kanban_db as kb\n"
        f"kb.specify_triage_task(kbc.connect(board={BOARD!r}), {task_id!r})\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"specify_triage_task échoué: {r.stderr.strip()[:300]}")


def _room_id(repo: str, issue_n: int) -> str:
    """room_id déterministe du ticket (même schéma que pj_room.py)."""
    import re as _re
    slug = _re.sub(r"[^a-z0-9-]+", "-", str(repo).lower()).strip("-")
    return f"pj-{slug}-issue-{int(issue_n)}"


# ---------------------------------------------------------------------------
# t3 grill-me — contrat d'identification des ambiguïtés (renfo 2)
#
# Objectif : ne PAS convoquer l'humain systématiquement, mais qualifier chaque
# ambiguïté et décider COMMENT la lever au plus tôt. Une issue aux contraintes
# complètes et sans ambiguïté n'a besoin d'aucun prototype — elle passe droit.
# Là où une ambiguïté coûteuse subsiste (vécu : le rendu des acteurs de dino-game,
# 55 h de tunnel avant le 1er jugement humain), on impose un ARTEFACT VÉRIFIABLE
# tôt (maquette / planche de sprites / capture) que l'humain tranche AVANT le
# développement de masse.
# ---------------------------------------------------------------------------

T3_BODY_TEMPLATE = """Clarifier l'issue #{issue_n} ({repo}) — **et qualifier son ambiguïté**. ≤3 questions serrées à l'humain sur Discord (thread de l'issue), puis `kanban_block` ; `unblock` → reformuler ce qui est appris.

## A. Quadrant d'ambiguïté — OBLIGATOIRE

Pour CHAQUE ambiguïté détectée dans l'issue, écris une ligne (aucune omission) :

| # | Ambiguïté | Levable sans humain ? | Comment la lever | Coût si non levée |
|---|---|---|---|---|
| 1 | … | oui / non | … | … |

- **Levable seul** : la réponse est dans le code, la mémoire projet (t2), une convention écrite ou la doc → lève-la TOI-MÊME, ne dérange pas l'humain.
- **Non levable** : décision de goût, d'arbitrage ou de priorité → question à l'humain (≤3), AVANT le développement de masse.
- **Coût si non levée** : quantifie ce que coûte la découverte tardive (« tout le rendu à refaire », « +2 slices », « nul »). C'est ce champ qui décide, pas l'intuition.

Une ambiguïté dont le coût est nul ou faible ne justifie NI question NI prototype : réponds `aucune ambiguïté bloquante` et avance.

## B. Verdict PROTOTYPAGE — OBLIGATOIRE

Réponds explicitement, en une ligne machine-lisible (reprise telle quelle par t4/t5) :

```
PROTOTYPE: oui | non
AMBIGU: <aucune | liste des ambiguïtés non levables>
ARTEFACT: <maquette HTML | planche de sprites | capture de rendu | schéma ASCII | aucun>
```

Règle de décision — `PROTOTYPE: oui` si **au moins une** condition est vraie :
1. une ambiguïté **non levable** subsiste sur un livrable **perceptible** (visuel, UX, ergonomie, texte lu par l'humain) ;
2. le périmètre dépasse **3 slices** et touche un domaine où « ça se voit » ;
3. l'humain a déjà **rejeté** une production antérieure sur ce sujet.

Sinon `PROTOTYPE: non` — et c'est le cas normal : des contraintes complètes et 0 ambiguïté ne demandent aucun prototype.

**Le prototype n'est pas le livrable final** : c'est le plus petit artefact qui permet à l'humain de dire oui/non. Maquette HTML d'un écran, planche de sprites en PNG, capture d'un rendu, schéma pour une structure. Il se produit AVANT les slices de production et se valide au gate humain de t5."""


def _ensure_room(repo: str, issue_n: int) -> None:
    """Crée (idempotent) la room Bot Mode du ticket. 0 LLM, non bloquant.

    Échec loggé mais jamais propagé : une room indisponible ne doit pas empêcher
    le déploiement du graphe kanban.
    """
    script = str(WORKFLOW_ROOT / "pipeline" / "pj_room.py")
    if not os.path.isfile(script):
        log(f"room {repo}#{issue_n}: pj_room.py absent — room non créée")
        return
    r = subprocess.run(
        [sys.executable, script, "--repo", repo, "--issue", str(issue_n), "--action", "ensure"],
        capture_output=True, text=True)
    if r.returncode != 0:
        log(f"room {repo}#{issue_n}: échec ensure ({r.stdout.strip()[:200]})")
        return
    log(f"room {repo}#{issue_n}: {r.stdout.strip()[:200]}")


def main() -> int:
    if not BOARD:
        log("PJ_BOARD manquant")
        return 1
    out = sh("list", "--status", "triage", "--json")
    roots = json.loads(out) or []
    deployed = 0
    for root in roots:
        body = root.get("body") or ""
        if "Importé depuis" not in body:
            continue  # triage non-pont : pas à nous
        try:
            if deploy(root):
                deployed += 1
        except Exception as e:
            log(f"ERREUR déploiement {root['id']}: {e}")
    if not deployed and not VERBOSE:
        return 0  # tick muet
    return 0


if __name__ == "__main__":
    sys.exit(main())