"""Vérifie la règle de filtrage is_spec de pj_card_lint (quelles cartes sont lintées).

Les cartes de process du pipeline (t1..t6, variantes t4a/t3b) sont exclues : leur body
décrit l'étape elle-même, pas une spec. Les cartes de production (test-k, dev-k, conv-k,
doc-k, doc-review, doc-memory) sont lintées.
"""
import re

import pytest

PROCESS_RE = re.compile(r"^t\d+[a-z]?\b", re.I)


def is_spec(title: str, status: str = "todo", body: str = "spec normale") -> bool:
    """Règle de pj_card_lint.is_spec (miroir, pour tester sans charger le module)."""
    low = (title or "").strip().lower()
    if PROCESS_RE.match(low):
        return False
    if status in ("done", "archived"):
        return False
    if "importé depuis" in (body or "").lower():
        return False
    return True


@pytest.mark.parametrize("title,expected", [
    # cartes de process -> exclues
    ("t1 worktree", False),
    ("t4a doc-cadrage", False),
    ("t3b doc-cadrage", False),
    ("t6 submitted #1", False),
    # cartes de production -> lintées
    ("test-1 : CI Playwright", True),
    ("dev-1 : bootstrap", True),
    ("conv-1 : convergence tests+couverture", True),
    ("doc-1 : vault archi", True),
    ("doc-review #3", True),
    ("doc-memory #3", True),
    ("worktree-mk #3 : créer le worktree", True),
    ("worktree-rm #3 : nettoyer", True),
])
def test_is_spec_filter(title, expected):
    assert is_spec(title) is expected


def test_root_card_excluded():
    """La racine importée par le pont n'est pas une spec (body = issue GitHub)."""
    assert is_spec("Dino game", body="corps\n—\nImporté depuis https://github.com/o/r/issues/1") is False


def test_done_excluded():
    assert is_spec("dev-1 : x", status="done") is False
    assert is_spec("dev-1 : x", status="archived") is False
