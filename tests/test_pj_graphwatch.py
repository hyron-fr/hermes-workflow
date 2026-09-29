"""Tests de pj_graphwatch.build_plan — topologie parallèle + convergence + worktree.

D2 : test-k ∥ dev-k (même worktree, même branche) puis conv-k.
D3 : worktree-mk en amont de toutes les slices, worktree-rm en aval (post-merge).
Anti-deadlock : les cartes de production sont PARENTS de t6.
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest

# Copie canonique UNIQUE : `bridge/` dupliquait 12 fichiers de `pipeline/`
# et avait divergé — un fichier ne vit qu'à un seul endroit.
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
    by = {c["key"]: c for c in _plan(gw)["cards"]}
    assert by["worktree-mk"]["assignee"] == "pj-dev"
    assert by["worktree-mk"]["parents"] == ["t5x"]  # amont = t5, jamais t6
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
    for key in ("conv-1", "conv-2", "doc-1", "doc-2", "doc-review"):
        # sens kanban : link <parent> <enfant> ⇒ l'enfant ATTEND le parent.
        # Un producteur est parent de t6 → le plan l'exprime par [producer, "t6"].
        assert [key, "t6"] in links, f"{key} doit être parent de t6"


def test_worktree_rm_is_post_merge(gw):
    links = _plan(gw)["links"]
    assert ["t6", "worktree-rm"] in links
    assert ["worktree-rm", "doc-memory"] in links
    assert ["doc-memory", "troot"] in links
    assert ["t6", "troot"] in links


def test_worktree_rm_points_at_the_real_holder_worktree(gw):
    """Le corps doit citer le chemin RÉEL du worktree qui tient la branche.

    Vécu (issue #2) : le manifeste d'adoption déclarait `.worktrees/t_a834f57a` mais le
    générateur recalculait le nom canonique `.worktrees/wt-issue-3-x` — un chemin
    INEXISTANT, donc un `git worktree remove` impossible et un critère d'acceptation
    qu'aucune commande ne peut satisfaire.
    """
    real = f"{gw.ANCHOR_ROOT}/dino-game/.worktrees/t_a834f57a"
    plan = gw.build_plan(DOC, t5_id="t5x", board="pj-dino-game", root_id="troot",
                         holders={"wt/issue-3-x": real})
    assert plan["worktree"]["path"] == real
    body = {c["key"]: c for c in plan["cards"]}["worktree-rm"]["body"]
    assert ".worktrees/t_a834f57a" in body, "le corps doit citer le worktree RÉEL"
    assert "wt-issue-3-x" not in body, "jamais le nom canonique quand un réel existe"


def test_foreign_holder_is_never_adopted(gw):
    """Un worktree HORS anchor n'est pas adopté : garde d'adoption, retour au canonique."""
    plan = gw.build_plan(DOC, t5_id="t5x", board="pj-dino-game", root_id="troot",
                         holders={"wt/issue-3-x": "/tmp/ailleurs/t_a834f57a"})
    assert plan["worktree"]["path"].endswith("/.worktrees/wt-issue-3-x")


def test_worktree_path_falls_back_to_canonical_without_holder(gw):
    """Sans worktree matériéalisé, le nom canonique reste la valeur (pas de régression)."""
    plan = gw.build_plan(DOC, t5_id="t5x", board="pj-dino-game", root_id="troot", holders={})
    assert plan["worktree"]["path"].endswith("/.worktrees/wt-issue-3-x")


def test_all_worktree_cards_carry_the_branch(gw):
    """D3 : toute carte en worktree DOIT porter --branch, sinon worktree séparé."""
    for c in _plan(gw)["cards"]:
        if str(c["workspace"]).startswith("worktree:"):
            assert c.get("branch") == "wt/issue-3-x", f"{c['key']} sans branche"


# --- Corps de la carte de nettoyage post-merge ---------------------------------
# Vécu (issue #2, carte t_7c5b773d) : la v1 du corps exigeait
# `git merge-base --is-ancestor origin/<branche-du-worktree> origin/dev` == exit 0.
# La décision humaine « A ⇒ rebase » a livré le contenu par une branche RE-BASÉE
# (commits ré-émargés, nouveaux SHA) : la branche du worktree n'est pas ancêtre de
# `dev` et ne le sera JAMAIS, alors que son ARBRE est identique à ce qui a été
# mergé. Le worker a donc bloqué à juste titre, sur un critère insatisfiable.

def test_worktree_rm_body_measures_commit_coverage_not_only_the_tree(gw):
    """Le critère doit mesurer la COUVERTURE commit-à-commit, pas seulement l'arbre.

    Vécu (issue #2) : `git diff --quiet origin/dev origin/<branche>` rend exit 0 — l'arbre
    n'a rien que `dev` n'ait pas — ALORS QUE 11 commits de la branche n'ont aucun
    équivalent dans `dev` (suppression de `bridge/`, traduction anglaise des 9 slices).
    Un diff de tip ne voit pas 11 commits d'histoire : l'arbre seul est un faux POSITIF,
    et supprimer sur cette base détruit du travail non livré.
    """
    body = {c["key"]: c for c in _plan(gw)["cards"]}["worktree-rm"]["body"]
    assert "git cherry -v origin/dev" in body, (
        "le critère doit nommer la mesure de couverture commit-à-commit (git cherry)")
    assert "ligne `+`" in body or "lignes `+`" in body, (
        "le corps doit dire ce qu'une sortie `+` signifie : un commit jamais livré")
    assert "faux positif" in body and "faux négatif" in body.lower(), (
        "les deux erreurs de critère (arbre seul = faux positif, lignée seule = faux négatif) "
        "doivent être nommées : un worker doit savoir laquelle il tient")


def test_worktree_rm_body_names_the_ancestor_check_as_a_false_negative(gw):
    """La lignée de commits est citée AU PLUS une fois, et étiquetée FAUX NÉGATIF.

    Elle ne doit jamais réapparaître comme condition d'acceptation : un worker qui
    relit `merge-base --is-ancestor` y voit un critère et bloque à juste titre."""
    body = {c["key"]: c for c in _plan(gw)["cards"]}["worktree-rm"]["body"]
    assert body.count("is-ancestor") <= 1
    assert "FAUX NÉGATIF" in body
