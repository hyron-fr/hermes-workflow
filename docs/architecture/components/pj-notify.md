---
type: component
status: draft
tags: [architecture, decision-interface, core-pur, hexagonal, notify-2-niveaux, issue-5]
issues: [5]
---

# Composant — `pipeline/pj_notify.py` (émetteur des DEUX notifications d'une décision `/ok`)

> Note de vault produite par `doc-k` (slice 5 `notify-2-niveaux`, vague finale de l'issue
> #5). Elle décrit le **livré** — le module tel que convergé au HEAD `b3ee580` (byte-
> identique au GREEN `88c79b8` re-mesuré en convergence, 93,33 % de couverture) —
> jamais une intention. Le cadrage ([[issue-5]]) positionne l'issue ; cette note fige le
> **contrat exact** de l'émetteur de notification et, surtout, la **règle des deux
> niveaux** qu'il porte.

## Ce que la slice 5 livre — et ce qu'elle ne livre PAS

La carte sœur (`test (RED)`, clé `contrat-notify-5`) et la convergence tranchent le
périmètre : la slice 5 livre **l'émetteur**, pas son câblage.

- **Livrée** : `pipeline/pj_notify.py` (neuf, 248 lignes, **zéro import**) — le module
  **pur** qui porte les deux notifications d'une décision déjà appliquée — et son banc
  `tests/test_notify_2_niveaux.py` (**28 cas**). Le GREEN `88c79b8` n'a touché que
  `pipeline/pj_notify.py` ; le RED `6b9d617` + renforts `750226f`/`b3ee580` le banc.
- **Non livrée** : le **câblage dans le pont**. Mesuré, `grep -rn 'pj_notify\|notify_decision\|decision_key'`
  sur `bridge/` + `pipeline/` (hors le module) → **0 hit** : aucune production ne
  connaît encore `pj_notify`. Ce n'est **pas** un défaut de la slice — c'est la même
  asymétrie test↔production que la slice 4 ([[pj-decision]]) a déjà consignée pour
  `pj_decision` : le module est **versionné et testé**, il n'est **pas encore appelé**.
  Son câblage (lire le `/ok`, appeler `notify_decision` avec les effets `gh`/`kanban`)
  appartient à la **slice de câblage** (post-#4, issue #4 — `pj_escalate.py`), hors de
  cette PR. **Consigné comme écart non bloquant** ci-dessous, à ne pas laisser croire
  câblé.

## Ce que le module EST

`pipeline/pj_notify.py` est l'**émetteur** des deux notifications d'une décision `/ok`
ratifiée par JB le 20/09 : *« le nœud fils est notifié et terminé, et le parent aussi
pour dire qu'il avance et est débloqué »*. Il est **pur** : il ne connaît ni `gh`, ni le
board, ni l'horloge. Les trois effets (commenter, fermer, tracer) sont **injectés** par
l'appelant (`effects`) — c'est ce qui rend le banc rejouable hors ligne, donc
**falsifiable**. Zéro import module-level (mesuré : `grep -nE '^(import|from) '` → 0
ligne), zéro LLM, zéro réseau : la pureté est prouvée par **exécution** (sentinelles
`sys.meta_path` + `builtins.__import__`), pas par lecture de texte.

Deux fonctions publiques :

- `decision_key(decision, ctx) -> str` — la clé de dédup (voir § dédup).
- `notify_decision(decision, ctx, effects) -> dict` — porte les deux notifications
  d'une décision **déjà appliquée** ; **ne lève jamais**.

## Les DEUX niveaux de notification — qui est notifié, où

Le module porte **deux** notifications distinctes, avec **deux textes distincts**
(constantes gelées par le banc) et **deux cibles** différentes :

| niveau | cible (où) | texte (marqueur gelé) | geste | fermé ? |
|---|---|---|---|---|
| **1 — l'enfant** | l'issue **enfant** (l'objet de décision, label `decision`) | `✅ **Décision enregistrée.** …` (`CHILD_MARKER`) | notifier **puis** fermer | **oui**, l'enfant est fermée |
| **2 — le parent** | l'issue **parent** (le ticket de suivi) | `📈 **Avancement — la carte X est débloquée.** …` (`PARENT_MARKER`) | notifier | **non**, le ticket continue |

- **Niveau 1 (l'enfant)** : la carte `{task_id}` (board `{board}`) est débloquée et
  repart en file ; cette issue de décision est **fermée** — « la suite se lit sur le fil
  du ticket ». Le message cite la **clé de dédup** (`_Trace de décision : <key>`) pour
  qu'elle soit lisible à froid.
- **Niveau 2 (le parent)** : le ticket avance — la décision humaine du fil de l'enfant
  (`#{child}`) a été appliquée, la carte repart, « aucune décision n'est plus attendue
  sur ce point ». Le message cite le **point de statuer exact** (`_anchor`), jamais une
  autre URL.

**Deux niveaux, deux textes distincts, jamais un seul** : l'enfant dit que **sa**
décision est enregistrée, le parent dit où en est le **ticket**. Le banc pin la
présence du marqueur côté enfant (`nominal_l_enfant_recoit_la_decision_enregistree`) et
le fait que le parent cite la carte débloquée
(`nominal_le_parent_recoit_l_avancement_qui_cite_la_carte`).

### L'ordre est contractuel (enfant)

L'enfant est **notifié, puis fermé**. Fermer **avant** de notifier effacerait la trace
de la décision pour l'humain qui a répondu (mutant `M17_close_avant_notify`, tué). Le
parent est **jamais fermé** — une décision de carte ne clôt pas le ticket
(mutant `M10_parent_ferme`, tué).

### L'ancre exacte du point de statuer

`_anchor(ctx, child)` rend l'**URL du commentaire `/ok` de l'enfant** — le lien que
l'humain doit pouvoir ouvrir depuis le ticket pour retrouver la décision qu'il a rendue.
Repli déterministe `issues/<n>#issuecomment-<id>` quand l'appelant ne transmet pas
d'URL. L'ancre est jugée **caractère pour caractère** sur l'URL fournie
(`nominal_l_ancre_ecrite_est_l_url_fournie_caractere_pour_caractere`) et **ne suit pas**
un repli voisin d'un commentaire étranger (`limite_l_ancre_suit_le_commentaire_courant`
/ `erreur_ancre_etrangere_ecrite_telle_quelle`) — le trou M5, fermé par `b3ee580`.

## La règle de dédup — par décision, jamais par horloge

Le risque ratifié est une **boucle de notifications** si le parent re-notifie à chaque
tick. La dédup porte donc **sur la décision, jamais sur l'horloge** :

- `decision_key = "board#task#child_number#comment_id"` — fonction **pure et
  déterministe** du couple (carte, id du commentaire `/ok`). Les trois dimensions qui
  font qu'une décision est une décision **différente** : la carte, l'issue enfant, et
  l'id du commentaire.
- **Un re-blocage produit un NOUVEAU commentaire ⇒ une NOUVELLE clé** ⇒ re-notifiable
  (`limite_un_reblocage_est_une_nouvelle_decision`).
- **Un rejeu porte le MÊME commentaire ⇒ la MÊME clé** ⇒ muet
  (`limite_aucune_notification_deux_fois_pour_la_meme_decision`).
- **Aucune horloge lue** : le module ne charge ni `time`, ni `datetime`, ni `random`,
  ni `sleep` (mesuré + verrouillé par `erreur_l_emetteur_ne_lit_aucune_horloge`).

La clé est enregistrée dans `ctx['notified']` (état **inter-ticks**, un `set`), **lu
puis mis à jour par l'appelant** — le module ne le crée pas, il l'ajoute. C'est cet
état qui rend le rejeu muet d'un tick à l'autre sans jamais lire le temps.

## La règle de non-blocage — une notification ratée ne retient pas une décision déjà acquise

`notify_decision` **ne lève jamais**. La décision est **acquise** avant que la
notification ne soit portée ; un échec de notification :

- **ne la remet pas en cause** (la carte reste débloquée, l'enfant reste fermée — le
  comportement nominal est tenu quel que soit l'échec d'un fil) ;
- **n'est jamais silencieux** : l'échec est **rapporté dans `errors`** ET **tracé sur la
  carte** via `effects['trace'](task_id, message)` (`out['traced'] = True`).

C'est le **plan de repli ratifié** : « notifier une seule fois par décision et tracer
l'état ». Concrètement, la clé de la décision est ajoutée à `ctx['notified']` **dès
que la décision a été portée, y compris si un effet a échoué** — un échec tracé ne doit
pas transformer la dédup en boucle de re-notification à chaque tick.

## Ce qui se passe si un fil est indisponible

Chaque effet est porté **sous son propre `try`** : un fil indisponible (retour `False`
**ou** exception) **n'emporte ni le tick, ni les autres étapes**.

- **Fil enfant indisponible** (commentaire ou fermeture refusée) → `errors` gagne
  `{step: "child_notify"|"child_close", issue, reason}` ; le **parent est quand même
  notifié** ; le tick continue (`erreur_enfant_indisponible_l_echec_est_trace`,
  `erreur_fermeture_de_l_enfant_refusee_est_tracee`).
- **Fil parent introuvable** (`ctx['parent_issue']` absent/`None`) → `errors` gagne
  `{step: "parent", issue: None, reason: "fil parent introuvable …"}` ; l'**enfant est
  quand même notifiée puis fermée** comme en nominal ; la décision **reste acquise** et
  est **tracée** (`erreur_parent_introuvable_la_decision_reste_acquise_et_est_tracee`,
  `erreur_parent_indisponible_l_echec_est_trace_jamais_silencieux`). **« Introuvable =
  doute tracé, pas silence. »**
- **Tout échoue** → le tick **ne lève jamais** (`erreur_le_tick_ne_leve_jamais_meme_quand_tout_echoue`).

Aucune écriture dans un fil d'un **autre** ticket
(`limite_aucune_ecriture_dans_le_fil_d_un_autre_ticket`) : chaque notification est
ciblée sur son propre issue.

## Contrat d'entrée / sortie

`notify_decision(decision, ctx, effects) -> dict` :

- `decision` : la sortie de `pj_decision.decision_from_comment`. **Seul
  `effect == "unblock"` notifie** — `comment`/`ignore` n'ont débloqué aucune carte, ils
  n'émettent donc rien (`out["skipped"] = True`) : notifier un déblocage qui n'a pas eu
  lieu serait un mensonge dans le fil du ticket
  (`erreur_une_decision_qui_n_a_pas_debloque_n_emet_rien`,
  `erreur_une_decision_ignoree_n_emet_rien`).
- `ctx` (dict, pré-alimenté par l'appelant, **aucune passe réseau**) : `card`
  (`task_id`, `board`), `child_issue` (`number`), `parent_issue` (`number` ou `None`),
  `decision_comment` (`id`, `url`), `notified` (état inter-ticks, `set`/liste).
- `effects` (dict de **callable injectés** par l'appelant) : `comment(issue, body)`,
  `close(issue)`, `trace(task_id, message)`.

Sortie — un dict, toujours :

```
{"decision_key", "skipped", "child_notified", "child_closed",
 "parent_notified", "parent_issue", "errors", "traced"}
errors = [{"step": "child_notify"|"child_close"|"parent",
           "issue": int|None, "reason": str}]
```

## Lecture hexagonale

Le module est le **core pur** de la **visibilité** de la décision : il manipule des
dicts/chaînes, **sans** GitHub, kanban, Discord, réseau ni horloge. Les **adapters**
(`gh` pour commenter/fermer les issues, le pont ou `pj_escalate` pour fournir le
`ctx`/les `effects`) restent en périphérie et ne portent **aucune** logique de
notification : ils injectent les effets. La dédup (par décision) et le non-blocage
(ne lève jamais, échec tracé) vivent ici, dans le core, pour être **testables hors
ligne**. Le module ne traverse **aucune** frontière : c'est le point où la frontière
est **franchie par l'appelant**, pas par lui.

## Convergence (slice 5) — mesures reprises telles quelles

- **Tests** : `python3 -m pytest tests/test_notify_2_niveaux.py -q` → **`28 passed`**
  sur l'arbre courant (HEAD `b3ee580` == `origin`) : 7 nominal / 8 limite / 9 erreur /
  4 garde-fou. Suite complète **`235 passed`**.
- **Couverture** : **93,33 %** (98/105 statements) sur `pipeline/pj_notify.py` > seuil
  80 % ; gate diff-scope `rc=0` sur périmètre ∩ rapport ; **non-viduité** prouvée par
  `--min 99.9` → `rc=1`. Lignes non atteintes `56, 59, 190, 191, 221, 239, 240`
  (branches **défensives**). Aucune exclusion, aucun seuil baissé.
- **Mutation** : 4 mutants **tués** avec 2 témoins par mutation — `M5_ancre_url_ignoree`
  (3 rouges), `M9_cle_sans_carte` (1 rouge), `M17_close_avant_notify` (1 rouge),
  `M10_parent_ferme` (1 rouge) ; 0 survivant ; contrôle négatif byte-identique inerte
  (28 passed).
- **RED re-mesuré** sur clones jetables : module **absent** → `rc=1`
  (1 failed + 26 errors « module versionné absent ») ; module **présent** → `rc=0`
  (28 passed). Le module était ABSENT au commit RED `6b9d617`, PRÉSENT au GREEN
  `88c79b8`.
- **Déterminisme / pureté** : 0 horloge (`time`/`datetime`/`random`/`sleep`), 0 LLM,
  0 import hors stdlib (en fait **0 import**). Provenance : `module_sha` à jour du
  blob de HEAD.

## Écarts non bloquants consignés (à ne pas laisser croire câblés/résolus)

1. **Asymétrie test ↔ production (maillon de câblage)** — le module est **versionné et
   testé**, mais **aucun consommateur de production n'existe** :
   `grep -rn 'pj_notify\|notify_decision\|decision_key'` hors le module et hors `tests/`
   → **0 hit**. Le **câblage dans le pont** (lire le `/ok`, alimenter `ctx`, appeler
   `notify_decision` avec les effets `gh`/`kanban` réels) n'est **pas** livré par la
   slice 5 et **ne fait pas partie de cette PR** : il relève de la **slice de câblage**
   (post-#4, issue #4 — `pj_escalate.py`, non versionné). Conséquence assumée et
   documentée : la PR de #5 rend l'émetteur **testable et versionné**, mais **ne notifie
   encore aucune décision en production** tant que le câblage n'est pas installé.
   **NON câblé** (déjà déclaré par la convergence `P8 : 0 commit slice 5 sur le
   pont`).
2. **Dette de couverture du pont** (non slice 5) — le gate du périmètre **total** du
   diff nomme `bridge/gh_kanban_bridge.py` à **72,22 %** < 80 % ; dette des slices
   2/3/2b (0 commit de la slice 5 dessus, mesuré par git), portée par la convergence
   2b (`t_f7e87436`). Aucune exclusion, aucun seuil baissé ici.

## Frontières (résumé)

```
décision /ok déjà appliquée (pj_decision → unblock)      [core de décision]
  → (pj_notify.notify_decision) les DEUX notifications, dédup par décision,
      ne lève jamais, échec tracé                          [core pur de visibilité]
      ├── niveau 1 : issue ENFANT → "Décision enregistrée" → fermée   [GitHub]
      └── niveau 2 : issue PARENT → "Avancement — débloquée" (jamais fermée) [GitHub]
  → (appelant, hors module) effets comment/close/trace injectés        [adapters]
```

Le module traverse **GitHub** (commenter/fermer l'enfant et le parent) **sans nouveau
port** : il réutilise le canal GitHub déjà lu par le pont, en ajoutant une **voie
d'écriture** (la visibilité de la décision) là où il n'y avait qu'une voie de lecture
(l'escalade). Les deux niveaux partagent **une** règle de dédup (par décision, jamais
par horloge) et **une** règle de non-blocage (une notification ratée ne retient pas une
décision déjà acquise, et n'est jamais silencieuse).
