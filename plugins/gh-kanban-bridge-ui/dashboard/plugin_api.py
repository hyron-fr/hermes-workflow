"""gh-kanban-bridge dashboard plugin — backend API routes.

Mounted at ``/api/plugins/gh-kanban-bridge/`` by the dashboard plugin system.

Three concerns, mirroring the three UI sections:

  * CONFIG  — read/write the bridge's env vars in the profile ``.env``.
  * STATE   — wrap ``gh_kanban_bridge.py stats --json``.
  * ACTIONS — run ``pull``/``push``/``sync``/``new`` and return the real
              stdout/stderr.

The bridge itself (``bridge/gh_kanban_bridge.py``) is NOT modified here; this
layer only drives it via subprocess, exactly as the cron does. ``sync`` stays
idempotent because the bridge's idempotency-key logic is untouched.

Security: the only keys this plugin ever reads or writes are the six
whitelisted bridge vars below. The Discord token (and every other secret in
``.env``) is never read, never returned, and never written — the whitelist is
the boundary for the "token never appears" acceptance criterion.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hermes_cli.config import load_env, save_env_value

# Racine du dépôt : résolue depuis ce fichier (aucun chemin absolu).
WORKFLOW_ROOT = Path(__file__).resolve().parents[1]

router = APIRouter()

# The only keys this plugin reads or writes. This whitelist is the security
# boundary: the Discord token and every other secret in .env are never touched.
CONFIG_KEYS = [
    "GH_REPO",
    "KANBAN_BOARD",
    "KANBAN_ASSIGNEE",
    "BOT_GRACE_SECONDS",
    "DRY_RUN",
    "BRIDGE_VERBOSE",
]
BOOL_KEYS = {"DRY_RUN", "BRIDGE_VERBOSE"}
DEFAULTS = {
    "GH_REPO": "hyron-fr/hermes-experiment",
    "KANBAN_BOARD": "hermes-experiment",
    "KANBAN_ASSIGNEE": "default",
    "BOT_GRACE_SECONDS": "600",
    "DRY_RUN": "0",
    "BRIDGE_VERBOSE": "0",
}

# Actions the bridge accepts (mirrors its main() dispatch).
ACTIONS = ("pull", "push", "sync", "new")


def _bridge_script() -> str:
    """Resolve the bridge entry point, preferring the deployed copy.

    Order: the deployed ``.py`` in the profile scripts dir, then the ``.sh``
    wrapper (which execs the repo copy), then the canonical repo path.
    """
    home = Path(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")))
    candidates = [
        home / "scripts" / "gh_kanban_bridge.py",
        home / "scripts" / "gh_kanban_bridge.sh",
        WORKFLOW_ROOT / "pipeline" / "gh_kanban_bridge.py",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return str(candidates[0])


def _bridge_env() -> dict:
    """``os.environ`` plus the bridge's config vars from ``.env``.

    The bridge reads its config at import time from the environment, so we
    inject the persisted values here so the UI's saved config takes effect.
    ``BRIDGE_VERBOSE`` is forced on for action runs so the UI always shows
    complete output (a UI-layer choice; the bridge's idempotency is unchanged).
    """
    env = dict(os.environ)
    loaded = load_env()
    for key in CONFIG_KEYS:
        val = loaded.get(key, DEFAULTS[key])
        if val is not None:
            env[key] = val
    env["BRIDGE_VERBOSE"] = "1"
    return env


def _run_bridge(action: str, timeout: int = 180) -> dict:
    """Run the bridge with ``action`` and return exit code + captured output."""
    script = _bridge_script()
    if script.endswith(".py"):
        cmd = [sys.executable, script, action]
    else:
        cmd = [script, action]
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=_bridge_env()
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504, detail=f"bridge {action} timed out after {timeout}s"
        )
    return {
        "action": action,
        "exit_code": r.returncode,
        "stdout": r.stdout,
        "stderr": r.stderr,
    }


def _run_stats() -> dict:
    """Run ``stats --json`` and return the parsed payload."""
    script = _bridge_script()
    if script.endswith(".py"):
        cmd = [sys.executable, script, "stats", "--json"]
    else:
        cmd = [script, "stats", "--json"]
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, env=_bridge_env()
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="bridge stats timed out")
    if r.returncode != 0:
        raise HTTPException(
            status_code=502, detail=f"stats failed: {r.stderr.strip()}"
        )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="stats returned non-JSON output")


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

@router.get("/config")
def get_config() -> dict:
    """Return the six bridge config fields (booleans as JSON booleans)."""
    loaded = load_env()
    out: dict[str, Any] = {}
    for key in CONFIG_KEYS:
        raw = loaded.get(key, DEFAULTS[key])
        out[key] = (raw == "1") if key in BOOL_KEYS else raw
    return out


class ConfigUpdate(BaseModel):
    values: dict[str, Any]


@router.put("/config")
def put_config(body: ConfigUpdate) -> dict:
    """Persist a subset of the bridge config fields to ``.env``.

    Only whitelisted keys are accepted; the token can never be written here.
    """
    for key, value in body.values.items():
        if key not in CONFIG_KEYS:
            raise HTTPException(status_code=400, detail=f"unknown config key: {key}")
        if key in BOOL_KEYS:
            if isinstance(value, bool):
                value = "1" if value else "0"
            elif str(value).lower() in ("1", "true", "yes", "on"):
                value = "1"
            elif str(value).lower() in ("0", "false", "no", "off"):
                value = "0"
            else:
                raise HTTPException(status_code=400, detail=f"{key} must be a boolean")
        else:
            value = str(value)
        try:
            save_env_value(key, value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    return get_config()


# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

@router.get("/state")
def get_state() -> dict:
    """Live bridge state (cards by status, issues, pending push/pull)."""
    return _run_stats()


# ---------------------------------------------------------------------------
# ACTIONS
# ---------------------------------------------------------------------------

@router.post("/sync")
def post_sync() -> dict:
    return _run_bridge("sync")


@router.post("/pull")
def post_pull() -> dict:
    return _run_bridge("pull")


@router.post("/push")
def post_push() -> dict:
    return _run_bridge("push")


@router.post("/new")
def post_new() -> dict:
    return _run_bridge("new")
