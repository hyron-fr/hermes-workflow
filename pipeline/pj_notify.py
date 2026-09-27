#!/usr/bin/env python3
"""Émetteur des DEUX notifications d'une décision humaine `/ok` (issue #5, slice 5).

Décision ratifiée par JB le 20/09 (« le nœud fils est notifié et terminé, et le
parent aussi pour dire qu'il avance et est débloqué ») : une décision acquise doit
être **visible des deux côtés** — sur l'objet de décision (l'issue enfant) et sur
le suivi du ticket (l'issue parent).

Ce module est PUR : il ne connaît ni `gh`, ni le board, ni l'horloge. Les trois
effets (commenter, fermer, tracer) sont **injectés** par l'appelant — c'est ce qui
rend `tests/test_notify_2_niveaux.py` rejouable hors ligne, donc falsifiable.

Contrat (gelé par le banc de la carte sœur `test (RED)`, clé `contrat-notify-5`) :

- `decision_key(decision, ctx)` — clé de dédup, fonction PURE et DÉTERMINISTE du
  couple (carte, id du commentaire `/ok`). **Jamais l'horloge** : le risque ratifié
  est une boucle de notifications, la dédup doit donc porter sur la décision, pas
  sur le tick. Un re-blocage produit un NOUVEAU commentaire, donc une NOUVELLE clé.
- `notify_decision(decision, ctx, effects)` — porte les deux notifications d'une
  décision **déjà appliquée**, et **ne lève jamais** : la décision est acquise, un
  échec de notification ne la remet pas en cause et n'est jamais silencieux
  (l'échec est rapporté dans `errors` ET tracé sur la carte).

Ordre contractuel : l'enfant est **notifié puis fermé** (fermer avant de notifier
effacerait la trace de la décision pour l'humain qui a répondu). Le parent est
notifié, **jamais fermé** — une décision de carte ne clôt pas le ticket.

Sortie :

    {"decision_key", "skipped", "child_notified", "child_closed",
     "parent_notified", "parent_issue", "errors", "traced"}

`errors = [{"step": "child_notify"|"child_close"|"parent", "issue": int|None,
            "reason": str}]`

Aucun import : le module ne charge ni réseau, ni LLM, ni `subprocess` (garde-fou
hexagonal, mesuré par exécution sous sentinelle d'import).
"""

TASK_UNBLOCK = "unblock"

# Marqueurs de message. Deux niveaux, deux textes distincts : l'enfant dit que SA
# décision est enregistrée, le parent dit où en est le TICKET. Le banc pin la
# présence du marqueur côté enfant (« décision enregistrée »).
CHILD_MARKER = "Décision enregistrée"
PARENT_MARKER = "Avancement"


def _as_int(value):
    """Entier exploitable, ou None (jamais d'exception sur une forme inattendue)."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    if isinstance(value, dict):
        return _as_int(value.get("number"))
    return None


def _task_of(decision, ctx):
    card = ctx.get("card") if isinstance(ctx.get("card"), dict) else {}
    return card.get("task_id") or decision.get("task_id") or ""


def _board_of(decision, ctx):
    card = ctx.get("card") if isinstance(ctx.get("card"), dict) else {}
    return card.get("board") or decision.get("board") or ""


def decision_key(decision, ctx):
    """Clé de dédup d'une décision — pure, déterministe, sans horloge.

    Elle porte les trois dimensions qui font qu'une décision est une décision
    DIFFÉRENTE : la carte, l'issue enfant (l'objet de décision) et l'id du
    commentaire `/ok`. C'est ce dernier qui rend un re-blocage notifiable (nouveau
    commentaire ⇒ nouvelle clé) tout en rendant un rejeu muet (même commentaire ⇒
    même clé), sans jamais lire le temps.
    """
    decision = decision if isinstance(decision, dict) else {}
    ctx = ctx if isinstance(ctx, dict) else {}
    child = ctx.get("child_issue") if isinstance(ctx.get("child_issue"), dict) else {}
    comment = ctx.get("decision_comment") if isinstance(ctx.get("decision_comment"), dict) else {}
    return "{}#{}#{}#{}".format(_board_of(decision, ctx), _task_of(decision, ctx),
                                _as_int(child.get("number")), _as_int(comment.get("id")))


def _anchor(ctx, child):
    """Ancre EXACTE du point de statuer : l'URL du commentaire `/ok` de l'enfant.

    C'est le lien que l'humain doit pouvoir ouvrir depuis le ticket pour retrouver
    la décision qu'il a rendue. Repli sur la forme `issues/<n>#issuecomment-<id>`
    quand l'appelant n'a pas transmis d'URL.
    """
    raw = ctx.get("decision_comment")
    comment = raw if isinstance(raw, dict) else {}
    url = comment.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return "issues/{}#issuecomment-{}".format(child, _as_int(comment.get("id")))


def _child_body(task_id, board, key):
    return (
        "✅ **{}.**\n\n"
        "Le commentaire de décision de ce fil a été appliqué : la carte `{}` "
        "(board `{}`) est débloquée et repart en file.\n\n"
        "Cette issue de décision est fermée — la suite se lit sur le fil du ticket.\n\n"
        "_Trace de décision : `{}`_".format(CHILD_MARKER, task_id, board, key)
    )


def _parent_body(task_id, board, child, anchor):
    return (
        "📈 **{} — la carte `{}` est débloquée.**\n\n"
        "La décision humaine du fil de l'issue enfant (#{}) a été appliquée : la "
        "carte `{}` du board `{}` repart en file. Le ticket continue, aucune "
        "décision n'est plus attendue sur ce point.\n\n"
        "Point de statuer (décision) : {}".format(
            PARENT_MARKER, task_id, child, task_id, board, anchor)
    )


def _failure(errors, step, issue, reason):
    errors.append({"step": step, "issue": issue, "reason": str(reason)[:300]})


def notify_decision(decision, ctx, effects):
    """Porte les deux notifications d'une décision DÉJÀ appliquée. Ne lève jamais.

    `decision` : la sortie de `pj_decision.decision_from_comment`. Seul
    `effect == "unblock"` notifie — `comment`/`ignore` n'ont débloqué aucune carte,
    ils n'émettent donc rien (`skipped`) : notifier un déblocage qui n'a pas eu lieu
    serait un mensonge dans le fil du ticket.

    `ctx['notified']` est LU puis MIS À JOUR : la clé de la décision y est ajoutée
    dès que la décision a été portée, y compris si un effet a échoué. Un échec tracé
    ne doit pas transformer la dédup en boucle de re-notification à chaque tick —
    c'est le plan de repli ratifié (« notifier une seule fois par décision et tracer
    l'état »).

    Chaque effet est porté sous son propre `try` : un fil indisponible (retour
    `False` **ou** exception) n'emporte ni le tick, ni les autres étapes.
    """
    decision = decision if isinstance(decision, dict) else {}
    ctx = ctx if isinstance(ctx, dict) else {}
    effects = effects if isinstance(effects, dict) else {}

    key = decision_key(decision, ctx)
    out = {"decision_key": key, "skipped": False, "child_notified": False,
           "child_closed": False, "parent_notified": False, "parent_issue": None,
           "errors": [], "traced": False}

    # 1. Décision sans effet : rien n'a été débloqué, rien n'est notifié.
    if decision.get("effect") != TASK_UNBLOCK:
        out["skipped"] = True
        return out

    task_id = _task_of(decision, ctx)
    board = _board_of(decision, ctx)

    # 2. Anti-rejeu : la MÊME décision ne notifie qu'une fois (état inter-ticks).
    notified = ctx.get("notified")
    if isinstance(notified, (set, list, tuple, frozenset)):
        if key in notified:
            out["skipped"] = True
            return out

    child = _as_int((ctx.get("child_issue") or {}).get("number")) \
        if isinstance(ctx.get("child_issue"), dict) else None
    parent = _as_int(ctx.get("parent_issue"))
    out["parent_issue"] = parent

    comment = effects.get("comment")
    close = effects.get("close")

    # 3. ENFANT — notifié, PUIS fermé (l'ordre est contractuel).
    if child is not None and callable(comment):
        try:
            ok = comment(child, _child_body(task_id, board, key))
            if ok:
                out["child_notified"] = True
            else:
                _failure(out["errors"], "child_notify", child,
                         "commentaire refusé par le fil de l'enfant")
        except Exception as exc:
            _failure(out["errors"], "child_notify", child,
                     "{}: {}".format(type(exc).__name__, exc))
    elif child is not None:
        _failure(out["errors"], "child_notify", child, "aucun effet 'comment' injecté")

    if child is not None and callable(close):
        try:
            ok = close(child)
            if ok:
                out["child_closed"] = True
            else:
                _failure(out["errors"], "child_close", child,
                         "fermeture refusée par le fil de l'enfant")
        except Exception as exc:
            _failure(out["errors"], "child_close", child,
                     "{}: {}".format(type(exc).__name__, exc))

    # 4. PARENT — notifié, jamais fermé. Introuvable = doute tracé, pas silence.
    if parent is None:
        _failure(out["errors"], "parent", None,
                 "fil parent introuvable : aucune issue parente dans le contexte")
    elif callable(comment):
        try:
            ok = comment(parent, _parent_body(task_id, board, child, _anchor(ctx, child)))
            if ok:
                out["parent_notified"] = True
            else:
                _failure(out["errors"], "parent", parent,
                         "commentaire refusé par le fil du parent")
        except Exception as exc:
            _failure(out["errors"], "parent", parent,
                     "{}: {}".format(type(exc).__name__, exc))
    else:
        _failure(out["errors"], "parent", parent, "aucun effet 'comment' injecté")

    # 5. Jamais silencieux : le doute est TRACÉ sur la carte. Un `trace` qui échoue
    #    lui-même ne relève pas l'erreur (le tick reste vivant) et laisse
    #    `traced=False` — l'état est donc lisible, pas invisible.
    if out["errors"]:
        trace = effects.get("trace")
        if callable(trace):
            try:
                trace(task_id, _trace_message(out["errors"], key))
                out["traced"] = True
            except Exception:
                out["traced"] = False

    # 6. La décision est portée : sa clé est enregistrée, échec ou non.
    if isinstance(notified, set):
        try:
            notified.add(key)
        except Exception:
            pass

    return out


def _trace_message(errors, key):
    lignes = "; ".join("{}#{} : {}".format(e["step"], e["issue"], e["reason"])
                       for e in errors)
    return "notification de décision incomplète ({}) — {}".format(key, lignes)
