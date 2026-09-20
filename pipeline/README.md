# Pipeline YAML — moteur d'orchestration kanban

Moteur de pipeline défini en YAML qui structure le comportement sur les
tickets kanban Hermes, en mélangeant étapes **déterministes** (commandes
shell : check template, CI, update kanban/GitHub) et **agentiques** (agents
externes : hermes profile+modèle, dsh/DeepSeek Harness, claude).

L'orchestration est pilotée par **structured output** : chaque étape
agentique émet un JSON validé contre un schéma, et un `gate` déterministe
décide de l'itération (`goto`) ou de la sortie.

## Fichiers

- `pipeline/engine.py` — le moteur (parse YAML, exécute les étapes, gate,
  cache d'état, CLI `run`/`list`)
- `pipeline/backends.py` — backends d'exécution agentique (hermes / dsh /
  claude) + extraction JSON robuste
- `pipeline/pj_escalate.py` — escalade des cartes bloquées vers le thread Discord
  de leur issue (voir ci-dessous)
- `workflows/spec.yaml` — premier workflow de validation (phase **spec**)
- `workflows/smoke.yaml` — workflow de test minimal (1 étape agentique dsh)
- `workflows/schemas/*.json` — schémas JSON des sorties structurées
- `workflows/templates/ticket.md` — template de ticket (check déterministe)

## Outil d'escalade `pj_escalate.py`

Remonte les cartes kanban **bloquées** vers le fil Discord de leur issue GitHub.
Déterministe (0 LLM), idempotent par `(carte, dernier event de blocage)`, déclenché
par un cron `no_agent` global (`main()` itère les boards `pj-*`, donc **sans**
suffixe de repo dans son wrapper).

Toute sa configuration vient de l'environnement — aucun identifiant, aucun chemin
de machine dans le fichier. Trois variables sont **requises**, les autres sont
**optionnelles** avec un défaut dérivé du répertoire personnel :

| variable | statut | défaut |
|---|---|---|
| `PJ_ESCALATE_CHANNEL_ID` | **requise** | — (canal des threads d'issue) |
| `PJ_ESCALATE_USER_ID` | **requise** | — (destinataire des décisions) |
| `PJ_ESCALATE_GUILD_ID` | **requise** | — |
| `PJ_ESCALATE_REPOS_ROOT` | optionnelle | `$HOME/pj-repos` |
| `PJ_ESCALATE_STATE_DIR` | optionnelle | `$HOME/.hermes/state` |
| `PJ_ESCALATE_THREAD_HELPER` | optionnelle | `$HOME/.hermes/scripts/discord_thread.py` |
| `PJ_ESCALATE_ORG` | optionnelle | `hyron-fr` |
| `PJ_ESCALATE_GH_BIN` | optionnelle | résolution `shutil.which` + candidats vérifiés |

**Une requise absente ou VIDE refuse le tick bruyamment** : `ConfigError`, message
sur la sortie d'erreur nommant la variable, code de sortie `2`, aucun envoi, aucune
écriture d'état. Une valeur vide n'est jamais un identifiant (mesuré : `target=""`
fait échouer le post, l'état n'avance pas, et le même message est reposté à chaque
tick, indéfiniment). Le répertoire d'état est validé par une **sonde d'écriture**
au tout début du tick, avant tout scan de board : sinon un `PermissionError` local
n'arrive qu'après que les boards précédents ont posté.

`PJ_ESCALATE_GH_BIN` est le seul cas où « posée vide » est un état **légitime** :
elle exprime « garde indisponible, escalade bruyante » — l'avertissement part, le
tick continue. Une variable **absente**, à l'inverse, laisse la résolution par
candidats vérifiés faire son travail.

Les identifiants Discord ne sont **jamais** écrits dans le dépôt (public) : le
wrapper `agents/pj-master/scripts/pj_escalate_all.sh` lit les `PJ_ESCALATE_*` du
`.env` **du profil** (`~/.hermes/profiles/<profil>/.env`, hors dépôt) et les
exporte vers le tick, en n'exportant **que** ce préfixe.

Les entrées-sorties passent par des points d'injection (`runner` pour les
sous-processus, `poster` pour l'envoi Discord, `conn_factory` pour la base kanban ;
défaut = implémentation réelle) : le tick complet s'exerce sans réseau et sans
exécutable réel.

## Schéma d'un workflow

```yaml
name: spec
orchestration:
  mode: structured_output
  max_iterations: 10        # borne les sauts ARRIÈRE (itérations)

steps:
  - id: viewpoints
    type: agentic            # ou deterministic / gate
    parallel: true
    prompt: "..."            # template {{ticket.*}} / {{steps.<id>}}
    agents:
      - { role: ddd, backend: hermes, profile: default, model: ... }
      - { role: tdd, backend: dsh, profile: headless }
    output: { kind: structured, schema: ./schemas/viewpoint.json }

  - id: gate
    type: gate
    check: "all(r.get('data',{}).get('status')=='ok' for r in revalidate.get('results',[]))"
    on_fail: revalidate      # saut arrière = itération
    on_pass: finalize        # saut avant = progression
```

Types d'étape :

- `agentic` — un ou plusieurs agents (`agents:` en parallèle, ou `agent:`
  seul). La sortie est extraite (JSON) puis validée contre `output.schema`.
- `deterministic` — `command:` (une commande) ou `actions:` (liste), rendues
  via `{{...}}` puis exécutées en shell.
- `gate` — évalue `check:` (expression Python sur les sorties d'étapes) et
  route via `on_pass`/`on_fail`.

Backends agentiques (`backend:` dans un agent) :

- `hermes` — `hermes -p <profile> chat -q "<prompt>"` (+ `model:` optionnel)
- `dsh` — `dsh --profile <profile> "<prompt>"` (DeepSeek Harness)
- `claude` — `claude -p "<prompt>"` (Claude Code CLI)

## Utilisation

```bash
# Lister les étapes d'un workflow (sans exécuter)
python3 pipeline/engine.py list workflows/spec.yaml

# Exécuter un workflow sur un ticket (simulation)
python3 pipeline/engine.py run workflows/spec.yaml <ticket_id> --dry-run

# Exécution réelle (écrit .pipeline/<ticket>.json + side effects)
python3 pipeline/engine.py run workflows/spec.yaml <ticket_id> --board hermes-experiment
```

## Idempotence / rejouabilité

Le moteur écrit un fichier d'état par ticket (`.pipeline/<ticket>.json`)
qui enregistre la sortie de chaque étape. Un re-run **saute les étapes déjà
réussies** (cache) et ne rejoue que ce qui a échoué ou changé. Supprimer le
fichier d'état force une exécution complète.

## Contexte de template

Les prompts et commandes utilisent `{{...}}` :

- `{{ticket.id}}`, `{{ticket.title}}`, `{{ticket.body}}`,
  `{{ticket.issue_number}}` (déduit de la ligne "Importé depuis <url>")
- `{{steps.<id>}}` — sortie JSON d'une étape précédente
- `{{board}}` — slug du board

## Traçabilité

- **GitHub = grosses mailles** : le `finalize` édite l'issue (numéro déduit
  du body de carte, même convention que le pont `gh_kanban_bridge.py`).
- **Hermes = détail** : chaque étape et sa sortie sont dans le fichier
  d'état `.pipeline/<ticket>.json` + commentaires kanban.
- **Discord = live** : à chaque passage d'étape (hors `--dry-run`), le
  moteur poste un update dans le thread Discord de l'issue (résolu par le
  nom `🎫 Issue #N — …` via `discord_thread.py threads`). Le thread est
  retrouvé depuis `ticket.issue_number` (déduit de la ligne « Importé
  depuis »). La notification est best-effort : si le thread est introuvable
  ou le post échoue, le pipeline continue sans casser.
