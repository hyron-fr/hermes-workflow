---
type: component
status: draft
tags: [architecture, pipeline, escalation, configuration, environment, component]
issues: [4]
---

# Composant — `pj_escalate` (escalade des cartes bloquées)

## Rôle

Keeper déterministe (**0 LLM**) qui scanne les cartes kanban en attente d'une
décision humaine (`blocked` / `triage`, event `blocked` /
`block_loop_detected`) et poste **un** message dans le thread Discord de leur
issue. Dédupliqué par `(carte, dernier event de blocage)`, idempotent par
`(board, task_id)`. Le tick est **global** : `main()` itère les boards `pj-*`
(ou un seul via `--board` / `PJ_BOARD`).

Chaîne déterministe : `scan blocked/triage → dernier event de blocage → dédup
→ résolution (repo, issue) → état du ticket (gh) → thread → post`.

Voir le cadrage [[issue-4]] pour la frontière dépôt ↔ copie exécutée et le
pattern `_resolve_bin`.

## Contrat de configuration

Toute la configuration vient de l'**environnement** — aucune valeur, aucun
identifiant, aucun chemin de machine n'est codé dans le fichier. Le contrat est
lu une fois par `escalation_config(env=None)` (défaut : `os.environ`) ; un
`HOME` injecté déplace **tous** les défauts dérivés du répertoire personnel.

### Variables requises

Trois variables, contrôlées sur **présence ET non-vacuité** (une valeur `None`,
vide ou blanche sont indiscernables via `_text`). L'ordre de la liste
`REQUIRED_VARS` fixe laquelle est nommée en premier quand plusieurs manquent.

| variable | rôle |
|---|---|
| `PJ_ESCALATE_CHANNEL_ID` | canal des threads d'issue (et cible de repli quand une carte n'a pas de thread dédié) |
| `PJ_ESCALATE_USER_ID` | destinataire des décisions (`<@user_id>` dans le message) |
| `PJ_ESCALATE_GUILD_ID` | guilde Discord lue par le helper de threads |

### Variables optionnelles

Défauts **dérivés du répertoire personnel** (`home = $HOME`), sauf `ORG` :

| variable | défaut |
|---|---|
| `PJ_ESCALATE_REPOS_ROOT` | `$HOME/pj-repos` (racine des clones dev) |
| `PJ_ESCALATE_STATE_DIR` | `$HOME/.hermes/state` (état de dédup, un fichier par board) |
| `PJ_ESCALATE_THREAD_HELPER` | `$HOME/.hermes/scripts/discord_thread.py` |
| `PJ_ESCALATE_ORG` | `hyron-fr` |
| `PJ_ESCALATE_GH_BIN` | *cas particulier, voir ci-dessous* |

`PJ_ESCALATE_GH_BIN` est le **seul** cas où « posée vide » est un état
**légitime**. Le port `gh` est un champ de configuration (injectable, testable)
avant d'être une variable d'environnement : si la variable est **absente** du
mapping, `gh_bin` vaut `GH_BIN` résolu à l'import par `_resolve_bin("gh",
"~/.local/bin/gh", "~/.hermes/bin/gh")` (PATH puis candidats **vérifiés**
`isfile` + `X_OK`, repli `""` si rien ne passe). Si elle est **définie**, sa
valeur est prise telle quelle — une valeur vide exprime « garde indisponible,
escalade bruyante » : l'avertissement part, le tick continue.

## Règle « une requise absente est bruyante »

Une variable requise **absente ou vide** refuse le tick **bruyamment** :
`ConfigError`, message sur la sortie d'erreur **nommant la variable**, code de
sortie `2`, **aucun envoi**, **aucune écriture d'état**. Jamais de repli
silencieux — une valeur vide n'est jamais un identifiant (mesuré :
`target=""` fait échouer le post, l'état n'avance pas, et le même message est
reposté à chaque tick, indéfiniment).

Le répertoire d'état est validé par une **sonde d'écriture**
(`validate_config` : `mkdir` + fichier créé puis retiré) **au tout début du
tick**, avant tout scan de board — sinon un `PermissionError` local n'arrive
qu'après que les boards précédents ont posté.

## Wrapper cron

`agents/pj-master/scripts/pj_escalate_all.sh` (versionné) lit les `PJ_ESCALATE_*`
du `.env` **du profil** (`$HOME/.hermes/profiles/pj-master/.env`, hors dépôt),
n'exporte **que** ce préfixe (les jetons et clés n'entrent pas dans le tick),
étend `PATH` avec `$HOME/.local/bin`, puis `exec python3` de la copie installée.
Sans suffixe de repo (le tick est global, contrairement aux wrappers
`pj_bridge_*` / `pj_graphwatch_*` / `pj_room_keeper_*`) — il ne pose donc **pas**
`PJ_BOARD` (le poser restreindrait le tick global à un seul board, en silence).

## Chemins de doute — quatre chemins, quatre avertissements

La garde d'état d'issue lit `gh issue view --json state` et décide, via la fonction
**pure** `escalation_allowed(state)` : `OPEN` → escalade, `CLOSED` → la carte est
marquée traitée sans post, **chaîne vide ou état inconnu → escalade quand même**
(un doute ne rend jamais une carte muette *par erreur*).

| chemin de doute | retour | avertissement |
|---|---|---|
| `gh` introuvable (`GH_BIN` vide) | `False` — on escalade | `gh introuvable … INDISPONIBLE` |
| retour non nul (`rc != 0`) | `False` — on escalade | `gh issue view rc=<n> … INDÉTERMINÉ` |
| exception du sous-processus | `False` — on escalade | `gh issue view a levé <Type> … INDÉTERMINÉ` |
| sortie illisible (ni `OPEN` ni `CLOSED`) | `False` — on escalade | `sortie '<x>' (ni OPEN ni CLOSED) … INDÉTERMINÉ` |

Règle « **quatre chemins de doute, quatre avertissements** » : les avertissements portent
des messages **distincts** parce que `_warn_once` déduplique **par message**. Réutiliser
la même chaîne rendrait muet le deuxième chemin du même tick — c'est exactement le défaut
d'origine (un unique appel de `_warn_once`, dans la branche `if not GH_BIN`). La dédup ne
joue donc qu'entre messages **identiques**, et deux chemins différents dans un même tick
produisent bien deux lignes. Les états **décidables** (`OPEN`, `CLOSED`) restent muets :
le nominal est bruyant uniquement quand il y a un doute.

Une exception ne **se propage jamais** : elle ferait tomber le tick entier, donc toutes
les cartes suivantes. Puits de l'avertissement : `print` → stdout → le fichier de sortie
du job de cron (`cron/output/<job_id>/*.md`).

## Points d'injection

Les entrées-sorties (kanban SQLite, `gh`, Discord, fichiers d'état) passent par
des points d'injection — `runner` (sous-processus), `poster` (envoi Discord),
`conn_factory` (base kanban) — défaut = implémentation réelle. Le tick complet
est ainsi exerçable sans réseau, sans exécutable réel et sur une base de test.
