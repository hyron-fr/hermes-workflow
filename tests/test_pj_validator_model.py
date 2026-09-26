"""Tests de pj_validator_model — modèle de validation distinct du dev (0 LLM).

Fonctions pures via importlib ; `env` injectable (aucun os.environ) ; sans
réseau ni dépendance externe. Convention : exits 0/2 sur la CLI.
"""
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PATH = str(REPO / "pipeline" / "pj_validator_model.py")


@pytest.fixture(scope="module")
def vm():
    spec = importlib.util.spec_from_file_location("vm", PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def slices(dev=None, validator=None, dev_slice=None, validator_slice=None):
    doc = {"repo": "r", "branch": "wt/x", "issue": 7, "slices": [
        {"k": 1, "parallel": {}},
    ]}
    if dev:
        doc["dev_model"] = dev
    if validator:
        doc["validator_model"] = validator
    if dev_slice:
        doc["slices"][0]["dev_model"] = dev_slice
    if validator_slice:
        doc["slices"][0]["validator_model"] = validator_slice
    return doc


# ------------------------------------------------------------------ rôles

def test_role_for_key_prefixes(vm):
    assert vm.role_for_key("dev-1") == "dev"
    assert vm.role_for_key("test-1") == "validator"
    assert vm.role_for_key("conv-1") == "validator"
    assert vm.role_for_key("doc-1") == "doc"
    assert vm.role_for_key("worktree-mk") == "dev"
    assert vm.role_for_key("worktree-rm") == "dev"
    assert vm.role_for_key("t6") == "master"
    assert vm.role_for_key("inconnu") is None


# ------------------------------------------------------------------ résolution

def test_resolve_none_by_default(vm):
    m = vm.resolve_role_models(slices(), {})
    assert all(m[r]["model"] is None for r in vm.ROLES)


def test_resolve_root_level(vm):
    m = vm.resolve_role_models(slices(dev="a", validator="b"), {})
    assert m["dev"]["model"] == "a"
    assert m["validator"]["model"] == "b"
    assert m["doc"]["model"] is None


def test_resolve_slice_beats_root(vm):
    m = vm.resolve_role_models(
        slices(dev="a", validator="b", validator_slice="c"), {})
    assert m["validator"]["model"] == "c"   # slice gagne
    assert m["dev"]["model"] == "a"


def test_resolve_env_is_last_resort(vm):
    env = {"PJ_DEV_MODEL": "env-dev", "PJ_VALIDATOR_MODEL": "env-val"}
    m = vm.resolve_role_models(slices(), env)
    assert m["dev"]["model"] == "env-dev"
    assert m["validator"]["model"] == "env-val"
    # racine > env
    m2 = vm.resolve_role_models(slices(dev="root"), env)
    assert m2["dev"]["model"] == "root"
    # slice > racine > env
    m3 = vm.resolve_role_models(slices(dev="root", dev_slice="s"), env)
    assert m3["dev"]["model"] == "s"


def test_resolve_provider_follows_same_rule(vm):
    doc = slices()
    doc["validator_provider"] = "litellm-proxy-gcp"
    m = vm.resolve_role_models(doc, {"PJ_DEV_PROVIDER": "p"})
    assert m["validator"]["provider"] == "litellm-proxy-gcp"
    assert m["dev"]["provider"] == "p"


def test_resolve_case_insensitive_distinction(vm):
    m = vm.resolve_role_models(slices(dev="Qwen3.8-27B", validator="qwen3.8-27b"), {})
    ok, reason = vm.validator_differs(m)
    assert ok is False
    assert "qwen3.8-27b" in reason


# ------------------------------------------------------------------ distinction

def test_differs_true_when_distinct(vm):
    m = vm.resolve_role_models(slices(dev="a", validator="b"), {})
    assert vm.validator_differs(m) == (True, "")


def test_differs_false_when_same(vm):
    m = vm.resolve_role_models(slices(dev="qwen3.8-27b", validator="qwen3.8-27b"), {})
    ok, reason = vm.validator_differs(m)
    assert ok is False
    assert "qwen3.8-27b" in reason and "self-confirmation" in reason


def test_differs_true_when_one_missing(vm):
    # dev pincé, validator hérite du profil : on ne peut pas affirmer la
    # self-confirmation -> pas d'alerte (dégradation ouverte).
    m = vm.resolve_role_models(slices(dev="a"), {})
    assert vm.validator_differs(m) == (True, "")


# ------------------------------------------------------------------ annotate

def test_annotate_pins_models_on_cards(vm):
    doc = slices(dev="m-dev", validator="m-val")
    m = vm.resolve_role_models(doc, {})
    plan = {"cards": [
        {"key": "dev-1", "assignee": "pj-dev"},
        {"key": "test-1", "assignee": "pj-test"},
        {"key": "conv-1", "assignee": "pj-test"},
        {"key": "t6", "assignee": "pj-master"},
    ]}
    plan, warns = vm.annotate_plan(plan, m)
    assert plan["cards"][0]["model"] == "m-dev"
    assert plan["cards"][1]["model"] == "m-val"
    assert plan["cards"][2]["model"] == "m-val"
    assert "model" not in plan["cards"][3]   # master sans modèle
    assert warns == []


def test_annotate_provider_without_model_warns(vm):
    doc = slices()
    doc["dev_provider"] = "p"
    m = vm.resolve_role_models(doc, {})
    plan = {"cards": [{"key": "dev-1"}]}
    _, warns = vm.annotate_plan(plan, m)
    assert warns and "provider sans modèle" in warns[0]
    assert "model" not in plan["cards"][0]


# ------------------------------------------------------------------ CLI

def test_cli_json(tmp_path, vm):
    p = tmp_path / "slices.json"
    p.write_text(json.dumps(slices(dev="a", validator="a")), encoding="utf-8")
    import subprocess, sys
    r = subprocess.run([sys.executable, PATH, "--slices", str(p), "--json"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["validator_differs"] is False


def test_cli_missing(tmp_path, vm):
    import subprocess, sys
    r = subprocess.run([sys.executable, PATH, "--slices", str(tmp_path / "x.json")],
                       capture_output=True, text=True)
    assert r.returncode == 2


def test_cli_bad_json(tmp_path, vm):
    p = tmp_path / "slices.json"
    p.write_text("{pas du json", encoding="utf-8")
    import subprocess, sys
    r = subprocess.run([sys.executable, PATH, "--slices", str(p)],
                       capture_output=True, text=True)
    assert r.returncode == 2
