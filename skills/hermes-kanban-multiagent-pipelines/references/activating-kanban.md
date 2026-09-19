# Activer le kanban — les deux couches, et où le vérifier

Deux choses indépendantes répondent toutes les deux à « comment activer le kanban dans
Hermes Desktop ». Répondre aux deux, dans cet ordre, et ne jamais affirmer sans avoir lu
le fichier cité :

| Couche | Où c'est défini | Activation |
|---|---|---|
| Board visuel dans l'app Desktop | `apps/desktop/src/plugins/kanban/plugin.tsx` (`defaultEnabled: false`) | Capabilities → Plugins → « Kanban » → colonne **Desktop** |
| Tools `kanban_*` dans une session agent | `tools/kanban_tools.py` : `_profile_has_kanban_toolset()` lit `load_config().get("toolsets", [])` | `hermes config set toolsets '["kanban"]'` |
| Déclenchement réel des cartes | `~/.hermes/kanban/.dispatcher.lock` (un seul détenteur par machine) | rien à activer : vérifier QUI dispatche |

## Couche Desktop (renderer, pas de CLI)

Le plugin desktop `kanban` est bundled mais **inventorié seulement** tant que
l'utilisateur ne l'active pas : il enregistre la page, la nav, le compteur de statusbar
et les notifications uniquement après le toggle.

- Store de la décision : `apps/desktop/src/contrib/plugins-store.ts` — clef localStorage
  `hermes.desktop.pluginDecisions.v2`, `pluginActive(id, defaultEnabled)` : l'**absence**
  de décision retombe sur le `defaultEnabled` du plugin (d'où l'opt-in par défaut).
- Toggle : `apps/desktop/src/app/skills/plugins-tab.tsx` → `setPluginEnabled(id, on)`.
  L'onglet vit dans `app/skills/index.tsx` (`SKILLS_MODES = ['skills','toolsets','mcp','plugins']`).
- Deep-link de la ligne : `/skills?tab=plugins&plugin=kanban` (`pluginElementId`).
- Anciens liens `?tab=plugins` sont redirigés (`app/settings/moved-tabs.ts`).

Ce que le plugin apporte une fois allumé : page `/kanban` + entrée de navigation
sidebar, compteur `running/ready` cliquable dans la statusbar, raccourci `mod+alt+n`
(nouvelle carte en triage), toasts in-app + notifications OS sur `completed`,
`blocked`, `gave_up`, `crashed`, `timed_out`, `block_loop_detected`.
Les notifications OS sont **gated** par Settings ▸ Notifications ▸ **Plugin
notifications** — et elles ne couvrent que la fenêtre où l'app tourne (pas de replay
des events arrivés app fermée ; pour de la livraison durable, abonner un gateway avec
`hermes kanban notify-subscribe`).

**Ne pas dire à l'utilisateur de taper `/kanban` dans le Desktop** : le slash y est
volontairement hors palette (`apps/desktop/src/lib/desktop-slash-commands.ts`,
`NO_DESKTOP_SURFACE.advanced`) et répond « use the relevant desktop control ». Le
chemin, c'est le board (page, palette ⌘K « Kanban: Open board », ou toggle).

## Couche tools (config, vérifiée)

- Le check_fn ne lit QUE la clef **racine** `toolsets` : `platform_toolsets.cli` peut
  contenir `kanban` (récupération read-time de `_get_platform_tools`) sans que le
  check_fn passe — ajouter `kanban` à la liste CLI ne débloque donc rien.
- `hermes config set toolsets '["kanban"]'` écrit une VRAIE liste YAML (vérifiable dans
  un `HERMES_HOME` temporaire avant de toucher la config vivante). La forme pointée
  `toolsets.0` écrit un dict fautif.
- Le bundle `hermes-cli` **liste** les `kanban_*` dans `TOOLSETS` — leur invisibilité
  vient du check_fn, pas de la liste : ne pas conclure « le toolset est déjà activé »
  en lisant la liste.
- Coût : ≈14 schémas `kanban_*` en plus dans chaque prompt de session.

## Diagnostic : qui dispatche ?

Le board ne s'ouvre pas tout seul et un seul gateway par machine détient le verrou.

```bash
fuser -v ~/.hermes/kanban/.dispatcher.lock      # PID détenteur
cat /proc/<pid>/cmdline | tr '\0' ' '           # quel profil (--profile X gateway run)
hermes kanban diagnostics                       # cartes en protocol_violation / blocked
tail -3 ~/.hermes/logs/gateway.log              # « another gateway already holds the dispatcher lock … will NOT dispatch »
```

Un gateway qui logue « will NOT dispatch » est normal (verrou singleton) : le tick
vient d'un autre profil. Ce n'est une panne que si AUCUN gateway ne logue
« embedded in gateway (interval=…) ». `kanban.dispatch_in_gateway: false` désactive
explicitement le tick pour un profil — le vérifier avant de chercher ailleurs.
