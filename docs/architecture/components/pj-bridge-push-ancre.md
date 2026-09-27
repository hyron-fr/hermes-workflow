---
type: component
status: draft
tags: [architecture, decision-interface, bridge, push, issue-number, issue-5]
issues: [5]
---

# Composant — ancre de `issue_number_of()` (slice 3 `push-ancre-ligne-import`)

> Note de vault produite par `doc-k` (slice 3 de l'issue #5). Elle décrit le
> **livré** — `push()`/`issue_number_of()` tels que convergés au HEAD `9aa0c15`
> (RED re-dérivé) / GREEN `58fb47f` — jamais une intention. Le cadrage
> ([[issue-5]]) positionne l'issue ; cette note fige le **contrat exact** de
> l'ancre qui lie une carte `done` à l'issue que `push()` doit fermer.

## Ce que la slice 3 livre

Une correction **mesurée** dans `bridge/gh_kanban_bridge.py` (copie miroir
`pipeline/gh_kanban_bridge.py`, byte-identique) : `issue_number_of()` ne prend
**plus** le premier `/issues/<n>` trouvé n'importe où dans le corps d'une carte.
Il lit désormais la **ligne de protocole** que `pull()` a écrite lui-même,
`Importé depuis <url>`, et il y cherche l'URL du dépôt `GH_REPO`.

Le défaut fermé est **réel, pas théorique** : une carte `done` dont le corps cite
l'URL d'une autre issue (le gabarit `Issue GitHub : …/issues/N` de la carte `t6`,
une issue citée en prose, un exemple de sous-chaîne `/issues/5` ⊂ `/issues/40`)
faisait fermer **l'issue de l'autre** avec le résumé du worker. Le correctif
ancre sur la ligne écrite par `pull()`, jamais sur le premier `/issues/<n>` du
texte.

## La règle exacte (livrée)

Deux constantes de module, en tête du fichier :

```
_IMPORT_LINE_PREFIX = "Importé depuis"
_IMPORT_LINE_RE = re.compile(r"^[ \t]*Importé depuis\b")
```

`issue_number_of(task)` :

```
body = task.get("body") or ""
for line in body.splitlines():
    if not _IMPORT_LINE_RE.match(line):
        continue
    m = re.search(r"github\.com/<repo>/issues/(\d+)", line)
    if m:
        return int(m.group(1))
return None
```

- **Ancre en tête de ligne** (`^[ \t]*`), jamais un `re.search` sur tout le body.
- **L'URL du dépôt `GH_REPO`** est cherchée **dans cette même ligne** — une ligne
  de protocole d'un autre dépôt (le pont est un fichier pour 4 dépôts) rend `None`.
- **Tolérance `\s*$`** : une ligne de protocole suivie d'espaces reste reconnue.
- **Aucune ligne d'import ⇒ `None`** : `push()` ignore la carte et ne ferme rien,
  et aucune exception n'est levée (une carte non issue du pont ne casse pas un tick).

## Pourquoi pas `idempotency_key`

La fausse bonne correction a été écartée **et mesurée** : `idempotency_key`
n'est **pas exposé** par `kanban list --json`. Le correctif reste donc ancré sur
le **body** — la ligne de protocole — jamais « utiliser la clé ».

## Lecture hexagonale

`issue_number_of` est une fonction **déterministe** sur un dict : aucun I/O. Les
adapters (`kanban list --json`, `gh issue view/close`) restent en périphérie dans
`push()`/`list_tasks()`. Le banc `tests/test_bridge_coverage_gate.py` (section
slice 3) est **pur** : il charge le pont avec `gh`/`kanban` remplacés par des
enregistreurs, observe exactement quels numéros sont fermés, sans réseau.

## Convergence (slice 3) — mesures reprises telles quelles

- **Tests** : `python3 -m pytest tests/test_bridge_coverage_gate.py -q` → `55 passed`
  (6 nominal / 5 limite / 4 erreur = 15 cas de la slice, décompte paramétrage
  inclus) ; suite complète `200 passed`.
- **Rejeu board réel** : les 5 racines `gh-issue-*` rendent `1/2/4/5/7` = leur clé
  (**0 carte légitime perdue**), les 4 cartes `t6` passent de `1/2/5/4` à `None`
  (**0 fermeture abusive restante**). Défaut réellement armé : 2 cartes `todo`
  où la règle brute ≠ la règle livrée, et l'incident `t_6333de16` (issue #1 fermée
  par une carte `t6` avant le merge de sa PR) reconstitué et tué.
- **Mutation** : 12 mutants, 9 tués, 1 survivant (M8) prouvé équivalent sur 356
  cartes réelles, 2 inertes dont le contrôle négatif.

## Corrigendum consigné (à ne pas laisser croire)

La **prémisse** de la carte annonçait « les 4 cartes à clé `gh-issue-*` rendent
brut `4/2/4/4` → ancré `1/2/4/5` ». Mesuré en convergence, cette prémisse est
**périmée** : `t_b0c76049` (la racine de #5) rend **5 en brut comme en ancré**,
et les **porteurs réels du défaut** sont les cartes **`t6`** (clés
`pj-sub-*`/`pj-t6-*`), brut `1/2/5/4` → livré `None`. Le **verdict** n'est pas
affecté (les 3 scénarios de la carte sont tenus) et le défaut reste **réel** —
mais le corps de la carte doit être amendé par `pj-master` pour refléter le
porteur exact.

## Frontières (résumé)

```
carte kanban (kanban list --json)                          [kanban]
  → (issue_number_of) lit la ligne « Importé depuis <url> »   [core pur]
  → (push) ne ferme que si la carte est `done` ET porte la ligne  [pont]
  → gh issue close <n> — fermeture de l'issue du graphe, jamais une autre  [GitHub]
```

L'ancre traverse **kanban → GitHub** sans nouveau port : elle réutilise `kanban`
et `gh` déjà présents, en remplaçant une recherche non bornée par une lecture de
la **seule** ligne que le pont contrôle.
