# Running a SLAC loop in Codex

A `.slac.md` file is a **loop definition**, not something you execute line by line.
Your job is to be the *engine*: validate it, then drive the loop the spec describes
on top of OpenAI Codex's `/goal` primitive — while patching the one place `/goal`
is unsafe.

## Step 1 — Validate first (never skip)

A malformed loop wastes a run. Always lint before executing:

```bash
slac lint --json THE_FILE.slac.md      # or: python3 path/to/linter/slac_lint.py --json THE_FILE.slac.md
```

- Any **error** (`MissingFieldError`, `UnknownFieldError`, `TypeError`,
  `ValueError`, `SLACSyntaxError`) → **do not run**. Fix it. For findings with
  `"fixSafety": "safe"` (e.g. a key typo) you may apply the fix yourself; for
  `review`/`needs-human`, ask the user.
- **Warnings** (`NoCheckerWarning`, etc.) → surface them, but you may proceed if
  the user accepts the risk.

## Step 2 — Lower the loop onto Codex `/goal`

Parse the frontmatter + body and map it onto Codex primitives:

- `# Goal` + `agents.maker.instructions` → the `/goal` `objective`.
- `budget.tokens` → `token_budget` (triggers `BudgetLimited`).
- `agents.maker` → the working agent on the thread.
- `agents.checker` → a SEPARATE agent via `spawn_agent` (different instructions,
  often `mode: refute`; `model` may differ). **Not native to `/goal` — you add it.**
- `context` → resolve `cmd`/`file`/`okf`/`mcp` to text and supply it to the thread
  fresh **every iteration**. Loops that fan out over rows use `spawn_agents_on_csv`.
- `state` (default `./log.md`) → write a portable on-disk `log.md`. Prefer this over
  Codex's internal SQLite **memories** so the same loop runs identically elsewhere.
- `boundaries` → injected as instructions; `never` = hard rules, `always` = do freely,
  `ask` items route through `approvals_reviewer` (`auto_review`/`guardian_subagent`).
- `max_iterations` → a counter in `state`, honored **alongside** `budget` (Codex
  stops on budget/blocked/complete, not iteration count — you add the cap).

## Step 3 — Execute the loop

Each iteration:

1. Read `state` (`log.md`) so the loop remembers prior runs.
2. Fetch `context` fresh.
3. Run the **maker** (the working thread), within `boundaries`.
4. Run the **checker** as a *separate* `spawn_agent`; have it report the `until`
   signals (e.g. `ci.green`, `tests.passed`) or judge prose `until` directly.
5. Evaluate `until`. If met → call `update_goal(status="complete")` and append the
   outcome to `state`. **STOP (done).**
6. Else append progress to `state`, increment the counter, and if
   `iteration > max_iterations` or `budget` is exhausted → **STOP (limit).**

## The one rule that matters

Codex's `/goal` injects a continuation prompt after each turn and lets the **same
working model** call `update_goal(status="complete")` — the maker grading its own
homework. **SLAC forbids this.** Do not let the maker self-declare done. Run the
separate `checker` and call `update_goal(status="complete")` only when it confirms
`until`. Codex's `approvals_reviewer` is a *security* review of escalated actions,
not goal-completion review — it does not substitute for the checker.

That maker/checker separation is the whole point of SLAC, and it's exactly what a
bare `/goal` lacks. See `mappings/codex.md` in the SLAC repo for the field-by-field
lowering onto `Goal`, `spawn_agent`, and `spawn_agents_on_csv`.
