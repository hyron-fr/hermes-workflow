#!/usr/bin/env python3
"""
pj_review.py — rubrique de review P0–P3 du pipeline (0 LLM).

Repère Factory Droid « /review » : les findings d'une review sont classés
par gravité et la gravité décide du verdict, de façon DÉTERMINISTE. Le
contenu de la review (les findings eux-mêmes) est produit par un agent
(step agentique, structured output — voir workflows/schemas/review.json)
ou par un humain ; cet outil ne fait que TRANCHER sur l'artefact :
validité du contrat + verdict P0–P3. Aucun appel LLM.

Gravité (du plus bloquant au plus mineur) :
  P0  blocant        : empêche la merge (bug critique, perte de données,
                       rupture de contrat). Doit porter une PREUVE
                       (evidence ou repro) — un P0 sans preuve est un
                       contrat violé (exit 2), pas un P0.
  P1  sérieux        : doit être tranché avant la merge (régression,
                       sécurité mineure, contrat partiel). Doit porter
                       une preuve.
  P2  mineur         : à corriger au fil de l'eau (edge case, performance).
  P3  nit           : style / clarté, non bloquant.

Verdict :
  block : ≥ 1 P0   -> exit 1 (gate fail : on n'avance pas)
  flag  : ≥ 1 P1   -> exit 1 (gate fail : à trancher, le gate humain/
           l'étape de revalidation décide)
  pass  : P2/P3 seulement (ou review vide) -> exit 0

Usage (audit, sans exécuter) :
  pj_review.py --findings review.json [--json]
  exit 0 = pass ; 1 = P0/P1 présent ; 2 = artefact illisible / contrat
  violé (sévérité inconnue, P0/P1 sans preuve, titre manquant).
"""

import argparse
import json
import sys
from pathlib import Path

PREFIX = "[pj-review]"
SEVERITIES = ("P0", "P1", "P2", "P3")
BLOCKING = ("P0", "P1")


def load_findings(path: str) -> list[dict]:
    """Charge les findings d'un artefact de review (liste de dicts)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("findings", [])
    if not isinstance(data, list):
        raise ValueError("artefact de review : `findings` n'est pas une liste")
    for i, f in enumerate(data):
        if not isinstance(f, dict):
            raise ValueError(f"finding #{i} n'est pas un objet")
    return data


def _norm_sev(sev) -> str:
    s = str(sev).strip().upper()
    if s not in SEVERITIES:
        raise ValueError(f"sévérité inconnue: {sev!r} (attendu: {', '.join(SEVERITIES)})")
    return s


def _has_proof(f: dict) -> bool:
    return bool((f.get("evidence") or "").strip() or (f.get("repro") or "").strip())


def validate_finding(f: dict) -> tuple[str, list[str]]:
    """Contrat d'un finding. Retourne (sévérité normalisée, erreurs)."""
    errs = []
    title = str(f.get("title") or "").strip()
    if not title:
        errs.append("titre manquant")
    try:
        sev = _norm_sev(f.get("severity"))
    except ValueError as e:
        return None, [str(e)]
    # P0/P1 exigent une preuve : sans elle le finding est incertain, et
    # trancher une merge sur du flou est exactement ce que le contrat
    # d'ambiguïté (grill-me) interdit.
    if sev in BLOCKING and not _has_proof(f):
        errs.append(f"{sev} sans preuve (evidence/repro manquante)")
    return sev, errs


def audit(findings: list[dict]) -> dict:
    """Verdict déterministe sur une liste de findings.

    Retourne {"verdict": "pass"|"flag"|"block", "counts": {...},
    "errors": [...], "blocking": [findings P0/P1]} — lève ValueError si
    le contrat d'un finding est violé (le caller convertit en exit 2).
    """
    counts = {s: 0 for s in SEVERITIES}
    errors: list[str] = []
    blocking: list[dict] = []
    for i, f in enumerate(findings):
        sev, errs = validate_finding(f)
        if errs:
            errors.append(f"finding #{i}: " + " ; ".join(errs))
        if sev:
            counts[sev] += 1
            if sev in BLOCKING:
                blocking.append({"index": i, "severity": sev,
                                 "title": str(f.get("title") or "").strip()[:120]})
    if errors:
        raise ValueError("contrat de review violé : " + " ; ".join(errors))
    if counts["P0"]:
        verdict = "block"
    elif counts["P1"]:
        verdict = "flag"
    else:
        verdict = "pass"
    return {"verdict": verdict, "counts": counts, "errors": [],
            "blocking": blocking}


def exit_code(audit_result: dict) -> int:
    """pass -> 0 ; flag/block -> 1 (contrat -> 2, géré par main)."""
    return 0 if audit_result["verdict"] == "pass" else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Rubrique de review P0–P3 (0 LLM) : trancher un artefact de findings.")
    ap.add_argument("--findings", required=True, help="artefact JSON de review (findings[])")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    args = ap.parse_args()

    p = Path(args.findings)
    if not p.exists():
        print(f"{PREFIX} artefact introuvable: {p}", file=sys.stderr)
        return 2
    try:
        findings = load_findings(str(p))
        res = audit(findings)
    except (json.JSONDecodeError, ValueError, OSError) as e:
        print(f"{PREFIX} artefact illisible : {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"verdict": res["verdict"], "counts": res["counts"],
                          "blocking": res["blocking"]}, ensure_ascii=False, indent=1))
        return exit_code(res)

    print(f"{PREFIX} {res['verdict']} — "
          + " ".join(f"{s}:{res['counts'][s]}" for s in SEVERITIES))
    for b in res["blocking"]:
        print(f"{PREFIX}   {b['severity']} [{b['index']}] {b['title']}")
    return exit_code(res)


if __name__ == "__main__":
    sys.exit(main())
