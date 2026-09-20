---
type: context
status: draft
tags: [architecture, decision-interface, escalation, discord, github, kanban, cadrage]
issues: [5]
---

# Cadrage architectural — issue #5 « Interface de décision humaine pour les cartes bloquées »

## Positionnement (cadre exact)

L'issue #5 **ne crée pas** un nouveau maillon du pipeline : elle **ferme une boucle
qui en est aujourd'hui ouverte**. Aujourd'hui un worker de production (dev/doc/test)
peut bloquer sa carte, et `pj_escalate` poste « 🔔 Décision attendue » dans le fil
Discord du ticket — mais **aucune surface ne permet de répondre**. L'humain doit
ouvrir un terminal et débloquer à la main, ce qu'il ne fait pas.

L'issue dote cette boucle d'une **interface de décision**, restreinte aux deux seules
surfaces humaines : **Discord** (boutons interactifs dans le fil) et **GitHub**
(commentaire `/unblock` ou label dédié). La recommandation retenue dans l'issue est
**A + C** : A (boutons attachés à chaque message de blocage, `custom_id` déterministe)
pour l'immédiateté, C (décision sur GitHub) comme voie de repli historisée.

C'est une **évolution de frontière d'interface**, pas un changement de topologie : le
graphe (t1..t5, t3b, slices dev) et les règles de déblocage (comment + `unblock` →
re-spawn) restent identiques. Ce qui change est **comment l'humain déclenche le
déblocage** — du terminal vers un clic ou un commentaire.

## Ce qui existe déjà (mesuré le 2026-09-20, ref `dev`)

| brique | ref | état mesuré |
|---|---|---|
| escalade | `~/.hermes/scripts/pj_escalate.py` | **non versionné** dans le dépôt (`git ls-files` vide). Poste « Décision attendue », ne peut pas recevoir de réponse. Son versionnement est l'objet de **l'issue #4** (OPEN), distincte. |
| boutons | `plugins/pj-buttons/pj-buttons/__init__.py` | versionné. Table d'actions `go`/`nogo` ; `parse_custom_id` est une **fonction pure** (schéma `pj:<action>:<board>/<task_id>` porte déjà l'identité exacte de la carte). |
| helper Discord | `skills/gh-kanban-bridge/scripts/discord_thread.py` | versionné **et** copié en `~/.hermes/scripts/discord_thread.py` — les deux **diffèrent** (`diff` → non identiques). |
| pont | `bridge/gh_kanban_bridge.py` | `pull()` fait `continue` si l'issue porte `MIRROR_LABEL` (`kanban`) ou `TRIAGE_LABEL` (`triage`) ; `cmd_new()` exclut par le même prédicat. |
| notifier gateway | `kanban_notify_subs` | **vide** (0 ligne sur 5 boards) : le notifier `blocked`/`needs_input` ne délivre rien. |

## Défauts de fond mesurés pendant la reconnaissance

### Défaut A — la trappe du gate de couverture (dans le pont)

Le commentaire de couverture propose « poser le label `kanban` ; le pont l'importera
au tick suivant ». **C'est faux** : `pull()` fait `continue` dès que l'issue porte
`kanban` (`if MIRROR_LABEL in labels or TRIAGE_LABEL in labels: continue`), et
`cmd_new()` l'exclut par le même prédicat. `kanban` est le label posé **après**
import, jamais un déclencheur. L'humain qui suit la consigne exclut l'issue pour
toujours. Ce défaut touche le **pont**, pas l'escalade — l'issue #5 le signale et
laisse la question 4 ouverte (traiter ici ou en issue dédiée).

### Défaut B — les boutons existants ne sont pas une voie de décision

`resolve_from_thread()` (schéma `triage:`, résolution par nom de fil) cherche une
carte `blocked` dont le titre contient `validate`/`grill`, sinon bascule sur « la
carte dont le body cite `/issues/<N>` » — la **racine** (souvent `done`). Un clic
`go` ferait `unblock` sur une carte terminée. C'est précisément ce que le `custom_id`
déterministe de l'option A élimine : il désigne la carte **directement**.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières externes)

- **Discord** — composants interactifs (`ActionRow`, `custom_id`), threads d'issue du
  canal `#pj-master`. Adapter : plugin `pj-buttons` (handler `on_interaction`,
  `component`), helper `discord_thread.py` (poster).
- **GitHub** — commentaires d'issue + labels comme canal de décision (option C).
  Adapter : `gh` CLI, déjà lu par le pont toutes les 5 min.
- **Kanban Hermes** — source de vérité. Le clic/commentaire aboutit à `comment` +
  `unblock` sur la carte, invoqués en `subprocess` (`kanban()` dans le plugin).
- **Aucun** nouveau port : les trois surfaces existent déjà ; l'issue les **réutilise**
  en ajoutant une voie d'écriture (le retour de décision) là où il n'y avait qu'une
  voie de lecture (l'escalade).

### Fonctionnel (capacité traversée)

La capacité traversée est la **décision humaine sur blocage**, qui relie aujourd'hui
deux capacités existantes de façon asymétrique : *escalade* (blocage → message, livrée)
et *reprise* (unblock → re-spawn, livrée). L'issue #5 ajoute le **maillon manquant**
entre elles : *saisie de décision*. Elle ne modifie ni l'escalade (hors-scope) ni la
reprise.

### Code (composants impactés)

- **`pj_escalate.py`** (non versionné — cf. issue #4) — attache à son message une
  `ActionRow` par carte bloquée, `custom_id` déterministe `pj:unblock:<board>/<task_id>`
  et `pj:drop:<board>/<task_id>`. Limite : 5 boutons/message Discord.
- **`plugins/pj-buttons/pj-buttons/__init__.py`** — étend la table d'actions
  (`go`/`nogo` → `+unblock`, `+drop`) et son parseur `parse_custom_id`. Le schéma
  `pj:` porte déjà `board`/`task_id` : l'extension est incrémentale, pas une refonte.
- **Pont / cron GitHub** (option C) — lit commentaires et labels, applique
  `/unblock <task_id>` ou `decision:unblock`. Coût faible (lecture déjà en place).

## Lecture SDD (spec-driven)

La spec est le body de l'issue #5, dont les quatre scénarios Gherkin sont **les**
critères d'acceptation (nominal, limite multi-cartes, erreur déjà-débloquée, erreur
ticket CLOS). La doc décrit le livré : les composants cités ci-dessus existent déjà en
dépôt (sauf `pj_escalate.py`, explicitement non versionné). Le livrable de l'issue
sera un **diff de code** (plugin + forme des boutons, + voie GitHub), à la différence
de l'issue #1 dont le livrable était un état de board.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *décision humaine* — chevauche *escalade* (production
  du message) et *admission/livraison* (cycle de vie de la carte), sans en être un
  nouveau : c'est la **jonction de reprise** entre deux contextes existants.
- **Agrégat racine** : la **carte kanban bloquée** (invariant : elle ne repart en
  `ready` que sur une décision explicite portant son `id` exact). Le `custom_id`
  `pj:<action>:<board>/<task_id>` est l'identifiant d'agrégat encodé dans l'UI.
- **Value objects** : le `custom_id` (schéma `pj:<action>:<board>/<task_id>`, porteur
  de l'identité exacte) ; le `(board, task_id)` résolu ; le `reason` du blocage
  (tronqué à 700 c). Le format de carte kanban (5 sections) reste inchangé.
- **Domain events** : `component interaction` (clic) → `comment` (« décision humaine »)
  → transition `blocked` → `ready` (re-spawn). La voie GitHub produit les mêmes
  événements, déclenchés par commentaire/label au lieu d'un clic.

## Lecture TDD (contrats testables)

Les fonctions que `pj-test` verrouillera (l'issue l'exige : les 4 scénarios
**automatisés**, parseur et table d'actions **purs**, testables sans Discord) :

- `parse_custom_id(custom_id)` — déjà pur, étendu à `unblock`/`drop` ; chaque schéma
  (`pj:`, `triage:`) et chaque action → tuple `(action, board, task_id)`.
- la **table d'actions** (`go`/`nogo`/`unblock`/`drop` → note + effet kanban) —
  fonction pure décrivant le mapping décision→(commentaire, transition).
- le mapping `custom_id` → carte : **sans** résolution par nom de fil pour le schéma
  `pj:` (le défaut B est éliminé par construction).

**Aucun test ne verrouille ces fonctions aujourd'hui** (mesuré : `grep` de
`parse_custom_id`/`custom_id`/`escalate` dans `tests/` → 0 hit). C'est l'apport TDD de
l'issue : rendre testable ce qui est aujourd'hui du code de plugin non éprouvé.

## Lecture hexagonale (le core reste pur)

Le **core pur** à préserver est le couple `parse_custom_id` + table d'actions : des
fonctions qui manipulent des chaînes/dicts, **sans** Discord, kanban, réseau ni
horloge. Les adapters (handler Discord `on_interaction`, `subprocess` `kanban()` et
`gh`) restent en périphérie et ne doivent porter **aucune** logique décisionnelle.
L'extension de l'option A respecte cette frontière : la nouvelle logique (quelles
actions existent, quel effet chacune a) vit dans le core testable, l'ACK éphemère et
l'appel `unblock` restent dans l'adapter.

## Composants impactés par l'issue #5

- `plugins/pj-buttons/pj-buttons/__init__.py` — table d'actions + parseur (core).
- `~/.hermes/scripts/pj_escalate.py` — forme des boutons (adapter, **non versionné** ;
  son versionnement relève de l'issue #4).
- `bridge/gh_kanban_bridge.py` (ou un cron dédié) — voie GitHub, option C (adapter).
- **Défaut A** — signalé, décision de périmètre ouverte (question 4 de l'issue) : il
  touche le pont, pas l'escalade ; si tranché ici, `bridge/gh_kanban_bridge.py`
  (`_flag_covered_issue`, `pull`, `cmd_new`) est impacté.

## Frontières traversées (résumé)

```
carte bloquée (kanban)
  → (pj_escalate) message + bouton [Discord]
  → (clic) custom_id pj:unblock:<board>/<task_id>
  → (pj-buttons) comment + unblock → ready → re-spawn          [kanban]

  ou, voie de repli :
  → (commentaire /unblock <task_id> | label decision:unblock) [GitHub]
  → (cron) comment + unblock → ready → re-spawn               [kanban]
```

Deux frontières traversées, aucune nouvelle : **Discord ↔ kanban** (clic → effet) et
**GitHub ↔ kanban** (commentaire/label → effet). Le saut « message → décision » qui
n'existait pas est comblé par des adapters déterministes (0 LLM), sans décision
automatique : seul l'humain déclenche le déblocage.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** les quatre questions ouvertes de l'issue (A+C vs A vs C ;
`drop` = archive vs relance ; >5 cartes bloquées ; Défaut A ici ou en issue dédiée) :
ce sont des arbitrages d'orchestrateur/humain, à rendre dans la discussion de l'issue,
pas des choix de rédaction.
