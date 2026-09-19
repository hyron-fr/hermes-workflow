"""pj-buttons — boutons décisionnels déterministes pour le pipeline pj.

Écoute les interactions de composant Discord, ACK le clic (sinon Discord affiche
« didn't respond in time »), vérifie l'autorisation, puis applique la décision
DIRECTEMENT en kanban (subprocess `hermes kanban ...`, aucun LLM) :

  - go   : commente la carte (« GO humain ») puis `unblock` → le dispatcher
           re-spawne le worker, qui relit le fil et continue le protocole.
  - nogo : commente la carte (« NO-GO humain ») puis `unblock` → le worker
           relit et relance la clarification (nouvelles questions grill-me).

Deux schémas de custom_id acceptés :

  pj:<action>:<board>/<task_id>      (format canonique pj, émis par le helper)
  triage:<action>:<N>                (héritage du helper gh-triage ; board+carte
                                      résolus depuis le nom du thread :
                                      « <repo> #<N> · <titre> »)

Résolution déterministe : nom du thread → repo + numéro d'issue → board `pj-<repo>`
→ carte dont le body contient « /issues/<N> ». Aucun appel LLM.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)

HERMES_BIN = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/hermes")
THREAD_NAME_RE = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*#(\d+)")


def parse_custom_id(custom_id: str):
    """-> (action, board, task_id) | (action, None, issue_number) | None."""
    if not custom_id:
        return None
    if custom_id.startswith("pj:"):
        parts = custom_id.split(":", 2)
        if len(parts) != 3:
            return None
        _, action, payload = parts
        if action not in ("go", "nogo") or "/" not in payload:
            return None
        board, task_id = payload.split("/", 1)
        if not board or not task_id:
            return None
        return action, board, task_id
    if custom_id.startswith("triage:"):
        parts = custom_id.split(":")
        if len(parts) != 3:
            return None
        _, action, n = parts
        if action not in ("go", "nogo") or not n.isdigit():
            return None
        return action, None, n
    return None


def board_for_repo(repo: str) -> str:
    return "pj-" + re.sub(r"[^a-z0-9-]+", "-", repo.lower()).strip("-")


def kanban(board: str, *args: str, timeout: int = 60):
    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/.local/bin:") + env.get("PATH", "")
    return subprocess.run([HERMES_BIN, "kanban", "--board", board, *args],
                          capture_output=True, text=True, env=env, timeout=timeout)


def resolve_from_thread(thread_name: str, issue_n: str):
    """(board, task_id) de la carte à débloquer pour le thread donné.

    Priorité 1 : la carte *blocked* du board (c'est elle qui attend une décision
    humaine : « t5 validate » pour un go/no-go, « t3 grill-me » pour des réponses).
    Priorité 2 : la racine dont le body cite l'URL de l'issue (audit/failback).
    """
    m = THREAD_NAME_RE.match(thread_name or "")
    if not m:
        return None, None
    repo = m.group(1)
    board = board_for_repo(repo)
    r = kanban(board, "list", "--json")
    if r.returncode != 0:
        return None, None
    try:
        tasks = json.loads(r.stdout or "[]")
    except Exception:
        return None, None

    blocked = [t for t in tasks if (t.get("status") == "blocked")]
    # Préférence aux cartes de décision du pipeline.
    for t in blocked:
        title = (t.get("title") or "").lower()
        if "validate" in title or "grill" in title:
            return board, t.get("id")
    if len(blocked) == 1:
        return board, blocked[0].get("id")

    needle = f"/issues/{issue_n}"
    for t in tasks:
        if needle in (t.get("body") or ""):
            return board, t.get("id")
    return board, None


def thread_name_of(interaction) -> str:
    ch = getattr(interaction, "channel", None)
    return getattr(ch, "name", "") or ""


def _data_get(data, key, default=None):
    """`interaction.data` est un dict chez discord.py, mais tolérer l'attribut."""
    if data is None:
        return default
    if isinstance(data, dict):
        return data.get(key, default)
    return getattr(data, key, default)


async def handle(adapter, interaction) -> bool:
    """Traite une interaction de composant pj/triage. True si consommée."""
    parsed = parse_custom_id(_data_get(interaction.data, "custom_id", ""))
    if parsed is None:
        return False
    action, board, task_or_n = parsed

    # Autorisation (même porte que les vues de boutons de l'adapter).
    try:
        from plugins.platforms.discord.adapter import _component_check_auth
        allowed = _component_check_auth(
            interaction,
            getattr(adapter, "_allowed_user_ids", set()),
            getattr(adapter, "_allowed_role_ids", set()),
        )
    except Exception:
        allowed = True
    if not allowed:
        try:
            await interaction.response.send_message(
                "Tu n'es pas autorisé à valider cette décision.", ephemeral=True)
        except Exception:
            pass
        return True

    # ACK immédiat — sans lui Discord affiche « didn't respond in time ».
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:
        pass

    # Résolution de la carte (déterministe, hors boucle d'événements).
    if board is None:
        n = task_or_n
        name = thread_name_of(interaction)
        board, task_id = await asyncio.to_thread(resolve_from_thread, name, n)
        if not task_id:
            logger.warning("pj-buttons: carte introuvable (thread=%r, issue=%s)", name, n)
            try:
                await interaction.followup.send(
                    f"Carte introuvable pour l'issue #{n} (thread « {name} »). "
                    f"Valide en CLI : `hermes kanban --board pj-<repo> list`.", ephemeral=True)
            except Exception:
                pass
            return True
    else:
        task_id = task_or_n

    verb = "GO" if action == "go" else "NO-GO"
    note = (
        f"Décision BOUTON Discord : {verb} humain reçu dans le thread. "
        + ("Poursuite du protocole (créer t6 + sous-tâches dev, règle ANTI-DEADLOCK)."
           if action == "go" else
           "Ne pas poursuivre : relancer la clarification (nouvelles questions grill-me).")
    )
    await asyncio.to_thread(kanban, board, "comment", task_id, note)
    r = await asyncio.to_thread(kanban, board, "unblock", task_id)
    ok = r.returncode == 0
    if not ok:
        # Carte peut-être déjà ready/running : le commentaire suffit, on le dit.
        logger.warning("pj-buttons: unblock %s -> rc=%s %s", task_id, r.returncode,
                       (r.stderr or r.stdout).strip()[:200])

    try:
        await interaction.followup.send(
            (f"✅ {verb} enregistré sur la carte `{task_id}` (board `{board}`). "
             + ("Le pipeline reprend." if ok else
                "Carte déjà active — la décision est notée en commentaire.")),
            ephemeral=True)
    except Exception:
        pass
    return True


def register(ctx):
    ctx.register_platform_handler("discord", _wire)


def _wire(native, adapter):
    import discord

    async def on_interaction(interaction):
        if getattr(interaction, "type", None) != discord.InteractionType.component:
            return
        try:
            consumed = await handle(adapter, interaction)
        except Exception:
            logger.warning("pj-buttons: erreur de traitement", exc_info=True)
            return
        if consumed:
            logger.info("pj-buttons: décision traitée (custom_id=%s)",
                        (getattr(interaction, "data", None) or {}).get("custom_id"))

    native.add_listener(on_interaction, "on_interaction")