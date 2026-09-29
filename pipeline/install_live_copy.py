#!/usr/bin/env python3
"""install_live_copy.py — installe la copie LIVE de `pj_graphwatch.py` depuis le canonique.

POURQUOI CE SCRIPT EXISTE (règle « une seule copie canonique »)
---------------------------------------------------------------
Le README installe les outils par `cp pipeline/*.py ~/.hermes/profiles/<profil>/scripts/`.
Ce `cp` nu est un piège : une copie installée **modifiée à la main** cesse de recevoir les
corrections du dépôt, et le dépôt n'apprend rien des correctifs appliqués en production.
Vécu sur `pj_graphwatch.py` : la copie live portait trois correctifs absents du dépôt
(racine d'ancrage surchargeable par `PJ_ANCHOR_ROOT`, et deux chemins `~/.hermes/scripts/`
dans des corps de carte) — deux programmes différents sous le même nom.

La règle : le canonique est `pipeline/<outil>.py` ; la copie installée en est **dérivée**
par ce script, et **toute** différence avec le canonique doit apparaître ci-dessous.
Une divergence non déclarée ici est une régression à corriger dans `pipeline/`.

Usage :
  python3 pipeline/install_live_copy.py [--profile pj-master] [--check]

  --check  n'écrit rien ; sort 1 si la copie installée diffère de ce que ce script
           produirait (le contrôle d'identité, à lancer avant de croire un `cp`).
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

CANON_NAME = "pj_graphwatch.py"
DEFAULT_PROFILE = "pj-master"

# --- Divergences DÉCLARÉES entre le canonique (public) et la copie installée -----------
# Les corps de carte citent les commandes que le WORKER peut réellement exécuter :
# `~/.hermes/scripts/<outil>.py` (copie installée), jamais `${HERMES_WORKFLOW}/pipeline/`
# — un worker headless n'a pas la variable d'environnement.
REPLACEMENTS = (
    ('f"`python3 <hermes-workflow>/pipeline/pj_docs_lint.py {anchor}` doit sortir "',
     'f"`python3 ~/.hermes/scripts/pj_docs_lint.py {anchor}` doit sortir "'),
    ('f"`python3 <hermes-workflow>/pipeline/pj_docs_memory.py --repo {anchor} "',
     'f"`~/.hermes/scripts/pj_docs_memory.py --repo {anchor} "'),
)


def build(canon: Path) -> str:
    src = canon.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        if old not in src:
            print("[install-live] AVERTISSEMENT motif absent du canonique : "
                  f"{old[:60]}…", file=sys.stderr)
            continue
        src = src.replace(old, new)
    return src


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--check", action="store_true",
                    help="n'écrit rien ; sort 1 si la copie installée a divergé")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    canon = repo / "pipeline" / CANON_NAME
    if not canon.is_file():
        print(f"[install-live] canonique introuvable : {canon}", file=sys.stderr)
        return 2

    home = Path(os.environ.get("HOME") or Path.home())
    live = home / ".hermes" / "profiles" / args.profile / "scripts" / CANON_NAME
    expected = build(canon)
    current = live.read_text(encoding="utf-8") if live.is_file() else ""

    if args.check:
        if current == expected:
            print(f"[install-live] conforme : {live}")
            return 0
        digest = hashlib.sha256(expected.encode("utf-8")).hexdigest()[:16]
        print(f"[install-live] DIVERGENCE : {live} diffère de {canon} "
              f"(attendu sha256={digest})", file=sys.stderr)
        return 1

    live.parent.mkdir(parents=True, exist_ok=True)
    if live.is_file() and current != expected:
        backup = live.with_suffix(live.suffix + ".bak-install")
        backup.write_text(current, encoding="utf-8")
        print(f"[install-live] sauvegarde de l'ancienne copie : {backup}")
    live.write_text(expected, encoding="utf-8")
    print(f"[install-live] installé : {live} (depuis {canon})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
