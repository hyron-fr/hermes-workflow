"""Tests du gate de readiness branché dans le pont GitHub (gh_kanban_bridge).

Règle : si PJ_READINESS_REPO pointe vers un clone du dépôt cible, le pull
n'importe QUE si le repo atteint le niveau minimum (modèle Agent Readiness,
Factory). Dégradation ouverte : script absent/erreur => pull sans gate.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

PATH = str(REPO / "pipeline" / "gh_kanban_bridge.py")


@pytest.fixture()
def br(monkeypatch):
    """Module bridge rechargé à chaque test, env de base posée avant import."""
    monkeypatch.setenv("GH_REPO", "hyron-fr/dino-game")
    monkeypatch.setenv("KANBAN_BOARD", "pj-dino-game")
    monkeypatch.setenv("PJ_READINESS_REPO", "")
    monkeypatch.setenv("PJ_READINESS_SCRIPT", "")
    spec = importlib.util.spec_from_file_location("br_readiness", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def arm(br, monkeypatch, repo: str, script: str = "", min_level: str = "3") -> None:
    """Arme le gate : le bridge lit ses constantes à l'import → on patche le module."""
    monkeypatch.setattr(br, "PJ_READINESS_REPO", repo)
    monkeypatch.setattr(br, "PJ_READINESS_SCRIPT", script)
    monkeypatch.setattr(br, "PJ_READINESS_MIN", min_level)


# ---------------------------------------------------------------- opt-in ----

def test_gate_inactive_sans_env(br):
    """Sans PJ_READINESS_REPO, le gate est transparent (comportement historique)."""
    v = br.readiness_verdict()
    assert v["blocked"] is False
    assert v["level"] is None


# ---------------------------------------------------------- dégradation ----

def test_script_absent_open_degradation(br, tmp_path, monkeypatch):
    """Script introuvable → pull SANS gate (pas de blocage dur)."""
    arm(br, monkeypatch, str(tmp_path), script=str(tmp_path / "absent.py"))
    v = br.readiness_verdict()
    assert v["blocked"] is False
    assert v["reason"] == "script absent"


def test_repo_inexistant_ouvre(br, tmp_path, monkeypatch):
    """Repo inexistant (exit 2 du script) → dégradation ouverte, log visible."""
    arm(br, monkeypatch, str(tmp_path / "inexistant"),
        script=str(REPO / "pipeline" / "pj_readiness.py"))
    v = br.readiness_verdict()
    assert v["blocked"] is False
    assert v["reason"] == "erreur exécution"


# ------------------------------------------------------------ verdicts ----

def test_repo_non_pret_bloque(br, tmp_path, monkeypatch):
    """Repo vide (N0 < N3 requis) → pull suspendu."""
    repo = tmp_path / "vide"
    repo.mkdir()
    arm(br, monkeypatch, str(repo), script=str(REPO / "pipeline" / "pj_readiness.py"))
    v = br.readiness_verdict()
    assert v["blocked"] is True
    assert v["level"] == 0
    assert v["min"] == "3"
    assert "insuffisant" in v["reason"]


def test_repo_pret_passe(br, tmp_path, monkeypatch):
    """Repo N2 avec min-level 2 → passe."""
    repo = tmp_path / "ok"
    (repo / "tests").mkdir(parents=True)
    for rel in ("README.md", ".flake8", "mypy.ini", "pytest.ini", "Makefile",
                "tests/test_a.py", "AGENTS.md", ".env.example",
                "docker-compose.yml", ".pre-commit-config.yaml",
                ".gitignore"):
        (repo / rel).touch()
    (repo / ".git").mkdir()
    arm(br, monkeypatch, str(repo),
        script=str(REPO / "pipeline" / "pj_readiness.py"), min_level="2")
    v = br.readiness_verdict()
    assert v["blocked"] is False
    assert v["level"] == 2
    assert v["min"] == "2"


def test_verdict_level_parsing(br, tmp_path, monkeypatch):
    """Le niveau est extrait du message REFUS (atteint N<x>)."""
    repo = tmp_path / "vide2"
    repo.mkdir()
    arm(br, monkeypatch, str(repo), script=str(REPO / "pipeline" / "pj_readiness.py"))
    v = br.readiness_verdict()
    assert v["level"] == 0


# ------------------------------------------------------ intégration pull ----

def test_pull_suspended_writes_log(br, tmp_path, monkeypatch, capsys):
    """pull() suspendu n'appelle PAS list_open_issues (aucun fetch GitHub)."""
    repo = tmp_path / "vide3"
    repo.mkdir()
    arm(br, monkeypatch, str(repo), script=str(REPO / "pipeline" / "pj_readiness.py"))
    monkeypatch.setattr(br, "QUIET_IDLE", False)  # log() -> print direct
    called = {"n": 0}

    def boom():
        called["n"] += 1
        raise AssertionError("list_open_issues ne doit pas être appelé")

    monkeypatch.setattr(br, "list_open_issues", boom)
    br.pull()
    out = capsys.readouterr().out
    assert called["n"] == 0
    assert "PULL SUSPENDU" in out
    assert "readiness" in out.lower()


def test_pull_passes_gate_then_fails_on_gh(br, tmp_path, monkeypatch, capsys):
    """Gate passant → pull continue (échec ensuite sur gh absent = OK, hors scope)."""
    repo = tmp_path / "ok2"
    (repo / "tests").mkdir(parents=True)
    for rel in ("README.md", ".flake8", "mypy.ini", "pytest.ini", "Makefile",
                "tests/test_a.py", "AGENTS.md", ".env.example",
                "docker-compose.yml", ".pre-commit-config.yaml", ".gitignore"):
        (repo / rel).touch()
    (repo / ".git").mkdir()
    arm(br, monkeypatch, str(repo),
        script=str(REPO / "pipeline" / "pj_readiness.py"), min_level="2")
    monkeypatch.setattr(br, "QUIET_IDLE", False)  # log() -> print direct
    called = {"n": 0}

    def fake_list():
        called["n"] += 1
        return []

    monkeypatch.setattr(br, "list_open_issues", fake_list)
    br.pull()
    assert called["n"] == 1  # le pull a bien continué après le gate