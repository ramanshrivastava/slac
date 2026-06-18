# Mapping: SLAC → Claude Code (`/loop`)

How a validated `.slac.md` *lowers* onto Claude Code's loop primitives. This is the
"back-end" of the SLAC compiler for the Claude Code target.

> Source read for this mapping (Claude Code repo):
> `src/skills/bundled/loop.ts`, `src/utils/cronScheduler.ts`,
> `src/utils/cronTasks.ts`, `src/tools/ScheduleCronTool/`.

## What `/loop` actually is

`/loop` is **interval cron**. It registers a `CronTask` that re-enqueues a prompt on
a cadence and auto-expires after ~7 days. From `cronTasks.ts`, a task is:

```ts
type CronTask = {
  id: string            // 8-char id
  cron: string          // 5-field cron, local time
  prompt: string        // the prompt re-enqueued each fire
  createdAt: number
  lastFiredAt?: number
  recurring?: boolean
  permanent?: boolean
  durable?: boolean     // persisted to .claude/scheduled_tasks.json
  agentId?: string      // route the fire to a teammate/subagent
}
```

`loop.ts` parses an interval (`5m`, `every 20m`, default `10m`) and converts it to a
cron string; `cronScheduler.ts` polls every second and reschedules from now after
each fire.

**Crucial gap:** `/loop` has **no completion evaluation**. It stops only on explicit
`CronDelete` or 7-day expiry. It never asks "was the goal met?" That is the job SLAC
adds on top.

## Field-by-field lowering

| SLAC field | Lowers to | Notes |
|---|---|---|
| `schedule` | `CronTask.cron` | `15m` → `*/15 * * * *`; `daily` → `0 0 * * *`. Omitted ⇒ run once now. |
| `agents.maker` | the prompt body of the fired task (or a subagent) | The maker's `instructions` + `# Goal` + fetched `context` become the prompt. |
| `agents.checker` | a **second** subagent run, gated before "done" | **Not native.** The engine must run the checker after the maker and only treat the loop as done if the checker confirms `until`. This is the part `/loop` lacks. |
| `until` (expression) | engine-side boolean eval after the checker reports signals | `/loop` can't do this itself; the SLAC engine evaluates it and calls `CronDelete` when true. |
| `until` (prose) | checker subagent judges, returns done/not-done | — |
| `context` | gathered before each fire, prepended to the prompt | `cmd`/`file`/`okf`/`mcp` resolved to text. |
| `state` | a `log.md` on disk, read at fire start, appended at end | Mirrors Addy's "memory on disk." `/loop` itself is stateless between fires. |
| `boundaries` | injected into the maker/checker prompts as rules | `ask` items should map to permission prompts where possible. |
| `max_iterations` | a counter in `state`; `CronDelete` when exceeded | `/loop`'s only native stop is the 7-day `recurringMaxAge`. |
| `budget` | not natively enforced | Track approximate tokens in `state`; stop when exceeded. |
| `isolation: worktree` | run the maker in a separate git worktree | Manual; `/loop` doesn't manage worktrees. |
| `agents.*` routing | `CronTask.agentId` | A fire can be routed to a specific teammate. |

## What the engine must add (because `/loop` doesn't)

1. **The checker step** — run `agents.checker` after the maker; only stop when it
   confirms `until`. Without this you have Claude Code's default: a loop that
   repeats forever with no notion of "done."
2. **`until` evaluation** — evaluate the boolean (or run the prose judge) and call
   `CronDelete` on success.
3. **State** — read/write `log.md` so the loop has memory across fires.

These three are exactly the structure SLAC exists to enforce.
