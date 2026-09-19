# Kanban builtin — table de transitions & mécanique rooms

## Statuts (kanban_db.py:89, fixés)

`triage, todo, scheduled, ready, running, blocked, review, done, archived`

Colonnes de carte utiles : `workflow_template_id`, `current_step_key`,
`completion_contract`, `tenant` (namespace souple), `idempotency_key` (dédup
automation, non exposé dans list/show --json).

## Transitions et déclencheurs

| Transition | Déclencheur | Mécanisme |
|---|---|---|
| create → triage | humain/bot | `kanban create` (`--triage`) |
| triage → todo | grooming | `hermes kanban specify <id>` (aux-LLM resserre titre+body) ou édition manuelle |
| todo → ready | dispatcher, AUTO quand tous les parents done | `kanban_link` |
| ready → running | dispatcher, claim atomique + spawn worker | tick dispatch (gate d'admission ici) |
| running → blocked | worker/humain, + AUTO après `failure_limit` échecs consécutifs | `kanban_block` (circuit breaker) |
| blocked → running | humain/bot | `kanban_unblock` |
| running → review | worker | `kanban_request_review` |
| review → running | reviewer | `kanban_request_changes` (reprends ton code) |
| running → done | worker | `kanban_complete` (+ contract PR si déclaré) |
| done → archived | humain/gc | `hermes kanban archive` / `gc` |
| (parking) scheduled | timing/follow-up connue | `hermes kanban schedule` |

Statuts initiaux alternatifs à la création : `--initial-status blocked|running`.
Réassignation : `hermes kanban reassign` / `reclaim` (une carte peut changer de
worker entre étapes — alternative à une carte par étape).

## Gate de résultat vs gate de claim

- Gate de claim (hook `kanban_task_claimed`) : filtre d'admission, verdict en
  commentaire `[gate] pass|fail`. Observer — exit code ignoré.
- Gate de résultat : soit un profil revieweur (`kanban_request_review` →
  `request_changes`), soit un completion contract (`--completion-contract
  OWNER/REPO` ou `local-only`) : le `done` est refusé sans checks requis verts,
  avec événements durables `pr_acceptance` et `last_failure_error` pour le
  retry.

## Rooms (group chats) — mécanique

- 2-6 bots ; ton message → ≤3 rounds sériels × ≤10 messages/round ; un membre
  répond seulement s'il a quelque chose à ajouter, sinon il passe ; le room
  settle quand un round complet est silencieux.
- `@mention` scope le round aux ciblés ; `@user` escalade à l'humain (badge
  needs-you ; les prompts en attente le rallument aussi).
- Chaque membre = session persistante `Group: <name>` (contexte qui survit).
- Durable : si tous les membres partagent un gateway, le driver du gateway
  porte la room — fermer le desktop n'interrompt pas (catch-up au log).
- Multi-machines possible (Desktop relay / `hermes peer`) mais le driver
  durable n'est garanti que sur un gateway partagé.
- `message_agent` : DM bot↔bot fire-and-forget, SEULEMENT depuis le canonical
  Bot Chat (jamais en room ni en CLI).
- Hooks plugins : `on_room_member_activity` projette turn.started/turn.settled.
