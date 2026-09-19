"""Tests du gate de couverture du pont GitHub (renfo 1).

Règle : une issue qui recouvre du travail DÉJÀ en vol (PR ouverte, issue ouverte
avec graphe) ne doit PAS être importée en nouveau graphe — sinon 3 issues pour un
changement. La décision reste humaine, mais elle est POSÉE au lieu d'être contournée.
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
import os

import pytest

PATH = str(REPO / "pipeline" / "gh_kanban_bridge.py")


@pytest.fixture(scope="module")
def br():
    os.environ.setdefault("GH_REPO", "hyron-fr/dino-game")
    os.environ.setdefault("KANBAN_BOARD", "pj-dino-game")
    spec = importlib.util.spec_from_file_location("br", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------- références ---

def test_refs_extracts_hash_numbers(br):
    assert br.issue_refs("corrige #4 et aussi #9.") == {4, 9}


def test_refs_ignores_bare_numbers(br):
    """« 600 » ou « x=848 » ne sont pas des références d'issue."""
    assert br.issue_refs("Q2 600, sprite x=848 y=2, 26x50") == set()


def test_refs_ignores_url_refs(br):
    """Une URL d'import complète n'est pas une référence de chevauchement."""
    assert br.issue_refs("Importé depuis https://github.com/hyron-fr/dino-game/issues/4") == set()


def test_refs_handles_empty(br):
    assert br.issue_refs("") == set()
    assert br.issue_refs(None) == set()


# ------------------------------------------------------------------ titres ----

def test_title_tokens_normalizes(br):
    t = br.title_tokens("Refonte graphique des acteurs (dino, cactus, ptérosaure)")
    assert "graphique" in t and "acteurs" in t
    assert "refonte" in t
    # les mots vides et la ponctuation disparaissent
    assert "des" not in t and "(" not in " ".join(t)


def test_title_overlap_detects_related_issues(br):
    """Le cas VÉCU : #9 « Refonte graphique des acteurs » vs #4 « Améliorer l'UX »
    ne se recouvrent PAS par le titre — c'est la référence #4 dans le body qui
    révèle le chevauchement."""
    a = br.title_tokens("Refonte graphique des acteurs (dino, cactus, ptérosaure)")
    b = br.title_tokens("Améliorer l'UX")
    assert br.title_overlap(a, b) < 0.34


def test_title_overlap_same_subject(br):
    a = br.title_tokens("Refonte graphique des acteurs dino")
    b = br.title_tokens("Refonte graphique des acteurs (dino, cactus)")
    assert br.title_overlap(a, b) >= 0.5


# ------------------------------------------------------------------- gate -----

def test_gate_blocks_issue_referencing_open_pr(br):
    """Une issue qui cite une issue déjà en vol est SUSPECTE (décision humaine)."""
    issue = {"number": 9, "title": "Refonte graphique", "body": "suite de #4"}
    ctx = {"open_issues": {4}, "open_pr_issues": {4}, "graph_issues": {4}}
    v = br.coverage_verdict(issue, ctx)
    assert v["blocked"] is True
    assert 4 in v["overlaps"]


def test_gate_blocks_issue_covered_by_open_pr_without_ref(br):
    """Pas de référence explicite, mais recouvrement de titre → suspect aussi."""
    issue = {"number": 11, "title": "Refonte graphique des acteurs dino",
             "body": "silhouettes à revoir"}
    ctx = {"open_issues": {4},
           "open_pr_issues": {4},
           "graph_issues": {4},
           "titles": {4: "Refonte graphique des acteurs (dino, cactus)"}}
    v = br.coverage_verdict(issue, ctx)
    assert v["blocked"] is True
    assert 4 in v["overlaps"]


def test_gate_allows_genuinely_new_issue(br):
    """Une issue réellement neuve passe : le gate n'est pas un blocage systématique."""
    issue = {"number": 12, "title": "Ajouter un compteur de parties",
             "body": "nouvelle fonctionnalité de statistiques"}
    ctx = {"open_issues": {4}, "open_pr_issues": {4}, "graph_issues": {4},
           "titles": {4: "Refonte graphique des acteurs"}}
    v = br.coverage_verdict(issue, ctx)
    assert v["blocked"] is False
    assert v["overlaps"] == []


def test_gate_does_not_block_on_itself(br):
    """Une issue ne se référence pas elle-même (réédition, note de suivi)."""
    issue = {"number": 4, "title": "Améliorer l'UX", "body": "voir #4"}
    ctx = {"open_issues": {4}, "open_pr_issues": {4}, "graph_issues": {4},
           "titles": {4: "Améliorer l'UX"}}
    v = br.coverage_verdict(issue, ctx)
    assert v["blocked"] is False


def test_gate_reports_why(br):
    """Le verdict doit être explicable à l'humain (c'est lui qui décide)."""
    issue = {"number": 9, "title": "Refonte graphique", "body": "suite de #4"}
    ctx = {"open_issues": {4}, "open_pr_issues": {4}, "graph_issues": {4}}
    v = br.coverage_verdict(issue, ctx)
    assert v["reason"]
    assert "#4" in v["reason"]


# ------------------------------------------------------- lien PR -> issue ------

def test_closes_line_format(br):
    """t6 doit écrire une ligne de fermeture NATIVE — sinon GitHub ne lie pas la PR."""
    assert br.closes_line(7) == "Closes #7"
    assert "7" in br.closes_line(7)
