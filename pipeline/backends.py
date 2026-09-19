#!/usr/bin/env python3
"""
Backends d'exécution des étapes agentiques du moteur de pipeline.

Chaque backend transforme (role, prompt, ticket) en une sortie texte
structurée (JSON) renvoyée par un agent externe. Le moteur valide ensuite
cette sortie contre le schéma JSON de l'étape.

Backends supportés :
  - hermes : `hermes -p <profile> chat -q "<prompt>"` (profil + modèle)
  - dsh    : `dsh --profile headless "<prompt>"` (DeepSeek Harness)
  - claude : `claude -p "<prompt>"` (Claude Code CLI, print mode)

Chaque backend est un simple appel subprocess : le moteur n'a pas besoin de
connaître les détails internes de l'agent, seulement comment l'invoquer et
récupérer sa sortie.
"""

import json
import os
import re
import shutil
import subprocess
import sys


def _which(name: str) -> str | None:
    return shutil.which(name)


def _run(cmd: list[str], timeout: int = 600) -> str:
    """Exécute une commande, renvoie stdout, lève sur échec."""
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(
            f"backend {' '.join(cmd[:2])} -> exit {r.returncode}\n"
            f"{r.stderr.strip()[:500]}")
    return r.stdout


def extract_json(text: str) -> dict:
    """Extrait le premier objet JSON d'une sortie d'agent.

    Les agents peuvent préfixer leur JSON par du texte (pensée à voix haute,
    markdown). On cherche le premier bloc `{...}` équilibré.
    """
    # Cas simple : la sortie est déjà du JSON pur.
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Cherche un bloc ```json ... ``` puis un objet brut.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass

    # Dernier recours : scanne tous les objets JSON valides dans la sortie et
    # renvoie le dernier. La sortie d'un backend 'hermes' est un transcript de
    # session (blocs [thinking] + références + réponse) où la prose contient
    # des accolades déséquilibrées ; un simple comptage de profondeur échoue.
    # On utilise raw_decode pour ne retenir que les objets réellement valides.
    #
    # IMPORTANT : le transcript hermes contient plusieurs blocs [thinking]
    # (références multi-modèles), chacun avec du JSON. La VRAIE réponse de
    # l'agent vient APRÈS le dernier [thinking]. On restreint donc le scan au
    # dernier segment (après le dernier marqueur [thinking]) pour ne pas
    # confondre une référence partielle avec la réponse finale.
    segments = re.split(r"\[thinking\]", text)
    if len(segments) > 1:
        text = segments[-1]

    decoder = json.JSONDecoder()
    last = None
    i = 0
    while True:
        start = text.find("{", i)
        if start == -1:
            break
        try:
            obj, end = decoder.raw_decode(text, start)
            last = obj
            i = end
        except json.JSONDecodeError:
            i = start + 1
    if last is not None:
        return last
    raise ValueError("objet JSON non équilibré dans la sortie de l'agent")


def run_hermes(prompt: str, profile: str, model: str | None = None,
               timeout: int = 600) -> str:
    bin_ = _which("hermes") or os.path.expanduser(
        "~/.hermes/hermes-agent/venv/bin/hermes")
    cmd = [bin_, "-p", profile, "chat", "-q", prompt]
    if model:
        cmd += ["-m", model]
    return _run(cmd, timeout=timeout)


def run_hermes_artifact(prompt: str, out_path: str, profile: str = "default",
                        model: str | None = None, timeout: int = 600) -> str:
    """Exécute un agent hermes qui ÉCRIT son JSON dans un fichier.

    Pattern "structured output as artifact" : au lieu de demander à l'agent de
    "rédiger" un JSON dans sa réponse (qu'il faut ensuite parser dans un
    transcript plein de prose), on lui demande d'écrire le JSON dans un fichier
    via son outil write_file. On lit ensuite le fichier — pas de parsing.

    Retourne le contenu du fichier (JSON brut).
    """
    bin_ = _which("hermes") or os.path.expanduser(
        "~/.hermes/hermes-agent/venv/bin/hermes")
    # Prompt augmenté : demande d'écrire le JSON dans out_path.
    artifact_prompt = (
        f"{prompt}\n\n"
        f"IMPORTANT : écris ta réponse JSON dans le fichier {out_path} "
        f"via ton outil d'écriture de fichier (write_file). "
        f"Le fichier doit contenir UNIQUEMENT le JSON valide, sans texte "
        f"autour. Réponds ensuite juste 'fait'."
    )
    cmd = [bin_, "-p", profile, "chat", "-q", artifact_prompt]
    if model:
        cmd += ["-m", model]
    _run(cmd, timeout=timeout)
    # Lit le fichier écrit par l'agent.
    if not os.path.exists(out_path):
        raise RuntimeError(
            f"agent hermes n'a pas écrit le fichier {out_path} "
            f"(outil write_file non utilisé)")
    with open(out_path) as f:
        return f.read()


def run_dsh(prompt: str, profile: str = "headless", timeout: int = 600) -> str:
    bin_ = _which("dsh")
    if not bin_:
        raise RuntimeError("dsh introuvable dans le PATH")
    return _run([bin_, "--profile", profile, prompt], timeout=timeout)


def run_claude(prompt: str, timeout: int = 600) -> str:
    bin_ = _which("claude")
    if not bin_:
        raise RuntimeError("claude introuvable dans le PATH")
    return _run([bin_, "-p", prompt], timeout=timeout)


BACKENDS = {
    "hermes": run_hermes,
    "dsh": run_dsh,
    "claude": run_claude,
}


def run_agent(agent: dict, prompt: str, timeout: int = 600) -> str:
    """Exécute un agent déclaré dans le YAML et renvoie sa sortie brute.

    agent : dict avec au minimum `backend` ; `profile`/`model` selon backend.
    """
    backend = agent.get("backend", "hermes")
    fn = BACKENDS.get(backend)
    if fn is None:
        raise ValueError(f"backend inconnu: {backend!r} "
                         f"(attendu: {', '.join(BACKENDS)})")
    if backend == "hermes":
        return fn(prompt, profile=agent.get("profile", "default"),
                  model=agent.get("model"), timeout=timeout)
    if backend == "dsh":
        return fn(prompt, profile=agent.get("profile", "headless"),
                  timeout=timeout)
    if backend == "claude":
        return fn(prompt, timeout=timeout)
    raise ValueError(f"backend non géré: {backend!r}")


if __name__ == "__main__":
    # Test rapide : echo du JSON d'un agent dsh.
    print(run_agent({"backend": "dsh"},
                    "Réponds uniquement par le JSON exact: {\"ok\": true}"))
