"""Tests du contrat de résultat par run (pj_run_contract).

Le contrat distingue deux réalités que le dispatcher confond :
  A. travail FAIT, seul l'acte terminal manque  -> un retry complète
  B. worker JAMAIS démarré (infra)              -> un retry est inutile
"""
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PATH = str(REPO / "pipeline" / "pj_run_contract.py")


@pytest.fixture(scope="module")
def rc():
    spec = importlib.util.spec_from_file_location("rc", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------- logs worker réels

LOG_NEVER_STARTED = """
❌ Non-retryable client error (HTTP 400). Aborting.
   🔌 Provider: custom  Model: deepseek-v4-flash
   🌐 Endpoint: http://10.0.0.240/v1
 HTTP 400: /chat/completions: Invalid model name passed in
 model=deepseek-v4-flash. Call /v1/models to view available models.

Resume this session with:
  hermes --resume 20260910_154620_ffa6dc
Session:        20260910_154620_ffa6dc
Duration:       4s
Messages:       1 (1 user, 0 tool calls)
"""

LOG_WORKED = """
[tool] read_file(path="a.py")
[tool] write_file(path="a.py")
Session:        20260910_999999_abcdef
Duration:       120s
Messages:       14 (2 user, 9 tool calls)
"""

LOG_RATE_LIMITED = """
Error: rate limit exceeded (429)
Messages:       1 (1 user, 0 tool calls)
"""


# ------------------------------------------------------- parse du log

def test_parse_log_never_started(rc):
    ev = rc.parse_worker_log(LOG_NEVER_STARTED)
    assert ev["messages"] == 1
    assert ev["tool_calls"] == 0
    assert ev["provider_error"] == "non-retryable client error"
    assert ev["session_id"] == "20260910_154620_ffa6dc"


def test_parse_log_worked(rc):
    ev = rc.parse_worker_log(LOG_WORKED)
    assert ev["tool_calls"] == 9
    assert ev["messages"] == 14
    assert ev["provider_error"] is None


def test_parse_log_empty(rc):
    ev = rc.parse_worker_log("")
    assert ev["tool_calls"] is None and ev["messages"] is None


def test_parse_log_rate_limit(rc):
    assert rc.parse_worker_log(LOG_RATE_LIMITED)["provider_error"] == "rate limit"


# ------------------------------------------------------- détection violation

def test_violation_by_marker(rc):
    run = {"outcome": "crashed", "metadata": {"protocol_violation": True}}
    assert rc.run_violated(run) is True


def test_violation_by_error_text_legacy(rc):
    """Runs antérieurs au marqueur : repli sur le texte."""
    run = {"outcome": "crashed", "metadata": {},
           "error": "worker exited cleanly (rc=0) without calling "
                    "kanban_complete or kanban_block — protocol violation"}
    assert rc.run_violated(run) is True


def test_no_violation_for_rate_limited(rc):
    run = {"outcome": "rate_limited", "metadata": {"pid": 1}}
    assert rc.run_violated(run) is False


def test_satisfied_requires_metadata(rc):
    assert rc.run_satisfied({"outcome": "completed", "metadata": {"pr": {}}}) is True
    assert rc.run_satisfied({"outcome": "completed", "metadata": {}}) is False
    assert rc.run_satisfied({"outcome": "crashed", "metadata": {"x": 1}}) is False


# ------------------------------------------------------- verdicts

def test_verdict_never_started_infra(rc):
    """Le cas réel t_94f83933 : HTTP 400, 0 tool call."""
    run = {"id": 46, "outcome": "crashed",
           "metadata": {"protocol_violation": True, "exit_code": 0}}
    v = rc.classify_run(run, LOG_NEVER_STARTED, None)
    assert v["verdict"] == rc.NEVER_STARTED
    assert "0 appel" in v["reason"]
    assert v["evidence"]["provider_error"] == "non-retryable client error"


def test_verdict_rate_limit_is_infra(rc):
    run = {"id": 37, "outcome": "crashed",
           "metadata": {"protocol_violation": True}}
    v = rc.classify_run(run, LOG_RATE_LIMITED, "quota saturé")
    assert v["verdict"] == rc.NEVER_STARTED


def test_verdict_work_done(rc):
    """Le worker a travaillé (9 tool calls) puis oublié le paperwork."""
    run = {"id": 50, "outcome": "crashed",
           "metadata": {"protocol_violation": True}}
    v = rc.classify_run(run, LOG_WORKED, "commit 50f881f, implémentation en place")
    assert v["verdict"] == rc.WORK_DONE


def test_verdict_unclear_without_evidence(rc):
    run = {"id": 1, "outcome": "crashed",
           "metadata": {"protocol_violation": True}}
    assert rc.classify_run(run, "", "")["verdict"] == rc.UNCLEAR


def test_verdict_satisfied_terminal_run(rc):
    run = {"id": 60, "outcome": "completed", "metadata": {"pr": {"number": 9}}}
    assert rc.classify_run(run, "")["verdict"] == rc.SATISFIED


def test_non_violation_run_is_satisfied(rc):
    assert rc.classify_run({"id": 61, "outcome": "timed_out",
                            "metadata": {}})["verdict"] == rc.SATISFIED


def test_old_run_not_judged_on_latest_log(rc):
    """Le log décrit le DERNIER run : un run antérieur ne doit pas en hériter.

    Sinon un vieux run serait jugé « a travaillé » sur le log d'un autre.
    """
    old = {"id": 34, "outcome": "crashed",
           "metadata": {"protocol_violation": True}}
    v = rc.classify_run(old, LOG_WORKED, "", is_latest=False)
    assert v["verdict"] == rc.UNCLEAR  # pas de preuve propre à CE run


# ------------------------------------------------------- agrégat

def _viol(i):
    return {"id": i, "outcome": "crashed",
            "metadata": {"protocol_violation": True}}


def test_contract_state_never_started(rc):
    c = rc.task_contract([_viol(34), _viol(35), _viol(37)], LOG_NEVER_STARTED)
    assert c["state"] == rc.NEVER_STARTED
    assert c["violations"] == 3
    assert c["gave_up"] == 0


def test_contract_state_work_done(rc):
    c = rc.task_contract([_viol(50)], LOG_WORKED, "commit 50f881f")
    assert c["state"] == rc.WORK_DONE


def test_contract_log_goes_to_last_violation_not_last_run(rc):
    """Le log décrit le dernier run EXÉCUTÉ — qui peut être un run réussi
    après les violations. L'attribuer au dernier run (non-violation) laisserait
    toutes les violations sans preuve : c'est le bug constaté sur projecta.
    """
    runs = [_viol(1), _viol(2), _viol(3), _viol(4),
            {"id": 5, "outcome": "completed", "metadata": {"pr": {"number": 3}}}]
    c = rc.task_contract(runs, LOG_NEVER_STARTED)
    assert c["state"] == rc.NEVER_STARTED          # le log est bien exploité
    assert c["violations"] == 4
    assert c["runs_satisfied"] == 1


def test_contract_infra_dominates(rc):
    """Si le dernier run n'a pas démarré, l'infra domine — même si un
    summary antérieur décrit du travail : le vrai blocage est l'infra."""
    c = rc.task_contract([_viol(34), _viol(46)], LOG_NEVER_STARTED,
                         "ancien commit 50f881f")
    assert c["state"] == rc.NEVER_STARTED


def test_contract_satisfied_without_violation(rc):
    runs = [{"id": 60, "outcome": "completed", "metadata": {"pr": {}}},
            {"id": 61, "outcome": "reclaimed", "metadata": {"pid": 1}}]
    c = rc.task_contract(runs)
    assert c["state"] == rc.SATISFIED
    assert c["runs_satisfied"] == 1
    assert c["violations"] == 0


def test_contract_counts_gave_up(rc):
    events = [{"kind": "gave_up", "payload": {"failures": 4}},
              {"kind": "protocol_violation", "payload": {}}]
    c = rc.task_contract([_viol(46)], LOG_NEVER_STARTED, None, events)
    assert c["gave_up"] == 1


def test_contract_report_shape(rc):
    c = rc.task_contract([_viol(46)], LOG_NEVER_STARTED)
    for key in ("state", "runs_audited", "runs_satisfied", "violations",
                "gave_up", "verdicts"):
        assert key in c


# ------------------------------------------------------------------ CLI

def test_main_requires_target(rc, monkeypatch):
    monkeypatch.setattr("sys.argv", ["pj_run_contract.py", "--board", "x"])
    with pytest.raises(SystemExit):
        rc.main()


def test_status_flag_includes_archived(rc, monkeypatch):
    """Les cartes écartées (archived) sont auditables via --status.

    Ce sont justement celles qui ont été bloquées par l'infra et mises de
    côté sans diagnostic — l'audit doit pouvoir les rattraper.
    """
    seen = {}

    def fake_list(board, statuses=None):
        seen["statuses"] = statuses
        return []

    monkeypatch.setattr(rc, "list_tasks", fake_list)
    monkeypatch.setattr("sys.argv",
                        ["pj_run_contract.py", "--board", "x", "--all",
                         "--status", "archived,done", "--quiet"])
    assert rc.main() == 0
    assert seen["statuses"] == ["archived", "done"]


def test_default_status_is_active_scope(rc, monkeypatch):
    seen = {}

    def fake_list(board, statuses=None):
        seen["statuses"] = statuses
        return []

    monkeypatch.setattr(rc, "list_tasks", fake_list)
    monkeypatch.setattr("sys.argv",
                        ["pj_run_contract.py", "--board", "x", "--all", "--quiet"])
    assert rc.main() == 0
    assert "archived" not in seen["statuses"]


def test_main_boards_error(rc, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("board absent")
    monkeypatch.setattr(rc, "kanban", boom)
    monkeypatch.setattr("sys.argv",
                        ["pj_run_contract.py", "--board", "x", "--task", "t_1"])
    assert rc.main() == 2


def test_board_inexistant_is_error_not_green(rc, monkeypatch, capsys):
    """Un board inexistant sort en rc=0 avec du TEXTE sur stdout.

    Avaler l'erreur produirait un faux « tout va bien » (exit 0) alors que
    rien n'a été audité — le pire verdict possible.
    """
    def fake_kanban(board, *args, **kw):
        return "kanban: board 'x' does not exist. Create it with `hermes kanban boards create x`.\n"
    monkeypatch.setattr(rc, "kanban", fake_kanban)
    monkeypatch.setattr("sys.argv",
                        ["pj_run_contract.py", "--board", "x", "--all"])
    assert rc.main() == 2
    assert "ERREUR" in capsys.readouterr().out


def test_list_tasks_rejects_non_json(rc, monkeypatch):
    monkeypatch.setattr(rc, "kanban", lambda *a, **k: "board 'x' does not exist")
    with pytest.raises(RuntimeError):
        rc.list_tasks("x")


def test_list_tasks_empty_board_is_ok(rc, monkeypatch):
    monkeypatch.setattr(rc, "kanban", lambda *a, **k: "[]")
    assert rc.list_tasks("x") == []