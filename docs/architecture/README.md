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
- [[issue-2]] — Rewrite in english (documentation-wide translation).
- [[issue-2-datation]] — Dating rule for state benches: the anchoring key and INDÉTERMINÉ.
- [[issue-19]] — Discord thread title and description update (titre + description du thread selon l'état de l'issue).
- [[issue-31]] — point de décision : le commit GREEN de la slice 5 de #19 (bloc Description épinglé) est absent du worktree partagé — intégrité de l'histoire de branche, verdict de convergence bloqué.
- [[issue-45]] — 4ᵉ escalade conv-5 : RECYCLE du GREEN perdu (slice 5/5 #19), ticket de décision sur la carte `t_7aaf3d49` ; périmètre gelé (banc 10/10 RED, helper sans `upsert-desc`/`pin`), re-poussage du GREEN en attente du `/ok`.

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
- [[pj-thread-name]] — le nom du thread Discord comme value object (issue #19) : les deux formats acceptés (`<icône> <repo>|#<n>|<titre>` et l'ancien par lecteur), les 3 lecteurs (`thread_index`, `THREAD_NAME_RE`, `resolve_thread`), le formateur pur et la table des 4 états, et depuis la slice 4 le keeper comme écrivain unique du titre (coalescence par fenêtre de 600 s, best-effort, priorité ⚠ > 🛑 > ⚙️ > 🎬) et la règle de non-régression.
