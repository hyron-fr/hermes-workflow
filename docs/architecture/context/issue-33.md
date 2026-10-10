---
type: context
status: draft
tags: [architecture, decision-interface, escalation, discord, github, kanban, cadrage, slice-5, description-epinglee, decision-ticket]
issues: [33]
---

# Cadrage architectural — issue #33 « slice 5/5 — convergence »

## Positionnement (cadre exact)

L'issue #33 est un **ticket de décision** (labels `decision` + `kanban`, OPEN sur
`hyron-fr/hermes-workflow`, idempotency-key `gh-issue-33`) — le **3ᵉ import** du
point à statuer de la chaîne **conv-5** du chantier **#19** (« Discord thread title
and description update ») : `#19 → #27 → #30 → … → #33` (cette issue). C'est le
miroir de #27 et de #29 (mêmes labels, même motif), ré-importé par le pont de
couverture.

**Le corps de l'issue pointe `t_f23f65af`** (board `pj-hermes-workflow`, import de
#30, **archivée le 2026-10-04** — 11 cartes-clones des issues #26/#28/#30/#31/#32
ont été archivées au 10:55 du 04/10 pour dédoublonner le défaut du cron
graphwatch). La **carte opérationnelle vivante** n'est donc **pas** la cible du
corps, mais la **`t_f725879f`** (« slice 5/5 — convergence », assignée `pj-test`,
status `blocked`, worktree partagé `t_c22a7e74`, branche
`wt/issue-19-discord-thread-title-description`).

**Le point à statuer, mesuré** (verdict conv-5 **NÉGATIF** posé par `pj-test` le
2026-10-07, HEAD `55e6659` du worktree partagé) :

1. **Banc slice 5 : 7/10 verts, 3 rouges nommés** —
   - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique` :
     `sync_description` appelle `build_description_for_card(card, log=log)` **sans**
     `issue_url_lookup` → le patch module-level du banc est ignoré →
     `thread_id=None, ok=None` au lieu de `post/ok=True`
     (`pipeline/pj_room_keeper.py`, ~L726) ;
   - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception` :
     `_gh_repo()` (`pipeline/pj_room_keeper.py` ~L652) perd l'ORG du repo
     (`rsplit("/")[-1]`) → la ligne Issue rend `…/hermes-workflow/issues/19` au
     lieu de `hyron-fr/hermes-workflow` ;
   - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick` :
     `sync_all_descriptions` ne passe pas `issue_url_lookup` à
     `build_description_for_card` → `issue_url=None` → `built=None` → 0 écriture.
2. **Helper incomplet** : `skills/gh-kanban-bridge/scripts/discord_thread.py` n'a
   **pas** les commandes `upsert-desc` ni `pin` (grep vide), pourtant le keeper les
   appelle déjà (`_discord_pin` ~L773, `upsert-desc` ~L896). Le 4ᵉ fichier du
   périmètre GREEN n'est pas livré.
3. **Branche** : HEAD local `55e6659` = 2 commits AU-DESSUS de
   `origin/wt/issue-19-discord-thread-title-description` (`03e09f1`) sans code
   GREEN ; le commit OOM `dccf75f` n'est sur **aucune** ref remote
   (`git branch -a --contains dccf75f` → local only). La DoD de dev-5 exige
   push `0 0` : non satisfait.

Le GREEN original dev-5 (`6661362`) est **perdu** (absent de tous les refs locaux,
des reflogs, des objets unreachable et du remote — vérifié en 04/10). La
re-livraison doit produire un **NOUVEAU** commit intègrant les 3 retouches nommées
ci-dessus **plus** le correctif OOM (boucle de journalisation infinie de
`build_description_for_card`, corrigé par itération sur instantané `_emit`,
mesuré OOM-kill du cgroup 4 GiB en 45 s).

**Décision demandée** : commentez l'issue #33 avec le jeton `/ok` en **premier
élément** → la carte bloquée est débloquée et repart en file ; le re-poussage du
GREEN (nouveau commit sur `wt/issue-19-discord-thread-title-description`) est porté
par **dev-5/dispatcher**, jamais par ce cadrage. Tout autre commentaire est une
demande d'éclaircissement et ne débloque rien.

Le présent cadrage **ne tranche pas** : il positionne le point à statuer dans
l'architecture existante, identifie les composants impactés, et fixe les critères
de décision. Le verdict humain (`/ok` sur l'issue) débloque la carte ; le re-push
effectif suit.

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision (commentaire `/ok` sur l'issue #33,
  idempotency-key `gh-issue-33`) et surface de preuve (commits de la branche
  `wt/issue-19-discord-thread-title-description`, remote à `03e09f1`).
- **Git / worktree partagé** — surface de livraison : le branch head de
  `wt/issue-19-discord-thread-title-description` est la **preuve de livraison** de
  la slice 5. Un commit absent du branch head est un travail non livré, quel que
  soit le handoff du worker (le handoff de `dev-5` revendiquait « 0 0 vs `@{u}`,
  arbre propre » sur un commit introuvable).
- **Kanban Hermes** — source de vérité de l'état des cartes : `t_f725879f`
  (conv-5, vivante, `blocked`) porte le point à statuer ; `t_f23f65af` (la carte
  ciblée par le corps de l'issue) est **archivée** — le corps est **obsolète** et
  doit être relu vers `t_f725879f`.
- **Discord** — le but du travail débloqué : le thread du ticket #19. Adapter :
  `skills/gh-kanban-bridge/scripts/discord_thread.py` (capacité `upsert-desc` +
  `pin` annoncée par le keeper mais **absente** du helper versionné).

### Fonctionnel (capacité traversée)

La capacité traversée est **convergence + preuve de livraison**, pas la
fonctionnalité #19 elle-même. #19 est déjà cadré par la note `issue-19` et par la
note composant `pj-thread-name` (slices 2–4 livrées) ; la slice 5 (bloc
Description épinglé) est en attente de re-livraison. Ce que #33 porte :

- **le point de décision** : la slice 5 est-elle livrée ? Mesurée : **non** —
  7/10 bancs verts, helper incomplet, branch non poussé ;
- **la chaîne de re-push** : qui repousse le NOUVEAU commit GREEN (3 retouches +
  correctif OOM) sur `wt/issue-19-discord-thread-title-description` ?
- **le verdict de convergence** : après re-push, le banc
  `tests/test_thread_description.py` passe-t-il 10/10 ?

C'est une **boucle de décision + re-livraison**, pas une évolution de
fonctionnalité. Le code de la slice 5 est décrit par le banc
`tests/test_thread_description.py` (gelé depuis le RED, 10 cas) — ce cadrage ne
le redécrit pas.

### Code (composants impactés)

- **`tests/test_thread_description.py`** (worktree partagé, commit `49bb284`) —
  le banc RED de la slice 5 : 10 cas, rejoué 7/10 verts / 3 rouges. C'est lui qui
  **verrouille le contrat** du bloc Description épinglé : `DESCRIPTION_MARKER =
  "[description]"`, `build_description_lines`, `keeper.build_description_for_card`,
  `keeper.sync_description`, `keeper.sync_all_descriptions`. Sources injectées,
  0 réseau. **Intouchable** (contrat-5) : seul le code est à retoucher, jamais le
  banc.
- **`pipeline/pj_room_keeper.py`** (worktree partagé, HEAD `55e6659`) — **porteur
  des 3 retouches nommées** :
  1. `sync_description` / `sync_all_descriptions` doivent **déduire le
     thread_id du body de la carte** (ancre `Importé depuis …/issues/N` →
     `TH-N` déterministe, 0 réseau) ; le `thread_lookup` module-level n'est appelé
     **que si** le fil n'est pas déductible du body ;
  2. `_issue_url_from_card` doit **extraire l'org depuis l'ancre** du body
     (pattern `github.com/<org>/<repo>/issues/N`) au lieu de reconstruire via
     `_gh_repo()` (dernier segment du slug) ; le fallback n'est utilisé que si
     l'ancre est absente ;
  3. `sync_all_descriptions` doit **écrire le verdict** (bloc omis + log de
     l'exception) **avant** le `continue` quand un lecteur de source lève.
  La description n'appartient pas au core pur d'`engine.py` : c'est une lecture
  d'état (gh/git) résolue hors du core, puis injectée.
- **`pipeline/engine.py`** (worktree partagé) — formateur pur du titre (`format_title`,
  slice 3 livrée) ; la slice 5 **n'y change rien** (`build_description_lines` y
  est déjà portée par le GREEN partial `55e6659` — le GREEN partial vit dans ce
  commit). Non impacté par les 3 retouches.
- **`pipeline/pj_decision.py`** (dev, commit `8e35b6e`) — core pur de décision
  `/ok` : le jeton vaut **en tête du corps ou immédiatement après UNE amorce**
  (`TOKEN_PREFIX_MAX = 1`, `_token_index`). C'est ce fix (faux négatif mesuré
  2026-10-06 : « rattaché /ok » ignoré en silence, carte restée bloquée) qui rend
  le `/ok` de l'issue #33 **opérationnel** — même si l'humain le commente après une
  amorce. Banc `tests/test_decision_humaine.py` : **34 passed** mesuré sur le
  branch du worktree #33.
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** — helper Discord (adapter
  REST) : `create` / `send` / `rename` / `threads` / `delete`. **Aucune** capacité
  `upsert-desc` ni `pin` : la slice 5 l'étend (4ᵉ fichier du périmètre GREEN, à
  ajouter par dev-5 au re-push).
- **`bridge/pj_room_keeper.py`** + **`agents/pj-master/scripts/pj_room_keeper.py`**
  — miroirs/copies du keeper. La slice 5 les touche aussi (l'écriture de la
  description y est portée). Toute divergence `pipeline/` ↔ `~/.hermes/scripts/`
  doit être **déclarée** (D1 vivante : `pj_escalate.py` live ≠ versionné).

## Lecture SDD (spec-driven)

La spec de #33 est le **point à statuer** : le commit GREEN de la slice 5 est
perdu / incomplet, 3 bancs rouges nommés, helper incomplet, branch non poussé. Le
livrable de #33 n'est **pas** un code, mais **l'état de convergence de la slice 5
de #19** : soit le NOUVEAU commit GREEN est repoussé et le banc passe 10/10, soit
l'escalade se poursuit. La doc décrit ce qui existe aujourd'hui (le GREEN partial
`55e6659`, les 3 retouches nommées, le worktree de re-push) — pas une intention.

## Lecture DDD (bounded contexts, agrégats, événements)

- **Bounded context** : *convergence / livraison* — chevauche *développement*
  (slice 5 de #19) et *décision humaine* (l'escalade #27/#30/#33), sans en être
  un nouveau : c'est la **jonction** entre les deux.
- **Agrégat racine** : la **carte `t_f725879f` (conv-5)** — invariant : elle ne
  repart en `ready` que sur un `/ok` humain portant son `id` exact (le
  commentaire sur l'issue #33). L'**issue #33** est l'objet de décision qui
  matérialise la carte.
- **Value objects** : le **branch head SHA** (`55e6659` local / `03e09f1`
  remote, mesurés) ; le **commit SHA** du GREEN à produire ; l'**idempotency-key**
  `gh-issue-33` ; le **verdict conv-5** (7/10 bancs, 3 retouches nommées).
- **Domain events** : `/ok` humain sur l'issue #33 → unblock de
  `t_f725879f` → re-push du NOUVEAU commit GREEN (3 retouches + correctif OOM) par
  `dev-5`/`dispatcher` sur `wt/issue-19-discord-thread-title-description` →
  convergence GREEN (banc 10/10) → doc → doc-review → PR (t6) → merge.

## Lecture TDD (contrats testables)

Le contrat testable de #33 n'est pas un code, mais **un invariant mesurable** :

- **Le branch head de `wt/issue-19-discord-thread-title-description` contient le
  NOUVEAU commit GREEN** — vérifiable par `git cat-file -t <sha>` dans le dépôt
  principal et par `git log --oneline` sur la branche (le `0 0` du
  `git rev-list --left-right --count HEAD...@{u}` est la preuve de push).
- **Le banc `tests/test_thread_description.py` passe 10/10 GREEN** — rejouable
  sans Discord ni réseau (sources injectées) ; les 3 rouges nommés sont les
  critères d'acceptation directs de la retouche.
- **Les 3 retouches de `pj_room_keeper.py`** sont les **contrats TDD** de la
  slice 5 : chaque cas rouge du banc correspond à une retouche nommée
  (déduction du thread_id du body, extraction de l'org de l'ancre, écriture du
  verdict avant le `continue`) — le banc **gèle** le contrat, le code doit
  converger vers lui.

Ces invariants sont mesurables par `pj_graphwatch` (couverture commit-à-commit +
chemin réel du worktree, cf. commits `009f0a7`, `9e49771`, `318bea1` de l'issue
#2) et par le pont de couverture (`pj_coverage_gate`) qui a identifié #33 comme
recouvrant #19 et #27.

## Lecture hexagonale (le core reste pur)

Le core pur de la slice 5 est `build_description_lines` (fonction pure :
issue_url, branch, pr_url → list[str], 0 réseau, 0 horloge, 0 aléa). L'écriture
du message épinglé et de l'épingle passe par le helper `discord_thread.py`
(adapter REST, hors core). Le contrat d'interface (marqueur `[description]`,
`build_description_for_card`, `sync_description`, `sync_all_descriptions`) est
testable sans Discord : les sources et l'adaptateur sont injectés.

La frontière à respecter : **la description est une lecture d'état** (gh/git/
blackboard) résolue **hors** du core, puis injectée dans le formateur pur. Jamais
l'inverse : le formateur ne lit pas le réseau. Les 3 retouches nommées renforcent
cette frontière : la déduction du thread_id et de l'org **du body de la carte**
(cote 0 réseau) remplace les appels module-level `thread_lookup()` et
`_gh_repo()` qui contournaient l'injection.

## Composants impactés par l'issue #33

| composant | impact | slice #19 |
|---|---|---|
| `tests/test_thread_description.py` | banc gelé (livré, `26bad5d` + `49bb284`), 7/10 verts / 3 rouges | 5 |
| `pipeline/pj_room_keeper.py` | **3 retouches nommées** (non livrées, HEAD `55e6659`) | 5 |
| `pipeline/engine.py` | formateur pur du titre (livré, slices 3–4) ; `build_description_lines` dans le GREEN partial | 3–4, 5 |
| `pipeline/pj_decision.py` | core pur `/ok` (livré, `8e35b6e` sur le branch #33) : amorce acceptée | post-#5 |
| `skills/gh-kanban-bridge/scripts/discord_thread.py` | capacités `upsert-desc` + `pin` à ajouter (**non livrées**) | 5 |
| `bridge/pj_room_keeper.py` + `agents/pj-master/scripts/pj_room_keeper.py` | miroirs du keeper (**non livrés**) | 5 |

## Hors-scope

- **Le re-push du NOUVEAU commit GREEN** : porté par `dev-5`/`dispatcher` sur le
  worktree partagé `t_c22a7e74` (`wt/issue-19-discord-thread-title-description`),
  **jamais** par ce cadrage.
- **La convergence effective de la slice 5** : portée par la carte
  `t_f725879f` après le `/ok` humain.
- **Les slices 1–4 de #19** : déjà livrées, cadrées par la note `issue-19` (worktree
  t_c22a7e74) et la note composant `pj-thread-name` (slice 4).
- **Le fix `8e35b6e` (jeton `/ok` après amorce)** : déjà livré sur
  `fix/decision-jeton-apres-amorce` / `wt/t_e1e48e52`, en attente de merge vers
  `dev` — il précède l'issue #33 et n'est pas son livrable.
- **La duplication bridge↔pipeline↔agents des `pj_*.py`** : divergence connue, non
  traitée par #33.
- **Le verdict de convergence** : porté par `pj-test` sur la carte
  `t_f725879f`, pas par ce cadrage.

## Frontières traversées (résumé)

```
issue #33 (GitHub, label decision + kanban)
  → commentaire /ok humain (surface de décision, pj_decision.py : tête ou 1 amorce)
  → unblock de t_f725879f (kanban)
  → re-push du NOUVEAU commit GREEN sur wt/issue-19-discord-thread-title-description (git)
  → banc test_thread_description.py 10/10 GREEN (preuve de livraison)
  → convergence GREEN → doc → doc-review → PR (t6) → merge
```

Deux frontières : **GitHub ↔ kanban** (décision → effet) et **git ↔ worktree
partagé** (preuve de livraison). Le point de fragilité n'est pas l'appel réseau
mais **la couverture commit-à-commit** : un commit absent du branch head est un
travail non livré, quel que soit le handoff du worker. Le second point de
fragilité est **l'obsolétence du corps** : l'issue #33 pointe `t_f23f65af`
(archivée), mais la carte vivante est `t_f725879f` — le re-miroir doit relire la
cible.

## État mesuré (2026-10-10)

- `origin/dev` = `2027333` (docs cadrage issue-29).
- **Branch du worktree #33** : `wt/t_e1e48e52` @ `8e35b6e` (1 commit au-dessus de
  `origin/dev` : `fix(decision): le jeton /ok vaut aussi après UNE amorce` — le
  fix du faux négatif de décision qui a précédé l'issue #33 ; **non mergé** dans
  `dev`).
- **Worktree partagé** `t_c22a7e74` (`wt/issue-19-discord-thread-title-description`) :
  - **local** = `55e6659` (2 commits au-dessus du remote : `dccf75f` fix OOM +
    `55e6659` baseline conv-audit) ;
  - **remote** = `03e09f1` (docs issue-31, **aucun code GREEN**).
- **Banc `tests/test_thread_description.py`** : **7 passed / 3 failed** (mesuré
  2026-10-07, verdict conv-5 NÉGATIF). Les 3 rouges nommés sont les critères de
  la retouche.
- **`pipeline/pj_decision.py`** (sur le branch #33) : `TOKEN_PREFIX_MAX = 1`,
  `_token_index` livré ; banc `tests/test_decision_humaine.py` = **34 passed**.
- **Helper `discord_thread.py`** : **pas** de `upsert-desc` / `pin` (grep vide) —
  capacité non livrée.
- `pj_docs_lint.py` sur `/home/elix/pj-repos/hermes-workflow` → `exit=0`.
