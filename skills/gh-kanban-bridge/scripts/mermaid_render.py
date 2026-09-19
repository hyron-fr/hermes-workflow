#!/usr/bin/env python3
"""
Rendu Mermaid -> PNG pour gh-triage (Firefox headless, mermaid vendoré).

Usage :
  mermaid_render.py render "<fichier.mmd ou texte mermaid>" <png_sortie>
      -> écrit le PNG, imprime son chemin absolu.
  mermaid_render.py attach <thread_id> <png> "<message>"
      -> envoie le PNG dans un thread Discord (multipart).

Le rendu passe par un HTML temporaire embarquant le diagramme + mermaid
local (bridge/mermaid.min.js), screenshoté par Firefox headless (le snap
ne peut pas écrire dans /tmp, d'où le tmpdir sous $HOME).
"""

import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

REPO = Path.home() / "hermes-experiment"
MERMAID_JS = REPO / "bridge" / "mermaid.min.js"
TOKEN_FILE = Path.home() / ".hermes/profiles/gh-triage/.env"
# Firefox snap ne peut PAS écrire dans les répertoires cachés (.hermes) :
# le tmpdir doit être un dossier non caché du home.
TMP_DIR = Path.home() / "mermaid-tmp"
API = "https://discord.com/api/v10"
HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<script>{mermaid}</script>
<style>body{{background:#1e1e2e;margin:0;padding:12px;font-family:sans-serif}}</style>
</head><body>
<pre class="mermaid">
{diagram}
</pre>
<script>mermaid.initialize({{startOnLoad:true, theme:'dark', securityLevel:'loose'}});</script>
</body></html>"""


def bot_token() -> str:
    for line in TOKEN_FILE.read_text().splitlines():
        if line.startswith("DISCORD_BOT_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("DISCORD_BOT_TOKEN introuvable")


def render(diagram: str, out_png: Path) -> Path:
    if not MERMAID_JS.exists():
        raise SystemExit(f"mermaid.min.js introuvable: {MERMAID_JS}")
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=TMP_DIR) as td:
        html = Path(td) / "d.html"
        html.write_text(HTML.format(mermaid=MERMAID_JS.read_text(),
                                    diagram=diagram.replace("`", "")))
        png = Path(td) / "d.png"
        r = subprocess.run(
            ["firefox", "--headless", "--screenshot", str(png),
             "--window-size=1400,900", f"file://{html}"],
            capture_output=True, timeout=60)
        # Firefox headless reste parfois accroché après le screenshot :
        # on vérifie le fichier au lieu d'attendre la fin du process.
        for _ in range(20):
            if png.exists() and png.stat().st_size > 3000:
                break
            time.sleep(0.5)
        if not png.exists():
            raise SystemExit("rendu échoué (pas de PNG)")
        crop = _autocrop(png)
        shutil.copy(crop, out_png)
        if crop != png:
            png.unlink(missing_ok=True)
    return out_png


def _autocrop(png: Path, pad: int = 24) -> Path:
    """Recadre le PNG sur le diagramme (mermaid laisse un canvas vide)."""
    try:
        from PIL import Image, ImageChops
        img = Image.open(png).convert("RGB")
        bg = Image.new("RGB", img.size, img.getpixel((2, 2)))
        diff = ImageChops.difference(img, bg)
        bbox = diff.getbbox()
        if bbox:
            x0, y0, x1, y1 = bbox
            x0 = max(0, x0 - pad); y0 = max(0, y0 - pad)
            x1 = min(img.width, x1 + pad); y1 = min(img.height, y1 + pad)
            cropped = png.with_name(png.stem + "-crop.png")
            img.crop((x0, y0, x1, y1)).save(cropped)
            return cropped
    except Exception:
        pass
    return png


def attach(thread_id: str, png: Path, message: str) -> None:
    boundary = uuid.uuid4().hex
    payload_json = json.dumps({"content": message}).encode()
    png_bytes = png.read_bytes()
    body = b""
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name="
             f'"payload_json"\r\nContent-Type: application/json\r\n\r\n'
             ).encode() + payload_json + b"\r\n"
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name="
             f'"files[0]"; filename="{png.name}"\r\n'
             f"Content-Type: image/png\r\n\r\n").encode() + png_bytes + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{API}/channels/{thread_id}/messages", data=body, method="POST",
        headers={
            "Authorization": "Bot " + bot_token(),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "DiscordBot (https://github.com/hyron-fr/hermes-experiment, 1.0)",
        })
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status not in (200, 201):
            raise SystemExit(f"HTTP {r.status}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "render":
        src = Path(sys.argv[2])
        diagram = src.read_text() if src.exists() else sys.argv[2]
        out = Path(sys.argv[3]).resolve()
        print(render(diagram, out))
    elif cmd == "attach":
        attach(sys.argv[2], Path(sys.argv[3]).resolve(), sys.argv[4])
        print("attached")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()