---
type: context
status: draft
tags: [architecture, decision-interface, escalation, convergence, discord, github, kanban, cadrage]
issues: [32]
---

# Cadrage architectural — issue #32 « slice 5/5 — convergence »

## Positionnement (cadre exact)

L'issue #32 **n'est pas une tâche de développement** : c'est un **objet de décision**
(labels `decision` + `kanban`) créé par l'escalade `pj_escalate` lorsqu'une carte de
production a cessé d'être débloquable par l'humain. Elle est le **4ᵉ échelon** d'une
chaîne d'escalade linéaire sur un même incident :

```
t_f725879f (conv-5, issue #19) — BLOQUÉ transient
  « GREEN dev-5 (commit 6661362) absent : branch head = 49bb284 (RED test-5),
    banc 10/10 RED rejoué. Impossible de juger la convergence sans le code. »
    → escalade #27 (décision sur t_b7953265)
    → escalade #28 (décision sur t_44969bfe)
    → escalade #32 (décision sur t_44969bfe, ticket #28)
```

La carte visée par le `/ok` est **`t_44969bfe`** (convergence slice 5/5, board
`pj-hermes-workflow`), qui est elle-même le **convergence gate** du pipeline de
l'issue #28 (elle-même escalade de l'issue #19). Le `/ok` sur #32 **ne débloque
pas `t_44969bfe` directement** — il débloque la chaîne d'escalade, ce qui permet
à `t_44969bfe` de repartir en file, ce qui à son tour permet à son pipeline
(`t_566c200d` = t3 grill-me, `t_f6ca9ad2` = t4 draft spec, `t_805ebd61` = t5
convergence) de converger.

**Le problème sous-jacent** (issue #19, slice 5) : le commit GREEN `6661362` est
**définitivement perdu** (absent de tous les refs locaux, reflogs, objets
unreachable et GitHub). La branche `wt/issue-19-discord-thread-title-description`
pointe sur `49bb284` (RED test-5). Le banc 10/10 est RED rejoué. La convergence
ne peut pas juger sans le code.

**Ce que fait le `/ok`** : il débloque la carte `t_44969bfe` (convergence), qui
repart en file. La convergence (t5) attend alors que le GREEN soit re-implanté
par dev-5 dans le worktree partagé `t_c22a7e74` (branche
`wt/issue-19-discord-thread-title-description`). **Le `/ok` ne re-pousse pas le
commit perdu** : c'est l'arbitrage humain de décider si le GREEN doit être
re-généré depuis le banc RED ou re-pushé depuis une autre source.

## Le livré — 0 slice de développement

L'issue #32 est une **carte de décision**, pas de dev. Le pipeline standard
(t1 worktree, t2 mémoire, t3 grill-me, t3b doc-cadrage, t4 draft spec, t5
convergence) est importé par le pont GitHub pour structurer l'inspection et le
handoff, mais **aucune slice de production ne code de nouveau**. Le worktree t1
(`wt/t_940bbc31`, base `origin/dev @ 009f0a7`, 0 commit d'avance) sert à
l'inspection et au handoff, pas au développement.

Le seul livrable concret de cette issue est le **cadrage architectural** (cette
note) qui documente :
- la chaîne d'escalade complète (mesurée, rejouable) ;
- le composant impacté (`pj_escalate` + `pj_decision` + `pj_decision_watch`) ;
- le trou structurel connu (rèconciliation des enfants de décision) ;
- le fait que le pipeline standard est importé pour une décision, pas pour un dev.

## Ce qui existe déjà (mesuré le 2026-10-04, ref `origin/dev @ 009f0a7`)

| brique | ref | état mesuré |
|---|---|---|
| escalade | `pipeline/pj_escalate.py` | versionné dans le dépôt. Poste « Décision attendue » dans le thread Discord de l'issue. Crée l'enfant de décision. Ne reçoit pas de réponse (le câblage `/ok` est dans le worktree `t_okwiring`, branche `wt/issue-5-cablage-ok`, non mergé). |
| core décision | `pipeline/pj_decision.py` | versionné dans le dépôt. Module pur : `decision_from_comment(ctx, comment) → {effect, task_id, board, note, acted}`. `effect ∈ {"ignore", "unblock", "comment"}`. |
| câblage /ok | `pipeline/pj_decision_watch.py` | **non versionné** dans `origin/dev` — présent uniquement dans le worktree `t_okwiring` (branche `wt/issue-5-cablage-ok`, 4 commits d'avance sur `origin/dev`). Ce câblage consomme `pj_decision.decision_from_comment` et porte les deux notifications (enfant + parent). |
| notifier | `pipeline/pj_notify.py` | versionné dans le dépôt. `notify_decision(decision, ctx, effects)` porte les deux notifications de la décision `/ok`. |
| bridge | `bridge/gh_kanban_bridge.py` + `pipeline/gh_kanban_bridge.py` | versionné. `pull()` exclut les issues portant `kanban`, `triage` ou `decision`. `push()` ferme l'issue de la ligne `Importé depuis <url>`. |

## Défauts de fond mesurés pendant la reconnaissance

### Défaut A — le câblage `/ok` n'est pas mergé dans `origin/dev`

`pipeline/pj_decision_watch.py` (le keeper qui consomme `pj_decision.decision_from_comment`
et porte les notifications) n'existe **pas** dans `origin/dev @ 009f0a7`. Il vit
uniquement dans le worktree `t_okwiring` (branche `wt/issue-5-cablage-ok`, 4
commits d'avance). La décision `/ok` sur #32 **ne peut pas être consommée
automatiquement** par le pipeline en production tant que ce câblage n'est pas
mergé. Le `/ok` doit donc être consommé **manuellement** par l'humain ou par
l'orchestrateur (`pj-master`), qui invoque `hermes kanban unblock` sur la carte
cible.

### Défaut B — le pipeline standard est importé pour une décision, pas pour un dev

Le pont GitHub importe le graphe pipeline standard (t1 worktree, t2 mémoire,
t3 grill-me, t3b doc-cadrage, t4 draft spec, t5 convergence) pour **toute**
issue ouverte sans label `kanban`/`triage`/`decision`. Or l'issue #32 est une
**décision**, pas un dev. Le pipeline ne produit pas de code, il produit un
**cadrage** (cette note) et un **draft de spec** (t4) qui documentent la
décision. C'est un **trou structurel connu** (documenté par t2) : le pipeline
n'a pas de graphe dédié aux issues de décision.

### Défaut C — `pj_decision_watch.py` ne réconcilie pas les enfants de décision dont la carte a cessé d'être bloquée

Mesuré sur #20 et #21 (fermés à la main). La phase production de
`pj_decision_watch.py` ne parcourt que `blocked_cards()` (L742). Une enfant de
décision dont la carte a déjà été débloquée (par un moyen autre que le `/ok`
consommé par le keeper) n'est pas fermée automatiquement. Elle reste OPEN sur
GitHub. C'est le cas de l'issue #28 (parent de #32) : si `t_44969bfe` est
débloquée par un autre moyen que le `/ok` sur #32, l'issue #28 reste OPEN.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières externes)

- **GitHub** — le canal de décision : un commentaire sur l'issue **enfant**
  (`hyron-fr/hermes-workflow#32`) dont le premier élément est `/ok`. Adapter :
  `gh` CLI, lu par le pont toutes les 5 min.
- **Discord** — notifieur uniquement : message + lien direct vers le point à
  statuer. Adapter : helper `discord_thread.py`. Aucun composant interactif.
- **Kanban Hermes** — source de vérité. La décision aboutit à `comment` +
  `unblock` sur la carte `t_44969bfe`, invoqués en `subprocess`.
- **Aucun** nouveau port : les trois surfaces existent déjà ; l'issue les
  **réutilise** en ajoutant une voie de lecture (le retour de décision) là où il
  n'y avait qu'une voie d'écriture (l'escalade).

### Fonctionnel (capacité traversée)

La capacité traversée est la **décision humaine sur blocage**, qui relie
aujourd'hui deux capacités existantes de façon asymétrique : *escalade*
(blocage → message, livrée) et *reprise* (unblock → re-spawn, livrée). L'issue
#32 **n'ajoute pas** de nouveau maillon : elle est le **4ᵉ échelon** de la
chaîne d'escalade existante. Elle ne modifie ni l'escalade (hors-scope, issue #4)
ni la reprise.

### Code (composants impactés)

- **`pipeline/pj_escalate.py`** — crée l'enfant de décision, poste le point à
  statuer dans Discord. **Impacté indirectement** : c'est lui qui a créé #32.
- **`pipeline/pj_decision.py`** — module pur de décision. **Non impacté** : le
  `/ok` sur #32 passe par `decision_from_comment`, mais le câblage qui l'appelle
  (`pj_decision_watch.py`) n'est pas mergé.
- **`pipeline/pj_decision_watch.py`** — **non versionné** (worktree `t_okwiring`
  uniquement). C'est lui qui consommerait le `/ok`. **Impacté** : sans lui, le
  `/ok` n'est pas consommé automatiquement.
- **`pipeline/pj_notify.py`** — émetteur des deux notifications. **Non impacté**
  : il est versionné et fonctionnel, mais n'est pas appelé tant que
  `pj_decision_watch.py` n'est pas mergé.
- **`bridge/gh_kanban_bridge.py`** + **`pipeline/gh_kanban_bridge.py`** — pont.
  **Non impacté** : il importe déjà les issues avec label `decision` dans le
  board kanban (c'est ainsi que la carte `t_44969bfe` a été créée).

## Lecture SDD (spec-driven)

La spec est le body de l'issue #32, dont le scénario est :
- **Nominal** : le `/ok` est commenté sur #32 → `t_44969bfe` est débloquée → le
  pipeline de convergence (#28) repart en file.
- **Limite** : le GREEN `6661362` est perdu → la convergence ne peut pas juger
  → le `/ok` débloque la carte mais ne produit pas de code.
- **Erreur** : le `/ok` est commenté alors que `t_44969bfe` n'est plus
  `blocked` → `pj_decision` produit `effect = "comment"` (« carte(s) déjà
  active(s) : décision écrite, rien à débloquer »), jamais d'échec silencieux.

La doc décrit le livré : le cadrage architectural (cette note) et le draft de
spec (t4). **Le livrable de l'issue est un diff de doc** (cette note + le draft
de spec), à la différence de l'issue #19 dont le livrable était un diff de code.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *décision humaine* — chevauche *escalade*
  (production du message) et *admission/livraison* (cycle de vie de la carte),
  sans en être un nouveau : c'est la **jonction de reprise** entre deux
  contextes existants.
- **Agrégat racine** : la **carte kanban bloquée** `t_44969bfe` (invariant :
  elle ne repart en `ready` que sur une décision explicite portant son `id`
  exact). L'**issue enfant** #32 est l'objet de décision qui matérialise la
  carte : une enfant par carte, rouverte (jamais dupliquée) sur re-blocage.
- **Value objects** : le **jeton `/ok`** (unique, casse indifférente —
  `/unblock` rejeté) ; le `(board, task_id)` résolu depuis l'enfant ; la clé
  `parents` et le marqueur `last_reopen_comment_id` (re-blocage).
- **Domain events** : `commentaire GitHub` (premier élément `/ok`) → `comment`
  (« décision humaine ») → transition `blocked` → `ready` (re-spawn) →
  fermeture de l'enfant. Un commentaire sans `/ok` produit une demande
  d'éclaircissement sans transition.

## Lecture TDD (contrats testables)

Les fonctions que `pj-test` verrouille (l'issue l'exige : les scénarios
**automatisés**, le module de décision **pur**, testable sans Discord ni réseau) :

- **`pipeline/pj_decision.py`** — module pur : pour un commentaire, rend la
  décision (token `/ok` présent ou non) et l'effet (réponse verbatim, unblock,
  fermeture de l'enfant, réouverture sur re-blocage). `tests/test_decision_humaine.py`
  porte **20 cas** (RED re-dérivé sur le design ratifié, commit `c91353d`).
- **`pipeline/pj_decision_watch.py`** (worktree `t_okwiring`) — le keeper qui
  consomme `pj_decision.decision_from_comment` et porte les notifications.
  **Non versionné** : les tests sont dans le worktree, pas dans `origin/dev`.
- Le mapping **commentaire → carte** : par l'**enfant** uniquement, **sans**
  résolution par nom de fil (le défaut B historique est éliminé par
  construction).

## Lecture hexagonale (le core reste pur)

Le **core pur** à préserver est le module de décision `pipeline/pj_decision.py` :
une fonction qui manipule des chaînes/dicts, **sans** Discord, kanban, réseau ni
horloge. Les adapters (`gh` pour lire le commentaire, `discord_thread.py` pour
notifier, `subprocess` `kanban()` pour `comment`/`unblock`) restent en
périphérie et ne portent **aucune** logique décisionnelle. Le keeper
`pj_decision_watch.py` (worktree `t_okwiring`) est l'**adapter** qui relie le
core pur au monde réel : il lit les commentaires GitHub, appelle
`decision_from_comment`, puis invoque `notify_decision` et `kanban unblock`.

## Composants impactés par l'issue #32

- `pipeline/pj_escalate.py` — création de l'enfant + point à statuer +
  consommation du `/ok` (adapter, versionné dans `origin/dev`).
- `pipeline/pj_decision.py` — module de décision (core pur, versionné dans
  `origin/dev`).
- `pipeline/pj_decision_watch.py` — keeper qui consomme le `/ok` (adapter,
  **non versionné** — worktree `t_okwiring` uniquement).
- `pipeline/pj_notify.py` — émetteur des deux notifications (adapter, versionné
  dans `origin/dev`).
- `bridge/gh_kanban_bridge.py` + `pipeline/gh_kanban_bridge.py` — pont
  (adapters, versionnés dans `origin/dev`).

## Frontières traversées (résumé)

```
carte bloquée (kanban) — t_f725879f (conv-5, #19)
  → (pj_escalate) issue ENFANT #27 + notification + lien direct   [Discord]
  → (commentaire GitHub /ok sur #27)                              [GitHub]
  → (pj_decision) réponse verbatim + unblock → ready → re-spawn   [kanban]
  → (pj_escalate) issue ENFANT #28 + notification + lien direct   [Discord]
  → (commentaire GitHub /ok sur #28)                              [GitHub]
  → (pj_decision) réponse verbatim + unblock → ready → re-spawn   [kanban]
  → (pj_escalate) issue ENFANT #32 + notification + lien direct   [Discord]
  → (commentaire GitHub /ok sur #32)                              [GitHub]
  → (pj_decision) réponse verbatim + unblock → ready → re-spawn   [kanban]
  → fermeture de l'enfant ; re-blocage ⇒ réouverture de la MÊME enfant
```

Trois frontières traversées, aucune nouvelle : **GitHub ↔ kanban** (commentaire →
effet, voie de décision) et **Discord ↔ kanban** (notification → lecture, voie de
lecture seule). Le saut « message → décision » qui n'existait pas est comblé par
un module pur déterministe (0 LLM, 0 bouton) : seul l'humain déclenche le
déblocage, par `/ok`.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** les questions ouvertes qui relèvent d'arbitrages
d'orchestrateur/humain, à rendre dans la discussion de l'issue :

1. **Cause de la perte du commit `6661362`** (force-push ? clôture avant push ?)
   — non levable seule ;
2. **Action de déblocage** (re-push vs re-générer le GREEN depuis le banc RED)
   — arbitrage humain ;
3. **Trous structurels** (rèconciliation des enfants de décision, pipeline
   standard importé pour une décision) — documentés, pas décidés ici.

## Verdict `PROTOTYPE: non`

Le verdict de t3 est `PROTOTYPE: non` : aucune ambiguïté non levable sur un
livrable perceptible. L'issue #32 est une **carte de décision**, pas un
livrable visuel. Le `/ok` débloque la carte, il ne produit pas de code. Le
cadrage (cette note) et le draft de spec (t4) documentent la décision.
