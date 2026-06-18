---
name: run-slac-loop
description: >
  Run an agentic coding loop defined in a .slac.md file. Use when the user asks
  to "run", "start", or "kick off" a SLAC loop, or points at a *.slac.md file.
  Validates the loop, then executes it by lowering onto Claude Code's /loop cron
  and maker/checker subagents.
---

# Running a SLAC loop in Claude Code

A `.slac.md` file is a **loop definition**, not something you execute line by line.
Your job is to be the *engine*: validate it, then drive the loop the spec describes.

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

## Step 2 — Read the loop into a run plan

Parse the frontmatter + body and extract:

- `# Goal` and `agents.maker.instructions` → the maker's task
- `context` → fetch each item (`cmd` output, `file` globs, `okf` links, `mcp`
  queries) fresh **every iteration**
- `agents.checker` → a SEPARATE verifier (different instructions, often
  `mode: refute`). **Never let the maker decide it's done.**
- `until` → the stop condition (a Python boolean over signals, or prose)
- `boundaries` → `never` = hard rules, `ask` = pause for approval, `always` = do freely
- `state` (default `./log.md`) → read it at the start of each iteration
- `max_iterations` / `budget` → hard caps

## Step 3 — Execute the loop

Each iteration:

1. Read `state` (`log.md`) so you remember prior runs.
2. Fetch `context`.
3. Run the **maker** as a subagent, within `boundaries`.
4. Run the **checker** as a *separate* subagent; have it report the `until`
   signals (e.g. `ci.green`, `tests.passed`) or judge prose `until` directly.
5. Evaluate `until`. If met → **STOP (done)**. Append the outcome to `state`.
6. Else append progress to `state`, increment the counter, and if
   `iteration > max_iterations` or the `budget` is exhausted → **STOP (limit)**.

If the loop has a `schedule`, register it with `/loop` so it re-fires on cadence;
the per-fire prompt is the maker task plus the freshly fetched context.

## The one rule that matters

The maker and checker MUST be different agents with different instructions. Claude
Code's `/loop` does not enforce this on its own — that separation is the whole point
of SLAC. A loop that lets the writer grade its own work is the failure mode this
skill exists to prevent.

See `mappings/claude-code.md` in the SLAC repo for the field-by-field lowering onto
`CronTask` and subagents.
