#!/usr/bin/env python3
"""
pj_autonomy.py — graduation d'autonomie du pipeline YAML (0 LLM).

Repère Factory Droid « ctrl+L pour autonomy » : chaque workflow YAML porte
un niveau d'autonomie qui contrôle ce que le moteur est autorisé à EXÉCUTER
autonomement, sans geste humain. La mécanique est pure (table de politique
déterministe) — aucun appel LLM.

Niveaux (du plus strict au plus lâche) :
  off     — rien ne s'exécute seul : seule la route des gates (évaluation
            lecture-seule) tourne ; chaque étape commandique/agentique
            ESCALE (kanban block needs_input, la carte attend l'humain).
  low     — seules les étapes déterministes non-irréversibles s'exécutent ;
            toute étape agentique (LLM autonome) ESCALE.
  medium  — tout s'exécute SAUF les effets irréversibles (push, merge,
            suppression forcée, publication) : ceux-ci ESCALENT.
  high    — tout s'exécute (comportement historique, défaut).

Résolution du niveau (priorité décroissante) :
  étape `autonomy:`  >  `orchestration.autonomy:`  >  `high`

Effets irréversibles : détectés de façon déterministe (regex) sur la
`command:`/`actions:` de l'étape déterministe et sur la `side_effect:`
déclarée de l'étape agentique. Un workflow ne DOIT PAS compter sur la
détection : déclarer `side_effect:` est le contrat explicite.

Usage (audit, sans exécuter) :
  pj_autonomy.py --workflow workflows/spec.yaml [--json]
  exit 0 = politique lue et affichée ; 2 = niveau invalide ou fichier introuvable
"""

import argparse
import json
import re
import sys
from pathlib import Path

LEVELS = ("off", "low", "medium", "high")
DEFAULT_LEVEL = "high"

# Marqueurs de commande IRRÉVERSIBLE (ou publication) — regex sur le texte
# de la commande rendue. Conservé strictement : faux positif = escalade
# (dégradation ouverte vers l'humain), faux négatif = effet exécuté seul.
_IRREVERSIBLE_CMD = re.compile(
    r"""
    (?:\bgit\s+(?:push|merge|rebase|reset\s+--hard)\b)          # git destructif/push
    | (?:\bgh\s+(?:pr\s+merge|issue\s+close|repo\s+delete)\b)
    | (?:\brm\s+(?:-\S+\s+)*-\S*f\w*)                           # rm -f / rm -rf
    | (?:\bdocker\s+rm\b|\bkillall\b|\bshutdown\b)              # infra
    | (?:\bmerge\s+PR\b|\bmerger\s+la\s+PR\b)                   # prose d'effet
    """,
    re.VERBOSE,
)

# `side_effect:` déclarée (contrat explicite) -> irréversibilité.
_SIDE_EFFECTS_IRREVERSIBLE = {
    "merge", "push", "publish", "create_subtickets", "delete", "reset",
}

GATE_PREFIX = "[autonomy] "


def normalize_level(value) -> str:
    """Valide un niveau. Retourne un membre de LEVELS ; lève ValueError sinon.

    `None` / "" -> DEFAULT_LEVEL (comportement historique non exprimé).
    Piège YAML 1.1 : `off` est parsé par PyYAML comme le booléen `False`
    (on/off/yes/no sont des booléens) — `autonomy: off` arrive donc ici
    sous forme `False`, pas la chaîne "off". `False` -> "off" est le
    raccourci explicite ; `True` n'a pas de niveau correspondant.
    """
    if value in (None, ""):
        return DEFAULT_LEVEL
    if value is False:
        return "off"
    s = str(value).strip().lower()
    if s not in LEVELS:
        raise ValueError(
            f"niveau d'autonomie invalide: {value!r} (attendu: {', '.join(LEVELS)})")
    return s


def effective_level(step: dict, workflow_level: str) -> str:
    """Niveau effectif d'une étape : override d'étape > niveau workflow."""
    return normalize_level(step.get("autonomy") or workflow_level)


def irreversible_effects(step: dict) -> list[str]:
    """Liste déterministe des effets irréversibles d'une étape (vide = aucun).

    Sources : `side_effect:` déclarée (contrat) + regex sur `command:`/`actions:`.
    Une étape `gate` n'exécute jamais de commande -> jamais irréversible.
    """
    stype = step.get("type", "agentic")
    found: list[str] = []

    se = step.get("side_effect")
    if isinstance(se, str):
        se = [se]
    if isinstance(se, list):
        for item in se:
            if str(item).strip().lower() in _SIDE_EFFECTS_IRREVERSIBLE:
                found.append(f"side_effect:{item}")

    if stype != "gate":
        cmds = step.get("command") or step.get("actions") or []
        if isinstance(cmds, str):
            cmds = [cmds]
        for cmd in cmds:
            m = _IRREVERSIBLE_CMD.search(str(cmd))
            if m:
                found.append(f"command:{m.group(0).strip()[:60]}")
    return found


def decision(level: str, step: dict) -> tuple[str, str | None]:
    """Politique centrale. Retourne ("run", None) ou ("escalate", raison).

    - gate : toujours run (évaluation lecture-seule, aucun effet).
    - off  : tout le reste escale.
    - low  : les étapes agentiques escalement ; le déterministe n'exécute que
             s'il est réversible.
    - medium : seuls les effets irréversibles escalement.
    - high : tout s'exécute.
    """
    level = normalize_level(level)
    stype = step.get("type", "agentic")
    sid = step.get("id", "?")
    if stype == "gate":
        return "run", None
    if level == "high":
        return "run", None
    effects = irreversible_effects(step)
    if level == "off":
        return "escalate", f"autonomy=off — l'étape {sid} ne s'exécute pas seule"
    if level == "low" and stype == "agentic":
        return "escalate", f"autonomy=low — l'étape agentique {sid} ne s'exécute pas seule"
    if effects:
        return "escalate", (f"autonomy={level} — effet(s) irréversible(s) "
                            f"dans {sid} : {', '.join(effects)}")
    return "run", None


def escalate_comment(step: dict, reason: str, board: str, ticket_id: str) -> str:
    """Message structuré posté (kanban block needs_input) pour escalade."""
    return (f"{GATE_PREFIX}{reason} — carte {ticket_id} (board {board}) : "
            f"débloque pour laisser le moteur poursuivre (idempotent : les "
            f"étapes déjà réussies ne sont pas rejouées).")


def workflow_level(wf: dict) -> str:
    """Niveau du workflow depuis `orchestration.autonomy` (défaut high)."""
    return normalize_level((wf.get("orchestration") or {}).get("autonomy"))


def audit(wf: dict) -> list[dict]:
    """Politique effective par étape (lecture seule)."""
    wl = workflow_level(wf)
    out = []
    for step in wf.get("steps", []):
        lvl = effective_level(step, wl)
        verdict, reason = decision(lvl, step)
        out.append({
            "id": step.get("id", "?"),
            "type": step.get("type", "agentic"),
            "level": lvl,
            "verdict": verdict,
            "reason": reason,
            "irreversible": irreversible_effects(step),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit de la politique d'autonomie d'un workflow YAML.")
    ap.add_argument("--workflow", required=True, help="chemin du workflow YAML")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    args = ap.parse_args()

    path = Path(args.workflow)
    if not path.exists():
        print(f"[pj-autonomy] workflow introuvable: {path}", file=sys.stderr)
        return 2
    try:
        import yaml
        wf = yaml.safe_load(path.read_text())
    except Exception as e:
        print(f"[pj-autonomy] workflow illisible: {e}", file=sys.stderr)
        return 2
    if not isinstance(wf, dict) or "steps" not in wf:
        print(f"[pj-autonomy] pas un workflow (pas de steps): {path}", file=sys.stderr)
        return 2

    try:
        rows = audit(wf)
    except ValueError as e:
        print(f"[pj-autonomy] {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"workflow": wf.get("name"), "rows": rows},
                         ensure_ascii=False, indent=1))
        return 0
    wl = workflow_level(wf)
    print(f"workflow {wf.get('name', '?')} — autonomie par défaut: {wl}")
    for r in rows:
        mark = "run" if r["verdict"] == "run" else "ESCALE"
        line = f"  {r['id']:<18} {r['type']:<13} {r['level']:<7} {mark}"
        if r["reason"]:
            line += f"  ({r['reason']})"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
