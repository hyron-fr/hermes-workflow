---
type: component
status: draft
tags: [architecture, discord, thread, value-object, notification, component]
issues: [19]
---

# Composant — `pj-thread-name` (le nom du thread, value object lu par 3 lecteurs)

## Rôle

Le **nom du thread Discord d'une issue** est un *value object* : une chaîne
formatée qui **porte l'état** de l'issue et qui est **consommée en lecture** pour
retrouver le thread. Sa grammaire est un **contrat** (arbitrage humain `1a` du
02/10/2026, matérialisé par la maquette `issue-19-maquette.html`, commit
`12abc16`) : changer la forme du nom sans mettre à jour les lecteurs qui le
pars**ent** est une régression silencieuse qui désactive la notification d'étape,
l'escalade et les boutons de décision.

Le cadrage complet est dans [[issue-19]]. Cette note documente **le livré**
(slices 2 `lecteurs-nom-deux-formats` + 3 `titre-4-etats-formateur-pur`, commits
`b1ed6b4` et `1887dad`) : les deux formats acceptés, le formateur pur et la table
des 4 états, les trois lecteurs, et la règle de non-régression — pas un motif
cible non implémenté.

## Les deux formats acceptés

Le format est **arbitré** : `🎬/⚙️/⚠/🛑 <repo>|#<numéro d'issue>|<titre>`.
L'identité `repo|#n` est **fixe d'un état à l'autre** ; seule l'icône de tête
change. L'icône est **optionnelle** pour les lecteurs (ils ancrent sur
`repo|#n`, pas sur l'icône).

```
nouveau (arbitrage 1a)  : <icône> <repo>|#<n>|<titre>      ex. « 🎬 hermes-workflow|#19|… »
ancien (avant #19)       : dépend du lecteur — voir ci-dessous
```

Il n'existe **pas un** ancien format unique : chaque lecteur parle son propre
vocabulaire d'avant #19, et chacun le **conserve** (coexistence, jamais
migration — 18 fils vivants portent encore l'ancienne forme).

## Le formateur pur et la table des 4 états (slice 3)

Le **producteur** du nouveau format est un **formateur pur** livré par la slice 3
(`titre-4-etats-formateur-pur`, commit `1887dad`) : une table d'états fermée et
une fonction de composition, **sans réseau, sans horloge, sans aléa**. Il est le
seul écrivain de nom ; les trois lecteurs de la section suivante n'écrivent jamais.

### La table `TITLE_ICONS` (bijection état → icône)

`pipeline/engine.py` L207–212 — la **seule** source d'icônes ; elle remplace
l'ancien jeu de libellés de statut du moteur (`DEFAULT_STATUS_LABELS`, supprimé).
Bijection : une icône par état, jamais deux fois la même.

| état arbitré | icône | codepoints | sens humain |
|---|---|---|---|
| `startup` | 🎬 | `U+1F3AC` | démarrage — jusqu'à la validation du plan |
| `in_progress` | ⚙️ | `U+2699` **+ VS16** (`U+FE0F`) | les agents travaillent |
| `blocked` | ⚠ | `U+26A0` **sans** VS16 | intervention humaine requise |
| `done` | 🛑 | `U+1F6D1` | terminé |

Les codepoints sont ceux écrits par l'humain (relus au GET sur le message
d'arbitrage) : `⚙️` porte le VS16, `⚠` **ne le porte pas**. Le marqueur `👆`
(option écartée par Q3 = d) est **mort** : aucun état ne le produit, il ne figure
pas dans la table. Le jeu historique `✅ done / ❌ fail / 🔁 retry` n'a plus cours.

### `format_title(project, ticket, title, state)` (formateur pur)

`pipeline/engine.py` L226–239 — compose `<icône> <project>|#<ticket>|<titre>` :

- l'icône vient de `title_icon(state)` (L233), qui **refuse** un état hors table
  (`ValueError` nommant l'état) *avant* toute composition ;
- le `ticket` doit être un entier (pas `bool`) — sinon `TypeError`, jamais un
  `#abc` inventé ;
- l'identité `project|#ticket|` est **fixe d'un état à l'autre** : seule l'icône
  de tête change ;
- un `|` déjà présent dans le titre d'origine est **conservé** (aucun
  échappement) : `project` et `#ticket` restent les deux premiers segments.

**Borne de longueur** (le contrat de troncature) : le nom complet est borné à
`NAME_MAX = 100` (borne Discord, L206). La coupe porte sur la **fin du titre** —
`prefix = f"{icon} {project}|#{n}|"`, puis `budget = NAME_MAX - len(prefix)`, et le
titre est coupé à `[:budget]`. L'identité `repo|#n` n'est **jamais** coupée (elle
est en tête, avant la coupe) ; un titre vide donne un nom valide réduit à
l'identité, **sans placeholder**.

### `rename_thread` — l'écrivain best-effort

`pipeline/engine.py` L256–289 — traduit l'état **interne** du moteur
(`running`/`done`/`fail`/`retry`) en état arbitré, puis délègue au formateur :
`_OUTCOME_STATE = {"running": "in_progress", "done": "done"}` (L215). Le formateur
**reçoit** l'état, il ne décide pas de la transition. Un outcome sans équivalent
arbitré (`fail`, `retry`) **n'écrit aucun titre partiel** (la fonction rend sans
PATCH). Le renommage est **best-effort** : une exception du helper est avalée,
elle ne casse jamais le pipeline. Le projet écrit vient de `ticket["repo"]`, repli
sur `GH_REPO` (basename) puis `DEFAULT_BOARD` (commit `04099bc`).

### La frontière 🎬 → ⚙️

Le passage de l'icône 🎬 (démarrage) à ⚙️ (in progress) correspond à la
**validation du plan par l'humain** (gate `t5`). C'est une frontière de **mot
humain**, pas une transition que le formateur calcule : le formateur reçoit l'état
déjà arbitré, il ne décide jamais du moment de bascule.

## Les trois lecteurs (motifs livrés, chemins et lignes)

Les trois lecteurs résolvent un fil par son **nom** ; tous acceptent le nouveau
format **et** leur ancien format. L'identité `repo|#n` est l'ancre de
l'élargissement : un `#n` **orphelin** (sans repo) ne résout rien, et le fil
d'un **autre dépôt** n'est jamais attribué au dépôt écouté.

### Lecteur 1 — `pj_escalate.thread_index`

- Fichier : `pipeline/pj_escalate.py` — `thread_index(cfg, *, runner=…)`.
- Ancien motif (L261) : `re.match(re.escape(repo) + r"\s+#(\d+)\b", name)` →
  forme `hermes-workflow #19 · …`.
- Nouveau motif (L267) : `re.match(r"(?:\S+\s+)?" + re.escape(repo) + r"\|#0*(\d+)\b", name)`
  → forme `🎬 hermes-workflow|#19|…` (icône de tête optionnelle, `repo|#n` ancre).
- **Sens du repli** : le nouveau motif n'est tenté que si l'ancien **ne matche
  pas** (`if not m:`). Le fil est indexé par `setdefault((repo, n), tid)` : la
  **première** occurrence gagne, aucune entrée n'est écrasée. Un nom sans
  identité n'alimente **aucune** entrée ; le repo résolu est **toujours** celui
  de `known_repos(cfg)`, jamais un repo étranger présent dans le même listage.

### Lecteur 2 — `pj-buttons.THREAD_NAME_RE`

- Fichier : `plugins/pj-buttons/pj-buttons/__init__.py` — `THREAD_NAME_RE` (L35).
- Motif (L35) : `re.compile(r"^\s*(?:\S+\s+)?([A-Za-z0-9._-]+)(?:\s*#|\|#)(\d+)")`
  → les deux séparateurs `#` et `|#` sont acceptés ; l'icône de tête optionnelle
  est absorbée par `(?:\S+\s+)?`.
- Groupes inchangés : `group(1)` = repo, `group(2)` = numéro d'issue.
- **Sens du repli** : `match()` rend `None` sur un nom sans `repo` + séparateur
  (`#19 sans repo ni icône` → `None`) ; il lit le numéro **écrit** (`#9999` →
  `9999`), sans jamais en fabriquer un.

### Lecteur 3 — `engine.resolve_thread`

- Fichier : `pipeline/engine.py` — `resolve_thread(issue_number)`.
- Ancien motif (L77) : `re.compile(rf"issue\s*#?\s*{issue_number}\b", re.IGNORECASE)`
  → formes `🎫 Issue #19 — …` / `{icon} {status} - issue 19 …`.
- Nouveau motif (L83-84) : `re.compile(rf"{re.escape(repo)}\|#0*{issue_number}(?!\d)", re.IGNORECASE)`
  avec `repo = (GH_REPO or "").rsplit("/", 1)[-1]` (L82) → forme `🎬 hermes-workflow|#19|…`.
- **Sens du repli** : `resolve_thread` est **scopé au repo écrit** (`GH_REPO`) :
  le fil d'un autre dépôt (`hermes-experiment|#19|…` cherché comme
  `hermes-workflow`) rend `None`. Le repli `pat_nouveau` est `None` si `GH_REPO`
  est vide (aucun élargissement). Sur aucun match, la fonction rend `None` — le
  thread n'est **pas retrouvé** (l'étape retombe alors sur le canal), jamais un
  fil voisin : `#194` n'est pas confondu avec `#19` (`(?!\d)` borne le numéro).

## Règle de non-régression

Deux bancs gèlent le contrat, en **deux étages** :

**Étage lecture** — `tests/test_thread_name_resolvers.py` (slice 2) :

- les **trois** lecteurs résolvent le nouveau format **et** leur ancien format ;
- les deux formats **coexistent** dans un même listage (un lecteur rend les deux
  entrées) ;
- le numéro **voisin** (`19` vs `194`) n'est jamais confondu ;
- un **repo étranger** n'est jamais attribué au repo écouté ;
- un numéro **inconnu** (`#9999`) ne résout rien et aucun lecteur n'invente de
  numéro ;
- un nom **sans ancre d'identité** (`#19 sans repo ni icône`) ne résout rien.

**Étage écriture** — `tests/test_thread_title_format.py` +
`tests/test_thread_state_source.py` (slice 3) : le formateur est pur, la table est
bijective et fermée (4 états, `⚠` sans VS16, `⚙️` avec VS16), la borne `NAME_MAX`
= 100 ne coupe jamais l'identité, un `|` dans le titre est conservé, `👆` et le jeu
historique `✅/❌/🔁` sont morts, `DEFAULT_STATUS_LABELS` a disparu, et un
workflow sans table ne produit aucun libellé historique.

Tout futur changement de format du nom **doit** repasser par ces trois lecteurs
et ces bancs : renommer sans les mettre à jour est le faux vert qui casse la
notification d'étape, l'escalade et les boutons de décision.

## Points d'injection

Aucun des trois lecteurs ne dépend du réseau dans son contrat : `thread_index`
reçoit le listage via `runner` (sous-processus injectable), `resolve_thread`
via `sh`, et `THREAD_NAME_RE` est une regex pure jugée sur son match. Le banc
exerce les trois sans Discord.
