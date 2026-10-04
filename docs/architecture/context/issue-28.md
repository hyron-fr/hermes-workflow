---
type: context
status: draft
tags: [architecture, decision-interface, reconciliation, escalation, kanban, github, discord, cadrage]
issues: [28]
---

# Cadrage architectural — issue #28 « slice 5/5 — convergence » (point à statuer, carte `t_b7953265`)

## Positionnement (cadre exact)

L'issue #28 est une **issue de décision** (labels `decision` + `kanban`, parent
GitHub : l'issue #27) : le « point à statuer » est la carte de convergence
`slice 5/5` (`t_b7953265`, board `pj-hermes-workflow`), **todo**, dont les 6 parents
(t1..t5 + t3b du pipeline standard) ne sont pas encore `done`. Sa décision attendue
est le jeton `/ok` (ou une question) posté en commentaire sur l'issue #28 —
mécanique héritée de l'issue #5 ([[issue-5]]).

**Ce que #28 tranche, mesuré et documenté par les handoffs t1/t2 (#28) et t1/t2 (#27) :**

Le blocage de fond est celui de la carte convergence #19 `t_f725879f` (issue #19,
slice 5/5, description épinglée du thread Discord) :

- le worktree partagé #19 `.worktrees/t_c22a7e74` (branche
  `wt/issue-19-discord-thread-title-description`) pointe sur `49bb284`
  (= dernier commit **RED test-5**), local **et** remote (`git ls-remote` vérifié) ;
- le commit GREEN revendiqué par le handoff dev-5 (`6661362`) **n'existe nulle part**
  (`git cat-file -t 6661362` → `fatal: Not a valid object name`) ;
- l'API slice 5 (`build_description_lines`, `sync_description`) a **0 occurrence**
  dans `pipeline/`, `bridge/`, `skills/` du worktree partagé — seuls les tests
  `tests/test_thread_description.py` la citent ; banc rejoué : **10/10 RED**.

Le verdict de convergence est donc impossible sans re-push. La décision #28 (portée
par l'humain, 0 LLM) est ce qui permet de rouvrir la chaîne.

**Nature : décision de reprise, pas un livrable de feature.** Le travail de code
attendu par la suite (re-push du GREEN dev-5 ou re-écriture de la slice 5) est le
relais de l'issue #19 — il **ne** fait pas partie de #28.

## Le mismatch structuel documenté (hérité du t2 #27, confirmé sur #28)

Le graphe importé pour #28 (t1 worktree, t2 mémoire, t3 grill-me, t3b doc-cadrage,
t4 draft, t5 validate, t6/racine) est le graphe standard d'une **tâche de
développement** ([[pj-decision]], [[pj-escalate]]). Or #28 est une **décision** :
les phases spec/grill/draft y sont **dégénérées** — t3 ne peut que confirmer la
qualification « décision, re-push », t4 n'a pas de spec de feature à produire, et le
verdict PROTOTYPE est **non applicable** (condition 2 : ≥3 slices sur un livrable
perceptible — une décision n'a aucun livrable perceptible).

Ce n'est **pas** un défaut à corriger ici : c'est le comportement mesuré du
mécanisme d'import de [[pj-bridge-push-ancre]]/bridge — une issue de décision
traverse le pipeline de développement par construction. La note de cadrage sert à
**documenter ce comportement**, pas à le modifier. Toute évolution (ex. : pipeline
dédié aux décisions) relèverait d'une issue de développement propre, hors-scope ici.

## Défaut de fond mesuré — le trou de réconciliation de `pj_decision_watch.py`

**Fait vérifié (non supposé) : `pj_decision_watch.py` n'existe dans le dépôt
versionné NI sous forme de script, NI sous forme de note, NI sous forme de test —
`grep -rln "decision_watch\|pj_decision_watch"` retourne 0 occurrence dans
`pipeline/`, `bridge/`, `tests/`, `docs/` du worktree `t_0b9741ee` (mesuré
2026-10-04, base `origin/dev @ 009f0a7`).** Le trou de réconciliation décrit par le
t2 (#27) ne correspond donc à **aucun composant du dépôt versionné** : il est porté
hors dépôt, dans le mécanisme de suivi de décision d'origine (non versionné,
cf. [[pj-escalate]]).

**Description du trou (mémoire projet, #20 et #21 déjà fermés à la main) :** si la
carte de convergence (ou toute carte de décision) est débloquée par un chemin
**non-`/ok`** (ex. : réponse humaine dans le fil Discord + `kanban unblock` par
l'orchestrateur), le mécanisme de réconciliation ne **ferme jamais** l'issue
décision correspondante → l'issue reste ouverte à vie avec « Point à statuer » alors
que rien n'attend plus.

**Impact direct sur #28 :** si la carte `t_b7953265` passe en `done` sans que l'issue
#28 n'ait reçu `/ok` (par exemple un unblock manuel), **#28 reste ouverte
indéfiniment**. Le trou s'exerce ici, pas seulement sur #27.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — le canal de décision : un commentaire sur l'issue #28 dont le premier
  élément est `/ok`. Adapter : `gh` CLI, déjà lu par le pont toutes les 5 min.
- **Kanban Hermes** — source de vérité : la décision aboutit à `unblock` sur la
  carte `t_b7953265`, invoqué par le mécanisme de décision (hors dépôt versionné,
  cf. [[pj-escalate]] et [[pj-decision]]).
- **Discord** — notifieur (pas de décision) : le thread de l'issue #28 est le canal
  de notification du point à statuer. **Aucun** composant interactif (cohérence avec
  le design ratifié de #5, [[issue-5]]).
- **Aucune** nouvelle frontière : #28 réutilise les trois surfaces existantes
  exactement comme #5 et #27.

### Fonctionnel (capacité traversée)

La capacité traversée est la **réconciliation de décision** : la boucle
`blocage carte → escalade → issue décision → /ok → unblock → carte re-spawn →
convergence` **doit** se terminer par la **fermeture de l'issue décision**.
L'issue #5 a livré le saut « message → décision » ; le trou de réconciliation est
la **faible liaison** qui reste entre « carte terminée (par un chemin quelconque) »
et « issue décision fermée ». #28 **expose** cette faiblesse ; elle ne la répare pas.

### Code (composants impactés)

Aucun composant du dépôt versionné n'est **modifié** par #28 (c'est une décision).
Les composants **impactés en lecture** (à surveiller si la décision aboutit à une
réconciliation future) :

- **[[pj-decision]]** — le core pur `/ok` ; s'il doit traiter un chemin de
  réconciliation non-`/ok`, c'est ici que la logique doit s'implanter.
- **[[pj-notify]]** — émetteur des notifications de décision ; une réconciliation
  non-`/ok` doit produire un effet notifiable symétrique.
- **[[pj-escalate]]** — chaîne d'escalade ; le mécanisme de suivi de décision
  (actuellement hors dépôt) en est le pendant côté consommation.
- **[[pj-bridge-push-ancre]]** — le pont qui ferme l'issue ; si la carte passe en
  `done` par un chemin non-lié à l'issue, le pont ne ferme pas #28.

**Frontière hexagonale préservée :** le core pur `pipeline/pj_decision.py`
(règle `/ok` → effet) reste **inchangé** par cette décision. Tout travail de
réconciliation ultérieur doit passer par des adapters (mécanisme de suivi, pont),
sans toucher au core.

## Lecture SDD (spec-driven)

La spec de #28 est le body de l'issue : le jeton `/ok` débloque la carte
`t_b7953265` et la fait repartir en file ; tout autre commentaire est une demande
d'éclaircissement. **Aucune** spec de feature à produire — la doc décrit le livré,
et le livré est une décision humaine (0 ligne de code de cette issue). La note de
cadrage (cette note) est le seul artefact de doc ; elle **documente le comportement
observé**, elle ne spécifie pas un futur.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context** : *réconciliation de décision* — chevauche la *décision
  humaine* ([[issue-5]]) et l'*admission/livraison* (cycle de vie de la carte kanban),
  sans en être un nouveau : c'est la **jonction de clôture** entre deux contextes.
- **Agrégat racine** : la **carte kanban** `t_b7953265` (invariant : elle ne passe en
  `done` que si la convergence #19 est jugée ; le re-push GREEN est un prérequis
  externe, pas un état de la carte). L'**issue décision** #28 en est l'objet de
  décision, créé par le mécanisme d'escalade.
- **Value objects** : le **jeton `/ok`** (identique à #5) ; la **clé
  `(board, task_id)`** = `pj-hermes-workflow/t_b7953265` ; l'**ancre d'import**
  `Importé depuis https://github.com/hyron-fr/hermes-workflow/issues/28`.
- **Domain events** :
  - `/ok` (premier élément du commentaire GitHub) → `unblock(t_b7953265)` → `ready`
    → re-spawn du worker convergence → jugement → `done` ;
  - autre commentaire → demande d'éclaircissement, **aucun** geste ;
  - **trou** : `unblock` par chemin non-`/ok` → **pas** de fermeture de l'issue #28
    (événement manquant, à modéliser si le trou est comblé par une future issue).

## Lecture TDD (contrats testables)

Aucun contrat nouveau de code ne devient testable par cette issue (0 ligne de
production attendue). Les contrats **existants** que #28 met en scène :

- **`pj_decision.decision_from_comment`** ([[pj-decision]]) — le jeton `/ok` sur #28
  doit produire `EFFECT_UNBLOCK` pour la carte `t_b7953265` ; banc existant :
  `tests/test_decision_humaine.py` (20 cas).
- **`pj_notify.decision_key` / `notify_decision`** ([[pj-notify]]) — la notification
  de la décision #28 doit être dédupliquée par clé de décision ; banc existant :
  `tests/test_notify_2_niveaux.py`.
- **`pj_docs_lint`** ([[pj-lang-lint]]) — cette note de cadrage doit passer le linter
  du vault (preuve de cette carte) ; banc existant : `tests/test_pj_docs_lint.py`.

Le trou de réconciliation, s'il est comblé par une future issue, devra porter **ses
propres bancs** (scénarios : unblock non-`/ok` → issue fermée ; unblock hors décision
→ issue inchangée ; issue déjà fermée → idempotence). **Non tranché ici.**

## Lecture hexagonale (le core reste pur)

Le **core pur** concerné est `pipeline/pj_decision.py` : il n'est **pas** modifié
par #28 (c'est une décision, pas un développement). Les **adapters** qui portent le
trou de réconciliation (mécanisme de suivi hors dépôt, pont `gh_kanban_bridge.py`,
[[pj-escalate]]) sont en **périphérie** ; toute réparation future doit rester
adapter-side, sans réintroduire de logique décisionnelle hors du core.

## Composants impactés par l'issue #28

| Composant | Rôle dans #28 | État |
|---|---|---|
| [[pj-decision]] | Calcule le `/ok` (core, **inchangé**) | livré (#5) |
| [[pj-notify]] | Notifie la décision (adapters, **inchangé**) | livré (#5) |
| [[pj-escalate]] | Chaîne d'escalade (hors dépôt versionné, **inchangé**) | livré (#4) |
| [[pj-bridge-push-ancre]] | Ancre du pont (adapters, **inchangé**) | livré (#5) |
| [[pj-bridge-coverage-gate]] | Gate de couverture (adapters, **inchangé**) | livré (#5) |
| `pj_decision_watch.py` (hors dépôt) | Mécanisme de suivi — **trou de réconciliation** | non versionné, **non couvert** |

## Frontières traversées (résumé)

```
carte t_b7953265 (kanban, todo — 6 parents non done)
  → (issue #28 ouverte, label decision + kanban)           [GitHub]
  → (commentaire /ok sur #28)                              [GitHub]
  → (mécanisme de décision, hors dépôt versionné)          [adapter]
  → (unblock t_b7953265 → ready → re-spawn convergence)    [kanban]
  → (jugement convergence #19, re-push GREEN 6661362 préalable)
  → (t_b7953265 done → #28 fermée par le pont)             [GitHub]
```

Deux frontières traversées, **aucune** nouvelle : **GitHub ↔ kanban** (commentaire →
effet, voie de décision) et **Discord ↔ kanban** (notification, voie de lecture
seule). Le saut « décision → réconciliation » qui **n'existe pas** (trou de
`pj_decision_watch.py`) est **documenté** ici, pas comblé.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :

- le **re-push du commit GREEN dev-5** (`6661362`) : c'est le travail de l'issue #19,
  relayé par la décision #28, pas #28 elle-même ;
- la **réparation du trou de réconciliation** : une future issue de développement
  devra porter ce chantier (bancs + core + adapters) — la présente note est le
  **cadre** de cette future spec, pas sa spec ;
- le **pipeline dédié aux décisions** (ou l'adaptation du pipeline standard pour
  l'absorber) : arbitrage d'orchestrateur/humain, hors-scope ici.
