# hermes-workflow

Pipeline **issue GitHub → PR** piloté par des agents Hermes : pont GitHub↔kanban,
spécialisation des profils, portes humaines, et graphe de développement construit
mécaniquement.

Ce dépôt est la **référence versionnée** du projet. Il contient les agents, le
workflow, les skills et les outils déterministes — **sans aucun secret**.

---

## Le problème résolu

Un dépôt GitHub a des issues ; un pipeline multi-agents a besoin d'un état durable,
de portes humaines et d'une traçabilité. Ce projet relie les deux :

```
issue GitHub
  └─ pont (import, label miroir)          ← 0 LLM
       └─ graphe kanban t1..t5            ← 0 LLM (deployeur)
            ├─ t1 worktree
            ├─ t2 mémoire projet (Hindsight)
            ├─ t3 grill-me + quadrant d'ambiguïté
            ├─ t3b doc-cadrage (architecture)
            ├─ t4 draft spec  (délibération en room Bot Mode)
            └─ t5 validate    ← PORTE HUMAINE (go / no-go)
                 └─ graphe de développement (test ∥ dev → convergence → doc)
                      └─ t6 submitted → PR (jamais mergée par l'agent)
```

**Principe directeur** : tout ce qui est mécanique est **scripté sans LLM** ; le LLM
n'intervient que là où il faut juger. Un pipeline au repos coûte zéro token.

---

## Arborescence

| chemin | contenu |
|---|---|
| `bridge/` | pont GitHub ↔ kanban, hooks, garde-fous d'admission |
| `pipeline/` | outils déterministes (construction de graphe, linters, portes de qualité) |
| `agents/` | `SOUL.md` de chaque profil + `config.yaml.example` **assaini** |
| `skills/` | skills Hermes du projet (procédures réutilisables) |
| `workflows/` | schémas et templates de workflow YAML |
| `plugins/` | plugins de l'app desktop (boutons Discord, UI dashboard) |
| `tests/` | 113 tests, sans dépendance externe |

---

## Installation

### 1. Prérequis

- Hermes Agent installé (`~/.hermes/`)
- `gh` CLI authentifié
- Un dépôt cible avec une branche `dev`

### 2. Créer les profils

```bash
for p in pj-master pj-dev pj-doc pj-test; do hermes profile create "$p"; done
```

### 3. Configurer chaque profil

```bash
cp agents/pj-master/config.yaml.example ~/.hermes/profiles/pj-master/config.yaml
# puis éditer : renseigner base_url et la clé d'API (jamais versionnée)
```

Les secrets vivent dans `~/.hermes/profiles/<profil>/.env`, **hors de ce dépôt**.
Variables attendues :

```
LITELLM_API_KEY=...
DISCORD_BOT_TOKEN=...
DISCORD_ALLOWED_USERS=...
HERMES_KANBAN_BOARD=pj
```

### 4. Déployer les outils

La variable `HERMES_WORKFLOW` doit pointer vers ce dépôt (les scripts l'utilisent
pour se résoudre eux-mêmes) :

```bash
export HERMES_WORKFLOW="$PWD"     # à ajouter au profil shell
```



```bash
mkdir -p ~/.hermes/scripts
cp pipeline/*.py ${HERMES_WORKFLOW}/pipeline/
cp pipeline/*.py ~/.hermes/profiles/pj-master/scripts/   # les crons résolvent ici
chmod +x ${HERMES_WORKFLOW}/pipeline/pj_*.py
```

> **Pourquoi deux copies ?** Les crons résolvent leurs `--script` dans le dossier
> `scripts/` **du profil**, pas dans `${HERMES_WORKFLOW}/pipeline/`. Les deux emplacements
> sont nécessaires.

### 5. Créer un board par dépôt

```bash
hermes kanban boards create pj-<repo>
hermes kanban boards set-default-workdir pj-<repo> /chemin/vers/clone-dev
```

---

## Portes de qualité (toutes déterministes, 0 LLM)

| outil | rôle | échec |
|---|---|---|
| `pj_card_lint.py` | 5 sections obligatoires + BDD + DoR/DoD + INVEST | exit 1 |
| `pj_slices_lint.py` | contrat du graphe + slice `preview` si prototypage requis | exit 1 |
| `pj_coverage_gate.py` | couverture par fichier **modifié** | exit 1 |
| `pj_docs_lint.py` | vault documentaire (frontmatter, liens, orphelines) | exit 1 |
| `pj_spawn_guard.py` | liste blanche d'assignees par board | bloque la carte |

**Règle** : un contrôle qui filtre par motif filtre en **général**, jamais par liste
fermée — sinon toute étape ajoutée devient un faux positif, précisément au moment
où on l'ajoute.

---

## Garde-fous appris en production

1. **Gate de couverture** — une issue qui recouvre du travail en vol (PR ouverte,
   graphe existant) n'importe pas : elle est signalée pour décision humaine. Sans
   lui, une demande de modification en nouvelle issue repart en graphe complet.
2. **Quadrant d'ambiguïté** (t3) — chaque ambiguïté est qualifiée : levable seule
   ou non, **coût si non levée**. Le prototypage n'est exigé que si une ambiguïté
   non levable porte sur un livrable perceptible.
3. **Sens des liens kanban** — `link <parent> <child>` : l'**enfant attend** le
   parent. Une carte de synthèse se construit à l'envers, sinon deadlock.
4. **Branche unique par issue** — partager un worktree entre cartes exige le **même**
   `--branch`, sinon repli silencieux sur un worktree isolé.
5. **Garde-fou anti-livelock** — une délibération bloquée (defer en série) est
   détectée et coupée automatiquement, avec trace sur la carte.

---

## Tests

```bash
python3 -m pytest tests/ -q     # 113 passed
```

Les tests chargent leurs modules **depuis ce dépôt** (chemins relatifs), jamais
depuis un emplacement externe.

---

## Licence

MIT — voir `LICENSE`.
