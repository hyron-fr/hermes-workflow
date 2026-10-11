#!/usr/bin/env python3
"""Core PUR de décision humaine `/ok` (issue #5, slice 4 — `core-decision-ok-pur`).

Ce module **calcule** une décision, il ne l'applique jamais : aucun `gh`, aucun
réseau, aucun fichier, aucun `subprocess`. Les effets (débloquer la carte, poster
le commentaire, fermer l'enfant) sont portés par l'appelant — c'est ce qui rend le
banc `tests/test_decision_humaine.py` rejouable hors ligne.

Design ratifié (une issue enfant par carte bloquée) :

- la décision est un commentaire GitHub **portant le jeton `/ok` en tête**, ou
  immédiatement après **une** amorce (« rattaché /ok », « d'accord, /ok ») — la
  position exacte est de la présentation, pas de la décision ; au-delà, le jeton est
  *cité* et ne décide rien (`_token_index`). Casse indifférente. `/unblock` n'est
  **pas** une grammaire : il est ignoré (deux grammaires = une divergence garantie) ;
- la **cible** de la décision est l'enfant, donc la carte que **cet** enfant
  désigne. Elle n'est jamais résolue par le fil ni par un `#N` du ticket parent :
  le lien est porté par `ctx['cards']` (chaque carte porte le numéro d'issue de
  son enfant), pré-alimenté par l'appelant — **aucune passe réseau** ici ;
- l'argument éventuel du commentaire (`/ok t_bbb`) est inerte : la grammaire
  ratifiée est `/ok` seul ;
- un `/ok` **antérieur au re-blocage** (`ctx['last_reopen_comment_id']`) est
  périmé : sinon l'enfant rouverte serait immédiatement re-fermée par le jeton du
  round précédent, toujours présent dans le fil ;
- un `/ok` reçu alors que la carte n'est plus `blocked` ne débloque **rien** : il
  produit un commentaire pour l'humain (jamais d'échec silencieux).

La ligne canonique `carte: <board>/<task_id>` portée par le corps de l'issue
enfant (le pendant de `ROOM:` côté room) est le marqueur de trace de cet objet.
Sa lecture à froid appartient au câblage (slice post-#4) : ici la liaison machine
est `card['issue'] == issue['number']`, telle que le banc la pin.

Sortie : `{effect, task_id, board, note, acted}` avec
`effect ∈ {"ignore", "unblock", "comment"}`.
"""

TOKEN = "/ok"

# Grammaires REFUSÉES : présentes dans la nature (le design précédent les utilisait),
# jamais des décisions. Les reconnaître explicitement évite qu'un futur lecteur les
# réintroduise « pour compatibilité » — la note de refus le dit alors noir sur blanc.
REJECTED_TOKENS = ("/unblock", "/block", "/drop")

EFFECT_IGNORE = "ignore"
EFFECT_UNBLOCK = "unblock"
EFFECT_COMMENT = "comment"

# Effet « comment » : la décision est écrite (trace humaine), rien n'est débloqué.
COMMENT_ACTIVE = ("carte(s) déjà active(s) : décision écrite, rien à débloquer")
COMMENT_NO_CARD = "aucune carte liée à cette issue enfant : rien à débloquer"
COMMENT_AMBIGUOUS = "plusieurs cartes bloquées pour cette enfant : cible indéterminée"


def _decision(effect, task_id=None, board=None, note="", acted=None):
    """Fabrique l'objet de décision (une seule forme pour tous les chemins)."""
    if acted is None:
        acted = effect != EFFECT_IGNORE
    return {"effect": effect, "task_id": task_id, "board": board,
            "note": note, "acted": acted}


def _ignore(note=""):
    return _decision(EFFECT_IGNORE, note=note)


def _first_token(body):
    """Premier élément du corps de commentaire, en minuscules.

    Sert à NOMMER une grammaire refusée (`/unblock`…) dans la note d'ignoré.
    « jeton cité au milieu d'une phrase » n'est pas un acte : `split()` fait foi,
    et l'argument éventuel (`/ok t_bbb`) reste inerte.
    """
    if not body:
        return ""
    parts = str(body).split()
    return parts[0].lower() if parts else ""


# Nombre d'éléments tolérés AVANT le jeton. 1 = « une amorce » : « rattaché /ok »,
# « d'accord, /ok », « +1 /ok ». La position exacte du jeton est de la présentation
# du commentaire, pas de la décision : exiger la toute première place a produit un
# FAUX NÉGATIF mesuré en production (2026-10-06) — un humain a commenté
# « rattaché /ok » en réponse à une instruction qui disait « commenter ici la
# décision », la carte est restée bloquée, et la seule trace était un `ignore` de
# tick, invisible pour lui. Un jeton *cité* reste refusé (cas limite du banc).
TOKEN_PREFIX_MAX = 1


def _token_index(parts):
    """Index du jeton de décision dans `parts`, ou -1 s'il n'est pas porteur d'acte.

    Tête, ou immédiatement après ≤ `TOKEN_PREFIX_MAX` amorce(s). Au-delà le jeton
    est *cité* dans une phrase (« est-ce que /ok est le bon jeton ? ») : c'est une
    question, elle ne décide rien.
    """
    for i, part in enumerate(parts[:TOKEN_PREFIX_MAX + 1]):
        if part.lower() == TOKEN:
            return i
    return -1


def _as_int(value):
    """Entier, ou None si la valeur n'est pas un entier exploitable (`None`, `''`…)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _issue_number(ctx):
    issue = ctx.get("issue") or {}
    return _as_int(issue.get("number") if isinstance(issue, dict) else None)


def _target_cards(ctx):
    """Cartes de `ctx['cards']` liées à CETTE issue enfant (0, 1 ou plusieurs)."""
    number = _issue_number(ctx)
    if number is None:
        return []
    return [c for c in (ctx.get("cards") or [])
            if isinstance(c, dict) and _as_int(c.get("issue")) == number]


def decision_from_comment(ctx: dict, comment: dict) -> dict:
    """Décision portée par `comment` sur l'enfant décrit par `ctx` (aucun effet).

    ctx = {
      "issue": {"number": N, "state": "OPEN"|"CLOSED", ...},
      "cards": [{"task_id": ..., "board": ..., "status": ..., "issue": N}, ...],
      "seen_comment_ids": {ids déjà consommés},
      "last_reopen_comment_id": id | None,   # marqueur de re-blocage
    }

    Ne lève jamais : un corps vide, un ctx partiel ou un commentaire CLOSED
    produisent `effect == "ignore"`.
    """
    ctx = ctx if isinstance(ctx, dict) else {}
    body = comment.get("body") if isinstance(comment, dict) else None
    token = _first_token(body)
    parts = str(body).split() if body else []

    # 1. jeton porteur d'acte — tête du corps, ou immédiatement après une amorce.
    #    Un jeton *cité* en pleine phrase, un corps vide, une grammaire refusée
    #    n'agissent pas.
    if token in REJECTED_TOKENS:
        return _ignore(f"grammaire refusée {token} : seule {TOKEN} décide")
    if _token_index(parts) < 0:
        return _ignore("corps sans jeton porteur d'acte : ignorer")

    cid = _as_int(comment.get("id"))

    # 2. anti-rejeu dans le round : le même commentaire ne débloque pas deux fois.
    if cid is not None and cid in (ctx.get("seen_comment_ids") or set()):
        return _decision(EFFECT_IGNORE, note="commentaire déjà consommé", acted=False)

    # 3. objet de décision clos : plus aucune décision à calculer.
    issue = ctx.get("issue") or {}
    if str(issue.get("state") or "").upper() != "OPEN":
        return _ignore("issue enfant non ouverte : aucune décision")

    # 4. péremption : un /ok antérieur (ou égal) au re-blocage ne vaut plus.
    reopen = _as_int(ctx.get("last_reopen_comment_id"))
    if reopen is not None and (cid is None or cid <= reopen):
        return _ignore("jeton antérieur au re-blocage : périmé")

    # 5. cible = la carte que CET enfant désigne (jamais le fil, jamais un `#N`).
    cards = _target_cards(ctx)
    if not cards:
        return _decision(EFFECT_COMMENT, note=COMMENT_NO_CARD)

    blocked = [c for c in cards if str(c.get("status")) == "blocked"]
    if not blocked:
        return _decision(EFFECT_COMMENT, board=cards[0].get("board"),
                         note=COMMENT_ACTIVE)
    if len(blocked) > 1:
        return _decision(EFFECT_COMMENT, note=COMMENT_AMBIGUOUS)

    card = blocked[0]
    return _decision(EFFECT_UNBLOCK, task_id=card.get("task_id"),
                     board=card.get("board"), note=f"décision {TOKEN} : débloquer la carte")
