#!/usr/bin/env bash
# Wrapper cron : câblage /ok (issue #5) — consomme les enfants de décision du dépôt
# hermes-workflow, applique la décision humaine (comment + unblock) et notifie les
# deux fils (enfant notifié puis fermé, parent notifié, jamais fermé).
#
# Déterministe, 0 LLM. Tick muet (rc=0, stdout vide) = rien à faire.
#
# Les variables sont requises : validate_config refuse bruyamment (rc=2) si l'une
# manque ou est vide — un tick fantôme serait pire qu'un tick refusé.
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

export PJ_WATCH_ORG="hyron-fr"
export PJ_WATCH_REPOS="hermes-workflow"
export PJ_WATCH_BOARD="pj-hermes-workflow"

# Copie canonique versionnée du dépôt (le dépôt est la source ; la copie installée
# du profil est une copie d'exécution — même modèle que pj_escalate / pj_publish).
WATCH_SRC="${PJ_WATCH_SRC:-/home/elix/pj-repos/hermes-workflow/pipeline/pj_decision_watch.py}"
if [ ! -f "$WATCH_SRC" ]; then
  echo "câblage /ok introuvable : $WATCH_SRC" >&2
  exit 2
fi

exec python3 "$WATCH_SRC" "$@"
