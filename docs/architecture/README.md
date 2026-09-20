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

## Composants

- [[pj-decision]] — Core pur de décision `/ok` (issue #5, slice 4) : calcule la décision portée par un commentaire, ne l'applique jamais.
- [[pj-bridge-coverage-gate]] — Gate de couverture du pont (issue #5, slice 2) : exemption du parent par soustraction, label `decision`, ancre des graphes, trappe honnête `pj-import`.
- [[pj-bridge-push-ancre]] — Ancre de `issue_number_of()` (issue #5, slice 3) : la carte `done` ferme l'issue de sa ligne de protocole `Importé depuis <url>`, jamais une autre citée dans le corps.
