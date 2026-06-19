"""The backend interface shared by every engine."""

from dataclasses import dataclass, field


@dataclass
class AgentResult:
    """The result of one agent turn.

    `contract` is the parsed `{"signals": {...}, "done": bool, "verdict": "..."}`
    block the checker is asked to emit (empty for the maker). `text` is the
    agent's full reply; `raw` is the untouched backend output for debugging.
    """

    text: str = ""
    contract: dict = field(default_factory=dict)
    raw: str = ""
    ok: bool = True
    error: str = ""
    tokens: int = 0
    cost: float = 0.0

    @property
    def signals(self):
        if not isinstance(self.contract, dict):
            return {}
        sig = self.contract.get("signals", {})
        # The checker may report a non-object here; never let it crash the runner.
        return sig if isinstance(sig, dict) else {}

    @property
    def done(self):
        return self.contract.get("done") if isinstance(self.contract, dict) else None

    @property
    def verdict(self):
        return self.contract.get("verdict", "") if isinstance(self.contract, dict) else ""


class Backend:
    """Run a single agent turn on one engine."""

    name = "base"

    def is_available(self):
        """True if this engine can run here (e.g. its CLI is installed)."""
        return False

    def run_agent(self, role, prompt, model=None, permission_mode=None, timeout=None):
        """Run one turn. `role` is 'maker' or 'checker'. Returns an AgentResult."""
        raise NotImplementedError

    def describe(self):
        """Short human description for --dry-run."""
        return "%s (available: %s)" % (self.name, self.is_available())
