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
ouvrir un terminal et débloquer à la main, ce qu'il ne fait pas (mesuré : 5 cartes
bloquées, 0 déblocable).

L'issue dote cette boucle d'une **interface de décision** au design ratifié par
l'humain en **4 tours d'arbitrage** :

- **une issue enfant par carte bloquée**, créée automatiquement au 1er blocage (0 LLM) ;
- **décision = un commentaire GitHub dont le premier élément est `/ok`** (casse
  indifférente). Tout autre commentaire est une **demande d'éclaircissement** (copié
  sur la carte, aucun geste, la carte reste bloquée). `/unblock` est **rejeté** : deux
  grammaires = divergence garantie ;
- **la cible est l'enfant** : la décision est portée par l'objet qui représente la
  carte, donc **aucune résolution par nom de fil** ni par `#N` du ticket parent ;
- **Discord ne décide plus, il notifie** : lien direct vers le point à statuer
  (`…/issues/<n>#issuecomment-<id>`). **Aucun bouton**, aucun composant interactif ;
- **`abandon` est retiré** : « abandonner » n'est pas un geste valide sur une carte qui
  attend une réponse — si la réponse est « on arrête », c'est le **ticket** qu'on ferme ;
- fermeture de l'enfant sur décision ; re-blocage ⇒ la **même** enfant est rouverte.

C'est une **évolution de frontière d'interface**, pas un changement de topologie : le
graphe (t1..t5, t3b, slices dev) et les règles de déblocage (comment + unblock →
re-spawn) restent identiques. Ce qui change est **comment l'humain déclenche le
déblocage** — du terminal vers un **commentaire GitHub `/ok`**, Discord ne faisant
que notifier.

## Le livré — 4 slices, une branche, une PR

Le périmètre est découpé en 4 slices séquentielles sur la branche
`wt/issue-5-interface-decision-humaine` (worktree partagé `.worktrees/t_6bf54cea`) :

| k | slice | ce qui devient vrai | fichiers |
|---|---|---|---|
| 1 | `preview-artefacts-decision` | l'humain **juge le rendu** (diagramme V2 + maquette de texte) avant tout développement | `docs/architecture/context/issue-5-decision-flow.html` + `.measure.py`, `tests/test_issue5_artefacts.py` |
| 2 | `gate-exemption-parent-exclusion` | l'enfant de décision n'est **plus importé** ; le **parent ne compte plus** comme recouvrement | `bridge/gh_kanban_bridge.py`, `pipeline/gh_kanban_bridge.py`, `tests/test_bridge_coverage_gate.py` |
| 3 | `push-ancre-ligne-import` | `push()` ferme **l'issue du graphe**, jamais une autre | idem slice 2 (séquentiel) |
| 4 | `core-decision-ok-pur` | un `/ok` est calculé par un **module versionné pur** | `pipeline/pj_decision.py` (neuf), `tests/test_decision_humaine.py` |

`prototype_required: true` — la **slice 1** (preview) est une **preview en tête**,
parente de toutes les slices de production. Les slices 2 et 3 touchent **le même
fichier** : elles sont **séquentielles**, jamais en parallèle sur le même fichier.

## Verdict `PROTOTYPE: oui` — la page des artefacts (slice 1)

Le verdict de t3 est `PROTOTYPE: oui` : l'humain doit pouvoir **juger le rendu**
avant tout développement. Deux artefacts **existaient déjà et sont ratifiés** par t3 ;
la slice 1 les **matérialise dans le dépôt** pour qu'ils soient jugeables, versionnés
et rejouables — elle n'en produit **aucun nouveau**. Sans elle, un artefact posté dans
Discord n'est ni versionné ni rejouable.

La page **`docs/architecture/context/issue-5-decision-flow.html`** (page **inerte**, 0
composant interactif) porte les deux artefacts ratifiés :

- **(a) le diagramme de séquence V2** — PNG, `sha256 b311b966793227d6…` (93 406
  octets), provenance Discord `1551179637655207957`. Il décrit le flux en **3 phases** :
  1. création automatique de l'issue enfant au premier blocage (0 LLM) ; 2. décision par
  commentaire GitHub `/ok` ; 3. re-blocage ⇒ la même enfant rouverte. Il **remplace** le
  diagramme v1 à boutons ;
- **(b) la maquette de texte inerte en 2 messages** (0 composant) : la notification
  reçue (`sha256 a4b3ed538e…`, 788 octets, provenance `1551179956640555048`) et le
  commentaire « point à statuer » + la table des effets de la réponse
  (`sha256 b5ca3d354af7…`, 1 437 octets, provenance `1551179959974887539`). La maquette
  **dit elle-même** où la notification est postée : « Posté dans **le fil de l'issue
  enfant** (jamais dans le fil du ticket) ».

La page porte un **registre machine** (`<script type="application/json"
id="decision-flow-ledger">`) qui déclare l'attendu (nom, nature, empreinte, taille) de
chaque artefact ; la page rendue porte le **mesuré**. Le script voisin
**`issue-5-decision-flow.measure.py`** confronte le rendu au déclaré, **là où
l'artefact est rendu** (jamais la charge déclarée comparée à elle-même) : déclarer une
empreinte sans rendre l'artefact ne passe pas, une retouche du rendu est détectée, et
un artefact dont l'empreinte est déclarée **obsolète** est refusé en nommant sa
provenance. Le script est **pur** (aucun réseau, aucun fichier écrit). Codes de sortie :
`0` concordance · `1` écart · `2` erreur d'usage.

Les **artefacts v1 sont obsolètes et interdits** comme état courant : le diagramme
`1551168046050054157` (boutons « Débloquer / Abandonner ») et la maquette
`1551167343504396362` (2 boutons `disabled`). Le design ratifié n'a **plus aucune**
interaction par bouton.

## Ce qui existe déjà (mesuré le 2026-09-20, ref `dev`)

| brique | ref | état mesuré |
|---|---|---|
| escalade | `~/.hermes/scripts/pj_escalate.py` | **non versionné** dans le dépôt (`git ls-files` vide). Poste « Décision attendue », ne peut pas recevoir de réponse. Son versionnement est l'objet de **l'issue #4** (OPEN), distincte — c'est lui qui, hors dépôt, créera l'enfant, postera le point à statuer et consommera le `/ok`. |
| helper Discord | `skills/gh-kanban-bridge/scripts/discord_thread.py` | versionné **et** copié en `~/.hermes/scripts/discord_thread.py` — les deux **diffèrent** (`diff` → non identiques). |
| pont | `bridge/gh_kanban_bridge.py` | `pull()` fait `continue` si l'issue porte `MIRROR_LABEL` (`kanban`) ou `TRIAGE_LABEL` (`triage`) ; `cmd_new()` exclut par le même prédicat. |
| notifier gateway | `kanban_notify_subs` | **vide** (0 ligne sur 5 boards) : le notifier `blocked`/`needs_input` ne délivre rien. |

## Défauts de fond mesurés pendant la reconnaissance

### Défaut A — la trappe du gate de couverture (dans le pont)

Le commentaire de couverture propose « poser le label `kanban` ; le pont l'importera
au tick suivant ». **C'est faux** : `pull()` fait `continue` dès que l'issue porte
`kanban` (`if MIRROR_LABEL in labels or TRIAGE_LABEL in labels: continue`), et
`cmd_new()` l'exclut par le même prédicat. `kanban` est le label posé **après**
import, jamais un déclencheur. Ce défaut touche le **pont**, pas l'escalade — il est
**corrigé par la slice 2** (`gate-exemption-parent-exclusion`).

### Défaut B — `push()` ferme la mauvaise issue

`issue_number_of()` rend la première `#N` citée dans le corps de la carte racine, pas
la ligne d'import `/issues/5`. Mesuré : la carte racine de #5 cite `#4` **avant** sa
ligne d'import ⇒ le pont fermerait `#4` avec le résumé du worker de #5. **Corrigé par
la slice 3** (`push-ancre-ligne-import`).

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières externes)

- **GitHub** — le canal de décision : un commentaire sur l'issue **enfant** dont le
  premier élément est `/ok`. Adapter : `gh` CLI, déjà lu par le pont toutes les 5 min.
- **Discord** — notifieur uniquement : message + **lien direct** vers le point à
  statuer. Adapter : helper `discord_thread.py`. **Aucun** composant interactif
  (`ActionRow`, `custom_id`) — le design ratifié ne porte plus de bouton.
- **Kanban Hermes** — source de vérité. La décision aboutit à `comment` + `unblock` sur
  la carte, invoqués en `subprocess`.
- **Aucun** nouveau port : les trois surfaces existent déjà ; l'issue les **réutilise**
  en ajoutant une voie d'écriture (le retour de décision) là où il n'y avait qu'une
  voie de lecture (l'escalade).

### Fonctionnel (capacité traversée)

La capacité traversée est la **décision humaine sur blocage**, qui relie aujourd'hui
deux capacités existantes de façon asymétrique : *escalade* (blocage → message, livrée)
et *reprise* (unblock → re-spawn, livrée). L'issue #5 ajoute le **maillon manquant**
entre elles : *saisie de décision*. Elle ne modifie ni l'escalade (hors-scope, issue #4)
ni la reprise.

### Code (composants impactés)

- **`pipeline/pj_decision.py`** (neuf, slice 4) — le **module versionné pur** qui
  calcule, pour un commentaire, la décision `/ok` et son effet (réponse verbatim,
  unblock, fermeture de l'enfant, re-blocage ⇒ réouverture). C'est le **core** de
  l'issue.
- **`bridge/gh_kanban_bridge.py`** + **`pipeline/gh_kanban_bridge.py`** (slices 2 et 3)
  — exemption du parent du calcul de recouvrement, exclusion de l'enfant à l'import,
  ancrage de `push()` sur la ligne d'import. Fichier **partagé** par les deux slices,
  donc séquentiel.
- **`~/.hermes/scripts/pj_escalate.py`** (non versionné — cf. issue #4) — créera
  l'enfant, postera le point à statuer, consommera le `/ok`. **Hors de cette PR** : son
  câblage relève du chantier de versionnement. Conséquence assumée et documentée : la PR
  de #5 rend le pont correct et le core testable, **mais ne débloque encore aucune carte
  en production**.

## Lecture SDD (spec-driven)

La spec est le body de l'issue #5, dont les scénarios Gherkin sont **les** critères
d'acceptation (nominal, limite multi-cartes, erreur déjà-débloquée, erreur ticket CLOS).
La doc décrit le livré : la slice 1 matérialise les artefacts ratifiés (page inerte +
script de mesure), la slice 4 livre le module de décision. Le livrable de l'issue est un
**diff de code** (pont + module pur + tests), à la différence de l'issue #1 dont le
livrable était un état de board.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *décision humaine* — chevauche *escalade* (production
  du message) et *admission/livraison* (cycle de vie de la carte), sans en être un
  nouveau : c'est la **jonction de reprise** entre deux contextes existants.
- **Agrégat racine** : la **carte kanban bloquée** (invariant : elle ne repart en
  `ready` que sur une décision explicite portant son `id` exact). L'**issue enfant**
  est l'objet de décision qui matérialise la carte : une enfant par carte, rouverte
  (jamais dupliquée) sur re-blocage.
- **Value objects** : le **jeton `/ok`** (unique, casse indifférente — `/unblock`
  rejeté) ; le `(board, task_id)` résolu depuis l'enfant ; la clé `parents` et le
  marqueur `last_reopen_comment_id` (re-blocage). Le format de carte kanban (5 sections)
  reste inchangé.
- **Domain events** : `commentaire GitHub` (premier élément `/ok`) → `comment`
  (« décision humaine ») → transition `blocked` → `ready` (re-spawn) → fermeture de
  l'enfant. Un commentaire sans `/ok` produit une demande d'éclaircissement sans
  transition.

## Lecture TDD (contrats testables)

Les fonctions que `pj-test` verrouille (l'issue l'exige : les scénarios **automatisés**,
le module de décision **pur**, testable sans Discord ni réseau) :

- **`pipeline/pj_decision.py`** (slice 4) — module pur : pour un commentaire, rend la
  décision (token `/ok` présent ou non) et l'effet (réponse verbatim, unblock, fermeture
  de l'enfant, réouverture sur re-blocage). `tests/test_decision_humaine.py` porte
  **20 cas** (RED re-dérivé sur le design ratifié, commit `c91353d`).
- le mapping **commentaire → carte** : par l'**enfant** uniquement, **sans** résolution
  par nom de fil (le défaut B historique est éliminé par construction).

La slice 1 est verrouillée par `tests/test_issue5_artefacts.py` (**20 cas** : nominal,
limite, erreur) qui mesure la page là où elle est rendue.

## Lecture hexagonale (le core reste pur)

Le **core pur** à préserver est le module de décision `pipeline/pj_decision.py` : une
fonction qui manipule des chaînes/dicts, **sans** Discord, kanban, réseau ni horloge.
Les adapters (`gh` pour lire le commentaire, `discord_thread.py` pour notifier,
`subprocess` `kanban()` pour `comment`/`unblock`) restent en périphérie et ne portent
**aucune** logique décisionnelle. Le script de mesure de la slice 1 est lui aussi pur
(aucun réseau, aucun fichier écrit).

## Composants impactés par l'issue #5

- `pipeline/pj_decision.py` — module de décision (core, slice 4, neuf).
- `bridge/gh_kanban_bridge.py` + `pipeline/gh_kanban_bridge.py` — pont (adapters,
  slices 2 et 3).
- `~/.hermes/scripts/pj_escalate.py` — création de l'enfant + point à statuer +
  consommation du `/ok` (adapter, **non versionné** ; câblage hors PR, issue #4).
- `docs/architecture/context/issue-5-decision-flow.html` + `.measure.py` — la preview
  (slice 1, livrée) : matérialise les artefacts ratifiés, aucun composant interactif.

## Frontières traversées (résumé)

```
carte bloquée (kanban)
  → (pj_escalate) issue ENFANT + notification + lien direct   [Discord]
  → (commentaire GitHub commençant par /ok sur l'enfant)      [GitHub]
  → (pj_decision) réponse verbatim + unblock → ready → re-spawn [kanban]
  → fermeture de l'enfant ; re-blocage ⇒ réouverture de la MÊME enfant
```

Deux frontières traversées, aucune nouvelle : **GitHub ↔ kanban** (commentaire → effet,
voie de décision) et **Discord ↔ kanban** (notification → lecture, voie de lecture
seule). Le saut « message → décision » qui n'existait pas est comblé par un module pur
déterministe (0 LLM, 0 bouton) : seul l'humain déclenche le déblocage, par `/ok`.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** les questions ouvertes qui relèvent d'arbitrages
d'orchestrateur/humain, à rendre dans la discussion de l'issue : l'installation du
câblage vers les copies live (chantier cross-repo, lié à l'issue #4), et la dérive
versionné ⟷ prod des wrappers de pont. Ces points sont **documentés**, pas décidés ici.
