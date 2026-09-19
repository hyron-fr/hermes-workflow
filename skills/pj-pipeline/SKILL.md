---
name: pj-pipeline
category: software-development
version: 1.0.0
description: "Use when working on the pj pipeline (pj-master, pj-dev)."
tags: [hermes, kanban, github, discord, automation]
---

# Pipeline pj — GitHub Issues → kanban → PR (pj-master / pj-dev)

Automatisation opérationnelle (installée 13/09/2026, validée E2E sur example-repo #20 → PR #21 mergée).

## Topologie

- Profils : **pj-master** (orchestrateur, bot Discord « Experiment », canal #pj-master
  ${DISCORD_ID}, guild ${DISCORD_GUILD} ${DISCORD_ID}, gateway systemd dédié) et
  **pj-dev** (worker dev). Provider litellm-proxy-gcp — la clé se copie PROGRAMMATIQUEMENT
  depuis ~/.hermes/config.yaml ; une clé reconstituée depuis un read_file redacté = 401.
- 1 board kanban par repo hyron-fr : `pj-<slug>`. Anchors clones sur dev :
  `${HOME}/pj-repos/<repo>` ; `default_workdir` par board (anchor worktree).
- Crons sur le profil pj-master (0 LLM pour tous) : `pj-bridge-<repo>` (pull issues/push
  done) + `pj-deploy-<repo>` (*/5) + `pj-graphwatch-<repo>` (*/5, graphe de dev) +
  `pj-room-keeper-<repo>` (*/5, cycle des rooms) + `pj-repo-watch` (*/10). Le compte
  s'incrémente à chaque board/étape ajouté — le lire dans `hermes cron list`, pas de mémoire.
- Mémoire : banque hindsight **pj** partagée, séparation par tags `project:<repo>`
  (le placeholder {workspace} est hardcodé "hermes" — pas de banque par worktree possible).
- Discord REST en cron : helper `${HERMES_WORKFLOW}/pipeline/discord_thread.py` (token lu dans
  pj-master/.env ; User-Agent style DiscordBot obligatoire sinon 403 Cloudflare).

## Flux (1 issue → graphe de cartes)

1. Pont importe la racine en **triage** (`PJ_IMPORT_TRIAGE=1`).
2. `pj_pipeline_deployer.py` (déterministe, sans LLM) : t1 worktree (`--workspace
   worktree:<anchor>`), t2 mémoire, t3 grill-me ; **t3b doc-cadrage** (assignee `pj-doc`,
   positionnement architectural SDD/DDD/TDD/hexagonal, croisement infra/fonctionnel/code
   — amont de t4) ; t4 draft (parents t1+t2+t3+t3b), t5 validate (parent t4) ; chaque t_i
   **PARENT** de la racine ; sortie de triage via `specify_triage_task` (API directe, pas
   de LLM).
3. t3/t5 : worker pose les questions sur Discord puis `kanban_block` ; réponse humaine →
   `kanban unblock` → re-spawn qui relit tout le fil.
4. GO humain : le worker t5 écrit le **manifeste de graphe** (section suivante) ; un cron
   déterministe construit t6 + les cartes de slice ; PR par le worker t6 ; racine
   réveillée done → le pont ferme l'issue + notif Discord.

## Graphe de dev : manifeste validé → cron déterministe

La topologie d'une issue ne se crée **jamais** par un LLM : à la sortie du gate humain, le
worker t5 écrit un manifeste, le valide, et un cron construit tout le graphe. C'est ce qui a
supprimé les dérives observées (cartes fantômes, liens inverses, assignees étrangers).

- **Manifeste** : `~/.hermes/kanban/boards/<board>/specs/<issue>/slices.json` — clés
  `issue`, `repo`, **`branch`** (UNE seule pour l'issue : `wt/issue-<n>-<slug>`), et
  `slices[]` = `{k, slug, depends_on, parallel:{test,dev}, convergence, doc}`.
- **Validation obligatoire** (`pj_slices_lint.py`, `exit 0`, sinon `request-changes` sur
  t5) : `k` contigus depuis 1 ; `depends_on` strictement inférieur (pas de dépendance
  avant) ; `branch` présente ; et la carte `test` doit porter **≥3 scénarios** — nominal,
  cas **limite**, **erreur** (mots-clés : limite/edge/bord, erreur/invalide/corrompu).
- **Construction** (`pj_graphwatch.py`, cron `*/5` no-agent, un par board) : repère les
  cartes `t6 submitted` sans enfants, lit le manifeste, crée TOUTES les cartes avec des clés
  d'idempotence (`pj-<clé>-<repo>-<issue>`), puis pose TOUS les liens — dont les liens
  anti-deadlock (cartes de production PARENTS de t6). Tick muet quand aucun t6 orphelin.
- **`PJ_DRY_RUN=1` imprime le plan et ne crée RIEN** : vérifier la topologie par dry-run
  avant tout run réel, puis relire le board.
- **Un script constructeur qui a un assignee PAR DÉFAUT l'applique à TOUTES les cartes
  qu'il crée.** Une carte destinée à un profil spécialiste se retrouve assignée à
  l'orchestrateur — sans erreur ni avertissement — et c'est le mauvais profil qui
  l'exécute (ou le garde-fou qui la bloque, selon la liste blanche). Chaque carte dont le
  propriétaire diffère du défaut doit passer son `--assignee` EXPLICITEMENT. La
  vérification se fait après un déploiement RÉEL en relisant l'`assignee` de chaque carte
  (`kanban show <id> --json`), jamais en relisant le script.

## Règles dures (vérifiées dans le source kanban_db.py)

- **Sens des liens** : `link P C` = C attend que P soit done (multi-parents OK, tous
  terminaux requis). Anti-deadlock : les sous-tâches dev sont PARENTS de t6, JAMAIS
  `--parent t6` sur une dev.
- La racine n'est pas parent de ses étapes : chaque t_i est parent de la racine.
- `promote` refuse depuis triage → `specify_triage_task` (API directe) ou UPDATE sqlite
  direct (seule transition triage sans CLI).
- Un cron d'un profil résout `--script` dans `~/.hermes/profiles/<profil>/scripts/`, PAS
  le global ; symlinks refusés (realpath).
- **`kanban.auto_decompose: false` + `auto_decompose_per_tick: 0` dans le config du
  PROFIL DONT LE GATEWAY TIENT LE VERROU DISPATCHER** (le dispatcher lit la config de
  ce profil-là — ni celle du profil de la carte, ni forcément celle de `default`).
  PITFALL VÉCU : la clé posée dans `~/.hermes/config.yaml` n'a rien arrêté, parce que
  le verrou était tenu par le gateway d'un AUTRE profil (profils = îles, pas
  d'héritage) — le décomposeur LLM a continué à frapper les triage avant le deployer et
  à livrer le travail à un profil étranger. Identifier le détenteur avec l'event
  `claimed {'lock': '<host>:<pid>'}` d'une carte croisé avec `hermes gateway list`
  (`.dispatcher.lock` peut être vide), patcher CE profil, redémarrer son gateway.
- Repo vide (HTTP 409, size 0) : ni branche dev ni clone possibles. Watcher 2 phases :
  A (wrappers+crons+board) dès la création → issues importées en triage, 0 LLM ;
  B (dev+clone+default_workdir) au premier commit, anchor résolu dynamiquement.
- Plugin **pj-buttons** (profil pj-master, gateway) : `defer()` l'ACK IMMÉDIATEMENT (sans
  ACK Discord affiche « didn't respond in time »), puis comment + unblock en CLI kanban.
  Il accepte DEUX schémas de custom_id — `pj:<action>:<board>/<task_id>` (canonique) et
  `triage:<action>:<N>` (émis par le helper `discord_thread.py send --go-nogo <N>`) — et
  résout la carte cible côté serveur depuis le nom du thread (`<repo> #<N> · <titre>` →
  la carte **blocked** du board : validate/grill, pas la racine). Un plugin qui n'écoute
  que son propre schéma laisse les clics inertes (le worker émet le schéma du helper).
- Après tout changement de config : `pj-master chat -q "PONG"` + `finish_reason=stop`
  dans logs/agent.log (un PONG « réussi » en apparence a été un 401).
- **Un changement de modèle n'est vérifié que si le modèle a RÉPONDU.** Le résumé CLI
  (Session/Duration/Messages) n'affiche pas le modèle : un profil peut continuer à
  tourner sur l'ancien, ou retomber sur un autre, sans que ça se voie. Lire la ligne
  `Turn ended: ... model=<modèle réel>` de `logs/agent.log` et confronter au modèle
  voulu. Écrire les DEUX clés (`model.default` ET `providers.<prov>.default_model`)
  dans le config DU PROFIL (`HERMES_HOME=~/.hermes/profiles/<p> hermes config set`) —
  sinon `hermes profile list` garde l'ancien ; ne pas se fier à la sortie du `config
  set` sans relire le fichier et la colonne Model.
- **Une carte d'un board `pj-*` peut être exécutée par un profil étranger, en silence.**
  Un dispatcher tenu par un autre profil applique SON `default_assignee` : travail hors
  graphe, sans gate humain et **sans fil Discord** (le contrat de notif dépend de t5, qui
  n'existe pas). Détecter par lecture du board, pas par confiance dans la provenance de
  la carte — `SELECT id,status,assignee,created_by FROM tasks WHERE
  assignee='<profil-étranger>' OR created_by LIKE '%decompos%'` — et vérifier que toute
  carte d'un board `pj-*` a bien des parents/`workflow_template_id` du pipeline.

## Profils complémentaires (pj-doc, pj-test, …)

- **pj-doc** — cadrage architectural en phase spec (positionnement SDD/DDD/TDD/hexagonal,
  croisement infra/fonctionnel/code → carte `t3b doc-cadrage`, amont de t4) ; tenue du vault
  `docs/` en phase dev ; revue de cohérence en phase review ; alimentation Hindsight post-merge.
- **pj-test** — porte les tests que pj-dev n'écrit plus : RED/GREEN, et garantit la couverture
  (>80 % par fichier du diff). Écrit uniquement dans `tests/**`.
- **Ajouter un profil spécialiste = élargir le garde-fou d'admission AVANT de créer sa
  première carte** (voir la section garde-fou), puis vérifier son intégration par un run RÉEL :
  une carte assignée au nouveau profil qui passe `done` avec une production vérifiable — pas un
  `PONG` ni une carte `ready`. Le test de bout en bout le plus probant : lui faire produire un
  artefact (note de cadrage, rapport de test) et VÉRIFIER son contenu contre le code.

## Rooms Bot Mode : propriété pj-master (décision user)

**pj-master gère les rooms de bout en bout** — une room par ticket, `room_id` =
`pj-<repo>-issue-<n>`, cycle `ensure → ask → report → disband` porté par un cron déterministe
`pj-room-keeper-<board>` (*/5, no-agent). Le lien room↔ticket est un marqueur `ROOM: <room_id>`
dans le body de t4 (posé par le deployer ; `kanban edit` refuse les cartes actives, donc une
carte déjà créée se migre en base). Le **board reste la source de vérité** : à l'étape `report`,
le transcript de la délibération part en `kanban_comment` sur la carte. Rien à faire à la main.

Deux points de conception à respecter :

- **Une room ne s'anime JAMAIS seule** : sans `message.user`, le moteur reste `idle`
  (`no_pending_user_event`) et la room est une coquille vide. C'est l'étape `ask` qui l'anime —
  d'où l'inutilité de créer la room sans prévoir l'animation.
- **Les bots n'ont pas besoin d'être rappelés pour réagir à la carte** : un worker qui a le
  toolset Bot Mode poste parfois lui-même son brouillon dans la room. Les deux chemins (worker
  et keeper) coexistent et se complètent — le keeper couvre les rooms que le worker n'anime pas.

Mécanique exacte, bornes, diagnostic du livelock multi-gateway et sortie de secours
(`request_room_stop`) : `hermes-multi-agent-orchestration` → `references/hosted-rooms.md`.

## Contrat de format des cartes (exigence user — appliqué à TOUTE tâche/sous-tâche)

Le body de chaque carte produite (t4 draft, t6, dev-k, futures sous-cartes) porte EXACTEMENT
5 sections numérotées, dans cet ordre, plus un dimensionnement INVEST :

1. **Contexte & Objectif** — issue #N, valeur, objectif = résultat observable (pas une
   activité), dépendances amont/aval.
2. **Critères d'acceptation (BDD/Gherkin)** — `Fonctionnalité:` + **≥3 `Scénario:` :
   nominal + CAS LIMITE + erreur** (exigence user : les cas limites sont des tests de
   première classe, au même titre que le nominal — pas un bonus de fin de carte), en
   Étant donné/Quand/Alors ; chaque critère automatisable.
3. **DoR & DoD** — DoR : spec validée, worktree prêt, parents done, aucune question ouverte
   (sinon `kanban_block`, jamais démarrer « en attendant »). DoD : tests verts, checks du
   repo verts, commits poussés, handoff écrit, artifacts, mémoire projet mise à jour.
4. **Considérations techniques & garde-fous** — fichiers/contrats touchés, contraintes,
   **interdits explicites**, risques + repli.
5. **Hors-scope** — ce que la carte ne fait pas ET où le sujet est traité.

**INVEST** : 1 slice verticale = 1 carte. Independent (dépendance = lien parent explicite,
jamais implicite), Negotiable, Valuable (démo/test E2E possible), Estimable (sinon carte
« spike »), **Small ≤ ~1 j d'agent / ≤ ~400 lignes / ≤ ~5 fichiers / 1 seul domaine —
dépassement = découper AVANT de créer**, Testable. Une sous-carte hérite du contexte de la
mère par référence (« issue #N, slice k/N ») et reçoit son PROPRE bloc Gherkin/DoR/DoD.

**Vérification opposable, pas une consigne de prompt** : `scripts/pj_card_lint.py`
(copie live dans le `scripts/` du profil pj-master) linte les bodies par regex, 0 LLM,
exit 1 si non conforme. La carte t5 le lance avant de demander le go humain — une spec non
conforme repart en t4. Le brief de format est AUSSI injecté dans les bodies que
`pj_pipeline_deployer.py` crée pour t4/t5, sinon seules les cartes dérivées l'héritent.

```bash
python3 ~/.hermes/profiles/pj-master/scripts/pj_card_lint.py --board pj-<repo> [--all|--task <id>]
```

Le linter exclut les cartes de process, les cartes done/archivées et tolère
« Contexte »/« Context » et un préfixe de numérotation varié (`1.`/`### 1.`).

**L'exclusion des cartes de process doit être écrite en motif GÉNÉRAL**
(`^t\d+[a-z]?\b`), pas en liste fermée des étapes du moment (`^t[1-6]\b`) : toute
étape ajoutée ensuite (`t3b`, `t4a`, …) devient un faux positif en masse dès sa
première carte, et c'est exactement quand on ajoute une étape qu'on lancerait le
linter. Inversement, un linter qui matche trop large rend le gate décoratif.

## Un contrôle déterministe ne valide que son PÉRIMÈTRE

Un linter de conformité (vault documentaire, format de carte, couverture) qui scanne
tout le dépôt produit des **faux positifs sur le contenu PRÉEXISTANT** — des dizaines
de fichiers hérités d'avant la convention, tous légitimes. Le gate devient
inutilisable : on le désactive au lieu de le corriger.

Règle : un gate ne valide que **la zone où la convention s'applique** (ex. les notes
sous les deux répertoires du vault, pas tout `docs/` ; les fichiers du diff, pas tout
le repo). Exigence de vérification associée : **éprouver le gate dans les DEUX sens —
muet sur un dépôt sain (exit 0) ET rouge sur une entrée volontairement fautive
(exit 1)**. Un gate seulement vert ne prouve rien (voir la règle « démontrer ROUGE »
plus haut).

## Un gate de couverture doit être démontré ROUGE

**Lancer le gate avant de s'appuyer dessus** : s'il sort vert du premier coup sur un
repo aux tests partiels, il ne mesure rien (rapport absent, scope ignoré, filtre
d'exclusion trop large). Deux pièges de périmètre vécus :

- le scope se calcule sur **les fichiers modifiés** (`git diff --name-only <base>...HEAD`),
  pas sur l'ensemble du rapport — un fichier ancien non touché ferait échouer toute
  slice ;
- les exclusions (`is_code_file`, `_version.py`, `*.d.ts`, configs, l'arborescence de
  tests) retirent des fichiers du décompte : un **test écrit avant l'ajout d'une
  exclusion** échoue après coup. Le test est alors obsolète, pas l'implémentation —
  le corriger, jamais l'inverse.

## Garde-fou d'admission (isolation des boards pj-*)

`pj_spawn_guard.py` (repo `hermes-experiment/bridge/`, copie live
`${HERMES_WORKFLOW}/pipeline/`) refuse tout travail hors pipeline sur un board `pj-*` : il bloque la
carte dont l'`assignee` n'est pas dans `DEFAULT_ALLOWED`. Enregistré sur DEUX hooks par
profil de gateway : `on_kanban_dispatch_tick` (tire APRÈS relâchement du verrou de
dispatch → bloque sans deadlock, et la carte n'est pas claimée au tick suivant : **c'est
lui qui protège**) et `kanban_task_claimed` (tire APRÈS le claim → le spawn courant n'est
PAS annulable ; y signaler seulement, ne jamais compter dessus pour annuler).

RÈGLE OPÉRATIONNELLE : **ajouter un profil au pipeline (`pj-doc`, `pj-test`, …) exige de
l'inscrire dans `DEFAULT_ALLOWED` ET de redéployer la copie utilisée par les hooks, AVANT
de créer la moindre carte** — sinon toutes ses cartes sont bloquées avant spawn, en
silence. Vérifier en créant une carte par assignee puis en appliquant le hook
`on_kanban_dispatch_tick` : attendu `ready` pour les profils pj, `blocked` pour les autres.

## Convention de couverture de tests (exigence user)

**>80 % par test, sur les fichiers MODIFIÉS par la PR** (patch coverage), pas sur tout le
dépôt fichier par fichier : une slice ne doit pas échouer à cause d'un fichier ancien
qu'elle n'a pas touché. Doubler d'un seuil global de non-régression. En TS le seuil natif
vitest (`thresholds.perFile`) est global et ne sait pas se limiter au diff → calculer la
mesure « patch » via `git diff --name-only origin/dev...HEAD` croisé avec le rapport de
couverture. Exclure les fichiers déclaratifs non exécutables (`*.d.ts`, configs,
`_version.py`, l'arborescence de tests elle-même).

Deux règles qui font la différence entre un gate utile et un gate décoratif :

- **Un gate de seuil doit être démontré ROUGE au premier lancement.** S'il sort vert
du premier coup sur un repo où les tests sont partiels, il ne teste rien : vérifier que
le rapport contient bien les fichiers visés et que le scope (`perFile`/liste de diff) est
pris en compte, avant de s'appuyer dessus.
- **Les cas limites se testent au même titre que le nominal** (voir le contrat de format
ci-dessus) : un gate de couverture seul ne les attrape pas — d'où la vérification par
SCÉNARIO de la carte de tests, pas seulement par pourcentage.

## Partager un worktree entre plusieurs cartes (peer programming)

**Le partage se fait par identité de BRANCHE, pas par chemin.** Vérifié dans
`kanban_db_workspace.py` : `if actual_branch == branch_name: return <chemin>, branche` —
deux cartes déclarant le **même `--branch`** réutilisent le même worktree ; une branche
différente fait retomber **silencieusement** sur un worktree propre à la carte
(`<repo>/.worktrees/<task-id>`). Donc :

- une **branche par issue**, déterministe (`wt/issue-<n>-<slug>`), **jamais** dérivée de
  l'id de carte, déclarée une fois et répétée sur TOUTES les cartes de la slice ;
- après déploiement, vérifier que deux cartes sœurs ont le même `workspace_path` ET le
  même `branch_name` (`kanban show <id> --json`) et qu'il n'existe qu'un worktree côté
  git (`git worktree list | grep -c`) — sinon le `--branch` n'a pas été posé ;
- conséquence de conception : un seul worktree par issue ⇒ les slices qui se recouvrent
  sont SÉQUENTIELLES, le parallélisme réel n'existe qu'entre composants disjoints ;
- périmètres d'écriture disjoints par contrat (le rôle test n'écrit que dans les tests,
  l'implémentation que dans les sources) ; conflit → `kanban_block`, jamais `--force`.

Cycle de vie : une carte **amont** crée le worktree (`worktree-mk`, poste chemin+branche
au blackboard, toutes les cartes de slice en dépendent) et une carte **aval** post-merge
le supprime (`worktree-rm`, enfant de la carte PR, exige `gh pr view --json state ==
MERGED` + `git merge-base --is-ancestor` sur chaque commit, `kanban_block` sinon).

## Onboard manuel d'un nouveau repo (sinon pj-repo-watch le fait)

1. Branche `dev` GitHub (depuis la default). 2. Clone dev → `~/pj-repos/<repo>`.
3. Wrappers `pj_bridge_<repo>.sh` / `pj_deploy_<repo>.sh` dans le scripts/ du profil.
4. 2 crons no-agent + board `pj-<slug>` + default_workdir (posé EN DERNIER = marqueur
   idempotent d'onboard complet).

## Coût LLM

Bridges, deployer, watcher, dispatcher, pj-buttons = **0 LLM**. Par issue traitée :
~7-10 runs (deepseek-v4-flash:cloud) : t1, t2, t3, t4, t5, chaque dev-k, t6.

## Voir aussi

`references/graph-manifest.md` (schéma du manifeste `slices.json`, règles de validation,
construction et test à blanc),
`scripts/pj_card_lint.py` (linter de conformité des cartes, 0 LLM),
`scripts/pj_coverage_gate.py` (gate de couverture scopé au diff, 0 LLM — copier dans le
scripts/ du profil avant de l'appeler depuis une carte),
`gh-kanban-bridge` (pont), `hermes-messaging-bots` (setup bot),
`hermes-multi-agent-orchestration` (règles de classe : sens des liens, gates, format,
topologie parallèle + convergence, cycle de vie du worktree),
`projecta-grooming` (grooming ≤3 questions), `obra/superpowers` (grill-me/brainstorming).

## Écrire un plan ou une spec qui cite l'existant

Un plan destiné à un implémenteur sans contexte propage toute erreur : **relire à la
source chaque chemin, comptage et nom de clé cité au moment de l'écrire**, jamais de
mémoire ni du transcript (les chiffres dérivent : un `.env` de profil, un regex de
linter, une version épinglée, une constante en dur, la signature d'une fonction).
Comportement à vérifier dans le code et non supposé : le sens des liens kanban, la
règle de partage de worktree, les valeurs par défaut de config, le nombre de lignes
d'un fichier cité. Quand une décision utilisateur invalide une partie du plan déjà
écrit, RÉÉCRIRE les sections concernées (pas d'ajout « mise à jour : en fait… ») — un
plan qui contient deux vérités contradictoires ne peut pas être exécuté.