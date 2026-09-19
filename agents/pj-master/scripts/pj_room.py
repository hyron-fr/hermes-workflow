#!/usr/bin/env python3
"""pj_room — une room Bot Mode par ticket, dans le pipeline pj.

Modèle : **une room par ticket**, `room_id` déterministe `pj-<repo>-issue-<n>`.
Elle sert de canal de délibération (peer programming, questions, arbitrages) ; le
board kanban reste la SOURCE DE VÉRITÉ — toute conclusion de room est reportée en
`kanban_comment` par pj-master.

Créée par le déployeur en même temps que le graphe, dissoute à la clôture de l'issue.

Membres : les 4 profils du pipeline (pj-master, pj-dev, pj-doc, pj-test).
Contrainte vérifiée : `validate_roster` impose 2..6 membres par room.

Écriture : la table `hosted_rooms` vit dans `~/.hermes/shared-state.db` (dédiée :
les gateways de profil n'ouvrent jamais `state.db` en écriture). L'API bas niveau
`gateway.hosted_rooms.create_room` est utilisée directement — le worker « hosted room »
est transport-free, il n'a pas besoin du desktop.

Usage :
  pj_room.py --repo dino-game --issue 8 --action ensure     # crée (idempotent) + état
  pj_room.py --repo dino-game --issue 8 --action disband    # dissout la room
  pj_room.py --repo dino-game --issue 8 --action state      # état seul
Sortie : une ligne JSON sur stdout (lisible par le déployeur et les workers).
exit 0 = action réussie ; 1 = échec ; 2 = usage.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

HERMES_AGENT = os.environ.get("PJ_HERMES_AGENT", "${HOME}/.hermes/hermes-agent")
DEFAULT_MEMBERS = ("pj-master", "pj-dev", "pj-doc", "pj-test")
VALID_ACTIONS = ("ensure", "disband", "state", "ask", "status", "transcript", "stop")


def room_id_for(repo: str, issue: int) -> str:
    """`pj-<repo-slug>-issue-<n>` — déterministe, donc retrouvable sans table de mapping."""
    slug = re.sub(r"[^a-z0-9-]+", "-", str(repo).lower()).strip("-")
    return f"pj-{slug}-issue-{int(issue)}"


def room_name_for(repo: str, issue: int) -> str:
    return f"pj {repo} #{int(issue)}"


def build_roster(profiles=DEFAULT_MEMBERS) -> list:
    """Roster au format attendu par validate_roster : {member_id, profile, handle}."""
    return [{"member_id": p, "profile": p, "handle": p} for p in profiles]


def parse_args(argv) -> dict:
    ap = argparse.ArgumentParser(prog="pj_room.py")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--issue", type=int, required=True)
    ap.add_argument("--action", default="ensure")
    ap.add_argument("--text", default="")
    ap.add_argument("--members", default="")
    a = ap.parse_args(argv)
    if a.action not in VALID_ACTIONS:
        raise ValueError(f"action invalide: {a.action} (attendu: {', '.join(VALID_ACTIONS)})")
    if a.action == "ask" and not a.text.strip():
        raise ValueError("action ask requiert --text")
    return {"repo": a.repo, "issue": a.issue, "action": a.action, "text": a.text,
            "members": [m.strip() for m in a.members.split(",") if m.strip()]}


def _hosted_rooms():
    if HERMES_AGENT not in sys.path:
        sys.path.insert(0, HERMES_AGENT)
    from gateway import hosted_rooms
    return hosted_rooms


def do_ensure(repo: str, issue: int) -> dict:
    hr = _hosted_rooms()
    rid = room_id_for(repo, issue)
    room = hr.create_room(
        hr.default_db_path(), room_id=rid, name=room_name_for(repo, issue),
        members=build_roster(), authority_gateway_id=hr.local_authority_gateway_id())
    return {"action": "ensure", "room_id": rid, "name": room.get("name"),
            "members": [m.get("profile") for m in (room.get("members") or [])],
            "idempotent": bool(room.get("idempotent")), "status": "ok"}


def _current_room(hr, rid: str):
    """Room courante (dict) ou None. `list_rooms` renvoie les rooms actives."""
    try:
        for r in hr.list_rooms(hr.default_db_path()):
            if str(r.get("room_id")) == rid:
                return r
    except Exception:
        pass
    return None


def do_disband(repo: str, issue: int) -> dict:
    hr = _hosted_rooms()
    rid = room_id_for(repo, issue)
    room = _current_room(hr, rid)
    if room is None:
        return {"action": "disband", "room_id": rid, "status": "absent"}
    # disband_room exige l'identité d'autorité ET son epoch (tombstone idempotente).
    try:
        hr.disband_room(
            hr.default_db_path(), room_id=rid,
            expected_gateway_id=room.get("authority_gateway_id"),
            expected_epoch=room.get("authority_epoch"))
    except Exception as e:
        return {"action": "disband", "room_id": rid, "status": "error",
                "detail": f"{type(e).__name__}: {e}"[:200]}
    return {"action": "disband", "room_id": rid, "status": "ok"}


def do_state(repo: str, issue: int) -> dict:
    hr = _hosted_rooms()
    rid = room_id_for(repo, issue)
    room = _current_room(hr, rid)
    if room is None:
        return {"action": "state", "room_id": rid, "status": "absent"}
    return {"action": "state", "room_id": rid, "name": room.get("name"),
            "disbanded": room.get("disbanded_at") is not None,
            "members": [m.get("profile") for m in (room.get("members") or [])],
            "authority_epoch": room.get("authority_epoch"), "status": "ok"}


def parse_room_id(rid: str):
    """(repo, issue) depuis `pj-<repo>-issue-<n>`, ou None si hors schéma du pipeline.

    C'est ce qui rend le réap sûr : une room est retrouvable depuis son seul
    identifiant, sans table de correspondance.
    """
    m = re.fullmatch(r"pj-(.+)-issue-(\d+)", str(rid or ""))
    if not m:
        return None
    return m.group(1), int(m.group(2))


def build_ask_text(repo: str, issue: int, members) -> str:
    """Message d'animation d'une délibération.

    Sans mention, le moteur interroge TOUS les membres au round 1 — on ne
    fabrique donc pas de @ quand la liste est vide.
    """
    mentions = " ".join(f"@{m}" for m in members if m)
    base = (f"Ticket #{int(issue)} ({repo}) — cadrage à valider par le pipeline. "
            f"Positionnez le périmètre exact, les impacts et les tests attendus.")
    return f"{base} {mentions}".strip() if mentions else base


def do_ask(repo: str, issue: int, text: str) -> dict:
    """Poste un message utilisateur dans la room — SEUL déclencheur d'une délibération.

    `plan_next_task` reste `idle` (« no_pending_user_event ») tant qu'aucun
    `message.user` n'existe : les bots ne parlent jamais spontanément, ils réagissent
    à une entrée utilisateur (round 1 = mentions, ou tous si aucune mention).
    Bornes du moteur : 3 rounds max, 10 messages max par discussion.
    """
    if not text or not text.strip():
        return {"action": "ask", "status": "error", "detail": "texte vide"}
    hr = _hosted_rooms()
    rid = room_id_for(repo, issue)
    if _current_room(hr, rid) is None:
        return {"action": "ask", "room_id": rid, "status": "absent"}
    thread_id = f"{rid}-t{int(__import__('time').time())}"
    event_id = f"ev-{rid}-{thread_id}"
    event = hr.append_event(
        hr.default_db_path(), room_id=rid, event_id=event_id, kind="message.user",
        actor={"kind": "user", "id": "pj-master"},
        payload={"text": text.strip(), "thread_id": thread_id},
        authority_gateway_id=hr.local_authority_gateway_id(), authority_epoch=1)
    return {"action": "ask", "room_id": rid, "thread_id": thread_id,
            "event_id": event_id, "seq": event.get("seq"), "status": "ok"}


def do_stop(repo: str, issue: int, reason: str = "livelock") -> dict:
    """Arrête la délibération en cours (fence `room.stop_requested`).

    `_pending_discussion` ignore tout message utilisateur dont le seq est ≤ au
    dernier `room.stop_requested` : l'arrêt supersède donc les tours antérieurs et
    débloque une délibération qui boucle (p.ex. `member_unavailable` en série).
    C'est la sortie de secours quand une room est en livelock.
    """
    hr = _hosted_rooms()
    rid = room_id_for(repo, issue)
    room = _current_room(hr, rid)
    if room is None:
        return {"action": "stop", "room_id": rid, "status": "absent"}
    try:
        hr.request_room_stop(
            hr.default_db_path(), room_id=rid,
            cancel_id=f"pj-{reason}-{rid}-{int(__import__('time').time())}",
            expected_gateway_id=room.get("authority_gateway_id"),
            expected_epoch=room.get("authority_epoch"))
    except Exception as e:
        return {"action": "stop", "room_id": rid, "status": "error",
                "detail": f"{type(e).__name__}: {e}"[:200]}
    return {"action": "stop", "room_id": rid, "status": "ok"}


LIVELOCK_THRESHOLD = 2
LIVELOCK_REASON = "member_unavailable"
# Un message de membre ou un tour terminé prouve que la délibération AVANCE :
# le compteur de defer est remis à zéro (sinon on couperait une délibération saine
# qui alterne defer et réponses).
_PROGRESS_KINDS = ("message.member", "turn.settled")


def detect_livelock(events, threshold: int = LIVELOCK_THRESHOLD) -> dict:
    """La délibération est-elle bloquée (defer en série sans aucun progrès) ?

    Signature observée d'un livelock multi-gateway : des `turn.deferred` répétés
    avec `reason=member_unavailable` (le gateway gagnant du lease marque la tâche
    `running` d'un autre gateway `indeterminate`, la réconciliation ne peut pas la
    récupérer et la diffère — indéfiniment), et AUCUN message de membre entre eux.

    On ne se base pas sur le NOMBRE total de defer (une délibération longue en
    compte légitimement) mais sur les defer CONSÉCUTIFS en fin de journal.
    """
    trailing = 0
    members: list = []
    for e in reversed(events or []):
        kind = e.get("kind")
        if kind in _PROGRESS_KINDS:
            break
        if kind == "room.stop_requested":
            return {"livelock": False, "trailing_defers": trailing, "members": [],
                    "detail": "déjà arrêtée"}
        if kind == "turn.deferred":
            if (e.get("payload") or {}).get("reason") != LIVELOCK_REASON:
                break
            trailing += 1
            m = (e.get("payload") or {}).get("member_id")
            if m and m not in members:
                members.append(m)
    return {"livelock": trailing >= int(threshold), "trailing_defers": trailing,
            "members": list(reversed(members)),
            "detail": f"{trailing} defer consécutif(s) en fin de journal"}


def do_status(repo: str, issue: int) -> dict:
    """État de la délibération : finie, en cours, ou EN LIVELOCK ?

    `_pending_discussion` (vérifié dans hosted_room_discussion.py) considère une
    discussion terminée quand un event `room.activity` porte `status` ∈ {settled,
    bounded} pour son `discussion_event_id`. `bounded` = plafond atteint
    (3 rounds / 10 messages).
    """
    hr = _hosted_rooms()
    rid = room_id_for(repo, issue)
    if _current_room(hr, rid) is None:
        return {"action": "status", "room_id": rid, "status": "absent"}
    ev = hr.read_events(hr.default_db_path(), room_id=rid)["events"]
    done = {str((e.get("payload") or {}).get("discussion_event_id"))
            for e in ev if e.get("kind") == "room.activity"
            and (e.get("payload") or {}).get("status") in ("settled", "bounded")}
    # Un `room.stop_requested` supersède tout message utilisateur antérieur :
    # `_pending_discussion` ne retient que les messages de seq > dernier stop.
    stopped_through = max((int(e.get("seq") or 0) for e in ev
                           if e.get("kind") == "room.stop_requested"), default=0)
    users = [e for e in ev if e.get("kind") == "message.user"]
    threads = {str((e.get("payload") or {}).get("thread_id")): e for e in users}
    pending = [t for t, e in threads.items()
               if e.get("event_id") not in done and int(e.get("seq") or 0) > stopped_through]
    replies = [e for e in ev if e.get("kind") == "message.member"]
    live = detect_livelock(ev)
    state = "pending" if pending else ("done" if users else "empty")
    if state == "pending" and live["livelock"]:
        state = "livelock"
    return {"action": "status", "room_id": rid, "state": state,
            "stopped": bool(stopped_through), "livelock": live["livelock"],
            "trailing_defers": live["trailing_defers"], "stalled_members": live["members"],
            "users": len(users), "replies": len(replies), "events": len(ev),
            "repliers": sorted({(e.get("actor") or {}).get("id") for e in replies}), "status": "ok"}


def do_transcript(repo: str, issue: int) -> dict:
    """Transcript lisible de la room (délibération complète, dans l'ordre)."""
    hr = _hosted_rooms()
    rid = room_id_for(repo, issue)
    if _current_room(hr, rid) is None:
        return {"action": "transcript", "room_id": rid, "status": "absent"}
    out = []
    for e in hr.read_events(hr.default_db_path(), room_id=rid)["events"]:
        k = e.get("kind")
        if k not in ("message.user", "message.member"):
            continue
        out.append({"seq": e.get("seq"), "kind": k,
                    "from": (e.get("actor") or {}).get("id"),
                    "text": (e.get("payload") or {}).get("text") or ""})
    return {"action": "transcript", "room_id": rid, "messages": out,
            "count": len(out), "status": "ok"}


def main(argv=None) -> int:
    try:
        args = parse_args(argv if argv is not None else sys.argv[1:])
    except (ValueError, SystemExit) as e:
        print(f"[pj-room] {e}")
        return 2
    table = {"ensure": do_ensure, "disband": do_disband, "state": do_state,
             "status": do_status, "transcript": do_transcript, "stop": do_stop}
    try:
        out = (do_ask(args["repo"], args["issue"], args["text"]) if args["action"] == "ask"
               else table[args["action"]](args["repo"], args["issue"]))
    except Exception as e:
        out = {"action": args["action"], "room_id": room_id_for(args["repo"], args["issue"]),
               "status": "error", "detail": f"{type(e).__name__}: {e}"[:300]}
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out.get("status") in ("ok", "noop", "absent") else 1


if __name__ == "__main__":
    sys.exit(main())
