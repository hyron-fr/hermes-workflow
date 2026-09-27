---
type: component
status: draft
tags: [architecture, decision-interface, bridge, coverage-gate, issue-5]
issues: [5]
---

# Composant — gate de couverture du pont (slice 2 `gate-exemption-parent-exclusion`, vague 2b)

> Note de vault produite par `doc-k` (slice 2 de l'issue #5, mise à jour par la
> carte doc de la vague 2b). Elle décrit le **livré** — le gate tel que convergé
> au HEAD `0283219`, vague 2b fixée par GREEN `990ce4a` + RED `52823cf` et
> re-jouée par la convergence (run 166, HEAD figé `52823cf`) — jamais une
> intention. Le cadrage ([[issue-5]]) positionne l'issue ; cette note fige le
> **contrat exact** du gate, de la trappe `pj-import` et de ses deux prédicats
> adjacents.

## Ce que les slices 2 et 2b livrent

Cinq corrections **mesurées une par une** sur le pont, toutes dans
`bridge/gh_kanban_bridge.py` (copie miroir `pipeline/gh_kanban_bridge.py`,
byte-identique — `test_les_deux_copies_versionnees_du_pont_sont_identiques`) :

1. **Exclusion de l'objet de décision** — `DECISION_LABEL = "decision"`.
2. **3ᵉ branche corrigée** — exemption du parent par **soustraction**.
3. **Ancre de `issues_with_graph()`** — plus d'issue fantôme.
4. **Trappe corrigée** — l'échappatoire proposée est réelle.
5. **Ordre 2b** — le label `pj-import` est **assuré** dans tout tick qui poste
   une trappe **ou** importe, **avant** le premier commentaire de trappe (§4).

## 1. Le label `decision` (exclusion déterministe)

`DECISION_LABEL = "decision"` est une **constante gelée**
(`test_le_label_de_decision_est_le_nom_gele`). Elle exclut l'**issue enfant de
décision** de l'import : un objet de décision n'est **pas une tâche**. L'importer
déclencherait un graphe complet `t1..t5` + une room de délibération **sous** une
carte de décision (mesuré : 6 cartes, 11 liens).

Le prédicat de `pull()` (avant le gate) et celui de `cmd_new()` (candidats au
drill) portent **le même** test :

```
if MIRROR_LABEL in labels or TRIAGE_LABEL in labels or DECISION_LABEL in labels:
    continue
```

L'objet de décision est écarté **avant** le gate, donc **zéro** appel de gate
(`test_objet_de_decision_coute_zero_appel_de_gate`) et **zéro** candidature au drill
(`test_l_objet_de_decision_n_est_pas_candidat_au_drill`).

**Nom gelé, jamais `kanban`** : `kanban` veut dire « déjà miroir d'une carte » — le
réutiliser réécrirait la trappe sous un autre motif. **Jamais** `decision:unblock`
non plus. Ce point est ratifié, pas négociable.

## 2. L'exemption du parent (3ᵉ branche par soustraction)

`coverage_verdict(issue, ctx)` calcule le chevauchement. La règle exacte :

```
overlaps = (refs | hits_titre) - {parent} - {self}
blocked  = bool(overlaps)
```

La soustraction est **appliquée AVANT toute passe**, références **et** titres :
`exempt = {self} | ({parent} if parent else set())` est retranché de `in_flight`
avant le calcul (`test_exemption_appliquee_avant_la_passe_de_titre`). Sans cet
ordre, le parent reviendrait par la porte de derrière via le recouvrement de titre
(mesuré : Jaccard 0,8 ≥ seuil 0,34).

**Piège mesuré et couvert** : `gh` rend `parent` comme `{"number": N, …}`, un
**dict**, pas un entier. `_parent_number()` lit deux sources dans l'ordre —
`ctx['parents']` (table pré-alimentée) puis repli sur `issue['parent']` — et
normalise le dict. Lu naïvement, l'exemption serait **silencieusement perdue**
(`test_repli_sur_le_parent_rendu_par_gh`,
`test_parent_rendu_comme_entier_nu_reste_lu`).

**Aucune passe réseau supplémentaire** : `ctx['parents']` est dérivé de la **même**
`gh issue list --json number,title,body,url,labels,createdAt,parent` déjà chargée
(`issue_parents()` / `coverage_context()`). `test_pull_ne_fait_aucune_passe_reseau_supplementaire`
le verrouille.

**Contrat de chaîne** : le **prédicat** + la **constante** `DECISION_LABEL` vivent
ici (**#5**). La création de l'enfant **avec** ce label appartient à la slice de
câblage (post-#4), qui appellera `ensure_mirror_label()` sur le nouveau nom comme
`pull()` le fait déjà pour `kanban`.

## 3. L'ancre de `issues_with_graph()`

La liste des graphes ne compte que **deux** sources, jamais les `#N` libres du
corps (`test_graph_liste_ignore_les_hash_libres_des_corps`) :

- **(a)** la ligne d'import `Importé depuis …/issues/<n>` (`_IMPORT_URL_RE`) ;
- **(b)** le titre du gabarit de graphe `t<n> … #N` (`_GRAPH_TITLE_RE`).

La version naïve ramassait **tous** les `#N` cités par une carte `t1…t6` : une
carte `t6` parlant de « la PR #7 de <autre repo> » inscrivait un numéro d'issue
**inexistant** dans la liste (mesuré `[1, 2, 4, 5, 7]` alors que
`gh issue view 7` répondait « Could not resolve »). Une future #7 de ce dépôt
aurait été refusée à l'import sur un **fantôme**. La règle ancrée rend la vérité du
board : 0 manque, 0 faux positif (`test_graph_liste_est_exactement_la_verite_du_board`).

## 4. La trappe corrigée (`pj-import`, pas `kanban`)

Le texte du gate ne propose **plus** de poser le label `kanban`
(`test_le_gate_ne_propose_plus_de_poser_le_label_kanban`) : c'était faux, car
`pull()` fait `continue` sur `kanban`. L'échappatoire réelle est
`IMPORT_OVERRIDE_LABEL = "pj-import"` — « nouvelle tâche assumée » posée **à la
main**. Le gate la lit **AVANT le verdict** (`test_l_echappatoire_proposee_par_le_gate_fonctionne`)
et la **respecte** : l'issue est importée malgré le recouvrement.

La trappe est honnête parce que le label **existe quand elle parle**. Contrat
figé par l'arbitrage `t_c58b9d46` (vague 2b), chaque point mesuré au HEAD :

- **C1 — assuré dans TOUT tick qui poste une trappe OU importe une issue.** Le
  garde est `if not DRY_RUN and (covered or to_import):`
  (`bridge/gh_kanban_bridge.py:504`) : `covered` non vide → une trappe va être
  postée (cas a) ; `to_import` non vide → une issue sera importée (cas b).
  **Indépendant de `to_import`** : quand la SEULE candidate du tick est couverte,
  le gate vide `to_import` (L490) et c'est `covered` qui déclenche la création.
  Un seul appel par tick, idempotent côté `gh` (garde « already exists », L241).
- **C1 — la création précède le PREMIER commentaire de trappe.**
  `ensure_import_override_label()` (L507) est émis avant la boucle `if covered:`
  qui poste les commentaires (L509–516). L'ordre est verrouillé par
  `test_slice2b_nominal_le_geste_propose_par_la_trappe_est_executable_dans_ce_tick`
  et `test_slice2b_limite_tick_mixte_l_ordre_tient_et_le_label_n_est_cree_qu_une_fois`
  (assertion `index(label create) < index(premier commentaire de trappe)`), le cas
  (b) seul — un tick qui importe, sans aucune trappe — par
  `test_slice2b_nominal_un_tick_qui_importe_cree_toujours_le_label`.
- **C2 — échec de création BRUYANT et AUCUNE promesse.** `gh label create`
  refusé (hors « already exists ») trace nom du label + stderr (L242–245) puis
  lève ; l'exception remonte **hors** du `try` de signalement (L517–521), donc le
  tick s'arrête **avant** la boucle `if covered:` : **aucun** commentaire de
  trappe nommant `pj-import` n'est posté dans ce tick. Conséquence assumée : le
  signalement du chevauchement est **reporté au tick suivant**, jamais perdu —
  l'issue reste ouverte sans label miroir (L469–471) et le marqueur
  d'idempotence n'est posé que si le commentaire a réellement été posté
  (L394–400), donc le signalement repart au tick suivant ; le mécanisme est mesuré
  par `test_slice2b_limite_deux_ticks_couverts_et_le_second_n_empile_rien`. Mesure
  de l'échec lui-même : `test_slice2b_erreur_un_label_non_cree_ne_laisse_aucune_trappe_qui_promet`
  (exception lève + 0 commentaire de trappe + trace) et
  `test_une_creation_de_label_ratee_est_bruyante` (le levé est diagnostiquable).
- **C3 — `DRY_RUN=1` n'écrit rien.** Le garde L504 exclut la création du label ;
  la boucle d'import passe en `continue` (L539–540) avant toute écriture kanban.
  Mesure : `test_slice2b_erreur_dry_run_n_cree_ni_label_ni_carte`.
- **C4 — `bridge/` et `pipeline/` byte-identiques.** La vague 2b a touché les deux
  copies (commit `990ce4a`, 36 lignes par copie) ; l'identité est verrouillée par
  `test_les_deux_copies_versionnees_du_pont_sont_identiques` et re-mesurée par
  `cmp bridge/gh_kanban_bridge.py pipeline/gh_kanban_bridge.py` → silencieux.
- **Le label miroir `kanban` reste lié à l'import** : `ensure_mirror_label()`
  n'est appelé que si `to_import` est non vide (L505–506) — il ne sert qu'aux
  imports, pas à la trappe.

**Historique (slice 2, corrigé par la vague 2b)** : l'affirmation initiale de
cette note — « le label est créé **avant l'import** » — était **démentie par la
mesure** : l'ancien garde `if to_import and not DRY_RUN:` vivait APRÈS que le
gate avait vidé `to_import`, donc le label n'était créé que dans un tick qui
importe — jamais dans le tick où la trappe parlait (défaut mesuré par sonde hors
ligne, docstring de tête du banc `tests/test_bridge_coverage_gate.py` L1028–1048 ;
escaladé hors-AC par `t_c58b9d46`, sans request-changes). La vague 2b (GREEN
`990ce4a`) a réécrit l'ordre : c'est **`covered or to_import`, avant le premier
commentaire**, qui déclenche la création.

## Lecture hexagonale

`coverage_verdict`, `_parent_number`, `issues_with_graph`, `issue_parents` sont des
fonctions **déterministes** sur des dicts/ensembles — aucun I/O. Les appels `gh` /
`kanban` restent dans les adapters (`list_open_issues`, `issues_with_open_pr`,
`issues_with_graph` lit `kanban list --json`). Le verdict ne **décide** pas : il
rend le chevauchement **visible** et laisse l'humain trancher (rattacher à #N ou
assumer). C'est la frontière hexagonale préservée : la logique décisionnelle du
gate est testable hors ligne, les effets (commenter l'issue, poser un label) sont
portés par l'appelant.

## Convergence (slice 2) — mesures reprises telles quelles

- **Tests** : `python3 -m pytest tests/test_bridge_coverage_gate.py -q` → `40 passed`
  (5 nominal / 9 limite / 12 erreur / 1 garde-fou + 13 renforts préexistants).
- **Couverture** : 55,85 % (origin/dev) → **62,21 %** (HEAD), 100 % des 157 lignes
  ajoutées atteintes, 0 exclusion, 0 seuil baissé. Le gate par fichier reste
  rc=1 à 62,21 % mais la dette est **préexistante** (attribuée par fonction) et le
  seuil atteignable (94,77 % mesuré par sonde de seams jetable).
- **Mutation** : 15 mutants, 13 tués, 1 survivant prouvé équivalent (1 296 cas,
  0 divergence), 1 contrôle négatif inerte.
- **Corrigendum de red-2** : la mesure annonçait `[1, 2, 4, 5]` avec #7 fantôme ;
  rejoué à 17:51, **#7 est un vrai graphe** (`gh issue view 7` = OPEN) — la règle
  ancrée rend `[1, 2, 4, 5, 7]`, la liste bouge par construction, pas un défaut.

## Convergence (vague 2b) — mesures reprises telles quelles (run 166)

- **Banc au HEAD figé `52823cf`** : `python3 -m pytest tests/test_bridge_coverage_gate.py -q`
  → `62 passed` (RUNA versionnée). Re-mesuré par cette carte au HEAD `0283219` :
  `62 passed`, 0 écriture dans le dépôt.
- **Non-régression** : 40 cas de la slice 2 intacts (disparus=0, modifiés/affaiblis=0),
  ajoutés=7 ; RUNC (contrôle avant-vague, `990ce4a^`) = `rc=1` 5 failed / 57 passed,
  **EXACTEMENT** les 5 cas de la vague.
- **Non-tautologie** : mutants spot-check rejoués — M1_cas_b_perdu → `rc=1`
  4 failed (cibles incluses), M3_dry_run_ignore → `rc=1` 1 failed (cible nommée),
  BASE `62 passed`.
- **Écart d'installation versionné⟷runtime** : RUNB (copie live du cron,
  `fe7009bc…` = origin/dev, 0 symbole de #5) → `rc=1` 33 failed / 29 passed ;
  attribution par ensembles : C\B=0 (les 5 rouges de la vague sont tous dans B),
  B\C=28 (le surplus tient à la copie runtime) — écart d'installation, **hors #5**
  (arbitrage `t_c58b9d46`). Voir écart n°1.

## Écarts non bloquants consignés (à ne pas laisser croire résolus)

1. **Maillon d'installation** — ce que cette slice livre est **versionné**, mais
   les crons n'exécutent pas le dépôt : les wrappers font
   `exec python3 /home/elix/hermes-experiment/bridge/gh_kanban_bridge.py`. Aucun
   mécanisme n'installe `pipeline/*` vers les copies live. **Merger la PR de #5 ne
   change donc rien au comportement des crons.** L'installation relève du chantier
   « dérive versionné ⟷ prod » (parqué, Q2=2c de #1) ou de l'issue **#4** — **pas #5**.
2. **`DRY_RUN=1` sur un tick couvert émet le commentaire de trappe** —
   comportement **pré-existant**, mesuré sur la copie versionnée d'avant correctif
   (docstring de `test_slice2b_erreur_dry_run_n_cree_ni_label_ni_carte`) : le
   contrat de la vague 2b (C3) ne porte que les écritures **ajoutées** par la vague
   (label + carte), pas ce commentaire. Tracé, pas corrigé ici.
3. **Gate de couverture (script) rouge hérité** — `bridge/pj_coverage_gate.py`
   `rc=1` à **72,22 %** < seuil 80 % (mesure de la convergence, run 166) ; dette
   **préexistante** (71,59 % avant la vague, amélioration +0,63 pt) et le DoD de la
   convergence ne porte aucun critère de couverture.
4. **L521 défensive non couverte** — la ligne de log du signalement
   indisponible (`bridge/gh_kanban_bridge.py:521`) n'est pas couverte par le banc ;
   périmètre test de la jumelle, tracé sans action ici.

## Frontières (résumé)

```
issue GitHub (ouverte, sans label)
  → (pull) prédicat {kanban, triage, decision} → continue          [pont]
  → (coverage_verdict) overlaps = (refs | titres) - {parent} - {self}   [core pur]
  → si overlaps non vide : label pj-import assuré → trappe (échappatoire)  [GitHub]
  → import normal sinon ; l'objet de décision n'entre jamais            [kanban]
```

Le gate traverse **GitHub ↔ kanban** (lire l'issue, poser un label, commenter) sans
nouveau port : il réutilise `gh` et `kanban` déjà présents, en ajoutant une
décision **posée** plutôt que contournée.
