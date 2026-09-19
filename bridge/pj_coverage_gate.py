#!/usr/bin/env python3
"""pj_coverage_gate — enforce la couverture PAR FICHIER sur le périmètre des modifications.

D4 : le seuil (>80 % par défaut) porte sur **les fichiers modifiés par la branche**
(pas tout le repo — on ne pénalise pas une slice pour du code hérité non testé).

Deux modes :
  --diff-base origin/dev   ne contrôle QUE les fichiers modifiés depuis cette base
  (sans --diff-base)       contrôle tout le rapport (garde-fou anti-régression global)

Usage :
  pj_coverage_gate.py --json coverage.json --diff-base origin/dev [--min 80] [--repo PATH]
  pj_coverage_gate.py --json coverage.json --run "pytest --cov --cov-report=json"
Sortie : une ligne par fichier fautif. exit 0 conforme, 1 non conforme, 2 erreur.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

EXCLUDE_SUFFIXES = (".d.ts",)
EXCLUDE_NAMES = ("vite.config.ts", "vitest.config.ts", "playwright.config.ts",
                 "tsconfig.json", "app-meta.ts", "_version.py", "conftest.py")
EXCLUDE_PARTS = ("tests/", "test/", "docs/", "dist/", "build/")


def parse_coverage_json(doc: dict) -> dict:
    """{fichier: pourcentage} depuis un rapport `coverage json`."""
    out = {}
    for path, info in (doc.get("files") or {}).items():
        pct = (info.get("summary") or {}).get("percent_covered")
        if pct is None and "percent_covered" in info:
            pct = info["percent_covered"]
        if pct is not None:
            out[path] = round(float(pct), 2)
    return out


def is_code_file(path: str) -> bool:
    """Un fichier exécutable qu'on exige de couvrir (exclut configs, types, tests)."""
    p = path.replace("\\", "/")
    if any(p.endswith(s) for s in EXCLUDE_SUFFIXES):
        return False
    if any(p.endswith(n) or p.split("/")[-1] == n for n in EXCLUDE_NAMES):
        return False
    if any(part in p for part in EXCLUDE_PARTS):
        return False
    return p.endswith((".py", ".ts", ".tsx", ".js", ".jsx"))


def changed_files(repo: str, diff_base: str) -> set:
    """Fichiers modifiés depuis `diff_base` (triple-dot : depuis le merge-base)."""
    r = subprocess.run(["git", "-C", repo, "diff", "--name-only", f"{diff_base}...HEAD"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git diff a échoué: {r.stderr.strip()[:200]}")
    return {l.strip() for l in r.stdout.splitlines() if l.strip()}


def violations(pct: dict, minimum: float, ignore=(), scope=None) -> list:
    """[(fichier, pct)] sous le seuil, restreint à `scope` (set de chemins) si fourni."""
    ign = set(ignore or ())
    out = []
    for f, p in pct.items():
        if f in ign:
            continue
        if scope is not None and f not in scope:
            continue
        if not is_code_file(f):
            continue
        if p < minimum:
            out.append((f, p))
    return sorted(out, key=lambda x: (x[1], x[0]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", dest="json_path", required=True)
    ap.add_argument("--min", type=float, default=80.0)
    ap.add_argument("--ignore", default="")
    ap.add_argument("--run", default="")
    ap.add_argument("--diff-base", default="", help="ex. origin/dev — scope au diff")
    ap.add_argument("--repo", default=".", help="racine du repo (pour git diff)")
    a = ap.parse_args()

    if a.run:
        r = subprocess.run(a.run, shell=True, capture_output=True, text=True)
        if r.returncode != 0:
            # un run de tests rouge n'est PAS un échec du gate (la convergence juge le reste)
            print(f"[pj-cov] la commande de couverture a échoué (rc={r.returncode})")
            print((r.stderr or r.stdout).strip()[-800:])

    p = Path(a.json_path)
    if not p.exists():
        print(f"[pj-cov] rapport introuvable: {p}")
        return 2
    pct = parse_coverage_json(json.loads(p.read_text(encoding="utf-8")))
    ignore = [x.strip() for x in a.ignore.split(",") if x.strip()]
    scope = None
    if a.diff_base:
        try:
            scope = changed_files(a.repo, a.diff_base)
        except Exception as e:
            print(f"[pj-cov] {e}")
            return 2
        print(f"[pj-cov] périmètre : {len(scope)} fichier(s) modifié(s) depuis {a.diff_base}")
    bad = violations(pct, minimum=a.min, ignore=ignore, scope=scope)
    for f, v in bad:
        print(f"[pj-cov] {f}: {v}% < {a.min}%")
    if bad:
        print(f"[pj-cov] {len(bad)} fichier(s) modifié(s) sous le seuil de {a.min}%")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
