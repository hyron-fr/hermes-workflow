#!/usr/bin/env python3
"""Relit les N derniers messages d'un thread Discord (pj-master) — verification."""
import importlib.util
import sys
from pathlib import Path

HELPER = Path.home() / ".hermes/scripts/discord_thread.py"
spec = importlib.util.spec_from_file_location("discord_thread", HELPER)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

thread_id = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 3
data = mod.api("GET", f"/channels/{thread_id}/messages?limit={limit}")
for m in reversed(data):
    author = m.get("author", {}).get("username")
    content = (m.get("content") or "")[:160].replace("\n", " | ")
    print(f"[{m['id']}] {author}: {content}")
