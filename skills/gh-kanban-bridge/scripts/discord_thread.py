#!/usr/bin/env python3
"""
Helper Discord pour gh-triage (REST API, token lu dans le .env du profil).

Le bot gh-triage l'appelle depuis ses sessions cron — les outils
hermes-discord n'étant pas disponibles hors sessions gateway.

Usage :
  discord_thread.py create <channel_id> "<nom>" "<message>"
      -> crée un thread public ancré au channel + poste le message
         d'accueil dans le thread. Imprime l'id du thread.
  discord_thread.py send <thread_id> "<message>" [--go-nogo <N> | --components '<json>']
      -> poste un message dans un thread existant.
         --go-nogo <N>  : attache une ActionRow avec 2 boutons
                           ✅ Go (triage:go:<N>) / ❌ No go (triage:nogo:<N>).
         --components '<json>' : attache des composants Discord arbitraires
                           (format wire Discord) — pour les futurs points de
                           décision (import pull, clôture handoff).
  discord_thread.py rename <thread_id> "<nom>"
      -> renomme un thread (PATCH /channels/<id>).
  discord_thread.py threads <channel_id>
      -> liste les threads actifs d'un channel (id + nom).
"""

import json
import sys
import urllib.request
from pathlib import Path

TOKEN_FILE = Path.home() / ".hermes/profiles/gh-triage/.env"
API = "https://discord.com/api/v10"


def bot_token() -> str:
    for line in TOKEN_FILE.read_text().splitlines():
        if line.startswith("DISCORD_BOT_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("DISCORD_BOT_TOKEN introuvable dans " + str(TOKEN_FILE))


def api(method: str, path: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": "Bot " + bot_token(),
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (https://github.com/hyron-fr/hermes-experiment, 1.0)",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        raise SystemExit(f"HTTP {e.code}: {err[:300]}")


def go_nogo_components(n: str) -> list:
    """ActionRow go/no-go déterministe (custom_id encode la décision)."""
    return [
        {
            "type": 1,
            "components": [
                {"type": 2, "style": 3, "label": "✅ Go",
                 "custom_id": f"triage:go:{n}"},
                {"type": 2, "style": 4, "label": "❌ No go",
                 "custom_id": f"triage:nogo:{n}"},
            ],
        }
    ]


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "create":
        channel_id, name, message = sys.argv[2], sys.argv[3], sys.argv[4]
        thread = api("POST", f"/channels/{channel_id}/threads",
                     {"name": name, "type": 11, "auto_archive_duration": 4320})
        tid = thread["id"]
        api("POST", f"/channels/{tid}/messages", {"content": message})
        print(tid)
    elif cmd == "send":
        thread_id, message = sys.argv[2], sys.argv[3]
        payload = {"content": message}
        args = sys.argv[4:]
        if "--go-nogo" in args:
            n = args[args.index("--go-nogo") + 1]
            payload["components"] = go_nogo_components(n)
        elif "--components" in args:
            payload["components"] = json.loads(args[args.index("--components") + 1])
        api("POST", f"/channels/{thread_id}/messages", payload)
        print("sent")
    elif cmd == "threads":
        channel_id = sys.argv[2]
        guild_id = sys.argv[3] if len(sys.argv) > 3 else "${DISCORD_ID}"
        active = api("GET", f"/guilds/{guild_id}/threads/active")
        for t in active.get("threads", []):
            if t.get("parent_id") == channel_id or t.get("parent_id") is None:
                print(t["id"], t["name"])
    elif cmd == "rename":
        thread_id, name = sys.argv[2], sys.argv[3]
        api("PATCH", f"/channels/{thread_id}", {"name": name})
        print("renamed")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
