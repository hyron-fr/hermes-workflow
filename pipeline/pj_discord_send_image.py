#!/usr/bin/env python3
"""
Poste une IMAGE (pièce jointe) dans un thread/channel Discord — profil pj-master.

Le helper discord_thread.py ne sait poster que du texte (content JSON) ; pour
joindre un fichier il faut un POST multipart/form-data avec `payload_json` +
`files[0]`. C'est ce que fait ce script.

Usage :
  pj_discord_send_image.py <channel_ou_thread_id> <chemin_image> "<légende texte>"
    -> imprime "sent <message_id>" (+ l'URL de la pièce jointe)

Contraintes Discord respectées : légende <= 2000 caractères, fichier <= 8 Mo.
"""

import importlib.util
import json
import mimetypes
import sys
import urllib.request
import uuid
from pathlib import Path

HELPER = Path.home() / ".hermes/scripts/discord_thread.py"
spec = importlib.util.spec_from_file_location("discord_thread", HELPER)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

MAX_CAPTION = 2000
MAX_BYTES = 8 * 1024 * 1024


def post_image(channel_id: str, path: Path, caption: str) -> dict:
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise SystemExit(f"fichier trop gros : {len(data)} > {MAX_BYTES}")
    if len(caption) > MAX_CAPTION:
        raise SystemExit(f"légende trop longue : {len(caption)} > {MAX_CAPTION}")
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    boundary = "----pj" + uuid.uuid4().hex
    body = b""
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="payload_json"\r\n'
    body += b"Content-Type: application/json\r\n\r\n"
    body += json.dumps({"content": caption}).encode()
    body += b"\r\n"
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="files[0]"; filename="{path.name}"\r\n'.encode()
    body += f"Content-Type: {ctype}\r\n\r\n".encode()
    body += data
    body += b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        data=body,
        headers={
            "Authorization": "Bot " + mod.bot_token(),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "DiscordBot (https://github.com/hyron-fr/hermes-experiment, 1.0)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read().decode()[:400]}")


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    channel_id, p, caption = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    if not p.is_file():
        raise SystemExit(f"introuvable : {p}")
    msg = post_image(channel_id, p, caption)
    atts = msg.get("attachments", [])
    print("sent", msg.get("id"), "len", len(caption))
    for a in atts:
        print("attachment:", a.get("filename"), a.get("size"), a.get("url"))


if __name__ == "__main__":
    main()
