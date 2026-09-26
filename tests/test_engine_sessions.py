"""Tests P6 : reprise de session (resume/fork) du moteur + capture backend.

Sans réseau, sans LLM : le sidecar de sessions est simulé (tmp_path) et la
capture backend est vérifiée sur le parsing de la sortie `--pass-session-id`
(format réel du CLI hermes, capturé en prod le 26/09).
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pipeline"))


@pytest.fixture(scope="module")
def eng():
    spec = importlib.util.spec_from_file_location(
        "engine", REPO / "pipeline" / "engine.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def backends():
    spec = importlib.util.spec_from_file_location(
        "backends", REPO / "pipeline" / "backends.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def state_dir(tmp_path, monkeypatch, eng):
    """Redirecte STATE_DIR du moteur vers un tmp (aucun .pipeline réel)."""
    monkeypatch.setattr(eng, "STATE_DIR", tmp_path / ".pipeline")
    monkeypatch.setattr(eng, "ARTIFACT_DIR", tmp_path / ".pipeline" / "artifacts")
    return tmp_path


# ------------------------------------------------------------------ parsing

def test_parse_session_id_cli_format(backends):
    out = ("Réponse de l'agent.\n\n"
           "Session:        20260926_113527_bec163\n"
           "Duration:       29s\n"
           "Messages:       2 (1 user, 0 tool calls)")
    assert backends.parse_session_id(out) == "20260926_113527_bec163"


def test_parse_session_id_absent(backends):
    assert backends.parse_session_id("aucun bloc d'arrêt ici") is None
    assert backends.parse_session_id("") is None
    assert backends.parse_session_id(None) is None


def test_parse_session_id_no_false_positive(backends):
    # "Session:" en milieu de phrase (pas ancrée au début de ligne + espace)
    out = "Le mot Session:foo dans le texte\nSession x (mal formé)\n"
    assert backends.parse_session_id(out) is None


# ------------------------------------------------------------------ sidecar

def test_save_and_load_roundtrip(eng, state_dir):
    eng.save_session("t_x", "step1", "ddd", "20260926_000000_ab12cd")
    p = eng.session_sidecar_path("t_x")
    assert p.exists()
    data = json.loads(p.read_text())
    assert data == {"step1:ddd": "20260926_000000_ab12cd"}
    # save avec None = no-op (rien d'écrit)
    eng.save_session("t_x", "step1", "ddd", None)
    assert json.loads(p.read_text()) == {"step1:ddd": "20260926_000000_ab12cd"}


def test_load_sessions_corrupted_returns_empty(eng, state_dir):
    p = eng.session_sidecar_path("t_bad")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{pas du json")
    assert eng._load_sessions("t_bad") == {}
    p.write_text("[1,2,3]")
    assert eng._load_sessions("t_bad") == {}   # pas un dict


def test_save_session_missing_id_is_noop(eng, state_dir):
    eng.save_session("t_x", "s", "r", None)
    eng.save_session("t_x", "s", "r", "")
    assert not eng.session_sidecar_path("t_x").exists()


# ------------------------------------------------------------------ reprise

def test_resume_requires_flag(eng, state_dir):
    eng.save_session("t_x", "s", "r", "sid-1")
    # pas de flag resume -> None (fork par défaut)
    assert eng.resume_session_for({"id": "s"}, "t_x", "s", "r") is None
    # flag resume: true -> l'id capturé
    assert eng.resume_session_for({"id": "s", "resume": True},
                                  "t_x", "s", "r") == "sid-1"


def test_resume_per_role(eng, state_dir):
    eng.save_session("t_x", "s", "ddd", "sid-ddd")
    eng.save_session("t_x", "s", "tdd", "sid-tdd")
    step = {"id": "s", "resume": True}
    assert eng.resume_session_for(step, "t_x", "s", "ddd") == "sid-ddd"
    assert eng.resume_session_for(step, "t_x", "s", "tdd") == "sid-tdd"
    assert eng.resume_session_for(step, "t_x", "s", "inconnu") is None


def test_resume_unknown_role_is_none(eng, state_dir):
    step = {"id": "s", "resume": True}
    assert eng.resume_session_for(step, "t_neuf", "s", "ddd") is None
