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
- [[issue-7]] — bridge/mermaid.min.js ne parse pas (littéral numérique substitué par un placeholder de sanitisation).

## Décisions (ADR)

- [[ADR-0001-identite-asset-et-preuve-sans-oracle-externe]] — l'identité d'un asset vendu se prouve par un invariant dérivable, jamais par un chemin, un `cmp` ni un hash d'artefact externe (issue #7).

## Composants

_(à compléter par les cartes `doc-k` au fil des slices livrées.)_
