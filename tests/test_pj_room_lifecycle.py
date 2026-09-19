"""Tests de pj_room.py — volet cycle de vie (analyse d'état, réap).

Le cycle de vie complet est porté par pj-master :
  ensure (création) -> ask (animation) -> statut (fin ?) -> transcript -> disband.
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest

PATH = str(REPO / "pipeline" / "pj_room.py")


@pytest.fixture(scope="module")
def pr():
    spec = importlib.util.spec_from_file_location("pr", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parse_room_id_roundtrip(pr):
    """L'identité d'un ticket doit être récupérable depuis le room_id (pas de table de mapping)."""
    assert pr.parse_room_id("pj-dino-game-issue-8") == ("dino-game", 8)
    assert pr.parse_room_id("pj-hermes-experiment-issue-12") == ("hermes-experiment", 12)


def test_parse_room_id_rejects_foreign_or_malformed(pr):
    """Une room qui n'est pas au schéma du pipeline n'est pas réappable."""
    for bad in ("pj-dino-game", "other-room-3", "pj-x-issue-", "pj-x-task-1", ""):
        assert pr.parse_room_id(bad) is None


def test_room_id_parse_roundtrip_with_room_id_for(pr):
    """room_id_for puis parse_room_id redonne l'entrée — c'est ce qui rend le réap sûr."""
    for repo, n in (("dino-game", 8), ("hermes-experiment", 120), ("a-b_c", 3)):
        rid = pr.room_id_for(repo, n)
        got = pr.parse_room_id(rid)
        assert got is not None, rid
        assert got[1] == n


def test_ask_text_names_the_issue_and_members(pr):
    """Le message d'animation doit citer le ticket et les profils à faire réagir."""
    txt = pr.build_ask_text("dino-game", 8, ["pj-dev", "pj-doc"])
    assert "#8" in txt or "8" in txt
    assert "@pj-dev" in txt and "@pj-doc" in txt
    assert "dino-game" in txt


def test_ask_text_without_members_mentions_nobody(pr):
    """Sans mention, le moteur interroge TOUS les membres (round 1) — pas de @ inventé."""
    txt = pr.build_ask_text("dino-game", 8, [])
    assert "@pj-" not in txt
