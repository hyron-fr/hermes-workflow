---
type: context
status: draft
tags: [architecture, assets, vendor, sanitisation, cadrage]
issues: [7]
---

# Cadrage architectural — issue #7 « bridge/mermaid.min.js ne parse pas »

## Positionnement (cadre exact)

L'issue #7 ne demande **aucune nouvelle fonctionnalité** et ne touche **aucun code
métier** : c'est un **défaut d'intégrité d'un asset vendu** (bibliothèque tierce
minifiée). Le fichier `bridge/mermaid.min.js` (esbuild-bundle mermaid, 3 572 657
octets, versionné depuis le commit initial `3c6d59b`) est **syntaxiquement
invalide** :

```
$ node --check bridge/mermaid.min.js
SyntaxError: Unexpected token '{'    rc=1
```

**Cause mesurée (root cause, pas hypothèse)** : un sanitizer de secrets a
substitué un littéral numérique de 17 chiffres — `16666666666666666`, la fraction
**1/6** (`.1666…`) dans une interpolation de rampe de couleur
(`r<.1666…?e+(t-e)*6*r:r<.5?…`) — par le placeholder `${DISCORD_ID}` **en position
de littéral numérique**, ce qui casse la syntaxe. Le sanitizer a pris un
littéral de couleur pour un *snowflake* Discord.

Ce n'est **pas** un bug dans le code du projet : c'est un **faux positif du
sanitizer** commis en amont du versionnement. Le littéral est un nombre de
rampe de dégradé, pas un secret. La « livraison » attendue est une
**restauration d'asset**, prouvée par un contrôle rejouable, pas un changement
de logique.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

Aucune frontière runtime n'est traversée : le correctif est **statique**, dans
le dépôt. Le producteur du défaut est **hors dépôt** (le sanitizer, non tracké)
et le consommateur est un script de rendu hors-ligne.

- **Sanitizer de secrets** — producteur du placeholder, **non versionné**
  (`git ls-files | grep -i sanitiz` → 0). Sa règle de détection
  (« littéral 17-19 chiffres ≈ identifiant Discord ») est la cause racine. Le
  placeholder `${DISCORD_ID}` qu'il injecte est par ailleurs **légitime** dans
  les fichiers de config qu'il est censé assainir (`pipeline/gh_triage_poll.py`
  L29 `CHANNEL_ID = "${DISCORD_ID}"`, `skills/gh-kanban-bridge/scripts/*.py`) ;
  c'est **uniquement** son application à un littéral JS de bibliothèque qui est
  fautive.
- **Git** — deux copies versionnées divergent déjà : `bridge/mermaid.min.js`
  (branche `dev`) et `assets/mermaid.min.js` (branche `main`, `origin/main`).
  Les **deux** portent le placeholder et échouent `node --check` (mesuré rc=1
  sur chacune). La copie **saine** est hors dépôt :
  `/home/elix/hermes-experiment/bridge/mermaid.min.js` (3 sites numériques
  17-19 chiffres, 0 placeholder, `node --check` rc=0).

### Fonctionnel (capacité traversée)

Le défaut brise la capacité **« rendu Mermaid → PNG pour gh-triage »**
(`skills/gh-kanban-bridge/scripts/mermaid_render.py`). La chaîne :

```
texte mermaid → mermaid_render.py render → HTML temporaire (script inliné)
  → Firefox headless --screenshot → PNG → autocrop → attach Discord
```

`mermaid_render.py` lit le fichier via `MERMAID_JS.read_text()` et l'inline dans
`<script>{mermaid}</script>`. Un `SyntaxError` y est **silencieux** : le script ne
s'exécute pas, la page ne signale rien, aucun PNG n'est produit — le rendu
annoncé n'a jamais lieu. C'est le constat de l'issue « Interface de décision
humaine » (slice 1 chargeait ce script et annonçait un rendu inexistant).

**Divergence de résolution du chemin** (à nommer, pas à trancher ici) :

| branche | `MERMAID_JS` | pointe vers | état |
|---|---|---|---|
| `dev` | `Path.home()/"hermes-experiment"/"bridge"/…` | copie hors-dépôt **saine** | rendu OK |
| `main` | `Path(__file__).resolve().parents[3]/"assets"/…` | copie in-repo **cassée** | rendu muet |

La copie exécutée sur `dev` est donc saine par accident (chemin absolu vers un
autre repo) ; la copie que `main` exécute est la copie cassée versionnée dans ce
dépôt.

### Code (composants, ports, adapters)

- **Core pur (hexagonal)** — **non concerné**. Aucune fonction déterministe de
  décision n'est modifiée : il n'y a ici ni agrégat, ni entité, ni value object
  de domaine. L'artefact est un **asset vendu**, pas du code écrit par le
  projet. Le « invariant » à préserver est l'**intégrité d'octets** du fichier,
  pas une logique de décision.
- **Asset vendu** — `bridge/mermaid.min.js` (esbuild bundle de mermaid +
  dayjs + iconify). Sa restauration relève de la copie saine ou de la
  régénération amont, **jamais** d'une réécriture approximative (un littéral
  substitué au hasard parse mais ne calcule plus la même rampe de couleur —
  garde-fou explicite de l'issue).
- **Adapter de rendu** — `skills/gh-kanban-bridge/scripts/mermaid_render.py`
  (consommateur, inchangé par l'issue, mais porteur de la divergence de chemin
  ci-dessus).

## Lecture SDD (spec-driven)

La spec (body de l'issue) est la source de vérité ; elle exige une **preuve
rejouable**, pas une promesse :

```
node --check bridge/mermaid.min.js          # rc=0 attendu
cmp bridge/mermaid.min.js <copie saine>     # identité, ou écart justifié
```

La doc ci-présente ne décrit que ce qui existe et est mesuré : deux copies
versionnées cassées, une copie saine hors-dépôt, un consommateur. Elle ne
spécule sur aucun composant futur.

## Lecture DDD

Pas de bounded context applicatif : l'objet est un artefact d'infrastructure.
Les seules notions pertinentes sont :

- **Value object** — l'**identité d'octets** du fichier (somme `sha256`/`cmp`
  vs copie saine) : c'est l'invariant à restaurer et à vérifier.
- **Domain event** — l'**échec silencieux** du rendu (script non exécuté, aucun
  PNG) : observable seulement par l'absence d'artefact, jamais signalé — c'est
  précisément ce qui rend le défaut coûteux et non détecté.

## Lecture TDD (contrat testable)

Le contrat est un **contrôle de build/asset**, pas un test unitaire Python :
il n'y a pas de fonction à tester, seulement un fichier à valider. Le contrat
rejouable à figer est le couple :

1. `node --check` sur la copie versionnée → `rc=0` (parse valide) ;
2. `cmp` vs copie saine → identité (ou écart documenté et justifié).

Ce couple est le **RED/GREEN** de l'issue : tant que `node --check` sort `rc=1`,
l'issue n'est pas résolue. Un garde-fou post-correctif pertinent (à proposer,
hors périmètre de l'issue) serait un contrôle d'intégrité au versionnement qui
détecte tout `${DISCORD_ID}` dans un fichier `.js` vendu.

## Lecture hexagonale

La frontière à respecter est **la frontière core / asset** : le correctif ne doit
introduire **aucune** logique décisionnelle dans un adapter, et ne doit **pas**
toucher le core pur. Il s'agit d'une opération de restauration de donnée
(copier la valeur saine prouvée), déterministe et vérifiable, sans dépendance
réseau/DOM/Canvas. Le rendu (Firefox headless) reste un adapter hors-ligne ;
aucune décision nouvelle n'y est déplacée.

## Composants impactés par l'issue #7

- `bridge/mermaid.min.js` (branche `dev`) — **à restaurer** (copie cassée) ;
- `assets/mermaid.min.js` (branche `main`) — **à restaurer** (copie cassée,
  même défaut) ;
- `skills/gh-kanban-bridge/scripts/mermaid_render.py` — **exercé** (consommateur),
  non modifié ; porteur de la divergence de chemin `dev` vs `main` ;
- copie saine hors-dépôt `/home/elix/hermes-experiment/bridge/mermaid.min.js` —
  **source de vérité** pour `cmp`.

## Frontières traversées (résumé)

```
sanitizer (hors dépôt, non tracké)            → faux positif
  └─ bridge/mermaid.min.js  (dev, cassé)      → à restaurer
  └─ assets/mermaid.min.js  (main, cassé)     → à restaurer
copie saine (hermes-experiment)               → source de vérité (cmp)
  → mermaid_render.py (consommateur, inchangé) → rendu Mermaid → PNG → Discord
```

Aucune frontière de contexte runtime n'est franchie ; le correctif est une
restauration d'octets versionnée, prouvée par `node --check` + `cmp`.
