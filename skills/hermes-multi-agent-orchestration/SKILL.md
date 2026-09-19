---
name: hermes-multi-agent-orchestration
description: "Use when designing multi-agent workflows with Hermes kanban."
version: 1.0.0
tags: [hermes, kanban, bots, orchestration]
---

# Orchestration multi-agents avec le builtin Hermes

Classe : construire un pipeline multi-agents (ex. profil scrum orchestrateur + bots
spécialistes) avec UNIQUEMENT les primitives builtin — kanban durable, Bot Mode,
hooks, cron — sans moteur d'orchestration custom.

## Règles toujours vraies

- **Builtin vs on-top, séparés explicitement.** Les systèmes durables builtin :
  delegate_task, cron, curator, kanban (+ Bot Mode = UI desktop par-dessus les
  profils ; un bot EST un profil). Le moteur workflow YAML (`workflows/*.yaml` +
  gate qui charge `workflow_template_id`) et le pont GitHub sont du glue CUSTOM
  du repo hermes-experiment : ne JAMAIS les présenter comme builtin ; les
  nommer comme custom quand ils interviennent. (Correction user expresse.)
- **Vérifier dans la source avant d'affirmer** une capacité kanban :
  `hermes_cli/kanban_db.py` (statuts, transitions, colonnes) +
  `hermes kanban <verb> --help` (ex. pas de sous-commande `update`).
- **La machine à états est builtin et intouchable.** 9 statuts fixes :
  `triage, todo, scheduled, ready, running, blocked, review, done, archived`.
  Pas de statuts custom sans patcher le core — le design s'y oppose. Les
  "étapes" métier vivent dans les colonnes natives `workflow_template_id` +
  `current_step_key` (données de carte, filtrables via
  `kanban list --workflow-template-id/--step-key`). Avancer une étape =
  bookkeeping de l'orchestrateur sur la carte, pas une transition de statut.
- **Deux types de gate, ne pas les confondre.** (1) Gate d'admission = hook
  `kanban_task_claimed`, AVANT le spawn du worker. (2) Gate de résultat = APRÈS
  le travail : `kanban_request_review` / `kanban_request_changes` (natif —
  "les tests échouent, reprends ton code" est ce chemin, pas la gate de claim)
  ou completion contract PR (`--completion-contract`, done refusé sans checks
  requis verts). Réutiliser la gate de claim pour un contrôle après coup est
  impossible : elle s'exécute avant que le travail existe.
- **Sens des liens = qui attend qui (vérifié `kanban_db.py`).** `link
  <parent> <child>` / `create --parent X` : l'ENFANT attend la fin du parent
  (multi-parents = ET logique ; `recompute_ready` garde l'enfant `todo` tant
  qu'un parent n'est pas done, et le résumé de chaque parent done est injecté
  au worker enfant via `_ctx_parent_results`). Une carte « synthèse/submitted »
  qui doit attendre ses sous-tâches se construit à l'ENVERS : chaque sous-tâche
  est PARENT de la carte synthèse (pattern decompose : la racine est liée sous
  chaque enfant et se réveille quand tout le graphe est done). Jamais
  `--parent <synthèse>` sur une de ses entrées — deadlock (l'entrée attend la
  done de la synthèse, qui attend que les entrées produisent).
- **Une carte racine d'orchestration n'est pas un worker one-shot.** Un worker
  spawné ne peut pas « rendre la main » : `complete` la marque done (ferme le
  ticket/issue amont trop tôt), `block` est sticky. La racine qui déploie un
  graphe se parque en `--triage` (à l'import : `create --triage`), un script
  déterministe déploie enfants+liens, puis elle sort du triage via
  `kb.specify_triage_task` (appel Python direct, sans LLM ; le CLI
  `kanban specify` passe par le LLM aux ; `kanban promote` REFUSE le triage).
 Devenue enfant de toutes ses tâches, elle se réveille seule à la fin.
 Corollaire : un worker qui a DÉJÀ livré peut continuer à tourner en rond sans pouvoir
 rendre la main (contexte de 100 k+ tokens, dizaines d'appels API, outils répétés
 `skill_view`/`terminal` sans écriture). Le détecter par les ARTEFACTS, pas par le
 process : comparer les mtime des fichiers produits et le volume de sortie — s'ils ne
 bougent plus, le worker est fini même si la carte dit `running`. Récupération : tuer,
 `kanban reclaim <id>` (la carte repasse `ready` et le dispatcher la respawne), et
 vérifier que le nouveau run PRODUIT vraiment avant de conclure.
- **Un seul mécanisme de fan-out par board.** L'auto-decompose du dispatcher
  et un deployer custom visent tous deux les racines triage : sur un même
  board ils doublonnent le graphe (enfants parasites qui contournent les
  gates humains). Désactiver l'un des deux ; un deployer custom skippe les
  racines portant déjà un event `decomposed`. L'auto-decompose est ON par
  défaut (`kanban.auto_decompose: true`) et **lit la config du profil dont
  le gateway tient le verrou dispatcher**, pas celle du profil de la carte.
  Corollaire qui coûte cher : les profils sont des îles, donc poser
  `auto_decompose: false` dans `~/.hermes/config.yaml` ne couvre QUE le
  gateway du profil default — si le verrou est tenu par un autre profil, le
  décomposeur continue de frapper. **Identifier le profil dispatcher AVANT
  de patcher** : l'event `claimed {'lock': '<host>:<pid>'}` d'une carte donne
  le PID du gateway qui spawne ; le confronter à `hermes gateway list` donne
  le profil (le fichier `.dispatcher.lock` peut être vide — ne pas s'y fier).
  Puis `auto_decompose: false` + `auto_decompose_per_tick: 0` dans le
  config.yaml de CE profil, et redémarrer son gateway.
- **Une carte d'un board de pipeline peut être exécutée par un profil
  étranger, en silence.** Un dispatcher tenu par un autre profil applique SON
  `kanban.default_assignee` aux cartes triage et aux enfants qu'il
  auto-décompose : le travail part chez un profil sans lien avec le pipeline,
  donc sans graphe, **sans gate humain et sans aucune notification**. Un
  contrat de notification qui dépend du pipeline ayant créé la carte est un
  contrat troué : la détection doit se faire par lecture du board, pas par
  confiance dans la provenance. Balayage (assignee/creator, pas l'affichage) :
  `sqlite3 <board>/kanban.db "SELECT id,status,assignee,created_by FROM tasks
  WHERE assignee='<profil-étranger>' OR created_by LIKE '%decompos%';"`.
- **Arrêter un acteur hors pipeline : tuer PUIS neutraliser, et relire le
  board.** `kill` seul laisse la carte `running` avec un claim : le dispatcher
  la respawn au tick suivant. Enchaîner : (1) tuer les workers du profil
  (`ps -eo pid,args | grep 'hermes.*-p <profil>.*chat -q'`), vérifier 0
  restant. **Un worker tué reste visible en zombie** (`Zs [hermes] <defunct>`) :
  `ps -p <pid>` le compte comme VIVANT et fait croire à un process actif. Filtrer
  `grep -v defunct` (ou lire la colonne STAT) avant de conclure. Un zombie qui traîne
  n'exécute plus rien mais garde son claim : la libération se fait par
  `kanban reclaim <id>`, pas en re-tuant ; (2) neutraliser chaque carte. `kanban block` **est refusé selon le
  statut de départ** (constaté depuis `todo` — « cannot block ») ; `reassign`
  fonctionne même depuis `todo` mais rend la carte spawnable par le nouveau
  profil : si l'arrêt doit être définitif, archiver. (3) Relire le board et
  confirmer qu'aucune carte n'est `ready`/`running` sur le profil visé — une
  carte neutralisée « à l'affichage » peut rester engageable.
- **Le format d'une carte se vérifie mécaniquement, pas par prompt.** Une
  consigne de format dans le SOUL dérive (workers one-shot, respawns). Le
  contrat (sections obligatoires, scénarios BDD, DoR/DoD, garde-fous,
  hors-scope, dimensionnement INVEST/Small) doit être couvert par un LINTER
  déterministe 0-LLM appelé avant le gate humain, avec exit code — c'est lui
  qui rend l'exigence opposable. Le linter exclut les cartes de PROCESS
  (étapes de pipeline, racine importée dont le body est la source amont) et
  les cartes done/archivées, sinon il produit des faux positifs en masse.
  Le brief de format doit aussi être injecté dans les bodies que le deployer
  crée, sinon seules les cartes dérivées l'héritent.
- **Un gate déterministe ne vaut que par son PÉRIMÈTRE, et un périmètre trop
  large tue le gate.** Un linter (format de carte, vault documentaire,
  couverture) qui scanne tout le dépôt signale le contenu PRÉEXISTANT — des
  dizaines de fichiers antérieurs à la convention, tous légitimes : le gate
  devient inutilisable et se fait désactiver au lieu d'être corrigé. Le
  restreindre à la zone où la convention s'applique (les répertoires du vault,
  pas tout `docs/` ; les fichiers du diff, pas tout le repo). Corollaire sur
  les exclusions : elles changent le décompte, donc un test écrit AVANT l'ajout
  d'une exclusion (`_version.py`, `*.d.ts`, configs, arbo de tests) échoue
  après coup — c'est le test qui est obsolète, pas l'implémentation.
- **Un contrôle qui filtre par motif doit filtrer en GÉNÉRAL, pas en liste
  fermée.** Un linter qui exclut les étapes de pipeline par énumération
  (`^t[1-6]\b`) transforme toute étape ajoutée ensuite (`t3b`, `t4a`) en faux
  positif en masse — précisément au moment où l'on ajoute une étape, donc où
  l'on lance le linter. Écrire le motif général (`^t\d+[a-z]?\b`).
- **Éprouver un gate dans les DEUX sens : muet sur une entrée saine ET rouge
  sur une entrée fautive.** Un gate seulement vert ne prouve rien (rapport
  absent, scope ignoré, exclusion trop large) ; un gate seulement rouge détruit
  la confiance. Construire une entrée volontairement fautive et vérifier
  l'exit 1 fait partie de la livraison du gate, pas d'un test de confort.
- **Un gate humain en bouton ne peut pas dépendre d'un schéma de custom_id
  que l'émetteur ne connaît pas.** Quand le worker émet le bouton via un
  helper générique et que le listener vit dans un plugin écrit pour un autre
  schéma, les clics sont inertes et le client affiche « didn't respond in
  time » (l'ACK n'arrive jamais). Règle : le listener doit `defer()` l'ACK
  IMMÉDIATEMENT (avant toute résolution), accepter les schémas émis par les
  helpers en place, et résoudre la carte cible côté serveur (par le contexte
  du thread/message) plutôt que d'exiger un payload que l'émetteur ignore.
  L'API de bot ne permet pas de simuler un clic : tester le handler sur le
  board réel (mock de l'adaptateur, kanban réel), pas en espérant un clic.
- **Ajouter un profil spécialiste à un pipeline = élargir le garde-fou
  d'admission AVANT de créer la moindre carte pour lui.** Un garde-fou de board
  (liste blanche d'assignees) refuse tout assignee inconnu : les nouvelles cartes
  sont bloquées avant leur spawn, en silence — le garde fait exactement son
  travail, rien ne signale l'erreur. Ordre obligatoire : (1) élargir la liste
  blanche à la source, (2) recopier la version DÉPLOYÉE que les hooks appellent
  réellement (un garde vit souvent en deux exemplaires : le repo + une copie dans
  le scripts/ du profil), (3) redémarrer le gateway qui détient le dispatcher,
  (4) tester l'admission sur un board réel : une carte par profil autorisé ET une
  par profil interdit, exécuter le hook à la main, vérifier ready vs blocked,
  archiver les cartes de test. Tant que (2)+(3) ne sont pas faits, le test passe
  et le pipeline bloque quand même.
- **Parallélisme et convergence : le builtin `kanban swarm` donne la topologie.**
  `hermes kanban swarm --worker PROFIL:TITRE --verifier P --synthesizer P` écrit
  un graphe root → workers parallèles → verifier (parents = tous les workers) →
  synthesizer (parent = verifier). Le « blackboard » partagé est un commentaire
  JSON structuré sur la carte racine (`[swarm:blackboard]`), donc la coordination
  vit dans les tables natives (comments/events) — aucun service ni scheduler en
  plus. Pour une **boucle de convergence** (peer programming : deux rôles en
  parallèle puis réconciliation), la primitive est la lane review native :
  `kanban request-review [--reviewer <profil>]` passe la carte en `review`
  (dispatché si `kanban.review_dispatch`, défaut ON) ; `kanban request-changes
  <id> <raison>` la RENVOIE à l'implémenteur (review → todo, gating parents
  réappliqué) — c'est le « non, reprends » du cycle, pas un statut à inventer.
  Plafonds de parallélisme : `kanban.max_in_progress` (global) et
  `kanban.max_in_progress_per_profile` (sinon N boards multiplient le budget).
- **Deux cartes partagent un worktree par IDENTITÉ DE BRANCHE, pas par chemin.**
  Vérifié dans `kanban_db_workspace.py` : le resolver fait
  `if actual_branch == branch_name: return <chemin>, branche` — donc deux cartes
  qui déclarent le MÊME `--branch` réutilisent le même worktree, alors qu'une
  branche DIFFÉRENTE le fait retomber **silencieusement** sur un worktree propre à
  la carte (`<repo>/.worktrees/<task-id>`, branche `wt/<task-id>`) sans aucun
  avertissement : le peer programming devient du travail isolé et les cartes ne
  partagent plus rien. Règle : **une branche par ISSUE**
  (`wt/issue-<n>-<slug>`, jamais dérivée de l'id de carte), déclarée une fois dans
  le manifeste de graphe et répétée sur TOUTES les cartes de la slice ; vérifier
  après déploiement que deux cartes sœurs ont le même `workspace_path` ET le même
  `branch_name` (`kanban show <id> --json`) et qu'un seul worktree existe côté git
  (`git worktree list | grep -c`). Conséquence de conception : un seul worktree par
  issue ⇒ les slices qui se recouvrent sont SÉQUENTIELLES — le parallélisme réel
  n'existe qu'entre slices aux composants disjoints.
- **La couverture se mesure sur le périmètre de la carte, pas sur tout le repo.**
  Un seuil global par fichier (ex. vitest `thresholds.perFile`) échoue sur du code
  que la carte n'a pas touché : le worker se retrouve bloqué pour un travail qui
  n'est pas le sien. Le gate d'une carte se scope à SES fichiers (liste du diff
  `git diff --name-only <base>...HEAD` croisée avec le rapport de couverture) ;
  garder en plus un seuil global comme garde-fou anti-régression, mais il ne
  conditionne pas la carte. Et les **cas limites sont des tests de première
  classe** au même titre que le nominal : nominal + limite + erreur, sinon la
  spec est incomplète (pas « plus petite »).
- **Ne JAMAIS retaper un secret lu dans un fichier de config.** Les outils de
  lecture masquent les clés (`sk-…`) : la valeur affichée n'est pas la valeur réelle,
  et la recopier « en la complétant » produit un 401 (`token_not_found_in_db`)
  découvert seulement au premier vrai run. Un nouveau profil copie donc la config
  du profil source par PROGRAMME (lire le YAML, écrire le YAML — la clé traverse sans
  être affichée), jamais par réécriture manuelle.
- **Un profil neuf n'hérite de rien : dupliquer la config du profile source.**
  Le provider doit être réécrit avec ses DEUX clés (`model.default` ET
  `providers.<nom>.default_model`) — sinon `hermes profile list` et le picker gardent
  l'ancien modèle. Les secrets d'un profil vivent dans SON `.env` (copier les clés de
  service nécessaires, ex. mémoire) ; les variables de plateforme (token de bot)
  ne se copient PAS — un token n'appartient qu'à un profil à la fois.
- **Vérifier une affirmation AVANT de l'écrire dans un plan ou une spec.** Un
  plan destiné à un implémenteur sans contexte propage toute erreur : chaque
  chemin, comptage et nom de clé cité doit être relu à la source au moment de
  l'écrire (les chiffres dérivent : un `.env` de profil, un regex de linter, une
  version épinglée dans un lock). Même règle pour un plan qui cite un
  comportement de l'environnement : le lire dans le code, pas de mémoire.
- **`~` peut pointer ailleurs que le HOME attendu.** Certaines commandes tournent
  dans un contexte dont `$HOME` diffère (session sandboxifiée) : `ls ~/.hermes/...`
  renvoie « no such file » alors que le pipeline est intact. Avant de conclure à
  une disparition, vérifier `echo "HOME=$HOME user=$(whoami)"` et `pwd` ; utiliser
  des chemins absolus (`/home/<user>/.hermes/...`) dans les scripts et vérifications.
  Un répertoire « disparu » est presque toujours un changement de contexte, pas une
  suppression.
- **Mémoire par projet ≠ banque par profil (exigence user).**
  `bank_id_template` `{workspace}` rend une constante ("hermes", forcée dans
  agent_init.py) et les tools hindsight_* n'ont pas de paramètre bank :
  l'isolation par projet d'un pipeline multi-profils = banque partagée + tags
  `project:<slug>` obligatoires sur chaque retain (le recall reste au niveau
  banque ; le filtrage par tags passe par l'API REST memories/list, pas par le
  tool). La mémoire d'un pipeline ne doit jamais dépendre du profil qui
  tourne — elle vit par projet.
- **Worktree cross-profil : éviter `--project`.** Il résout le repo via le
  projects.db du HOME du profil — un worker spawné sous un autre profil ne le
  voit pas. Ancrer explicitement : `--workspace worktree:<chemin-absolu-repo>`
  ou `hermes kanban boards set-default-workdir <slug> <chemin>` (anchor par
  board, lisible par tous les profils ; la base = upstream tip du checkout
  anchor → cloner l'anchor SUR la branche de base voulue, ex. dev).
- **Le verrou dispatcher (`.dispatcher.lock`) est par machine, pas par
  profil.** Au (re)démarrage des gateways il peut basculer vers un autre —
  l'event `claimed {'lock': ...}` dit qui spawne réellement. L'auto-assign
  `kanban.default_assignee` du PROFIL DISPATCHER peut écraser l'assignee d'une
  carte importée : vérifier l'assignee de la racine après déploiement et
  `kanban reassign` si besoin (une carte assignée au mauvais profil est
  exécutée par ce profil quand elle devient ready).
- **Coût : les ticks ne consomment rien, le coût est par issue.** Crons
  `--no-agent`, dispatcher kanban et plugins à handlers déterministes
  n'appellent jamais le LLM (tick muet = 0 appel) ; le coût se concentre dans
  les runs workers (~7-10 par issue traitée, cache prompt ≥90 % observé) et
  l'aux LLM du decompose. Un pipeline au repos coûte zéro.
- **Un token Discord n'appartient qu'à un profil à la fois.** Déplacer un bot
  vers un autre profil = arrêter le gateway de l'ANCIEN profil avant de poser
  le token dans le nouveau .env — deux profils vivants avec le même token
  refusent le démarrage du gateway (duplicate credential). Les listeners
  `on_interaction` (boutons) vivent sur le gateway qui porte le token : après
  un déménagement, réinstaller le plugin sur le nouveau profil, sinon les
  clics sont inertes (fallback : texte « go » dans le thread ou CLI unblock).

## Recette : pattern scrum orchestrateur

1. **Entrée** : carte assignée au profil scrum (dispatcher spawn) OU discussion
   Discord (cron/webhook du profil scrum surveille — le board n'ouvre rien
   tout seul : `kanban_create` + `assignee` engagent un worker).
2. **Grooming** : ≤3 questions à la fois en `kanban_comment` + `kanban_block` ;
   l'humain répond puis `unblock` ; au respawn le worker relit TOUT le fil.
   Alternative conversationnelle : room/DM + `@user` (escalade).
3. **Split** : `kanban_create` enfants (un par domaine) + `kanban_link
   parent→enfant`, assignee = profil spécialiste. Même board + liens
   (recommandé : promotion auto + graphe de dépendances visible) ; board
   séparé seulement pour isoler réellement un domaine.
4. **Cascade** : done du parent → enfants `todo→ready` au PROCHAIN tick du
   dispatcher. Accélérer : hook sur les events kanban ou `hermes kanban
   dispatch` manuel. Un worker peut créer des sous-enfants (profondeur libre —
   pas de max_spawn_depth côté kanban).
5. **Itération/consolidation** : avis rapide DANS un run = `delegate_task`
   (éphémère) ; avis durable = carte. Critère de stabilisation écrit dans le
   SOUL/prompt de l'orchestrateur ; consolidation = `kanban_complete
   (artifacts=[...])` — copiés en stockage durable avant nettoyage du scratch.

## Pièges

- **`default_assignee` vide = le profil du DISPATCHER devient l'assignee.**
  Vérifié dans la source : `kanban_decompose._resolve_profile_from_cfg` retombe sur
  `get_active_profile_name()` quand `kanban.default_assignee`/`orchestrator_profile`
  sont vides — donc le profil qui EXÉCUTE le dispatcher (gateway embarqué) s'attribue
  les cartes. Symptôme vécu : cartes « créées par auto-decomposer » assignées à un
  profil métier sans rapport (example-local) sur un board dédié à un autre pipeline.
  Fix : poser `kanban.default_assignee` + `kanban.orchestrator_profile` dans le profil
  QUI DÉTIENT LE DISPATCHER (pas seulement dans le profil du pipeline), et
  `kanban.auto_decompose: false` (défaut = True). Vérifier le log gateway :
  `kanban dispatcher: default_assignee='<profil>'`.
- **Garde-fou d'admission (isolation de board).** Quand un board doit être réservé à
  une liste d'assignees, la config ne suffit pas (elle se re-perd : autre gateway,
  config recréée). Script de garde branché sur DEUX hooks :
  `on_kanban_dispatch_tick` (tire APRÈS relâchement du `_dispatch_tick_lock` → peut
  bloquer sans deadlock, et la carte n'est pas claimée au tick suivant) +
  `kanban_task_claimed` (tire après le claim, donc AVANT le spawn mais SANS pouvoir
  annuler le claim courant : signaler seulement). Ne jamais tenter un `kanban block`
  bloquant depuis `kanban_task_claimed` en croyant annuler le spawn — il a déjà eu lieu.
- **Nettoyer sans perte : prouver que le travail est déjà ailleurs avant de
  supprimer.** Avant de supprimer worktrees/branches qu'on croit obsolètes,
  vérifier pour chacun que la branche est DÉJÀ dans la base (ancêtre —
  `git merge-base --is-ancestor origin/<wt> origin/dev`) ET que l'arbre est propre
  (`git status --porcelain`). Un worktree « terminé » peut porter des commits non
  poussés. Après MERGE humain, la branche distante survit au cleanup kanban :
  `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branche>`.
- **Casser les liens AVANT d'archiver des cartes parasites.** L'auto-decompose
  chaîne ses enfants comme PARENTS de la racine importée : archiver l'enfant ne
  délie pas la racine, qui reste `todo` en attente d'un parent archivé — elle ne
  se réveillera jamais. Ordre : `kanban unlink <parasite> <racine>` (et entre
  parasites), puis archiver les parasites, puis remettre la racine dans son état
  de départ pour repasser par le pipeline. La seule transition retour vers
  `triage` est un UPDATE direct en base (`kanban promote`/`specify` ne font pas
  triage ← todo) — c'est acceptable pour une remise en état, à documenter sur la
  carte par un commentaire.
- Déclarer tout nouveau type de carte DANS le gate d'admission avant de
  créer — sinon un crash rate-limit 429 se déclare en `protocol_violation` et
  bloque faussement le pipeline (le gate refuse, pas le travail).
- Les workers ne se spawnent pas entre eux : "l'architecte délègue" = il crée
  des cartes liées et le DISPATCHER spawn. Le flux de données passe par le
  board (comments/attachments), jamais par la mémoire du parent — c'est ce qui
  rend la cascade durable et crash-safe.
- Changer le modèle d'un profil ne corrige ni les runs en vol ni les cartes
  portant un `workflow_template_id` (modèle forcé par étape par le moteur
  custom) : patcher aussi les YAML et redispatcher les cartes non terminées.
- Les hooks kanban sont des observers : exit code ignoré, l'influence voyage
  par les commentaires/cartes.

## Cycle de vie d'une room (exploitation)

- **Cycle de vie d'une room = 4 états + un marqueur sur la carte.** Le moteur ne connaît
  aucun lien vers une carte : le lien room↔ticket se porte par un marqueur `ROOM: <room_id>`
  dans le body de la carte (posé à la création — `kanban edit` refuse les cartes actives,
  donc migration en base pour l'existant). Cycle : `ensure` (création) → `ask` (animation) →
  `report` (transcript → `kanban_comment`) → `disband`. L'état se lit par les events :
  une discussion est FINIE quand un event `room.activity` porte `status` ∈ {settled, bounded}
  pour son `discussion_event_id` (`bounded` = plafond 3 rounds / 10 messages atteint).
- **Règles de sûreté du cycle (sinon on perd du travail ou on sature).** (1) `ask`
  uniquement si la room est VIDE (users=0) et la carte active — ré-animer une délibération
  en cours la ferait repartir de zéro. (2) `disband` uniquement après `report` : dissoudre
  une délibération non reportée perd le travail des agents. `pending` (délibération en cours)
  n'est JAMAIS touché — la reporter à mi-parcours tronquerait le débat. (3) une room VIDE
  sur une carte finie se dissout directement (rien à préserver) — sinon ces rooms consomment
  un slot `MAX_ACTIVE_ROOMS` à vie.
- **Un `room_id` dissous est RETIRÉ DÉFINITIVEMENT** (`hosted_room_retired_ids`,
  `create_room` lève `RoomConflictError: room_id belongs to a disbanded room`). Ce n'est pas
  un bug : un id dissous ne doit jamais reprendre un ancien historique. Conséquence : une
  automatisation de cycle doit traiter cette erreur comme terminale (ignorer la room), jamais
  réessayer en boucle. Corollaire : ne pas dissoudre à la légère — c'est irréversible.
- **Un gate/parseur qui cherche un marqueur doit le trouver PARTOUT dans le body.** Un regex
  ancré `^MARQUEUR: (\S+)$` en MULTILINE rate le cas réel où le marqueur est noyé dans une
  ligne (carte créée sur une seule ligne) : l'automatisation devient muette sans erreur.
  Chercher `MARQUEUR:\s*(\S+)` sans ancre — et tester ce cas (régression vécue).

- **Un livelock de room doit être détecté et coupé, sinon la carte meurt avec lui.** La
  contention multi-gateway produit un état stable-non-progressif : le gateway gagnant du lease
  marque la tâche `running` d'un autre `indeterminate`, la réconciliation ne peut pas la
  récupérer et la **diffère** en série (`turn.deferred`, `reason=member_unavailable`), pendant
  que `plan_next_task` continue de répondre `task/member_turn` — donc le moteur relance
  indéfiniment et la carte reste `running`. **Signature de détection : ≥2 `turn.deferred`
  consécutifs avec `reason=member_unavailable` en fin de journal, sans aucun `message.member`
  entre eux.** Compter les defer CONSÉCUTIFS, pas le total (une longue délibération en compte
  beaucoup, légitimement) et réinitialiser sur tout `message.member`/`turn.settled` (progrès
  réel). Un seul defer ne suffit pas à couper (incident transitoire).
- **La sortie d'un livelock est `request_room_stop` (fence `room.stop_requested`), pas un
  kill.** `gateway.hosted_rooms.request_room_stop(db, room_id=…, cancel_id=…,
  expected_gateway_id=…, expected_epoch=…)` : `_pending_discussion` ignore alors tout
  `message.user` de seq ≤ au dernier stop, donc la délibération bloquée est réputée close et
  `plan_next_task` retourne `idle`. Vérifier après coup que le plan est bien `idle` — c'est la
  seule preuve que le livelock est rompu. Tracer l'arrêt automatique sur la carte
  (commentaire + marqueur dédié) : un arrêt déclenché par une machine doit rester auditable.
  Attention : un nouveau `message.user` postérieur relance une délibération — c'est voulu.
- **Un worker de carte ne peut pas « rendre la main » : il peut vivre en zombie.** Constaté :
  un worker kanban ayant livré ses artefacts continue ses appels LLM en boucle (80 appels,
  150 k+ de contexte) et son process apparaît `Zs [hermes] <defunct>` — donc `ps -p <pid>`
  répond **présent** alors qu'il est mort. Toujours filtrer `grep -v defunct` avant de
  conclure qu'un worker tourne. Réparer une carte bloquée en `running` : arrêter le process,
  `kanban reclaim <id>` (libère le claim, la carte repasse `ready` et est respawnée avec tout
  le contexte des commentaires — dont le report de room).

- **Un pont qui importe « toute issue ouverte » fabrique des graphes en double.** Sans gate
  de couverture, une demande de modification déposée en NOUVELLE issue repart en graphe neuf
  complet (t1..t5) alors que la livraison est en vol. Vécu : 3 issues (#4, #9, #10) pour un
  seul changement, ~776 min d'agent brûlées pour conclure « redondante avec #4 ». Le gate se
  pose AVANT l'import et combine deux signaux : (1) références `#N` dans le body de l'issue
  (hors URL, hors nombres nus), (2) recouvrement de titre (Jaccard) contre les issues ayant
  une PR ouverte ou un graphe. **Le gate ne tranche pas** : il commente l'issue avec les deux
  issues possibles (rattacher / assumer) et laisse l'humain décider — un blocage silencieux
  serait pire que le doublon.
- **Détecter « issue couverte » demande DEUX sources : le lien natif GitHub ET la convention
  de branche.** `closingIssuesReferences` est vide dès que la PR omet `Closes #N` — vérifié
  sur une PR réelle du pipeline. Sans le repli sur `feat/issue-<n>` dans `headRefName`, le
  gate laisse tout passer. Et sans `Closes #N` dans les cartes t6, GitHub ne rattache jamais
  la PR à l'issue : la fermeture ne dépend plus que du pont, donc toute issue ouverte sur le
  même sujet repart en graphe neuf.
- **Le grill-me doit QUALIFIER l'ambiguïté, pas convoquer l'humain.** Deux productions
  obligatoires : (1) un quadrant par ambiguïté — *levable sans humain ? comment ? **coût si
  non levée ?*** ; une ambiguïté levable dans le code/la mémoire/la doc se lève seule ; (2) un
  verdict machine-lisible (`PROTOTYPE:`/`AMBIGU:`/`ARTEFACT:`) repris par les étapes aval.
  `PROTOTYPE: oui` seulement si ambiguïté non levable sur un livrable **perceptible**, ou
  périmètre > 3 slices sur un domaine qui « se voit », ou rejet humain antérieur sur le sujet.
  Sinon `PROTOTYPE: non` — le cas normal. Exiger un prototype à chaque ticket est aussi nocif
  qu'un tunnel : ça ajoute un gate humain là où il n'y a rien à arbitrer.
- **Un seuil de « trop de travail avant le premier jugement » doit être MÉCANIQUE.** Quand le
  livrable est perceptible (visuel/UX/texte lu), l'artefact le moins cher (maquette, planche,
  capture, schéma) se valide AVANT les slices de production : `prototype_required: true` dans
  le manifeste de graphe + une slice `preview` en PREMIÈRE position, parente de toutes les
  autres, refusée par le validateur si absente ou mal placée (`exit 1`). Vécu : ~55 h d'agent
  et +5 355 lignes produits avant le premier regard humain, jugement négatif.
- **Ne jamais câbler un exécutable sur un chemin en dur.** `shutil.which(gh) or "/usr/bin/gh"`
  a produit `FileNotFoundError` (gh vit dans `~/.local/bin`) dans tous les subprocess sans PATH
  interactif — crons et kernels Python notamment ; le bug ne se voit qu'hors shell de login.
  Résoudre par `which` puis une liste de candidats vérifiés (`isfile` + `X_OK`), jamais par
  défaut absolu.

## Room vs board (Bot Mode group chats)

- Room (group chat 2-6 bots) = délibération : @mention déclenche ≤3 rounds ×
  ≤10 msg/round, un bot peut passer sans répondre, `@user` escalade à l'humain
  (badge needs-you). Chaque membre garde une session persistante
  `Group: <name>` ; la room est durable si tous les membres partagent un
  gateway.
- **Le moteur de room est dans le GATEWAY, pas dans le desktop — une room se
  crée et se pilote en ligne de commande.** Le desktop n'est qu'un client : il
  n'existe aucune sous-commande CLI `hermes groups`, mais tout passe par
  l'API bas niveau `gateway.hosted_rooms` (voir ci-dessous). Ne pas conclure
  « hors périmètre » parce que le CLI n'expose rien.
- **Bornes réelles (lues dans le code, ≠ doc) :** `MAX_ACTIVE_ROOMS=256`
  (rooms actives par hôte), `validate_roster` impose **2-6 membres**
  (`MIN/MAX_DISCUSSION_MEMBERS`), `MAX_DISCUSSION_ROUNDS=3`,
  `MAX_DISCUSSION_MESSAGES=10`, `max_concurrent_rooms=4` (délibérations
  simultanées). Le « 2-6 » de la doc est donc bien la limite métier, pas une
  limite d'UI ; les 128 membres du schéma sont une borne bas niveau.
- **Une room n'est structurellement liée à AUCUNE carte.** La table
  `hosted_rooms` n'a ni `task_id` ni `issue` (le `task_id` visible ailleurs est
  un identifiant de TOUR de parole, table `hosted_room_remote_runs`). Le lien
  room↔ticket est une convention de nommage (`pj-<repo>-issue-<n>`) — donc
  retrouvable sans table de mapping, mais qu'un renommage casse.
- **Créer une room depuis un script (API bas niveau) :**

  ```python
  import sys; sys.path.insert(0, "${HOME}/.hermes/hermes-agent")
  from gateway import hosted_rooms as hr
  hr.create_room(hr.default_db_path(), room_id="pj-repo-issue-8", name="pj repo #8",
      members=[{"member_id": p, "profile": p, "handle": p} for p in PROFILS],
      authority_gateway_id=hr.local_authority_gateway_id())
  ```

  - Roster : exactement `{member_id, profile, handle}` (+ `display_name`,
    `target` optionnels) — un champ en trop est refusé (`_exact_fields`). Les
    profils doivent être **locaux au gateway** (`~/.hermes/profiles/`).
  - `disband_room(db, room_id=…, expected_gateway_id=…, expected_epoch=…)` :
    l'epoch est **obligatoire** (tombstone idempotente).
  - Lecture : `list_rooms(db)` / `room_state(db, room_id=…)` /
    `read_events(db, room_id=…)`. ⚠️ `read_events` renvoie un **dict** avec la
    clé `events` (pas une liste) ; `get_room` et `list_events` n'existent pas.
  - Pas besoin de `wakeup()` : `bindings()` relit la base à chaque cycle
    (poll 5 s / 0.25 s actif) et la boucle découvre seule la room créée.
- **Les bots ne parlent JAMAIS spontanément : il faut poster un `message.user`.**
  `plan_next_task` reste `idle` (« no_pending_user_event ») — une room créée
  reste muette indéfiniment. Déclencheur (payload EXACT `{text, thread_id}`) :

  ```python
  hr.append_event(hr.default_db_path(), room_id=rid, event_id=f"ev-{rid}-{tid}",
      kind="message.user", actor={"kind": "user", "id": "pj-master"},
      payload={"text": "…", "thread_id": tid},
      authority_gateway_id=hr.local_authority_gateway_id(), authority_epoch=1)
  ```

  Round 1 = les membres mentionnés (aucune mention = tous) ; rounds 2-3 = opt-in
  (un pair cité qui n'a pas encore parlé).
- **⚠️ Piège multi-gateway : la base des rooms est PARTAGÉE par tous les profils.**
  `default_db_path()` = `~/.hermes/shared-state.db`, quel que soit le profil
  (délibéré : éviter que les gateways de profil écrivent dans `state.db`). Et
  **chaque gateway démarre son worker de room**, sans levier de désactivation.
  Conséquence vécue : avec plusieurs gateways actifs, ils se disputent le lease
  de room (`lease_ttl_seconds=30`) et le gagnant marque `indeterminate` toute
  tâche `running` sans sa propre fence (variable `foreign_running`,
  `hosted_room_driver.py`) — une délibération peut donc partir en
  `indeterminate`. **Ce n'est PAS auto-réparateur** : la réconciliation ne peut pas
  récupérer le tour d'un autre processus, elle le « defer » avec
  `reason='member_unavailable'` toutes les ~60 s — tant que le lease circule, le cycle
  `indeterminate → deferred → retry` tourne indéfiniment et la délibération ne progresse
  plus. Le lease garantit l'exclusion mutuelle (aucun doublon d'`event_id`) mais **pas la
  progression**. Sortie de secours : `request_room_stop` (fence `room.stop_requested`),
  qui supersède les tours antérieurs et fait repasser le planificateur à `idle` — préférer
  cette fence à un kill. Régime sûr : **une seule délibération active** quand plusieurs
  gateways tournent. Diagnostic chiffré (compteur `lease_generation`, nombre de
  `run_process_generation` distincts) et mécanisme complet :
  `references/hosted-rooms.md`.
- Board = engagement : décisions, artifacts, statuts, audit. Le bot pivot
  (scrum) participe à la room ET porte les tools kanban_* : il écrit les
  conclusions en `kanban_comment`. Une room ne remplace jamais le board comme
  source de vérité.
- `message_agent` (DM bot↔bot, fire-and-forget) n'existe que dans le canonical
  Bot Chat — en room, @mentionner suffit.
- Coût : la room fait tourner plusieurs bots par échange ; le board un worker
  à la fois. Délibérer en room, livrer au board.

## Voir aussi

- Skill `hermes-kanban-multiagent-pipelines` : activation des deux couches
  (board Desktop = toggle Capabilities, tools = clef racine `toolsets`),
  et son `references/activating-kanban.md` pour le diagnostic « qui tient le
  verrou dispatcher » (`fuser -v ~/.hermes/kanban/.dispatcher.lock`).
- `kanban-gate` : protocole worker pour lire/agir sur le verdict `[gate]`.
- `gh-kanban-bridge` : pont GitHub↔kanban + le glue custom (workflows YAML).
- Skill bundled `hermes-agent` : routing table vers la doc officielle.
- `references/kanban-builtins.md` : table des transitions + mécanique rooms.
- `references/hosted-rooms.md` : API bas niveau des rooms (signatures, bornes réelles,
  kinds d'events, base partagée), cycle de vie, et diagnostic du livelock multi-gateway
  (compteur `lease_generation`, fence `request_room_stop`).
- `references/issue-pipeline.md` : pipeline complet issue GitHub → PR — import
  en triage, deployer mécanique, gates humains block/unblock, submitted/PR,
  contrat de format des cartes (5 sections + BDD + DoR/DoD + INVEST).
- `pj-pipeline/references/graph-manifest.md` : schéma du manifeste de graphe
  (`slices.json`) et les règles que son validateur doit refuser — le pendant
  concret de la règle « le graphe se construit mécaniquement ».
- `scripts/kanban_card_lint.py` : linter déterministe 0-LLM du contrat de format
  des cartes (sections, BDD, DoR/DoD, garde-fous, dimensionnement) — exit 1 si
  non conforme ; à appeler AVANT un gate humain de validation.
- `scripts/pj_repo_watch.py` : watcher d'onboard automatique des nouveaux repos
  (copie live dans le scripts/ du profil orchestrateur), onboard en 2 phases.
- Le scheduler cron résout `--script` dans le scripts/ DU PROFIL
  (`~/.hermes/profiles/<nom>/scripts/`), pas `${HERMES_WORKFLOW}/pipeline/` (qui n'est que le cas
  du profil default) — y copier les scripts (pas de symlink, refusé par realpath).
  Un script au mauvais endroit = échec silencieux répété `Script not found` : les ticks
  d'un cron no-agent se ressemblent tous, donc VÉRIFIER `Last run: ok` dans
  `hermes cron list` après création (sinon croire à tort que l'automation tourne).
  Un stdout vide n'est PAS la preuve qu'un cron fonctionne.
- Allowlist d'un bot-profil (`DISCORD_ALLOWED_USERS=<discord_user_id>`) : sans elle
  l'humain est ignoré en silence, et un handler de bouton fail-closed rejette le clic sans
  message. Vérifier l'ID réel via `/guilds/<id>/members` de l'API Discord, pas de mémoire.
- **Le bridge est paramétrable par env — une seule copie sert N projets.**
  `GH_REPO` + `KANBAN_BOARD` + `KANBAN_ASSIGNEE` (+ `BOT_GRACE_SECONDS`, et un flag pour
  importer en `triage` au lieu de `ready`). Deux repos sur le MÊME board se collisionnent :
  la clé d'idempotence est `gh-issue-<n>`, numérotée par repo → 1 board par repo. Un
  `BOT_GRACE_SECONDS` par défaut réserve les issues fraîches à un bot de triage : le mettre
  à 0 sur les boards sans bot, sinon les nouvelles issues semblent ignorées pendant 10 min.
  Un repo vide (aucun commit) n'est ni clonable ni branchable — l'import d'issues peut
  toutefois tourner (cartes en attente) : découper l'onboard en deux phases (board+crons
  dès la création du repo, branche+clone au premier commit).
- Auto-onboard des nouveaux repos : watcher déterministe (copie live
  `scripts/pj_repo_watch.py`, cron */10 sur le profil orchestrateur) —
  détecte tout repo non archivé sans board `pj-<slug>` et déroule les
  4 étapes d'onboard (branche dev, clone anchor, wrappers, crons) puis pose
  le board EN DERNIER comme marqueur de complétion ; idempotent, repo vide
  = différé au premier commit, retry au tick suivant sur échec.
