---
type: context
status: draft
tags: [architecture, decision, escalation, discord, github, kanban, cadrage, grill-me, decision-interface]
issues: [42]
---

# Cadrage architectural — issue #42 « t3 grill-me »

## Positionnement (cadre exact)

L'issue #42 est une **issue de décision** (`labels: kanban, decision`, `state: OPEN`,
ouverte 2026-10-04) issue de la **3ᵉ escalade** du chantier #19
(Discord thread title and description update). Elle matérialise le point à statuer
sur la carte **`t_566c200d`** (t3 grill-me, board `pj-hermes-workflow`), bloquée
depuis le 04/10 (106 h au moment du cadrage).

### Chaîne d'escalade

```
#28 (1ʳᵉ escalade) → #32 (2ᵉ) → #44 (3ᵉ) → #42 (t3 grill-me, 4ᵉ)
```

Chacune porte le **même** point à statuer : le commit GREEN dev-5 `6661362`
est perdu (mesuré absent de tout l'historique git et de l'API GitHub). Le banc
`tests/test_thread_description.py` (10 cas) est le contrat de re-génération.

### État mesuré (2026-10-08)

| fait | preuve |
|---|---|
| `6661362` absent du dépôt local **et** du remote | `git cat-file -t 6661362` → `Not a valid object name` ; `git log --all` → 0 hit |
| Branche `wt/issue-19-discord-thread-title-description` pointe sur `6a827a0` (cadrage #45) | `git log --oneline wt/issue-19-discord-thread-title-description` |
| `origin/dev` = `2027333` (cadrage #29) | `git rev-parse --short origin/dev` |
| Banc `tests/test_thread_description.py` **absent du dépôt** (worktree t_7f053139, base `2027333`) | `ls tests/` → 0 hit `test_thread_description` |
| API slice 5 (`DESCRIPTION_MARKER`, `build_description_*`, `sync_description`, `upsert-desc`) **absente** de `pipeline/`, `bridge/`, `skills/` | `grep -rn` → 0 hit |
| Helper Discord n'a pas de capacité `upsert-desc` ni `pin` | `grep upsert-desc\|pin skills/gh-kanban-bridge/scripts/discord_thread.py` → 0 hit |
| Worktree partagé #19 : `t_c22a7e74` | `git worktree list` |
| Worktree de re-push : `t_4d471dce` (`wt/issue-19-restore-green-5`) | `git worktree list` |

### Ce que la décision débloque

Le jeton `/ok` en tête de commentaire sur l'issue #42 :
1. Débloque la carte `t_566c200d` (t3 grill-me) via `pipeline/pj_decision.py`.
2. Repart la carte en file → le dispatcher re-spawn `pj-master`.
3. **Travail débloqué** (hors périmètre de cette issue) : re-génération du GREEN
   dev-5 depuis le banc RED test-5 (10 cas), sur la branche
   `wt/issue-19-discord-thread-title-description`.

Tout autre commentaire est une demande d'éclaircissement — rien n'est débloqué.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #42
  (`labels: kanban, decision`, `idempotency-key gh-issue-42`). Adapter : `gh` CLI.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_566c200d`, invoqués par le câblage de #5
  ([[pj-decision]] : `decision_from_comment` calcule, l'appelant applique).
- **Discord** — canal de notification (`pj_escalate.py` a posté le grill-me
  dans le thread « hermes-workflow #28 · Décision conv-5 GREEN dev-5 perdu »).
  La capacité `upsert-desc` + `pin` du helper Discord reste **absente du code**.
- **Aucun nouveau port** : toutes les surfaces existent ; #42 réutilise la boucle
  de décision #5 sans ajouter de composant.

### Fonctionnel (capacité traversée)

La capacité traversée est la **décision humaine sur blocage** (issue #5, livrée),
au service de la capacité **notification Discord du chantier #19** — moitié
« description » (slice 5 de #19).

- **Moitié titre (slices 1–4, livrées)** : formateur pur `format_title` + table
  `TITLE_ICONS` (4 états) dans `pipeline/engine.py`, 3 lecteurs du nom de thread,
  keeper écrivain unique du titre avec coalescence `TITLE_WINDOW = 600 s`.
- **Moitié description (slice 5, GREEN perdu)** : ce que #42 débloque. Le fil
  Discord d'une issue doit porter un **bloc Description épinglé** (marqueur
  `[description]`, 4 lignes max : `**Issue**`, `**Branche**`, `**PR**` ; omission
  des sources absentes, jamais placeholder).

### Code (composants impactés)

Le périmètre de la slice 5 de #19 (à re-pousser après le `/ok`) :

| composant | impact | état |
|---|---|---|
| `pipeline/engine.py` | `DESCRIPTION_MARKER` + `build_description_lines` (composition pure) | **non livré** (absent du code) |
| `pipeline/pj_room_keeper.py` + miroirs `bridge/`, `agents/` | `build_description_for_card` + `sync_description` + `sync_all_descriptions` | **non livré** |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | capacité `upsert-desc` + `pin` | **non livré** |
| `tests/test_thread_description.py` | banc RED 10 cas (contrat `contrat-5`) | **absent du dépôt courant** (existant uniquement sur la branche `wt/issue-19-…` tip `6a827a0`) |

**Core pur** à préserver : `build_description_lines` et `build_description_for_card`
(chaînes/dicts, sources injectées — 0 réseau, 0 horloge, 0 aléa). L'écriture du
message et de l'épingle passe par l'adapter `discord_thread.py`.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d`).
L'issue #42 est le **point à statuer** de sa carte `t_566c200d` (AC Gherkin :
un seul message Description épinglé, lignes correspondant aux valeurs réelles ;
doublon détecté → refusé + `request-changes`). La doc décrit le livré : ici le
« livré » attendu est le re-poussage du GREEN dev-5. Jusqu'au `/ok`, l'état
mesuré est le RED test-5 et **aucune** doc ne peut décrire la moitié description
comme livrée.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *décision humaine sur blocage* (contexte #5,
  livrée) au service du contexte *notification Discord du chantier #19*.
- **Agrégat racine** : la **carte `t_566c200d`** (invariant : elle ne repart en
  `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_566c200d`). L'issue #42 est l'objet de décision.
- **Value objects** : le **bloc Description** (marqueur `[description]` + 3 lignes,
  4 max, omission plutôt que placeholder) ; le `thread_id` résolu par l'ancre
  `Importé depuis …/issues/N` ; la clé `branch` du plan de slices.
- **Domain events** : `commentaire GitHub /ok` sur #42 → `comment` + `unblock` sur
  `t_566c200d` (re-spawn `pj-master`) → **re-génération du GREEN** (nouveau commit
  sur `wt/issue-19-discord-thread-title-description`, banc 10/10 vert) → convergence.

## Lecture TDD (contrats testables)

Le banc `tests/test_thread_description.py` (10 cas, présent sur la branche
`wt/issue-19-…` tip `6a827a0`) est le contrat testable :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]`
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader, issue_url_lookup)`
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)`
- `keeper.sync_all_descriptions(...)` — ne lève jamais (lecker de source qui lève
  est capturé et tracé, le cycle du keeper ne meurt pas)

Ces contrats sont testables sans Discord ni réseau (sources injectées, sentinelle
`sys.meta_path` pour prouver la pureté du core).

## Lecture hexagonale (le core reste pur)

- **Core pur** : `build_description_lines` + `build_description_for_card` —
  chaînes/dicts, sources injectées, 0 réseau, 0 horloge.
- **Adapters** : lecteur du board (`hermes kanban list --json`), plan de slices
  (`specs/<n>/slices.json`), `gh pr list --head <branche>`, écriture Discord
  (`discord_thread.py upsert-desc` / `pin`).
- **Porteur** : `pipeline/pj_room_keeper.py` — cycle de vie, déduplication par
  marqueur `[description]`, best-effort. Le keeper est déjà l'écrivain unique du
  titre (slice 4) ; la description s'y implante à côté du cycle de renommage.

## Frontières traversées (résumé)

```
carte t_566c200d bloquée (kanban) + GREEN dev-5 6661362 perdu
  → (pj_escalate) issue ENFANT #42 + notification Discord                  [Discord]
  → (commentaire GitHub /ok sur #42)                                        [GitHub]
  → (pj_decision) unblock → ready → re-spawn t_566c200d (pj-master)         [kanban]
  → re-génération GREEN dev-5 (nouveau commit, banc 10/10 vert)
  → convergence (verdict pj-test) → doc → doc-review → PR → merge
```

Deux frontières, **aucune nouvelle** : **GitHub ↔ kanban** (décision → effet,
livrée par #5) et **Discord ↔ kanban** (le travail débloqué écrit le bloc
Description dans le fil via l'adapter helper). L'issue #42 elle-même ne traverse
rien : elle est le point où l'humain franchit la première frontière.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la boucle #5,
  aucun changement de code.
- **Travail débloqué (slice 5 de #19, à re-générer)** : `pipeline/engine.py`
  (composition pure), `pipeline/pj_room_keeper.py` + miroirs (écrivain),
  `skills/gh-kanban-bridge/scripts/discord_thread.py` (`upsert-desc` + `pin`),
  `tests/test_thread_description.py` (banc, verrouillé contractuellement).
- **Vault** : à la convergence, la moitié description gagnera sa note composant et
  le MOC `docs/architecture/README.md` sera mis à jour — hors périmètre de cette décision.

## Hors-scope

- **Le re-génération du GREEN dev-5** : porté par `dev-5`/`dispatcher`, jamais
  par ce cadrage.
- **La convergence effective de la slice 5** : portée par la carte
  `t_566c200d` après le `/ok` humain.
- **Les slices 1–4 de #19** : déjà livrées, cadrées par la note `issue-19` et
  la note composant `pj-thread-name`.
- **La duplication bridge↔pipeline↔agents des `pj_*.py`** : divergence connue,
  non traitée par #42.
- **Le verdict de convergence** : porté par `pj-test`, pas par ce cadrage.
- **La réconciliation « débloquée hors `/ok` »** : signalé par la mémoire projet,
  à trancher par l'orchestrateur.
