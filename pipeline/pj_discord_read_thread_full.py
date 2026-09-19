#!/usr/bin/env python3
"""Relit TOUT un thread Discord (token pj-master) avec les messages COMPLETS.

Contrairement à `pj_discord_read_thread.py` (qui tronque le contenu à 160 c et
ne lit que les N derniers messages), ce lecteur pagine tout le fil et imprime
le contenu intégral. Indispensable pour vérifier un verdict humain (un « 2a »
noyé dans un fil de 90 messages) ou relire une décision avant d'agir.

Usage :
  python3 <hermes-workflow>/pipeline/pj_discord_read_thread_full.py <thread_id> [max_chars]
      max_chars : troncature par message (défaut 6000, 0 = pas de troncature)
"""
import importlib.util
import sys
from pathlib import Path

# Racine du depot, resolue depuis ce fichier (aucun chemin absolu).
WORKFLOW_ROOT = Path(__file__).resolve().parents[1]

HELPER = Path.home() / ".hermes/scripts/discord_thread.py"
spec = importlib.util.spec_from_file_location("discord_thread", HELPER)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fetch_all(thread_id: str) -> list[dict]:
    """Récupère tous les messages du fil, paginés par `after`, triés par id."""
    msgs: list[dict] = []
    after = None
    while True:
        path = f"/channels/{thread_id}/messages?limit=100"
        if after:
            path += f"&after={after}"
        data = mod.api("GET", path)
        if not data:
            break
        msgs.extend(data)
        if len(data) < 100:
            break
        after = max(int(m["id"]) for m in data)
    msgs.sort(key=lambda m: int(m["id"]))
    return msgs


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    thread_id = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 6000

    msgs = fetch_all(thread_id)
    # Les messages du bot lui-même sont du bruit de progression : on les marque
    # mais on les imprime (la traçabilité des envois compte pour la vérification).
    print(f"TOTAL {len(msgs)} messages (thread {thread_id})")
    for m in msgs:
        a = m.get("author", {})
        att = [x.get("filename") for x in m.get("attachments", [])]
        body = m.get("content") or ""
        if limit:
            body = body[:limit]
        print("=" * 90)
        print(f"{m['id']} {a.get('username')} {a.get('id')} {m.get('timestamp')} "
              f"ATT:{att} len={len(m.get('content') or '')}")
        print(body)


if __name__ == "__main__":
    main()
