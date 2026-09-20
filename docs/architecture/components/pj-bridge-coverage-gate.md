---
type: component
status: draft
tags: [architecture, decision-interface, bridge, coverage-gate, issue-5]
issues: [5]
---

# Composant — gate de couverture du pont (slice 2 `gate-exemption-parent-exclusion`)

> Note de vault produite par `doc-k` (slice 2 de l'issue #5). Elle décrit le
> **livré** — le gate tel que convergé au HEAD `126fde7` (RED re-dérivé) / GREEN
> `b8bdea5` — jamais une intention. Le cadrage ([[issue-5]]) positionne l'issue ;
> cette note fige le **contrat exact** du gate et des deux prédicats adjacents.

## Ce que la slice 2 livre

Quatre corrections **mesurées une par une** sur le pont, toutes dans
`bridge/gh_kanban_bridge.py` (copie miroir `pipeline/gh_kanban_bridge.py`,
byte-identique — `test_les_deux_copies_versionnees_du_pont_sont_identiques`) :

1. **Exclusion de l'objet de décision** — `DECISION_LABEL = "decision"`.
2. **3ᵉ branche corrigée** — exemption du parent par **soustraction**.
3. **Ancre de `issues_with_graph()`** — plus d'issue fantôme.
4. **Trappe corrigée** — l'échappatoire proposée est réelle.

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

Le label est **créé avant** d'être proposé (`ensure_import_override_label()` appelé
avant l'import), sinon la trappe serait un mensonge autrement formulé
(`test_le_label_d_echappatoire_est_cree_avant_d_etre_propose`). Une création ratée
est **bruyante** (`test_une_creation_de_label_ratee_est_bruyante`).

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

## Écarts non bloquants consignés (à ne pas laisser croire résolus)

1. **Maillon d'installation** — ce que cette slice livre est **versionné**, mais
   les crons n'exécutent pas le dépôt : les wrappers font
   `exec python3 /home/elix/hermes-experiment/bridge/gh_kanban_bridge.py`. Aucun
   mécanisme n'installe `pipeline/*` vers les copies live. **Merger la PR de #5 ne
   change donc rien au comportement des crons.** L'installation relève du chantier
   « dérive versionné ⟷ prod » (parqué, Q2=2c de #1) ou de l'issue **#4** — **pas #5**.
2. **Écart hors-AC escaladé** (`t_c58b9d46`, pj-master) : dans le tick où la trappe
   parle, le label `pj-import` qu'elle propose n'existe pas — `to_import` est vidé
   avant l'appel d'`ensure_import_override_label`. Pas de request-changes : les 4
   critères de la carte sont tenus et le fichier est partagé avec la slice 3.

## Frontières (résumé)

```
issue GitHub (ouverte, sans label)
  → (pull) prédicat {kanban, triage, decision} → continue          [pont]
  → (coverage_verdict) overlaps = (refs | titres) - {parent} - {self}   [core pur]
  → si overlaps non vide : trappe + label pj-import (échappatoire)      [GitHub]
  → import normal sinon ; l'objet de décision n'entre jamais            [kanban]
```

Le gate traverse **GitHub ↔ kanban** (lire l'issue, poser un label, commenter) sans
nouveau port : il réutilise `gh` et `kanban` déjà présents, en ajoutant une
décision **posée** plutôt que contournée.
