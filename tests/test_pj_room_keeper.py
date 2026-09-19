"""Tests de pj_room_keeper — pj-master gère les rooms de bout en bout.

Cycle : ensure (création) → ask (animation) → report (transcript → comment) → disband (clôture).
Source de vérité du lien room↔ticket = le body de la carte (marqueur ROOM:), pas le moteur.
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import pytest

PATH = str(REPO / "bridge" / "pj_room_keeper.py")

T4_BODY = ("1er jet de spec + sous-tâches pour l'issue #8, à partir des handoffs t1/t2/t3.\n"
           "ROOM: pj-dino-game-issue-8\n")


@pytest.fixture(scope="module")
def kp():
    spec = importlib.util.spec_from_file_location("kp", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_room_marker_roundtrip(kp):
    assert kp.room_marker("pj-dino-game-issue-8") in kp.with_room_marker("body", "pj-dino-game-issue-8")
    assert kp.room_from_body(T4_BODY) == "pj-dino-game-issue-8"


def test_room_from_body_absent(kp):
    assert kp.room_from_body("pas de marqueur ici") is None
    assert kp.room_from_body("") is None


def test_room_from_body_marker_inline(kp):
    """Régression : le marqueur peut être noyé dans une ligne de texte.

    Un regex ancré ^...$ (MULTILINE) ratait ce cas — une carte réelle avait son
    corps sur une seule ligne et le keeper ne la voyait pas.
    """
    assert kp.room_from_body("TEST keeper — chemin ask. ROOM: pj-dino-game-issue-12") == "pj-dino-game-issue-12"
    assert kp.room_from_body("bla ROOM: pj-x-issue-3 suite du texte") == "pj-x-issue-3"
    # tolère le marqueur entre backticks (body markdown du déployeur)
    assert kp.room_from_body("room `pj-x-issue-7`\nROOM: pj-x-issue-7") == "pj-x-issue-7"


def test_with_room_marker_is_idempotent(kp):
    """Ré-écrire le marqueur ne doit pas le dupliquer (le deployer repasse)."""
    once = kp.with_room_marker("body", "pj-x-issue-1")
    twice = kp.with_room_marker(once, "pj-x-issue-1")
    assert once == twice
    assert once.count("ROOM:") == 1


def test_rooms_to_serve_picks_room_cards(kp):
    """Une carte portant le marqueur ROOM est une carte à servir ; les autres non."""
    cards = [
        {"id": "t4", "title": "t4 draft spec", "status": "running", "body": T4_BODY},
        {"id": "t5", "title": "t5 validate", "status": "todo", "body": "sans marqueur"},
    ]
    assert kp.rooms_to_serve(cards) == [("pj-dino-game-issue-8", "t4")]


def test_decide_ask_when_room_empty_and_card_active(kp):
    """Room vide + carte active (running) → il faut animer."""
    assert kp.decide(room_state="empty", card_status="running", reported=False) == "ask"
    assert kp.decide(room_state="empty", card_status="todo", reported=False) is None


def test_decide_report_when_discussion_done(kp):
    assert kp.decide(room_state="done", card_status="running", reported=False) == "report"
    assert kp.decide(room_state="done", card_status="running", reported=True) is None


def test_decide_disband_when_card_done_and_reported(kp):
    """Room clôturée seulement quand la carte est finie ET le transcript reporté."""
    assert kp.decide(room_state="done", card_status="done", reported=True) == "disband"
    assert kp.decide(room_state="done", card_status="done", reported=False) == "report"


def test_decide_never_disbands_an_unreported_room(kp):
    """Une délibération FINIE non reportée doit être reportée avant dissolution.

    `pending` signifie « délibération en cours » : le keeper n'y touche jamais
    (ni report ni disband) — la reporter à mi-parcours tronquerait le débat.
    """
    # délibération en cours : jamais touchée
    assert kp.decide(room_state="pending", card_status="done", reported=False) is None
    assert kp.decide(room_state="pending", card_status="done", reported=True) is None
    # délibération finie : report obligatoire d'abord, dissolution ensuite
    assert kp.decide(room_state="done", card_status="done", reported=False) == "report"
    assert kp.decide(room_state="done", card_status="done", reported=True) == "disband"
    # finie mais carte non terminée : reporté, on attend la fin de la carte
    assert kp.decide(room_state="done", card_status="running", reported=True) is None


def test_disbanded_room_is_not_replayable(kp):
    """Un room_id dissous est retiré définitivement : le keeper doit l'ignorer, pas boucler.

    Vérifié dans hosted_rooms.create_room : `_is_retired` -> RoomConflictError
    « room_id belongs to a disbanded room ». On ne recrée donc jamais la même room.
    """
    assert kp.is_disbanded_error(
        "pj_room ensure: RoomConflictError: room_id belongs to a disbanded room")
    assert not kp.is_disbanded_error("pj_room ensure: connexion refusée")


def test_empty_room_on_finished_card_is_disbanded(kp):
    """Une room jamais animée sur une carte finie doit libérer son slot.

    Régression : les rooms créées par migration sur des tickets déjà clos
    restaient actives à vie et consommaient un slot (MAX_ACTIVE_ROOMS).
    """
    assert kp.decide(room_state="empty", card_status="done", reported=False) == "disband"
    assert kp.decide(room_state="empty", card_status="archived", reported=False) == "disband"
    assert kp.is_reported([{"body": f"{kp.REPORT_MARKER} bla"}])
    assert not kp.is_reported([{"body": "un commentaire normal"}])
    assert not kp.is_reported([])

# ------------------------------------------------- anti-livelock (garde-fou) ---

def test_decide_unblocks_a_livelocked_room(kp):
    """Une room EN LIVELOCK ne doit pas être laissée pendante : on la coupe."""
    assert kp.decide(room_state="livelock", card_status="running", reported=False) == "unblock"


def test_decide_unblock_wins_over_other_states(kp):
    """Le livelock a priorité : une room en cours ne doit pas être ignorée."""
    assert kp.decide(room_state="livelock", card_status="ready", reported=False) == "unblock"
    assert kp.decide(room_state="livelock", card_status="done", reported=True) == "unblock"


def test_decide_livelock_then_reports(kp):
    """Après le stop la room redevient `done` -> on reporte (le cycle reprend)."""
    assert kp.decide(room_state="done", card_status="running", reported=False) == "report"

def test_unblock_does_not_repeat_after_stop(kp):
    """Un stop répété serait un harcèlement : après l'arrêt la room n'est plus en livelock.

    Le cycle réel : livelock -> unblock (stop) -> la room devient `done`
    (`room.stop_requested` retire le message utilisateur des discussions pendantes)
    -> report -> disband. Le garde-fou ne doit donc jamais se déclencher deux fois.
    """
    # 1) livelock -> on coupe
    assert kp.decide(room_state="livelock", card_status="running", reported=False) == "unblock"
    # 2) après le stop, l'état remonte par pj_room est `done` -> report, pas unblock
    assert kp.decide(room_state="done", card_status="running", reported=False) == "report"
