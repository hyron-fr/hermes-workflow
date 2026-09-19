"""Tests de l'alimentation Hindsight depuis le vault docs/ (post-merge)."""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest

PATH = str(REPO / "pipeline" / "pj_docs_memory.py")


@pytest.fixture(scope="module")
def dm():
    spec = importlib.util.spec_from_file_location("dm", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_iter_notes_excludes_playtest(dm, tmp_path):
    docs = tmp_path / "docs"
    (docs / "architecture").mkdir(parents=True)
    (docs / "playtest").mkdir(parents=True)
    (docs / "architecture" / "a.md").write_text("---\ntype: component\n---\ncontenu A")
    (docs / "playtest" / "b.md").write_text("ignore moi")
    notes = list(dm.iter_notes(tmp_path))
    assert [p.name for p, _ in notes] == ["a.md"]


def test_iter_notes_skips_empty(dm, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "vide.md").write_text("   \n\n")
    assert list(dm.iter_notes(tmp_path)) == []


def test_content_hash_is_stable(dm):
    assert dm.content_hash("abc") == dm.content_hash("abc")
    assert dm.content_hash("abc") != dm.content_hash("abd")


def test_build_payload_tags(dm):
    p = dm.build_payload(repo="dino-game", issue=3, relpath="docs/architecture/a.md",
                         text="contenu")
    assert p["tags"] == ["project:dino-game", "doc:docs/architecture/a.md", "issue:3"]
    assert p["context"].startswith("doc:")
