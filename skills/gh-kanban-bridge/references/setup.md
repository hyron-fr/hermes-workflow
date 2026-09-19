# Setup : pont GitHub ↔ kanban + bot Discord gh-triage

Déploiement sur une nouvelle instance Hermes. **Une seule commande** câble
tout : helpers, profil, board, labels, crons. Idempotent — relancer ne
duplique rien.

## Prérequis

- Hermes Agent installé (`hermes` dans le PATH)
- `gh` CLI authentifié sur le repo cible (`gh auth login`)
- Un bot Discord créé et invité sur le serveur cible (token à mettre dans
  le `.env` du profil, voir §Secrets)

## Installation

```bash
bash <skill_dir>/scripts/setup.sh
```

Ce que fait `setup.sh` (dans l'ordre) :

1. Vérifie `gh auth status` (exit 1 si non authentifié)
2. Copie les 4 helpers `scripts/*.py` vers `${HERMES_WORKFLOW}/pipeline/`
3. Crée le profil `gh-triage` (si absent) + copie `gh_triage_poll.py` dans
   son dossier `scripts/`
4. Crée le board kanban (si absent)
5. Crée les labels GitHub `kanban` et `triage` (si absents)
6. Crée le cron `gh-kanban-bridge` (no-agent, `*/5`) si absent
7. Crée le cron `gh-triage-poll` (profil gh-triage, agent) si absent

Chaque étape est gardée par un test d'existence : relancer `setup.sh` ne
crée aucun doublon (mêmes crons, labels, board).

## Configuration (env, surchargeable)

| Variable | Défaut | Rôle |
|---|---|---|
| `GH_REPO` | hyron-fr/hermes-experiment | repo cible |
| `KANBAN_BOARD` | hermes-experiment | board kanban |
| `KANBAN_ASSIGNEE` | default | profil worker |
| `DISCORD_GUILD_ID` | ${DISCORD_ID} | serveur Discord |
| `DISCORD_CHANNEL_ID` | ${DISCORD_ID} | channel de triage |

Exemple :

```bash
GH_REPO=acme/prod KANBAN_BOARD=prod KANBAN_ASSIGNEE=worker \
  bash <skill_dir>/scripts/setup.sh
```

## Étapes manuelles restantes (hors setup.sh)

`setup.sh` ne gère PAS les secrets ni le gateway Discord — à faire à la main :

### Secrets du profil (`~/.hermes/profiles/gh-triage/.env`)

```
DISCORD_BOT_TOKEN=<token du bot>
DISCORD_FREE_RESPONSE_CHANNELS=<channel_id>     # pas de @mention requis
DISCORD_ALLOWED_USERS=<discord_user_id>          # OBLIGATOIRE (sinon silence)
```

Récupérer l'ID Discord de l'utilisateur : clic droit sur le pseudo →
"Copy User ID" (mode développeur activé).

```bash
chmod 600 ~/.hermes/profiles/gh-triage/.env
```

### Gateway du profil (bot Discord)

```bash
hermes -p gh-triage config set discord.allowed_guilds "[<guild_id>]"
hermes -p gh-triage config set discord.allowed_channels <channel_id>
hermes -p gh-triage gateway install      # service systemd user
journalctl --user -u hermes-gateway-gh-triage | grep "discord connected"
```

### Gateway principal (dispatcher kanban)

```bash
hermes gateway install                   # si pas déjà fait
hermes kanban --board <board-slug> list  # vérifier la visibilité
```

### Protocole du bot (SOUL.md)

Copier `references/SOUL-template.md` vers
`~/.hermes/profiles/gh-triage/SOUL.md` et adapter les IDs.

## Variables du pont (runtime)

| Variable | Défaut | Rôle |
|---|---|---|
| `GH_REPO` | hyron-fr/hermes-experiment | repo cible |
| `KANBAN_BOARD` | hermes-experiment | board kanban |
| `KANBAN_ASSIGNEE` | default | profil worker |
| `BOT_GRACE_SECONDS` | 600 | issue < N s réservée au bot |
| `DRY_RUN` | 0 | simulation sans écriture |
| `BRIDGE_VERBOSE` | 0 | loguer même les ticks sans action |

## Dashboard UI (onglet gh-kanban-bridge)

Le pont est aussi pilotable depuis la web dashboard Hermes via un plugin UI
(composant séparé de la skill, distribué par clone git). L'onglet expose
trois sections : CONFIG (les 6 variables du pont, persistées dans le `.env`
du profil — le token Discord n'est jamais lu ni renvoyé), ÉTAT (live via
`stats --json`), ACTIONS (pull/push/sync/new avec la sortie réelle).

### Installation

```bash
# 1. Cloner le plugin dans ~/.hermes/plugins/
git clone https://github.com/hyron-fr/hermes-experiment.git /tmp/he
cp -r /tmp/he/plugins/gh-kanban-bridge-ui ~/.hermes/plugins/

# 2. Activer le plugin (gate plugins.enabled)
hermes plugins enable gh-kanban-bridge --no-allow-tool-override

# 3. Redémarrer la dashboard (ou rescan)
hermes dashboard --stop
hermes dashboard --host 0.0.0.0 --no-open
#   ou, sans redémarrage :
curl http://127.0.0.1:9119/api/dashboard/plugins/rescan
```

`setup.sh` fait les étapes 1–2 automatiquement (copie du plugin depuis le
repo + enable) et rappelle le restart dashboard.

### Vérification (check curl)

La dashboard est derrière l'auth (basic/OAuth) : obtenir un cookie de session
puis tester les routes.

```bash
# 1. Login (provider basic) → cookie de session
curl -c /tmp/hc.txt -X POST http://127.0.0.1:9119/auth/password-login \
  -H "Content-Type: application/json" \
  -d '{"provider":"basic","username":"<user>","password":"<pass>","next":""}'

# 2. Config (6 champs, jamais le token)
curl -b /tmp/hc.txt http://127.0.0.1:9119/api/plugins/gh-kanban-bridge/config

# 3. État (cartes par statut + push/pull en attente)
curl -b /tmp/hc.txt http://127.0.0.1:9119/api/plugins/gh-kanban-bridge/state

# 4. Sync (déclenche le pont, sortie réelle)
curl -b /tmp/hc.txt -X POST http://127.0.0.1:9119/api/plugins/gh-kanban-bridge/sync
```

L'onglet apparaît dans la sidebar après `after:kanban` (path
`/gh-kanban-bridge`).

## Checklist de validation

1. `bash setup.sh` → exit 0, logs `[setup] terminé`
2. `hermes cron list` montre `gh-kanban-bridge` ET `hermes -p gh-triage cron
   list` montre `gh-triage-poll`
3. `gh label list --repo <owner>/<repo>` montre `kanban` ET `triage`
4. `hermes kanban boards list` montre le board (défaut `hermes-experiment`)
5. Relancer `setup.sh` → exit 0, AUCUN doublon (mêmes crons, labels, board)
6. `python3 gh_kanban_bridge.py sync` → tick muet (exit 0, stdout vide)
7. Issue de test → poll l'annonce → thread ouvert + label `triage`
8. Réponses dans le thread → synthèse structurée postée par le bot
9. "go" → carte `ready` (idempotency-key `gh-issue-<n>`) + label `kanban`
10. Dispatcher → worker → `done` → sync ferme l'issue avec le résumé
11. Diagramme dans le thread : bloc ```mermaid + PNG via mermaid_render.py
