#!/usr/bin/env python3
"""pj_lang_lint — language gate for the migrated corpus (issue #2, slice 2).

The repository is being rewritten in English. This scan is the gate that keeps it
that way: it reports every line of a versioned `.md` that still carries a diacritic
**outside a frozen span**.

Usage:

    python3 pipeline/pj_lang_lint.py [--exclusions F] [<path> ...]

Contract (frozen by `tests/test_lang_lint.py`, card t_ea1ae788):

- with **no argument**: enumerates the TRACKED `.md` of the work tree
  (`git ls-files '*.md'`, resolved through `git rev-parse --show-toplevel` when the
  cwd is a sub-directory). Never a directory walk: each worktree carries a copy of
  the corpus, so `os.walk` would report sibling worktrees as if they were the tree.
- with an explicit `<path>`: restricts the scan to that path. A path that was asked
  for and cannot be found is a USAGE ERROR (`rc 2`), never a violation.
- `rc 0` = compliant, and the output is SILENT (stdout and stderr both empty);
  `rc 1` = at least one violation, each line naming path + line + the faulty text;
  `rc 2` = usage error (missing path, missing/unreadable exclusions file, unknown
  flag) — never confused with a violation, and vice versa.

Granularity is the SPAN, never the whole line: the spans matching the frozen
literals are REMOVED from the line, and the line is reported only if a diacritic
survives outside them. A line of prose that trips a detector through a false
positive is a FAILED translation, not an exclusion — that is why the exemptions are
the two machine protocols and nothing else.

The exemption file is `pipeline/pj_lang_lint.exclusions.yaml`: a `.yaml` so it stays
outside the `.md` corpus the scan enumerates, and versioned so each declaration can
be re-read by the script it cites.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Character class of the contract, identical to the plate ratified at the gate and
# to the slice-1 bench: latin letters carrying a diacritic or a latin ligature.
ACCENTS = "àâäçéèêëîïôöùûüÿœæñÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆÑ"

DEFAULT_EXCLUSIONS = "pipeline/pj_lang_lint.exclusions.yaml"
SCRIPT_DIR = Path(__file__).resolve().parent

# YAML keys that carry a frozen literal, and keys that carry a plain list of them.
LITERAL_KEYS = ("litteral", "literal", "litteraux", "literaux")
LIST_KEYS = ("protocoles", "geles", "gelés", "frozen_literals")

# Punctuation trimmed off an offending token before it is printed.
TRIM = "`*_\"'()[]{}.,;:!?«»…—–-"


def usage(msg: str) -> int:
    print("[pj-lang-lint] %s" % msg, file=sys.stderr)
    return 2


# --------------------------------------------------------------------------- git


def show_toplevel(cwd: Path):
    """The work tree root, or None when `cwd` is not inside a git work tree."""
    try:
        p = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0 or not p.stdout.strip():
        return None
    return Path(p.stdout.strip().splitlines()[0])


def tracked_md(root: Path, prefix: str = ""):
    """Tracked `.md`, enumerated by the INDEX — never by a directory walk.

    Returns paths relative to `root`, sorted; `prefix` restricts to a sub-tree.
    """
    args = ["git", "-C", str(root), "ls-files", "-z", "--", "*.md"]
    p = subprocess.run(args, capture_output=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "replace").strip()[:200]
                           or "git ls-files failed")
    out = [x.decode("utf-8", "replace") for x in p.stdout.split(b"\x00") if x]
    if prefix:
        out = [x for x in out if x == prefix or x.startswith(prefix.rstrip("/") + "/")]
    return sorted(out)


# ------------------------------------------------------------------- exclusions


def _collect_literals(node, list_ctx=False, out=None):
    """Frozen literals declared by a parsed exclusions document.

    Accepts both shapes: a node whose value carries the literal
    (`- litteral: "Importé depuis"`) and a plain list of strings under a list key
    (`protocoles: ["Importé depuis"]`). Both are what a human would write by hand.
    """
    if out is None:
        out = []
    if isinstance(node, dict):
        for key, val in node.items():
            kl = str(key).strip().lower()
            if kl in LITERAL_KEYS and isinstance(val, str):
                out.append(val)
                continue
            _collect_literals(val, kl in LIST_KEYS, out)
    elif isinstance(node, (list, tuple)):
        for val in node:
            if isinstance(val, str) and list_ctx:
                out.append(val)
            else:
                _collect_literals(val, list_ctx, out)
    return out


def load_literals(path: Path):
    """(literals, None) or (None, message) — never raises on a bad file."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, "unreadable exclusions file %s (%s)" % (path, exc.strerror or exc)
    try:
        import yaml
    except ImportError:  # pragma: no cover - PyYAML ships with this environment
        return None, "PyYAML is required to read %s" % path
    try:
        doc = yaml.safe_load(raw)
    except Exception as exc:  # yaml.YAMLError and anything a hand-edited file raises
        return None, "unreadable exclusions file %s (%s: %s)" % (
            path, type(exc).__name__, str(exc).splitlines()[0][:120])
    lits = [l.strip() for l in _collect_literals(doc) if l and l.strip()]
    if not lits:
        return None, ("%s declares no frozen literal: scanning without spans would "
                      "flag correct translations" % path)
    return list(dict.fromkeys(lits)), None


def resolve_exclusions(given, root: Path, cwd: Path):
    """Explicit path validated, or the canonical file looked up next to the corpus.

    With no `--exclusions`, the canonical file is looked up next to the corpus, next
    to the cwd, then next to the script — a caller may run the tool from a fixture
    tree that mirrors the canonical layout, or from anywhere at all.
    """
    if given is not None:
        p = Path(given)
        if not p.is_absolute():
            p = cwd / p
        if not p.is_file():
            return None, "exclusions file not found: %s" % given
        return p, None
    for cand in (root / DEFAULT_EXCLUSIONS, cwd / DEFAULT_EXCLUSIONS,
                 SCRIPT_DIR / "pj_lang_lint.exclusions.yaml"):
        if cand.is_file():
            return cand, None
    return None, ("no exclusions file found (looked for %s)" % DEFAULT_EXCLUSIONS)


# ------------------------------------------------------------------------- scan


def residual(line: str, literals):
    """The line minus every frozen span: whatever is left is prose to be judged."""
    for lit in literals:
        if lit:
            line = line.replace(lit, "")
    return line


def faulty(text: str):
    """Accented tokens of a residual line, tidy enough to print."""
    out = []
    for tok in re.findall(r"\S+", text):
        core = tok.strip(TRIM)
        if core and any(c in ACCENTS for c in core):
            out.append(core)
    return out


def scan_file(path: Path, literals):
    """[(line_number, [tokens])] for the lines carrying a diacritic outside a span."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits = []
    for num, line in enumerate(text.splitlines(), 1):
        reste = residual(line, literals)
        if not any(c in ACCENTS for c in reste):
            continue
        hits.append((num, faulty(reste) or [reste.strip()]))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="pj_lang_lint.py",
        description="Report diacritics outside the frozen spans of the tracked .md.")
    ap.add_argument("--exclusions", metavar="F",
                    help="exclusions file (default: %s)" % DEFAULT_EXCLUSIONS)
    ap.add_argument("chemins", nargs="*", metavar="path",
                    help="restrict the scan to this path (default: the whole corpus)")
    # argparse exits 2 on an unknown flag: that IS the contract, not an accident.
    a = ap.parse_args()

    cwd = Path.cwd()
    root = show_toplevel(cwd)
    if root is None:
        return usage("not inside a git work tree: %s (the corpus is the index, "
                     "never a directory walk)" % cwd)

    exclusions, problem = resolve_exclusions(a.exclusions, root, cwd)
    if problem or exclusions is None:
        return usage(problem or "no exclusions file resolved")
    literals, problem = load_literals(exclusions)
    if problem or literals is None:
        return usage(problem or "no frozen literal loaded")

    cibles = []
    for arg in a.chemins:
        p = Path(arg)
        if not p.is_absolute():
            p = cwd / p
        if not p.exists():
            return usage("path not found: %s" % arg)
        try:
            rel = os.path.relpath(p, root)
        except ValueError:  # pragma: no cover - different drive, non-POSIX only
            rel = str(p)
        if os.path.isabs(rel) or rel.startswith(".."):
            rel = str(p)
        if p.is_dir():
            cibles.extend(tracked_md(root, prefix=rel if rel != "." else ""))
        else:
            cibles.append(rel)

    if not a.chemins:
        try:
            cibles = tracked_md(root)
        except RuntimeError as exc:
            return usage("cannot enumerate the corpus: %s" % exc)

    violations = 0
    fichiers = 0
    for rel in dict.fromkeys(cibles):
        hits = scan_file(root / rel, literals)
        if not hits:
            continue
        fichiers += 1
        for num, toks in hits:
            violations += 1
            print("[pj-lang-lint] %s:%d — diacritic outside a frozen span: %s"
                  % (rel, num, " ".join("« %s »" % t for t in toks[:4])))
    if violations:
        print("[pj-lang-lint] %d line(s) in %d file(s) — %d tracked .md scanned, "
              "spans frozen by %s"
              % (violations, fichiers, len(set(cibles)),
                 exclusions.name))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
