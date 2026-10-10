---
type: context
status: draft
tags: [architecture, decision, escalation, recycle, convergence, slice-5, description-epinglee, t5-validate, cadrage]
issues: [79]
---

# Cadrage architectural — issue #79 « t5 validate » (reprise de l'escalade conv-5)

## Positionnement (cadre exact)

L'issue #79 (`labels decision` + `kanban`, `idempotency-key gh-issue-79`, parent
#44, sub-issue #82) est **l'escalade de décision de la carte `t_abd8a183`**
(« t5 validate issue #44 », assignée à `pj-master`, board `pj-hermes-workflow`),
bloquée sur le chantier **#44** (« t3 grill-me » — 3ᵉ échelon de l'escalade
conv-5 : #28 → #32 → #44) depuis le 2026-10-08 (58 h+ au blocage au moment de
la mesure).

**Ce n'est pas une nouvelle slice de développement.** C'est le point de
statuer du graphe #44 déjà construit : t5 (`t_abd8a183`) attend le go humain
pour écrire `slices.json` (1 slice docs) et passer `kanban_complete`. Le
verdict t3 est `PROTOTYPE: non / AMBIGU: aucune / ARTEFACT: aucun` → gate
normal, aucun prototype à exiger.

C'est la **reprise de la chaîne conv-5** après que la décision du point à
statuer (#44) a déjà été tranchée par l'option (a) — re-générer le GREEN
dev-5 perdu, couverture portée par l'issue #45 (RECYCLE). La décision
#44 est tracée dans `docs/architecture/context/issue-41.md` (cadrage de la
4ᵉ escalade) et sa spécification dans le body de l'issue #44 (spec complète :
5 sections + Gherkin 3 scénarios + DoR/DoD + slices.json).

Le pipeline de l'issue #79 est déjà déployé (commentaire de la carte racine
`t_0df2e90b`) :

| carte | id | rôle |
|---|---|---|
| t1 worktree | `t_d454dc60` | fourni — `wt/t_d454dc60` sur `dev` @ `2027333` (2 commits devant) |
| t2 mémoire | `t_a5656095` | Hindsight, tags `project:hermes-workflow`, `issue:79` |
| t3 grill-me | `t_65a1b2ed` | verdict à produire (PROTOTYPE / AMBIGU / ARTEFACT) |
| **t3b doc-cadrage** | **`t_d2d8d886`** | **cette note** |
| t4 draft spec | `t_055f62c3` | spec + sous-tâches, room `pj-hermes-workflow-issue-79` |
| t5 validate | `t_8e9c4cce` | publication de la spec + blocage jusqu'au go humain |

## Le point à statuer (tel quel, mesuré le 2026-10-10)

La carte `t_abd8a183` est bloquée avec le motif :

> Attente réponse humaine : spec #44 publiée dans l'issue GitHub +
> notification Discord envoyée (thread `1557708797487882291`, boutons
> Go/No-go). Verdict t3 = PROTOTYPE:non, gate normal.

Le body de l'issue #44 (spec validée par t5, déjà publiée) porte le périmètre
exact de la slice à produire :

- **Fichier** : `docs/architecture/context/issue-44.md` — enrichissement de la
  section « Point à statuer & décision » : verbatim du point + options a/b/c +
  recommandation (a) + raisonnement de couverture (#45 RECYCLE porte déjà le
  re-livrage, banc 7/10).
- **Branch** : `wt/t_0192052f` (worktree partagé `t_0192052f`, tip `e399747`).
- **Preuve** : `pj_docs_lint.py` exit 0 sur le worktree, `git rev-list
  --left-right --count HEAD...@{u}` = `0 0`, `git status --porcelain` vide,
  PR ouverte avec `Closes #44` dans le body.
- **Périmètre INVEST** : 1 slice décision, ≤ 2 fichiers, ~100 lignes.
  `slices.json` : 1 slice `decision-conv5-green-dev5`, `parallel.test=false`,
  `parallel.dev=true`, `convergence=true`, `doc=false`.

L'effet du go humain : `t_abd8a183` (t5) écrit `slices.json` (schéma
ci-dessus), valide par `pj_slices_lint.py` (exit 0 obligatoire),
`kanban_complete` → `pj-graphwatch` construit le graphe (worktree-mk → dev-k ∥
test-k → conv-k → doc-k → doc-review → t6 → worktree-rm → doc-memory →
racine).

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : le jeton `/ok` sur l'issue #79 (premier
  élément du commentaire) est lu par le pont `gh-kanban-bridge` et débloque la
  carte `t_abd8a183`. Adapter : `gh` CLI. La carte `t_abd8a183` est l'objet de
  la reprise.
- **Kanban Hermes** — source de vérité de l'état des cartes. L'effet est
  `comment` + `unblock` sur `t_abd8a183`, invoqués en `subprocess` par le
  câblage de #5 ([[pj-decision]] : `decision_from_comment` calcule,
  l'appelant applique).
- **Discord** — surface de notification : le thread `1557708797487882291`
  (portée par `pj-notify`, [[pj-notify]]) porte les boutons Go/No-go
  (`custom_id pj:go:t_abd8a183` / `pj:nogo:t_abd8a183`). Le go par bouton
  Discord est équivalent au `/ok` sur l'issue.
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/t_0192052f` (worktree `t_0192052f`, tip `e399747`) est la **preuve de
  livraison** de la slice docs #44. État mesuré : propre, 0 mod.
- **Aucun nouveau port** : les quatre surfaces (GitHub, kanban, Discord,
  git) existent déjà dans la boucle #5 ; l'issue #79 les réutilise sans
  en ajouter.

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison** (pas une
fonctionnalité nouvelle). Le chantier #44 est déjà cadré par la note
`issue-41` (escalade 4ᵉ, qui documente le même point à statuer) et le body
de l'issue #44 (spec complète). #79 porte :

- **le point de décision** : le go humain est-il donné ? (Le verdict t3 est
  déjà `PROTOTYPE: non` — il n'y a pas d'artefact à valider, le périmètre est
  une note de doc de ~100 lignes sur 2 fichiers.)
- **la chaîne de livraison** : qui écrit `slices.json` et pousse la PR ?
  (La carte `t_abd8a183` elle-même, au go — 1 slice docs, `convergence=true`.)
- **le verdict de convergence** : après la slice docs, `pj_docs_lint.py`
  sort-il exit 0 sur `wt/t_0192052f` et le `git status` est-il propre ?

### Code (composants impactés)

| composant | état mesuré (2026-10-10) | impact |
|---|---|---|
| `pipeline/pj_decision.py` | présent, stable | [[pj-decision]] — `decision_from_comment` calcule le go, l'appelant applique. Aucun changement. |
| `pipeline/pj_notify.py` | présent, stable | [[pj-notify]] — le thread Discord + boutons Go/No-go déjà envoyés. Aucun changement. |
| `pipeline/pj_escalate.py` | présent, stable | [[pj-escalate]] — la chaîne d'escalade #28→#32→#44→#79. Aucun changement. |
| `docs/architecture/context/issue-44.md` | à enrichir (section « Point à statuer & décision ») | **Fichier de la slice docs #44** — porteur de la décision (a/b/c + recommandation + raisonnement de couverture #45). |
| `docs/architecture/README.md` (MOC) | `issue-44` pas encore référencé | Ligne MOC à ajouter par la carte `doc-k` de #44. |

Le **core pur** à préserver : aucun — cette issue ne touche pas de code de
pipeline. Le périmètre est 100 % documentation (note `issue-44.md` + MOC),
comme le spécifie `slices.json` (`parallel.test=false`, `doc=false` → la
preuve est le lint, pas un banc de tests).

## Lecture SDD (spec-driven)

La spec est le body de l'issue **#44** (spec complète : 5 sections + Gherkin
3 scénarios + DoR/DoD + garde-fous + hors-scope + slices.json), publiée par
la carte `t_abd8a183` (t5) dans l'issue GitHub et le thread Discord. L'issue
#79 **est** le point à statuer de cette carte : elle ne décrit pas une
nouvelle évolution mais le geste de validation qui déclenche la production de
la slice docs #44. La doc décrit le livré : ici le « livré » attendu est la
note `issue-44.md` enrichie (section « Point à statuer & décision ») + la
ligne MOC + le commit poussé sur `wt/t_0192052f` + la PR avec `Closes #44`.
Jusqu'au go, l'état est : spec publiée, thread notifié, carte bloquée.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context traversé** : *décision humaine / convergence* — la
  jonction entre l'escalade (la chaîne #28→#32→#44→#79) et la livraison de la
  slice docs #44. Ce n'est pas un nouveau contexte : c'est le point de
  statuer qui referme l'escalade.
- **Agrégat racine** : la **carte `t_abd8a183`** (invariant : elle ne repart
  en `ready` que sur un `/ok` portant sa ligne canonique
  `carte: pj-hermes-workflow/t_abd8a183` ou un clic Go sur le bouton Discord
  `pj:go:t_abd8a183`). L'**issue #79** est l'objet de décision qui la
  matérialise.
- **Value objects** : le **branch head SHA** `e399747` de `wt/t_0192052f`
  (mesuré 2026-10-10) ; le **thread Discord** `1557708797487882291` ;
  l'**idempotency-key** `gh-issue-79` ; le **verdict t3**
  (`PROTOTYPE: non, AMBIGU: aucune, ARTEFACT: aucun` — gate normal).
- **Domain events** : `/ok` humain sur l'issue #79 (ou bouton Go Discord) →
  unblock de `t_abd8a183` → re-spawn (t5 reformule) → écriture de
  `slices.json` (1 slice docs) → `pj_slices_lint.py` exit 0 →
  `kanban_complete` → `pj-graphwatch` construit le graphe → dev-k enrichit
  `issue-44.md` → conv-k vérifie lint + push + tree propre → doc-k →
  doc-review → t6 → worktree-rm → doc-memory → racine.

## Lecture TDD (contrats testables)

Le contrat testable de la slice docs #44 est **double** :

1. **Preuve de conformité du vault** : `pj_docs_lint.py` sort `exit=0` sur le
   worktree `t_0192052f` (frontmatter YAML valide, `type: context`,
   `status: draft`, `tags` liste, liens `[[nom]]` résolus par nom de fichier,
   MOC à jour). Rejouable sans réseau.
2. **Preuve de livraison git** : `git rev-list --left-right --count
   HEAD...@{u}` = `0 0` (branche en sync avec l'upstream) et
   `git status --porcelain` vide (arbre propre). Rejouable sans réseau.

Il n'y a pas de banc de tests Python pour cette slice (`parallel.test=false`
dans `slices.json`) — le périmètre est 100 % documentation. Les critères
d'acceptation du Gherkin (issue #44, section 2) sont :

- Scénario 1 : le point à statuer est tranchable en un geste → `/ok` sur
  l'issue #44 (ou #79 pour la reprise) débloque `t_abd8a183`.
- Scénario 2 : décision tracée et autoportante → `issue-44.md` porte le
  verbatim du point + options a/b/c + recommandation + raisonnement de
  couverture (#45).
- Scénario 3 (limite) : décision opposée (b/c) → la carte est débloquée avec
  le motif choisi et une carte de suivi dédiée est créée, jamais les deux en
  même temps.

## Lecture hexagonale (le core reste pur)

Cette issue ne touche **aucun code de pipeline** — le périmètre est
documentation. Le core pur (`pipeline/engine.py`, `pipeline/pj_room_keeper.py`,
`pipeline/pj_decision.py`, `pipeline/pj_notify.py`, `pipeline/pj_escalate.py`)
n'est pas modifié. La frontière à respecter est celle de la **boucle de
décision #5** : `pj_decision.decision_from_comment` calcule le go (fonction
pure : commentaire → décision, 0 réseau), l'appelant (le pont
`gh-kanban-bridge`) applique l'effet (unblock + comment sur la carte). Le
cadrage ne change ni l'un ni l'autre.

## Frontières traversées (résumé)

```
issue #79 (GitHub, labels decision+kanban, parent #44)
  → commentaire /ok humain OU bouton Go Discord (surface de décision)
  → unblock de t_abd8a183 (kanban)
  → re-spawn t5 → écriture de slices.json (1 slice docs)
  → pj_slices_lint.py exit 0 → kanban_complete
  → pj-graphwatch construit le graphe
  → dev-k enrichit docs/architecture/context/issue-44.md
  → conv-k : pj_docs_lint.py exit 0 + push 0 0 + tree propre
  → doc-k → doc-review → t6 → worktree-rm → doc-memory → racine
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et
**git ↔ worktree partagé** (preuve de livraison). Le point de fragilité n'est
pas l'appel réseau mais **la couverture commit-à-commit** : le commit de la
slice docs #44 doit être poussé et le branch head doit être en sync
(`0 0`) avant que la convergence ne soit validée.

## État mesuré (2026-10-10, rejouable)

- `origin/dev` = `2027333` (docs cadrage #29).
- `wt/t_d454dc60` (worktree issue #79, fourni par t1 `t_d454dc60`) :
  - **local** = `7091678` (2 commits devant `origin/dev` : `8e35b6e`
    fix(decision) + `7091678` docs issue #81).
  - `git status` : propre.
- `wt/t_0192052f` (worktree partagé de la slice docs #44,
  worktree `t_0192052f`) :
  - **local** = `e399747`.
  - `git status` : propre, 0 mod.
- `git cat-file -t 6661362` → **fatal : Not a valid object name** (le GREEN
  dev-5 original est définitivement absent du dépôt local et du remote —
  confirmé 2026-10-10).
- La carte `t_abd8a183` est **bloquée** depuis le 2026-10-08 (motif : attente
  go humain, thread Discord `1557708797487882291`).
- `docs/architecture/context/issue-41.md` : note de cadrage de la 4ᵉ
  escalade, documente le même point à statuer (banc 8/10 au 2026-10-08).
- `docs/architecture/context/issue-81.md` : note de cadrage de la 5ᵉ
  escalade, documente l'état du banc 7/10 (mesuré 2026-10-10, 3 RED :
  `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`,
  `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`,
  `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`).
- La capacité `upsert-desc` / `pin` est **absente** du helper
  `skills/gh-kanban-bridge/scripts/discord_thread.py` (grep : 0 hit).
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.

## Composants impactés (résumé)

- **Décision (cette issue)** : `pipeline/pj_decision.py` ([[pj-decision]]) +
  `pipeline/pj_notify.py` ([[pj-notify]]) + `pipeline/pj_escalate.py`
  ([[pj-escalate]]) — la boucle #5, aucun changement de code.
- **Travail débloqué (slice docs #44)** :
  - `docs/architecture/context/issue-44.md` — enrichissement de la section
    « Point à statuer & décision » (verbatim du point + options a/b/c +
    recommandation (a) + raisonnement de couverture #45).
  - `docs/architecture/README.md` (MOC) — ligne `issue-44` à ajouter.
- **Vault** : à la convergence, la slice docs #44 gagnera sa référence MOC
  et le MOC `docs/architecture/README.md` sera mis à jour par la carte
  `doc-k` de #44 — hors périmètre de cette décision.

## Non tranché (et qui doit le rester ici)

Le cadrage ne tranche **pas** :
1. **Le go humain** — seul l'humain peut débloquer `t_abd8a183` (le jeton
   `/ok` sur l'issue #79 ou le bouton Go sur le thread Discord
   `1557708797487882291`). Le cadrage documente le point à statuer, il ne le
   tranche pas.
2. **Le contenu exact de la section « Point à statuer & décision » de
   `issue-44.md`** — porté par la carte `dev-k` de #44 après le go (la spec
   #44 définit le périmètre, pas le cadrage).
3. **La forme de la PR** — portée par la carte `t6` de #44 (ouverture de la
   PR avec `Closes #44` dans le body) ; le merge est une décision humaine.

Ces points sont **documentés**, pas décidés ici.
