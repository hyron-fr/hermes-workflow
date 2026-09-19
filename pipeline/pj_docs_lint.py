#!/usr/bin/env python3
"""pj_docs_lint — valide le vault docs/ (frontmatter, wikilinks, notes orphelines).

Conventions (voir SOUL pj-doc) : frontmatter YAML obligatoire (type/status/tags),
liens [[note]] résolus par basename, toute note non-MOC référencée depuis le MOC
de sa section.

Usage : pj_docs_lint.py <repo_path> [--json]
Sortie : stdout vide = conforme (tick muet). exit 0 conforme, 1 non conforme, 2 erreur.
"""
import json
import re
import sys
from pathlib import Path

REQUIRED_KEYS = ("type", "status", "tags")
SECTIONS = ("architecture", "functional")
EXCLUDE_PARTS = ("playtest", ".obsidian")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def parse_frontmatter(text: str) -> dict:
    """Frontmatter YAML minimal (clé: valeur, listes inline [a, b]). {} si absent."""
    m = FM_RE.match(text)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            out[k] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        else:
            out[k] = v.strip("'\"")
    return out


def missing_keys(fm: dict, required=REQUIRED_KEYS) -> list:
    return [k for k in required if k not in fm]


def extract_wikilinks(text: str) -> list:
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]


def unresolved_links(links: list, notes: set) -> list:
    """Un lien résout si son dernier segment (basename) est une note existante."""
    bad = []
    for link in links:
        base = link.split("/")[-1].strip()
        if base and base not in notes:
            bad.append(link)
    return bad


def orphans(notes: list, moc_text: str) -> list:
    """Notes absentes du MOC fourni (les MOC eux-mêmes sont exclus par l'appelant)."""
    linked = {l.split("/")[-1].strip() for l in extract_wikilinks(moc_text)}
    return [n for n in notes if n not in linked]


def scan(repo: Path) -> dict:
    """Valide le vault pj : uniquement les notes sous docs/architecture/ et docs/functional/.

    La documentation héritée à plat dans docs/ (fichiers préexistants au vault pj)
    est HORS PÉRIMÈTRE : elle n'a pas à recevoir le frontmatter pj, et la signaler
    bloquerait les cartes doc-k sur du travail qui n'est pas le leur.
    """
    docs = repo / "docs"
    result = {"errors": [], "notes": 0}
    if not docs.is_dir():
        return result
    notes = {}
    for section in SECTIONS:
        sec_dir = docs / section
        if not sec_dir.is_dir():
            continue
        for p in sec_dir.rglob("*.md"):
            if any(part in EXCLUDE_PARTS for part in p.parts):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            notes[p.stem] = {"path": p, "text": text, "fm": parse_frontmatter(text),
                             "section": section}
            result["notes"] += 1
    if not notes:
        return result

    for stem, n in notes.items():
        if stem.lower() in ("readme", "glossary"):
            continue
        miss = missing_keys(n["fm"])
        if miss:
            rel = n["path"].relative_to(repo)
            result["errors"].append(f"{rel}: frontmatter incomplet ({', '.join(miss)})")
        bad = unresolved_links(extract_wikilinks(n["text"]), set(notes))
        for b in bad:
            rel = n["path"].relative_to(repo)
            result["errors"].append(f"{rel}: lien non résolu [[{b}]]")

    for section in SECTIONS:
        moc = docs / section / "README.md"
        if not moc.exists():
            continue
        section_notes = [s for s, n in notes.items()
                         if (docs / section) in n["path"].parents and s.lower() != "readme"]
        moc_text = moc.read_text(encoding="utf-8", errors="replace")
        for o in orphans(section_notes, moc_text):
            result["errors"].append(
                f"docs/{section}/README.md: note orpheline [[{o}]] non référencée")
    return result


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: pj_docs_lint.py <repo_path> [--json]")
        return 2
    repo = Path(sys.argv[1]).expanduser().resolve()
    if not repo.is_dir():
        print(f"repo introuvable: {repo}")
        return 2
    res = scan(repo)
    if "--json" in sys.argv:
        print(json.dumps(res, indent=2, default=str))
    elif res["errors"]:
        for e in res["errors"]:
            print(f"[pj-docs] {e}")
    return 1 if res["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
