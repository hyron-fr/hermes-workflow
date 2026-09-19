# Contributing

Merci de l'intérêt. Ce dépôt est un **pipeline d'agents** : les règles de contribution
portent surtout sur ce qui doit rester **déterministe** et **vérifiable**.

---

## Avant de proposer une modification

### 1. Ouvrir une issue

Toute modification non triviale commence par une issue. Décrivez :

- le **symptôme observé** (pas seulement la solution souhaitée) ;
- la **commande exacte** qui le reproduit et sa sortie réelle ;
- le comportement attendu.

> Une PR qui corrige un bug doit pouvoir citer **la ligne exacte** où le bug se
> manifeste. Une PR dont la prémisse ne tient pas contre le code sera refusée, même
> bien écrite.

### 2. Vérifier le chevauchement

Avant d'ouvrir une nouvelle issue, cherchez-en une qui couvre déjà le sujet
(ouverte ou avec une PR ouverte). Ce dépôt applique lui-même cette règle : son pont
GitHub bloque l'import d'une issue qui recouvre du travail en vol.

---

## Règles de conception (non négociables)

### Le mécanique est scripté, sans LLM

Tout ce qui peut être déterministe le reste : import d'issues, construction de graphe,
linters, portes de qualité. **Un pipeline au repos doit coûter zéro token.** Le LLM
n'intervient que là où il faut juger (rédiger une spec, arbitrer une ambiguïté).

Une PR qui ajoute un appel LLM sur un chemin mécanique sera refusée.

### Une porte de qualité s'éprouve dans les DEUX sens

Un contrôle qui ne teste qu'un cas sain ne prouve rien (scope ignoré, rapport absent,
exclusion trop large). Toute porte doit être livrée avec :

1. un cas **sain** → exit 0, muet ;
2. un cas **fautif** → exit 1, avec un message actionnable.

Les deux doivent être dans la suite de tests.

### Un filtre par motif filtre en GÉNÉRAL, jamais par liste fermée

Un linter qui exclut `^t[1-6]\b` transforme toute étape ajoutée ensuite (`t3b`, `t4a`)
en faux positif **précisément au moment où on ajoute une étape**. Écrire le motif
général (`^t\d+[a-z]?\b`).

### Un gate déterministe vaut par son PÉRIMÈTRE

Un contrôle qui scanne tout le dépôt signale le contenu **préexistant** : il devient
inutilisable et se fait désactiver au lieu d'être corrigé. Restreindre à la zone où la
convention s'applique (les répertoires du vault, pas tout `docs/` ; les fichiers du
diff, pas tout le repo).

### Pas de chemin en dur, pas de variable en dur

- Jamais `/home/<user>/...` : résoudre depuis `Path(__file__)` ou une variable
  documentée.
- Jamais d'identifiant d'environnement (canal Discord, guild) dans le code : variable
  d'environnement, avec valeur par défaut vide.
- Jamais d'exécutable par chemin absolu supposé : `shutil.which()` puis une liste de
  candidats **vérifiés** (`isfile` + `X_OK`).

> Un cron n'a pas le PATH interactif. Un chemin en dur qui marche dans votre shell
> échoue en production, silencieusement.

### Le sens des liens kanban est `link <parent> <child>` — l'enfant ATTEND le parent

Une carte de synthèse se construit **à l'envers** (chaque production est parent de la
synthèse). Jamais `--parent <synthèse>` sur une de ses entrées : deadlock.

### Les cartes de pipeline se créent mécaniquement

Ne jamais créer à la main les cartes qu'un script sait construire (graphe `t1..t5`,
slices, worktrees). Un graphe écrit à la main dérive de la spec ; un graphe construit
depuis `slices.json` est vérifiable.

---

## Tests

```bash
python3 -m pytest tests/ -q      # doit afficher 113 passed
```

- Les tests chargent leurs modules **depuis ce dépôt** (chemins relatifs via `REPO`),
  jamais depuis un emplacement externe. Un test qui lit `/home/<user>/...` passe sur la
  machine de son auteur et échoue partout ailleurs.
- Pas de test « change-detector » (qui fige une valeur destinée à changer : comptage,
  catalogue, numéro de version).
- Un test qui lit le **texte source** d'un fichier est refusé : il teste la forme, pas
  le comportement. Extraire la logique dans une fonction pure et l'appeler.
- Toute correction de bug arrive avec un test **invariant** qui échoue sur le code
  d'avant.

### Vérifier qu'un test échoue bien pour la bonne raison

Un test vert ne prouve pas qu'il teste ce qu'il prétend. Contre-épreuve utile : masquer
ou déplacer la ressource testée et vérifier que la suite échoue — sinon le test lisait
autre chose.

---

## Assainissement (dépôt public)

**Aucun secret, aucune donnée d'infrastructure, aucun identifiant d'environnement.**
Avant de pousser :

```bash
# clés, tokens, IP privées, chemins personnels, identifiants Discord
grep -rnE "sk-[A-Za-z0-9_-]{10,}|/home/[a-z]+|[0-9]{17,19}" --include="*.py" --include="*.md" .
```

Les secrets vivent dans `~/.hermes/profiles/<profil>/.env`, **hors de ce dépôt**.
`config.yaml.example` est assaini : il ne contient que des placeholders `${VAR}`.

---

## Commits et PR

- Un commit par intention, message à l'impératif, expliquant le **pourquoi**.
- La PR référence l'issue (`Closes #N`) — sans cette ligne, GitHub ne lie pas la PR à
  l'issue et la fermeture dépend d'un seul mécanisme.
- **L'agent ne merge jamais.** Le merge est une décision humaine.
- Une PR qui touche une porte de qualité doit montrer les **deux** cas (sain/fautif)
  dans sa description.

---

## Signaler un problème de conception

Les règles ci-dessus viennent de défauts observés en production. Si vous en découvrez
un nouveau, documentez-le : **le symptôme, la cause racine vérifiée dans le code, et
la règle qui l'aurait empêché.** C'est ainsi que ce fichier a été écrit.
