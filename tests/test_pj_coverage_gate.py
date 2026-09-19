"""Tests du gate de couverture par fichier (pj_coverage_gate).

D4 : le seuil porte sur les fichiers MODIFIÉS par la branche (scope=diff),
pas sur tout le repo.
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest

PATH = str(REPO / "bridge" / "pj_coverage_gate.py")

COV_JSON = {
    "files": {
        "kerios_core/core/indexer.py": {"summary": {"percent_covered": 92.5}},
        "kerios_core/interfaces/cli.py": {"summary": {"percent_covered": 61.0}},
        "kerios_core/_version.py": {"summary": {"percent_covered": 0.0}},
    }
}


@pytest.fixture(scope="module")
def cg():
    spec = importlib.util.spec_from_file_location("cg", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parse_coverage_json(cg):
    pct = cg.parse_coverage_json(COV_JSON)
    assert pct["kerios_core/core/indexer.py"] == 92.5
    assert pct["kerios_core/interfaces/cli.py"] == 61.0


def test_violations_below_min(cg):
    """_version.py est exclu automatiquement (is_code_file) : seule cli.py est fautive."""
    pct = cg.parse_coverage_json(COV_JSON)
    v = cg.violations(pct, minimum=80.0, ignore=())
    assert v == [("kerios_core/interfaces/cli.py", 61.0)]


def test_violations_orders_by_pct(cg):
    """Deux fichiers fautifs : ordre croissant de couverture (le pire d'abord)."""
    pct = {"a.py": 40.0, "b.py": 10.0, "c.py": 90.0}
    assert cg.violations(pct, minimum=80.0, ignore=()) == [("b.py", 10.0), ("a.py", 40.0)]


def test_violations_respects_ignore(cg):
    pct = cg.parse_coverage_json(COV_JSON)
    v = cg.violations(pct, minimum=80.0, ignore=("kerios_core/interfaces/cli.py",))
    assert v == []


def test_violations_empty_when_all_above(cg):
    assert cg.violations({"core/a.py": 80.0}, minimum=80.0, ignore=()) == []


def test_violations_scoped_to_diff(cg):
    """D4 : hors périmètre du diff, aucune violation n'est remontée."""
    pct = {"core/a.py": 50.0, "core/vieux.py": 20.0}
    assert cg.violations(pct, minimum=80.0, ignore=(), scope={"core/a.py"}) == [("core/a.py", 50.0)]


def test_is_code_file_excludes_configs_and_tests(cg):
    assert cg.is_code_file("core/game.ts") is True
    assert cg.is_code_file("vite.config.ts") is False
    assert cg.is_code_file("types/global.d.ts") is False
    assert cg.is_code_file("tests/domain/game.test.ts") is False
    assert cg.is_code_file("kerios_core/_version.py") is False
