#!/usr/bin/env python3
"""Poste le contenu d'un fichier dans un thread Discord (pj-master)."""
import importlib.util
import sys
from pathlib import Path

HELPER = Path.home() / ".hermes/scripts/discord_thread.py"
spec = importlib.util.spec_from_file_location("discord_thread", HELPER)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

thread_id = sys.argv[1]
path = Path(sys.argv[2])
content = path.read_text(encoding="utf-8")
msg = mod.api("POST", f"/channels/{thread_id}/messages", {"content": content})
print("sent", msg.get("id"), "len", len(content))
