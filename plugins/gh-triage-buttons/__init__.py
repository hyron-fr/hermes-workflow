"""gh-triage-buttons — boutons go/no-go déterministes pour le drill gh-triage.

Enregistre un handler de plateforme Discord qui écoute les interactions de
composant (clics de bouton) portant un ``custom_id`` ``triage:go:<N>`` /
``triage:nogo:<N>``, acquitte le clic, puis route une instruction
déterministe dans la session Hermes du thread pour que le bot gh-triage
agisse (créer la carte / relancer le drill) SANS interprétation LLM du
déclencheur.

Généralisable : le schéma de ``custom_id`` est ``<décision>:<action>:<payload>``.
Ce plugin ne traite aujourd'hui que le point de décision ``triage:``, mais le
câblage est réutilisable pour les futurs points (validation d'import pull,
validation de clôture handoff) — il suffit d'étendre ``parse_custom_id`` et
``instruction_for``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Point de décision traité par ce plugin. Étendre pour les futurs points.
_DECISION_PREFIX = "triage:"


def parse_custom_id(custom_id: str):
    """Retourne (action, payload) pour une décision triage, ou None.

    Déterministe : ``triage:go:<N>`` -> ("go", "<N>"),
    ``triage:nogo:<N>`` -> ("nogo", "<N>"). Tout le reste -> None.
    """
    if not custom_id or not custom_id.startswith(_DECISION_PREFIX):
        return None
    parts = custom_id.split(":")
    if len(parts) != 3:
        return None
    _, action, payload = parts
    if action not in ("go", "nogo") or not payload:
        return None
    return action, payload


def instruction_for(action: str, payload: str) -> str:
    """Instruction déterministe que le bot exécute (voir SOUL.md)."""
    if action == "go":
        return (
            f"[DÉCISION BOUTON] go — issue #{payload}. "
            f"Crée la carte kanban maintenant selon la synthèse postée "
            f"(protocole SOUL.md étape 6)."
        )
    return (
        f"[DÉCISION BOUTON] no go — issue #{payload}. "
        f"Relance le drill : repose des questions de précision, "
        f"ne crée aucune carte."
    )


def register(ctx):
    ctx.register_platform_handler("discord", _wire)


def _wire(native, adapter):
    import discord

    async def on_interaction(interaction):
        if getattr(interaction, "type", None) != discord.InteractionType.component:
            return
        data = getattr(interaction, "data", None) or {}
        custom_id = data.get("custom_id", "")
        parsed = parse_custom_id(custom_id)
        if parsed is None:
            return
        action, payload = parsed

        # Autorise le cliqueur (même porte que les vues de boutons de l'adapter).
        try:
            from plugins.platforms.discord.adapter import _component_check_auth

            allowed = _component_check_auth(
                interaction,
                getattr(adapter, "_allowed_user_ids", set()),
                getattr(adapter, "_allowed_role_ids", set()),
            )
        except Exception:
            allowed = True  # fail-open uniquement si le check lui-même est indisponible
        if not allowed:
            try:
                await interaction.response.send_message(
                    "Tu n'es pas autorisé à valider ce triage.", ephemeral=True
                )
            except Exception:
                pass
            return

        # Acquitte le clic immédiatement.
        try:
            await interaction.response.send_message(
                "✅ Décision reçue — je traite…", ephemeral=True
            )
        except Exception:
            try:
                await interaction.response.defer()
            except Exception:
                pass

        # Route une instruction déterministe dans la session du thread.
        text = instruction_for(action, payload)
        try:
            event = adapter._build_slash_event(interaction, text)
        except Exception:
            logger.warning(
                "gh-triage-buttons: _build_slash_event a échoué", exc_info=True
            )
            return
        await adapter.handle_message(event)

    native.add_listener(on_interaction, "on_interaction")
