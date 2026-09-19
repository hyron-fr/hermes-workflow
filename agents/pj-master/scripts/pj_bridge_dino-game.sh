#!/usr/bin/env bash
# Wrapper cron : pont GitHub<->kanban pour hyron-fr/dino-game (board pj-dino-game).
export PATH="$HOME/.local/bin:$PATH"
command -v gh >/dev/null 2>&1 || { echo "gh introuvable"; exit 1; }
export GH_REPO=hyron-fr/dino-game
export KANBAN_BOARD=pj-dino-game
export KANBAN_ASSIGNEE=pj-master
export BOT_GRACE_SECONDS=0
export PJ_IMPORT_TRIAGE=1
exec python3 ${HERMES_WORKFLOW}/pipeline/gh_kanban_bridge.py "$@"
