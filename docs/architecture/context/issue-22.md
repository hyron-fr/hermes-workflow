---
type: context
status: draft
tags: [architecture, decision-interface, pj-decision, cadrage, issue-19]
issues: [22]
---

# Cadrage architectural — issue #22 « t5 validate »

## Positionnement (cadre exact)

L'issue #22 est un **ticket de décision** (labels `decision` + `kanban`) : son point à
statuer est le déblocage de la carte `t_4eaf85c8` (`t5 validate`, board
`pj-hermes-workflow`), qui porte le gate humain du chantier #19. Le body est le
« Point à statuer » que l'escalade de décision a posé — il ne décrit pas une
fonctionnalité à construire : le périmètre de #22 est **la décision**, pas du code.

**État mesuré le 2026-10-10 (ref `wt/t_572cbbf8` @ `8e35b6e`)** : le point a déjà été
tranché, et la carte pointée est **done** :

| fait | valeur mesurée | preuve |
|---|---|---|
| `t_4eaf85c8` (carte pointée) | **`done`** depuis le 2026-10-03 11:25 | `hermes kanban show t_4eaf85c8` |
| GO humain #19 | enregistré le **2026-10-03 09:15 UTC** (clic ✅ Go non ACKé par le plugin `pj-buttons` → « The application didn't respond in time » ; voie de secours CLI `unblock`, commenté sur la carte) | 4e commentaire de `t_4eaf85c8` |
| suite du GO | `t6 submitted #19` (`t_ad99e220`) créé + graphe de 25 cartes / 16 liens construit par le builder officiel `pj_graphwatch` | commentaire de complétion de `t_4eaf85c8` |
| jeton `/ok` sur l'issue #22 | **absent** — 0 commentaire `/ok` (2 commentaires : la bannière `pj-coverage-gate` + le miroir d'import `t_ec7bc24c`) | `gh issue view 22 --comments` |
| `t_ec7bc24c` (miroir kanban de #22) | `todo`, parents t1/t2/t3/t3b/t4/t5 du pipeline #22 — en attente du reste du pipeline | `hermes kanban show t_ec7bc24c` |

Conclusion : **#22 ne demande plus de décision humaine**. Il est un **re-import stérile
du point déjà tranché** : la carte `t_4eaf85c8` n'attend plus de `/ok`, et poser le
jeton sur #22 aujourd'hui ne débloquerait rien (la cible est déjà `done`). La décision
naturelle à porter dans le fil est le **rattachement au travail en vol #19** (option 1 de
la bannière `pj-coverage-gate`) : l'issue #22 se ferme quand sa carte racine
`done` — et le pipeline #22 (carte `t_ec7bc24c`) enchaîne sur ce cadrage.

## Où l'évolution s'implante (croisement infrastructure / fonctionnel / code)

Ce ticket ne crée aucun nouveau composant. Il **s'appuie sur le maillon de décision
livré par l'issue #5** ([[issue-5]]), et son périmètre réel est le **constat d'état** de
ce maillon :

### Infrastructure (frontières externes)

- **GitHub** — canal de décision (le jeton `/ok` en commentaire sur l'enfant). Ici :
  aucun `/ok` n'a été posé, et le jeton n'a **pas lieu d'être** (cible déjà `done`).
- **Kanban Hermes** — source de vérité. La carte cible est lue par le câblage hors
  module (`ctx['cards']`) ; le point à statuer cite la ligne canonique
  `carte: pj-hermes-workflow/t_4eaf85c8` pour la lecture à froid par l'humain.
- **Discord** — notifieur (pas décideur) dans le design ratifié de #5 ; le clic ✅ Go
  de 2026-10-03 a échoué au niveau du plugin `pj-buttons` (wiring des handlers de
  gateway), et a été compensé par la CLI. C'est un défaut d'infrastructure **séparé**
  de #22 : le ticket #21 portait le défaut du plugin, #22 ne le re-porte pas.

### Fonctionnel (capacité traversée)

Capacité *décision humaine sur blocage* (jonction *escalade* → *reprise* livrée par
#5). #22 ne l'étend pas : il **exerce** cette capacité sur une carte qui, au moment de
l'escalade, était bloquée et qui depuis a été débloquée et close par une autre voie
(voie de secours). Le périmètre fonctionnel de #22 est donc **nul en évolution** :
c'est un re-import stérile, et la doc doit le dire plutôt que de décrire une
fonctionnalité absente.

### Code (composants impactés)

Aucun code de production n'est concerné par #22 lui-même. Les composants que le
cadrage **consigne** (mesurés sur `wt/t_572cbbf8` @ `8e35b6e`, base = `origin/dev`
`2027333` + 1 commit) :

| composant | état mesuré | preuve |
|---|---|---|
| `pipeline/pj_decision.py` (core pur `/ok`) | versionné ; le fix « `/ok` après UNE amorce » (`8e35b6e`, `TOKEN_PREFIX_MAX = 1`) est **HEAD de cette branche** — absent de `origin/dev` (`git merge-base --is-ancestor 8e35b6e origin/dev` → no) et de `origin/main` | `git show 8e35b6e --stat` |
| `pipeline/pj_notify.py` (émetteur des 2 notifications) | versionné, testé (`notify_decision`), **non câblé en production** : `grep decision_from_comment\|pj_decision` hors `tests/` et hors le module lui-même → 0 hit dans `pipeline/`/`bridge/` (seule référence : le docstring de `pj_notify`) | `grep` mesuré |
| banc décision | `tests/test_decision_humaine.py` : **26 fonctions `def test`** = **34 cas** (paramétrés) → `34 passed` ; `tests/test_notify_2_niveaux.py` : 28 fonctions = 28 cas → `28 passed` ; combiné **62 passed** | `pytest -q` (venv hermes-agent) |

Le fix `8e35b6e` a été **mesuré en production le 2026-10-06** (faux négatif : « rattaché
/ok » sur l'enfant #31, carte restée bloquée, seule trace = un `ignore` de tick). C'est
lui que ce worktree #22 embarque au-dessus de la base `dev` — il est le **dernier
commit non-dev de la branche**, pas une doc.

## Lecture SDD (spec-driven)

La spec de #22 est son **body** : le point à statuer, la carte cible
(`t_4eaf85c8`), et la règle « `/ok` en premier élément débloque, tout le reste est une
demande d'éclaircissement ». La doc décrit le **livré** : ce cadrage, qui consigne
l'état mesuré du point (tranché) et du maillon de décision (core + notifier, câblage
production hors dépôt). Il ne prescrit pas de nouvelle slice de production.

## Lecture DDD (bounded contexts, agrégats, value objects, domain events)

- **Bounded context** : *décision humaine* (le même que #5). #22 n'ouvre pas de nouveau
  contexte ; il en est un **exercice postérieur** dont le résultat est déjà produit.
- **Agrégat racine** : la **carte kanban** `t_4eaf85c8` (invariant : ne repart en
  `ready` que sur une décision explicite portant son `id` exact). L'**issue enfant**
  #22 est l'objet de décision qui la matérialise — un enfant par carte, et cet enfant
  est devenu obsolète dès que la carte a été débloquée par la voie de secours.
- **Value objects** : le **jeton `/ok`** (unique, casse indifférente, toléré après UNE
  amorce depuis `8e35b6e` — `/unblock` rejeté) ; le couple `(board, task_id)` de la
  ligne canonique `carte: <board>/<task_id>` ; le marqueur `last_reopen_comment_id`
  (péremption du jeton au re-blocage).
- **Domain events** attendus sur #22 : `commentaire GitHub /ok` → `unblock` de
  `t_4eaf85c8` → fermeture de #22. **Mesuré : aucun de ces événements n'a eu lieu, et
  ne peut plus avoir lieu utilement** (cible `done`) — l'événement produit est le
  constat de re-import stérile.

## Lecture TDD (contrats testables)

Les contrats que `pj-test` verrouille déjà et que #22 **n'étend pas** :

- `pipeline/pj_decision.py` : `tests/test_decision_humaine.py` (34 cas, GREEN) couvre la
  grammaire `/ok` (tête / amorce / citation / grammaires refusées), l'anti-rejeu, la
  péremption, la cible unique et le tri-état OPEN/CLOSED/UNKNOWN ;
- `pipeline/pj_notify.py` : `tests/test_notify_2_niveaux.py` (28 cas, GREEN) couvre la
  dédup par décision, les notifications deux-niveaux (enfant notifiée puis fermée,
  parent notifié jamais fermé) et les branches de repli ;
- **hors périmètre de #22** : le câblage production (consommateur de
  `decision_from_comment` dans `pj_escalate`/le pont) — il n'existe pas encore
  (mesuré : 0 hit), et sa livraison ne relève pas de ce ticket.

## Lecture hexagonale (le core reste pur)

Le **core pur** est `pipeline/pj_decision.py` : il calcule la décision portée par un
commentaire, il ne l'applique jamais — aucun `gh`, `subprocess`, `requests`, `sqlite3`.
Les effects (comment + unblock + fermeture) sont portés par l'appelant (hors module).
`pipeline/pj_notify.py` porte les **notifications** d'une décision déjà appliquée
(également sans effet de bord direct sur le kanban, par injection `ctx`). #22 ne
traverse **aucune frontière** : c'est un constat, pas un saut GitHub→kanban.

## Composants impactés par l'issue #22

- `docs/architecture/context/issue-22.md` — **cette note** (le seul livrable de #22).
- `docs/architecture/README.md` (MOC) — une ligne `[[issue-22]]` ajoutée à la section
  « Contextes d'issue (cadrage) ».
- `pipeline/pj_decision.py` + `pipeline/pj_notify.py` + leurs bancs — **consignés, non
  modifiés** par #22 : l'état mesuré (core versionné, notifier versionné, câblage
  production absent) est porté dans cette note, pas dans le code.

## Frontières traversées (résumé)

````
carte bloquée (kanban)
  → (pj_escalate) issue ENFANT + notification                        [Discord]
  → (commentaire GitHub /ok sur l'enfant — absent sur #22, cible done) [GitHub]
  → (voix de secours CLI unblock — déjà posée le 2026-10-03)           [kanban]
  → t_4eaf85c8 done le 2026-10-03 ; #22 reste OPEN, re-import stérile
````

#22 ne franchit aucune frontière : le point qu'il désigne a été tranché par une voie
hors ticket (clic Discord non ACKé + CLI), et le ticket n'a plus de décision à porter.

## Écarts non bloquants consignés (à ne pas laisser croire résolus)

1. **Asymétrie test ↔ production du maillon décision** : `pipeline/pj_decision.py` et
   `pipeline/pj_notify.py` sont versionnés et testés, mais **aucun consommateur de
   production ne les importe** (`grep` hors `tests/` et hors les modules eux-mêmes →
   0 hit dans `pipeline/`/`bridge/`). La livraison du câblage relève du chantier #4
   (versionnement de `pj_escalate`) et de la slice post-#5 — hors périmètre de #22.
2. **Fix `8e35b6e` hors `dev`/`main`** : le correctif du faux négatif du jeton
   (`TOKEN_PREFIX_MAX = 1`) est HEAD de `wt/t_572cbbf8` et de
   `wt/issue-43-decision-jeton-ok`, mais **absent de `origin/dev` et de
   `origin/main`** (mesuré : `git merge-base --is-ancestor 8e35b6e origin/dev` → no ;
   `origin/main` → no). Tant qu'il n'est pas mergé, les crons qui exécutent la copie
   live de `pj_escalate.py` (hors dépôt) ne bénéficient pas du correctif. C'est un
   point de **publication** à trancher, pas un défaut du core : le core est
   versionné et le banc est GREEN.
3. **Miroir de #22 en attente** : `t_ec7bc24c` (carte kanban importée depuis #22,
   `todo`) porte le pipeline du chantier #22 lui-même ; il n'est pas le point à
   statuer de #22, mais il **en hérite** — si le pipeline #22 devait produire du
   code, son cadrage partirait de cette note (et non du body de l'issue, qui est un
   point à statuer périmé).

## Non tranché (et qui doit le rester ici)

Ce cadrage **ne tranche pas** : (a) le rattachement de #22 au travail en vol #19
(option 1 de la bannière `pj-coverage-gate`) vs une nouvelle tâche autonome (option 2)
— c'est un **arbitrage d'orchestrateur** à rendre dans le fil ; (b) la publication du
fix `8e35b6e` vers `dev`/`main` — point de publication, pas de cadrage ; (c) le câblage
production du maillon décision — chantier #4 + slice post-#5. Ces points sont
**documentés**, pas décidés ici.
