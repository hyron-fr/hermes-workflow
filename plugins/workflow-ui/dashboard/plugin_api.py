"""workflow dashboard plugin — backend API routes.

Mounted at ``/api/plugins/workflow/`` by the dashboard plugin system.

Concerns, mirroring the UI:

  * LIST     — enumerate the ``.yaml`` files in the workflows/ directory.
  * READ     — read + parse a workflow YAML, return raw text + parsed
               structure + validation errors.
  * VALIDATE — validate raw YAML text WITHOUT saving (live validation in the
               editor, debounced client-side).
  * SAVE     — validate then persist a workflow YAML.

The workflow engine (``pipeline/engine.py``) is NOT modified here; this layer
only reads/validates/writes the YAML files the engine consumes. Validation
mirrors the engine's expectations (step ``id``/``type``, ``gate`` routing via
``on_pass``/``on_fail``, ``on_fail`` targets) so a workflow that passes here
is one the engine can actually run.

Security: this plugin only ever reads/writes files inside the workflows
directory. The ``name`` path segment is sanitized (no ``..``, no absolute
paths, no separators) so a crafted request cannot escape the directory.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Valid step types understood by pipeline/engine.py.
STEP_TYPES = ("agentic", "deterministic", "gate")

# A workflow name is a bare filename stem: letters, digits, ``_``, ``-``, ``.``.
_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _workflows_dir() -> Path:
    """Resolve the workflows directory.

    Order: ``WORKFLOWS_DIR`` env override, then the hermes-experiment repo
    (canonical location), then a home-relative fallback.
    """
    env = os.environ.get("WORKFLOWS_DIR")
    if env:
        return Path(env).expanduser()
    for cand in (
        Path("${HOME}/hermes-experiment/workflows"),
        Path.home() / "hermes-experiment" / "workflows",
    ):
        if cand.is_dir():
            return cand
    return Path("${HOME}/hermes-experiment/workflows")


def _safe_name(name: str) -> str:
    """Reject path traversal / absolute paths in a workflow name."""
    if not name or not _NAME_RE.match(name):
        raise HTTPException(status_code=400, detail=f"invalid workflow name: {name!r}")
    if name in (".", "..") or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail=f"invalid workflow name: {name!r}")
    return name


def _resolve(name: str) -> Path:
    """Resolve a workflow name to a file path inside the workflows dir."""
    safe = _safe_name(name)
    path = _workflows_dir() / f"{safe}.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"workflow not found: {name}")
    return path


# ---------------------------------------------------------------------------
# Validation (mirrors pipeline/engine.py expectations)
# ---------------------------------------------------------------------------

def validate_workflow(parsed: Any) -> list[str]:
    """Return a list of human-readable validation errors (empty = valid).

    Checks the structural contract the engine relies on: a mapping with a
    ``steps`` list, each step carrying an ``id`` and a known ``type``, unique
    ids, and every routing target (``on_pass``/``on_fail``) pointing at a real
    step id.
    """
    errors: list[str] = []

    if parsed is None:
        return ["workflow vide (aucun contenu YAML)"]
    if not isinstance(parsed, dict):
        return ["le workflow doit être un mapping YAML (clé: valeur)"]

    steps = parsed.get("steps")
    if steps is None:
        errors.append("champ `steps` manquant")
        return errors
    if not isinstance(steps, list):
        errors.append("`steps` doit être une liste")
        return errors
    if not steps:
        errors.append("`steps` est vide (aucune étape)")
        return errors

    ids: list[str] = []
    for i, step in enumerate(steps):
        where = f"steps[{i}]"
        if not isinstance(step, dict):
            errors.append(f"{where}: doit être un mapping")
            continue
        sid = step.get("id")
        if not sid or not isinstance(sid, str):
            errors.append(f"{where}: champ `id` manquant ou non-string")
        else:
            ids.append(sid)
        stype = step.get("type", "agentic")
        if stype not in STEP_TYPES:
            errors.append(
                f"{where} ({sid or '?'}): type inconnu {stype!r} "
                f"(attendu: {', '.join(STEP_TYPES)})"
            )
        if stype == "gate":
            for key in ("on_pass", "on_fail"):
                if not step.get(key):
                    errors.append(f"{where} ({sid or '?'}): gate sans `{key}`")

    # Duplicate ids.
    seen: set[str] = set()
    for sid in ids:
        if sid in seen:
            errors.append(f"id d'étape dupliqué: {sid}")
        seen.add(sid)

    # Routing targets must reference a real step id.
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        sid = step.get("id", f"steps[{i}]")
        for key in ("on_pass", "on_fail"):
            target = step.get(key)
            if target and target not in seen:
                errors.append(f"{sid}: `{key}` pointe vers une étape inconnue: {target}")

    return errors


def _parse(text: str) -> tuple[Any, list[str]]:
    """Parse YAML text, returning (parsed, errors)."""
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return None, [f"erreur de syntaxe YAML: {exc}"]
    return parsed, validate_workflow(parsed)


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------

@router.get("/workflows")
def list_workflows() -> dict:
    """Enumerate the ``.yaml`` files in the workflows directory."""
    wdir = _workflows_dir()
    items = []
    if wdir.is_dir():
        for p in sorted(wdir.glob("*.yaml")):
            st = p.stat()
            items.append(
                {
                    "name": p.stem,
                    "path": str(p),
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                }
            )
    return {"dir": str(wdir), "workflows": items}


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------

@router.get("/workflows/{name}")
def get_workflow(name: str) -> dict:
    """Read a workflow: raw YAML + parsed structure + validation errors."""
    path = _resolve(name)
    text = path.read_text(encoding="utf-8")
    parsed, errors = _parse(text)
    return {
        "name": name,
        "path": str(path),
        "yaml": text,
        "parsed": parsed,
        "errors": errors,
        "valid": not errors,
        "mtime": path.stat().st_mtime,
    }


# ---------------------------------------------------------------------------
# VALIDATE (no save)
# ---------------------------------------------------------------------------

class ValidateBody(BaseModel):
    yaml: str


@router.post("/validate")
def validate(body: ValidateBody) -> dict:
    """Validate raw YAML text without persisting (live editor validation)."""
    parsed, errors = _parse(body.yaml)
    return {"valid": not errors, "errors": errors, "parsed": parsed}


# ---------------------------------------------------------------------------
# SAVE
# ---------------------------------------------------------------------------

class SaveBody(BaseModel):
    yaml: str


@router.put("/workflows/{name}")
def put_workflow(name: str, body: SaveBody) -> dict:
    """Validate then persist a workflow YAML. Refuses to save invalid YAML."""
    path = _resolve(name)
    parsed, errors = _parse(body.yaml)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "workflow invalide — non sauvegardé", "errors": errors},
        )
    path.write_text(body.yaml, encoding="utf-8")
    return {
        "name": name,
        "path": str(path),
        "valid": True,
        "errors": [],
        "mtime": path.stat().st_mtime,
    }
