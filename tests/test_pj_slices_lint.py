"""Tests du validateur slices.json (contrat du graphe de dev).

Topologie (D2/D3) : lot parallèle test ∥ dev, puis convergence, puis doc.
Branche unique pour l'issue (partage du worktree). D4 : la carte test porte
≥3 scénarios Gherkin (nominal, limite, erreur).
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest

PATH = str(REPO / "pipeline" / "pj_slices_lint.py")

GOOD_TEST_BODY = """1. Contexte & Objectif
Objectif : la persistance du high score est garantie.
2. Critères d'acceptation (BDD/Gherkin)
Fonctionnalité: persistance du high score
  Scénario: nominal — le high score est relu au démarrage
    Étant donné un storage contenant 1200
    Quand le jeu démarre
    Alors le high score affiché est 1200
  Scénario: limite — score égal au high score existant
    Étant donné un storage contenant 1200 et un score courant de 1200
    Quand la partie se termine
    Alors le high score reste 1200
  Scénario: erreur — storage corrompu
    Étant donné un storage illisible
    Quand le jeu démarre
    Alors le high score vaut 0 sans exception
"""


@pytest.fixture(scope="module")
def sl():
    spec = importlib.util.spec_from_file_location("sl", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _slice(k, deps=(), body=GOOD_TEST_BODY):
    return {"k": k, "slug": f"s{k}", "depends_on": list(deps),
            "parallel": {"test": {"title": f"test-{k}", "body": body},
                         "dev": {"title": f"dev-{k}", "body": "b"}},
            "convergence": {"title": f"conv-{k}", "body": "b"},
            "doc": {"title": f"doc-{k}", "body": "b"}}


def _doc(slices=None, **kw):
    d = {"issue": 3, "repo": "r", "branch": "wt/issue-3-x",
         "slices": slices if slices is not None else [_slice(1)]}
    d.update(kw)
    return d


def test_ok(sl):
    ok, errs = sl.validate(_doc([_slice(1), _slice(2, [1])]))
    assert ok and errs == []


def test_empty_slices(sl):
    ok, errs = sl.validate(_doc([]))
    assert not ok and any("aucune slice" in e for e in errs)


def test_missing_branch(sl):
    d = _doc(); del d["branch"]
    ok, errs = sl.validate(d)
    assert not ok and any("branch" in e for e in errs)


def test_missing_parallel_test(sl):
    s = _slice(1); del s["parallel"]["test"]
    ok, errs = sl.validate(_doc([s]))
    assert not ok and any("parallel.test" in e for e in errs)


def test_missing_convergence(sl):
    s = _slice(1); del s["convergence"]
    ok, errs = sl.validate(_doc([s]))
    assert not ok and any("convergence" in e for e in errs)


def test_non_contiguous_k(sl):
    ok, errs = sl.validate(_doc([_slice(1), _slice(3)]))
    assert not ok and any("contigus" in e for e in errs)


def test_forward_dependency(sl):
    ok, errs = sl.validate(_doc([_slice(1, [2]), _slice(2)]))
    assert not ok and any("dépendance" in e for e in errs)


def test_missing_issue(sl):
    d = _doc(); del d["issue"]
    ok, errs = sl.validate(d)
    assert not ok and any("issue" in e for e in errs)


def test_gherkin_three_scenarios_required(sl):
    """D4 : nominal + limite + erreur sont obligatoires."""
    body = ("1. Contexte & Objectif\n2. Critères d'acceptation\n"
            "Fonctionnalité: x\n  Scénario: nominal — cas heureux\n"
            "  Scénario: limite — bord\n")   # pas de scénario d'erreur
    ok, errs = sl.validate(_doc([_slice(1, body=body)]))
    assert not ok and any("erreur" in e for e in errs)


def test_gherkin_missing_limite(sl):
    body = ("Fonctionnalité: x\n  Scénario: nominal — ok\n"
            "  Scénario: erreur — ko\n  Scénario: autre cas nominal\n")
    ok, errs = sl.validate(_doc([_slice(1, body=body)]))
    assert not ok and any("limite" in e for e in errs)

def _slugged(k, slug):
    """Slice conforme dont le SLUG est controle (pour tester la detection de preview)."""
    d = _slice(k)
    d["slug"] = slug
    return d


# ------------------------------------------- slice preview (renfo 2) ----------

def test_preview_required_when_prototype_needed(sl):
    """`prototype_required=true` + aucune slice preview -> NON conforme."""
    doc = _doc([_slugged(1, "decor"), _slugged(2, "acteurs")], prototype_required=True)
    ok, errs = sl.validate(doc)
    assert ok is False
    assert any("preview" in e.lower() for e in errs)


def test_preview_present_satisfies_requirement(sl):
    """Avec la slice 0 preview en tete, la conformite est acquise."""
    doc = _doc([_slugged(1, "preview-artefact"), _slugged(2, "decor")],
               prototype_required=True)
    ok, errs = sl.validate(doc)
    assert ok is True, errs


def test_no_preview_required_by_default(sl):
    """`PROTOTYPE: non` = pas de slice preview imposee (cas normal)."""
    ok, errs = sl.validate(_doc([_slugged(1, "compteur")]))
    assert ok is True, errs


def test_preview_must_be_first(sl):
    """La preview doit etre la PREMIERE slice : sinon le tunnel repart quand meme."""
    doc = _doc([_slugged(1, "decor"), _slugged(2, "preview-artefact")],
               prototype_required=True)
    ok, errs = sl.validate(doc)
    assert ok is False
    assert any("preview" in e.lower() for e in errs)


def test_preview_can_be_detected_by_slug(sl):
    """Detection souple : `preview`, `proto`, `maquette` en tete de slug."""
    for slug in ("preview-artefact", "proto-visuel", "maquette-ecran"):
        doc = _doc([_slugged(1, slug), _slugged(2, "suite")], prototype_required=True)
        ok, errs = sl.validate(doc)
        assert ok is True, (slug, errs)
