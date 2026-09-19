#!/usr/bin/env python3
"""pj_slices_lint — valide le slices.json produit par t5 (contrat du graphe de dev).

Topologie visée (D2/D3) : par slice, un lot PARALLÈLE (test ∥ dev) puis une carte de
CONVERGENCE, puis la doc. La branche est unique pour l'issue (partage du worktree).
Contrainte D4 : la carte test doit porter ≥3 scénarios Gherkin (nominal, limite, erreur).

Usage : pj_slices_lint.py <slices.json>
Sortie : une ligne par erreur. exit 0 conforme, 1 non conforme, 2 erreur d'exécution.
"""
import json
import re
import sys
from pathlib import Path

SCENARIO_RE = re.compile(r"^\s*#*\s*(?:sc[eé]nario|scenario)\s*:\s*(.+)$", re.I | re.M)
LIMITE_RE = re.compile(r"limite|edge|bord|d[eé]grad", re.I)
ERREUR_RE = re.compile(r"erreur|error|invalide|refus|[eé]chec|corrompu", re.I)


def _scenario_names(body: str) -> list:
    return [m.group(1).strip() for m in SCENARIO_RE.finditer(body or "")]


PREVIEW_PREFIXES = ("preview", "proto", "maquette")


def _has_preview(slices: list) -> bool:
    """La PREMIÈRE slice est-elle une slice de preview (artefact à valider tôt) ?

    Détection par le slug : le validateur ne peut pas deviner le rôle d'une slice
    autrement. Elle doit être en tête — une preview en fin de graphe ne protège rien.
    """
    if not slices:
        return False
    slug = str((slices[0] or {}).get("slug") or "").strip().lower()
    return slug.startswith(PREVIEW_PREFIXES)


def validate(doc: dict) -> tuple:
    """(ok, erreurs) — validation complète du contrat slices.json."""
    errs = []
    if not isinstance(doc, dict):
        return False, ["document non-objet"]
    for key in ("issue", "repo", "branch"):
        if not doc.get(key):
            errs.append(f"clé '{key}' manquante")

    slices = doc.get("slices")
    if not isinstance(slices, list) or not slices:
        errs.append("aucune slice ('slices' vide ou absent)")
        return False, errs

    ks = [s.get("k") for s in slices]
    if any(not isinstance(k, int) for k in ks):
        errs.append("'k' doit être un entier pour chaque slice")
    elif ks != list(range(1, len(ks) + 1)):
        errs.append(f"slices 'k' non contigus à partir de 1 (reçu {ks})")
    if len(set(ks)) != len(ks):
        errs.append("'k' dupliqués")

    # RENFO 2 — slice preview imposée quand t3 a rendu `PROTOTYPE: oui`.
    # Sans elle, le tunnel repart : vérifié sur dino-game (issue #4), 55 h de
    # développement avant le premier rendu jugé par l'humain.
    if doc.get("prototype_required"):
        if not _has_preview(slices):
            errs.append("prototype_required=true : la 1re slice doit être une slice "
                        "'preview' (slug préfixé preview-/proto-/maquette-) — "
                        "l'artefact se valide AVANT le développement de masse")

    for s in slices:
        k = s.get("k")
        par = s.get("parallel")
        if not isinstance(par, dict):
            errs.append(f"slice {k}: bloc 'parallel' manquant")
        else:
            for side in ("test", "dev"):
                blk = par.get(side)
                if not isinstance(blk, dict) or not blk.get("title"):
                    errs.append(f"slice {k}: bloc 'parallel.{side}' manquant ou sans titre")
        for key in ("convergence", "doc"):
            blk = s.get(key)
            if not isinstance(blk, dict) or not blk.get("title"):
                errs.append(f"slice {k}: bloc '{key}' manquant ou sans titre")

        # D4 : la carte test porte les 3 natures de scénarios (nominal, limite, erreur)
        tbody = ((par or {}).get("test") or {}).get("body") or ""
        names = _scenario_names(tbody)
        if len(names) < 3:
            errs.append(f"slice {k}: carte test — {len(names)} scénario(s), minimum 3 "
                        f"(nominal + limite + erreur)")
        else:
            joined = " | ".join(names)
            if not LIMITE_RE.search(joined):
                errs.append(f"slice {k}: carte test — aucun scénario de cas limite")
            if not ERREUR_RE.search(joined):
                errs.append(f"slice {k}: carte test — aucun scénario d'erreur")

        deps = s.get("depends_on") or []
        if not isinstance(deps, list):
            errs.append(f"slice {k}: 'depends_on' doit être une liste")
            continue
        for d in deps:
            if not isinstance(d, int) or d >= (k or 0):
                errs.append(f"slice {k}: dépendance invalide {d} "
                            f"(doit être un entier strictement inférieur)")
    return (not errs), errs


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: pj_slices_lint.py <slices.json>")
        return 2
    p = Path(sys.argv[1])
    if not p.exists():
        print(f"[pj-slices] introuvable: {p}")
        return 2
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[pj-slices] JSON invalide: {e}")
        return 2
    ok, errs = validate(doc)
    for e in errs:
        print(f"[pj-slices] {e}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
