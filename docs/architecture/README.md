---
type: moc
status: draft
tags: [architecture, moc]
---

# Architecture — MOC

Map of Content du vault `docs/architecture/`. Chaque note de cadrage
(`context/`) et chaque composant documenté doit être référencé ici pour ne pas
être signalé orphelin par `pj_docs_lint.py`.

## Contextes d'issue (cadrage)

- [[issue-1]] — Vérifier le cycle complet du pipeline (issue de test du framework).
- [[issue-1-verification-contract]] — Contrat de vérification de #1 (protocole C1..C6, provenance des 4 maillons, verdict de convergence).
- [[issue-5]] — Interface de décision humaine pour les cartes bloquées (Discord + GitHub uniquement).
- [[issue-4]] — Versionner pj_escalate.py (pipeline/) : garde-fou d'état d'issue + résolution de binaire hors PATH.
- [[issue-7]] — bridge/mermaid.min.js ne parse pas (littéral numérique substitué par un placeholder de sanitisation).
- [[issue-27]] — « slice 5/5 — convergence » : issue de décision (escalade de la carte conv-5 `t_f725879f` du chantier #19), GREEN dev-5 perdu, banc 10/10 RED ; `/ok` débloque, le re-poussage du GREEN suit.
- [[issue-29]] — « slice 5/5 — convergence » : miroir de décision de #27 (même carte conv-5 `t_f725879f` du chantier #19, GREEN dev-5 perdu) ; cadrage de convergence/preuve de livraison par couverture commit-à-commit.
- [[issue-41]] — « t3 grill-me » : 4ᵉ escalade conv-5 (carte `t_3f7e0be4`), GREEN original `6661362` définitivement absent, GREEN partial présent (banc 8/10, 2 fixes keeper + `upsert-desc`/`pin` restants) ; verdict grill-me `PROTOTYPE: non`, `/ok` débloque la carte.
- [[issue-2]] — Rewrite in english (documentation-wide translation).
- [[issue-2-datation]] — Dating rule for state benches: the anchoring key and INDÉTERMINÉ.
- [[issue-19]] — Discord thread title and description update (titre + description du thread selon l'état de l'issue).

## Décisions (ADR)

- [[ADR-0001-identite-asset-et-preuve-sans-oracle-externe]] — l'identité d'un asset vendu se prouve par un invariant dérivable, jamais par un chemin, un `cmp` ni un hash d'artefact externe (issue #7).

_(peuplé par la carte `doc-k` : chaque ADR sous `decisions/` doit être référencé ici, sinon `pj_docs_lint.py` le signale orphelin.)_

## Règles

- [[declared-delta-rule]] — What the seal guard protects: the declared-delta rule (5 testable points).

## Composants

- [[pj-decision]] — Core pur de décision `/ok` (issue #5, slice 4) : calcule la décision portée par un commentaire, ne l'applique jamais.
- [[pj-bridge-coverage-gate]] — Gate de couverture du pont (issue #5, slice 2 + 2b) : exemption du parent par soustraction, label `decision`, ancre des graphes, trappe `pj-import` assurée avant d'être proposée.
- [[pj-bridge-push-ancre]] — Ancre de `issue_number_of()` (issue #5, slice 3) : la carte `done` ferme l'issue de sa ligne de protocole `Importé depuis <url>`, jamais une autre citée dans le corps.
- [[pj-notify]] — Émetteur des DEUX notifications d'une décision `/ok` (issue #5, slice 5) : l'enfant notifiée puis fermée, le parent notifié jamais fermé ; dédup par décision (jamais par horloge), non-blocant et jamais silencieux.
- [[pj-escalate]] — Escalade déterministe des cartes bloquées vers Discord (contrat de variables d'environnement requises/optionnelles, règle « requise absente = refus bruyant », garde d'état d'issue : quatre chemins de doute, quatre avertissements distincts ; chaîne de publication `pj_publish.py` : identité sur le contenu tel qu'il s'exécute, contrôle des exports par motif, 5 étapes du geste dans l'ordre, codes de sortie `2 > 1 > 0`).
- [[pj-lang-lint]] — deterministic language gate for the English corpus (issue #2, slice 2).
- [[pj-thread-name]] — Le nom du thread Discord comme value object (issue #19, slices 2–4) : les deux formats acceptés, le formateur pur, la table des 4 états, les trois lecteurs, l'écrivain unique (keeper) et la coalescence par fenêtre de 600 s. (note livrée sur `wt/issue-19-discord-thread-title-description`, en attente de merge de la PR de #19.)
