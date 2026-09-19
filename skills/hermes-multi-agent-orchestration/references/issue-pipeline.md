# Pipeline issue GitHub → PR multi-agents (pattern pj)

Classe : un orchestrateur (profil bot Discord, ex. pj-master) + workers (ex.
pj-dev) transforment chaque issue GitHub en spec validée puis en PR. Mémoire
partagée (banque unique + tags `project:<repo>`), jamais liée au profil.

Validé E2E de bout en bout : import → t1..t5 → go humain → phase dev →
t6 → PR ouverte (sans merge) → issue fermée par le pont push.

## Infrastructure par repo (une fois)

1. Branche de base `dev` sur le repo distant : `git push origin
   origin/<main>:refs/heads/dev` (depuis un checkout local) ou sans checkout
   `gh api -X POST repos/<owner>/<repo>/git/refs -f ref=refs/heads/dev -f
   sha=<sha de la branche main>`.
2. Clone anchor SUR dev : `git clone --branch dev <url> ~/pj-repos/<repo>` —
   le resolver worktree branche depuis l'upstream tip de CE checkout, donc
   l'anchor doit être posé sur la branche de base voulue (jamais un checkout
   principal sur une autre branche).
3. `hermes kanban boards create pj-<repo>` puis
   `hermes kanban boards set-default-workdir pj-<repo> ~/pj-repos/<repo>` :
   les cartes `--workspace worktree` atterrissent dans `<repo>/.worktrees/<id>`
   sans projects.db — donc lisibles par tous les profils du pipeline.
4. Wrapper pont `${HERMES_WORKFLOW}/pipeline/pj_bridge_<repo>.sh` : exporter PATH avec
   ~/.local/bin (le scheduler cron ne voit pas gh), puis `GH_REPO`,
   `KANBAN_BOARD=pj-<repo>`, `KANBAN_ASSIGNEE=<orchestrateur>`,
   `BOT_GRACE_SECONDS=0` si aucun bot de drill ne dessert le repo,
   `PJ_IMPORT_TRIAGE=1` (import en triage — la racine ne doit jamais être
   claimable comme worker) ; `exec python3 <repo canonique>/pipeline/
   gh_kanban_bridge.py "$@"`.
5. Cron `--no-agent` */5 par repo, créé SUR LE PROFIL ORCHESTRATEUR (HERMES_HOME
   du profil) ; stdout vide = tick muet.

## Déployeur du graphe (script déterministe, cron no-agent)

Racine importée en triage → script SANS LLM :
- déduit repo + n° d'issue de la ligne `Importé depuis <url issue>` du body
  (skip sinon) ; idempotence : skip si enfants déjà présents ou event
  `decomposed` ; idempotency-key par étape `<prefix>-t<k>-<repo>-<n>`.
- crée t1 worktree (`--workspace worktree`), t2 mémoire, t3 grill-me,
  t4 draft, t5 validate — toutes `--assignee <orchestrateur>`, bodies
  autoporteurs (le worker relit carte+fil, pas la mémoire du parent).
- liens (l'enfant attend le parent) : t1,t2,t3 parents de t4 ; t4 parent de
  t5 ; chaque t_i PARENT de la RACINE (elle se réveille quand tout est done).
- sort du triage via `kb.specify_triage_task` (import Python direct du module
  hermes_cli ; le CLI `kanban specify` passe par le LLM aux ; `kanban promote`
  refuse le statut triage).
- Cron `--no-agent` */5 SUR LE PROFIL ORCHESTRATEUR : wrapper bash par board
  qui exporte `PJ_BOARD=pj-<repo>` puis exec le deployer — le scheduler ne
  partage pas l'env interactif, l'env du job se pose dans le wrapper.

## Gates humains (block/unblock)

- t3 grill-me : worker crée le thread Discord de l'issue
  (`discord_thread.py create <channel> "Issue #N" "..."`), pose ≤3 questions
  (1/message), résume dans la carte, `kanban_block` (attente réponse humaine).
- L'humain répond dans le thread → `hermes kanban unblock <id>` → re-spawn :
  le worker relit TOUT le fil + les réponses, puis `kanban_complete`.
- t5 validate : worker met à jour l'issue (`gh issue edit N --body` — spec avec
  réf. de code vérifiées dans le worktree), notifie Discord (boutons go/no-go),
  `kanban_block` jusqu'au go explicite. Jamais d'auto-validation.

## Contrat de format des cartes (exigence user, généralisable)

Toute carte qui spécifie ou implémente (pas les cartes de process) porte 5 sections
numérotées dans l'ordre — c'est ce qui rend une spec relisible par un worker qui n'a
pas la conversation :

1. **Contexte & Objectif** — source (issue #N), valeur, objectif = RÉSULTAT observable
   (« l'utilisateur peut X », pas « travailler sur X »), dépendances amont/aval.
2. **Critères d'acceptation (BDD/Gherkin)** — `Fonctionnalité:` + ≥2 `Scénario:`
   (nominal + limite/erreur), étapes Étant donné/Quand/Alors ; chaque critère
   automatisable (sinon l'écrire et dire comment il sera vérifié).
3. **DoR & DoD** — DoR : spec validée, worktree prêt, parents done, aucune question
   ouverte (sinon `kanban_block`, jamais démarrer « en attendant »). DoD : critères
   couverts par tests verts, checks du repo verts, commits poussés, handoff écrit,
   artifacts, mémoire projet mise à jour.
4. **Considérations techniques & garde-fous** — fichiers/contrats touchés, contraintes,
   interdits explicites, risques + repli.
5. **Hors-scope** — ce que la carte ne fait pas ET où le sujet est traité.

Dimensionnement **INVEST** explicite, parce qu'un worker est one-shot et qu'une carte
fourre-tout ne se reprend pas : 1 slice verticale = 1 carte ; Independent (dépendance =
lien parent explicite, jamais implicite) ; Valuable (démo ou test E2E possible) ;
Estimable (sinon carte « spike ») ; **Small ≤ ~1 j d'agent / ≤ ~400 lignes / ≤ ~5
fichiers / 1 seul domaine — dépassement = découper AVANT de créer** ; Testable. Une
sous-carte référence la mère (« issue #N, slice k/N ») et porte son PROPRE bloc
Gherkin/DoR/DoD.

## Extensions du graphe : rôles spécialisés (test, doc, archi)

Un pipeline à un seul worker « dev » se généralise en ajoutant des cartes par rôle,
sans nouveau moteur — même mécanique parent/enfant, mêmes gates.

**Le graphe de dev doit être MÉCANIQUE, pas construit par le LLM.** Faire créer t6 et
ses enfants par le worker validate a produit des dérives réelles (cartes fantômes,
liens inversés, assignees hors pipeline). Pattern retenu : le worker t5 écrit un
manifeste JSON d'artefact (`specs/<n>/slices.json` sous le dossier DU BOARD) qui
valide ses entrées, puis un script déterministe 0-LLM (cron `--no-agent`) lit ce
manifeste et construit t6 + toutes les cartes + TOUS les liens. Le graphe devient
reconstructible, relisible et testable à blanc (`PJ_DRY_RUN=1` imprime le plan sans
rien créer). Un manifeste invalide → `request-changes` sur t5 : la validation est un
gate, pas une politesse.

Ce que le validateur du manifeste doit REFUSER (chaque règle correspond à une dérive
qui a réellement atteint un board) :

- `issue` / `repo` absents, `slices[]` vide ;
- `k` non contigus depuis 1 (trou = carte jamais produite) ;
- `depends_on` contenant une valeur ≥ `k` — une slice ne peut pas dépendre d'elle-même
  ni d'une slice aval (dépendance inversée = attente mutuelle) ;
- **`branch` absente ou divergente entre slices** : c'est elle qui fait partager le
  worktree (voir plus bas) ; un manifeste sans branche unique produit un lot
  « parallèle » qui ne partage rien ;
- une carte `test` sans ses **trois natures de scénario** (nominal + cas limite +
  erreur) : deux scénarios suffisent à une carte ordinaire, pas à une carte de test —
  c'est la règle qui rend les cas limites opposables ;
- toute carte `parallel` vide (un rôle annoncé mais aucune carte).

**Un assignee PAR DÉFAUT posé sur le constructeur s'applique à TOUTES les cartes qu'il
crée.** Le script écrit pour un orchestrateur crée par défaut des cartes d'orchestrateur :
la carte destinée au spécialiste est silencieusement assignée au mauvais profil (elle
est alors exécutée par lui, ou bloquée par le garde-fou d'admission — dans les deux cas
sans erreur ni avertissement). Chaque carte dont le propriétaire diffère du défaut doit
recevoir son assignee EXPLICITEMENT au moment du `create`. Vérification obligatoire APRÈS
un déploiement RÉEL, en relisant l'`assignee` de chaque carte (`kanban show <id> --json`) :
relire le script ne prouve rien, il est juste et le board faux.

**Topologie par slice, avec convergence :**
- les rôles d'une même slice tournent en parallèle quand ils sont indépendants
  (écriture de tests vs implémentation), puis une carte de convergence
  les réconcilie — `request-review` pour juger, `request-changes` pour renvoyer
  (boucle, pas échec) ;
- les rôles séquentiels restent chaînés par un lien parent (la doc après la
  convergence, la review après la doc) : c'est la dépendance qui porte l'ordre,
  jamais la confiance dans le prompt ;
- **une slice dépendante attend la CONVERGENCE de l'amont**, pas seulement sa
  carte d'implémentation : ses deux côtés (test et dev) prennent `conv-<amont>`
  en parent, sinon ils démarrent sur un état non réconcilié ;
- **anti-deadlock inchangé** : t6 et sa carte de clôture attendent (sont ENFANTS de)
  toutes les cartes d'implémentation ; aucune d'elles n'est enfant de t6 ;
- une carte de mémoire post-merge (alimenter la mémoire durable depuis la doc
  livrée) est PARENT de la racine et ENFANT de la carte de nettoyage : elle doit
  vérifier l'état réel de la PR avant d'agir, et `kanban_block` si le merge humain
  n'a pas eu lieu — sinon elle bloque la fermeture de l'issue pour toujours.

**Cycle de vie du worktree : une carte AMONT + une carte AVAL.** Pour un lot
parallèle, aucune des deux cartes sœurs ne peut créer le worktree sans courir
contre l'autre : une carte dédiée `worktree-mk` (assignée au rôle implémentation)
le crée et publie chemin+branche au blackboard ; toutes les cartes de slice en
dépendent. Symétriquement, une carte `worktree-rm` post-merge le supprime — elle
est enfant de t6, exige `gh pr view <url> --json state == MERGED` ET
`git merge-base --is-ancestor` sur chaque commit avant de supprimer, et
`kanban_block` sinon (le cleanup natif du kanban préserve de toute façon les
worktrees sales/unpushed, mais une branche distante survit au cleanup).

**Branche déterministe = partage du worktree.** Le resolver compare la branche de
la carte à celle du worktree visé et retombe SILENCIEUSEMENT sur un worktree propre
à la carte si elles diffèrent : la branche est donc un identifiant de travail
partagé (`wt/issue-<n>-<slug>`), déclarée une fois pour l'issue et répétée sur
chaque carte — jamais un `wt/<task-id>`. Le manifeste de graphe porte une clé
`branch` unique, et le script de construction l'ajoute à chaque `kanban create` de
carte en worktree (`if card.get("branch"): args += ["--branch", card["branch"]]`) :
sans ce `--branch`, les cartes sœurs ne partagent rien et le peer programming est
silencieusement décorrélé.

**Périmètres d'écriture disjoints par contrat.** Deux workers dans le même worktree
ne se gênent que si on le leur permet : le rôle test n'écrit QUE dans l'arborescence
de tests, le rôle implémentation QUE dans les sources, et le blackboard fige la clé
`contrat-<k>` (signatures d'API, chemins de tests) AVANT que l'un ou l'autre
n'écrive. Conflit ou doute → `kanban_block` sur la carte fautive, jamais un
`--force` ni un merge de branches parallèles.

**Rôle documentation — quatre phases, chacune une carte.** (1) en spec : cadrage
architectural (positionnement dans l'existant, croisement infrastructure /
fonctionnel / code, lecture SDD/DDD/TDD/hexagonal) en amont de la carte de draft ;
(2) en dev : vault versionné + doc in-code APRÈS la convergence de la slice ;
(3) en review : cohérence code ↔ doc ↔ objectif, verdict opposable (sortie du
linter de vault, pas une appréciation) ; (4) post-merge : alimentation de la
mémoire durable depuis le vault, idempotente par hash de contenu pour ne pas
ré-envoyer une note inchangée à chaque passage.

**Boucle de convergence : borner l'itération.** `request-changes` renvoie à
l'implémenteur autant de fois que nécessaire ; le garde-fou est le circuit breaker
natif (`consecutive_failures` / `kanban.failure_limit`, défaut 2) qui auto-bloque
et remonte à l'humain. Corollaire de rédaction : la carte de convergence doit
lister des écarts PRÉCIS et actionnables — une consigne « à refaire » consomme une
itération entière sans rien résoudre.

**Artefacts de spec hors du repo.** Un manifeste de graphe ou un cadrage destinés aux
workers (pas au produit) vont sous le dossier du board
(`~/.hermes/kanban/boards/<board>/specs/<n>/`), pas dans le dépôt : zéro bruit dans
les PR, et lisible par tous les profils. Ce qui est du livrable (vault de doc, ADR)
reste dans le repo, versionné avec le code qu'il décrit.

**Vault de documentation versionné.** Quand un rôle tient la doc, la rendre
vérifiable comme le code : frontmatter obligatoire, liens internes résolus par nom de
fichier, toute note référencée depuis son index (une note orpheline = une note perdue),
un linter déterministe dédié par-dessus la même règle « consigne seule → dérive ».

Mise en œuvre : le contrat est à la fois (a) écrit dans le SOUL de l'orchestrateur ET du
worker, (b) injecté dans les bodies que le deployer crée (sinon seules les cartes
DÉRIVÉES l'héritent), et (c) vérifié par un linter déterministe 0-LLM appelé avant le
gate humain (exit code) — la consigne seule dérive. Voir
`scripts/pj_card_lint.py` (copie live dans le scripts/ du profil orchestrateur).

## Go → phase dev

Au go, le worker t5 écrit le manifeste de graphe et le valide (section précédente) ;
un cron déterministe construit ensuite t6 « submitted » et l'ensemble des cartes de
slice avec leurs liens. Le worker ne crée AUCUNE carte de dev lui-même — c'est la
règle qui supprime les dérives de graphe.

**Anti-deadlock (invariant)** : t6 est créée avec `--parent <t5>`, puis chaque carte
de production (implémentation, convergence, doc, review) est liée comme PARENT de t6
(`link <carte> <t6>`) : t6 se réveille quand toutes sont done, et l'agrégateur n'est
JAMAIS parent de ses entrées. Une carte de production qui se retrouve ENFANT de t6 la
fait attendre indéfiniment.

Les cartes de slice : `--assignee <rôle> --workspace worktree --branch <branche
unique de l'issue>`, TDD + cycle de checks du repo (ex. Taskfile.ia.yml :
worktree:start → task:start → task:check → task:submit). Toutes les créations portent
une idempotency-key explicite (`pj-<clé>-<repo>-<n>`) — le constructeur est un cron
*/5 : sans clé, deux ticks proches dupliquent le graphe.
t6 réveillée : ouvre la PR (`gh pr create`), poste l'URL (commentaire carte +
issue + Discord), `kanban_complete` — ou `--completion-contract OWNER/REPO`
sur t6 si le repo a des checks requis. RACINE réveillée (tous t_i done) →
le pont push ferme l'issue avec le handoff du worker.

## Pièges opérationnels

- **Le verrou dispatcher peut être tenu par un autre profil — identifier AVANT
  de patcher.** Un dispatcher étranger applique SON `default_assignee` aux
  racines triage et aux enfants de son auto-decompose : le travail part hors
  graphe, **sans gate humain et sans notification Discord** (le contrat de
  notif dépend de t5, qui n'existe jamais). Le détenteur se lit dans l'event
  `claimed {'lock': '<host>:<pid>'}` d'une carte croisé avec `hermes gateway
  list` (`.dispatcher.lock` peut être vide). Détecter les fuites par lecture du
  board, jamais par confiance dans la provenance : `SELECT
  id,status,assignee,created_by FROM tasks WHERE assignee='<profil-étranger>'
  OR created_by LIKE '%decompos%'` ; toute carte d'un board `pj-*` doit avoir
  des parents du pipeline.
- **Arrêter un acteur hors pipeline = tuer PUIS neutraliser PUIS relire.**
  `kill` seul laisse la carte `running` avec un claim → respawn au tick
  suivant. Tuer les workers du profil (`ps -eo pid,args | grep 'hermes.*-p
  <profil>.*chat -q'`), vérifier qu'il n'en reste aucun, puis neutraliser
  chaque carte : `kanban block` est REFUSÉ selon le statut de départ
  (« cannot block » depuis `todo`), `reassign` marche depuis `todo` mais rend
  la carte spawnable par le nouveau profil (si l'arrêt doit être définitif :
  archiver). Terminer par une relecture du board : une carte neutralisée à
  l'affichage peut rester `ready`/`running`.
- Archiver une carte avec un run actif : `hermes kanban reclaim <id>` D'ABORD
  — sinon le worker en vol continue d'écrire (enfants/commentaires parasites)
  après l'archive.
- Après MERGE humain d'une PR : le cleanup kanban préserve le sale/unpushed
  mais ne supprime pas la branche distante — `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branche wt>`
  post-merge, sinon les branches wt/ s'accumulent sur le repo.
- Auto-onboard des repos suivants : watcher déterministe (copie live dans le
  scripts/ du profil orchestrateur, cron `--no-agent` */10) — détecte tout
  repo non archivé sans board `pj-<slug>` et déroule les 4 étapes
  idempotemment, board posé EN DERNIER comme marqueur de complétion ; repo
  vide = différé au premier commit (409 sur /commits) ; retry au tick
  suivant sur échec intermédiaire.
- Idempotency-key du pont = `gh-issue-<n>` SANS repo → 1 board par repo
  obligatoire (collision dès qu'un n° d'issue est partagé entre repos).
- Boutons Discord inertes après un déménagement de token : l'écouteur
  on_interaction vit sur le gateway de l'ANCIEN profil — le réinstaller sur
  le nouveau, sinon fallback texte « go » dans le thread ou CLI `unblock`.
- Vérifier le vivant après tout edit de config profil : `chat -q "PONG"` +
  `logs/agent.log` doit montrer `finish_reason=stop` — une 401 auth sort
  proprement, le banner CLI seul n'est pas une preuve.
- Les outils hermes-discord n'existent pas en session cron/CLI : les crons du
  bot passent par le helper REST discord_thread.py (create|send|threads),
  dont TOKEN_FILE doit pointer sur le .env du profil qui possède le token.
- Boutons décisionnels portables : plugin platform `pj-buttons` (profil
  orchestrateur, généralisé de gh-triage-buttons). Il doit accepter DEUX
  schémas de custom_id — `pj:<go|nogo>:<board>/<task_id>` (canonique) et
  `triage:<go|nogo>:<N>` (celui qu'émet le helper générique `discord_thread.py
  send --go-nogo <N>` : un worker one-shot appelle le helper tel quel) — et
  résoudre la carte cible CÔTÉ SERVEUR depuis le nom du thread
  (`<repo> #<N> · <titre>` → la carte `blocked` du board : validate/grill, pas
  la racine). ACK (`defer()`) AVANT toute résolution, sinon le client affiche
  « didn't respond in time » ; le clic ne fait pas tourner d'LLM (comment +
  unblock en CLI). Un listener qui n'accepte que son propre schéma rend tous
  les clics inertes. Portage : copier le dossier plugin, l'ajouter à
  `plugins.enabled` du profil cible, `hermes plugins doctor <nom>`, restart
  gateway, vérifier le log `Wired native handlers from plugin ...` ; l'API de
  bot ne permet PAS de simuler un clic → tester le handler sur le board réel
  (mock de l'adaptateur, kanban réel), jamais en attendant un clic.
