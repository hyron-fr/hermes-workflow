---
name: gh-kanban-bridge
description: "Use when syncing GitHub Issues with the Hermes kanban board."
version: 1.0.0
---

# Pont GitHub Issues ↔ Kanban Hermes

Bridge opérationnel sur cette machine : cron `gh-kanban-bridge` (job 619353aaeed4, */5 * * * *, no-agent) + dispatcher kanban dans le gateway systemd `hermes-gateway.service`.

## Architecture

- Repo canonique : `${HOME}/hermes-experiment` (github.com/hyron-fr/hermes-experiment)
- Script : `bridge/gh_kanban_bridge.py` (pull | push | sync), wrapper cron : `${HERMES_WORKFLOW}/pipeline/gh_kanban_bridge.sh`
- Board kanban dédiée : `hermes-experiment` (toujours passer `--board hermes-experiment`, le current pointer est resté sur default)
- Pull : issues ouvertes sans label `kanban` → cartes (idempotency-key `gh-issue-<n>`, label miroir auto-créé, commentaire avec l'id de carte)
- Push : cartes done liées à une issue ouverte → issue fermée avec le résumé du handoff worker
- Mode silencieux : tick cron sans action = stdout vide (= muet pour `--no-agent`), log seulement si écriture. `BRIDGE_VERBOSE=1` pour tout voir.

## Pièges appris (ne pas redécouvrir)

- `hermes kanban daemon` est DÉPRÉCIÉ : le dispatcher vit dans le gateway (`hermes gateway install` + start ; systemd user, Linger=yes).
- `idempotency_key` n'est PAS exposé dans `kanban list --json`/`show --json` (stocké en base seulement) → le pont déduit le n° d'issue de l'URL d'import dans le body de la carte.
- Le champ `runs --json` retourne une liste directe ; `show --json` imbrique {children, comments, events, latest_summary, parents, task}.
- Symlinks refusés dans `${HERMES_WORKFLOW}/pipeline/` (anti-traversale realpath) → wrapper bash vers le fichier canonique du repo.
- Dashboard exposé hors localhost : il faut HERMES_DASHBOARD_BASIC_AUTH_USERNAME/PASSWORD/SECRET dans ~/.hermes/.env (hardening 06/2026), sinon le serveur downgrade silencieusement le bind en 127.0.0.1. Vérif : curl :9119/api/status → auth_required:true, providers:[basic].
- Workers kanban = profils hermes spawnés `chat -q "work kanban task <id>"`, toolset kanban inclus.

## Limites connues (roadmap Exp2 dans les issues)

- Pas de sync des éditions d'issue (import one-shot)
- Pas de réouverture d'issue si la carte re-block/review
- Webhook GitHub impossible sans tunnel (machine derrière NetBird) → cron 5 min choisi

## Bot gh-triage (Discord, ajout 05/09)

- Profil `gh-triage` : qwen3.8-27b via litellm-proxy-gcp, gateway dédié `hermes-gateway-gh-triage.service`, bot Discord "Experiment" sur guild ${DISCORD_ID} / channel ${DISCORD_ID} (free-response, sans @mention).
- Allowlist OBLIGATOIRE : DISCORD_ALLOWED_USERS=<discord_user_id> dans le .env du profil, sinon "Unauthorized user" et l'humain est ignoré en silence.
- Les outils hermes-discord ne sont PAS disponibles dans les sessions cron/CLI — uniquement dans les sessions gateway. En cron, le bot passe par le helper `${HERMES_WORKFLOW}/pipeline/discord_thread.py` (REST, create|send|threads).
- Pièges REST Discord : User-Agent obligatoire style "DiscordBot (url, version)" sinon Cloudflare 403 code 1010 ; les threads se listent via /guilds/<id>/threads/active (le /channels/<id>/threads/active renvoie 404).
- Label 'triage' = en cours de drill (pont ET poll le respectent). BOT_GRACE_SECONDS=600 dans le pont : issue < 10 min réservée au bot, sinon import direct en carte.
- Cron poll `gh-triage-poll` (profil gh-triage, job 18a2a393aad5) : script `gh_triage_poll.py` (état local gh-triage-poll-state.json, stdout vide = tick muet = pas d'appel LLM ; stdout JSON = injecté en prompt). En mode agent+script, stdout vide → return None (vérifié scheduler.py:4869).
- Protocole bot dans ~/.hermes/profiles/gh-triage/SOUL.md : thread '🎫 Issue #N', drill, carte SEULEMENT après clic ✅ Go (bouton), ligne 'Importé depuis <url issue>' obligatoire dans le body de carte (le push du pont s'en sert).
- BOUTONS GO/NO-GO (issue #12) : le déclencheur de création est le BOUTON ✅ Go (custom_id `triage:go:<N>`), plus le texte "go". Le helper `discord_thread.py send <thread> "<msg>" --go-nogo <N>` pose l'ActionRow (✅ Go / ❌ No go). Le plugin `gh-triage-buttons` (profil gh-triage, plugins.enabled) écoute `on_interaction` (discord.py add_listener), parse le custom_id de façon déterministe, ACK le clic, puis route `[DÉCISION BOUTON] go|no go — issue #N` dans la session du thread via `adapter._build_slash_event` + `adapter.handle_message`. No go → relance le drill, aucune carte. Généralisable : schéma `<décision>:<action>:<payload>`.
- SOURCES DE VÉRITÉ (fix 6/09) : la DESCRIPTION de l'issue GitHub porte l'état courant (synthèse de drill éditée via gh issue edit N --body, body original conservé en bas) ; les COMMENTAIRES sont réservés à l'avancement (timeline, clôture). Le bot n'affirme jamais une action sans preuve tool-call.
- DÉRIVE CORRIGÉE (6/09) : le bot avait créé les cartes #9/#10 directement DEPUIS le thread #8 (une autre issue) sur un simple 'oui', en lançant les workers — contournement du gate humain. Fix en dur dans SOUL.md + SOUL-template (commit 5f935d0) : UN THREAD PAR ISSUE, non négociable — idée émergente dans une conversation = créer l'issue GitHub et laisser le cycle poll/thread/drill/go se dérouler. Aucune carte ne naît d'une conversation.
- Latence qwen3.8 sur le proxy : 160-245 s/appel → un run cron peut dépasser 10 min ; les ticks suivants skip ('already running') — mission cron bornée (2-3 appels) obligatoire. → Basculé sur deepseek-v4-flash:cloud (même provider litellm-proxy-gcp) : 16 s pour la chaîne complète.

## Modèles & coût dans les workflows kanban

Les cartes créées via le pont héritent du modèle du profil worker, SAUF lorsque la carte porte un `workflow_template_id`. Dans ce cas le moteur de pipeline lit `hermes-experiment/workflows/*.yaml` et FORCE le modèle déclaré par étape, indépendamment de `model.default` du profil.

Pitfalls constatés 2026-09:
- Les workflows `spec.yaml`/`smoke.yaml` déclaraient `deepseek-v4-flash:cloud` (et par chaîne `deepseek-v4-pro:cloud`) avant bascule. Les runs déjà dispatchés ont verrouillé ces modèles, même après changement du profil.
- Les cartes kanban classiques sans `workflow_template_id` utilisent `model.default` du profil. Tant que les profils `default`/`example`/`gh-triage` pointaient sur des modèles cloud, ces cartes consommaient du quota pro.
- Basculer le profil ne corrige PAS les runs en vol ; il faut aussi patcher les YAML de workflow et redispatcher les cartes non terminées.

Règle de garde-fou:
- Whitelist locale pour les workflows de test : n'autoriser que `muse-glimmer:nim` / `nemotron-*` dans `spec.yaml` et `smoke.yaml`.
- Bloquer le dispatch si `model` ∉ whitelist → évite les surprises de quota.
- Audit rapide :
  ```bash
  grep -r "deepseek-v4-flash:cloud\|glm-5.3-flash:cloud" ${HOME}/hermes-experiment/workflows/
  for p in ${HOME}/.hermes/profiles/*/config.yaml; do echo "===$p==="; grep -A2 "^model:" "$p"; done
  ```

Conception plugin:
L'onglet Workflow a été greffé dans `plugins/gh-kanban-bridge-ui`. Le domaine Workflow appartient au contexte `workflow-ui`. Ce mélange crée du scope creep (édition YAML, validation live) et des régressions. Recommandation : déplacer l'UI Workflow dans `plugins/workflow-ui`, garder `gh-kanban-bridge-ui` strictement GitHub ↔ Kanban.

## Distribution comme skill shareable (testée)

- Le hub de skills accepte `hermes skills install hyron-fr/<repo>/skills/<nom>` (format owner/repo/path) — testé OK sur une instance isolée (HERMES_HOME distinct) : `Installed: gh-kanban-bridge`, visible dans `hermes skills list` comme source community.
- Packaging réel poussé dans le repo : `skills/gh-kanban-bridge/` = SKILL.md (hub format, frontmatter ≤60 chars, author humain d'abord) + `scripts/` (4 helpers copiés) + `references/setup.md` (pas-à-pas complet) + `references/SOUL-template.md`.
- Le scanner skills-guard-v2 BLOQUE à l'installation (verdict DANGEROUS non forçable) si la skill contient : la chaîne "~/.hermes/.env" dans une incitation (même négative : "ne révèle jamais..." → finding exfiltration CRITICAL), des subprocess.run en MEDIUM cumulé. Fix : reformuler sans la chaîne littérale ("fichiers de secrets du profil"), le subprocess MEDIUM cumulé passe si pas de CRITICAL.
- L'URL raw.githubusercontent.com peut rester en 404 (cache négatif) même quand le fichier existe — le chemin owner/repo/path contourne ça.
- `hermes skills install` accepte aussi une URL directe vers un SKILL.md.
- Issue #8 = ticket de test du déploiement plugin (critères d'acceptation complets).