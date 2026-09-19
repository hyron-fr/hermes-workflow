#!/usr/bin/env python3
"""pj_docs_memory — alimente Hindsight avec le vault docs/ après merge de la PR.

Idempotent : un fichier d'état garde le hash du contenu déjà envoyé (par repo+chemin).
N'envoie que les notes dont le hash a changé.

Usage :
  pj_docs_memory.py --repo ${HOME}/pj-repos/dino-game --issue 3 [--dry-run]
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

HINDSIGHT_URL = os.environ.get("HINDSIGHT_API_URL", "http://localhost:9078")
BANK = os.environ.get("HINDSIGHT_BANK_ID", "pj")
STATE = Path.home() / ".hermes" / "cache" / "pj_docs_memory_state.json"
EXCLUDE_PARTS = {"playtest", ".obsidian"}


def iter_notes(repo: Path):
    """(path, text) des notes du vault, hors playtest, hors vides."""
    docs = repo / "docs"
    if not docs.is_dir():
        return
    for p in sorted(docs.rglob("*.md")):
        if EXCLUDE_PARTS & set(p.parts):
            continue
        text = p.read_text(encoding="utf-8", errors="replace").strip()
        if text:
            yield p, text


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_payload(repo: str, issue: int, relpath: str, text: str) -> dict:
    return {
        "content": text,
        "context": f"doc:{relpath}",
        "tags": [f"project:{repo}", f"doc:{relpath}", f"issue:{issue}"],
    }


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True))


def retain(payload: dict) -> bool:
    url = f"{HINDSIGHT_URL}/v1/default/banks/{BANK}/memories"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return 200 <= r.status < 300
    except Exception as e:
        print(f"[pj-docmem] échec retain: {e}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--issue", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    repo_path = Path(a.repo).expanduser().resolve()
    repo = repo_path.name
    state = load_state()
    sent = skipped = failed = 0
    for p, text in iter_notes(repo_path):
        rel = str(p.relative_to(repo_path))
        h = content_hash(text)
        key = f"{repo}:{rel}"
        if state.get(key) == h:
            skipped += 1
            continue
        payload = build_payload(repo, a.issue, rel, text)
        if a.dry_run:
            print(f"[pj-docmem] (dry) {rel} ({len(text)} car.)")
            sent += 1
            continue
        if retain(payload):
            state[key] = h
            sent += 1
        else:
            failed += 1
    if not a.dry_run:
        save_state(state)
    print(f"[pj-docmem] envoyés={sent} inchangés={skipped} échecs={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
