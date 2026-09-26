#!/usr/bin/env python3
"""
pj_validator_model.py — modèle de validation DISTINCT du modèle de dev (0 LLM).

Repère Factory Droid « validator-model: distinct du dev » : le modèle qui
VALIDE (écrit les tests, fait la convergence) ne doit pas être le même que
celui qui DÉVELOPPE — sinon l'agent se confirme lui-même (self-confirmation
bias). La décision de quel modèle piquer sur quelle carte est déterministe
(lecture de config) : aucun appel LLM.

Rôles du graphe (clé de carte) :
  dev-*/worktree-mk/worktree-rm -> dev        (pj-dev)
  test-*/conv-*                  -> validator (pj-test)
  doc-*/doc-review/doc-memory    -> doc       (pj-doc)
  t6                             -> master    (pj-master)

Résolution du modèle par rôle (priorité décroissante) :
  slices.json `slices[i].<role>_model`  >  slices.json racine `<role>_model`
  >  env `PJ_<ROLE>_MODEL`              >  None (hérite du défaut du profil)

Le provider suit la même règle (`<role>_provider` / `PJ_<ROLE>_PROVIDER`).

SIGNAL DE NON-DISTINCTION (valeur de P4) : si `dev` et `validator` résolvent
le même modèle, `validator_differs()` renvoie (False, raison). C'est une
ALERTE à loguer (dégradation ouverte : on n'empêche jamais le graphe), pas un
blocage — le graphe part, mais l'humain voit que le validateur se confirme
lui-même.

Usage (audit, sans écrire) :
  pj_validator_model.py --slices <slices.json> [--json]
  exit 0 = config lue ; 2 = slices.json illisible / absent
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROLES = ("dev", "validator", "doc", "master")

# Préfixe / clé de carte -> rôle.
CARD_ROLE_PREFIX = (
    ("worktree-", "dev"),
    ("dev-", "dev"),
    ("test-", "validator"),
    ("conv-", "validator"),
    ("doc-", "doc"),
)
CARD_ROLE_EXACT = {"t6": "master"}

# Variables d'environnement par rôle (défaut de résolution, le moins prioritaire).
ENV_MODEL = {r: f"PJ_{r.upper()}_MODEL" for r in ROLES}
ENV_PROVIDER = {r: f"PJ_{r.upper()}_PROVIDER" for r in ROLES}


def role_for_key(key: str) -> str | None:
    """Rôle d'une clé de carte (None si inconnue)."""
    if key in CARD_ROLE_EXACT:
        return CARD_ROLE_EXACT[key]
    for prefix, role in CARD_ROLE_PREFIX:
        if key.startswith(prefix):
            return role
    return None


def _norm(model) -> str | None:
    """Normalise un modèle (None/vide -> None, sinon str strip, case-insensible
    pour la comparaison de distinction)."""
    if model in (None, ""):
        return None
    return str(model).strip()


def _lower(model) -> str | None:
    m = _norm(model)
    return m.lower() if m else None


def resolve_role_models(doc: dict, env: dict) -> dict:
    """Résout {rôle: {"model": m|None, "provider": p|None}}.

    `doc` = slices.json (repo/branch/issue/slices + champs optionnels de
    modèle). `env` = mapping clé->valeur (injectable pour les tests, ne lit
    PAS os.environ ici). Priorité : slice > racine > env > None.
    """
    out = {}
    for role in ROLES:
        model = provider = None
        # 1) overrides par slice : le premier slice qui le déclare gagne
        #    (réglage de graphe, pas de réglage par carte).
        for s in doc.get("slices") or []:
            if model is None:
                model = _norm(s.get(f"{role}_model"))
            if provider is None:
                provider = _norm(s.get(f"{role}_provider"))
        # 2) racine du slices.json (ne remplace PAS un override de slice).
        if model is None:
            model = _norm(doc.get(f"{role}_model"))
        if provider is None:
            provider = _norm(doc.get(f"{role}_provider"))
        # 3) environnement (dernier recours).
        if model is None:
            model = _norm(env.get(ENV_MODEL[role]))
        if provider is None:
            provider = _norm(env.get(ENV_PROVIDER[role]))
        out[role] = {"model": model, "provider": provider}
    return out


def validator_differs(models: dict) -> tuple[bool, str]:
    """Le modèle de validation est-il DISTINCT du modèle de dev ?

    Retourne (True, "") si distinct (ou inconnu d'un côté => on ne peut pas
    affirmer la self-confirmation), sinon (False, raison). Ne bloque JAMAIS
    : c'est un signal à loguer.
    """
    dev = _lower((models.get("dev") or {}).get("model"))
    val = _lower((models.get("validator") or {}).get("model"))
    if dev and val and dev == val:
        return False, (f"validator-model == dev-model ({dev}) — "
                       "self-confirmation : le validateur se juge lui-même")
    return True, ""


def annotate_plan(plan: dict, models: dict) -> tuple[dict, list[str]]:
    """Pique le modèle sur chaque carte du plan (mutation in-place).

    Ajoute `model`/`provider` aux cartes dont le rôle a un modèle résolu.
    Retourne (plan, warnings). Un provider sans modèle est signalé (le
    dispatcher exige --model pour --provider).
    """
    warnings = []
    for c in plan.get("cards", []):
        role = role_for_key(c.get("key", ""))
        if not role:
            continue
        spec = models.get(role) or {}
        model, provider = spec.get("model"), spec.get("provider")
        if model:
            c["model"] = model
        if provider:
            c["provider"] = provider
        if provider and not model:
            warnings.append(f"carte {c.get('key')}: provider sans modèle ignoré "
                            f"(--provider exige --model)")
    return plan, warnings


def audit(doc: dict, env: dict) -> dict:
    """Lecture seule : modèles par rôle + signal de non-distinction."""
    models = resolve_role_models(doc, env)
    distinct, reason = validator_differs(models)
    return {
        "roles": models,
        "validator_differs": distinct,
        "validator_reason": reason,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit du modèle de validation (distinct du dev) d'un slices.json.")
    ap.add_argument("--slices", required=True, help="chemin du slices.json")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    path = Path(args.slices)
    if not path.exists():
        print(f"[pj-validator-model] slices.json introuvable: {path}", file=sys.stderr)
        return 2
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[pj-validator-model] slices.json illisible: {e}", file=sys.stderr)
        return 2
    if not isinstance(doc, dict):
        print(f"[pj-validator-model] pas un slices.json: {path}", file=sys.stderr)
        return 2

    data = audit(doc, os.environ)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
        return 0
    print(f"slices {doc.get('repo', '?')} #{doc.get('issue', '?')} : modèles par rôle")
    for role in ROLES:
        m = data["roles"][role]
        print(f"  {role:<10} {m['model'] or '(défaut profil)':<32} "
              f"{m['provider'] or ''}")
    tag = "OK — validateur distinct du dev" if data["validator_differs"] \
        else "ALERTE — " + data["validator_reason"]
    print(f"  {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
