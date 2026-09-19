---
type: context
status: draft
tags: [architecture, verification-contract, pipeline, issue-smoke-test]
issues: [1]
---

# Contrat de vérification — issue #1 « Vérifier le cycle complet du pipeline »

> Note de vault produite par `doc-1` (slice 1/1). Elle décrit le **livré** — le
> comportement **prouvé** par le protocole de `test-1`, le relevé de `dev-1` et le
> verdict de `conv-1` — jamais une intention. Le cadrage positionne l'issue
> ([[issue-1]]) ; cette note fige ce que #1 a **réellement vérifié**.

## Le fait central que le cadrage ne dit pas

Les quatre maillons vérifiés sont les **copies exécutées** (profil `pj-master` +
clone `hermes-experiment`), **pas le dépôt**. Mesuré, trois des quatre copies
exécutées divergent de leurs copies versionnées (`pipeline/`) ; une seule — le pont —
est identique des deux côtés.

Une vérification qui ne le dit pas laisse croire que le dépôt a été validé. Le dépôt
**n'a pas** été validé : ce sont les binaires que le cron lance réellement qui ont été
mesurés. C'est le résultat le plus important du test.

## Provenance des 4 maillons (digests mesurés)

Chemin exécuté lu **dans le wrapper cron** (`exec python3 <chemin>`), pas déduit de la
présence d'un fichier dans le dépôt. Digests complets (`md5sum`), égaux à ceux du relevé
`dev-1` (`t_1a93a62f`) :

| maillon | copie exécutée | md5 exécuté | md5 versionné (`pipeline/`) | verdict |
|---|---|---|---|---|
| pont | `/home/elix/hermes-experiment/bridge/gh_kanban_bridge.py` | `50b6c3e1a0cfc5f090e9afca3ffdce2a` | `50b6c3e1a0cfc5f090e9afca3ffdce2a` | **identique** |
| déployeur | `~/.hermes/profiles/pj-master/scripts/pj_pipeline_deployer.py` | `0396c5a36b62fdaae351762cc5e578f6` | `414f5749fd14dead6aaaa1e3d392e4ff` | **divergent** |
| graphwatch | `~/.hermes/profiles/pj-master/scripts/pj_graphwatch.py` | `55b801905188dcc159fa99e8fb800ebf` | `69fcbbe238686cf12cb6ae22fec93b0d` | **divergent** |
| room-keeper | `~/.hermes/profiles/pj-master/scripts/pj_room_keeper.py` | `2fc7b0486256615bb0b722262b807cff` | `8f8429771c01767e8a843daf12a6cd2f` | **divergent** |

La divergence n'est **jamais** qualifiée « en retard » ni « en avance » : la copie
versionnée n'est pas une version antérieure, c'est un **objet non exécutable sur ce
projet** (`ANCHOR_ROOT` code `${HOME}/pj-repos` littéral pour le déployeur et graphwatch,
`ANCHORS` d'un autre projet pour le déployeur). **Deux objets, pas deux versions du
même.** La direction de la divergence change d'un artefact à l'autre : énoncer « la
dérive » au singulier serait faux pour au moins une ligne.

## Le protocole de contrôle (C1..C6)

Chaque contrôle a été exécuté **avec son contrôle négatif** — un contrôle qui ne peut
pas échouer ne compte pas. Verdicts re-mesurés par `conv-1` (`t_3e2a0a8f`) sur l'état
réel, jamais relayés depuis une carte :

| # | contrôle | statut | mesure |
|---|---|---|---|
| C1 | le pont a importé | **satisfait** | 1 carte (`t_951b01aa`) porte l'URL d'import de #1 ; 2 négatifs corps-pur → `None` |
| C2 | le déployeur a construit t1..t5+t3b | **satisfait** | 6/6 cartes de phase parents de la racine (t1,t2,t3,t3b,t4,t5) ; CLI et base concordent |
| C3 | worktree partagé, branche unique | **satisfait** | positif OK sur le chemin réel ; `WorktreeConflict` sur chemin tiers ET sur `worktree_path` retiré |
| C4 | graphe de dev topologiquement correct | **satisfait** | `build_plan_checked` rc=0, 9 cartes, plan identique à `task_links` ; 5 négatifs `ValueError` |
| C5 | room du ticket animée | **NON ÉTABLI** | room #1 dans `hosted_room_retired_ids` : état définitif non reproductible ; aucun négatif exécuté ne fait échouer le contrôle |
| C6 | les linters refusent une spec invalide | **satisfait** | `validate(slices.json)` = `ok=True` ; 4 négatifs ; exit codes 0/1/2 mesurés dans les deux directions |

**C5 n'est ni vert ni rouge** : la room #1 a été dissoute et son id définitivement
retiré, donc l'état n'est pas reproductible. C'est un résultat documenté, pas un échec.

## Ce que ces contrôles SONT, et ce qu'ils ne sont pas

Ils **rejouent**, ils ne **déclenchent** rien : aucun cron ne les exécute, et **aucun
test versionné ne les épingle** (mesuré : `check_topology` / `preflight_worktree` /
`build_plan_checked` → 0 hit dans `tests/`). Le verdict **autorise la PR**, il ne
**protège pas** la branche. Aucune note de vault ne peut donc dire que le comportement
de cette branche est verrouillé par ces contrôles.

## Le diff de la PR est un vault, pas du code

Le diff de la branche vs `origin/dev` est limité à **deux fichiers sous `docs/`**
(`docs/architecture/README.md`, `docs/architecture/context/issue-1.md`, plus cette note) :
**aucun fichier exécutable**. L'AC de couverture > 80 % est **vacuous** sur ce diff
(0 fichier retenu par `is_code_file`, `EXCLUDE_PARTS` contient `docs/`) — elle ne peut
pas servir de preuve, et elle a été retirée de la spec.

## Ce qui n'a PAS été établi (et doit rester non tranché)

- **C5 — rejouabilité** : room #1 retirée, `ensure` impossible.
- **C4 — la boucle `t6 → racine → t6`** est acceptée par `check_topology` dans la forme
  auto-cohérente (mesuré : `OK`) ; le board refuse-t-il lui-même ce lien = **NON MESURÉ**.
- **C1 — horodatage de l'import** : le marqueur est un état persisté, pas un événement daté.
- **C6 — aucun consommateur automatique** des linters (aucun cron ne les cite).
- **Aucun consommateur du blackboard** n'est câblé en production.

## La dérive versionné ↔ exécuté n'est PAS une décision d'architecture

Elle est un **fait mesuré à documenter**, pas une décision à trancher. L'humain a
explicitement différé le « où/quand corriger » (Q2 = 2c) : **rien n'est corrigé dans
#1**, et aucun ADR ne légifère ici sur « quelle copie est canonique ». Ce sujet appartient
à l'issue de resynchronisation, quand l'humain l'ouvrira.
