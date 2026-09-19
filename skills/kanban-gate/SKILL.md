---
name: kanban-gate
description: "Use when working a kanban card preceded by a deterministic gate. Read the [gate] verdict and act (pass=continue, fail=block/retry)."
version: 1.0.0
---

# kanban-gate

Skill worker pour les cartes kanban précédées d'un gate déterministe
(`gate_hook.py` déclenché par le hook `kanban_task_claimed`).

## Rôle

Quand tu travailles une carte kanban, le dispatcher a exécuté un gate
déterministe **juste avant** de te spawner. Le verdict est écrit en
commentaire structuré `[gate] pass|fail: <message>` sur la carte.

**Tu DOIS lire ce verdict avant d'agir** et te comporter en conséquence.

## Protocole

1. **Lire la carte** : `kanban_show` (ou `hermes kanban show <id> --json`).
   Cherche le commentaire le plus récent commençant par `[gate] `.
2. **Interpréter** :
   - `[gate] pass: ...` → le gate est vert. **Continue** le travail normalement.
   - `[gate] fail: ...` → le gate est rouge. **Ne pas** exécuter le travail.
     Bloque la carte avec la raison du gate : `kanban_block <id> --reason "<message du gate>"`.
3. **Ne jamais ignorer** un verdict `fail`. Un gate fail signifie qu'une
   précondition déterministe n'est pas satisfaite (template manquant, CI
   rouge, schéma invalide, etc.) — le travail serait invalide.

## Exemple

```
Commentaire: [gate] fail: gate fail (exit 1): test -f ./templates/ticket.md
→ Action: kanban_block t_xxx --reason "gate fail: template ticket.md manquant"
```

## Notes

- Le gate est **déterministe** (script shell), pas un avis LLM. Son verdict
  est contraignant.
- Si aucun commentaire `[gate]` n'est présent (carte sans gate), continue
  normalement — le gate est optionnel.
- Le verdict est écrit par le dispatcher (auteur = profil dispatcher), pas
  par un worker.
