---
type: context
status: draft
tags: [architecture, decision, escalation, convergence, recycle, slice-5, description-epinglee, cadrage]
issues: [24]
---

# Cadrage architectural — issue #24 « slice 5/5 — convergence » (7ᵉ import conv-5)

## Positionnement (cadre exact)

L'issue #24 (`labels: kanban` + `decision`, `idempotency-key gh-issue-24`, carte
racine du pipeline `t_96d403c8`) est le **7ᵉ import du point à statuer conv-5** du
chantier **#19** (« Discord thread title and description update », moitié «
Description épinglée »). Elle matérialise la carte **`t_f725879f`** (« slice 5/5 —
convergence », assignée à `pj-test`, board `pj-hermes-workflow`), qui est
**bloquée** : son verdict de convergence est impossible tant que le commit GREEN
de la slice 5 n'est pas livré sur le worktree partagé.

La chaîne conv-5 (mesurée, rejouable) :

| n° | Issue | Objet | Note de cadrage |
|---|---|---|---|
| 1ᵉʳ | #27 | point à statuer conv-5 (`t_f725879f`) | (note sur `wt/issue-19-discord-thread-title-description`) |
| 2ᵉ | #29 | même point, ré-importé par le pont de couverture | [[issue-29]] |
| 3ᵉ | #45 | RECYCLE du GREEN perdu (carte `t_7aaf3d49`) | (note issue-45 sur `wt/issue-19-discord-thread-title-description`) |
| 4ᵉ | #41 | t3 grill-me conv-5 (carte `t_3f7e0be4`) | (note sur `wt/issue-19-discord-thread-title-description`) |
| 5ᵉ | #33 | tranchement : re-poussage GREEN par cycle normal | (voir commentaire de `t_f725879f`, 2026-10-10) |
| 6ᵉ | #26 | miroir GitHub « premier import » de l'état mesuré 2026-10-10 | (note issue-26 sur `wt/issue-19-discord-thread-title-description`) |
| **7ᵉ** | **#24** | **reprise du pipeline complet (t1..t5 + t3b) sur le même point** | **cette note** |

**État mesuré au 2026-10-10 (worktree partagé `t_c22a7e74`, rejouable)** :

- HEAD = `6a2d8e3` (docs issue-26), `0 0` vs `@{u}`, branch
  `wt/issue-19-discord-thread-title-description`.
- **Banc `tests/test_thread_description.py` = 7/10 GREEN, 3 RED** (mesuré,
  venv Hermes) — les 3 rouges sont les mêmes que le verdict conv-5 de pj-test
  (2026-10-08) : (1) `sync_description` n'injectait pas `issue_url_lookup`,
  (2) `_gh_repo()` perdait l'ORG via `rsplit("/")[-1]`, (3)
  `sync_all_descriptions` n'injectait pas les lecteurs de source.
- **Correctifs présents mais NON COMMIS** : diff uncommitted
  `pipeline/pj_room_keeper.py` (+43/-13) portant le correctif OOM
  (`_emit(list(log_list))` — instantané, boucle de journalisation infinie
  supprimée) + les 3 retouches keeper ci-dessus.
- **Capacités `upsert-desc` / `pin` du helper Discord : ABSENTES** de
  `skills/gh-kanban-bridge/scripts/discord_thread.py` (112 lignes ; commandes
  `create`/`send`/`threads`/`rename` seulement).
- Le commit GREEN original `6661362` est **perdu de toutes les refs**
  (`git cat-file -t 6661362` → fatal) — tranchement #33 (JB, 2026-10-10) :
  **re-poussage par cycle normal via issue #45** (dev-5 RECYCLE, carte
  `t_854f0f77`, assignée `pj-dev`), jamais un replay de `6661362`.

**Ce que cette issue débloque / porte** : le jeton `/ok` (premier élément du
commentaire GitHub) débloque la carte `t_f725879f` ; l'effet attendant est le
**commit GREEN complet** (diff uncommitted + correctif OOM + `upsert-desc`/`pin`
du helper) poussé sur `wt/issue-19-discord-thread-title-description`, puis le
verdict de convergence (banc 10/10). Tout autre commentaire est une demande
d'éclaircissement.

**Verdict t3 (carte `t_30d54ade`, 2026-10-10)** : `PROTOTYPE: non`,
`AMBIGU: aucune`, `ARTEFACT: aucun` — 5 ambiguïtés détectées, toutes levées par
mesure ; 0 question humaine. Domaine mécanique (banc gelé, périmètre connu),
aucun livrable perceptible nouveau.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #24 (le
  miroir). Adapter : `gh` CLI, lu par le pont. La carte `t_f725879f` est l'objet
  de la reprise.
- **Kanban Hermes** — source de vérité de l'état : `t_f725879f` en `blocked`
  porte le point à statuer ; le `/ok` produit `comment` + `unblock` (boucle #5,
  [[pj-decision]] : `decision_from_comment` calcule, l'appelant applique).
- **Git / worktree partagé `t_c22a7e74`** — surface de livraison : le branch
  head de `wt/issue-19-discord-thread-title-description` est la **preuve de
  livraison** de la slice 5 ; le diff uncommitted n'est pas un travail livré
  (invariant de couverture commit-à-commit, issue #2 / [[pj-bridge-coverage-gate]]).
- **Aucun nouveau port** : les trois surfaces existent ; #24 réutilise la boucle
  de décision #5 et la chaîne conv-5.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** de la moitié
« Description » de #19 — pas une fonctionnalité nouvelle. Les slices 1–4 de #19
(moitié titre : formateur pur, 3 lecteurs, écrivain unique + coalescence 600 s)
sont livrées (note composant `pj-thread-name`, sur la branche de #19). La slice 5 (bloc Description épinglé :
marqueur `[description]` + lignes `**Issue**`/`**Branche**`/`**PR**`, 4 lignes
max, omission jamais placeholder) est l'objet du verdict : banc 10/10 GREEN +
code présent dans le commit poussé.

### Code (composants impactés)

| composant | état mesuré 2026-10-10 | impact slice 5 |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` (L221) + `build_description_lines` (L224) **présents** (GREEN partial, commit `55e6659`) | Livré |
| `pipeline/pj_room_keeper.py` | `build_description_for_card` (L572), `sync_description` (L715), `sync_all_descriptions` (L829) **présents** ; diff uncommitted = correctif OOM + 3 retouches keeper | **À commiter** |
| `tests/test_thread_description.py` | 387 lignes, 10 cas, **7 GREEN / 3 RED** (mesuré) | Banc gelé (contrat-5), intouchable |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | 112 lignes ; `create`/`send`/`threads`/`rename` seulement | **`upsert-desc` + `pin` à ajouter** |

Le **core pur** à préserver : `build_description_lines` (composition pure :
issue_url, branch, pr_url → `list[str]`, 0 réseau) et
`build_description_for_card` (sources **injectées** — `specs_reader`,
`pr_reader`, `issue_url_lookup` ; le banc empoisonne le réseau et le
sous-système). L'écriture du message et de l'épingle passe par l'adapter
injecté `write_message` / le helper Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`) ;
le contrat de la slice 5 y est fixé (message Description dédié épinglé, jamais
le champ `topic` — mesuré : jeté en silence). L'issue #24 **est** le point à
statuer de sa carte `conv-5` : AC Gherkin de `t_f725879f` (un seul message
Description épinglé, lignes correspondant aux valeurs réelles ; doublon →
refusé + `request-changes`). La doc décrit le livré : ici le « livré » attendu
est le commit GREEN complet ; l'état mesuré est 7/10 + diff uncommitted +
helper incomplet, et **aucune** doc ne peut décrire la moitié description comme
livrée tant que le commit n'est pas poussé.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *convergence / livraison* — jonction entre
  *développement* (slice 5 de #19) et *décision humaine* (chaîne #27→#29→#45→#41→#33→#26→#24).
- **Agrégat racine** : la **carte `t_f725879f`** (invariant : elle ne repart en
  `ready` que sur un `/ok` portant sa ligne canonique `carte:
  pj-hermes-workflow/t_f725879f`). L'issue #24 est l'objet de décision qui la
  matérialise (7ᵉ miroir).
- **Value objects** : le **branch head SHA** (`6a2d8e3` mesuré) ; le **diff
  uncommitted** (+43/-13, OOM + 3 retouches) ; le **banc 7/10** (état de
  convergence partiel) ; l'**idempotency-key** `gh-issue-24`.
- **Domain events** : `/ok` humain sur #24 → unblock de `t_f725879f` →
  dev-5 RECYCLE (carte `t_854f0f77`) committe le diff + le correctif OOM +
  `upsert-desc`/`pin` → push vérifié `0 0` → banc 10/10 GREEN → convergence
  (verdict `pj-test`) → doc → doc-review → PR #19 → merge.

## Lecture TDD (contrats testables)

Le contrat testable est le **banc `tests/test_thread_description.py`** (10 cas,
rejouable sans Discord ni réseau), mesuré 7/10 au 2026-10-10 :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]`
  — composition pure, 4 lignes, omission des `None`/vides (GREEN).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources injectées (RED : le reader qui
  lève ne doit pas tuer le tick — corrigé dans le diff uncommitted).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None,
  specs_reader, pr_reader, issue_url_lookup)` — écrivain best-effort : dédup
  par marqueur, `edit` jamais second post (RED : un seul message épinglé mis à
  jour, pas dupliqué — corrigé dans le diff uncommitted).
- Les **3 cas RED** sont les critères d'acceptation restants ; leur passage
  GREEN **dans le commit poussé** est la preuve de convergence (le banc audite
  le commit, jamais le dirty state).

## Lecture hexagonale (le core reste pur)

Le **core pur** : `build_description_lines` (fonction pure, 0 réseau, 0
horloge, 0 aléa) et `build_description_for_card` (sources injectées). L'écriture
du message épinglé et de l'épingle passe par le helper `discord_thread.py`
(adapter REST, hors core). La description est une **lecture d'état**
(gh/git/blackboard) résolue **hors** du core puis injectée dans le formateur
pur — jamais l'inverse. La coalescence du titre (fenêtre 600 s, 429 Discord)
s'applique au titre (slice 4) ; la description est un message dédié dont la
réécriture est une édition idempotente par marqueur, pas un renommage.

## Frontières traversées (résumé)

```
issue #24 (GitHub, labels kanban+decision, idempotency-key gh-issue-24)
  → commentaire /ok humain (surface de décision)
  → unblock de t_f725879f (kanban)
  → dev-5 RECYCLE (t_854f0f77) : commit GREEN = diff uncommitted + OOM + upsert-desc/pin
  → push sur wt/issue-19-discord-thread-title-description (preuve commit-à-commit)
  → banc test_thread_description.py 10/10 GREEN (preuve de convergence)
  → convergence (verdict pj-test) → doc → doc-review → PR #19 → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : le diff uncommitted
du worktree partagé n'est pas un travail livré tant qu'il n'est pas commité et
poussé.

## État mesuré (2026-10-10, rejouable)

- Worktree partagé `/home/elix/pj-repos/hermes-workflow/.worktrees/t_c22a7e74`,
  branch `wt/issue-19-discord-thread-title-description`, HEAD `6a2d8e3`,
  `0 0` vs `@{u}`.
- `git status --short` → `M pipeline/pj_room_keeper.py` (+43/-13 : correctif
  OOM `_emit(list(log_list))` L589-631 + retouches `_issue_url_from_card` /
  `_gh_repo` / signature `sync_description`) + `?? diag2.py` (diagnostic,
  à supprimer — tranchement #33).
- `pytest tests/test_thread_description.py -q` → **3 failed, 7 passed**
  (venv Hermes ; les 3 rouges nommés ci-dessus).
- `skills/gh-kanban-bridge/scripts/discord_thread.py` : 112 lignes, commandes
  `create`/`send`/`threads`/`rename` — **0 hit** `upsert-desc` / `pin`.
- `git cat-file -t 6661362` → fatal (GREEN original perdu de toutes les refs).
- Tranchement acquis (issue #33, JB, 2026-10-10) : re-poussage par cycle
  normal via #45 (`t_854f0f77`, pj-dev) — pas de replay de `6661362`.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la
  boucle #5, aucun changement de code.
- **Travail débloqué (slice 5 de #19, à commiter et compléter)** :
  - `pipeline/pj_room_keeper.py` — commit du diff uncommitted (correctif OOM +
    3 retouches keeper).
  - `skills/gh-kanban-bridge/scripts/discord_thread.py` — ajout des capacités
    `upsert-desc` (édition du message du fil) et `pin` (épingle du message).
- **Vault** : à la convergence, la moitié description gagnera sa note
  composant et le MOC `docs/architecture/README.md` sera mis à jour par la
  carte `doc-k` (phase 4, post-merge) — hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** : (1) **la forme exacte des capacités
`upsert-desc`/`pin`** du helper — portée par le dev (le banc ne teste pas le
helper directement : adapter injecté) ; (2) **le sort du fichier `diag2.py`**
(untracked, diagnostic 2026-10-07) — commit ou suppression, décision du dev au
moment du commit GREEN ; (3) **la publication live des copies
`~/.hermes/scripts/`** (divergence D2 déclarée dans le handoff `dev-5`) —
opération de fin de graphe contrôlée par identité. Ces points sont
**documentés**, pas décidés ici.
