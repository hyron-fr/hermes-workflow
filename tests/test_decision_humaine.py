"""RED — décision humaine sur carte bloquée (issue #5).

Contrat PROVISOIRE, publié en room (blackboard `contrat-5`) et à confirmer par
@pj-dev / @pj-master avant que le code n'existe. Trois points de nommage sont
regroupés en constantes en tête de fichier : une ligne à changer suffit si
l'arbitrage retient d'autres noms.

Ce que ces tests verrouillent (fonctions PURES, aucune horloge, aucun RNG) :

  A. `coverage_verdict` + 3e branche « parent en vol » : une issue dont le PARENT
     est en vol est bloquée, même quand son corps ne cite le parent que par URL
     (cas réel : le corps de #5 cite `.../issues/4`, donc `issue_refs()` rend ∅).
  B. Le module VERSIONNÉ de décision `/ok` : jeton en tête, casse indifférente,
     anti-rejeu, `/ok` hors blocage → commentaire sans déblocage, ticket CLOSED →
     silence. Effet décrit en sortie, zéro appel gh/réseau/fichier : les effets
     sont portés par l'appelant.
"""
import importlib.util
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Quelle copie ce run valide-t-il ? Mesuré : `tests/test_bridge_coverage_gate.py`
# existe en deux exemplaires homonymes (hermes-workflow et hermes-experiment) qui
# ne diffèrent QUE par cette ligne — l'un importe `REPO/bridge`, l'autre
# `/home/elix/hermes-experiment/bridge` (la copie que les wrappers EXÉCUTENT).
# Un même fichier de test peut donc être vert sans que le pipeline soit réparé.
# La variable PJ_BRIDGE_COPY permet de rejouer CE fichier contre la copie runtime :
# la convergence #5 doit produire les deux runs, sinon « tests verts » n'est pas
# « pont réparé ».
BRIDGE = Path(os.environ["PJ_BRIDGE_COPY"]) if os.environ.get("PJ_BRIDGE_COPY") \
    else REPO / "bridge" / "gh_kanban_bridge.py"

# --------------------------------------------------------------------------
# NOMS À CONFIRMER (une ligne chacun, cf. contrat-5)
# --------------------------------------------------------------------------
# 1. chemin du module de décision versionné (core pur, sans adapter)
DECISION_MODULE = REPO / "pipeline" / "pj_decision.py"
# 2. clé de ctx portant {numéro d'issue: numéro du parent} (None si pas de parent)
PARENTS_KEY = "parents"
# 3. jetons acceptés en tête de commentaire. `/ok` = contrat annoncé par pj-dev ;
#    `/unblock` = jeton écrit dans la spec (body de l'issue #5) — les deux sont
#    testés : si le cadrage en retient un seul, retirer l'autre du paramétrage.
TOKENS = ("/ok", "/unblock")

BOARD = "pj-hermes-workflow"


def _load(path: Path, name: str):
    if not path.exists():
        pytest.fail(
            f"module versionné absent : {path} — le RED ne peut pas porter sur du "
            f"code non versionné (mesuré : git ls-files | grep -ci escalat -> 0). "
            f"Si l'arbitrage retient un autre chemin, changer DECISION_MODULE."
        )
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def br():
    os.environ.setdefault("GH_REPO", "hyron-fr/hermes-workflow")
    os.environ.setdefault("KANBAN_BOARD", BOARD)
    return _load(BRIDGE, "br_issue5")


@pytest.fixture(scope="module")
def dm():
    os.environ.setdefault("KANBAN_BOARD", BOARD)
    return _load(DECISION_MODULE, "pj_decision_issue5")


# ==========================================================================
# A. coverage_verdict — 3e branche : le PARENT en vol bloque l'issue
# ==========================================================================

ISSUE_5 = {
    "number": 5,
    "title": "Interface de décision humaine pour les cartes bloquées "
             "(Discord + GitHub uniquement)",
    "body": "Hors-scope : déjà traité par "
            "https://github.com/hyron-fr/hermes-workflow/issues/4",
}


def _ctx(**kw):
    base = {"open_pr_issues": set(), "graph_issues": set(), "titles": {}}
    base[PARENTS_KEY] = kw.pop("parents", {})
    base.update(kw)
    return base


def test_parent_en_vol_bloque_meme_sans_reference_texte(br):
    """NOMINAL — cas réel #5 : le corps ne cite le parent que par URL.

    Mesuré : `issue_refs(body_#5)` -> set() (l'URL est retirée avant extraction),
    donc la 3e branche est la SEULE qui voit le recouvrement.
    """
    assert br.issue_refs(ISSUE_5["body"]) == set()          # la prémisse du cas
    v = br.coverage_verdict(ISSUE_5, _ctx(parents={5: 4}, graph_issues={4}))
    assert v["blocked"] is True
    assert v["overlaps"] == [4]
    assert "4" in v["reason"]


def test_parent_hors_vol_ne_bloque_pas(br):
    """LIMITE — la 3e branche ne doit pas devenir « tout parent bloque ».

    Un parent ni en PR ni en graphe n'est pas du travail en vol : l'issue passe.
    """
    v = br.coverage_verdict(ISSUE_5, _ctx(parents={5: 4}))
    assert v["blocked"] is False
    assert v["overlaps"] == []


def test_ctx_sans_cle_parents_reste_compatible(br):
    """LIMITE — rétrocompatibilité : un ctx sans la clé ne lève pas.

    Le pont construit son ctx en une passe ; un appelant ancien doit continuer
    à fonctionner (dégradation silencieuse, pas de crash du pull).
    """
    ctx = {"open_pr_issues": set(), "graph_issues": set(), "titles": {}}
    v = br.coverage_verdict(ISSUE_5, ctx)
    assert v["blocked"] is False


def test_parent_absent_ne_bloque_pas(br):
    """ERREUR — parent explicite à None (issue racine) : aucune 3e branche."""
    v = br.coverage_verdict(ISSUE_5, _ctx(parents={5: None}, graph_issues={9}))
    assert v["blocked"] is False


# ==========================================================================
# B. module versionné de décision `/ok` — core pur, sortie = décision
# ==========================================================================

def _blocked_ctx(**kw):
    ctx = {
        "issue": {"number": 5, "state": "OPEN"},
        "cards": [{"task_id": "t_aaa", "board": BOARD, "status": "blocked",
                   "issue": 5}],
        "seen_comment_ids": set(),
    }
    ctx.update(kw)
    return ctx


def _comment(body, cid=900):
    return {"id": cid, "body": body}


@pytest.mark.parametrize("token", TOKENS)
def test_ok_nominal_debloque_la_carte_bloquee(dm, token):
    """NOMINAL — jeton en tête sur une carte bloquée -> unblock de CETTE carte."""
    d = dm.decision_from_comment(_blocked_ctx(), _comment(token))
    assert d["effect"] == "unblock"
    assert d["task_id"] == "t_aaa"
    assert d["board"] == BOARD


@pytest.mark.parametrize("token", ("/OK", "/Ok", "/oK"))
def test_jeton_casse_indifferente(dm, token):
    """LIMITE — « /ok » et « /OK » sont la même décision."""
    d = dm.decision_from_comment(_blocked_ctx(), _comment(token))
    assert d["effect"] == "unblock"


def test_jeton_en_milieu_de_phrase_ignore(dm):
    """LIMITE — « en tête » est une règle : un jeton cité ne décide rien.

    Sinon une question (« est-ce que /ok est le bon jeton ? ») débloquerait
    une carte : la décision doit être un acte, pas une mention.
    """
    d = dm.decision_from_comment(_blocked_ctx(),
                                 _comment("peut-être /ok mais je ne sais pas"))
    assert d["effect"] == "ignore"


def test_deux_cartes_bloquees_sans_task_id_ne_debloque_rien(dm):
    """LIMITE — ambiguïté : deux cartes bloquées, jeton nu.

    Aucune résolution par nom de fil (Défaut B) : on ne devine pas, on demande
    le task_id en commentaire et on ne débloque AUCUNE carte.
    """
    ctx = _blocked_ctx(cards=[
        {"task_id": "t_aaa", "board": BOARD, "status": "blocked", "issue": 5},
        {"task_id": "t_bbb", "board": BOARD, "status": "blocked", "issue": 5},
    ])
    d = dm.decision_from_comment(ctx, _comment("/ok"))
    assert d["effect"] != "unblock"
    assert d["task_id"] is None


def test_task_id_explicite_cible_une_seule_carte(dm):
    """LIMITE (scénario 2 de la spec) — seule la carte nommée est débloquée."""
    ctx = _blocked_ctx(cards=[
        {"task_id": "t_aaa", "board": BOARD, "status": "blocked", "issue": 5},
        {"task_id": "t_bbb", "board": BOARD, "status": "blocked", "issue": 5},
    ])
    d = dm.decision_from_comment(ctx, _comment("/ok t_bbb"))
    assert d["effect"] == "unblock"
    assert d["task_id"] == "t_bbb"


def test_commentaire_deja_traite_non_rejoue(dm):
    """ERREUR — anti-rejeu : le même commentaire ne débloque pas deux fois."""
    ctx = _blocked_ctx(seen_comment_ids={900})
    d = dm.decision_from_comment(ctx, _comment("/ok", cid=900))
    assert d["effect"] == "ignore"
    assert d["acted"] is False


def test_ok_hors_blocage_commentaire_sans_unblock(dm):
    """ERREUR (scénario 3) — jeton valide, aucune carte bloquée.

    La décision est écrite (trace humaine) mais rien n'est débloqué, et
    l'humain est informé — jamais d'erreur silencieuse.
    """
    ctx = _blocked_ctx(cards=[{"task_id": "t_aaa", "board": BOARD,
                               "status": "running", "issue": 5}])
    d = dm.decision_from_comment(ctx, _comment("/ok"))
    assert d["effect"] == "comment"
    assert d["task_id"] is None
    assert d["note"]


def test_issue_closed_ignore(dm):
    """ERREUR (scénario 4) — ticket CLOSED : aucune décision, aucun message."""
    ctx = _blocked_ctx(issue={"number": 5, "state": "CLOSED"})
    d = dm.decision_from_comment(ctx, _comment("/ok"))
    assert d["effect"] == "ignore"


def test_commentaire_vide_ou_non_jeton_ignore(dm):
    """ERREUR — corps vide / None : jamais de crash, jamais d'effet."""
    for body in ("", "   ", "\n", "juste une remarque"):
        d = dm.decision_from_comment(_blocked_ctx(), _comment(body))
        assert d["effect"] == "ignore"


def test_le_core_de_decision_reste_pur(dm, monkeypatch):
    """Garde-fou hexagonal : le core ne porte AUCUN effet.

    Un import de subprocess/réseau dans le module de décision rendrait le RED
    infalsifiable (il faudrait un gh vivant pour le faire passer).
    """
    import subprocess

    for name in ("subprocess", "requests", "urllib", "socket", "sqlite3"):
        assert not hasattr(dm, name), f"{name} ne doit pas être importé dans le core"

    def _boom(*a, **k):
        raise AssertionError("le core pur ne doit pas appeler subprocess")

    monkeypatch.setattr(subprocess, "run", _boom)
    d = dm.decision_from_comment(_blocked_ctx(), _comment("/ok"))
    assert d["effect"] == "unblock"
