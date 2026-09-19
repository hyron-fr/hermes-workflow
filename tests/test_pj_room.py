"""Tests de pj_room.py — gestion des rooms Bot Mode du pipeline pj.

Une room par ticket : room_id déterministe `pj-<repo>-issue-<n>`, créée par le
déployeur, dissoute à la clôture. La room est un canal de délibération ; le board
reste la source de vérité.

Note : les tests n'ouvrent jamais la vraie base des rooms — les fonctions testées
sont pures (construction du room_id, du roster).
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest

PATH = str(REPO / "bridge" / "pj_room.py")


@pytest.fixture(scope="module")
def pr():
    spec = importlib.util.spec_from_file_location("pr", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_room_id_is_deterministic(pr):
    assert pr.room_id_for("dino-game", 8) == "pj-dino-game-issue-8"
    assert pr.room_id_for("hermes-experiment", 12) == "pj-hermes-experiment-issue-12"


def test_room_id_sanitizes_repo(pr):
    assert pr.room_id_for("my.repo_x", 3) == "pj-my-repo-x-issue-3"


def test_room_name_is_readable(pr):
    assert pr.room_name_for("dino-game", 8) == "pj dino-game #8"


def test_roster_default_members(pr):
    members = pr.build_roster()
    profiles = [m["profile"] for m in members]
    assert profiles == ["pj-master", "pj-dev", "pj-doc", "pj-test"]


def test_roster_member_shape(pr):
    """Le service attend exactement {member_id, profile, handle} (pas de champ remote)."""
    for m in pr.build_roster():
        assert set(m) == {"member_id", "profile", "handle"}
        assert m["handle"] == m["profile"]
        assert m["member_id"]


def test_roster_handles_unique(pr):
    handles = [m["handle"] for m in pr.build_roster()]
    assert len(handles) == len(set(handles))


def test_roster_respects_member_bounds(pr):
    """validate_roster impose 2..6 membres."""
    n = len(pr.build_roster())
    assert 2 <= n <= 6, f"{n} membres hors des bornes 2..6"


def test_parse_action_and_target(pr):
    assert pr.parse_args(["--repo", "dino-game", "--issue", "8", "--action", "ensure"]) == {
        "repo": "dino-game", "issue": 8, "action": "ensure", "text": "", "members": []}
    assert pr.parse_args(["--repo", "dino-game", "--issue", "8", "--action", "disband"]) == {
        "repo": "dino-game", "issue": 8, "action": "disband", "text": "", "members": []}


def test_ask_requires_text(pr):
    """`ask` sans --text est refusé : un message vide ne déclenche aucune délibération."""
    with pytest.raises(ValueError):
        pr.parse_args(["--repo", "r", "--issue", "1", "--action", "ask"])
    ok = pr.parse_args(["--repo", "r", "--issue", "1", "--action", "ask", "--text", "cadre ?"])
    assert ok["text"] == "cadre ?"


def test_full_message_user_payload_is_exact(pr):
    """validate_user_payload exige EXACTEMENT {text, thread_id} — aucun champ en trop."""
    import sys
    sys.path.insert(0, "${HOME}/.hermes/hermes-agent")
    from gateway import hosted_room_discussion as disc
    import inspect
    src = inspect.getsource(disc.validate_user_payload)
    assert "_USER_PAYLOAD_FIELDS" in src


def test_action_is_validated(pr):
    with pytest.raises(ValueError):
        pr.parse_args(["--repo", "r", "--issue", "1", "--action", "nuke"])

# ---------------------------------------------------------------- livelock ---

def _ev(kind, seq, **payload):
    return {"kind": kind, "seq": seq, "payload": payload, "actor": {"kind": "member", "id": "pj-test"}}


def test_detect_livelock_healthy_log(pr):
    """Une délibération saine ne déclenche rien."""
    ev = [_ev("message.user", 1, text="cadre", thread_id="t1"),
          _ev("message.member", 2, text="voici", thread_id="t1"),
          _ev("turn.settled", 3, passed=False)]
    r = pr.detect_livelock(ev)
    assert r["livelock"] is False and r["trailing_defers"] == 0


def test_detect_livelock_one_defer_is_not_enough(pr):
    """UN defer peut être un incident transitoire : on ne coupe pas."""
    ev = [_ev("message.user", 1, text="cadre", thread_id="t1"),
          _ev("message.member", 2, text="voici", thread_id="t1"),
          _ev("turn.settled", 3, passed=False),
          _ev("turn.deferred", 4, reason="member_unavailable", member_id="pj-test")]
    r = pr.detect_livelock(ev)
    assert r["livelock"] is False and r["trailing_defers"] == 1


def test_detect_livelock_two_trailing_defers(pr):
    """Le livelock OBSERVÉ : deux defer d'affilée, aucun message de membre entre les deux."""
    ev = [_ev("message.member", 1, text="voici", thread_id="t1"),
          _ev("turn.settled", 2, passed=False),
          _ev("turn.deferred", 3, reason="member_unavailable", member_id="pj-test", round_index=2),
          _ev("turn.deferred", 4, reason="member_unavailable", member_id="pj-dev", round_index=2)]
    r = pr.detect_livelock(ev)
    assert r["livelock"] is True
    assert r["trailing_defers"] == 2
    assert r["members"] == ["pj-test", "pj-dev"]


def test_detect_livelock_progress_resets_counter(pr):
    """Un message de membre ENTRE deux defer prouve que ça progresse → pas de livelock."""
    ev = [_ev("turn.deferred", 1, reason="member_unavailable", member_id="pj-test"),
          _ev("message.member", 2, text="réponse", thread_id="t1"),
          _ev("turn.deferred", 3, reason="member_unavailable", member_id="pj-dev")]
    r = pr.detect_livelock(ev)
    assert r["livelock"] is False and r["trailing_defers"] == 1


def test_detect_livelock_already_stopped_is_ignored(pr):
    """Après un stop, on ne redéclenche pas : la boucle est déjà coupée."""
    ev = [_ev("turn.deferred", 1, reason="member_unavailable", member_id="pj-test"),
          _ev("turn.deferred", 2, reason="member_unavailable", member_id="pj-dev"),
          _ev("room.stop_requested", 3, cancel_id="c1")]
    r = pr.detect_livelock(ev)
    assert r["livelock"] is False


def test_detect_livelock_threshold_is_configurable(pr):
    ev = [_ev("turn.deferred", 1, reason="member_unavailable", member_id="pj-test"),
          _ev("turn.deferred", 2, reason="member_unavailable", member_id="pj-dev")]
    assert pr.detect_livelock(ev, threshold=3)["livelock"] is False
    assert pr.detect_livelock(ev, threshold=2)["livelock"] is True


def test_detect_livelock_ignores_other_defer_reasons(pr):
    """Seul `member_unavailable` est la signature du stall ; un autre motif ne coupe pas."""
    ev = [_ev("turn.deferred", 1, reason="autre_chose", member_id="pj-test"),
          _ev("turn.deferred", 2, reason="autre_chose", member_id="pj-dev")]
    assert pr.detect_livelock(ev)["livelock"] is False
