# Mapping: SLAC → Codex (`/goal`)

How a validated `.slac.md` *lowers* onto OpenAI Codex's loop primitives. This is the
"back-end" of the SLAC compiler for the Codex target.

> Source read for this mapping (Codex repo):
> `codex-rs/core/src/goals.rs`, `codex-rs/core/src/tools/handlers/multi_agents_spec.rs`,
> `codex-rs/state/src/runtime/agent_jobs.rs`, `codex-rs/core/src/config_toml.rs`.

## What `/goal` actually is

A thread-scoped goal in `goals.rs`:

```
Goal {
  objective: String,        // the goal text
  token_budget: Option<..>, // optional ceiling
  status: Active | Paused | Blocked | UsageLimited | BudgetLimited | Complete,
}
```

After each turn while `Active`, a hidden continuation prompt is injected; the model
audits its own progress and calls `update_goal(status="complete")` when it judges
itself done. It stops on budget exhaustion, 3+ blocked turns, or self-declared
completion.

**Crucial gap:** completion is **self-evaluated by the same working model**. The
maker grades its own homework — the exact footgun SLAC's mandatory separate
`checker` removes. Codex's nearest thing to a reviewer is `approvals_reviewer:
{user, auto_review, guardian_subagent}`, but that's a *security* review of escalated
actions, not goal-completion review.

## Field-by-field lowering

| SLAC field | Lowers to | Notes |
|---|---|---|
| `# Goal` + `agents.maker.instructions` | `Goal.objective` | The maker's intent becomes the objective. |
| `budget.tokens` | `Goal.token_budget` | Direct match — triggers `BudgetLimited`. |
| `until` | **a separate checker, not `update_goal`** | SLAC forbids the maker self-declaring done. The engine runs `agents.checker` (a second `spawn_agent`) and evaluates `until` from its report. |
| `agents.maker` | the working model on the thread | — |
| `agents.checker` | a second agent via `spawn_agent` | **Not native to `/goal`.** SLAC adds it; model can differ via the `model` override. |
| `context` | gathered and supplied to the thread | `cmd`/`file`/`okf`/`mcp` resolved to text. |
| `context` (fan-out) | `spawn_agents_on_csv` | When a loop fans out over rows, Codex's CSV job runner (`csv_path`, `instruction`, `max_concurrency`, `max_runtime_seconds`) applies. |
| `state` | a `log.md` on disk | Codex has a SQLite **memories** pipeline; SLAC prefers a portable on-disk `log.md` so the loop is engine-independent. |
| `boundaries` | injected as instructions; `ask` ⇒ `approvals_reviewer` | `never` items become hard rules; `ask` items can route through `auto_review`/`guardian_subagent`. |
| `max_iterations` | a counter in `state` | Codex stops on budget/blocked/complete, not iteration count — SLAC adds the cap. |
| `schedule` | an automation cadence | — |
| `isolation: worktree` | manual | No native git-worktree isolation surfaced; sub-agents run in separate threads, not worktrees. |

## What the engine must add (because `/goal` doesn't)

1. **Replace self-completion with a checker** — do **not** let the maker call
   `update_goal(status="complete")` unchecked. Run `agents.checker` and only mark
   the goal complete when it confirms `until`. This is the single most important
   difference; it's why a SLAC loop on Codex is safer than a bare `/goal`.
2. **Portable state** — write `log.md` rather than relying on Codex's internal
   memories DB, so the same loop runs identically on Claude Code.
3. **Iteration cap** — honor `max_iterations` in addition to `budget`.
