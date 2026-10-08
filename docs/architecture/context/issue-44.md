---
type: context
status: draft
tags: [architecture, decision, escalation, discord, github, kanban, cadrage, jeton-ok]
issues: [44]
---

# Cadrage architectural — issue #44 « t3 grill-me »

## Positionnement (cadre exact)

L'issue #44 est une **issue miroir de carte kanban** (`label: kanban`,
`idempotency-key gh-issue-44`, carte `t_8f81e69a` sur le board
`pj-hermes-workflow`, assignée à `pj-master`, statut `todo`). Son body est le
**texte verbatim de la carte** `t_8f81e69a` — un « point à statuer » sur la
carte **`t_12b728e1`** (board `pj-hermes-workflow`), bloquée sur le ticket
#32 (« slice 5/5 — convergence », `label: decision`).

Le body de la carte dit exactement ceci (mesuré) :

> Grill-me #32 posé : 1 question non levable (l'action de débloquage du GREEN
> dev-5 `6661362` perdu — re-générer vs replanifier vs renoncer). Question
> posée dans le thread Discord « hermes-workflow #28 · Décision conv-5 GREEN
> dev-5 perdu » + commentaire de carte (comment 1048). Verdict : PROTOTYPE:
> non / AMBIGU: action de débloquage / ARTEFACT: aucun. En attente de la
> réponse de JB (token `/ok` pour l'option (a) re-générer, ou précision pour
> (b)/(c)) → unblock → je reformule le handoff final et je complete.
>
> **Pour trancher**, commentez cette issue avec le jeton `/ok` en **premier
> élément** : la carte est débloquée et repart en file. Tout autre commentaire
> est une demande d'éclaircissement et ne débloque rien.
>
> carte: pj-hermes-workflow/t_12b728e1

Le **point à statuer** (mesuré le 2026-10-08, ref `fix/decision-jeton-apres-amorce`
= `8e35b6e`, HEAD du worktree partagé `t_0192052f`) :

1. La carte `t_12b728e1` est en `blocked` (motif déclaré dans son body :
   grill-me #32 avec 1 question non levable sur l'action de débloquage du
   GREEN dev-5 `6661362` perdu).
2. La question est posée dans le thread Discord « hermes-workflow #28 ·
   Décision conv-5 GREEN dev-5 perdu ».
3. Le verdict de la carte est `PROTOTYPE: non / AMBIGU: action de débloquage
   / ARTEFACT: aucun`.
4. L'humain (JB) doit répondre avec `/ok` (option a — re-générer) ou préciser
   l'option (b) replanifier / (c) renoncer.

L'issue #44 **n'est pas un livrable de code**. C'est l'**objet de décision**
qui matérialise la carte `t_8f81e69a` (grill-me #32) dans GitHub, et elle
porte la surface de décision (`/ok` en premier élément) qui débloque la carte
`t_12b728e1` (conv-5) — pas directement, mais **par le biais du core
`pj_decision`** (issue #5, slice 4 + fix `8e35b6e`).

Le présent cadrage **ne tranche pas** : il positionne le point à statuer dans
l'architecture existante, identifie les composants impactés, et fixe les
critères de décision. Le verdict humain (`/ok` sur l'issue) débloque la carte
`conv-5` ; le re-poussage du GREEN suit.

## Contexte en aval (le défaut mesuré qui rend #44 tranchable)

Le défaut qui a rendu cette décision **perceptible** est mesuré en production
le 2026-10-06 et corrigé par le commit `8e35b6e` (fix/decision-jeton-apres-amorce,
HEAD du worktree partagé `t_0192052f`) :

- **Mesure** : l'humain a commenté `rattaché /ok` sur l'enfant de décision
  `#31` (réponse à une consigne qui disait « commenter ici la décision »).
  La règle historique « jeton en **toute première place** » a jugé la
  décision absente (`_first_token(body) == "rattaché"` → `effect == "ignore"`),
  la carte `t_f725879f` est restée bloquée, et la seule trace était un
  `ignore` de tick que l'humain ne voit pas.
- **Correction** : `_token_index` accepte la tête **ou** immédiatement après
  ≤ 1 amorce (`TOKEN_PREFIX_MAX = 1`). Au-delà, le jeton est *cité* et ne
  décide rien — c'est cette borne qui garde la grammaire unique, et
  `/unblock` reste refusé.
- **Banc** : 25 → **34** cas dans `tests/test_decision_humaine.py`
  (4 cas « porte le jeton », 4 cas « le cite », 1 cas grammaire refusée,
  paramétrés — dont le corps mesuré verbatim).

Sans cette correction, le `/ok` posé sur l'issue #44 aurait été jugé
*absent* s'il avait été préfixé d'une amorce (« rattaché /ok », « d'accord,
/ok »), et la carte `t_12b728e1` serait restée bloquée avec une trace
invisible. C'est donc le commit `8e35b6e` qui rend #44 **tranchable en
production** : le jeton `/ok` en premier élément **ou** immédiatement après
une amorce vaut désormais comme décision.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision (commentaire `/ok` sur l'issue #44,
  `idempotency-key gh-issue-44`) et surface de preuve (commits de la branche,
  PR éventuelle). Le commentaire du gate de couverture a identifié #44 comme
  recouvrant #28, #32 et #40 (travail en vol, PR ouverte / graphe déjà
  construit) : c'est la **même carte bloquée** (`t_12b728e1`), escaladée via
  la chaîne `#28` → `#32` → `#44`.
- **Discord** — notifieur uniquement : le thread « hermes-workflow #28 ·
  Décision conv-5 GREEN dev-5 perdu » porte la question de grill-me #32 ;
  l'issue #44 est la **matérialisation GitHub** de cette question.
- **Kanban Hermes** — source de vérité de l'état des cartes :
  `t_12b728e1` (conv-5) en `blocked` porte le point à statuer ;
  `t_8f81e69a` (grill-me #32, miroir de #44) est parente du graphe de
  l'issue #44. Le verdict `/ok` sur l'issue #44 produit `comment` +
  `unblock` sur `t_12b728e1` (via le core `pj_decision`).

### Fonctionnel (capacité traversée)

La capacité traversée est **décision humaine sur blocage**, pas la
fonctionnalité #19 ni #32 elle-même. Les issues en amont sont déjà cadrées :

- **#28** (« slice 5/5 — convergence ») — escalade de la conv-5 de #19,
  GREEN dev-5 perdu ;
- **#32** (« slice 5/5 — convergence ») — 4e escalade de la même chaîne,
  point à statuer sur l'action de débloquage du GREEN `6661362` perdu ;
- **#44** (présente) — **miroir de carte** qui matérialise la carte
  `t_8f81e69a` (grill-me #32) dans GitHub, avec le label `kanban` posé par
  l'humain pour déclencher l'import par le pont.

Ce que #44 porte :

- **le point de décision** : l'action de débloquage du GREEN dev-5
  `6661362` perdu est-elle re-générée (a), replanifiée (b), ou renoncée (c) ?
- **la surface de décision** : le jeton `/ok` en premier élément (ou
  immédiatement après une amorce) sur l'issue #44 ;
- **la chaîne de re-livraison** : après unblock de `t_12b728e1`, qui
  repousse le GREEN (ou son équivalent) ?

C'est une **boucle de décision + re-livraison**, pas une évolution de
fonctionnalité. Le code de la slice 5 (bloc Description épinglé,
`build_description_lines`, `sync_description`, capacité `edit/pin` du helper
Discord) est décrit par le banc `tests/test_thread_description.py` — ce
cadrage ne le redécrit pas.

### Code (composants impactés)

- **`pipeline/pj_decision.py`** (commit `8e35b6e`, fix
  `fix/decision-jeton-apres-amorce`) — le **core pur** de la décision `/ok`.
  Le fix introduit `TOKEN_PREFIX_MAX = 1` et `_token_index(parts)` : le
  jeton est reconnu en tête **ou** immédiatement après ≤ 1 amorce. Au-delà,
  il est *cité* et ne décide rien. **C'est ce composant qui rend #44
  tranchable en production** : sans lui, un `/ok` préfixé d'une amorce serait
  jugé *absent*.
- **`tests/test_decision_humaine.py`** (commit `8e35b6e`) — banc étendu de
  25 → 34 cas : 4 cas « porte le jeton » (dont le corps mesuré verbatim
  « rattaché /ok »), 4 cas « le cite », 1 cas grammaire refusée, tous
  paramétrés. C'est ce banc qui **verrouille le contrat** de la correction.
- **`docs/architecture/components/pj-decision.md`** (commit `8e35b6e`) — la
  note de composant est mise à jour : la grammaire est « tête ou
  immédiatement après UNE amorce », `/unblock` reste refusé, la borne
  `TOKEN_PREFIX_MAX` est documentée comme le garde qui garde la grammaire
  unique.
- **`pipeline/pj_escalate.py`** (modifié dans le worktree partagé
  `t_0192052f`, non commité) — le diff local étend `BLOCK_EVENT_KINDS` à
  `("blocked", "block_loop_detected", "gave_up", "crashed")` et fait lire
  `payload.error` en plus de `reason`/`summary` dans `last_block_event`.
  **Hors scope du fix `8e35b6e`** : ce diff est le travail d'une carte
  distincte (escalade des cartes qui meurent en `gave_up`/`crashed` sans
  event `blocked`), pas celui de #44.
- **`bridge/gh_kanban_bridge.py`** + **`pipeline/gh_kanban_bridge.py`** —
  le pont qui a importé #44 comme `t_8f81e69a` (idempotency-key
  `gh-issue-44`). Le label `kanban` posé par l'humain déclenche l'import
  (après la correction du Défaut A de l'issue #5, slice 2 : le parent ne
  compte plus comme recouvrement, l'enfant n'est plus importée).
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** — helper Discord
  (adapter REST) : `create` / `send` / `rename` / `threads` / `delete`.
  **Non impacté** par #44 (la décision est portée par le core `pj_decision`,
  pas par le helper).

## Lecture SDD (spec-driven)

La spec de #44 est le `point à statuer` : la carte `t_12b728e1` (conv-5) est
bloquée sur le ticket #32, et le grill-me #32 a posé 1 question non levable
sur l'action de débloquage du GREEN dev-5 `6661362` perdu. Le livrable de
#44 n'est **pas** un code, mais **l'état de convergence de la slice 5 de
#19** : soit le code est repoussé et le banc passe GREEN, soit l'escalade se
poursuit. La doc décrit ce qui existe aujourd'hui (le banc RED, le travail
non livré, le worktree de re-push, le fix `8e35b6e` qui rend le `/ok`
tranchable) — pas une intention.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context** : *décision humaine sur blocage* — chevauche
  *escalade* (production du message) et *admission/livraison* (cycle de vie
  de la carte), sans en être un nouveau : c'est la **jonction** entre les
  deux.
- **Agrégat racine** : la **carte `t_12b728e1` (conv-5)** — invariant : elle
  ne repart en `ready` que sur un `/ok` humain portant son `id` exact (le
  commentaire sur l'issue #44). L'**issue #44** est l'objet de décision qui
  matérialise la carte.
- **Value objects** : le **jeton `/ok`** (unique, casse indifférente,
  reconnu en tête ou immédiatement après ≤ 1 amorce — `TOKEN_PREFIX_MAX = 1`
  du fix `8e35b6e` ; `/unblock` rejeté) ; le `(board, task_id)` résolu depuis
  l'enfant ; la clé `parents` et le marqueur `last_reopen_comment_id`
  (re-blocage). Le format de carte kanban (5 sections) reste inchangé.
- **Domain events** : `commentaire GitHub` (jeton `/ok` en tête ou après une
  amorce) → `comment` (« décision humaine ») → transition `blocked` →
  `ready` (re-spawn) → re-poussage du GREEN (ou son équivalent) par
  `dev-5`/`dispatcher` sur `wt/issue-19-discord-thread-title-description`
  → convergence GREEN → doc → doc-review → PR (t6) → merge.

## Lecture TDD (contrats testables)

Les contrats testables de #44 sont :

- **Le core `pj_decision.py` reconnaît le jeton `/ok` en tête ou
  immédiatement après UNE amorce** — vérifié par les 34 cas du banc
  `tests/test_decision_humaine.py` (4 cas « porte le jeton », dont le corps
  mesuré verbatim « rattaché /ok » ; 4 cas « le cite » ; 1 cas grammaire
  refusée). Le fix `8e35b6e` est le GREEN de ce contrat.
- **Le banc `tests/test_thread_description.py` passe GREEN** — 10 cas,
  rejouable sans Discord ni réseau (sources injectées). C'est la preuve de
  convergence de la slice 5 de #19 (non lié directement à #44, mais
  l'objet du point à statuer).
- **Le commit `6661362` (ou son équivalent) est présent dans le branch head
  de `wt/issue-19-discord-thread-title-description`** — vérifiable par
  `git cat-file -t 6661362` dans le dépôt principal et par
  `git log --oneline` sur la branche.

Ces invariants sont mesurables par `pj_graphwatch` (couverture
commit-à-commit + chemin réel du worktree, cf. commits `009f0a7`, `9e49771`,
`318bea1` de l'issue #2) et par le pont de couverture
(`pj_coverage_gate`) qui a identifié #44 comme recouvrant #28, #32 et #40.

## Lecture hexagonale (le core reste pur)

Le **core pur** de la décision est `pipeline/pj_decision.py` : une fonction
qui manipule des chaînes/dicts, **sans** Discord, kanban, réseau ni horloge.
Le fix `8e35b6e` ( `_token_index`, `TOKEN_PREFIX_MAX = 1`) est **pur** :
aucun appel réseau, aucune horloge, aucun aléa. Les adapters (`gh` pour lire
le commentaire, `discord_thread.py` pour notifier, `subprocess kanban()`
pour `comment`/`unblock`) restent en périphérie et ne portent **aucune**
logique décisionnelle.

La frontière à respecter : **la décision est une lecture du commentaire
GitHub** résolue **dans** le core pur (le jeton est reconnu dans le corps du
commentaire, pas dans l'URL ni le nom de fil), puis **portée** par
l'appelant (adapter kanban). Jamais l'inverse : le core ne lit pas le réseau.

## Composants impactés par l'issue #44

| composant | impact | ref |
|---|---|---|
| `pipeline/pj_decision.py` | core pur de la décision `/ok` ; le fix `8e35b6e` rend le jeton tranchable (tête ou après UNE amorce) | `8e35b6e` (HEAD du worktree partagé) |
| `tests/test_decision_humaine.py` | banc étendu de 25 → 34 cas (4 « porte », 4 « cite », 1 « grammaire refusée », paramétrés) | `8e35b6e` |
| `docs/architecture/components/pj-decision.md` | note de composant mise à jour : grammaire « tête ou après UNE amorce », `/unblock` refusé, `TOKEN_PREFIX_MAX` documenté | `8e35b6e` |
| `bridge/gh_kanban_bridge.py` + `pipeline/gh_kanban_bridge.py` | pont qui a importé #44 comme `t_8f81e69a` (idempotency-key `gh-issue-44`) | non impacté par le fix |
| `pipeline/pj_escalate.py` | diff local (non commité) : extension de `BLOCK_EVENT_KINDS` à `gave_up`/`crashed` + lecture de `payload.error` — **hors scope** de #44 | worktree partagé `t_0192052f` |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | helper Discord (adapter REST) — non impacté | non modifié |

## Hors-scope

- **Le re-push du GREEN `6661362`** : porté par `dev-5`/`dispatcher` sur le
  worktree de re-push, **jamais** par ce cadrage.
- **La convergence effective de la slice 5 de #19** : portée par la carte
  `t_12b728e1` (conv-5) après le `/ok` humain.
- **Le diff local de `pipeline/pj_escalate.py`** (extension de
  `BLOCK_EVENT_KINDS` à `gave_up`/`crashed` + lecture de `payload.error`) :
  travail d'une carte distincte, **hors scope** de #44.
- **Les escalades en amont (#28, #32)** : déjà cadrées par les notes
  `issue-28` et `issue-32` ; #44 est leur matérialisation GitHub.
- **Le verdict de convergence** : porté par `pj-test` sur la carte
  `t_12b728e1`, pas par ce cadrage.
- **Le câblage du core `pj_decision` vers les copies live** (`~/.hermes/profiles/pj-master/scripts/pj_decision.py`) :
  chantier de versionnement (issue #4), hors PR de #5 (cf. note `issue-5`).

## Frontières traversées (résumé)

```
issue #44 (GitHub, label kanban + idempotency-key gh-issue-44)
  → commentaire /ok humain (surface de décision, tête ou après UNE amorce)
  → (pj_decision) décision calculée {effect: "unblock", task_id: "t_12b728e1", board: "pj-hermes-workflow"}
  → (adapter kanban) comment + unblock → ready → re-spawn de t_12b728e1
  → re-poussage du GREEN 6661362 (ou son équivalent) par dev-5/dispatcher
  → banc test_thread_description.py GREEN (preuve de livraison)
  → convergence GREEN → doc → doc-review → PR → merge
```

Deux frontières traversées, aucune nouvelle : **GitHub ↔ kanban**
(commentaire → effet, voie de décision) et **Discord ↔ kanban**
(notification → lecture, voie de lecture seule). Le saut « message →
décision » est comblé par un module pur déterministe (0 LLM, 0 bouton) :
seul l'humain déclenche le déblocage, par `/ok`. Le fix `8e35b6e` élargit
la grammaire acceptée (tête ou après UNE amorce) sans ajouter de frontière.

## État mesuré (2026-10-08)

- `origin/dev` = `2027333` (docs(cadrage): issue #29 — slice 5/5 convergence).
- `fix/decision-jeton-apres-amorce` = `8e35b6e` (HEAD du worktree partagé
  `t_0192052f`), **non mergée** dans `dev`.
- `wt/t_0192052f` = `8e35b6e` (worktree partagé de l'issue #44, propre, 0
  commit d'avance sur `fix/decision-jeton-apres-amorce`).
- `git cat-file -t 6661362` → **fatal : Not a valid object name** (commit
  absent du dépôt local et du remote).
- Banc `tests/test_decision_humaine.py` : **34 cas** (fix `8e35b6e`).
- Banc `tests/test_thread_description.py` : **10/10 RED** (non lié à #44).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.
