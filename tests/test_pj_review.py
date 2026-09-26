"""Tests de pj_review — rubrique de review P0–P3 (0 LLM).

Fonctions pures via importlib, fixtures tmp_path, sans réseau. Convention :
exits 0 (pass) / 1 (P0/P1) / 2 (artefact illisible ou contrat violé).
"""
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PATH = str(REPO / "pipeline" / "pj_review.py")


@pytest.fixture(scope="module")
def rv():
    spec = importlib.util.spec_from_file_location("rv", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def f(sev, title="t", evidence=None, repro=None):
    d = {"severity": sev, "title": title}
    if evidence:
        d["evidence"] = evidence
    if repro:
        d["repro"] = repro
    return d


# ------------------------------------------------------------------ contrat

def test_pass_empty(rv):
    assert rv.audit([])["verdict"] == "pass"


def test_pass_only_p2_p3(rv):
    res = rv.audit([f("P2", evidence="e"), f("P3")])
    assert res["verdict"] == "pass"
    assert res["counts"]["P2"] == 1 and res["counts"]["P3"] == 1


def test_flag_on_p1(rv):
    res = rv.audit([f("P1", evidence="e"), f("P2", evidence="e")])
    assert res["verdict"] == "flag"
    assert len(res["blocking"]) == 1 and res["blocking"][0]["severity"] == "P1"


def test_block_on_p0(rv):
    res = rv.audit([f("P0", evidence="e"), f("P1", evidence="e")])
    assert res["verdict"] == "block"
    assert len(res["blocking"]) == 2


def test_p0_without_proof_violates_contract(rv):
    with pytest.raises(ValueError, match="sans preuve"):
        rv.audit([f("P0")])
    with pytest.raises(ValueError, match="sans preuve"):
        rv.audit([f("P1", title="t", evidence="  ")])  # preuve vide


def test_unknown_severity_violates_contract(rv):
    with pytest.raises(ValueError, match="sévérité inconnue"):
        rv.audit([{"severity": "P4", "title": "t"}])


def test_missing_title_violates_contract(rv):
    with pytest.raises(ValueError, match="titre"):
        rv.audit([{"severity": "P2"}])


def test_severity_case_insensitive(rv):
    res = rv.audit([{"severity": "p0", "title": "t", "evidence": "e"}])
    assert res["verdict"] == "block"


# ------------------------------------------------------------------ exit

def test_exit_code_mapping(rv):
    assert rv.exit_code(rv.audit([])) == 0
    assert rv.exit_code(rv.audit([f("P2", evidence="e")])) == 0
    assert rv.exit_code(rv.audit([f("P1", evidence="e")])) == 1
    assert rv.exit_code(rv.audit([f("P0", evidence="e")])) == 1


# ------------------------------------------------------------------ CLI

def _write(tmp_path, payload):
    p = tmp_path / "review.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_cli_pass(tmp_path, rv):
    p = _write(tmp_path, {"findings": [f("P3")]})
    import subprocess, sys
    r = subprocess.run([sys.executable, PATH, "--findings", str(p)],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "pass" in r.stdout


def test_cli_block(tmp_path, rv):
    p = _write(tmp_path, {"findings": [f("P0", evidence="boom")]})
    import subprocess, sys
    r = subprocess.run([sys.executable, PATH, "--findings", str(p)],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "block" in r.stdout


def test_cli_contract_violation_exit2(tmp_path, rv):
    p = _write(tmp_path, {"findings": [f("P0")]})
    import subprocess, sys
    r = subprocess.run([sys.executable, PATH, "--findings", str(p)],
                       capture_output=True, text=True)
    assert r.returncode == 2
    assert "sans preuve" in r.stderr


def test_cli_missing_file_exit2(tmp_path, rv):
    import subprocess, sys
    r = subprocess.run([sys.executable, PATH, "--findings", str(tmp_path / "x.json")],
                       capture_output=True, text=True)
    assert r.returncode == 2


def test_cli_json_shape(tmp_path, rv):
    p = _write(tmp_path, {"findings": [f("P1", evidence="e")]})
    import subprocess, sys
    r = subprocess.run([sys.executable, PATH, "--findings", str(p), "--json"],
                       capture_output=True, text=True)
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert data["verdict"] == "flag"
    assert data["counts"]["P1"] == 1
    assert data["blocking"][0]["severity"] == "P1"


def test_load_findings_accepts_wrapped(rv, tmp_path):
    p = _write(tmp_path, {"findings": [f("P3")]})
    assert rv.load_findings(str(p)) == [f("P3")]
