# Rooms Bot Mode (Group Chats) — mécanique, diagnostic, exploitation

Profondeur pour le travail sur les rooms. Les RÈGLES toujours vraies restent dans SKILL.md
(« Room vs board ») ; ce fichier porte l'API exacte, les bornes, et le diagnostic des pannes.

## Où vit le moteur

Le desktop n'est qu'un CLIENT. Le moteur est dans le gateway :

| Fichier | Rôle |
|---|---|
| `gateway/hosted_rooms.py` | persistance : `create_room`, `disband_room`, `request_room_stop`, `append_event`, `read_events`, `list_rooms`, `room_state`, `default_db_path` |
| `gateway/hosted_room_discussion.py` | policy pure : `validate_roster`, `validate_room`, `plan_next_task`, `_pending_discussion` |
| `tui_gateway/hosted_room_service.py` | le service (`bindings()`, `start_hosted_room_service()`) |
| `tui_gateway/hosted_room_driver.py` | la boucle et le lease (`HostedRoomRuntime`, `acquire_lease`, `defer_indeterminate_task`) |

Aucune sous-commande CLI `hermes groups` : tout passe par ces modules en Python.

## Bornes réelles (lues dans le code, ≠ doc utilisateur)

| Constante | Valeur | Sens |
|---|---|---|
| `MAX_ACTIVE_ROOMS` | 256 | rooms actives simultanées par hôte |
| `MIN/MAX_DISCUSSION_MEMBERS` | 2 / 6 | imposé par `validate_roster` — c'est la limite métier |
| `MAX_DISCUSSION_ROUNDS` | 3 | rounds par discussion |
| `MAX_DISCUSSION_MESSAGES` | 10 | messages par discussion |
| `max_concurrent_rooms` | 4 | délibérations réellement simultanées |
| `lease_ttl_seconds` | 30 | durée du lease de room (renouvelé pendant un tour) |
| `indeterminate_defer_seconds` | 60 | délai avant de « defer » une tâche indéterminée |
| `MAX_MEMBERS` | 128 | borne BAS NIVEAU du schéma, inatteignable via l'API |

## Persistance : une base PARTAGÉE par tous les profils

`default_db_path()` renvoie `~/.hermes/shared-state.db` **quel que soit le profil** (HERMES_HOME
n'y change rien). C'est délibéré : éviter que les gateways de profil ouvrent `state.db` en
écriture (vecteur de corruption multi-writer). Conséquence directe : tous les gateways d'une
même installation voient et servent les mêmes rooms.

Tables utiles au diagnostic : `hosted_rooms`, `hosted_room_events`, `hosted_room_retired_ids`,
`hosted_room_driver_tasks`, `hosted_room_driver_leases`.

## API — signatures et pièges

```python
import sys; sys.path.insert(0, "<chemin>/hermes-agent")
from gateway import hosted_rooms as hr

hr.create_room(db, room_id=..., name=..., members=[{...}], authority_gateway_id=...)
hr.disband_room(db, room_id=..., expected_gateway_id=..., expected_epoch=...)   # epoch OBLIGATOIRE
hr.request_room_stop(db, room_id=..., cancel_id=..., expected_gateway_id=..., expected_epoch=...)
rooms = hr.list_rooms(db)
room  = hr.room_state(db, room_id=...)
events = hr.read_events(db, room_id=...)['events']    # dict, clé 'events'
hr.append_event(db, room_id=..., event_id=..., kind=..., actor=..., payload=...,
                authority_gateway_id=..., authority_epoch=...)
```

- `create_room` est **idempotent** (même room_id = même room renvoyée).
- **N'existent PAS** : `get_room`, `list_events`. Utiliser `list_rooms` / `room_state` /
  `read_events`. Se tromper de nom coûte un `AttributeError` au milieu d'un diagnostic.
- Roster : exactement `{member_id, profile, handle}` — `display_name` et `target` optionnels.
  Tout autre champ est refusé (`_exact_fields`). Les profils doivent être **locaux au gateway**
  (`local_profiles()` = les sous-dossiers de `~/.hermes/profiles/` + `default`).
- Aucun `wakeup()` nécessaire après un `create_room` hors processus : `bindings()` relit la base
  à chaque cycle (poll 5 s au repos, 0,25 s en actif) et découvre la room seule.

## Les bots ne parlent JAMAIS spontanément

`plan_next_task` renvoie `status='idle'`, `reason='no_pending_user_event'` tant qu'aucun
`message.user` n'existe. Une room créée et jamais animée reste donc silencieuse indéfiniment —
ce n'est pas une panne, c'est le contrat.

Déclencheur (payload **exact** `{text, thread_id}`) :

```python
hr.append_event(db, room_id=rid, event_id=f"ev-{rid}-{tid}", kind="message.user",
    actor={"kind": "user", "id": "<profil orchestrateur>"},
    payload={"text": "...", "thread_id": tid},
    authority_gateway_id=hr.local_authority_gateway_id(), authority_epoch=1)
```

Round 1 = les membres **mentionnés** (aucune mention = TOUS) ; rounds 2-3 = opt-in (un pair cité
qui n'a pas encore parlé). Ne pas fabriquer de `@` quand on veut interroger tout le monde.

## Fin d'une délibération : le critère exact

`_pending_discussion` considère une discussion close quand un event `room.activity` porte
`status` ∈ `{settled, bounded}` pour son `discussion_event_id` (`bounded` = plafond atteint :
3 rounds ou 10 messages). Un event `room.stop_requested` **supersède** tout message utilisateur
antérieur : seuls les `message.user` de `seq` > dernier stop restent « en attente ».

## Kinds d'events

`message.user`, `message.member`, `turn.settled`, `turn.failed`, `turn.cancelled`,
`turn.deferred`, `room.activity`, `room.stop_requested`.

## Livelock : `indeterminate` → `deferred` en boucle

**Mécanisme.** Un gateway qui acquiert le lease d'une room marque `indeterminate` toute tâche
`running` qui ne porte pas sa propre fence (`foreign_running`, `hosted_room_driver.py`). La
réconciliation ne peut PAS récupérer le tour d'un autre processus : elle « defer » la tâche
avec `reason='member_unavailable'` toutes les ~60 s (`indeterminate_defer_seconds`).

**Conséquence : ce n'est PAS auto-réparateur.** Tant que plusieurs gateways se repassent le
lease, le cycle `indeterminate → deferred → retry → indeterminate` tourne indéfiniment :
`plan_next_task` reste `task`/`member_turn`, la room reste `pending`, et la délibération ne
progresse plus. Le lease garantit l'exclusion mutuelle (jamais deux exécutions concurrentes,
aucun doublon d'`event_id`) mais **ne garantit pas la progression**.

**Diagnostic — mesurer la contention :**

```sql
-- Nombre de fois où le lease a été (re)pris : un compteur qui grimpe = contention.
SELECT room_id, lease_generation FROM hosted_room_driver_leases ORDER BY lease_generation DESC;
-- Nombre de PROCESS différents ayant réellement exécuté des tours sur la room.
SELECT run_process_generation, count(*) FROM hosted_room_driver_tasks
  WHERE room_id='<rid>' AND run_process_generation IS NOT NULL GROUP BY 1;
-- Raison d'un defer : member_unavailable = contention, pas un bug de la room.
SELECT status, count(*) FROM hosted_room_driver_tasks WHERE room_id='<rid>' GROUP BY status;
```

Un `lease_generation` à deux chiffres sur une room jeune, ou plusieurs `run_process_generation`
distincts pour une même room, confirment la contention. Vérifier aussi combien de gateways
tournent (`hermes gateway list`) : chacun démarre son worker de room.

**Sortie de secours — la fence d'arrêt.** `request_room_stop` appende un `room.stop_requested`
qui supersède les tours antérieurs : le planificateur repasse immédiatement à
`idle`/`no_pending_user_event` et la boucle de defer cesse. C'est la sortie propre d'un livelock
(préférable à un kill), et elle préserve le transcript (`read_events` garde tout) — à reporter
sur le board avant dissolution.

**Correctif de fond : non appliqué.** Le worker de room est démarré inconditionnellement par
chaque gateway (`_start_post_connect_services` → `_hosted_room_worker_watcher`) et il n'existe
ni clé de config ni hook pour le désactiver : le limiter au gateway qui détient le dispatcher
impose de patcher le core. À défaut, le régime sûr est **une seule délibération active** quand
plusieurs gateways tournent, avec la fence d'arrêt comme garde-fou.
