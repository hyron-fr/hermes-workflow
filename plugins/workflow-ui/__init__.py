"""workflow dashboard plugin.

This plugin only extends the web dashboard (see ``dashboard/``). The general
plugin loader requires a ``register(ctx)`` entry point; it is a no-op here —
all functionality lives in ``dashboard/`` (UI bundle + backend API routes).
"""


def register(ctx):
    """No-op entry point for the general plugin loader."""
    return None
