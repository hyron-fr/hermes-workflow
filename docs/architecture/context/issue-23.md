---
type: context
status: draft
tags: [architecture, convergence, decision, slice-5, discord, issue-19, cadrage]
issues: [23]
---

# Cadrage architectural — issue #23 « slice 5/5 — convergence »

> Miroir GitHub de la carte `t_f725879f` (board `pj-hermes-workflow`), issue
> `decision` enfant d'une carte **bloquée**. Cette note positionne le **point à
> statuer** dans l'architecture actuelle ; elle ne tranche rien — elle le décrit,
> mesuré, pour que la décision humaine `/ok` (ou une demande d'éclaircissement)
> ait le cadre exact devant elle.

## Positionnement (cadre exact)

L'issue #23 **n'est pas une évolution de code** : c'est le **miroir de décision**
d'une carte de **convergence** (slice 5 de l'issue #19, « Discord thread title and
description update ») qui est **bloquée**. La convergence est le maillon du pipeline
qui **juge la livraison d'une slice** : elle rejoue le banc, vérifie l'état du
worktree partagé, et prononce un verdict (GREEN/RED, complet/partiel,
`request-changes` éventuel). Ici, le verdict est **impossible à prononcer** —
pas par défaut de convergence du code, mais par **absence du code à juger**.

Le point à statuer, **mesuré** sur le worktree partagé de l'issue #19
(branche `wt/issue-19-discord-thread-title-description`) :

- le commit **GREEN** que `dev-5` revendique (`6661362`) est **absent de toutes les
  refs** du dépôt (mesuré : `git cat-file -t 6661362` → `fatal: Not a valid object
  name` ; `git log --all` → aucune occurrence) ;
- le head de la branche est `49bb284` (**RED** — le banc de test de la slice 5,
  0 occurrence de l'API slice 5 dans `pipeline/`, `bridge/` ou `skills/`) ;
- le banc **10/10 RED** est rejoué et échoue (état « rien n'est livré ») ;
- la carte `t_f725879f` est **bloquée** : « Impossible de juger la convergence
  sans le code ».

**Ce que l'évolution devrait implémenter** (si le GREEN était présent) : le **bloc
Description épinglé** du thread Discord de l'issue #19 — un message dédié, unique,
mis à jour (jamais dupliqué), dont les trois lignes (issue / branche / PR) se
résolvent depuis des sources injectées et se **taisent proprement** quand la valeur
n'existe pas encore. C'est la **seconde moitié** de la spec #19 (la première —
titre — est livrée par les slices 2/3/4).

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — le canal de décision : un commentaire sur l'issue **enfant** #23 dont
  le **premier élément est `/ok`** (casse indifférente) débloque la carte `t_f725879f`.
  Tout autre commentaire est une **demande d'éclaircissement** (copié sur la carte,
  aucun geste). Adaptateur : `gh` CLI, lu par le pont toutes les 5 min.
- **Discord** — **notifieur uniquement** (pas de canal de décision) : le fil de
  l'issue #19 porte déjà la notification « Décision attendue » ; l'issue #23 y
  postera le **lien direct** vers le point à statuer (
  `…/issues/23#issuecomment-<id>`). Aucun bouton, aucun composant interactif.
- **Kanban Hermes** — source de vérité. La décision aboutit à `comment` + `unblock`
  sur la carte, invoqués en `subprocess`.

Aucun **nouveau port** n'est ouvert : les trois surfaces existent déjà ; l'issue
#23 **réutilise** l'interface de décision de l'issue #5 (core pur
`pipeline/pj_decision.py`) en ajoutant un **objet de décision** (le miroir #23).

### Fonctionnel (capacité traversée)

La capacité traversée est la **décision humaine sur blocage** (issue #5), qui relie
*escalade* (blocage → message, livrée) et *reprise* (unblock → re-spawn, livrée).
L'issue #23 est un **exercice** de cette capacité, pas une évolution : elle
**matérialise** le miroir de la carte `t_f725879f` et **active** le flux de
décision `/ok` sur un cas réel (le GREEN slice 5 perdu). La capacité de
**convergence** (slices #19) est **exercée en lecture seule** : elle ne modifie
aucun code, elle **juge** l'état du worktree.

### Code (composants impactés)

- **`pipeline/pj_decision.py`** (core pur, issue #5 slice 4) — **exercé**, pas
  modifié : il calcule la décision `/ok` sur le commentaire de l'issue #23,
  produit `effect == "unblock"` (si `/ok` en tête) ou `"comment"` (sinon).
  Le core est **pur** : 0 réseau, 0 LLM, 0 bouton.
- **`~/.hermes/scripts/pj_escalate.py`** (non versionné, issue #4) — **exercé** :
  il créera l'enfant #23 (déjà fait), postera le point à statuer, consommera le
  `/ok`. **Hors de cette PR** : son câblage relève du chantier de versionnement.
- **`pipeline/pj_room_keeper.py`** (slice 5, issue #19) — **objet à juger** :
  le code GREEN **devrait** y porter `build_description_for_card`,
  `sync_description`, `sync_all_descriptions` (l'API slice 5). **Mesuré : absent**
  (grep 0 occurrence sur la branche `wt/issue-19-discord-thread-title-description`).
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** (adapter) — **exercé** :
  le GREEN **devrait** y porter les commandes `upsert-desc` et `pin`
  (l'écriture du message + l'épingle). **Mesuré : absentes** (seuls
  `create/send/threads/rename/delete`).
- **`tests/test_thread_description.py`** (banc RED, slice 5) — **présent** :
  10 cas (3 nominal, 3 limite, 4 erreur), **pur** (0 réseau, 0 sous-processus ;
  les sources sont injectées, `sh` et `subprocess.run` empoisonnés).

## Lecture SDD (spec-driven)

La **spec** est le body de l'issue #19 (la slice 5 y est décrite : « bloc
Description épinglé (issue, branche, PR) + capacité `edit/pin` du helper »).
L'issue #23 **n'ajoute aucune spec** : elle est le **miroir de décision** d'une
carte de convergence qui **juge** la livraison de la slice 5. Le livrable de
l'issue #23 est un **état de board** (la carte débloquée ou la demande
d'éclaircissement postée), à la différence de l'issue #19 dont le livrable est un
**diff de code** (keeper + helper + tests).

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *décision humaine* — chevauche *escalade*
  (production du message) et *convergence* (juge la livraison), sans en être un
  nouveau : c'est la **jonction de reprise** entre deux contextes existants.
- **Agrégat racine** : la **carte kanban bloquée** `t_f725879f` (invariant : elle
  ne repart en `ready` que sur une décision explicite portant son `id` exact).
  L'**issue enfant** #23 est l'objet de décision qui matérialise la carte : une
  enfant par carte, rouverte (jamais dupliquée) sur re-blocage.
- **Value objects** : le **jeton `/ok`** (unique, casse indifférente —
  `/unblock` rejeté) ; le `(board, task_id)` résolu depuis l'enfant
  (`pj-hermes-workflow`, `t_f725879f`) ; la clé `parents` et le marqueur
  `last_reopen_comment_id` (re-blocage). Le format de carte kanban (5 sections)
  reste inchangé.
- **Domain events** : `commentaire GitHub` (premier élément `/ok`) → `comment`
  (« décision humaine ») → transition `blocked` → `ready` (re-spawn) → fermeture
  de l'enfant. Un commentaire sans `/ok` produit une demande d'éclaircissement
  sans transition.

## Lecture TDD (contrats testables)

Les fonctions que `pj-test` verrouille (l'issue l'exige : les scénarios
**automatisés**, le module de décision **pur**, testable sans Discord ni réseau) :

- **`pipeline/pj_decision.py`** (core, issue #5 slice 4) — module pur : pour un
  commentaire, rend la décision (token `/ok` présent ou non) et l'effet
  (réponse verbatim, unblock, fermeture de l'enfant, réouverture sur re-blocage).
  `tests/test_decision_humaine.py` porte **34 cas** (RED re-dérivé sur le design
  ratifié, commit `c91353d`).
- **`tests/test_thread_description.py`** (banc RED, slice 5, issue #19) — **10
  cas** (3 nominal, 3 limite, 4 erreur) : **pur** (0 réseau, 0 sous-processus),
  verrouille le **contrat d'interface** de la slice 5 (l'API
  `build_description_lines`, `build_description_for_card`, `sync_description`,
  `sync_all_descriptions` du keeper + l'adapter `discord_thread.py`).

Le mapping **commentaire → carte** : par l'**enfant** uniquement, **sans**
résolution par nom de fil (le défaut B historique est éliminé par construction).

## Lecture hexagonale (le core reste pur)

Le **core pur** à préserver est le module de décision `pipeline/pj_decision.py` :
une fonction qui manipule des chaînes/dicts, **sans** Discord, kanban, réseau ni
horloge. Les adapters (`gh` pour lire le commentaire, `discord_thread.py` pour
notifier, `subprocess` `kanban()` pour `comment`/`unblock`) restent en périphérie
et ne portent **aucune** logique décisionnelle. Le banc `tests/test_thread_description.py`
est lui aussi pur (aucun réseau, aucun fichier écrit) : il **juge** l'état du
worktree (lecture seule), il **n'écrit** aucun code.

## Composants impactés par l'issue #23

- `pipeline/pj_decision.py` — module de décision (core, **exercé**, non modifié).
- `~/.hermes/scripts/pj_escalate.py` — création de l'enfant + point à statuer +
  consommation du `/ok` (adapter, **exercé**, non versionné ; câblage hors PR,
  issue #4).
- `pipeline/pj_room_keeper.py` — **objet à juger** (le code GREEN **devrait** y
  porter l'API slice 5 ; **mesuré : absent**).
- `skills/gh-kanban-bridge/scripts/discord_thread.py` — **exercé** (l'adapter
  **devrait** porter `upsert-desc`/`pin` ; **mesuré : absentes**).
- `tests/test_thread_description.py` — **présent** (banc RED, 10 cas, pur).

## Frontières traversées (résumé)

```
carte bloquée (kanban)
  → (pj_escalate) issue ENFANT + notification + lien direct   [Discord]
  → (commentaire GitHub commençant par /ok sur l'enfant)      [GitHub]
  → (pj_decision) réponse verbatim + unblock → ready → re-spawn [kanban]
  → fermeture de l'enfant ; re-blocage ⇒ réouverture de la MÊME enfant
```

Deux frontières traversées, aucune nouvelle : **GitHub ↔ kanban** (commentaire →
effet, voie de décision) et **Discord ↔ kanban** (notification → lecture, voie de
lecture seule). Le saut « message → décision » qui n'existait pas est comblé par un
module pur déterministe (0 LLM, 0 bouton) : seul l'humain déclenche le déblocage,
par `/ok`.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** les questions ouvertes qui relèvent d'arbitrages
d'orchestrateur/humain, à rendre dans la discussion de l'issue : le **re-poussage
du GREEN** (le commit `6661362` est perdu ; il faut un **nouveau** commit GREEN
sur la branche `wt/issue-19-discord-thread-title-description`), et la **reprise**
du cycle de convergence (la carte `t_f725879f` doit être re-déclenchée une fois le
GREEN poussé). Ces points sont **documentés**, pas décidés ici.
