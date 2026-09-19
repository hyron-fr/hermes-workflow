#!/usr/bin/env bash
# Wrapper cron : pont GitHub<->kanban pour hyron-fr/hermes-experiment (board pj-hermes-experiment).
export PATH="$HOME/.local/bin:$PATH"
command -v gh >/dev/null 2>&1 || { echo "gh introuvable"; exit 1; }
export GH_REPO=hyron-fr/hermes-experiment
export KANBAN_BOARD=pj-hermes-experiment
export KANBAN_ASSIGNEE=pj-master
export BOT_GRACE_SECONDS=0
export PJ_IMPORT_TRIAGE=1
exec python3 ${HERMES_WORKFLOW}/bridge/gh_kanban_bridge.py "$@"
