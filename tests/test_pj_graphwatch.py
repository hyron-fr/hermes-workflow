"""Tests de pj_graphwatch.build_plan — topologie parallèle + convergence + worktree.

D2 : test-k ∥ dev-k (même worktree, même branche) puis conv-k.
D3 : worktree-mk en amont de toutes les slices, worktree-rm en aval (post-merge).
Anti-deadlock : les cartes de production sont PARENTS de t6.
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest

PATH = str(REPO / "pipeline" / "pj_graphwatch.py")

DOC = {"issue": 3, "repo": "dino-game", "branch": "wt/issue-3-x", "slices": [
    {"k": 1, "slug": "a", "depends_on": [],
     "parallel": {"test": {"title": "test-1 a", "body": "b"},
                  "dev": {"title": "dev-1 a", "body": "b"}},
     "convergence": {"title": "conv-1 a", "body": "b"},
     "doc": {"title": "doc-1 a", "body": "b"}},
    {"k": 2, "slug": "b", "depends_on": [1],
     "parallel": {"test": {"title": "test-2 b", "body": "b"},
                  "dev": {"title": "dev-2 b", "body": "b"}},
     "convergence": {"title": "conv-2 b", "body": "b"},
     "doc": {"title": "doc-2 b", "body": "b"}},
]}


@pytest.fixture(scope="module")
def gw():
    spec = importlib.util.spec_from_file_location("gw", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _plan(gw):
    return gw.build_plan(DOC, t5_id="t5x", board="pj-dino-game", root_id="troot")


def test_worktree_mk_is_upstream_of_all_slices(gw):
    """worktree-mk dépend de t5 (le GO), pas de t6 : le worktree partagé doit
    exister AVANT test-k/dev-k, sinon le peer programming n'a pas de terrain."""
    by = {c["key"]: c for c in _plan(gw)["cards"]}
    assert by["worktree-mk"]["assignee"] == "pj-dev"
    assert by["worktree-mk"]["parents"] == ["t5x"]
    # on compare à la constante du module : le chemin du repo est un parametre,
    # pas une valeur codee en dur (le test doit suivre l'environnement reel)
    assert by["worktree-mk"]["workspace"].startswith("worktree:")
    assert by["worktree-mk"]["branch"] == "wt/issue-3-x"
    for key in ("test-1", "dev-1", "test-2", "dev-2"):
        assert "worktree-mk" in by[key]["parents"], f"{key} doit attendre worktree-mk"


def test_parallel_siblings_share_worktree_and_branch(gw):
    by = {c["key"]: c for c in _plan(gw)["cards"]}
    for k in (1, 2):
        t, d = by[f"test-{k}"], by[f"dev-{k}"]
        assert t["workspace"] == d["workspace"], f"slice {k}: worktree non partagé"
        assert t["branch"] == d["branch"] == "wt/issue-3-x"
        assert t["assignee"] == "pj-test" and d["assignee"] == "pj-dev"
        assert f"dev-{k}" not in t["parents"], f"slice {k}: test ne doit pas attendre dev"
        assert f"test-{k}" not in d["parents"], f"slice {k}: dev ne doit pas attendre test"


def test_convergence_waits_for_both_sides(gw):
    by = {c["key"]: c for c in _plan(gw)["cards"]}
    assert set(by["conv-1"]["parents"]) == {"test-1", "dev-1"}
    assert by["conv-1"]["assignee"] == "pj-test"
    assert by["conv-2"]["assignee"] == "pj-test"


def test_doc_after_convergence(gw):
    by = {c["key"]: c for c in _plan(gw)["cards"]}
    assert by["doc-1"]["parents"] == ["conv-1"]
    assert by["doc-1"]["assignee"] == "pj-doc"
    assert by["doc-2"]["parents"] == ["conv-2"]


def test_slice_dependency_goes_through_convergence(gw):
    by = {c["key"]: c for c in _plan(gw)["cards"]}
    assert "conv-1" in by["test-2"]["parents"]
    assert "conv-1" in by["dev-2"]["parents"]


def test_plan_card_keys_and_assignees(gw):
    by = {c["key"]: c for c in _plan(gw)["cards"]}
    for key in ("test-1", "test-2"):
        assert by[key]["assignee"] == "pj-test"
    for key in ("dev-1", "dev-2", "worktree-mk", "worktree-rm"):
        assert by[key]["assignee"] == "pj-dev"
    for key in ("doc-1", "doc-2", "doc-review", "doc-memory"):
        assert by[key]["assignee"] == "pj-doc"
    assert by["t6"]["assignee"] == "pj-master"


def test_t6_waits_only_for_t5(gw):
    by = {c["key"]: c for c in _plan(gw)["cards"]}
    assert by["t6"]["parents"] == ["t5x"]


def test_anti_deadlock_conv_and_doc_are_parents_of_t6(gw):
    links = _plan(gw)["links"]
    # Sens : `link <parent> <child>` -> l'enfant ATTEND le parent.
    # [key, "t6"] = key est parent de t6, donc t6 attend la production.
    # L'écrire à l'envers (["t6", key]) ferait attendre la PRODUCTION jusqu'à t6 :
    # c'est le deadlock que cette carte doit précisément empêcher.
    for key in ("conv-1", "conv-2", "doc-1", "doc-2", "doc-review"):
        assert [key, "t6"] in links, f"{key} doit être parent de t6 (anti-deadlock)"
        assert ["t6", key] not in links, f"{key} : sens inversé = deadlock"


def test_worktree_rm_is_post_merge(gw):
    links = _plan(gw)["links"]
    assert ["t6", "worktree-rm"] in links
    assert ["worktree-rm", "doc-memory"] in links
    assert ["doc-memory", "troot"] in links
    assert ["t6", "troot"] in links


def test_all_worktree_cards_carry_the_branch(gw):
    """D3 : toute carte en worktree DOIT porter --branch, sinon worktree séparé."""
    for c in _plan(gw)["cards"]:
        if str(c["workspace"]).startswith("worktree:"):
            assert c.get("branch") == "wt/issue-3-x", f"{c['key']} sans branche"
