#!/usr/bin/env python3
"""issue-2-plate.measure.py — reproduit depuis l'arbre les totaux de la planche (#2).

Source de vérité des totaux : le registre machine `plate-ledger` embarqué dans la planche
(bloc `<script type="application/json" id="plate-ledger">`). Le script ne compare À AUCUNE
constante recopiée dans son code : il MESURE l'arbre et le confronte au registre.

Usage :
    issue-2-plate.measure.py [--plate PATH] [--root PATH] [--json]

Codes de sortie :
    0  concordance arbre == registre ;
    1  écart : une ligne par fichier/champ nommant le chemin ET les deux nombres ;
    2  erreur d'usage, fichier DÉCLARÉ par la planche absent de l'arbre (`MISSING <chemin>`),
       racine introuvable, ou arbre étranger au script.

Défauts : `--plate` = la planche voisine du script ; `--root` = racine canonique du dépôt qui
contient le script. `--root` accepte n'importe quel chemin DANS un checkout : la racine
canonique est résolue par `git rev-parse --show-toplevel`. Le script REFUSE de mesurer un
arbre qui n'est pas le sien : sans cette garde, un vert peut venir de n'importe où.

Énumération : `git ls-files '*.md'` (jamais `os.walk` seul — mesuré : 65 `.md` dont 45 vivent
sous `.worktrees/`). Repli `os.walk` avec prune `.worktrees/**` quand git est indisponible
(arbre recopié sans `.git`) ; le repli est imprimé.

Un `.md` présent dans l'arbre mais non déclaré par la planche est un AVERTISSEMENT : il est
imprimé, il ne fait pas échouer la mesure (l'assignation du corpus est la propriété de la
planche, pas du scan).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PLATE = HERE / "issue-2-plate.html"

EXPECTED_ISSUE = 2
LEDGER_RE = re.compile(
    r"<script[^>]*id=[\"']plate-ledger[\"'][^>]*>(?P<json>.*?)</script>", re.S | re.I)

# Classe de caractères du contrat : lettres latines à diacritique + ligatures latines,
# minuscules ET majuscules. Mesurée : c'est celle qui reproduit les 1 559 lignes accentuées.
CHARACTER_CLASS_CHARS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"
ACCENTS = set(CHARACTER_CLASS_CHARS)
PRUNE = (".git", ".worktrees", "node_modules", "__pycache__")


def sh(args, cwd=None):
    """subprocess tolérant : None si le binaire est absent."""
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    except OSError:
        return None


def toplevel(path):
    """Racine canonique du checkout qui contient `path`, ou None hors dépôt git."""
    r = sh(["git", "-C", str(path), "rev-parse", "--show-toplevel"])
    if r is None or r.returncode != 0:
        return None
    out = r.stdout.strip()
    return Path(out).resolve() if out else None


def enumerate_md(root):
    """(chemins relatifs, méthode) — git ls-files d'abord, repli os.walk pruné."""
    r = sh(["git", "-C", str(root), "ls-files", "-z", "*.md"])
    if r is not None and r.returncode == 0:
        files = sorted(p for p in r.stdout.split("\0") if p)
        return files, "git ls-files '*.md'"
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PRUNE]
        for name in filenames:
            if name.endswith(".md"):
                found.append(str(Path(dirpath, name).relative_to(root)))
    return sorted(found), "os.walk (prune .worktrees/**) — git indisponible"


def stats(root, rel):
    """(lignes, lignes portant un caractère de la classe) — mesure, pas déclaration."""
    lines = (root / rel).read_text(encoding="utf-8").splitlines()
    return len(lines), sum(1 for line in lines if any(c in ACCENTS for c in line))


def declared(ledger):
    """{chemin: entrée de fichier ou None} depuis `slices` — jamais depuis les slices de création."""
    out = {}
    for rec in ledger.get("slices") or []:
        files = rec.get("files") or {}
        if isinstance(files, dict):
            for rel, entry in files.items():
                out[rel] = entry if isinstance(entry, dict) else None
        else:
            for rel in files:
                out[rel] = None
    return out


def slice_files(rec):
    """Liste normalisée des chemins d'une entrée de slice (liste ou mapping)."""
    files = rec.get("files") or []
    return list(files)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="issue-2-plate.measure.py",
        description="Mesure l'arbre et le confronte au registre de la planche (#2).")
    ap.add_argument("--plate", default=str(DEFAULT_PLATE),
                    help="planche HTML portant le registre plate-ledger")
    ap.add_argument("--root", default=None,
                    help="chemin DANS un checkout à mesurer (défaut : le dépôt du script)")
    ap.add_argument("--json", action="store_true", help="rapport machine-lisible sur stdout")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:                      # argparse sort 2 en usage invalide
        return int(exc.code or 0)

    # --- la planche et son registre -------------------------------------------------
    plate = Path(args.plate).expanduser()
    if not plate.is_file():
        print(f"planche introuvable : {plate}")
        return 2
    match = LEDGER_RE.search(plate.read_text(encoding="utf-8"))
    if not match:
        print(f"aucun registre `plate-ledger` dans {plate}")
        return 2
    try:
        ledger = json.loads(match.group("json"))
    except json.JSONDecodeError as exc:
        print(f"registre plate-ledger illisible : {exc}")
        return 2
    if ledger.get("issue") != EXPECTED_ISSUE:
        print(f"planche d'une autre issue : registre issue={ledger.get('issue')!r}, "
              f"attendu {EXPECTED_ISSUE}")
        return 2

    # --- la racine mesurée, et la garde d'auto-racine --------------------------------
    root_arg = Path(args.root).expanduser() if args.root else HERE
    if not root_arg.is_dir():
        print(f"racine introuvable : {root_arg}")
        return 2
    own = toplevel(HERE)
    root = toplevel(root_arg) or root_arg.resolve()
    if own is not None and root != own:
        print(f"arbre étranger refusé : le script vit sous {own}, --root résout {root}")
        return 2

    files, how = enumerate_md(root)
    decl = declared(ledger)
    corpus = ledger.get("corpus") or {}

    # --- fichier déclaré absent : erreur explicite, avant tout écart ------------------
    missing = [rel for rel in sorted(decl) if not (root / rel).is_file()]
    if missing:
        for rel in missing:
            print(f"MISSING {rel}")
        print(f"{len(missing)} fichier(s) déclaré(s) par la planche absent(s) de l'arbre "
              f"({root})")
        return 2

    # --- mesure de l'arbre -----------------------------------------------------------
    measured = {rel: stats(root, rel) for rel in files}
    ecarts = []

    for rel in sorted(decl):
        entry = decl[rel]
        if entry is None:
            continue
        lines, accented = measured[rel]
        if entry.get("lines") != lines:
            ecarts.append(f"{rel}: lignes attendues {entry.get('lines')}, mesurées {lines}")
        if entry.get("accented_lines") != accented:
            ecarts.append(f"{rel}: lignes accentuées attendues "
                          f"{entry.get('accented_lines')}, mesurées {accented}")

    for rec in ledger.get("slices") or []:
        k, slug = rec.get("k"), rec.get("slug") or ""
        rels = slice_files(rec)
        lines = sum(stats(root, rel)[0] for rel in rels)
        accented = sum(stats(root, rel)[1] for rel in rels)
        if rec.get("lines") != lines:
            ecarts.append(f"slice {k} ({slug}): lignes attendues {rec.get('lines')}, "
                          f"mesurées {lines}")
        if rec.get("accented_lines") != accented:
            ecarts.append(f"slice {k} ({slug}): lignes accentuées attendues "
                          f"{rec.get('accented_lines')}, mesurées {accented}")

    corpus_measured = {
        "files": len(decl),
        "lines": sum(stats(root, rel)[0] for rel in decl),
        "accented_lines": sum(stats(root, rel)[1] for rel in decl),
    }
    for champ in ("files", "lines", "accented_lines"):
        if corpus.get(champ) != corpus_measured[champ]:
            ecarts.append(f"corpus: {champ} attendu {corpus.get(champ)}, "
                          f"mesuré {corpus_measured[champ]}")

    unassigned = [rel for rel in files if rel not in decl]

    report = {
        "root": str(root),
        "plate": str(plate),
        "enumeration": how,
        "tracked_md": len(files),
        "declared_md": len(decl),
        "unassigned_md": unassigned,
        "declared": corpus,
        "measured": corpus_measured,
        "ecarts": ecarts,
        "verdict": "ecart" if ecarts else "concordance",
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if ecarts else 0

    print(f"arbre       : {root}")
    print(f"planche     : {plate}")
    print(f"énumération : {how} — {len(files)} .md suivis, "
          f"{len(decl)} déclarés par la planche")
    if unassigned:
        print(f"avertissement : {len(unassigned)} .md non déclaré(s) (hors corpus) — "
              f"{', '.join(unassigned)}")
    if ecarts:
        for ecart in ecarts:
            print(ecart)
        print(f"{len(ecarts)} écart(s) entre la planche et l'arbre — "
              f"registre : {corpus.get('files')} fichiers / {corpus.get('lines')} lignes / "
              f"{corpus.get('accented_lines')} accentuées")
        return 1
    print(f"concordance : {corpus_measured['files']} fichiers / "
          f"{corpus_measured['lines']} lignes / "
          f"{corpus_measured['accented_lines']} lignes accentuées (mesuré == registre)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
