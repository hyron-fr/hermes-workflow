#!/usr/bin/env bash
# Cron pj-escalate : remonte les blocages de cartes (dev/doc/test) vers le thread
# Discord de l'issue. Déterministe (0 LLM), idempotent par (carte, event).
#
# Modèle : `pj_repo_watch.sh` (PATH puis exec de la copie installée du profil).
# `pj_escalate` est GLOBAL — un seul cron, `main()` itère les boards `pj-*` — donc,
# contrairement aux `pj_bridge_*`/`pj_graphwatch_*`/`pj_room_keeper_*`, ce wrapper
# ne porte aucun suffixe de repo et ne pose PAS `PJ_BOARD` : le poser
# restreindrait le tick global à un seul board, en silence.
#
# Ce que le wrapper versionné porte, et pourquoi — trois écarts assumés avec le
# wrapper installé (qui, lui, exécute `exec python3 <chemin absolu>` sans PATH) :
#
# 1. `export PATH` : le PATH d'un cron ne contient pas `~/.local/bin`, or c'est là
#    que vit `gh`. Le wrapper reproduit l'environnement pour lequel l'outil a été
#    écrit, au lieu de compter sur un candidat de repli.
# 2. Les 3 variables REQUISES du contrat (`PJ_ESCALATE_CHANNEL_ID`,
#    `PJ_ESCALATE_USER_ID`, `PJ_ESCALATE_GUILD_ID`) sont exportées vers le tick,
#    lues dans le `.env` du profil — le foyer documenté des secrets et des
#    identifiants d'environnement (`README.md` §3, `.env.example`), hors dépôt et
#    jamais versionné. Elles ne peuvent PAS être écrites en clair ici : ce dépôt
#    est public, et des identifiants Discord (snowflakes 17-19 chiffres) y sont
#    interdits (CONTRIBUTING §Assainissement). Seuls les noms `PJ_ESCALATE_*`
#    sont exportés — le reste du `.env` (jetons, clés) n'entre pas dans le tick.
# 3. Aucun chemin de machine : `$HOME` partout.
#
# Un tick à qui il manque une variable requise ne part pas muet : `escalation_config`
# lève `ConfigError`, le processus sort en rc=2 et nomme la variable sur la sortie
# d'erreur (lue dans le fichier de sortie du cron).
set -u

export PATH="$HOME/.local/bin:$PATH"

PROFILE_ENV="$HOME/.hermes/profiles/pj-master/.env"
if [ -f "$PROFILE_ENV" ]; then
    while IFS='=' read -r name value; do
        value="${value%$'\r'}"
        case "$value" in
            \"*\") value="${value#\"}"; value="${value%\"}" ;;
            \'*\') value="${value#\'}"; value="${value%\'}" ;;
        esac
        case "$name" in
            PJ_ESCALATE_*) export "$name=$value" ;;
        esac
    done < "$PROFILE_ENV"
fi

exec python3 "$HOME/.hermes/profiles/pj-master/scripts/pj_escalate.py" "$@"
