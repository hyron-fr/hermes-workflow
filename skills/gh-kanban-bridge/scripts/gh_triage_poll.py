#!/usr/bin/env python3
"""
Poll des issues GitHub pour le bot gh-triage.

Affiche (stdout) les issues ouvertes candidates au drill — sans label
'kanban' (miroir carte créée) ni 'triage' (drill en cours) — UNIQUEMENT
quand il y en a de nouvelles depuis le dernier poll (fichier d'état
~/.hermes/profiles/gh-triage/gh-triage-poll-state.json).

Sans nouveauté : stdout vide (tick cron no-agent muet).
Avec nouveauté : stdout = JSON, injecté comme prompt dans une session
agent gh-triage (mode agent du cron) qui ouvre les threads + drill.

Usage :
  gh_triage_poll.py list   # force l'affichage des candidates (debug)
  gh_triage_poll.py mark N # marque l'issue N comme vue (après thread ouvert)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = "hyron-fr/hermes-experiment"
STATE_FILE = Path.home() / ".hermes/profiles/gh-triage/gh-triage-poll-state.json"
# IDs Discord fournis par l'utilisateur (serveur de l'expérience)
GUILD_ID = "${DISCORD_ID}"
CHANNEL_ID = "${DISCORD_ID}"
PROMPT_HEADER = (
    f"NOUVELLE(S) ISSUE(S) GITHUB à trier (repo {REPO}). Pour chacune :\n"
    f"1) Ouvre un thread Discord dans le channel {CHANNEL_ID} "
    f"(guild {GUILD_ID}) nommé '🎫 Issue #<N> — <titre>' avec ton message "
    f"d'accueil (résumé + lien + ta lecture du besoin).\n"
    f"2) Labellise l'issue 'triage' (gh issue edit N --repo {REPO} "
    f"--add-label triage) pour que le cron du pont ne l'importe pas "
    f"pendant le drill.\n"
    f"3) Drill jusqu'à spec complète, poste la synthèse AVEC les boutons "
    f"✅ Go / ❌ No go (discord_thread.py send --go-nogo <N>), et crée la "
    f"carte kanban SEULEMENT après le clic ✅ Go (voir SOUL.md).\n"
    "Issues à traiter (JSON) :\n"
)


def state_path() -> Path:
    return STATE_FILE


def seen_numbers() -> set[int]:
    try:
        return set(json.loads(state_path().read_text()))
    except Exception:
        return set()


def save_seen(numbers: set[int]) -> None:
    state_path().parent.mkdir(parents=True, exist_ok=True)
    state_path().write_text(json.dumps(sorted(numbers)))


def fetch_issues() -> list[dict]:
    out = subprocess.run(
        ["gh", "issue", "list", "--repo", REPO, "--state", "open",
         "--json", "number,title,body,url"],
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "poll"

    if mode == "mark":
        nums = seen_numbers()
        for a in sys.argv[2:]:
            nums.add(int(a))
        save_seen(nums)
        return

    issues = fetch_issues()
    if mode == "list":
        print(json.dumps(issues, indent=1, ensure_ascii=False))
        return

    seen = seen_numbers()
    fresh = [i for i in issues if i["number"] not in seen]

    # Anti-course : une issue déjà labellisée 'triage' ou 'kanban' n'est
    # pas une nouveauté à driller même si elle est absente de l'état local
    # (ex: marquée par le bot via un autre chemin).
    labels_out = subprocess.run(
        ["gh", "issue", "list", "--repo", REPO, "--state", "open",
         "--json", "number,labels"],
        capture_output=True, text=True, check=True)
    labeled = {l["number"]: {x["name"] for x in l["labels"]}
               for l in json.loads(labels_out.stdout)}
    fresh = [i for i in fresh
             if not ({"triage", "kanban"} & labeled.get(i["number"], set()))]

    # Marque tout ce qui est visible maintenant comme vu : soit on vient de
    # l'annoncer, soit on le saute volontairement (issue antérieure au bot).
    all_numbers = {i["number"] for i in issues} | seen
    if not fresh:
        save_seen(all_numbers)
        return  # tick muet

    save_seen(all_numbers)
    prompt = PROMPT_HEADER + json.dumps(fresh, indent=1, ensure_ascii=False)
    print(prompt)


if __name__ == "__main__":
    main()