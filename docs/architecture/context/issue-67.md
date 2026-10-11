---
type: context
status: draft
tags: [architecture, decision, escalation, convergence, discord, delivery-proof, cadrage]
issues: [67]
---

# Cadrage architectural — issue #67 « t1 worktree »

Mesuré le 2026-10-11, refs citées : `origin/dev @ 2027333`,
`wt/t_b84a4a2e @ 7091678`, `origin/wt/issue-19-discord-thread-title-description @ 9fcd207`.

## Positionnement (cadre exact)

L'issue **#67** est un **ticket de DÉCISION** (labels `decision` + `kanban`,
OPEN, parent GitHub `#29`, sub-issue GitHub `#94`) créé par le
**couverture-gate** (`<!-- pj-coverage-gate -->`, 08/10 11:20) : « Import
suspendu — cette issue recouvre du travail en vol : #29 (PR ouverte / graphe
déjà construit) ». C'est le **6ᵉ import du même point à statuer conv-5**
(chaîne : #19 → #27 → #29 → #30 → #31 → #37 → #40 → #41 → #44 → #45 → #67),
sur la même carte bloquée.

Le **point à statuer** (tel que posé par le corps de l'issue, vérifié en
direct) : la carte **`t_2678f842`** (board `pj-hermes-workflow`, titre
« t1 worktree », assignée `pj-master`, worktree
`.worktrees/t_2678f842`, branche `wt/t_2678f842 @ 009f0a7` = `origin/dev`
avant le cadrage de #29) est en **`blocked`/`gave_up`** depuis le
2026-10-03 : run 293 crashed (« Provider temporarily unavailable », 18:40),
puis `gave_up` (failures 1/1, retry_status `ready`). Les 34 events sont des
heartbeats jusqu'au crash — **0 commentaire humain** sur la carte, et
**0 commentaire de travail** : le body « Créer le worktree de l'issue #29,
base dev, et poster chemin+branche en commentaire » n'a jamais été exécuté.
Les enfants `t_21efb666` (archived) et `t_58c956c8` (todo) sont gelés avec
elle.

**Décision demandée** : commenter l'issue #67 (ou la carte) avec le jeton
`/ok` en premier élément → la carte est débloquée et repart en file. Tout
autre commentaire est une demande d'éclaircissement et ne débloque rien.

Ce cadrage **ne tranche pas** : il positionne le point à statuer dans
l'architecture existante et fixe les critères de décision. Le verdict humain
(`/ok`) débloque `t_2678f842` ; le re-livrage du GREEN slice 5 suit sur le
chantier #19 (voir « Croisement »).

## Croisement infrastructure / fonctionnel / code

### Infrastructure (frontières traversées)

- **GitHub** — surface de décision : commentaire `/ok` sur l'issue #67.
  Mesuré 2026-10-11 : **0 commentaire humain**, 0 `/ok` sur #67 ; les 2
  commentaires existants sont le gate de couverture (11:20) et l'annonce
  d'import kanban (19:21 → carte `t_4c130f6e`). Le `/ok` posé ailleurs
  n'a pas d'effet direct ici (mesuré : `#27: jb-priez /ok` présent,
  `#29/#30/#31/#37/#40/#44/#45: none`).
- **Kanban Hermes** — source de vérité de l'état des cartes. État mesuré :
  - `t_2678f842` : `blocked`/`gave_up`, blocage depuis le 03/10, 0
    commentaire, enfants `t_21efb666` (archived) / `t_58c956c8` (todo).
  - `t_7aaf3d49` (carte RECYCLE, pj-dev) : **archivée** le 08/10 après
    2 crashes (run 326/327) ; son dernier `blocked` (08/10 12:12,
    `needs_input`) demandait `/ok` sur **#45**.
  - `t_f725879f` (conv-5, pj-test, chantier #19) : **`blocked`**,
    diagnostic `critical` : « Agent crashed 10x » — la convergence du
    chantier #19 reste **suspendue** en aval.
- **Git / worktree partagé** — surface de livraison du GREEN. Mesuré
  2026-10-11 sur l'anchor `/home/elix/pj-repos/hermes-workflow` :
  - commit GREEN original **`6661362`** : `git cat-file -t` →
    `fatal: Not a valid object name` ; absent de `rev-list --all` →
    **définitivement perdu** (constat réaffirmé depuis le 04/10).
  - `origin/wt/issue-19-discord-thread-title-description` (worktree
    partagé `t_c22a7e74`) pointe à `9fcd207` (cadrages docs #73/#74/#75
    /#80 uniquement) et **porte le GREEN partial** : commit `55e6659`
    « conv-audit: baseline état courant worktree (GREEN partial, banc
    7/10) » (35 insertions dans `pipeline/engine.py`) est ancêtre de la
    branche (`git merge-base --is-ancestor` = oui).
  - Les marqueurs GREEN slice 5 sont **préents** sur cette branche :
    `sync_all_descriptions` (keeper L799), helper `pin` (L776) et
    `upsert-desc` (L896) dans `pipeline/pj_room_keeper.py`.

### Fonctionnel (capacité traversée)

La capacité traversée est **déblocage d'une carte technique + convergence
du chantier #19**, pas une évolution de fonctionnalité :

1. **Déblocage de `t_2678f842`** : carte t1 « worktree de l'issue #29 »
   jamais exécutée (crash provider avant action). Son déblocage relance
   les enfants gelés (`t_58c956c8` t4 draft spec du graphe #29) et
   débloque `#67` via le pont (`gh-issue-67`).
2. **Convergence de la slice 5 du chantier #19** (« Discord thread title
   and description update ») : le point de fond du point à statuer. Le
   GREEN original est perdu ; le GREEN partial existe ; le banc gelé
   `tests/test_thread_description.py` (10 cas, **intouchable**) mesure
   l'écart.

Le re-livrage du GREEN **n'appartient pas** à ce graphe (#67) : il est
porté par le chantier #19 (RECYCLE), et la chaîne d'escalade conv-5
n'empêche pas le re-GREEN de suivre la branche
`wt/issue-19-discord-thread-title-description`.

### Code (composants impactés / état mesuré)

- **`tests/test_thread_description.py`** (worktree partagé `t_c22a7e74`)
  — banc gelé de la slice 5, 10 cas (mesuré : `grep -c 'def test'` = 10).
  Rejoué le 2026-10-11 avec l'env venv hermes-agent : **7 passed / 3
  failed** (était 10/10 RED sur l'ancienne base ; les 7 GREEN partial ont
  fait progresser le banc) :
  - `test_nominal_un_seul_message_epingle_mis_a_jour_pas_duplique`
  - `test_erreur_gh_pr_list_en_erreur_ligne_omise_tracee_pas_exception`
  - `test_erreur_le_reader_de_source_qui_leve_ne_tue_pas_le_tick`
  → 3 retouches keeper attendues avant convergence.
- **`pipeline/pj_room_keeper.py`** — porteur de l'écriture de description
  (GREEN partial) : `sync_all_descriptions` (L799), `pin` (L776),
  `upsert-desc` (L896) ; coalescence titre `TITLE_WINDOW = 600` (slice 4,
  livrée).
- **`pipeline/engine.py`** — formateur pur du titre (slice 3) + 35
  insertions du GREEN partial (`55e6659`).
- **`skills/gh-kanban-bridge/scripts/discord_thread.py`** — helper
  Discord (adapter REST) : capacités `upsert-desc` / `pin` (slice 5).
- **`pipeline/pj_decision.py`** — cœur pur de décision `/ok`. État
  mesuré : le fix « jeton après une amorce » (`8e35b6e`, branch
  `fix/decision-jeton-apres-amorce`) est **absent de `origin/dev`**
  (`git merge-base --is-ancestor` = non) — la copie versionnée de `dev`
  ignore encore un `/ok` précédé d'une amorce ; la copie live
  `~/.hermes/scripts/pj_escalate.py` (sha256 `1f275887…`) porte en plus
  `gave_up`/`crashed` dans `BLOCK_EVENT_KINDS` (drift live↔versionné,
  déclarée, hors périmètre ici).

## Lecture SDD (spec-driven)

La spec de #67 est le corps de l'issue : un **point à statuer** posé par
le coverage-gate. Le livrable n'est **pas du code**, mais :
- le **verdict humain** (jeton `/ok`) qui débloque `t_2678f842` ;
- la **consistance de la doc** : cette note positionne le point à statuer
  sans réécrire le chantier #19 (déjà cadré par `issue-19` +
  `issue-29`/`issue-27`, et par le composant `pj-thread-name`).

La source de vérité est l'état mesuré ci-dessus (refs + banc + kanban),
jamais un résumé de thread.

## Lecture DDD (agrégats / entités / value objects / domain events)

- **Agrégat `Carte` (kanban)** : `t_2678f842` en état `gave_up` — un état
  terminal technique qui **n'est pas** un point de décision ; le
  coverage-gate l'a néanmoins transformé en issue de décision (c'est ce
  que #67 porte). Les enfants (`t_21efb666` archived, `t_58c956c8` todo)
  restent attachés à l'agrégat parent.
- **Agrégat `Issue` (GitHub)** : #67 est une entité de décision
  (labels `decision`+`kanban`) ; son identity est la
  `idempotency-key gh-issue-67` sur la carte racine `t_4c130f6e`.
- **Value object `Jeton /ok`** : sa position (tête de commentaire) est de
  la présentation, pas de la décision (fix `8e35b6e`, non encore sur
  `dev`) ; un jeton cité (« est-ce que /ok est le bon jeton ? ») ne
  décide rien — borne de la grammaire.
- **Domain event `Escalade`** : chaque crash/`gave_up` d'une carte du
  chantier #19 ré-émet un event `Escalade` → import kanban → nouvelle
  issue. La **non-idempotence sur le fond** du point à statuer (même
  carte, même motif) est la cause du cycle #67 ; c'est l'observation qui
  alimente la décision humaine, pas un défaut du pipeline à corriger ici.

## Lecture TDD (contrats testables)

Le périmètre de #67 est **décisionnel** : pas de nouveau contrat à
tester dans ce graphe. Les contrats concernés existent et sont déjà
verrouillés :

- `tests/test_thread_description.py` (10 cas, gelé, intouchable) —
  verrouille le contrat slice 5 (`build_description_for_card`,
  `sync_description`, `sync_all_descriptions`, capacités `pin`/
  `upsert-desc`). Rejoué 2026-10-11 : **7/10 GREEN, 3 RED** — les 3
  cas listés en « Code (composants impactés) » sont le périmètre de
  re-GREEN du chantier #19, hors périmètre de #67.
- `tests/test_decision_humaine.py` (34 cas, fix `8e35b6e`) — verrouille
  le contrat `/ok` après amorce (4 « porte le jeton » / 4 « le cite » /
  1 grammaire refusée) ; **hors `dev`** tant que `fix/decision-jeton-apres-amorce`
  n'est pas mergée — à signaler, pas à corriger ici.

## Lecture hexagonale (core pur / dépendances d'infrastructure)

Aucune frontière de dépendance n'est traversée par le livrable de #67 :
la décision `/ok` reste dans le **core pur** de décision
(`pipeline/pj_decision.py`, valeur pure, 0 réseau, 0 DOM) ; le
déblocage de `t_2678f842` est un effet de bord **port** kanban
(exécution humaine), pas du code. Le re-GREEN slice 5 (chantier #19)
conserve la frontière mesurée : `engine.py` (formateur pur, injecté) ↔
`pj_room_keeper.py` (tick, lecture d'état gh/git, écriture Discord via
helper `discord_thread.py` — adapter REST), aucune dépendance du core
vers l'infrastructure.

## Critères de décision (pour le verdict humain)

- **`/ok` sur #67** → `t_2678f842` débloquée → enfants gelés
  relancés → `#67` fermée par le pont ; le chantier #19 reste suspendu
  sur `t_f725879f` (conv-5) jusqu'au re-GREEN (3 retouches keeper).
- **Question de fond à qualifier au déblocage** (constat t2, mesuré) :
  le 6ᵉ import du même point à statuer montre que le pipeline
  d'escalade se réjoue mécaniquement à chaque crash. La question n'est
  pas « /ok ou pas » mais **le sort de la chaîne conv-5** : re-GREEN via
  re-spawn de RECYCLE (`t_7aaf3d49` archivée) vs recyclage définitif
  (clôture du chantier #19). Ce choix est celui de l'humain, pas du
  cadrage.
- **Hors périmètre** (mesuré, non actionné ici) : le fix `8e35b6e`
  (`/ok` après amorce) absent de `dev` ; le drift live↔versionné de
  `pj_escalate.py` (`BLOCK_EVENT_KINDS` élargi en live, déclarée dans
  la note `issue-29`).

## Composants impactés (liste fermée)

| Composant | Rôle dans #67 | État mesuré |
|---|---|---|
| `pipeline/pj_decision.py` | Évalue le jeton `/ok` de #67 | versionné (fix amorce absent de `dev`) |
| `pipeline/pj_coverage_gate.py` | A produit l'issue #67 (`pj-coverage-gate`) | versionné |
| Kanban `t_2678f842` | Carte au point à statuer | `blocked`/`gave_up`, 0 commentaire |
| `tests/test_thread_description.py` | Mesure la convergence slice 5 (fond) | 7/10 GREEN mesuré 2026-10-11 |
| `pipeline/pj_room_keeper.py` | Porteur GREEN partial (pin/upsert-desc) | sur `wt/issue-19-…` (`55e6659`) |

Aucun autre composant n'est impacté par le livrable de #67 ; le re-GREEN
est porté par le chantier #19 (voir `issue-29`, `issue-19`).

## Preuves (rejouables)

```bash
# issue et jetons
gh api repos/hyron-fr/hermes-workflow/issues/67 --jq '{number,state,title}'
gh api .../issues/67/comments --jq '[.[]|select(.body|test("/ok"))]|length'   # 0
# perte du GREEN
git cat-file -t 6661362   # fatal: Not a valid object name
# GREEN partial sur la branche du chantier
git merge-base --is-ancestor 55e6659 origin/wt/issue-19-discord-thread-title-description
# banc gelé
cd .worktrees/t_c22a7e74 && /home/elix/.hermes/hermes-agent/venv/bin/python -m pytest tests/test_thread_description.py -q -p no:randomly   # 7 passed, 3 failed
# fix /ok hors dev
git merge-base --is-ancestor 8e35b6e origin/dev   # non
```
