---
type: component
status: draft
tags: [architecture, decision-interface, core-pur, hexagonal, issue-5]
issues: [5]
---

# Composant — `pipeline/pj_decision.py` (core pur de décision `/ok`)

> Note de vault produite par `doc-k` (slice 4 `core-decision-ok-pur`). Elle décrit le
> **livré** — le module tel que convergé au commit `45cfa1d` (byte-identique au GREEN
> re-mesuré en convergence, HEAD `7994445`) — jamais une intention. Le cadrage
> ([[issue-5]]) positionne l'issue ; cette note fige le **contrat exact** du module.

## Ce que le module EST

`pipeline/pj_decision.py` est le **core pur** de l'issue #5 : il **calcule** la décision
portée par un commentaire GitHub, il ne l'applique jamais. Aucun appel `gh`, `subprocess`,
`requests`, `urllib`, `socket` ni `sqlite3` — les effets (débloquer la carte, poster le
commentaire, fermer l'enfant) sont portés par l'appelant. C'est ce qui rend le banc
`tests/test_decision_humaine.py` rejouable hors ligne, donc **falsifiable**.

Une seule fonction publique : `decision_from_comment(ctx, comment) -> dict`.

## Contrat d'entrée

`ctx` (dict, pré-alimenté par l'appelant, **aucune passe réseau**) :

- `ctx['issue']` — dict décrivant l'issue **enfant** (`number`, `state`, `parent`…) ;
- `ctx['cards']` — liste de cartes kanban, chacune portant `task_id`, `board`, `status`
  et le numéro d'issue (`issue`) de **son** enfant. C'est ce champ qui fait la liaison ;
- `ctx['seen_comment_ids']` — ensemble des ids de commentaires déjà consommés (anti-rejeu) ;
- `ctx['last_reopen_comment_id']` — id du commentaire « re-blocage », `None` au 1er round
  (borne de validité du jeton).

`comment` — dict `{"id": int, "body": str}` (le commentaire GitHub brut).

## Contrat de sortie

Un dict `{effect, task_id, board, note, acted}` :

- `effect ∈ {"ignore", "unblock", "comment"}` ;
- `task_id` / `board` — la cible quand `effect == "unblock"`, `None` sinon ;
- `note` — la raison, toujours renseignée quand l'humain doit être informé ;
- `acted` — `True` quand un effet est à porter, `False` pour un `ignore` (distingue
  « décision calculée » de « effet à porter »).

La fonction **ne lève jamais** : corps vide, `ctx` partiel, enfant `CLOSED` ou carte
absente produisent `effect == "ignore"` (ou `"comment"` pour l'humain), jamais un crash.

## Grammaire (une seule, pas deux)

- **`/ok`** est l'unique jeton de décision, **en tête** du corps (`split()` fait foi,
  casse indifférente, argument éventuel inerte — `test_argument_supplementaire_ne_retargette_pas`).
- **`/unblock` est rejeté** (avec `/block`, `/drop`) : `REJECTED_TOKENS`, reconnus
  explicitement pour qu'un futur lecteur ne les réintroduise pas « pour compatibilité ».
  Deux grammaires = une divergence garantie — c'est un point ratifié, pas un détail.

## Ordre des gardes (dans le code)

1. jeton en tête : un jeton cité au milieu, un corps vide ou une grammaire refusée → `ignore` ;
2. anti-rejeu dans le round : même `comment['id']` déjà dans `seen_comment_ids` → `ignore` ;
3. objet clos : `issue['state'] != "OPEN"` → `ignore` ;
4. péremption : `/ok` dont l'id est antérieur (ou égal) au `last_reopen_comment_id` → `ignore`
   (sinon l'enfant rouverte serait re-fermée par le jeton du round précédent) ;
5. cible : les cartes de `ctx['cards']` dont `issue == issue['number']` — 0 → `comment`
   (`COMMENT_NO_CARD`), aucune `blocked` → `comment` (`COMMENT_ACTIVE`), plus d'une
   `blocked` → `comment` (`COMMENT_AMBIGUOUS`, cible indéterminée), une seule → `unblock`.

## La ligne canonique `carte: <board>/<task_id>`

Le corps de l'issue enfant porte **une** ligne canonique, exactement
`carte: <board>/<task_id>` — le pendant de `ROOM:` côté room. Elle est le **marqueur de
trace** de l'objet de décision (chaque enfant désigne sa carte à froid). Le module **ne la
lit pas** : la liaison machine est `card['issue'] == issue['number']`. La lecture à froid
de cette ligne appartient au câblage (slice post-#4, hors périmètre de cette slice).

## Lecture hexagonale

Le module est le **core pur** : il manipule des chaînes/dicts, **sans** Discord, kanban,
réseau ni horloge. Les adapters (`gh` pour lire le commentaire, `discord_thread.py` pour
notifier, `subprocess kanban()` pour `comment`/`unblock`) restent en périphérie et ne
portent **aucune** logique décisionnelle. La pureté est prouvée par **exécution**
(`test_le_core_est_pur_a_l_execution` : sentinelle `sys.meta_path` + `builtins.__import__`),
pas par lecture de texte.

## Convergence (slice 4) — mesures reprises telles quelles

- **Tests** : `python3 -m pytest tests/test_decision_humaine.py -q` → `25 passed` sur
  l'arbre courant (HEAD `7994445` == `origin`).
- **Couverture** : `95,29 %` (58/61 statements). Lignes non atteintes `82-83` (except
  `TypeError`/`ValueError`) et `95` (issue enfant non entière) — branches **défensives**.
  Aucune exclusion, aucun seuil baissé.
- **Mutation** : 10 mutants, 9 tués, 1 survivant prouvé **équivalent** champ par champ
  (0 divergence sur `effect`/`task_id`/`board`/`acted`, 5 sur `note`).
- **Déterminisme** : 0 horloge, 0 aléa, 0 sleep ; 3 runs consécutifs → md5 des rouges identiques.

## Écarts non bloquants consignés (à ne pas laisser croire résolus)

1. La ligne canonique `carte: <board>/<task_id>` du contrat n'est **citée par aucun cas**
   du banc — la liaison est testée par `card['issue']`, pas par la ligne. **NON TESTÉE**
   (déjà déclaré par `red-4`).
2. **Asymétrie test ↔ production** du contrat d'entrée : le banc fabrique
   `{task_id, board, status, issue}` ; **aucun consommateur de production n'existe**
   (`grep pj_decision` hors `tests/` → 0 hit). Le module est versionné mais n'est pas
   encore câblé — le câblage relève de la slice post-#4, hors périmètre de cette slice.

## Frontières (résumé)

```
commentaire GitHub (premier élément /ok sur l'enfant)   [GitHub]
  → (pj_decision) décision calculée {effect, task_id, board, note, acted}   [core pur]
  → (appelant, hors module) comment + unblock → ready → re-spawn            [kanban]
```

Le module ne traverse **aucune** frontière : il est le point où la frontière est **franchie
par l'appelant**, pas par lui.
