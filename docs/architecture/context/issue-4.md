---
type: context
status: draft
tags: [architecture, pipeline, escalation, issue-state-guard, binary-resolution, cadrage]
issues: [4]
---

# Cadrage architectural — issue #4 « Versionner pj_escalate.py (pipeline/) »

## Positionnement (cadre exact)

L'issue #4 a **trois volets** qui convergent vers un même objet — l'outil
d'escalade `pj_escalate.py` — et une même frontière — **la frontière
dépôt ↔ copie exécutée**.

1. **Versionnement** : `pj_escalate.py` est le **seul** outil du pipeline absent
   du dépôt. Il n'existe qu'en **deux copies hors dépôt, byte-identiques** par
   non-recopie depuis 11:13 (`~/.hermes/scripts/pj_escalate.py`, inode 45219873,
   et `~/.hermes/profiles/pj-master/scripts/pj_escalate.py`, inode 49690564 —
   fichiers distincts, pas un hardlink), déclenché par un cron `no_agent` toutes
   les 3 minutes. La skill `blocked-card-human-escalation.md:66` (non versionnée)
   désigne `~/.hermes/scripts/pj_escalate.py` comme « là où vit le correctif »,
   alors que **seul** le chemin profil est exécuté par le cron ; la bascule de
   publication doit donc dire **laquelle** des deux copies est écrasée, sinon la
   prochaine remise à jour régénère la dérive. Tous ses voisins (`pj_card_lint`,
   `pj_graphwatch`, `pj_pipeline_deployer`, `pj_repo_watch`, `pj_room`,
   `pj_room_keeper`, `pj_slices_lint`) ont une copie dans `pipeline/` ou
   `agents/pj-master/`. Il n'est donc **ni relisible, ni testable, ni
   corrigeable par PR** — un trou de gouvernance, pas une question de style.
2. **Garde-fou d'état d'issue** : l'outil poste « Décision attendue » dans le
   thread Discord d'une issue **sans jamais lire son état**. Une carte rattachée
   à un ticket **CLOSED** est donc escaladée quand même — ce qui s'est produit
   sur l'issue #1 (fermée le 19/09, deux cartes créées après ont été remontées
   dans son fil).
3. **Résolution de binaire hors PATH** : le garde-fou naturel
   (`subprocess.run(["gh", …])`) écrit naïvement est **inerte sous cron** — le
   PATH d'un cron ne contient pas `~/.local/bin`, donc `shutil.which("gh")` est
   `None` et l'appel lève `FileNotFoundError`. Un garde-fou qui paraît actif en
   session interactive ne s'exécute jamais en production.

   *Nuance mesurée (@pj-master, 20/09)* : le candidat **vérifié**
   (`_resolve_bin` retombe sur `~/.local/bin/gh` via `isfile`+`X_OK`) fait que la
   garde est **déjà vivante sous PATH de cron** — `env -i HOME=/home/elix PATH=/usr/bin:/bin python3`
   résout quand même `GH_BIN="/home/elix/.local/bin/gh"`. L'inertie réelle ne
   vient pas du wrapper mais du **contrat de repli `"gh"` nu** (voir le seam
   `_resolve_bin` plus bas).

Le point de fond est le **premier** volet : les deux correctifs (2 et 3) ne
valent que s'ils sont **versionnés**. Une copie corrigée qui reste hors dépôt
reproduit exactement le défaut de dérive qu'ils prétendent corriger.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières externes traversées)

- **Kanban Hermes** — source de vérité lue : table SQLite locale
  (`~/.hermes/kanban/boards/<board>/kanban.db`). L'outil lit les cartes en
  statut `blocked`/`triage` et leurs événements `blocked`/`block_loop_detected`.
- **GitHub** — *nouvelle* lecture d'état (avant : aucun accès) : `gh issue view
  --json state` sur le ticket ciblé. Port `gh`, déjà franchi par
  `gh_kanban_bridge.py` (même pattern `_resolve_bin`).
- **Discord** — sortie : un message par carte, posté dans le thread de l'issue
  via le helper `discord_thread.py` (résolution `(repo, issue) → thread_id`).
- **Filesystem** — fichier d'état de dédup par board
  (`~/.hermes/state/pj_escalate_<board>.json`), indexé par
  `(task_id, dernier event de blocage)`.
- **Environnement cron** — frontière *implicite* et *traîtresse* : le PATH
  restreint d'un cron (sans `~/.local/bin`) est ce qui rend le garde-fou inerte.
  C'est une frontière d'exécution, pas de code, et c'est elle que le correctif
  n° 3 traverse.

### Fonctionnel (capacité exercée)

L'outil remplit **une seule capacité** : *escalader vers l'humain* les cartes
qui attendent une décision. Chaîne déterministe :

`scan cartes blocked/triage → dernier event de blocage → dédup par
(task, event) → résolution (repo, issue) → [état d'issue] → thread → post`.

L'issue #4 **ajoute** une étape de décision à cette chaîne — lire l'état du
ticket avant de poster — et **change** la nature de la dédup : une carte dont
l'issue est CLOSED est **marquée traitée sans post** (l'arbitrage revient à
l'orchestrateur `pj-master`, pas à l'humain). Le contenu du message, la liste
des états escaladables et la dédup par `(carte, event)` restent **inchangés**.

### Code (composants, ports, adapters)

- **Composant nouveau à versionner** : `pipeline/pj_escalate.py` (copie
  canonique, actuellement absente du dépôt). Fonctions : `resolve_issue`,
  `thread_index`, `last_block_event`, `build_message`, `post`, `run`, `main`.
- **Core pur à extraire (hexagonal)** — `escalation_allowed(state: str) -> bool` :
  la **décision** d'escalader, prise sur l'état du ticket en entrée. C'est le
  contrat exigé par l'issue (un test qui lirait le texte source est refusé) ; il
  n'existe **pas encore** dans la copie de profil, qui fait l'appel réseau
  *inline* dans `issue_is_closed()`.
- **Ports** : `gh` (lecture d'état), Discord (post), kanban (SQLite), filesystem
  (état JSON). Tous franchis par `subprocess` / `sqlite3`.

**Inventaire des littéraux à dé-hardcoder** (comptage AST @pj-dev, vérifié
20/09) : **8 littéraux + `KANBAN_ROOT` non paramétré**, répartis en 4 « ID »
(`CHANNEL_ID` l.41, `PJ_MASTER_USER` l.42, `GUILD_ID` l.43, `REPOS_ROOT` l.44),
les chemins (`STATE_DIR` l.45, `THREAD_HELPER` l.46 — double : chemin **et** nom
de fichier `discord_thread.py`), et les littéraux de **convention** :
`hyron-fr/{repo}` (l.249, org GitHub en f-string), la liste des 4 repos de
`known_repos()` (l.61), le préfixe `pj-` (l.107/341). Deux de ces littéraux
décident *à eux seuls* de la sémantique : la liste l.61 définit ce que
`resolve_issue` considère comme `UNKNOWN`, et `hyron-fr` rend l'outil
non-réutilisable hors org. Le mapping `constante → var d'env` doit être figé dans
la spec (préfixe `PJ_ESCALATE_`, nom du destinataire `USER_ID` vs `MASTER_USER`,
statut de `PJ_ESCALATE_GH_BIN` et de `PJ_ESCALATE_ORG`), sinon le `--require-env`
de publication et le RED ne peuvent pas désigner la même cible.

**Nomenclature des variables d'env (corrigée 20/09)** : le préfixe `PJ_ESCALATE_`
est utilisé **de façon cohérente** dans le draft (`CHANNEL_ID`, `USER_ID`,
`GUILD_ID`, `STATE_DIR`, `REPOS_ROOT`, `THREAD_HELPER` — 6 occurrences) ; les
occurrences `DISCORD_CHANNEL_ID` et `CHANNEL_ID`-sans-préfixe sont des
**sous-chaînes** de `PJ_ESCALATE_CHANNEL_ID` ou la **variable Python l.41** citée
en verbatim comme contre-exemple (`os.environ[...]` sans `export`), pas une dérive.
Ce qui reste réel : le mapping `constante Python → var d'env` doit être écrit
**une fois** dans le corps livré, et `pj_publish --require-env` / le RED de
`test-1` / le GREEN de `dev-1` doivent lire **la même liste**. `PJ_ESCALATE_GH_BIN`
est **0 occurrence** dans le draft — mais `_resolve_bin` porte **deux** candidats
(`~/.local/bin/gh`, `~/.hermes/bin/gh`) pour **un seul** seam ; la valeur résolue
se rattache à `escalation_config` (7ᵉ champ `gh_bin` injectable, testable), pas à
une variable d'env que l'AC ratifiée ne nomme pas.

**Arbitrages rendus (board #338/#340/#341, 20/09)** : `PJ_ESCALATE_ORG`
**optionnel, défaut `hyron-fr` documenté** (patron `GH_REPO` déjà versionné dans
`gh_kanban_bridge.py:39` ; le rendre REQUIS ferait échouer le wrapper en place au
premier tick) ; préfixe `pj-` **figé** (paramétrer un préfixe de board est une
variable sans emploi). `KANBAN_ROOT` n'est **pas** une variable d'env à ajouter :
le banc le neutralise par `monkeypatch` (`m.KANBAN_ROOT = Path("/tmp/fake-root")`)
sans board réel ni variable — demander une env pour ce que le monkeypatch fait
proprement serait de la surface d'API gratuite ;
validation = **présence et non-vacuité**, une fois, en contrôle d'**écriture**
(`mkdir`+sonde), pas de lecture — l'échec au niveau module (`KeyError` sur un ID
avant tout `main()`) est gratuit, mais `STATE_DIR` échoue par board après que
A..D ont posté.
- **Adapters** : `_resolve_bin(name, *candidates)` — `shutil.which()` puis
  candidats **vérifiés** (`isfile` + `X_OK`), pattern **déjà présent** dans le
  dépôt (`gh_kanban_bridge.py:50`) et que le correctif n° 3 doit **réutiliser**,
  pas réinventer. **Seam tranché par la mesure (@pj-test) — les deux replis ont
  des profils de sûreté OPPOSÉS** : le repli `""` (contrat `pj_escalate`) rend
  `GH_BIN` falsy → `_warn_once` part → **échec ouvert visible** ; le repli `name`
  (contrat `gh_kanban_bridge.py:60`) rend `GH_BIN` truthy → le
  `FileNotFoundError` du `subprocess.run` est avalé par le `except Exception` de
  `issue_is_closed` → **échec ouvert silencieux**, garde inerte et muette. Le
  docstring de la copie live (l.210-216) qui prescrit « réutiliser
  `gh_kanban_bridge._resolve_bin` … laissera remonter une erreur claire » est
  donc **faux dans ce point d'appel** : c'est précisément ce `except` qui mange
  l'erreur. Contrat à pin : repli `""` **et** l'invariant « indéterminé →
  escalade » doit produire `_warn_once` **visible** — le test asserte
  l'avertissement, pas seulement le `False`, et n'importe **pas**
  `gh_kanban_bridge._resolve_bin`.

## Lecture SDD (spec-driven)

La spec (le body de l'issue #4) est la source de vérité ; elle prescrit
**explicitement** que la décision doit vivre dans une **fonction pure** prenant
l'état du ticket en entrée (`escalation_allowed(state: str)` « ou l'équivalent »),
appelée directement par la suite de test, le chemin réseau restant **hors du
test**. Ce cadrage ne décrit que ce qui existe (la copie de profil, ses voisins
versionnés, le pattern `_resolve_bin` du pont) ; il ne spécule pas sur la forme
finale du refactor.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context** : *Escalade / coordination* — un **keeper déterministe de
  supervision** (0 LLM), distinct des quatre contextes métier (Admission, Graphe
  de spec, Développement, Livraison) décrits pour l'issue #1. Il observe le board
  et ne fait que réveiller l'humain ; il ne crée ni n'achève aucun travail.
- **Agrégat** : la **carte bloquée + son dernier event de blocage** ; l'invariant
  d'idempotence est le couple `(task_id, event_id)` stocké dans l'état de dédup
  — c'est lui qui garantit « une seule publication par blocage ».
- **Value object** : l'**état du ticket**, **tri-état** `OPEN` / `CLOSED` /
  `UNKNOWN` (rc≠0, exception, sortie illisible), consommé par
  `escalation_allowed(state)`. C'est la valeur que l'issue demande de rendre
  explicite et décidable — `UNKNOWN` est le troisième état que la copie live
  écrase en `False` indistinct.
- **Domain events** : `blocked`, `block_loop_detected` (kinds de `task_events`),
  qui pilotent le déclenchement ; l'état d'issue `CLOSED` est un *signal* externe
  (GitHub), pas un event du board.

## Lecture TDD (contrats testables)

Les quatre scénarios Gherkin de l'issue doivent être **automatisés**, et la
contrainte de conception est structurante : **le test ne doit pas lire le texte
source** (règle CONTRIBUTING), donc la décision vit dans une fonction pure.

Contrats à verrouiller :

- `escalation_allowed(state: str) -> bool` — **le contrat central, pur** : nom
  (OPEN → `True`), limite (CLOSED → `False`), erreur (état indéterminé/invalide →
  `True`, jamais de silence par erreur). **Contrat ratifié (GO humain 13:42Z,
  corps l.128-144)** : `OPEN` → vrai, `CLOSED` → faux, **chaîne vide ou inconnue
  → vrai** (un doute escalade). `issue_is_closed` est une **tri-état déguisée en
  booléen** : `OPEN`/`CLOSED` sont muets *et corrects*, les **trois** chemins de
  doute (`gh` introuvable, `rc≠0`, exception) **avertissent chacun nommément** sur
  la sortie standard, aucun n'étant rendu muet par la dédup. Le warning est émis
  **par l'appelant**, jamais par `issue_is_closed` lui-même ; le RED doit rendre
  `escalation_allowed(UNKNOWN) == True` **avec** un avertissement, et
  `escalation_allowed(OPEN) == True` **sans** avertissement — c'est cette **paire
  d'effets de bord** qui discrimine une vraie tri-état, pas la seule assertion
  sur le retour (une impl 2-états `s != "CLOSED"` passerait `UNKNOWN == True`).
- `_resolve_bin(name, *candidates)` — déterministe sur l'environnement : résout
  par `shutil.which` puis candidats **vérifiés** `isfile`+`X_OK`, jamais de chemin
  en dur ; si aucun candidat ne passe, retour **`""`** (l'appelant décide), **pas
  le nom nu** — le nom nu rend `GH_BIN` truthy et tue l'avertissement, le `""`
  l'émet (contrat ratifié, corps l.79-83).
- Le **comportement observable** de `run()` (post / pas de post / avertissement
  bruyant) reste testable par injection de l'état (la fonction pure) sans toucher
  au réseau.

## Lecture hexagonale (le core reste pur)

Le **core pur** est l'ensemble des fonctions décisionnelles déterministes :
`escalation_allowed(state)` (nouvelle) et `resolve_issue` (déjà déterministe sur
les données SQLite). Elles ne touchent **ni** réseau **ni** filesystem **ni**
horloge. Les entrées/sorties (`gh`, Discord, kanban, état JSON) passent par des
**ports** invoqués dans des **adapters** (`subprocess`, `sqlite3`). La règle
d'invariant de ce projet vaut ici **doublement** : le garde-fou d'état d'issue
doit être **dans le core** (une fonction pure sur l'état), et le chemin réseau
(`gh issue view`) doit rester **dans un adapter** — c'est précisément ce que la
copie de profil actuelle (appel réseau inline dans `issue_is_closed`) ne respecte
pas encore.

## Composants impactés par l'issue #4

La frontière dépôt ↔ copie exécutée traverse **trois** artefacts, pas un seul —
mesuré le 20/09 : le `.py` **et** son wrapper `.sh` **et** l'entrée de cron sont
tous trois hors dépôt et tous trois portent des chemins en dur.

- `pipeline/pj_escalate.py` — **créé** (copie canonique dé-hardcodée + extraction
  de la fonction pure `escalation_allowed`). `pipeline/` est le foyer canonique
  prescrit par l'issue : le seul geste de déploiement documenté (`README.md` §4)
  est `cp pipeline/*.py ~/.hermes/profiles/pj-master/scripts/`, et `grep -c 'cp bridge' README.md`
  → 0 — un canonique posé en `bridge/` seul ne serait recopié par rien et le cron
  `*/3 min` continuerait d'exécuter la copie live. Les tests qui pointent
  `bridge/` (9) testent le **même byte** que `pipeline/` pour les outils partagés ;
  le contre-exemple `pj_graphwatch.py` (`bridge/` 241 l. périmées vs `pipeline/`
  474 l.) montre le coût de la duplication dès qu'elle dérive — c'est la raison
  de **ne pas** ajouter une 2ᵉ copie en `bridge/` ;
- `agents/pj-master/scripts/pj_escalate_all.sh` — **créé** (wrapper cron
  versionné). C'est le **16e wrapper manquant** : **15** `.sh` sont déjà versionnés
  sous `agents/pj-master/scripts/` (families `pj_bridge_*`, `pj_deploy_*`,
  `pj_graphwatch_*`, `pj_room_keeper_*`, plus `pj_repo_watch.sh`). Le patron
  applicable est **`pj_repo_watch.sh`**, pas `pj_room_keeper_<repo>.sh` :
  `pj_escalate` est **global** (itère `pj-*`), donc sans suffixe de repo, et son
  jumeau in-repo est `export PATH="$HOME/.local/bin:$PATH"` + `exec python3 ${HOME}/.hermes/profiles/pj-master/scripts/pj_escalate.py`.
  Le wrapper live n'exporte **aucun** PATH (`exec python3 /home/elix/…` sec) et
  son chemin absolu (`profiles/pj-master/scripts/`) est **déjà la cible de
  déploiement** de `README.md` §4 — ce qui manque n'est donc pas le repointage
  mais le **geste d'installation** (une ligne `cp` + dé-hardcodage `$HOME`,
  amendement minimal requis pour que la livraison ne soit pas inerte). Précision
  (@pj-master) : `export PATH` ne **garde pas** la garde vivante — le candidat
  vérifié `~/.local/bin/gh` le fait déjà sous PATH de cron — ; il conditionne le
  **puits de sortie** (voir plus bas). Le modèle
  `pj_room_keeper_hermes-experiment.sh` (variable `${HERMES_WORKFLOW}`) casse en
  production : `HERMES_WORKFLOW` n'est exporté nulle part → `${HERMES_WORKFLOW}/bridge/...`
  exécute `/bridge/...`, mauvais fichier, rc=0 ;
- l'**entrée de cron** (`pj-master/cron/jobs.json`, id `aaf9ef8237f8`,
  `script: pj_escalate_all.sh`, `*/3 min`) — **non versionnée** et **non
  versionnable** : `jobs.json` est de l'état live, pas du source. Le précédent
  in-repo pour rendre une entrée de cron reproductible est
  `skills/gh-kanban-bridge/scripts/setup.sh` (l.108/118 : `hermes cron create … --script … --no-agent`),
  pas un `jobs.json` committé ;

  **Puits de sortie (mesuré, non décoratif)** : le job écrit déjà dans
  `~/.hermes/profiles/pj-master/cron/output/aaf9ef8237f8/*.md` — 50 fichiers,
  rétention bornée (`cron.output_retention`, défaut 50, ≤0 désactive). Un
  `print` d'un tick `no_agent` y est capturé tel quel : 49 fichiers
  `Status: silent (empty output)`, et un fichier réel (`2026-09-20_13-30-44.md`,
  188 o) porte le stdout `[escalate] pj-hermes-workflow: 1 escalade(s), 6 déjà
  vue(s)`. Le mécanisme fonctionne aujourd'hui ; ce qui est vrai c'est **non
  durable et non poussé** (`deliver: local`, aucun destinataire notifié). L'AC
  nomme donc ce chemin (`cron/output/<job_id>/*.md`), pas un `tee` de wrapper —
  un `tee` ajouterait un second puits sans rotation.

  **Dédup d'avertissement : hors périmètre (ratifié — GO 13:42Z, corps l.91-97)** :
  le warning est **visible et horodaté, par tick**, pas unique à vie. `_WARNED` est
  un **set process-local** alors que le cron lance un **process neuf à chaque
  tick** — un `GH_BIN` vide permanent réécrit le même avertissement toutes les 3
  minutes et évince les 50 fichiers au bout de ~2 h. Ce caveat est **assumé et
  borné** par la spec ratifiée : « un avertissement par message **et par tick**,
  comme la copie actuelle ». La **dédup persistée** (fichier d'état + politique de
  rétention) est **explicitement non livrée ici** — sujet séparé, décision que ce
  cadrage ne présume pas.
- `gh_kanban_bridge.py` — **référence** (pattern `_resolve_bin` à réutiliser,
  pas à dupliquer) ; non modifié ;
- les **tests** (`tests/`) — quatre scénarios automatisés, dont au moins un qui
  verrouille `escalation_allowed` directement.

**Aucun autre composant** n'est touché : les voisins versionnés, le contenu du
message, la liste des statuts escaladables et la dédup par `(carte, event)`
restent inchangés.

## Frontières traversées (résumé)

```
cron (PATH restreint)
  → lit kanban.db (cartes blocked/triage + events)
  → résout (repo, issue)               [idempotency_key → URL → parents → repli]
  → lit l'état du ticket (gh)          ← NOUVELLE frontière GitHub
  → escalation_allowed(state)          ← décision pure (core)
  → CLOSED ? marqué traité, pas de post
  → OPEN   ? post dans le thread Discord (helper discord_thread.py)
```

La frontière **critique** n'est ni GitHub ni Discord, mais la **frontière
d'exécution dépôt ↔ copie lancée** : tant que la copie exécutée n'est pas la
copie versionnée, aucun des deux correctifs n'est garanti en production.
