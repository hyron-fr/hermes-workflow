---
type: context
status: draft
tags: [architecture, cadrage, convergence, decision, escalation, slice-5, description-epinglee, delivery-proof]
issues: [25]
---

# Cadrage architectural — issue #25 « slice 5/5 — convergence »

## Positionnement (cadre exact)

L'issue #25 est **encore une import du même point à statuer conv-5** du chantier
**#19** (« Discord thread title and description update »), carte racine
`t_f725879f` (« slice 5/5 — convergence », board `pj-hermes-workflow`,
assignée `pj-test`). C'est le **6ᵉ import** de ce point de décision sur la
chaîne `#19 → #27 → #28 → #30 → #31 → #34 → #37 → #40 → #41 → #44 → #45 → #25`
(t2, commentaire 1198 de la carte mémoire).

Le corps de l'issue #25 **répète le constat mesuré à son import** :

| fait (tel que porté par #25) | preuve mesurée |
|---|---|
| Commit GREEN dev-5 `6661362` absent du worktree partagé | `git cat-file -t 6661362` → `Not a valid object name` ; `git log --all` → 0 hit |
| Branch head = `49bb284` (RED test-5) | `git log --oneline wt/issue-19-discord-thread-title-description` |
| 0 occurrence de l'API slice 5 dans `pipeline/`/`bridge/`/`skills/` | grep `DESCRIPTION_MARKER\|build_description\|sync_description\|upsert-desc` |
| Banc 10/10 RED rejoué | `pytest tests/test_thread_description.py` |
| À re-pousser par dev-5/dispatcher | directive de l'issue |

**Le point à statuer** (invariant depuis #27) : le jeton `/ok` en **premier
élément** d'un commentaire GitHub sur #25 débloque la carte `t_f725879f` et
la repart en file ; tout autre commentaire est une demande d'éclaircissement
et ne débloque rien. Le re-poussage du GREEN **suit** la décision, il n'est
pas ce cadrage.

### Ce qui a changé depuis le cadrage de #41 (le plus récent)

L'état du worktree partagé a bougé depuis la dernière note (`issue-41`, état
« GREEN partial, banc 8/10 ») :

- **Commit de docs `6a2d8e3`** (« docs(issue-26) : note de cadrage — premier
  miroir GitHub de l'escalade conv-5 ») a été poussé sur
  `wt/issue-19-discord-thread-title-description` : branch head est
  **`6a2d8e3`**, au-dessus de `dbf73da` (#41), `56e2525` (#41 correction),
  `578b7b2` (#41), `6a827a0` (#45), `55e6659` (conv-audit baseline),
  `dccf75f` (fix keeper journalisation bouclante), `03e09f1` (#31), `49bb284`
  (RED test-5), …
- **Fix keeper présent et poussé** (`dccf75f`) : la journalisation de
  `build_description_for_card` ne boucle plus à l'infini — c'est l'un des
  deux fixes nommés par le banc partiel de #41/#45.
- **`pipeline/pj_room_keeper.py`** contient désormais
  `build_description_for_card`, `sync_description` et
  `sync_all_descriptions` — soit **8 occurrences** de l'API slice 5, là où le
  constat de #25 en comptait 0. Le GREEN **partiel** (le composant keeper,
  porteur de l'écriture) est **présent** dans le worktree partagé.
- **Le commit original `6661362` est toujours introuvable** dans
  `git log --all` ; le contenu partiel a été **reconstruit** (rebuild) et
  poussé, pas le commit d'origine recyclé.
- **La moitié helper Discord est toujours absente** :
  `skills/gh-kanban-bridge/scripts/discord_thread.py` n'expose **ni**
  `upsert-desc` **ni** `pin` (grep = 0 occurrence). C'est l'autre fix restant
  du GREEN perdu.

Le travail restant est donc **plus étroit** qu'au moment de #25 : il ne
s'agit plus de re-pousser l'API slice 5 dans le keeper (présente) mais de
livrer les capacités **`edit`/`pin` du helper Discord** et de faire passer le
banc slice 5 du **partiel** au **10/10 GREEN**.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision (commentaire `/ok` en tête sur l'issue #25,
  `idempotency-key gh-issue-25`) et surface de preuve (commits de la branche,
  PR éventuelle). Le gate de couverture a identifié #25 comme recouvrant du
  travail en vol (#19, #27, #28, #29, #30, #31, #32) : c'est **la même carte
  bloquée** (`t_f725879f`), escaladée six fois.
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` est la **preuve de
  livraison** de la slice 5. Un commit absent du branch head = travail non
  livré, quel que soit le handoff du worker. La couverture commit-à-commit
  (invariant de l'issue #2, commits `009f0a7`/`9e49771`/`318bea1`) est le
  moyen de vérifier que le contenu est bien là.
- **Kanban Hermes** — source de vérité de l'état des cartes : `t_f725879f`
  (conv-5) en `blocked` porte le point à statuer ; la carte `t_b2b8002a`
  (issue #25) est parente du graphe de l'issue #19.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison**, pas la
fonctionnalité #19 elle-même. #19 est déjà cadré par la note de cadrage
`issue-19` (worktree t_c22a7e74) et par la note composant `pj-thread-name`
(slice 4). Ses slices 1–4 sont livrées ; la **slice 5** (moitié
« description épinglée ») est en cours de convergence.

Ce que #25 porte :

- **le point de décision** : le travail de la slice 5 est-il livré ?
- **la chaîne de re-livraison** : qui livre les capacités `edit`/`pin` du
  helper Discord et repousse le GREEN complet ?
- **le verdict de convergence** : après livraison, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

C'est une **boucle de décision + re-livraison**, pas une évolution de
fonctionnalité. Le code de la slice 5 (bloc Description épinglé,
`build_description_lines`, `sync_description`, `sync_all_descriptions`,
capacité `edit`/`pin` du helper Discord) est décrit par le banc
`tests/test_thread_description.py` — ce cadrage ne le redécrit pas.

### Code (composants impactés)

- **`tests/test_thread_description.py`** (worktree partagé t_c22a7e74, commit
  `26bad5d` + `49bb284`) — le banc de la slice 5 : 10 cas, rejouable. C'est
  lui qui **verrouille le contrat d'interface** de la moitié description de
  #19 (Q2 = 2b) : `DESCRIPTION_MARKER = "[description]"`,
  `build_description_lines`, `description_log_lines`,
  `keeper.build_description_for_card`, `keeper.sync_description`,
  `keeper.sync_all_descriptions`. Sources injectées, 0 réseau. État mesuré :
  **partiel** (le keeper est présent, le helper ne l'est pas) — le banc ne
  peut pas être 10/10 tant que les capacités `edit`/`pin` du helper ne sont
  pas livrées.
- **`pipeline/pj_room_keeper.py`** (worktree partagé t_c22a7e74) — porteur de
  l'écriture de la description : `build_description_for_card`,
  `sync_description`, `sync_all_descriptions` sont **présents** (fix
  `dccf75f` inclus). Le keeper est l'écrivain unique du titre (slice 4 livrée)
  **et** de la description (slice 5, en cours) ; les deux cycles cohabitent
  dans le même tick du keeper, best-effort, sans se conditionner.
- **`pipeline/engine.py`** (worktree partagé) — formateur pur du titre
  (`format_title`, `title_icon`, `TITLE_ICONS`, `NAME_MAX = 100`, slice 3
  livrée) ; le `rename_thread` délègue au keeper (slice 4). La description
  **n'appartient pas** à `engine.py` : c'est une lecture d'état (gh/git) qui
  doit être résolue hors du core, puis injectée.
- **`pipeline/pj_escalate.py`** (worktree partagé) — `thread_index` élargi au
  nouveau format (motif `(?:\S+\s+)?<repo>\|#0*(\d+)\b`). Non impacté par la
  slice 5.
- **`plugins/pj-buttons/pj-buttons/__init__.py`** (worktree partagé) —
  `THREAD_NAME_RE` élargi aux deux séparateurs (`#` et `|#`). Non impacté par
  la slice 5.
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** — helper Discord
  (adapter REST) : `create` / `send` / `rename` / `threads` / `delete`.
  **Aucune** capacité `pin` ni `edit` de message à ce stade. La slice 5
  l'étend (capacité `edit`/`pin` du helper) — **c'est le gap principal**.
- **`bridge/pj_room_keeper.py`** + **`agents/pj-master/scripts/pj_room_keeper.py`**
  — miroirs/copies du keeper. La slice 5 les touche aussi (l'écriture de la
  description y est portée).

## Lecture SDD (spec-driven)

La spec de #25 est le `point à statuer` : le commit GREEN dev-5 `6661362` est
absent du worktree partagé. Le livrable de #25 n'est **pas** un code, mais
**l'état de convergence de la slice 5 de #19** : soit le code (notamment les
capacités `edit`/`pin` du helper) est livré et le banc passe 10/10 GREEN, soit
l'escalade se poursuit. La doc décrit ce qui existe aujourd'hui (le banc, le
travail partiel, le worktree de re-livraison) — pas une intention.

Le manifeste `specs/19/slices.json` est **absent du dépôt** (mesuré par
`find` depuis la racine du worktree partagé) : il est la source de la ligne
`**Branche**` du bloc Description ; son absence est gérée par le contrat
(ligne omise + log bruyant), et sa localisation réelle relève du chantier,
pas de cette décision.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27/#31/#41/#25), sans en être un nouveau : c'est la **jonction** entre les
  deux.
- **Agrégat racine** : la **carte `t_f725879f` (conv-5)** — invariant : elle
  ne repart en `ready` que sur un `/ok` humain portant son `id` exact (le
  commentaire sur l'issue #25). L'**issue #25** est l'objet de décision qui
  matérialise la carte.
- **Value objects** : le **branch head SHA** (aujourd'hui `6a2d8e3`, le commit
  GREEN d'origine `6661362` est introuvable) ; le **commit SHA** de la slice 5
  (rebuild, pas le commit d'origine) ; l'**idempotency-key** `gh-issue-25`.
- **Domain events** : `/ok` humain sur l'issue #25 → unblock de
  `t_f725879f` → livraison des capacités `edit`/`pin` du helper + re-poussage
  du GREEN par `dev-5`/`dispatcher` sur
  `wt/issue-19-discord-thread-title-description` → banc 10/10 GREEN →
  convergence GREEN → doc → doc-review → PR (t6) → merge.

## Lecture TDD (contrats testables)

Le contrat testable de #25 n'est pas un code, mais **un invariant mesurable** :

- **Le branch head de `wt/issue-19-discord-thread-title-description` contient
  le commit GREEN (ou son équivalent rebuild)** — vérifiable par
  `git log --oneline` sur la branche et par la couverture commit-à-commit de
  `pj_graphwatch`.
- **Le banc `tests/test_thread_description.py` passe 10/10 GREEN** — 10 cas,
  rejouable sans Discord ni réseau (sources injectées).
- **Les capacités `edit`/`pin` du helper Discord sont présentes** dans
  `skills/gh-kanban-bridge/scripts/discord_thread.py` — vérifiable par grep
  et par le banc.
- **Les 10 cas du banc** sont les critères d'acceptation de la slice 5 ;
  leur état RED/GREEN est la preuve de convergence.

Ces invariants sont mesurables par `pj_graphwatch` (couverture
commit-à-commit + chemin réel du worktree) et par le pont de couverture
(`pj_coverage_gate`) qui a identifié #25 comme recouvrant #19 et #27.

## Lecture hexagonale (le core reste pur)

Le **core pur** de la slice 5 est `build_description_lines` (fonction pure :
issue_url, branch, pr_url → list[str], 0 réseau, 0 horloge, 0 aléa) et
`build_description_for_card` (assemblage de sources **injectées** — 0 réseau,
conformément au banc qui « empoisonne » le réseau par sentinelle). L'écriture
du message épinglé et de l'épingle passe par le helper `discord_thread.py`
(adapter REST, hors core). Le contrat d'interface (marqueur `[description]`,
`build_description_for_card`, `sync_description`, `sync_all_descriptions`)
est testable sans Discord : les sources et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le formateur
pur. Jamais l'inverse : le formateur ne lit pas le réseau. Le keeper
(`pj_room_keeper.py`) est le **porteur** (cycle de vie, déduplication par
marqueur, best-effort), pas le décideur de contenu.

## Composants impactés par l'issue #25

| composant | impact | slice #19 |
|---|---|---|
| `tests/test_thread_description.py` | banc (présent, `26bad5d` + `49bb284`) ; état partiel tant que le helper n'est pas livré | 5 |
| `pipeline/pj_room_keeper.py` + miroirs | porteur de l'écriture de la description (**présent**, fix `dccf75f` inclus) | 5 |
| `pipeline/engine.py` | formateur pur du titre (présent, slices 3–4) | 3–4 |
| `pipeline/pj_escalate.py` | `thread_index` élargi (présent, slice 2) | 2 |
| `plugins/pj-buttons/pj-buttons/__init__.py` | `THREAD_NAME_RE` élargi (présent, slice 2) | 2 |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | capacité `edit`/`pin` à ajouter (**absente** — gap principal) | 5 |
| `bridge/pj_room_keeper.py` + `agents/pj-master/scripts/pj_room_keeper.py` | miroirs du keeper (présents, à synchroniser si le keeper bouge) | 5 |

## Hors-scope

- **La livraison des capacités `edit`/`pin` du helper Discord** : portée par
  `dev-5`/`dispatcher` sur le worktree partagé, **jamais** par ce cadrage.
- **Le verdict de convergence** : porté par `pj-test` sur la carte
  `t_f725879f`, pas par ce cadrage.
- **Les slices 1–4 de #19** : déjà livrées, cadrées par la note `issue-19` et
  la note composant `pj-thread-name`.
- **La duplication bridge↔pipeline↔agents des `pj_*.py`** : divergence connue
  (les 3 copies du keeper sont identiques à ce stade), non traitée par #25.
- **Le re-poussage du commit original `6661362`** : le contenu a été
  reconstruit (rebuild) ; le commit d'origine reste introuvable — ce n'est
  plus un objectif, le contenu partiel est le livrable.

## Frontières traversées (résumé)

```
issue #25 (GitHub, label decision + kanban)
  → commentaire /ok humain (surface de décision)
  → unblock de t_f725879f (kanban)
  → livraison edit/pin du helper Discord + GREEN complet sur wt/issue-19-discord-thread-title-description (git)
  → banc test_thread_description.py 10/10 GREEN (preuve de livraison)
  → convergence GREEN → doc → doc-review → PR (t6) → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un commit absent
du branch head est un travail non livré, quel que soit le handoff du worker.

## État mesuré (2026-10-10, rejouable)

- `origin/dev` = `2027333` (docs cadrage #29).
- `wt/issue-19-discord-thread-title-description` :
  - **branch head** = `6a2d8e3` (docs issue-26), au-dessus de `dbf73da` (#41),
    `56e2525` (#41), `578b7b2` (#41), `6a827a0` (#45), `55e6659` (conv-audit
    baseline), `dccf75f` (fix keeper), `03e09f1` (#31), `49bb284` (RED test-5),
    `26bad5d` (RED test-5), `27c453c` (docs slice 4), `422878f` (GREEN slice 4),
    …
  - **GREEN partiel présent** : `pipeline/pj_room_keeper.py` contient
    `build_description_for_card`, `sync_description`, `sync_all_descriptions`
    (8 occurrences), fix `dccf75f` inclus.
  - **Helper Discord incomplet** : `skills/gh-kanban-bridge/scripts/discord_thread.py`
    ne contient **ni** `upsert-desc` **ni** `pin` (grep = 0 occurrence).
  - **Banc** `tests/test_thread_description.py` : 10 cas ; état partiel (le
    keeper est présent, le helper ne l'est pas) — le banc ne peut pas être
    10/10 GREEN tant que les capacités `edit`/`pin` ne sont pas livrées.
- `git cat-file -t 6661362` → **Not a valid object name** (commit absent du
  dépôt local et du remote ; le contenu a été reconstruit, pas le commit
  d'origine recyclé).
- `specs/` absent du dépôt (mesuré par `find` depuis la racine du worktree
  partagé).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → à vérifier
  après push de cette note.
