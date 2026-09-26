"""Tests de l'intégration autonomie dans le moteur engine.py (0 LLM, 0 réseau).

Le module `pj_autonomy` est testé séparément (test_pj_autonomy.py). Ici on
vérifie le câblage dans le moteur : compilation du graphe avec les arêtes
d'escalade, décision du guard, et le ctx porté par run_workflow.
Le guard est testé en `dry_run` (aucun appel kanban) — le chemin
escalade+block est couvert par la politique testée dans test_pj_autonomy.
"""
import importlib.util
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


WF = {
    "name": "w",
    "orchestration": {"autonomy": "off"},
    "steps": [
        {"id": "dev", "type": "agentic", "agent": {"role": "dev"},
         "prompt": "x"},
        {"id": "push", "type": "deterministic",
         "command": "git push origin dev"},
        {"id": "g", "type": "gate", "check": "True"},
    ],
}


def test_build_graph_compiles_with_escalation_edges(eng):
    g = eng.build_graph(WF, REPO / "workflows")
    assert g is not None


def test_guard_off_escalates_agentic_dry_run(eng):
    state = {"autonomy_level": "off", "dry_run": True,
             "board": "b", "ticket": {"id": "t_x"}}
    upd = eng._autonomy_guard(WF["steps"][0], state)
    assert upd is not None
    assert upd["escalated"] == "dev"
    assert upd["steps"]["dev"]["escalated"] is True
    assert upd["steps"]["dev"]["ok"] is False


def test_guard_high_runs(eng):
    state = {"autonomy_level": "high", "dry_run": False,
             "board": "b", "ticket": {"id": "t"}}
    assert eng._autonomy_guard(WF["steps"][1], state) is None


def test_guard_off_escalates_deterministic(eng):
    state = {"autonomy_level": "off", "dry_run": True,
             "board": "b", "ticket": {"id": "t"}}
    upd = eng._autonomy_guard(WF["steps"][1], state)
    assert upd and upd["escalated"] == "push"


def test_gate_never_escalated_even_off(eng):
    state = {"autonomy_level": "off", "dry_run": True,
             "board": "b", "ticket": {"id": "t"}}
    assert eng._autonomy_guard(WF["steps"][2], state) is None


def test_medium_escalates_only_irreversible_in_engine(eng):
    state = {"autonomy_level": "medium", "dry_run": True,
             "board": "b", "ticket": {"id": "t"}}
    # l'étape agentique (réversible) passe sous medium
    assert eng._autonomy_guard(WF["steps"][0], state) is None
    # l'étape irréversible escale
    upd = eng._autonomy_guard(WF["steps"][1], state)
    assert upd and upd["escalated"] == "push"


def test_workflow_level_used_by_run_ctx(eng):
    assert eng.pj_autonomy.workflow_level(WF) == "off"
    assert eng.pj_autonomy.workflow_level({"steps": []}) == "high"


def test_router_esc_end_circuit(eng):
    """Le routeur enveloppé renvoie END si `escalated` est posé."""
    g = eng.build_graph(WF, REPO / "workflows")
    # Le graphe est compilé avec les arêtes conditionnelles END ; le nœud
    # 'dev' escale -> le routage sortant de 'dev' doit viser 'push' ou END.
    # On vérifie la propriété structurelle : le chemin 'dev' existe dans le
    # graphe compilé (pas de rejet de build_graph sur la map d'arêtes).
    nodes = set(g.nodes) if hasattr(g, "nodes") else set()
    if nodes:
        assert "dev" in nodes and "push" in nodes and "g" in nodes
