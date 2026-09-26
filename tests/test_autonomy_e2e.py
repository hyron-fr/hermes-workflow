"""E2E LangGraph de l'escalade d'autonomie (dry-run, 0 LLM, 0 kanban).

Preuve de bout en bout : un workflow `autonomy: off` compilé dans LangGraph
ESCALE la première étape (le graphe s'arrête sur END, l'étape n'est jamais
exécutée — le LLM ne démarre pas), et `autonomy: high` laisse le déterministe
réversible s'exécuter sans escalade. Le `gate` passe toujours.
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


def ticket() -> dict:
    return {"id": "t_e2e", "title": "e2e", "body": "",
            "status": "ready", "issue_number": None}


def _wf(autonomy, irreversible=False):
    cmd = "git push origin dev" if irreversible else "echo ok"
    return {
        "name": "e2e",
        "orchestration": {"autonomy": autonomy},
        "steps": [
            {"id": "dev", "type": "agentic", "agent": {"role": "dev"},
             "prompt": "dev"},
            {"id": "det", "type": "deterministic", "command": cmd},
            {"id": "g", "type": "gate", "check": "True"},
        ],
    }


def _invoke(eng, wf, dry_run=True):
    g = eng.build_graph(wf, REPO / "workflows")
    return g.invoke({
        "ticket": ticket(), "steps": {}, "board": "b",
        "dry_run": dry_run, "base_dir": str(REPO),
        "autonomy_level": eng.pj_autonomy.workflow_level(wf),
    })


def test_off_escalates_first_step_and_stops(eng):
    st = _invoke(eng, _wf("off"))
    assert st.get("escalated") == "dev"
    # l'étape escaladée est marquée, les suivantes ne se sont pas exécutées
    assert st["steps"]["dev"]["escalated"] is True
    assert "det" not in st.get("steps", {})
    assert "g" not in st.get("steps", {})


def test_off_irreversible_not_run_either(eng):
    # Même si on force la première étape à passer, l'irréversible escale.
    st = _invoke(eng, _wf("off", irreversible=True))
    assert st.get("escalated") == "dev"
    assert st["steps"]["dev"]["escalated"] is True


def test_medium_runs_reversible_and_escalates_irreversible(eng):
    # medium : l'agentique réversible passe (dry-run), le déterministe
    # irréversible escale -> le graphe s'arrête sur 'det'.
    st = _invoke(eng, _wf("medium", irreversible=True))
    assert st.get("escalated") == "det"
    assert st["steps"]["dev"]["ok"] is True          # l'agentique a tourné (dry)
    assert st["steps"]["det"]["escalated"] is True
    assert "g" not in st.get("steps", {})


def test_medium_reversible_runs_to_gate(eng):
    # medium, déterministe réversible : on passe dev + det et le gate tourne.
    st = _invoke(eng, _wf("medium", irreversible=False))
    assert st.get("escalated", "") == ""
    assert st["steps"]["dev"]["ok"] is True
    assert st["steps"]["det"]["ok"] is True
    assert st["steps"]["g"]["passed"] is True


def test_high_runs_everything(eng):
    st = _invoke(eng, _wf("high", irreversible=True))
    assert st.get("escalated", "") == ""
    for sid in ("dev", "det", "g"):
        assert sid in st["steps"]
    assert st["steps"]["g"]["passed"] is True


def test_step_override_beats_workflow(eng):
    # workflow off, mais l'étape dev porte autonomy: high -> dev tourne ;
    # det (niveau workflow off) escale ensuite -> l'override n'a d'effet
    # QUE sur l'étape qui le porte.
    wf = _wf("off")
    wf["steps"][0]["autonomy"] = "high"
    st = _invoke(eng, wf)
    assert st["steps"]["dev"]["ok"] is True
    assert st.get("escalated") == "det"
    assert st["steps"]["det"]["escalated"] is True


def test_all_high_no_escalation(eng):
    # Le même workflow avec un override high sur chaque étape : rien
    # n'escale, même le déterministe irréversible.
    wf = _wf("off", irreversible=True)
    for s in wf["steps"]:
        s["autonomy"] = "high"
    st = _invoke(eng, wf)
    assert st.get("escalated", "") == ""
    for sid in ("dev", "det", "g"):
        assert sid in st["steps"]
