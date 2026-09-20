---
type: component
status: draft
tags: [architecture, pipeline, escalation, configuration, environment, publication, component]
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

Voir le cadrage [[issue-4]] pour la frontière dépôt ↔ copie exécutée, le
pattern `_resolve_bin`, et ci-dessous la chaîne de publication que
`pipeline/pj_publish.py` ferme.

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

## Chaîne de publication — `pipeline/pj_publish.py`

La copie versionnée ne s'exécute jamais directement : le cron exécute la
**copie installée** (`~/.hermes/profiles/pj-master/scripts/pj_escalate.py`),
un fichier distinct que rien ne resynchronise. `pipeline/pj_publish.py`
referme cette frontière dépôt ↔ copie exécutée : il **compare** les deux
copies, **contrôle les `export` du wrapper**, et **refuse de basculer** tant
que l'identité et le contrat d'exports ne sont pas établis. L'écart cesse
d'être une découverte tardive ; il devient un contrôle de livraison.

### L'identité se mesure sur le contenu tel qu'il s'exécute

La copie versionnée est **assainie** (contrat de configuration plus haut :
aucun identifiant, aucun chemin de machine). L'identité ne peut donc pas
porter sur une comparaison de sources brutes qui ignorerait l'environnement
: une copie byte-identique dont le wrapper ne fournit pas les variables
requises est une **livraison morte** — le tick sortirait en `rc=2`
(`ConfigError`), bruyamment, et plus aucune escalade ne partirait. Le
contrôle d'identité est donc **le contenu de la copie + les `export` du
wrapper** : même contenu, wrapper fautif → l'identité n'est pas établie.

### Le contrôle des exports reconnaît un motif, pas des littéraux

Le wrapper versionné `pj_escalate_all.sh` n'écrit pas
`export PJ_ESCALATE_CHANNEL_ID=…` trois fois : il lit le `.env` du profil et
exporte via `case "$name" in PJ_ESCALATE_*) export "$name=$value"`. Le
contrôle reconnaît donc :

- les `export` **littéraux** (`export VAR`, `export VAR=valeur`, export
  multi-noms) ;
- une couverture par **motif** (`export PJ_ESCALATE_*`, ou un `case` dont le
  motif glob exporte `"$name=$value"`).

Un contrôle qui n'accepterait que la forme littérale **refuserait le
wrapper du dépôt lui-même**, le mode `--publish` resterait fermé et la
slice serait **inerte** (le geste humain n'aboutirait jamais). Une
**affectation non exportée** (`VAR=…`) ne compte toujours pas : c'est
précisément le défaut que le contrôle existe pour voir. Le banc de tests
épinge ce cas.

### Le geste de publication — l'ordre est un garde-fou

Le wrapper installé **n'exporte rien** aujourd'hui (un `exec python3
<chemin>` sec). Basculer la copie assainie **avant** d'ajouter les
`export` tue le tick : `escalation_config` lève `ConfigError`, le processus
sort en `rc=2` et plus aucune escalade ne part — silencieusement, puisque
personne ne lit le fichier de sortie du cron. L'ordre ci-dessous n'est pas
une commodité ; l'inverser rend le composant muet :

1. **contrôler** — `python3 pipeline/pj_publish.py --check --wrapper
   <wrapper installé>` : constate l'écart **et** l'absence d'`export`
   (l'outil nomme la variable manquante et le wrapper fautif) ;
2. **l'humain** ajoute les `export` des variables requises au wrapper
   (fichier **hors dépôt** — le worker n'y écrit pas) ;
3. **re-contrôler** — le même `--check` doit maintenant voir les variables
   : c'est la preuve que la variable est **vue du tick**, pas seulement
   écrite ;
4. **publier** — `--publish --target ~/.hermes/profiles/pj-master/scripts/pj_escalate.py`
   (la copie que le cron exécute) ; ajouter `--target ~/.hermes/scripts/pj_escalate.py`
   si la seconde copie installée doit suivre ;
5. **vérifier par exécution** — un tick du wrapper doit rester **muet**
   (`rc=0`, 0 escalade parasite) : un tick qui parle pour une carte déjà
   traitée signale que la bascule a atterri au mauvais endroit.

### Codes de sortie — priorité `2 > 1 > 0`

| code | signification |
|---|---|
| `0` | conforme — identité établie, exports conformes |
| `1` | **écart livré** : divergence entre copies, export manquant, fichier de code sous le seuil (mode `--coverage`) |
| `2` | **erreur d'exécution** : cible/source/wrapper absente ou illisible, périmètre vide, rapport muet, argument manquant |

`2` est réservé à ce qui **empêche de conclure** : « je n'ai pas pu
vérifier » n'est jamais un succès (`0`), et ce n'est pas non plus un écart
constaté (`1`). Le contrôle des exports vient **en premier** dans
`--check` : inutile de décrire une identité que le wrapper ne rendrait pas
exécutable. Le mode `--check` est le **défaut** et est **strictement** en
lecture seule (aucune écriture, aucun `mkdir`, aucun fichier temporaire) ;
`--publish` exige un `--target` explicite, refuse de basculer si le
wrapper est fautif, est **idempotent** (une cible déjà identique n'est pas
réécrite), et **re-vérifie l'identité après écriture** — jamais de
« publié » sur une écriture non relue. Les diagnostics vont sur stdout ;
les refus sont **aussi** écrits sur stderr, pour que le « bruyant » ne
dépende pas du flux qu'un lecteur choisit. Mode d'emploi complet :
`pipeline/README.md`, section « Publication et contrôle d'identité ».

**État mesuré aujourd'hui (avant le geste humain)** : `--check` sur la
copie installée rend `rc=1` — 544 lignes divergentes, copie versionnée
`87c3463b` (574 l.) contre copie installée `0ed3264c` (355 l.). Le wrapper
versionné, lui, **passe** le contrôle des exports. Le geste d'étape 2-5
reste à l'humain (hors dépôt) ; sa trace est le commentaire de la carte de
convergence.

## Points d'injection

Les entrées-sorties (kanban SQLite, `gh`, Discord, fichiers d'état) passent par
des points d'injection — `runner` (sous-processus), `poster` (envoi Discord),
`conn_factory` (base kanban) — défaut = implémentation réelle. Le tick complet
est ainsi exerçable sans réseau, sans exécutable réel et sur une base de test.
