"""The `slac` command-line interface.

Subcommands:
    slac lint FILE...     validate .slac.md loop files (type-check + lint)
    slac new NAME         scaffold a starter loop that lints clean
    slac explain [NAME]   explain a diagnostic (or list them all)
"""

import argparse
import os
import sys

from . import __version__
from .linter import run as lint_run

STARTER = """\
---
type: slac.loop
loop: {name}
version: 0.0.1
title: {title}
description: TODO — one sentence on what this loop achieves.

context:
  - cmd: echo "TODO: real fuel (commands, files, signals)"
  - signal: ci          # fills ci.green; declare every signal used in `until`

agents:
  maker:
    model: opus
    instructions: |
      TODO: what the implementer should do each iteration.
  checker:
    model: opus
    mode: refute        # a SEPARATE agent confirms "done" — never the maker
    instructions: |
      TODO: how the checker independently verifies the goal is met.

until: ci.green and consecutive_green >= 2

state: ./log.md         # on-disk memory between runs (OKF log.md)

boundaries:
  always: []
  ask: []
  never:
    - commit secrets

max_iterations: 20
budget:
  tokens: 500_000
---

# Goal

TODO: one clear sentence describing the outcome this loop drives toward.
"""

DIAGNOSTICS = {
    "SLACSyntaxError": "ERROR — the file isn't a well-formed SLAC document "
                       "(no/!closed frontmatter). Like Python's SyntaxError.",
    "MissingFieldError": "ERROR — a required field or the '# Goal' section is "
                         "absent. Like a missing function argument.",
    "UnknownFieldError": "ERROR — a frontmatter key SLAC doesn't define; catches "
                         "typos (suggests the nearest real field). Like NameError.",
    "TypeError": "ERROR — a field has the wrong type (e.g. context as a string).",
    "ValueError": "ERROR — a field's value is out of range / not an allowed enum.",
    "NoCheckerWarning": "WARNING — maker but no checker; it grades its own work "
                        "(the /goal footgun). Add agents.checker.",
    "NoStateWarning": "WARNING — no state file; the loop forgets between runs. "
                      "Add state: ./log.md.",
    "UnreachableStopWarning": "WARNING — `until` names a signal nothing produces, "
                              "so the loop can never stop on it.",
    "NoBoundaryWarning": "WARNING — no boundaries.never; the loop has no hard stops.",
    "RunawayWarning": "WARNING — no max_iterations and no budget; it can run forever.",
}


def cmd_lint(args):
    return lint_run(args.files, as_json=args.json, strict=args.strict)


def cmd_new(args):
    name = args.name
    if not name.replace("_", "a").isalnum() or not name[0].isalpha() or not name.islower():
        print("loop name must be snake_case (lowercase letters, digits, underscores)",
              file=sys.stderr)
        return 1
    title = name.replace("_", " ").title()
    content = STARTER.format(name=name, title=title)
    out = args.output or "%s.slac.md" % name
    if os.path.exists(out) and not args.force:
        print("refusing to overwrite %s (use --force)" % out, file=sys.stderr)
        return 1
    with open(out, "w", encoding="utf-8") as f:
        f.write(content)
    print("wrote %s" % out)
    print("next: fill in the TODOs, then `slac lint %s`" % out)
    return 0


def cmd_explain(args):
    if args.name:
        desc = DIAGNOSTICS.get(args.name)
        if not desc:
            print("unknown diagnostic: %s" % args.name, file=sys.stderr)
            print("known: %s" % ", ".join(sorted(DIAGNOSTICS)), file=sys.stderr)
            return 1
        print("%s\n  %s" % (args.name, desc))
        return 0
    for name in sorted(DIAGNOSTICS, key=lambda n: (n.endswith("Warning"), n)):
        print("%-24s %s" % (name, DIAGNOSTICS[name].split(" — ")[0]))
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="slac",
        description="SLAC — Structured Language for Agentic Coding.",
    )
    p.add_argument("--version", action="version", version="slac %s" % __version__)
    sub = p.add_subparsers(dest="command")

    pl = sub.add_parser("lint", help="validate .slac.md loop files")
    pl.add_argument("files", nargs="+", help="one or more .slac.md files")
    pl.add_argument("--json", action="store_true", help="machine-readable findings")
    pl.add_argument("--strict", action="store_true", help="warnings become errors")
    pl.set_defaults(func=cmd_lint)

    pn = sub.add_parser("new", help="scaffold a starter loop that lints clean")
    pn.add_argument("name", help="snake_case loop name")
    pn.add_argument("-o", "--output", help="output path (default: <name>.slac.md)")
    pn.add_argument("--force", action="store_true", help="overwrite if it exists")
    pn.set_defaults(func=cmd_new)

    pe = sub.add_parser("explain", help="explain a diagnostic (or list them all)")
    pe.add_argument("name", nargs="?", help="diagnostic name, e.g. NoCheckerWarning")
    pe.set_defaults(func=cmd_explain)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
