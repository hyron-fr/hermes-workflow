"""Tests de pj_autonomy — graduation d'autonomie du pipeline (0 LLM).

Fonctions pures via importlib, fixtures tmp_path, sans réseau ni dépendance
externe (ni langgraph, ni hermes). Convention : exits 0/1/2.
"""
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PATH = str(REPO / "pipeline" / "pj_autonomy.py")


@pytest.fixture(scope="module")
def au():
    spec = importlib.util.spec_from_file_location("au", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def wf(*steps) -> dict:
    return {"name": "w", "steps": list(steps)}


def det(sid, command):
    return {"id": sid, "type": "deterministic", "command": command}


def ag(sid, side_effect=None):
    s = {"id": sid, "type": "agentic", "agent": {"role": "dev"}}
    if side_effect:
        s["side_effect"] = side_effect
    return s


def gate(sid, check="True"):
    return {"id": sid, "type": "gate", "check": check}


# ------------------------------------------------------------------ normalize

def test_normalize_levels_ok(au):
    for lv in ("off", "low", "medium", "high"):
        assert au.normalize_level(lv) == lv


def test_normalize_default_when_absent(au):
    assert au.normalize_level(None) == "high"
    assert au.normalize_level("") == "high"


def test_normalize_case_and_space(au):
    assert au.normalize_level("  LOW ") == "low"
    assert au.normalize_level("off ") == "off"  # le strip fait partie du contrat


def test_normalize_yaml_off_is_boolean_false(au):
    # Piège YAML 1.1 : PyYAML parsé `autonomy: off` -> False (booléen).
    assert au.normalize_level(False) == "off"
    with pytest.raises(ValueError):
        au.normalize_level(True)  # "on" n'est pas un niveau


def test_normalize_invalid_raises(au):
    for bad in ("OFF!", "very-high", "auto", 3):
        with pytest.raises(ValueError):
            au.normalize_level(bad)


# ------------------------------------------------------------------ résolution

def test_effective_level_default_high(au):
    assert au.effective_level(det("a", "echo ok"), "high") == "high"


def test_effective_level_inherited(au):
    assert au.effective_level(det("a", "echo ok"), "low") == "low"


def test_effective_level_step_override(au):
    assert au.effective_level({"id": "a", "type": "deterministic",
                               "command": "echo ok", "autonomy": "high"}, "low") == "high"
    assert au.effective_level({"id": "a", "type": "deterministic",
                               "command": "echo ok", "autonomy": "off"}, "high") == "off"


def test_effective_level_invalid_override_raises(au):
    with pytest.raises(ValueError):
        au.effective_level({"id": "a", "type": "deterministic",
                            "command": "x", "autonomy": "mega"}, "high")


def test_workflow_level(au):
    assert au.workflow_level(wf()) == "high"
    assert au.workflow_level({"orchestration": {"autonomy": "off"},
                              "steps": []}) == "off"
    with pytest.raises(ValueError):
        au.workflow_level({"orchestration": {"autonomy": "ultra"}, "steps": []})


# ------------------------------------------------------------------ irréversibilité

def test_no_effect_plain_command(au):
    assert au.irreversible_effects(det("a", "echo ok")) == []
    assert au.irreversible_effects(det("a", "python3 tools/lint.py")) == []


def test_git_push_detected(au):
    eff = au.irreversible_effects(det("a", "git push origin dev"))
    assert eff and "git push" in eff[0]


def test_git_merge_detected(au):
    assert au.irreversible_effects(det("a", "git merge dev"))


def test_rm_rf_detected(au):
    assert au.irreversible_effects(det("a", "rm -rf build/"))


def test_gh_pr_merge_detected(au):
    assert au.irreversible_effects(det("a", "gh pr merge 14 --squash"))


def test_gh_issue_comment_reversible(au):
    # Commenter une issue n'est PAS un effet irréversible du pipeline :
    # c'est de l'information (contrat de notification du moteur).
    assert au.irreversible_effects(det("a", "gh issue comment 14 --body ok")) == []


def test_actions_list_detected(au):
    step = {"id": "a", "type": "deterministic",
            "actions": ["echo ok", "git push origin dev"]}
    assert au.irreversible_effects(step)


def test_side_effect_declared(au):
    assert au.irreversible_effects(ag("a", side_effect="merge"))
    assert au.irreversible_effects(ag("a", side_effect="create_subtickets"))
    assert au.irreversible_effects(ag("a")) == []


def test_side_effect_list(au):
    assert au.irreversible_effects({"id": "a", "type": "agentic",
                                    "side_effect": ["notify", "push"]})


def test_gate_never_irreversible(au):
    # Un gate n'exécute pas de commande : jamais irréversible, même avec
    # du texte qui ressemblerait à un effet dans `check`.
    assert au.irreversible_effects(gate("g", check="all(x.get('ok') for x in r)")) == []


# ------------------------------------------------------------------ décision

def test_high_runs_everything(au):
    assert au.decision("high", ag("a")) == ("run", None)
    assert au.decision("high", det("a", "git push")) == ("run", None)


def test_off_escalates_non_gate(au):
    for st in (ag("a"), det("a", "echo ok")):
        verdict, reason = au.decision("off", st)
        assert verdict == "escalate"
        assert "autonomy=off" in reason


def test_off_gate_runs(au):
    assert au.decision("off", gate("g")) == ("run", None)


def test_low_escalates_agentic(au):
    verdict, reason = au.decision("low", ag("a"))
    assert verdict == "escalate" and "agentique" in reason


def test_low_runs_reversible_deterministic(au):
    assert au.decision("low", det("a", "python3 lint.py")) == ("run", None)


def test_low_escalates_irreversible_deterministic(au):
    verdict, reason = au.decision("low", det("a", "git push"))
    assert verdict == "escalate" and "git push" in reason


def test_medium_runs_reversible(au):
    assert au.decision("medium", ag("a")) == ("run", None)
    assert au.decision("medium", det("a", "echo ok")) == ("run", None)


def test_medium_escalates_irreversible(au):
    verdict, reason = au.decision("medium", det("a", "gh pr merge 14"))
    assert verdict == "escalate" and "irréversible" in reason
    verdict2, _ = au.decision("medium", ag("a", side_effect="merge"))
    assert verdict2 == "escalate"


def test_medium_gate_runs(au):
    assert au.decision("medium", gate("g")) == ("run", None)


# ------------------------------------------------------------------ audit

def test_audit_rows_all_steps(au):
    rows = au.audit(wf(ag("s1"), det("s2", "echo ok"), gate("g")))
    assert [r["id"] for r in rows] == ["s1", "s2", "g"]
    assert all(r["verdict"] == "run" for r in rows)  # défaut high
    assert all(r["level"] == "high" for r in rows)


def test_audit_with_workflow_level_and_override(au):
    wf = {"name": "w", "orchestration": {"autonomy": "medium"},
          "steps": [ag("s1"),
                    det("s2", "git push origin dev", ),
                    {"id": "s3", "type": "deterministic",
                     "command": "git push", "autonomy": "high"}]}
    rows = au.audit(wf)
    assert rows[0]["verdict"] == "run"
    assert rows[1]["verdict"] == "escalate"
    assert rows[1]["level"] == "medium"
    assert rows[2]["verdict"] == "run" and rows[2]["level"] == "high"


def test_escalate_comment_structured(au):
    c = au.escalate_comment({"id": "s1"}, "raison", "hermes-experiment", "t_x")
    assert c.startswith("[autonomy] ")
    assert "t_x" in c and "hermes-experiment" in c


# ------------------------------------------------------------------ CLI

def _write_wf(tmp_path: Path, wf_text: str) -> Path:
    p = tmp_path / "wf.yaml"
    p.write_text(wf_text, encoding="utf-8")
    return p


def test_cli_missing_file_exit2(au, tmp_path):
    import subprocess, sys
    r = subprocess.run([sys.executable, PATH, "--workflow", str(tmp_path / "absent.yaml")],
                       capture_output=True, text=True)
    assert r.returncode == 2


def test_cli_invalid_level_exit2(au, tmp_path):
    import subprocess, sys
    p = _write_wf(tmp_path, "name: w\norchestration:\n  autonomy: ultra\n"
                            "steps:\n  - {id: a, type: gate}\n")
    r = subprocess.run([sys.executable, PATH, "--workflow", str(p)],
                       capture_output=True, text=True)
    assert r.returncode == 2
    assert "invalide" in r.stderr


def test_cli_json_audit(au, tmp_path):
    import subprocess, sys
    p = _write_wf(tmp_path,
        "name: w\norchestration:\n  autonomy: medium\n"
        "steps:\n"
        "  - {id: dev, type: agentic, agent: {role: dev}}\n"
        "  - {id: push, type: deterministic, command: 'git push origin dev'}\n"
        "  - {id: g, type: gate}\n")
    r = subprocess.run([sys.executable, PATH, "--workflow", str(p), "--json"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    by_id = {row["id"]: row for row in data["rows"]}
    assert by_id["dev"]["verdict"] == "run"
    assert by_id["push"]["verdict"] == "escalate"
    assert by_id["g"]["verdict"] == "run"
    assert "git push" in by_id["push"]["irreversible"][0]
