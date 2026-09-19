#!/usr/bin/env bash
# Wrapper cron : pont GitHub<->kanban pour hyron-fr/example-repo (board pj-example-repo).
# Le scheduler cron ne partage pas le PATH interactif : résoudre gh/hermes.
export PATH="$HOME/.local/bin:$PATH"
command -v gh >/dev/null 2>&1 || { echo "gh introuvable dans PATH"; exit 1; }
export GH_REPO=hyron-fr/example-repo
export KANBAN_BOARD=pj-example-repo
export KANBAN_ASSIGNEE=pj-master
export BOT_GRACE_SECONDS=0  # pas de bot gh-triage sur ces boards
export PJ_IMPORT_TRIAGE=1  # racine en triage ; déploiement par cron agent pj-master
exec python3 ${HERMES_WORKFLOW}/pipeline/gh_kanban_bridge.py "$@"
