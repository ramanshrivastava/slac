"""Execution backends for `slac run`.

Each backend knows how to run one agent turn on a given engine. The default
backends shell out to the CLIs the user is already logged into (`claude`,
`codex`) — no API key, no separate metered billing.
"""

from .base import AgentResult, Backend
from .claude_cli import ClaudeCLIBackend

# Registry of available backends by name.
_BACKENDS = {
    ClaudeCLIBackend.name: ClaudeCLIBackend,
}

try:  # codex backend lands in Phase C; tolerate its absence.
    from .codex_cli import CodexCLIBackend

    _BACKENDS[CodexCLIBackend.name] = CodexCLIBackend
except ImportError:
    pass


def get_backend(name):
    """Instantiate a backend by name (e.g. 'claude_cli'). Raises KeyError if unknown."""
    if name not in _BACKENDS:
        raise KeyError(
            "unknown engine %r (available: %s)"
            % (name, ", ".join(sorted(_BACKENDS)))
        )
    return _BACKENDS[name]()


def available_backends():
    return sorted(_BACKENDS)


__all__ = ["AgentResult", "Backend", "ClaudeCLIBackend", "get_backend",
           "available_backends"]
