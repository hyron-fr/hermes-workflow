"""Tests du validateur de vault docs/ (pj_docs_lint)."""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest

PATH = str(REPO / "pipeline" / "pj_docs_lint.py")
REQUIRED = ("type", "status", "tags")


@pytest.fixture(scope="module")
def dl():
    spec = importlib.util.spec_from_file_location("dl", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parse_frontmatter_ok(dl):
    text = "---\ntype: adr\nstatus: draft\ntags: [a, b]\n---\n\n# Titre\n"
    fm = dl.parse_frontmatter(text)
    assert fm["type"] == "adr" and fm["tags"] == ["a", "b"]


def test_parse_frontmatter_absent(dl):
    assert dl.parse_frontmatter("# pas de frontmatter\n") == {}


def test_missing_keys(dl):
    assert dl.missing_keys({"type": "adr"}, REQUIRED) == ["status", "tags"]


def test_extract_wikilinks(dl):
    body = "Voir [[architecture/README|MOC]] et [[game-loop]] puis [[decisions/ADR-0001-hexagonal]]"
    assert dl.extract_wikilinks(body) == [
        "architecture/README", "game-loop", "decisions/ADR-0001-hexagonal"]


def test_unresolved_links(dl):
    notes = {"README", "game-loop"}
    links = ["game-loop", "inconnue", "decisions/ADR-9999-x"]
    assert dl.unresolved_links(links, notes) == ["inconnue", "decisions/ADR-9999-x"]


def test_orphan_notes(dl):
    moc = "[[game-loop]] et [[score]]"
    notes = ["game-loop", "score", "oubliée"]
    assert dl.orphans(notes, moc) == ["oubliée"]
