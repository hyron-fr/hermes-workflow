---
type: context
status: draft
tags: [architecture, decision-interface, escalation, discord, github, kanban, cadrage, slice-5, description-epinglee, recycle]
issues: [45]
---

# Cadrage architectural — issue #45 « slice 5/5 — dev (GREEN) — RECYCLE : re-livrer le commit GREEN perdu »

## Positionnement (cadre exact)

L'issue #45 **n'est pas une tâche de développement** : c'est une **issue de décision**
(labels `decision` + `kanban`, OPEN), importée du kanban Hermes (board
`pj-hermes-workflow`) comme carte `t_854f0f77` (idempotency-key `gh-issue-45`), et
elle **matérialise la 4ᵉ escalade** de la chaîne conv-5 du chantier #19 (« Discord
thread title and description update ») : `#19 → #20/#21 → #28 → #32 → #45`.

**Elle porte le point à statuer sur la carte `t_7aaf3d49`** (RECYCLE GREEN slice 5/5,
assignée à `pj-master`), bloquée sur le ticket #19. Pour trancher, il faut commenter
l'issue #45 avec le jeton `/ok` **en premier élément** : la carte est débloquée et
repart en file. Tout autre commentaire est une demande d'éclaircissement et ne
débloque rien.

**Ce que la décision débloque** : le re-livraison du commit GREEN perdu de la slice 5
de #19 (moitié « description » : bloc Description épinglé dans le thread Discord).
Le GREEN dev-5 initial (`6661362`) est **perdu** — mesuré : `git cat-file -t 6661362`
→ « Not a valid object name », absent de `git log --all`, absent de `origin`, absent
de tous les worktrees. La branche `wt/issue-19-discord-thread-title-description`
pointe aujourd'hui sur le **baseline conv-audit `55e6659`** (worktree partagé
`t_c22a7e74`, 2 commits au-dessus de `origin`), et le banc
`tests/test_thread_description.py` est **10/10 RED** (mesuré 2026-10-08, rejouable).

**Le périmètre du travail qui sera débloqué** (celui de la slice 5 de #19, arbitre
`Q2 = 2b` : message Description dédié épinglé, jamais le champ `topic` — mesuré :
`PATCH {"topic": …}` rend 200 puis `topic = None`) : le fil Discord d'une issue porte
un **bloc Description épinglé** dont chaque ligne est vraie au moment du verdict
(4 lignes max : marqueur `[description]` + `**Issue**`, `**Branche**`, `**PR**` ;
une ligne non résolue est **omise**, jamais remplacée par un placeholder).

**État mesuré du GREEN partiel déjà présent dans le worktree partagé**
(`t_c22a7e74` @ `55e6659`, 2026-10-08) :

| fait | preuve |
|---|---|
| La moitié titre de #19 (slices 1–4) est **livrée et présente** | `TITLE_ICONS`, `format_title`, `title_icon`, `rename_thread` dans `pipeline/engine.py` ; note composant `pj-thread-name` référencée dans le MOC |
| La moitié description (slice 5) est **partiellement présente** — GREEN *partial* | `DESCRIPTION_MARKER`, `build_description_lines` (16 occurrences mesurées 2026-10-08, hors banc) dans `pipeline/engine.py` ; `build_description_for_card`, `sync_description`, `sync_all_descriptions` dans `pipeline/pj_room_keeper.py` — mais **banc 10/10 RED** : le GREEN complet n'est pas livré |
| Le banc test-5 est **intact et gèle le contrat** | `tests/test_thread_description.py` (387 lignes, 10 cas : 3 nominal, 3 limite, 4 erreur) — rejouable : `10 failed` |
| Le helper Discord versionné n'a **pas encore** `upsert-desc` / `pin` | `skills/gh-kanban-bridge/scripts/discord_thread.py` (112 lignes) : `create`, `send`, `rename`, `threads`, `delete` seulement |
| Le worktree partagé est `t_c22a7e74` | `/home/elix/pj-repos/hermes-workflow/.worktrees/t_c22a7e74` ; branche `wt/issue-19-discord-thread-title-description` @ `55e6659`, 2 commits unpushed |
| PR #46 (concomitance) est **ouverte** | `fix/decision-jeton-apres-amorce` (commit `8e35b6e` sur l'anchor, base `dev`) — corrige le faux négatif du jeton `/ok` après amorce, causalité directe des 10 crashs de conv-5 |

**Ce que la décision ne débloque PAS** : le re-poussage du GREEN (c'est l'effet
attendant, hors périmètre de cette issue), ni la publication live des copies
`~/.hermes/scripts/` (divergence D2 déclarée, opération de fin de graphe contrôlée
par identité), ni le trou de réconciliation « débloquée hors `/ok` » (l'enfant #45
resterait ouverte à vie si la carte est débloquée hors jeton — documenté, pas tranché
ici).

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières externes)

- **GitHub** — canal de décision : commentaire `/ok` en tête sur l'issue #45
  (l'enfant). Adapter : `gh` CLI, lu par le pont. La carte `t_7aaf3d49` est l'objet
  de la reprise.
- **Kanban Hermes** — source de vérité du plan. L'effet est `comment` + `unblock`
  sur `t_7aaf3d49`, invoqués en `subprocess` par le câblage de #5
  ([[pj-decision]] : `decision_from_comment` calcule, l'appelant applique).
- **Discord** — le but du travail débloqué : thread du ticket #19. Adapter :
  `skills/gh-kanban-bridge/scripts/discord_thread.py` (aujourd'hui : `create`,
  `send`, `rename`, `threads`, `delete` — la capacité `upsert-desc` + `pin` est
  **annoncée mais absente** du code : elle est dans le GREEN perdu).
- **Aucun nouveau port** : les trois surfaces existent ; l'issue #45 réutilise la
  boucle de décision #5 et n'ajoute rien de neuf.

### Fonctionnel (capacité traversée)

La capacité traversée est la **décision humaine sur blocage** (issue #5, livrée), au
service de la capacité **notification Discord du chantier #19** — moitié «
description » (slice 5 de #19). Les deux moitiés de #19 :

- **Moitié titre (slices 1–4, livrées et présentes dans le code)** : formateur pur
  `format_title` + table `TITLE_ICONS` (4 états 🎬/⚙️/⚠/🛑) dans `pipeline/engine.py`,
  3 lecteurs du nom de thread (les deux formats arbitre + l'ancien, non-régression
  des 18 fils vivants), le keeper comme **écrivain unique** du titre avec
  coalescence par fenêtre `TITLE_WINDOW = 600 s` (Discord : la 3ᵉ `PATCH name` rend
  429).
- **Moitié description (slice 5, le GREEN est perdu)** : ce que cette issue débloque.

### Code (composants impactés par le travail débloqué)

Le périmètre de la slice 5 (mesuré dans le banc `tests/test_thread_description.py`
et le handoff `dev-5`) :

- **`pipeline/engine.py`** — `DESCRIPTION_MARKER` + `build_description_lines`
  (composition **pure** du bloc : 4 lignes max, omission des sources absentes, log
  bruyant). Le formateur pur du titre (slices 1–3) y vit déjà : `TITLE_ICONS`,
  `format_title`, `rename_thread` (best-effort), `NAME_MAX = 100`.
- **`pipeline/pj_room_keeper.py`** — porteur de l'écriture, présent mais banc
  10/10 RED (le GREEN complet n'est pas livré) : `build_description_for_card` +
  `sync_description` (déduplication par marqueur `[description]`, **édition** jamais
  second post, accueil du fil intact) + `sync_all_descriptions` (**ne lève jamais** :
  un lecteur de source qui lève est capturé et tracé, le cycle du keeper ne meurt
  pas). Le keeper est déjà l'écrivain unique du titre (slice 4) : la description s'y
  implante **à côté** du cycle de renommage, en fin de cycle, sans conditionner les
  transitions. **Écart mesuré (consigné, pas tranché ici)** : dans
  `sync_description` (ligne 725), l'appel `build_description_for_card(card, log=log)`
  ne transmet **ni** `specs_reader` **ni** `pr_reader` **ni** `issue_url_lookup` —
  alors que `sync_all_descriptions` (ligne 824) les transmet tous les trois. Un banc
  qui n'exerce que `sync_all_descriptions` ne verrait pas ce défaut.
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** — le helper gagne
  `upsert-desc` + `pin` (capacité d'édition + d'épingle d'un message). Divergence
  D2 déclarée dans le handoff `dev-5` : la copie live `~/.hermes/scripts/discord_thread.py`
  ne les porte pas ; la publication live est une opération de fin de graphe contrôlée
  par identité (hors périmètre de cette décision).
- **`tests/test_thread_description.py`** — le banc RED intact (387 lignes, 10 cas),
  qui gèle le contrat `contrat-5`. C'est lui qui sera GREEN quand le travail sera
  re-poussé.

Le **core pur** à préserver : `build_description_lines` et
`build_description_for_card` (chaînes/dicts, sources **injectées** — 0 réseau,
conformément au banc qui « empoisonne » le réseau) ; l'écriture du message et de
l'épingle passent par l'adapter injecté `write_message` / le helper Discord.

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#19** (arbitrages `Q1=1a`, `Q2=2b`, `Q3=d` — le
contrat de la slice 5 y est fixé : message dédié épinglé, lignes issue/branche/PR,
omission jamais placeholder) ; l'issue #45 **est** le point à statuer de sa carte
`conv-5` (AC Gherkin de `t_7aaf3d49` : un seul message Description épinglé, lignes
correspondant aux valeurs réelles ; doublon détecté → refusé + `request-changes`).
La doc décrit le livré : ici le « livré » attendu est le re-poussage du GREEN dev-5 ;
jusqu'au `/ok`, l'état mesuré est le RED test-5 et **aucune** doc ne peut décrire la
moitié description comme livrée. Le manifeste `specs/19/slices.json` (le plan de
slices) est **absent du dépôt** (mesuré) — il est la source de la ligne `**Branche**`
du bloc Description ; son absence est gérée par le contrat (ligne omise + log bruyant),
et sa localisation réelle relève du chantier, pas de cette décision.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *décision humaine sur blocage* (contexte #5, livrée)
  au service du contexte *notification Discord du chantier #19*.
- **Agrégat racine** : la **carte `t_7aaf3d49`** (invariant : elle ne repart en
  `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_7aaf3d49`). L'**issue #45** est l'objet de décision
  qui la matérialise.
- **Value objects** : le **bloc Description** (marqueur `[description]` + lignes
  `**Issue**`/`**Branche**`/`**PR**`, 4 lignes max, omission plutôt que placeholder —
  valeur d'identité du bloc, dédupliée par son marqueur) ; le `thread_id` résolu par
  l'ancre `Importé depuis …/issues/N` de la carte racine ; la clé `branch` du plan de
  slices. Le titre arbitré reste un value object distinct (note composant du slice 2,
  livrée sur la branche de #19, référencée par le MOC en la note composant
  `pj-thread-name`).
- **Domain events** : `commentaire GitHub /ok` sur #45 → `comment` + `unblock` sur
  `t_7aaf3d49` (re-spawn `pj-test`) → **re-poussage du GREEN** (nouveau commit sur
  `wt/issue-19-discord-thread-title-description`, banc 10/10 vert) → convergence.
  Le trou structurel signalé par la mémoire projet (t2) : si la carte est débloquée
  **hors jeton /ok**, l'enfant #45 ne se referme pas (pas de réconciliation par
  l'humain) — documenté, pas tranché ici.

## Lecture TDD (contrats testables)

Le banc existant **est** le contrat, et il est **vert ou rouge par exécution** (RED
mesuré : `10 failed in 0.21s` le 2026-10-04, rejouable) :

- `build_description_lines(issue_url, branch, pr_url, log=print) -> list[str]` —
  composition pure, 4 lignes, omission des `None`/vides, ordre `Issue`→`Branche`→`PR`
  (cas nominal ×3, limite ×3 : PR absente / plan absent / rien ne se résout).
- `keeper.build_description_for_card(card, *, …, specs_reader, pr_reader,
  issue_url_lookup)` — assemblage des sources **injectées** (0 réseau ; le banc
  « empoisonne » le réseau par sentinelle).
- `keeper.sync_description(cards, *, fetch_messages, write_message, log=None)` —
  écrivain best-effort : dédup par marqueur, `edit` jamais second post, accueil
  intact, un verdict par carte, omission des non-résolues ; **ne lève jamais**
  (cas erreur ×4, dont un lecteur de source qui lève ne tue pas le tick).
- `keeper.sync_all_descriptions(cards, *, fetch_messages, write_message, log=None,
  specs_reader=None, pr_reader=None, issue_url_lookup=None)` — câblage best-effort,
  ne lève jamais.
- La pureté du core doit rester prouvable par exécution (pattern [[pj-decision]] :
  sentinelle `sys.meta_path`), pas par lecture de texte.

## Lecture hexagonale (le core reste pur)

Le **core pur** : la composition du bloc Description (`build_description_lines`) et
l'assemblage de sources par carte (`build_description_for_card`) — chaînes/dicts,
sources injectées, **aucun** Discord, kanban, réseau, horloge. Les adapters restent
en périphérie : le lecteur du board (`hermes kanban list --json`), le plan de slices
(`specs/<n>/slices.json`, injecté), `gh pr list --head <branche>` (injecté), et
l'écriture du message + épingle (`discord_thread.py upsert-desc` / `pin`).
Le keeper (`pj_room_keeper.py`) est le **porteur** (cycle de vie, déduplication,
best-effort), pas le décideur de contenu ; il est déjà l'écrivain unique du titre —
le pattern d'écrivain unique + coalescence par fenêtre s'étend à la description,
sans le casser (le renommage ne conditionne aucune transition, et réciproquement).

## Frontières traversées (résumé)

```
carte t_7aaf3d49 bloquée (kanban) + état incohérent du dépôt (GREEN perdu, banc 10/10 RED)
  → (pj_escalate) issue ENFANT #45 + notification Discord + lien direct   [Discord]
  → (commentaire GitHub /ok sur #45)                                       [GitHub]
  → (pj_decision) unblock → ready → re-spawn de t_7aaf3d49 (pj-test)       [kanban]
  → re-poussage du GREEN dev-5 (nouveau commit sur wt/issue-19-…) → banc 10/10 vert
  → convergence (verdict pj-test) → doc-5 → t6 PR #19
```

Deux frontières traversées, **aucune nouvelle** : **GitHub ↔ kanban** (voie de
décision, livrée par #5) et **Discord ↔ kanban** (le travail débloqué écrit le bloc
Description dans le fil via l'adapter helper). L'issue #45 elle-même ne traverse
rien : elle est le point où l'humain franchit la première frontière.

## État mesuré (2026-10-08, rejouable, worktree partagé `t_c22a7e74`)

- `origin/dev` = `009f0a7` ; `origin/wt/issue-19-discord-thread-title-description`
  = `49bb284` ; HEAD du worktree partagé = `55e6659` (« conv-audit : baseline état
  courant worktree (GREEN partial, banc 7/10) »), **2 commits au-dessus** de
  `origin` (`dccf75f` fix keeper boucle infinie de journalisation + `55e6659`),
  1 fichier non tracké (`diag2.py`).
- `git cat-file -t 6661362` → « Not a valid object name » ; `git log --all` → 0 hit
  : le GREEN dev-5 original reste absent de tout le dépôt et de tous les worktrees.
- L'API slice 5 **est présente mais incomplète** (mesuré par grep 2026-10-08,
  hors banc) : `DESCRIPTION_MARKER` + `build_description_lines` dans
  `pipeline/engine.py` ; `build_description_for_card`, `sync_description`,
  `sync_all_descriptions` dans `pipeline/pj_room_keeper.py` ; le keeper y appelle
  déjà `upsert-desc` et `pin` (lignes 896, 776) — mais ces sous-commandes sont
  **absentes du helper versionné** `skills/gh-kanban-bridge/scripts/discord_thread.py`
  (112 lignes : `create`, `send`, `rename`, `threads`, `delete` seulement).
- `tests/test_thread_description.py` (387 lignes, 10 cas) reste **RED** : le banc
  n'est pas satisfait par le code partiel (rejoué 2026-10-08 ; pytest absent de
  l'env par défaut, exécutable via `uv run --with pytest`).
- `specs/` absent du dépôt (mesuré par `find` depuis la racine du worktree).
- Les notes de slice 2–4 de #19 (la note composant `pj-thread-name` et ses sœurs)
  vivent **sur la branche du worktree partagé**, non encore dans `dev` : la
  documentation de #19 s'écrit sur cette branche, et le MOC courant la référence en
  attendant (convention déjà en place pour la note composant `pj-thread-name`).

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_escalate.py` / `pipeline/pj_notify.py` ([[pj-notify]]) — la boucle #5,
  aucun changement de code.
- **Travail débloqué (slice 5 de #19, à re-pousser)** : `pipeline/engine.py`
  (composition pure du bloc), `pipeline/pj_room_keeper.py` (écrivain, à côté du cycle
  de titre), `skills/gh-kanban-bridge/scripts/discord_thread.py` (`upsert-desc` +
  `pin`), `tests/test_thread_description.py` (banc, déjà verrouillé contractuellement).
- **Vault** : à la convergence, la moitié description gagnera sa note composant et
  le MOC `docs/architecture/README.md` sera mis à jour par la carte `doc-5` — hors
  périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** : (1) si le re-poussage du GREEN se fait par
reconstruction du commit ou par réécriture — décision du `dev-5` / dispatcher ;
(2) le trou de réconciliation « débloquée hors `/ok` » (l'enfant #45 resterait ouverte
à vie) — signalé par la mémoire projet (t2), à trancher par l'orchestrateur ;
(3) la publication live des copies `~/.hermes/scripts/` (divergence D2 déclarée,
opération de fin de graphe contrôlée par identité). Ces points sont **documentés**,
pas décidés ici.
