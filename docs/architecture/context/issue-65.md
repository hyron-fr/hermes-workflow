---
type: context
status: draft
tags: [architecture, convergence, slice-5, description-epinglee, cadrage]
issues: [65]
---

# Cadrage architectural — issue #65 « slice 5/5 — convergence » (chantier #19, carte conv-5 `t_f725879f`)

## Positionnement (cadre exact)

L'issue #65 (`labels: kanban + decision`, `idempotency-key gh-issue-65`, état OPEN au 2026-10-11)
est le **miroir GitHub** de la carte **`t_f725879f`** (board `pj-hermes-workflow`, assignée
`pj-test`), elle-même la carte **convergence 5/5** du chantier #19 « Discord thread title and
description update » (slice 5 = `description-epinglee-issue-branche-pr`).

Ce n'est PAS une escalade de blocage classique : la carte est déjà `blocked` (diagnostic
critique : 10 crashs worker, protocole violation), et le corps de l'issue est le **point à
statuer** qui résume le **VERDICT conv-5 NÉGATIF** mesuré le 2026-10-07 (rejoué au 2026-10-11
sur le même état). Le jeton `/ok` en premier élément du commentaire GitHub débloque la carte
et la repart en file ; tout autre commentaire est une demande d'éclaircissement.

**Position dans la chaîne conv-5** (mesurée, rejouable) : #27 → #29 → #30 → #41 → #81 →
#80 → #75 → #74 → #73 → **#65**. C'est la plus récente : elle porte le verdict « GREEN
partial, 3 fixes keeper + capacités helper manquantes » — identique en substance à #70/#73
(même carte `t_f725879f`, même banc 7/10). Les escalades précédentes ont déjà documenté
l'historique (notes [[issue-27]], [[issue-29]], [[issue-41]], [[issue-81]], [[issue-70]] ;
les notes #73/#74/#75/#80 sont livrées sur la branche du chantier, à merge avec #19).

**Particularité de #65** : le corps porte le verdict **détaillé** (les 3 rouges nommés avec
leur cause code), contrairement à #70 (motif « non détaillé »). Le cadrage peut donc
positionner les 3 fixes nommément — sans les implémenter (périmètre dev, pas doc).

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #65 (miroir de
  `t_f725879f`). Adapter : `gh` CLI, lu par le pont `gh-kanban-bridge` ; effet kanban =
  unblock + re-spawn de la carte conv-5 (même boucle de décision que [[issue-5]]).
- **Kanban Hermes** — source de vérité de l'état des cartes. `t_f725879f` est `blocked`
  avec diagnostic critique (10 crashs worker consécutifs, `consecutive_crashes=10`).
  Les cartes-twins du cycle courant (pipeline t1–t5 + t3b de cette issue) sont sur le
  board : `t1=t_df03a401` (worktree), `t2=t_dbdcbac7` (mémoire), `t3=t_f495f2ef`
  (grill-me), `t3b=t_0a4e884b` (cette carte), `t4=t_d468fe83` (spec), `t5=t_5162b5d2`
  (GO), racine `t_7e27b1a5`.
- **Git / worktree partagé** — surface de livraison : `wt/issue-19-discord-thread-title-description`
  (worktree `t_c22a7e74`). C'est le **seul** endroit où le GREEN partial slice 5 existe.
  La décision débloque un re-cycle RED-GREEN : le commit GREEN complet (3 fixes + helper)
  doit être commité et poussé sur cette branche avant que la convergence ne puisse être
  auditée. **Aucun nouveau port** : GitHub/kanban/git existent ; l'issue réutilise la
  boucle de décision #5 et le contrat de convergence du chantier #19.
- **Discord** — surface d'observation du livrable final (le fil du ticket #19 porte le
  bloc Description épinglé). Hors périmètre de la décision : la conv-5 **lit** le fil,
  n'y écrit pas (quota de renommage réservé à la slice 4, garde-fou de la carte).

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** de la slice 5 — pas une
fonctionnalité nouvelle. Le chantier #19 est déjà cadré par [[issue-19]] et la note
composant [[pj-thread-name]] (slices 2–4 livrées : formateur pur du titre, 3 lecteurs,
écrivain unique du titre + coalescence). La slice 5 porte :

- **le point de décision** : la slice 5 est-elle convergée ? État mesuré : **NON** —
  banc 7/10, 3 rouges nommés + helper incomplet (voir État mesuré).
- **la chaîne de livraison débloquée par le `/ok`** : dev re-cycle le GREEN
  (3 fixes keeper + `upsert-desc`/`pin` du helper) → push vérifié `0 0` → conv-5
  re-audite (banc 10/10, lecture du fil, rev-list) → verdict POSITIF → doc → doc-review
  → PR (`t6`) → merge.
- **le verdict de convergence** (critères de la carte conv-5) : verdict posté (liste des
  messages Description du fil, valeurs résolues, `pytest -q` vs baseline) + clé
  `convergence-5` au blackboard racine + `kanban_complete` avec artifacts.

### Code (composants impactés)

État mesuré **dans le worktree partagé** (`/home/elix/pj-repos/hermes-workflow/.worktrees/t_c22a7e74`,
branche `wt/issue-19-discord-thread-title-description`, HEAD `9fcd207`) au 2026-10-11 :

| composant | état mesuré | impact de la décision |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` (L221) + `build_description_lines` (L224, formateur pur) **présents** | Livré dans le GREEN partial — non touché par le re-cycle |
| `pipeline/pj_room_keeper.py` | `build_description_for_card` (L572), `sync_description` (L695), `sync_all_descriptions` (L799) **présents mais défectueux** : 3 rouges nommés | 3 fixes : (1) passer `issue_url_lookup` à `build_description_for_card` (défaut de contexte, ~L726), (2) préserver l'ORG dans `_gh_repo()` (le `rsplit("/")[-1]` perd le namespace, ~L652), (3) propagater `issue_url_lookup` dans `sync_all_descriptions` (~L824) |
| `tests/test_thread_description.py` | 10 cas, **7 GREEN / 3 RED** (mesuré 2026-10-11, rejouable) | Banc qui **gèle le contrat** de la slice 5 ; les 3 rouges sont les critères d'acceptation restants — le banc n'est jamais affaibli (garde-fou de la carte) |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement ; `upsert-desc`/`pin` **absents** (grep 0 hit) | Le keeper les appelle déjà (`_discord_pin` ~L773, `upsert-desc` ~L896) — capacités à ajouter (4ᵉ fichier du périmètre GREEN) |
| `specs/19/slices.json` | Contrat du graphe du chantier #19 (lint ok) | Non touché : le périmètre slice 5 est déjà validé (grill-me `PROTOTYPE: non`) |

Le **core pur** à préserver reste le même qu'en slice 3/4 : `build_description_lines`
(composition pure, 0 réseau) et `build_description_for_card` (sources **injectées**).
L'écriture du message et de l'épingle passe par l'adapter injecté `write_message` / le
helper Discord. Les 3 fixes attendues sont des **fixes de câblage** (injection du lookup,
préserver le namespace org), pas des changements de contrat : le banc existant les
vérifie déjà, il n'y a donc pas de nouveau contrat à figer.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`, 5 slices
validées par le GO humain du 2026-10-03) ; le manifeste `specs/19/slices.json` est le
contrat déterministe (lint ok au cadrage de #19). L'issue #65 **est** le point à statuer
de sa carte `t_f725879f` : le verdict conv-5 négatif est le constat de non-convergence,
pas une spec. Le périmètre est **gelé** : le grill-me (verdict `PROTOTYPE: non`,
`AMBIGU: aucune`, `ARTEFACT: aucun` — carte `t_1d781414` sur #43) fixe l'action unique
= faire passer les 10 tests et pousser. La doc décrit le livré : ici le « livré »
attendu est le GREEN 10/10 (3 fixes keeper + `upsert-desc`/`pin`) ; jusqu'au re-cycle,
l'état mesuré est 7/10 + helper incomplet — c'est exactement ce que ce verdict dit.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — jonction entre
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade sur `t_f725879f`),
  sans en être un nouveau.
- **Agrégat racine** : la **carte `t_f725879f`** (invariant : elle ne repart en `ready`
  que sur un `/ok` portant sa ligne canonique `carte: pj-hermes-workflow/t_f725879f`).
  L'**issue #65** est l'objet de décision qui la matérialise.
- **Value objects** : le **banc 7/10** (état de convergence partiel, rejouable) ; le
  **branch head SHA** `9fcd207` (HEAD local = remote, en sync) ; l'absence du commit
  GREEN `6661362` (`git cat-file -t` → fatal) ; l'**idempotency-key** `gh-issue-65`.
- **Domain events** : `/ok` humain sur l'issue #65 → unblock de `t_f725879f` →
  re-spawn dev (re-cycle RED-GREEN : 3 fixes keeper + `upsert-desc`/`pin`) → commit
  GREEN + push vérifié `0 0` → re-spawn conv-5 (audit : banc 10/10, lecture datée du
  fil, rev-list) → verdict POSITIF → doc → doc-review → PR `t6` → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`** (10 cas),
rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]` —
  composition pure, omission des `None`/vides (cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader, issue_url_lookup)`
  — assemblage des sources injectées. **3 cas RED = critères d'acceptation restants** :
  1. `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique` — le `sync_description`
     doit propager le `issue_url_lookup` au builder (sinon thread non résolu → verdict
     `{thread_id: None, ok: None}` au lieu de post/ok=True).
  2. `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception` — le reader de
     PR qui lève doit être capturé : ligne PR omise + tracée, jamais d'exception qui tue
     le tick.
  3. `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick` — de même, une source
     qui lève ne doit pas produire de bloc vide ni tuer le tick (propagation du lookup).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)` — écrivain
  best-effort : dédup par marqueur `[description]`, `edit` jamais second post.
- Les 3 rouges **ne sont pas de nouveaux contrats** : ils sont déjà écrits (RED de
  test-5) ; le passage GREEN est la preuve de convergence. Aucun nouveau test n'est
  attendu par la décision ; le banc est intouchable (garde-fou).

## Lecture hexagonale (le core reste pur)

- **Core pur** : `build_description_lines` (fonction pure : 3 entrées → `list[str]`,
  0 réseau, 0 horloge, 0 aléa) et `build_description_for_card` (sources **injectées**
  via `issue_url_lookup`, `specs_reader`, `pr_reader`). La frontière hexagonale est
  respectée dans le GREEN partial : les fixs attendus sont du **câblage du port**
  (propager le lookup injecté dans les appels du keeper), jamais une lecture réseau
  dans le formateur.
- **Adapters** : le helper `discord_thread.py` (REST Discord, à compléter avec
  `upsert-desc`/`pin`) et le reader `gh pr list` (via le port `pr_reader`). L'écriture
  du message épinglé et de l'épingle ne rentre jamais dans le core.
- **Frontière à respecter** : la description est une **lecture d'état** (gh/git/
  blackboard) résolue **hors** du core puis injectée dans le formateur pur. Jamais
  l'inverse. Le verdict conv-5 négatif ne remet pas en cause cette frontière — il
  signale un port mal câblé, pas une violation de l'architecture.

## Frontières traversées (résumé)

```
issue #65 (GitHub, labels kanban + decision, miroir de t_f725879f)
  → commentaire /ok humain (surface de décision)
  → unblock de t_f725879f (kanban)
  → re-spawn dev : 3 fixes keeper + upsert-desc/pin (worktree t_c22a7e74)
  → commit GREEN + push vérifié rev-list 0 0 (preuve de livraison)
  → re-spawn conv-5 : banc 10/10 GREEN + lecture datée du fil (preuve de convergence)
  → verdict POSITIF → doc → doc-review → PR t6 → merge
```

Deux frontières portantes : **GitHub ↔ kanban** (décision → effet sur la carte) et
**git ↔ worktree partagé** (preuve de livraison commit-à-commit). Le point de fragilité
n'est pas l'appel réseau mais **la couverture commit-à-commit** : un fix non-commité
dans l'arbre n'est pas un travail livré (leçon de la perte du GREEN `6661362` :
commit jamais sur une ref → perdu au reset du worktree partagé).

## État mesuré (2026-10-11, rejouable)

Mesures effectuées dans `/home/elix/pj-repos/hermes-workflow/.worktrees/t_c22a7e74`
(branche `wt/issue-19-discord-thread-title-description`) :

- `git log --oneline -1` = `9fcd207` (docs cadrage #73) ; **local = remote**
  (`git rev-list --left-right --count HEAD...@{u}` = `0 0`). Le tip a avancé depuis
  les notes #41/#81 (`6a2d8e3`/`6a827a0`) et le HEAD du verdict du 2026-10-07
  (`55e6659`) — en avance uniquement en docs (notes de cadrage), **pas en code**.
- `git cat-file -t 6661362` → **fatal: Not a valid object name** (le GREEN original
  est définitivement absent de toutes les refs).
- `grep DESCRIPTION_MARKER|build_description|sync_description pipeline/` → présents
  : `pipeline/engine.py` L221/L224 (`DESCRIPTION_MARKER`, `build_description_lines`),
  `pipeline/pj_room_keeper.py` L572/L695/L799 (`build_description_for_card`,
  `sync_description`, `sync_all_descriptions`). GREEN partial **dans l'arbre**.
- `grep "upsert-desc\|pin" skills/gh-kanban-bridge/scripts/discord_thread.py` →
  **0 hit** (capacités non livrées ; le keeper les appelle déjà ~L773/_discord_pin et
  ~L896/upsert-desc).
- Banc : `/home/elix/.hermes/hermes-agent/venv/bin/python -m pytest
  tests/test_thread_description.py -q -p no:randomly` = **3 failed, 7 passed**
  (mesuré 2026-10-11). Les 3 rouges :
  - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`
  - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
- Notes non commitées sur le worktree partagé : `?? docs/architecture/context/issue-27.md`,
  `?? docs/architecture/context/issue-29.md` (hors périmètre de la slice 5 ; déjà
  référencées par le MOC via la branche `origin/dev` `2027333`).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0` (baseline).
- Carte `t_f725879f` : `blocked`, diagnostic critique `consecutive_crashes=10` ;
  parent : `t_0fa1c596`, `t_d1d4eb41` (test-5/dev-5) ; enfants : `t_ad99e220`,
  `t_e9484d73` (doc-5 / suite).

## Composants impactés (résumé)

- **Décision (cette issue)** : la boucle de décision [[pj-decision]] +
  [[pj-escalate]]/[[pj-notify]] (boucle #5) — aucun changement de code attendu de
  l'issue #65 elle-même ; le `/ok` déclenche uniquement l'unblock kanban.
- **Travail débloqué (slice 5 de #19, à re-cycler par pj-dev)** :
  - `pipeline/pj_room_keeper.py` — 3 fixes de câblage nommés par le verdict
    (propagation de `issue_url_lookup` + préservation du namespace ORG dans `_gh_repo()`).
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` — ajout `upsert-desc` + `pin`.
- **Preuve de convergence (pj-test, conv-5)** : banc 10/10 + lecture datée du fil
  Discord du ticket #19 (observation seule, aucune écriture de titre — quota réservé
  à la slice 4) + `rev-list 0 0` sur le commit GREEN.
- **Vault** : à la convergence, la slice 5 gagnera sa note composant et le MOC
  `docs/architecture/README.md` sera mis à jour par la carte `doc-k` — hors périmètre
  de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **Le contenu exact des 3 fixes keeper** — porté par le dev après le `/ok` ; le banc
   définit le contrat, le cadrage le positionne.
2. **La forme des capacités `upsert-desc`/`pin`** — porté par le dev ; le helper est
   un adapter (injecté), non testé directement par le banc.
3. **Le re-spawn après 10 crashs worker** — le diagnostic critique (protocole
   violation, `worker exited cleanly without kanban_complete`) relève de l'infrastructure
   dispatcher ; le `/ok` re-file la carte mais ne corrige pas la cause des crashs si
   elle persiste.
4. **La publication live des copies `~/.hermes/scripts/`** (divergence D1 déclarée
   dans le body de la carte conv-5 : `pj_escalate.py` live sha ≠ versionné) —
   opération de fin de graphe contrôlée par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.
