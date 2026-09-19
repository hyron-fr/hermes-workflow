"""Tests du contrat t3 grill-me (renfo 2).

Le grill-me doit FORCER l'identification des ambiguïtés qui exigent un artefact
(prototype/preview) — au lieu de laisser le tunnel partir 55 h avant le 1er rendu
jugé par l'humain. L'objectif n'est PAS d'ajouter l'humain systématiquement :
c'est de qualifier CHAQUE ambiguïté et de décider comment la lever au plus tôt.
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
import re

import pytest

PATH = str(REPO / "agents" / "pj-master" / "scripts" / "pj_pipeline_deployer.py")


@pytest.fixture(scope="module")
def dep():
    spec = importlib.util.spec_from_file_location("dep", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_grill_body_imposes_ambiguity_quadrant(dep):
    """Le body de t3 doit exiger le quadrant ambiguïté (levable / non levable / …)."""
    body = dep.T3_BODY_TEMPLATE.format(issue_n=4, repo="dino-game")
    low = body.lower()
    assert "ambigu" in low
    for kind in ("levable", "non levable"):
        assert kind in low, kind


def test_grill_body_imposes_verdict_on_prototyping(dep):
    """Le verdict prototypage est OBLIGATOIRE, pas optionnel."""
    body = dep.T3_BODY_TEMPLATE.format(issue_n=4, repo="dino-game")
    low = body.lower()
    assert "prototyp" in low
    assert "obligatoire" in low


def test_grill_body_demands_cost_of_not_clarifying(dep):
    """La décision se prend sur le COÛT de l'ambiguïté non levée, pas au feeling."""
    body = dep.T3_BODY_TEMPLATE.format(issue_n=4, repo="dino-game")
    low = body.lower()
    assert "coût" in low or "cout" in low
    assert "tunnel" in low or "tard" in low


def test_grill_body_names_the_artifact_type(dep):
    """« Prototyper » doit être concret : quel artefact, pour quelle décision."""
    body = dep.T3_BODY_TEMPLATE.format(issue_n=4, repo="dino-game")
    low = body.lower()
    for a in ("maquette", "planche", "capture"):
        assert a in low, a


def test_grill_body_does_not_systematize_human(dep):
    """L'humain n'est PAS convoqué par défaut : une tâche sans ambiguïté passe."""
    body = dep.T3_BODY_TEMPLATE.format(issue_n=4, repo="dino-game")
    low = body.lower()
    assert "pas d'ambigu" in low or "aucune ambigu" in low or "pas de prototyp" in low


def test_grill_body_defines_the_gate_variable(dep):
    """Le verdict doit s'écrire dans une variable lisible par t4/t5 (contrat)."""
    body = dep.T3_BODY_TEMPLATE.format(issue_n=4, repo="dino-game")
    assert "PROTOTYPE" in body          # marqueur machine-lisible
    assert "AMBIGU" in body
