# SLAC diagnostics

Every check the linter (`slac_lint.py`) can emit, with rationale. Diagnostics are
named like **Python exceptions**, and split the way Python splits problems:

- **Errors** behave like a raised `Exception` — they **halt**. The loop is *refused,
  not run*. (`SLACSyntaxError`, `MissingFieldError`, `UnknownFieldError`,
  `TypeError`, `ValueError`)
- **Warnings** behave like the `warnings` module — they **notify** but the loop
  still runs. (`*Warning`)

Each finding carries a **`fixSafety`** label:

| fixSafety | meaning |
|---|---|
| `safe` | mechanically fixable (e.g. a key typo, applying a default) — an agent may auto-apply |
| `review` | a human should glance at it before accepting a fix |
| `needs-human` | a real design gap; only a human can supply the missing intent |

Validation runs in three ordered stages and **stops at the first stage that
produces an error**:

1. **OKF conformance** → 2. **type check (schema)** → 3. **semantic lint**

---

## Errors (halt the loop)

### `SLACSyntaxError`  — *like Python's `SyntaxError`*
The file isn't a well-formed SLAC document at all: no opening `---`, an unclosed
frontmatter block, or frontmatter that isn't a mapping.
`fixSafety: needs-human`.

### `MissingFieldError`  — *like a missing function argument (`TypeError`)*
A required field or body section is absent: `type`, `loop`, `until`, `context`,
`agents.maker`, or the `# Goal` body heading. An empty `context` list counts as
missing.
`fixSafety: needs-human`.

### `UnknownFieldError`  — *like Python's `NameError`*
A frontmatter key that SLAC doesn't define. This is what catches typos — the
linter suggests the nearest real field (`'untill' … did you mean 'until'?`).
`fixSafety: safe`.

### `TypeError`  — *same name as Python*
A field has the wrong type: `context` as a string instead of a list, `agents` as a
list instead of a mapping, a `context` item that is neither a string nor a
single-key `cmd/file/signal/okf/mcp` mapping.
`fixSafety: review`.

### `ValueError`  — *same name as Python*
A field has a valid type but a disallowed value: `type` other than `slac.loop`,
`isolation` not in `{none, worktree}`, a `loop` name that isn't snake_case, a
`max_iterations` below 1.
`fixSafety: review`.

---

## Warnings (loop runs, but it's a footgun)

### `NoCheckerWarning`
A `maker` is defined but no `checker`. The maker would grade its own work — exactly
the weakness we found in Codex `/goal`, where the same model marks its own goal
`complete`. A separate checker is SLAC's whole reason to exist.
*Fix:* add `agents.checker`. `fixSafety: review`.

### `NoStateWarning`
No `state` file. The loop forgets everything between runs ("the model forgets
between runs, so the memory has to be on disk"). It defaults to `./log.md`, but you
should set it explicitly.
*Fix:* add `state: ./log.md`. `fixSafety: safe`.

### `UnreachableStopWarning`
The `until` expression references a signal that nothing produces, so the loop can
never observe it and can never stop on it.
*Fix:* declare the signal with a `context` item `- signal: <name>`, or remove it
from `until`. `fixSafety: review`.

### `NoBoundaryWarning`
No `boundaries.never` list. A loop with no hard stops can do anything — edit public
APIs, delete tests, commit secrets.
*Fix:* add a `boundaries.never` list. `fixSafety: review`.

### `RunawayWarning`
Neither `max_iterations` nor `budget` is set. The loop can run forever.
*Fix:* add `max_iterations`, a `budget`, or both. `fixSafety: review`.

---

## Why named diagnostics instead of numeric codes

Numeric codes (`E501`, `SLAC010`) force you to memorize a lookup table. A name like
`NoCheckerWarning` *is* the explanation. Since SLAC's audience already knows
Python, reusing Python's exception vocabulary means there is no new error language
to learn — a `TypeError` here means what it means everywhere.
