---
type: context
status: draft
tags: [architecture, decision, escalation, convergence, slice-5, description-epinglee, cadrage]
issues: [55]
---

# Cadrage architectural — issue #55 « slice 5/5 — convergence » (miroir de décision de `t_8cc1e5c1`)

## Positionnement (cadre exact)

L'issue #55 est le
miroir GitHub de la carte **`t_8cc1e5c1`** (« slice 5/5 — convergence »,
board `pj-hermes-workflow`, assignée à `pj-master`, **`done`** le
2026-10-10), importée par le pont (`gh-issue-55`). Son corps déclare :

> **Point à statuer** sur la carte `t_8cc1e5c1` (board `pj-hermes-workflow`),
> bloquée sur le ticket #33. Motif déclaré : (non détaillé).
> `carte: pj-hermes-workflow/t_8cc1e5c1`

C'est un **miroir de décision** de la chaîne **conv-5** déjà documentée par
les notes de cadrage existantes ([[issue-29]], [[issue-4]], [[issue-5]],
[[issue-7]]) et par les escalades de même point à statuer référencées dans le
MOC (`issue-27`, `issue-41`, `issue-70`, `issue-81`, `issue-64` — notes en
vol ou sur la branche de #19, non encore committées sur `origin/dev` au moment
de ce cadrage) : le point à statuer est le **même** — la convergence de la
**slice 5 du chantier #19** (« Discord thread title and description update »,
slice `description-epinglee`), dont le commit GREEN original `6661362` est
**définitivement perdu** (vérifié 2026-10-11 : `git cat-file -t 6661362` →
fatal, absent de toutes refs locales et remote).

**Particularité de #55 (distincte de #27/#29/#41/#64/#70/#81)** : la carte
cible `t_8cc1e5c1` est **`done`** (pas `blocked`) — le tranchement a eu lieu
le 2026-10-10 par `pj-master` (commentaire de carte) : le jeton `/ok` a été
posé sur l'issue **#33** (fermée), le statut Discord posé sur le thread #33, et
le re-poussage du GREEN a été porté par l'issue **#45** (dev-5 RECYCLE, carte
`t_854f0f77`). L'issue #55 est **ouverte** : le pont ne l'a pas fermée car la
carte n'a pas de ligne `Importé depuis https://github.com/…/issues/55` dans son
corps — la carte `t_8cc1e5c1` est elle-même un miroir de #33 (pas de #55), et
le pont ne ferme que l'issue de sa propre ligne d'import (ancre
`pj-bridge-push-ancre`). #55 reste donc un **miroir orphelin ouvert** : le
point à statuer qu'elle représente est déjà tranché, mais l'issue elle-même ne
se fermera qu'au merge de la PR de #19 (qui fermera l'issue #19) ou par geste
humain (commentaire de rattachement, ou fermeture directe).

**Ce que la décision débloque** : le jeton `/ok` sur l'issue #55 (premier
élément) ne débloque **aucune carte** — la carte cible `t_8cc1e5c1` est déjà
`done`. Le tranchement a déjà eu lieu sur #33 (portée opérationnelle #45).
Tout commentaire sur #55 est une demande d'éclaircissement ou un geste
d'hygiène miroir (rattachement, fermeture), pas un déblocage.

**Le présent cadrage ne tranche pas** : il positionne le point à statuer dans
l'architecture existante, identifie les composants impactés, et fixe les
critères de décision. Le re-poussage du GREEN (le commit est perdu, il faut le
re-faire ou le re-écrire) est porté par le dev après le `/ok` de #33/#45,
jamais par ce cadrage.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision (commentaire `/ok` sur l'issue #55,
  `idempotency-key gh-issue-55`) et surface de preuve (commits de la branche,
  PR éventuelle). L'issue #55 est le miroir de la carte `t_8cc1e5c1` ; le pont
  de couverture a identifié #55 comme recouvrant #33 (travail en vol) et a
  importé la carte malgré le recouvrement (commentaire `pj-coverage-gate` du
  2026-10-08, puis import effectif le 2026-10-08 19:22). La ligne canonique
  de la carte est `carte: pj-hermes-workflow/t_8cc1e5c1` — **pas** la ligne
  `Importé depuis`, donc le pont ne peut pas fermer #55 au `done` de la carte.
- **Kanban Hermes** — source de vérité de l'état des cartes : `t_8cc1e5c1`
  (t3b doc-cadrage de #33) est en `done` ; la carte conv-5 `t_f725879f`
  (assignée `pj-test`) reste **`blocked`** — elle porte le vrai point à
  statuer conv-5 (le verdict de convergence de la slice 5 après re-push).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` (worktree `t_c22a7e74`)
  est la **preuve de livraison** de la slice 5. État mesuré (ci-dessous) :
  tip `95d4db0`, 31 commits au-dessus de `origin/dev`, GREEN partial présent
  dans `pipeline/`, banc 7/10 (3 RED), helper sans `upsert-desc`/`pin`.
- **Aucun nouveau port** : les trois surfaces (GitHub, kanban, git)
  existent ; l'issue #55 réutilise la boucle de décision #5
  ([[pj-decision]] : `decision_from_comment` calcule, l'appelant applique).

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #19 (« Discord thread title and
description update ») est déjà cadré par la note de cadrage initiale (commit
`ed75032` sur `wt/issue-19-discord-thread-title-description`), la note composant
`pj-thread-name` (slices 2–4 livrées) et les notes des escalades conv-5
(ci-dessous). #55 porte :

- **le point de décision** : la slice 5 est-elle convergée ? État mesuré :
  NON — 3 tests RED, le helper Discord n'a pas `upsert-desc`/`pin`.
- **la chaîne de livraison** : qui applique les 3 fixes keeper restants et
  ajoute les 2 capacités helper ? (Le dev, via #45 / dev-5 RECYCLE, après le
  `/ok` de #33.)
- **le verdict de convergence** : après les fixes, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 GREEN ?

### Code (composants impactés)

| composant | état mesuré (2026-10-11, branche `wt/issue-19-discord-thread-title-description` tip `95d4db0`) | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` (L221) + `build_description_lines` (L224) présents | Livré dans le GREEN partial |
| `pipeline/pj_room_keeper.py` | `build_description_for_card` (L572), `sync_description` (L695), `sync_all_descriptions` (L799) présents | **3 tests RED** : (1) `sync_description` L725 appelle `build_description_for_card(card, log=log)` SANS `issue_url_lookup` → `issue_url` non résolue → verdict `thread_id=None` ; (2) `_gh_repo()` L657 fait `.rsplit("/", 1)[-1]` sur `GH_REPO` (`hyron-fr/hermes-workflow`) → perd l'ORG → URL issue sans ORG ; (3) la déduplication par marqueur dans `sync_description` ne garantit pas qu'un second cycle ne poste pas un second message (test nominal épinglé) |
| `tests/test_thread_description.py` | 387 lignes, 10 cas, 7 GREEN / 3 RED | Banc qui gèle le contrat `contrat-5` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | Commandes `create`/`send`/`rename`/`threads` seulement (grep `upsert-desc\|pin` → 0 hit) | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → list[str], 0 réseau, 0 horloge, 0 aléa) et
`build_description_for_card` (sources injectées). L'écriture du message et de
l'épingle passe par l'adapter injecté `write_message` / le helper Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`) ;
l'issue #55 **est** le point à statuer de sa carte `t_8cc1e5c1`. La spec est
la source de vérité : le livrable de #55 n'est pas un code, mais **l'état de
convergence de la slice 5 de #19** : soit les 3 fixes keeper + les 2 capacités
helper sont appliqués et le banc passe 10/10 GREEN, soit l'escalade se
poursuit. La doc décrit le livré : ici le « livré » attendu est le GREEN 10/10
; jusqu'au re-push, l'état mesuré est 7/10 GREEN + helper incomplet.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — chevauche
  *développement* (slice 5 de #19) et *décision humaine* (l'escalade
  #27→#29→#45→#41→#55→#64→#70→#81), sans en être un nouveau : c'est la
  **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_8cc1e5c1`** (invariant : elle ne repart
  en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_8cc1e5c1`). L'**issue #55** est l'objet de
  décision qui la matérialise. État : la carte est déjà `done` ; l'issue
  reste `OPEN` (miroir orphelin, sans ligne `Importé depuis`).
- **Value objects** : le **branch head SHA** (`95d4db0` mesuré) ; le **banc
  7/10** (état de convergence partiel) ; l'**idempotency-key** `gh-issue-55`.
- **Domain events** : `/ok` humain sur l'issue #55 → aucun unblock (la carte
  est déjà `done`) → l'issue peut être fermée au merge de la PR de #19 (le
  pont ferme l'issue de sa ligne `Importé depuis`, pas #55) ou par geste
  humain (rattachement ou fermeture directe) → le vrai point à statuer
  conv-5 reste sur `t_f725879f` (blocked), tranché au re-push du GREEN.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`**
(10 cas), rejouable sans Discord ni réseau (sources injectées) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]`
  — composition pure, 4 lignes, omission des `None`/vides (4 cas GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (2 cas GREEN,
  1 cas RED : le reader qui lève ne doit pas tuer le tick).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)`
  — écrivain best-effort : dédup par marqueur, `edit` jamais second post
  (1 cas RED : un seul message épinglé mis à jour pas dupliqué).
- **1 cas RED supplémentaire** :
  `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception` —
  gestion d'erreur quand `gh pr list` lève (la ligne PR est omise mais tracée,
  pas d'exception).
- Les **3 cas RED** sont les critères d'acceptation restants de la slice 5 ;
  leur passage GREEN est la preuve de convergence.

## Lecture hexagonale (le core reste pur)

Le **core pur** : `build_description_lines` (fonction pure : issue_url,
branch, pr_url → list[str], 0 réseau, 0 horloge, 0 aléa) et
`build_description_for_card` (sources injectées, 0 réseau). L'écriture du
message épinglé et de l'épingle passe par le helper `discord_thread.py`
(adapter REST, hors core). Le contrat d'interface (marqueur `[description]`,
`sync_description`, `sync_all_descriptions`) est testable sans Discord :
les sources et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état**
(gh/git/blackboard) résolue **hors** du core, puis injectée dans le
formateur pur. Jamais l'inverse : le formateur ne lit pas le réseau.

## Frontières traversées (résumé)

```
issue #55 (GitHub, labels decision + kanban, idempotency-key gh-issue-55)
  → commentaire /ok humain (surface de décision)
  → (aucun unblock — t_8cc1e5c1 est déjà done)
  → l'issue reste OPEN (miroir orphelin : pas de ligne "Importé depuis")
  → le vrai point conv-5 reste sur t_f725879f (blocked)
  → re-push du GREEN par #45 / dev-5 RECYCLE
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → doc → doc-review → PR → merge → fermeture de l'issue #19 (pas #55)
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : un commit absent
du branch head est un travail non livré, quel que soit le handoff du worker.
Le point de fragilité supplémentaire de #55 est la **ligne d'import absente**
: le pont ne ferme pas l'issue #55 au `done` de la carte `t_8cc1e5c1` (ancre
[[pj-bridge-push-ancre]]), donc l'issue reste ouverte comme miroir orphelin.

## État mesuré (2026-10-11, rejouable)

- `origin/dev` = `2027333` (docs cadrage #29).
- `wt/issue-19-discord-thread-title-description` :
  - **local** (worktree `t_c22a7e74`) = `95d4db0` (31 commits au-dessus de
    `origin/dev` ; dernier = `docs(cadrage): issue #58 — miroir de décision`).
  - **remote** = `95d4db0` (en sync, `git rev-list --left-right --count HEAD...@{u}` = `0 0`).
  - `git status --short` : propre (0 fichier modifié dans le worktree).
- `git cat-file -t 6661362` → **fatal : Not a valid object name**
  (définitivement absent de toutes refs locales et remote).
- `grep DESCRIPTION_MARKER|build_description|sync_description` sur
  `pipeline/` (branche `wt/issue-19-discord-thread-title-description`) →
  **présents** dans `pipeline/engine.py` (L221, L224) et
  `pipeline/pj_room_keeper.py` (L572, L695, L799) (GREEN partial livré
  dans l'arbre).
- `grep upsert-desc|pin` sur `skills/gh-kanban-bridge/scripts/discord_thread.py`
  → **0 hit** (capacité non livrée).
- `sync_description` L725 : `build_description_for_card(card, log=log)` —
  **SANS** `issue_url_lookup` (fix manquant 1).
- `_gh_repo()` L657 : `(os.environ.get("GH_REPO") or "").rsplit("/", 1)[-1]`
  → perd l'ORG `hyron-fr` (fix manquant 2).
- `sync_all_descriptions` L828 : `issue_url_lookup=issue_url_lookup` —
  transmis ici, mais le test RED « reader qui lève ne tue pas le tick »
  reste rouge (fix manquant 3 : gestion d'exception dans la boucle).
- Banc `tests/test_thread_description.py` : **7/10 GREEN, 3 RED** (mesuré
  2026-10-11, rejouable via
  `python3 -m pytest tests/test_thread_description.py -q -p no:randomly`
  dans le venv hermes-agent, worktree `t_c22a7e74`).
  Les 3 cas rouges :
  - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`
    → `sync_description` (L725) appelle `build_description_for_card(card, log=log)`
    SANS `issue_url_lookup` → `_issue_url_from_card` ne résout pas l'URL →
    verdict `thread_id=None` au lieu de `TH-19`.
  - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
    → `_gh_repo()` (L657) fait `.rsplit("/", 1)[-1]` sur `GH_REPO`
    (`hyron-fr/hermes-workflow`) → perd l'ORG `hyron-fr` → URL issue
    `https://github.com/hermes-workflow/issues/19` au lieu de
    `https://github.com/hyron-fr/hermes-workflow/issues/19`.
  - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
    → la gestion d'exception dans `build_description_for_card` ne capture
    pas le reader qui lève (le tick meurt au lieu de tracer et omettre la ligne).
- **Aucune PR ouverte** vers `dev` depuis `wt/issue-19-discord-thread-title-description`
  (`gh pr list --state open` : 0 PR sur cette branche ; la PR #39 draft est
  CLOSED, la PR #46 est sur `fix/decision-jeton-apres-amorce`).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`
  (mesuré sur le checkout principal, qui contient les notes `issue-27.md`,
  `issue-41.md`, `issue-70.md` non commitées mais référencées dans le MOC).

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la
  boucle #5, aucun changement de code. L'issue #55 est un miroir orphelin :
  le `/ok` ne débloque rien (la carte cible est déjà `done`).
- **Travail débloqué (slice 5 de #19, à compléter)** :
  - `pipeline/pj_room_keeper.py` — 3 fixes :
    (1) `sync_description` L725 : transmettre `issue_url_lookup` (et
        `specs_reader`, `pr_reader`) à `build_description_for_card` ;
    (2) `_gh_repo()` L657 : ne pas `.rsplit` (conservation de l'ORG `hyron-fr`)
        ou reconstituer l'URL complète avec l'ORG ;
    (3) `build_description_for_card` : capturer l'exception du reader de source
        (le tick ne meurt pas, la ligne est omise et tracée).
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` — ajout des
    capacités `upsert-desc` (édition du message du fil) et `pin`
    (épingle du message).
- **Vault** : à la convergence, la slice 5 gagnera sa note composant et le
  MOC `docs/architecture/README.md` sera mis à jour par la carte `doc-k` —
  hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **Le contenu exact des 3 fixes keeper** — porté par le dev après le
   `/ok` de #33/#45 (le banc définit le contrat, pas le cadrage).
2. **La forme des capacités `upsert-desc`/`pin`** — porté par le dev ; le
   banc ne les teste pas directement (le helper est un adapter, injecté).
3. **Le geste de fermeture de l'issue #55** — le pont ne la ferme pas
   (pas de ligne `Importé depuis` sur la carte `t_8cc1e5c1`) ; la fermeture
   est portée par le merge de la PR de #19 (qui ferme #19, pas #55) ou par
   geste humain (rattachement commenté ou fermeture directe). Ce cadrage ne
   décide pas de ce geste.
4. **La publication live des copies `~/.hermes/scripts/`** (divergence D2
   déclarée dans le handoff `dev-5`) — opération de fin de graphe contrôlée
   par identité, hors périmètre de cette décision.

Ces points sont **documentés**, pas décidés ici.

## Hors-scope

- **Le re-push du GREEN** : porté par #45 / dev-5 RECYCLE (carte
  `t_854f0f77`, assignée `pj-dev`), jamais par ce cadrage.
- **La convergence effective de la slice 5** : portée par la carte
  `t_f725879f` (conv-5, `pj-test`) après le re-push.
- **Les slices 1–4 de #19** : déjà livrées, cadrées par la note composant
  `pj-thread-name` (slices 2–4) et la note de cadrage initiale (commit
  `ed75032`).
- **La duplication bridge↔pipeline↔agents des `pj_*.py`** : divergence connue
  (les 3 copies du keeper sont identiques à ce stade), non traitée par #55.
- **Le verdict de convergence** : porté par `pj-test` sur la carte
  `t_f725879f`, pas par ce cadrage.
