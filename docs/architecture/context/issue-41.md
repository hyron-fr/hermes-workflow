---
type: context
status: draft
tags: [architecture, decision-interface, escalation, discord, github, kanban, cadrage, slice-5, description-epinglee, recycle, decision-ticket]
issues: [41]
---

# Cadrage architectural — issue #41 « t3 grill-me » (conv-5, 4ᵉ échelon — GREEN slice-5 perdu)

## Positionnement (cadre exact)

L'issue #41 est une **carte de décision** (labels `decision` + `kanban`, OPEN sur
`hyron-fr/hermes-workflow`), importée dans le kanban Hermes comme `t_b6ac7c9e`
(idempotency-key `gh-issue-41`). Elle **matérialise le 4ᵉ échelon de la chaîne
conv-5** du chantier #19 (« Discord thread title and description update ») :
`#19 → #27 → #30 → #43 → #41` (cette issue).

**Elle porte le point à statuer hérité de la carte `t_3f7e0be4`** (t3 grill-me de
l'issue #27, bloquée `needs_input`). Le point : le commit GREEN de la slice 5
(démo 6661362) a disparu (422 GitHub, reflog vide, `git fsck` 0 orphelin), et la
voie de re-poussée n'était pas tranchée. Le corps de l'issue pointe explicitement
la carte `t_3f7e0be4` et le ticket #27.

**Ce que la décision débloque** : le re-poussage du GREEN perdu de la slice 5/5
de #19 (moitié « Description épinglée » du thread Discord). Les 3 options étaient :
(a) re-run dev-5 par le dispatcher [recommandé], (b) reprise manuelle par
pj-dev, (c) autre.

**Écart mesuré sur le travail déjà effectué sur la branche ciblée** :
Le GREEN partial vit dans le commit `55e6659` (baseline conv-audit, worktree
partagé `t_c22a7e74`). Mesuré 2026-10-08 par le banc `uv run --with pytest` :
**7/10 GREEN, 3 RED**. Les 3 cas restants exigent 3 retouches dans
`pipeline/pj_room_keeper.py` (le banc reste intouchable, contrat-5) :

| # | Cas RED | Retouche |
|---|---|---|
| 1 | `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique` — `thread_id=None` car le code appelle `thread_lookup()` module-level → `engine.resolve_thread` → réseau (empoisonné par le banc) | `sync_description` / `sync_all_descriptions` doivent **déduire le thread_id du body de la carte** (ancre `Importé depuis …/issues/N` → `TH-N` déterministe, 0 réseau) ; le `thread_lookup` module-level n'est appelé **que si** le fil n'est pas déductible du body |
| 2 | `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception` — org perdu : `_issue_url_from_card` reconstruit l'URL via `_gh_repo()` (dernier segment du slug) au lieu de lire l'org complet depuis l'ancre du body | `_issue_url_from_card` extrait l'org depuis le pattern `github.com/<org>/<repo>/issues/N` présent dans le body ; le fallback `_gh_repo()` n'est utilisé que si l'ancre est absente |
| 3 | `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick` — verdict manquant : quand un lecteur (ex. `specs_reader`) lève, le `continue` saute l'écriture du verdict alors que le banc attend 1 écriture (bloc omis mais tracé) | `sync_all_descriptions` écrit le verdict (avec le bloc omis et le log de l'exception) même quand un lecteur lève, avant le `continue` |

Aucune des 3 retouches ne touche `tests/` ni `pipeline/engine.py`.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières externes)

- **GitHub** — canal de décision : commentaire `/ok` en tête sur l'issue #41
  (l'enfant). Adapter : `gh` CLI, lu par le pont. La carte cible du re-poussage
  est `t_3f7e0be4` / `t_7aaf3d49`.
- **Kanban Hermes** — source de vérité du plan. L'effet est `comment` + `unblock`
  sur la carte de re-poussage du GREEN, invoqués par le câblage de #5.
- **Discord** — le but du travail débloqué : thread du ticket #19. Adapter :
  `skills/gh-kanban-bridge/scripts/discord_thread.py` (capacité `upsert-desc` +
  `pin` annoncée mais absente du helper versionné — hors périmètre de cette
  décision, opération de fin de graphe).
- **Aucun nouveau port** : les trois surfaces existent ; l'issue #41 réutilise la
  boucle de décision #5 et n'ajoute rien de neuf.

### Fonctionnel (capacité traversée)

La capacité traversée est la **décision humaine sur blocage** (issue #5, livrée),
au service de la capacité **notification Discord du chantier #19** — moitié
« description » (slice 5 de #19). Les deux moitiés :

- **Moitié titre (slices 1–4, livrées et présentes)** : formateur pur
  `format_title` + table `TITLE_ICONS` (4 états 🎬/⚙️/⚠/🛑) dans
  `pipeline/engine.py`, keeper comme écrivain unique du titre avec coalescence
  par fenêtre `TITLE_WINDOW = 600 s`.
- **Moitié description (slice 5, le GREEN est perdu)** : ce que cette issue
  débloque. Le GREEN partial vit dans le commit `55e6659` (baseline conv-audit,
  worktree partagé `t_c22a7e74`) ; banc mesuré 7/10, 3 retouches restantes.

### Code (composants impactés par le travail débloqué)

Le périmètre de la slice 5 (mesuré dans le banc `tests/test_thread_description.py`
et le diff du worktree partagé `t_c22a7e74`) :

- **`pipeline/engine.py`** — `DESCRIPTION_MARKER` + `build_description_lines`
  (composition **pure** du bloc : 4 lignes max, omission des sources absentes,
  log bruyant). Le formateur pur du titre (slices 1–3) y vit déjà.
- **`pipeline/pj_room_keeper.py`** — porteur de l'écriture (GREEN partial dans le
  commit `55e6659`, banc 7/10) : 3 retouches à appliquer (mesurées 2026-10-08 par
  le banc) : (1) déduction du `thread_id` depuis l'ancre du body (pas `thread_lookup`
  module-level), (2) lecture de l'org depuis l'ancre du body dans `_issue_url_from_card`
  (pas reconstitution via `_gh_repo()`), (3) écriture du verdict même quand un
  lecteur lève dans `sync_all_descriptions`. `build_description_for_card` +
  `sync_description` (déduplication par marqueur `[description]`, édition jamais
  second post, accueil du fil intact) + `sync_all_descriptions` (délégation à
  `sync_description` avec lecteurs injectés, ne lève jamais). Le keeper est
  déjà l'écrivain unique du titre (slice 4) : la description s'y implante
  **à côté** du cycle de renommage, sans conditionner les transitions.
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** — le helper doit
  gagner `upsert-desc` + `pin` (capacité d'édition + d'épingle). Divergence D2
  déclarée : la copie live ne les porte pas ; publication hors périmètre.
- **`tests/test_thread_description.py`** — le banc RED intact (387 lignes,
  10 cas), qui gèle le contrat `contrat-5`. C'est lui qui sera GREEN quand le
  travail sera re-poussé.

Le **core pur** à préserver : `build_description_lines` et
`build_description_for_card` (chaînes/dicts, sources **injectées** — 0 réseau,
conformément au banc qui « empoisonne » le réseau) ; l'écriture du message et
de l'épingle passent par l'adapter injecté `write_message` / le helper Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d` — le
contrat de la slice 5 y est fixé : message dédié épinglé, lignes issue/branche/PR,
omission jamais placeholder) ; l'issue #41 **est** le point à statuer de sa carte
`conv-5`. La doc décrit le livré : ici le « livré » attendu est le re-poussage du
GREEN dev-5 ; jusqu'au `/ok`, l'état mesuré est le RED test-5 et **aucune** doc
ne peut décrire la moitié description comme livrée.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *décision humaine sur blocage* (contexte #5,
  livrée) au service du contexte *notification Discord du chantier #19*.
- **Agrégat racine** : la **carte de re-poussage** (invariant : elle ne repart en
  `ready` que sur un `/ok` portant sa ligne canonique `carte: pj-hermes-workflow/…`).
  L'**issue #41** est l'objet de décision qui la matérialise.
- **Value objects** : le **bloc Description** (marqueur `[description]` + lignes
  `**Issue**`/`**Branche**`/`**PR**`, 4 lignes max, omission plutôt que
  placeholder) ; le `thread_id` résolu par l'ancre `Importé depuis …/issues/N` ;
  la clé `branch` du plan de slices.
- **Domain events** : `commentaire GitHub /ok` sur #41 → `comment` + `unblock` sur
  la carte de re-poussage → **re-poussage du GREEN** (commit du diff existant +
  poussée sur `wt/issue-19-discord-thread-title-description`, banc 10/10 vert) →
  convergence.

## Lecture TDD (contrats testables)

Le banc existant **est** le contrat (RED mesuré : `10 failed in 0.21s` le
2026-10-04, rejouable via `uv run --with pytest`) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]` —
  composition pure, 4 lignes, omission des `None`/vides, ordre `Issue`→`Branche`→`PR`.
- `keeper.build_description_for_card(card, *, specs_reader, pr_reader, issue_url_lookup)` —
  assemblage des sources **injectées** (0 réseau ; le banc « empoisonne » le réseau
  par sentinelle).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None,
  issue_url_lookup=None, specs_reader=None, pr_reader=None)` — écrivain best-effort :
  dédup par marqueur, `edit` jamais second post, accueil intact, **ne lève jamais**.
- `keeper.sync_all_descriptions(cards, *, fetch_messages, write_message, log=None,
  specs_reader=None, pr_reader=None, issue_url_lookup=None)` — délégation à
  `sync_description`, ne lève jamais.

## Lecture hexagonale (le core reste pur)

Le **core pur** : la composition du bloc Description (`build_description_lines`) et
l'assemblage de sources par carte (`build_description_for_card`) — chaînes/dicts,
sources injectées, **aucun** Discord, kanban, réseau, horloge. Les adapters restent
en périphérie : le lecteur du board, le plan de slices (injecté), `gh pr list`
(injecté), et l'écriture du message + épingle (`discord_thread.py upsert-desc` /
`pin`). Le keeper est le **porteur** (cycle de vie, déduplication, best-effort),
pas le décideur de contenu.

## Frontières traversées (résumé)

```
carte de re-poussage bloquée (kanban) + GREEN perdu (banc 10/10 RED)
  → (commentaire GitHub /ok sur #41)                                       [GitHub]
  → (pj_decision) unblock → ready → re-spawn de la carte de re-poussage     [kanban]
  → commit du diff existant + push sur wt/issue-19-… → banc 10/10 vert
  → convergence (verdict pj-test) → doc-5 → t6 PR #19
```

Deux frontières traversées, **aucune nouvelle** : **GitHub ↔ kanban** (voie de
décision, livrée par #5) et **Discord ↔ kanban** (le travail débloqué écrit le bloc
Description dans le fil via l'adapter helper). L'issue #41 elle-même ne traverse
rien : elle est le point où l'humain franchit la première frontière.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` + `pipeline/pj_escalate.py`
  / `pipeline/pj_notify.py` — la boucle #5, aucun changement de code.
- **Travail débloqué (slice 5 de #19, à re-pousser)** : `pipeline/engine.py`
  (composition pure du bloc), `pipeline/pj_room_keeper.py` (écrivain, diff non
  commité déjà présent dans le worktree partagé), `skills/gh-kanban-bridge/scripts/
  discord_thread.py` (`upsert-desc` + `pin`), `tests/test_thread_description.py`
  (banc, déjà verrouillé contractuellement).
- **Vault** : à la convergence, la moitié description gagnera sa note composant
  et le MOC `docs/architecture/README.md` sera mis à jour par la carte `doc-5` —
  hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** : (1) la voie exacte de re-poussage (a/b/c) —
décision de l'humain sur le thread #27, déjà posée ; (2) le trou de
réconciliation « débloquée hors `/ok` » ; (3) la publication live des copies
`~/.hermes/scripts/` (divergence D2 déclarée). Ces points sont **documentés**,
pas décidés ici.
