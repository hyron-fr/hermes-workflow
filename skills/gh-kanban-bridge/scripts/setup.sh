#!/usr/bin/env bash
# setup.sh — déploiement idempotent du pont GitHub ↔ kanban + bot gh-triage.
#
# Câble tout sur une instance Hermes vierge en une commande :
#   - copie les 4 helpers scripts/*.py vers ${HERMES_WORKFLOW}/pipeline/
#   - crée le profil gh-triage (si absent)
#   - crée le board kanban (si absent)
#   - crée les labels GitHub kanban/triage (si absents)
#   - crée le cron gh-kanban-bridge (no-agent, */5) si absent
#   - crée le cron gh-triage-poll (profil gh-triage, agent) si absent
#   - vérifie gh auth status
#
# Idempotent : relancer ne duplique rien (mêmes crons, labels, board).
#
# Variables d'environnement (défauts entre parenthèses) :
#   GH_REPO            (hyron-fr/hermes-experiment)
#   KANBAN_BOARD       (hermes-experiment)
#   KANBAN_ASSIGNEE    (default)
#   DISCORD_GUILD_ID   (${DISCORD_ID})
#   DISCORD_CHANNEL_ID (${DISCORD_ID})

set -euo pipefail

# ---------------------------------------------------------------- config
GH_REPO="${GH_REPO:-hyron-fr/hermes-experiment}"
KANBAN_BOARD="${KANBAN_BOARD:-hermes-experiment}"
KANBAN_ASSIGNEE="${KANBAN_ASSIGNEE:-default}"
DISCORD_GUILD_ID="${DISCORD_GUILD_ID:-${DISCORD_ID}}"
DISCORD_CHANNEL_ID="${DISCORD_CHANNEL_ID:-${DISCORD_ID}}"

TRIAGE_PROFILE="gh-triage"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
export HERMES_HOME

SCRIPTS_DIR="$HERMES_HOME/scripts"
TRIAGE_SCRIPTS_DIR="$HERMES_HOME/profiles/$TRIAGE_PROFILE/scripts"

# Répertoire de la skill (là où vit setup.sh) — source des scripts à copier.
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------- binaires
HERMES_BIN="$(command -v hermes || true)"
GH_BIN="$(command -v gh || true)"
[ -n "$HERMES_BIN" ] || { echo "ERREUR: 'hermes' introuvable dans le PATH" >&2; exit 1; }
[ -n "$GH_BIN" ] || { echo "ERREUR: 'gh' introuvable dans le PATH" >&2; exit 1; }

log() { echo "[setup] $*"; }

# ---------------------------------------------------------------- gh auth
log "vérification gh auth status"
if ! "$GH_BIN" auth status >/dev/null 2>&1; then
  echo "ERREUR: gh n'est pas authentifié. Lance 'gh auth login' d'abord." >&2
  exit 1
fi

# ---------------------------------------------------------------- scripts
log "copie des helpers vers $SCRIPTS_DIR"
mkdir -p "$SCRIPTS_DIR"
for f in gh_kanban_bridge.py gh_triage_poll.py discord_thread.py mermaid_render.py; do
  cp "$SKILL_DIR/$f" "$SCRIPTS_DIR/$f"
done

# ---------------------------------------------------------------- profil gh-triage
if [ -d "$HERMES_HOME/profiles/$TRIAGE_PROFILE" ]; then
  log "profil $TRIAGE_PROFILE déjà présent"
else
  log "création du profil $TRIAGE_PROFILE"
  "$HERMES_BIN" profile create "$TRIAGE_PROFILE" >/dev/null
fi
mkdir -p "$TRIAGE_SCRIPTS_DIR"
cp "$SKILL_DIR/gh_triage_poll.py" "$TRIAGE_SCRIPTS_DIR/gh_triage_poll.py"

# ---------------------------------------------------------------- board
if "$HERMES_BIN" kanban boards list --json 2>/dev/null | grep -q "\"slug\": \"$KANBAN_BOARD\""; then
  log "board $KANBAN_BOARD déjà présent"
else
  log "création du board $KANBAN_BOARD"
  "$HERMES_BIN" kanban boards create "$KANBAN_BOARD" --name "$KANBAN_BOARD" >/dev/null
fi

# ---------------------------------------------------------------- labels
ensure_label() {
  local label="$1" color="$2" desc="$3"
  if "$GH_BIN" label list --repo "$GH_REPO" --json name 2>/dev/null | grep -q "\"$label\""; then
    log "label $label déjà présent"
  else
    log "création du label $label"
    "$GH_BIN" label create "$label" --repo "$GH_REPO" --color "$color" \
      --description "$desc" >/dev/null
  fi
}
ensure_label kanban 1d76db "Issue miroir d'une carte kanban Hermes"
ensure_label triage d93f0b "Issue en cours de drill (pas d'import auto)"

# ---------------------------------------------------------------- crons
cron_exists() {
  # $1 = chemin jobs.json, $2 = nom du job
  local jobs_file="$1" name="$2"
  [ -f "$jobs_file" ] || return 1
  JOBS_FILE="$jobs_file" JOB_NAME="$name" python3 -c '
import json, os
d = json.load(open(os.environ["JOBS_FILE"]))
print("yes" if any(j.get("name") == os.environ["JOB_NAME"] for j in d.get("jobs", [])) else "no")
' | grep -q yes
}

# Bridge (profil default, no-agent)
BRIDGE_JOBS="$HERMES_HOME/cron/jobs.json"
if cron_exists "$BRIDGE_JOBS" gh-kanban-bridge; then
  log "cron gh-kanban-bridge déjà présent"
else
  log "création du cron gh-kanban-bridge (no-agent, */5)"
  "$HERMES_BIN" cron create "*/5 * * * *" --name gh-kanban-bridge \
    --script gh_kanban_bridge.py --no-agent >/dev/null
fi

# Poll (profil gh-triage, agent)
POLL_JOBS="$HERMES_HOME/profiles/$TRIAGE_PROFILE/cron/jobs.json"
if cron_exists "$POLL_JOBS" gh-triage-poll; then
  log "cron gh-triage-poll déjà présent"
else
  log "création du cron gh-triage-poll (agent, */5)"
  "$HERMES_BIN" -p "$TRIAGE_PROFILE" cron create "*/5 * * * *" \
    "Traite les issues GitHub listées dans le Script Output. Pour CHACUNE: (1) ouvre un thread Discord dans le channel $DISCORD_CHANNEL_ID titré 'Ticket Issue #N - titre' avec message d'accueil (résumé, lien GitHub, lecture du besoin, questions de drill); (2) labellise l'issue 'triage' pour bloquer l'import auto par le pont; (3) poursuis le drill dans le thread jusqu'à spec complète - la carte kanban sera créée seulement après un 'go' explicite d'un humain dans le thread (protocole SOUL.md). Ne crée jamais de carte sans 'go'." \
    --name gh-triage-poll --script gh_triage_poll.py >/dev/null
fi

# ---------------------------------------------------------------- dashboard UI
# Plugin UI dashboard (onglet gh-kanban-bridge) : clone + enable + rappel restart.
# Le plugin vit dans le repo (plugins/gh-kanban-bridge-ui/) ; on le copie dans
# ~/.hermes/plugins/ puis on l'active (gate plugins.enabled). Le restart de la
# dashboard est laissé à l'opérateur (rappel en fin de script).
PLUGIN_SRC="$SKILL_DIR/../../../plugins/gh-kanban-bridge-ui"
PLUGIN_DST="$HERMES_HOME/plugins/gh-kanban-bridge-ui"
if [ -d "$PLUGIN_SRC" ]; then
  if [ -d "$PLUGIN_DST" ]; then
    log "plugin dashboard gh-kanban-bridge déjà présent"
  else
    log "copie du plugin dashboard gh-kanban-bridge vers $PLUGIN_DST"
    mkdir -p "$HERMES_HOME/plugins"
    cp -r "$PLUGIN_SRC" "$PLUGIN_DST"
  fi
  if "$HERMES_BIN" plugins enable gh-kanban-bridge --no-allow-tool-override >/dev/null 2>&1; then
    log "plugin gh-kanban-bridge activé"
  else
    log "AVERTISSEMENT: activation du plugin gh-kanban-bridge échouée (à faire à la main)"
  fi
else
  log "AVERTISSEMENT: plugins/gh-kanban-bridge-ui introuvable (repo incomplet ?)"
fi

# ---------------------------------------------------------------- boutons go/no-go
# Plugin gh-triage-buttons : route les clics ✅ Go / ❌ No go (custom_id
# triage:go:<N> / triage:nogo:<N>) vers la session du thread. Vit dans le
# repo (plugins/gh-triage-buttons/) ; copié dans le profil gh-triage puis
# activé (plugins.enabled). Le restart du gateway gh-triage est laissé à
# l'opérateur (rappel en fin de script).
BTN_SRC="$SKILL_DIR/../../../plugins/gh-triage-buttons"
BTN_DST="$HERMES_HOME/profiles/$TRIAGE_PROFILE/plugins/gh-triage-buttons"
if [ -d "$BTN_SRC" ]; then
  if [ -d "$BTN_DST" ]; then
    log "plugin gh-triage-buttons déjà présent"
  else
    log "copie du plugin gh-triage-buttons vers $BTN_DST"
    mkdir -p "$HERMES_HOME/profiles/$TRIAGE_PROFILE/plugins"
    cp -r "$BTN_SRC" "$BTN_DST"
  fi
  if "$HERMES_BIN" -p "$TRIAGE_PROFILE" plugins enable gh-triage-buttons >/dev/null 2>&1; then
    log "plugin gh-triage-buttons activé"
  else
    log "AVERTISSEMENT: activation du plugin gh-triage-buttons échouée (à faire à la main)"
  fi
else
  log "AVERTISSEMENT: plugins/gh-triage-buttons introuvable (repo incomplet ?)"
fi

log "terminé. board=$KANBAN_BOARD repo=$GH_REPO assignee=$KANBAN_ASSIGNEE"
log "RAPPEL: redémarrer la dashboard pour voir l'onglet gh-kanban-bridge :"
log "  hermes dashboard --stop && hermes dashboard --host 0.0.0.0 --no-open"
log "RAPPEL: redémarrer le gateway gh-triage pour activer les boutons go/no-go :"
log "  systemctl --user restart hermes-gateway-gh-triage.service"
