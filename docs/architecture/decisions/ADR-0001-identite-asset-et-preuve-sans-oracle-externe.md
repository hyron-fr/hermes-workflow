---
type: adr
status: draft
tags: [architecture, adr, assets, vendor, integrite, preuve]
issues: [7]
---

# ADR-0001 — Identité d'un asset vendu et preuve sans oracle externe

## Statut

Proposé (`draft`), porté par la slice doc de l'issue #7 ([[issue-7]]). La
décision est **déjà appliquée** par le banc
`tests/test_asset_mermaid_integrity.py` ; cette note la codifie pour qu'elle
cesse d'être implicite. Validation par l'humain attendue à la review (t6).

## Contexte

L'issue #7 ne corrige pas une logique : elle restaure un **asset vendu**
(`bridge/mermaid.min.js`, bundle esbuild mermaid@11.17.2, 3 572 657 o) dont un
sanitizer de secrets a substitué un littéral numérique — `16666666666666666`,
fraction 1/6 d'une rampe de teinte HSL — par le placeholder `${DISCORD_ID}` en
position de littéral, ce qui casse la syntaxe (`node --check` rc=1).

Le défaut est resté **latent** : le consommateur versionné (`git grep
'script src'` = 0) ne lit pas ce blob, et la copie réellement exécutée en
production pointe **hors dépôt** (`/home/elix/hermes-experiment/bridge/…`,
saine) et masque le défaut.

Trois façons « naturelles » de prouver la restauration se sont révélées
insuffisantes, mesurées pendant le cadrage et la convergence :

1. **Le chemin** — la constante `MERMAID_JS` du renderer pointe vers la copie
   saine hors dépôt sur `dev` ; un contrôle qui résoudrait le chemin par cette
   constante produit un **faux vert** (il validerait une copie que le dépôt ne
   publie pas).
2. **Le `cmp` contre une copie externe** — la copie saine hors dépôt n'est pas
   une « version » de la copie versionnée, c'est un **autre objet** ; de plus
   un littéral substitué « voisin qui parse » (ex. `…6665`) passe `node
   --check` et `cmp` le refuse, mais pas pour la bonne raison.
3. **Le hash d'un artefact externe** — aucun oracle n'est présent dans l'ODB :
   un seul blob a jamais existé, le hash amont est une **mesure figée**, pas
   une source consultable à l'exécution du banc.

## Décision

**L'identité d'un asset vendu se prouve par un invariant dérivable, jamais par
un chemin, un `cmp`, ni un hash d'artefact externe.**

Concrètement, pour tout asset vendu minifié versionné dans le dépôt :

- l'**oracle** est la **somme sha256 de l'artefact amont**, mesurée une fois et
  figée en constante du banc (`SHA_AMONT`) — elle n'est jamais reconsultée à
  l'exécution, elle est **dérivée** de l'octet attendu ;
- le **verdict d'intégrité** est porté par un **census dérivé** des littéraux
  numériques suspects (multiset des séquences 17-19 chiffres) plus la rampe de
  teinte dont la valeur flottante doit être **exactement** `1/6` — un littéral
  « voisin qui parse » échappe à `node --check` mais pas au census ;
- `node --check` n'est qu'un **renfort** (syntaxe), avec `skip` visible si
  l'interpréteur manque — le verdict reste porté par le census + le sha256,
  jamais par l'absence d'outil ;
- la cible du verdict est le **blob VERSIONNÉ** (`git cat-file blob HEAD:<chemin>`),
  jamais le fichier du worktree : un correctif non committé ne peut pas
  blanchir le banc.

## Conséquences

**Garde-fou cause racine** (à appliquer à toute passe de sanitisation de
secrets) : **exclure les assets vendus minifiés** (`mermaid.min.js` et
assimilés) de la détection de secrets. Un bundle minifié ne contient pas de
secrets ; il contient des littéraux numériques qui **ressemblent** à des
snowflakes. La règle de détection « littéral 17-19 chiffres ≈ identifiant
Discord » est un faux positif sur ce type de fichier, et sa substitution casse
la syntaxe sans être détectée.

Conséquences positives :

- la preuve est **rejouable hors réseau** (le banc n'accède ni à npm ni à
  aucune copie externe) ;
- elle est **non vacuous** : `git ls-files '*.js'` rend 3 blobs dont **1 seul**
  échoue (`origin/dev`), donc un contrôle vert a un pouvoir discriminant ;
- elle **refuse la récidive** : placeholder littéral, littéral approximatif, ou
  rampe dont la valeur flottante a changé, sont tous refusés — là où
  `node --check` seul ne voit rien.

Conséquences négatives :

- le sha256 amont est une **constante figée** : si l'asset est légitimement
  mis à niveau (nouvelle version de mermaid), la constante doit être re-mesurée
  et re-versionnée avec le bundle — c'est un geste volontaire, documenté, pas
  une détection automatique ;
- la preuve porte sur la **classe** de défaut (un fichier de travail sain
  masquant un blob versionné cassé), reconstituée par dépôt jetable : elle ne
  rejoue pas littéralement un `git clone --shared`.

## Références

- [[issue-7]] — cadrage architectural de l'issue.
- `tests/test_asset_mermaid_integrity.py` — banc qui applique cette décision.
- Blob cassé `c3922946` (sha256 `ba67386c…`, 3 572 657 o) ; blob restauré
  `79b89d7c` (sha256 `581ed7d7…`, 3 572 661 o = amont mermaid@11.17.2).
