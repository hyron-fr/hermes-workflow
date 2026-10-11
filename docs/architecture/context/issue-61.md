---
type: context
status: draft
tags: [architecture, decision, escalation, convergence, slice-5, description-epinglee, cadrage]
issues: [61]
---

# Cadrage architectural — issue #61 « slice 5/5 — convergence » (escalade conv-5, carte `t_c410a564`)

## Positionnement (cadre exact)

L'issue #61 (`labels: decision + kanban`, `idempotency-key gh-issue-61`) est
une **escalade de décision** de la carte **`t_c410a564`** (« slice 5/5 —
convergence », board `pj-hermes-workflow`), bloquée sur le chantier
**#19** (« Discord thread title and description update ») via le ticket
intermédiaire **#23** (« slice 5/5 — convergence ») — d'où le corps de
l'issue : « Point à statuer sur la carte `t_c410a564`, bloquée sur le
ticket #23 ».

C'est le **nouvel échelon** de la chaîne conv-5 déjà documentée : le point à
statuer est toujours le **même** — la convergence de la slice 5 de #19
(bloc « Description épinglée »), dont le commit GREEN original `6661362`
est **définitivement perdu** (`git cat-file -t 6661362` → fatal, mesuré
2026-10-11 sur le worktree partagé). Les miroirs antérieurs de la même
convergence (notes issue-23/29/64/81, lives sur leurs propres worktrees
ou dans l'histoire, non encore sur `dev`) décrivent le même état.

**Ce que la décision débloque** : le jeton `/ok` en premier élément sur
l'issue #61 fait déboucler la carte `t_c410a564` et la repart en file.
Tout autre commentaire est une demande d'éclaircissement et ne débloque
rien. Après le `/ok`, le re-poussage du GREEN est porté par le cycle dev
(voir décision JB 09/10 : re-poussage par cycle normal, pas de replay de
`6661362`) — jamais par ce cadrage.

**Ce que le cadrage ne fait pas** : ne tranche pas, ne reformule pas le
motif de blocage déclaré « (non détaillé) » — il positionne le point à
statuer dans l'architecture existante et décrit l'état **mesuré**.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision (commentaire `/ok` sur l'issue #61,
  `idempotency-key gh-issue-61`) et surface de preuve. L'issue #61 est le
  miroir kanban de la carte `t_c410a564` ; le pont de couverture a posé
  son gate le 2026-10-08 (recouvrement de #23, PR ouverte, graphe
  construit — commentaire `pj-coverage-gate`).
- **Kanban Hermes** — source de vérité de l'état des cartes : `t_c410a564`
  en `todo` porte le point à statuer ; le graphe de cette issue
  (t1..t5 + t3b) est construit, la racine `t_8c48cd3c` attend la
  convergence.
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`)
  est la preuve de livraison de la slice 5. État mesuré : tip `9fcd207`,
  GREEN partial présent, banc 7/10 (3 RED).
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git)
  existent ; l'issue #61 réutilise la boucle de décision #5
  ([[pj-decision]] : `decision_from_comment` calcule, l'appelant
  applique).

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 est déjà cadré par la note
composant `pj-thread-name` (slices 2–4 livrées : formateur pur, table des
4 états, écrivain unique + coalescence 600 s) et par les escalades de la
chaîne conv-5 (issues #23, #29, #64, #81 — notes de cadrage sur les
worktrees de leurs cycles, non encore fusionnées). #61 porte :

- **le point de décision** : la slice 5 est-elle convergée ? État mesuré :
  NON — 3 fixes keeper manquent, le helper Discord n'a pas
  `upsert-desc`/`pin`.
- **la chaîne de livraison** : qui applique les 3 fixes keeper restants et
  ajoute les 2 capacités helper ? (Le dev, après le `/ok`.)
- **le verdict de convergence** : après les fixes, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

État mesuré le 2026-10-11 sur `wt/issue-19-discord-thread-title-description`
(tip `9fcd207`) :

| composant | état mesuré | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` présents | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card`, `sync_description`, `sync_all_descriptions` présents | **3 tests RED** : (1) `sync_description` appelle `build_description_for_card` SANS `issue_url_lookup` → `issue_url` non résolue ; (2) `_gh_repo()` perd l'ORG `hyron-fr` (`.rsplit("/")[-1]`) → URL issue sans ORG ; (3) `sync_all_descriptions` ne transmet pas `issue_url_lookup` |
| `tests/test_thread_description.py` | 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat de la slice 5 |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → `list[str]`, 0 réseau) et
`build_description_for_card` (sources injectées). L'écriture du message et
de l'épingle passent par l'adapter injecté `write_message` / le helper
Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`,
`Q3=d`) ; l'issue #61 **est** le point à statuer de sa carte
`t_c410a564`. La spec est la source de vérité : le livrable de #61 n'est
pas du code, mais **l'état de convergence de la slice 5 de #19** : soit
les 3 fixes keeper + les 2 capacités helper sont appliqués et le banc
passe 10/10 GREEN, soit l'escalade se poursuit. La doc décrit le livré :
ici le « livré » attendu est le GREEN 10/10 ; jusqu'au `/ok`, l'état
mesuré est 7/10 GREEN + helper incomplet.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #23→#61), sans en être un nouveau : c'est la **jonction** entre les
  deux.
- **Agrégat racine** : la **carte `t_c410a564`** (invariant : elle ne
  repart en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_c410a564`). L'**issue #61** est l'objet de
  décision qui la matérialise.
- **Value objects** : le **branch head SHA** (`9fcd207` mesuré) ; le
  **banc 7/10** (état de convergence partiel) ; l'**idempotency-key**
  `gh-issue-61`.
- **Domain events** : `/ok` humain sur l'issue #61 → unblock de
  `t_c410a564` → re-spawn → dev applique les 3 fixes keeper + ajoute
  `upsert-desc`/`pin` → banc 10/10 GREEN → convergence → doc →
  doc-review → PR → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(10 cas), rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) ->
  list[str]` — composition pure, 4 lignes, omission des `None`/vides
  (4 cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (2 cas GREEN,
  1 cas RED : le reader qui lève ne doit pas tuer le tick).
- `keeper.sync_description(cards, *, fetch_messages, write_message,
  log=None)` — écrivain best-effort : dédup par marqueur, `edit` jamais
  second post (1 cas RED : un seul message épinglé mis à jour, pas
  dupliqué).
- **1 cas RED supplémentaire** : `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  — gestion d'erreur quand `gh pr list` lève (la ligne PR est omise mais
  tracée, pas d'exception).
- Les **3 cas RED** sont les critères d'acceptation restants de la
  slice 5 ; leur passage GREEN est la preuve de convergence.

## Lecture hexagonale (le core reste pur)

Le **core pur** : `build_description_lines` (fonction pure : issue_url,
branch, pr_url → `list[str]`, 0 réseau, 0 horloge, 0 aléa) et
`build_description_for_card` (sources injectées, 0 réseau). L'écriture du
message épinglé et de l'épingle passe par le helper `discord_thread.py`
(adapter REST, hors core). Le contrat d'interface (marqueur
`[description]`, `sync_description`, `sync_all_descriptions`) est
testable sans Discord : les sources et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le
formateur pur. Jamais l'inverse : le formateur ne lit pas le réseau.

## Frontières traversées (résumé)

```
issue #61 (GitHub, labels decision + kanban, idempotency-key gh-issue-61)
  → commentaire /ok humain (surface de décision)
  → unblock de t_c410a564 (kanban)
  → re-spawn → dev applique 3 fixes keeper + upsert-desc/pin
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité
n'est pas l'appel réseau mais **la couverture commit-à-commit** : un fix
non-commité dans l'arbre n'est pas un travail livré.

## État mesuré (2026-10-11, rejouable)

Mesuré sur le worktree partagé `wt/issue-19-discord-thread-title-description`
(tip `9fcd207`) + l'ancrage `origin/dev` (`2027333`) :

- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (définitivement absent de toutes refs).
- `grep DESCRIPTION_MARKER|build_description|sync_description` sur
  `pipeline/` → présents dans `pipeline/engine.py` et
  `pipeline/pj_room_keeper.py` (GREEN partial livré dans l'arbre).
- `grep upsert-desc|pin` sur
  `skills/gh-kanban-bridge/scripts/discord_thread.py` → **0 hit**
  (capacité non livrée).
- Banc `tests/test_thread_description.py` : **7/10 GREEN, 3 RED** (mesuré
  2026-10-11 ; rejouable via
  `python3 -m pytest tests/test_thread_description.py -q -p no:randomly`
  dans le venv hermes-agent). Les 3 cas rouges :
  - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`
    → `sync_description` appelle `build_description_for_card` SANS
    `issue_url_lookup` → `issue_url` non résolue.
  - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
    → `_gh_repo()` perd l'ORG `hyron-fr` (`.rsplit("/")[-1]`) → URL issue
    sans ORG.
  - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
    → `sync_all_descriptions` SANS `issue_url_lookup` → le bloc n'est pas
    écrit.
- Décision antérieure (mémoire projet, JB 09/10) : re-poussage du GREEN
  par cycle normal (dev-5 RECYCLE), **pas** de replay de `6661362`.
- `pj_docs_lint.py` sur le worktree → `exit=0` (voir handoff de la carte).

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py`
  ([[pj-decision]]) + `pipeline/pj_escalate.py` / `pipeline/pj_notify.py`
  ([[pj-notify]]) — la boucle #5, aucun changement de code.
- **Travail débloqué (slice 5 de #19, à compléter)** :
  - `pipeline/pj_room_keeper.py` — 3 fixes :
    (1) `sync_description` : transmettre `issue_url_lookup` (et
        `specs_reader`, `pr_reader`) à `build_description_for_card` ;
    (2) `_gh_repo()` : ne pas `.rsplit` (conservation de l'ORG
        `hyron-fr`) ou reconstituer l'URL complète avec l'ORG ;
    (3) `sync_all_descriptions` : transmettre `issue_url_lookup` à
        `build_description_for_card`.
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` — ajout des
    capacités `upsert-desc` (édition du message du fil) et `pin`
    (épingle du message).
- **Vault** : à la convergence, la slice 5 gagnera sa note composant et
  le MOC `docs/architecture/README.md` sera mis à jour par la carte
  `doc-k` — hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **Le contenu exact des 3 fixes keeper** — porté par le dev après le
   `/ok` (le banc définit le contrat, pas le cadrage).
2. **La forme des capacités `upsert-desc`/`pin`** — porté par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
3. **Le motif de blocage de la carte `t_c410a564`** — déclaré « (non
   détaillé) » sur l'issue #61 ; le détail est sur la carte elle-même. Le
   cadrage décrit l'état mesuré de la slice 5, ne reformule pas le motif.
4. **La publication live des copies `~/.hermes/scripts/`** (divergence
   déclarée dans le handoff `dev-5`) — opération de fin de graphe
   contrôlée par identité, hors périmètre de cette décision.
