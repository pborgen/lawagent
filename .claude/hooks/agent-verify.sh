#!/usr/bin/env sh
# Stop-hook verification gate — the agent self-correction loop.
#
# Fires whenever the agent finishes a turn. It runs `make check`
# (ruff + pytest + tsc, ~a few seconds) ONLY when tracked code changed
# this session; pure-conversation turns skip instantly. On failure it
# exits 2 and writes the full output to stderr, which the harness feeds
# back to the agent as if you'd pasted it — so the agent fixes the
# problem and tries again without you relaying anything.
#
# Turn it off by deleting the "Stop" hook from .claude/settings.json.
set -eu

root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$root"

# Nothing relevant changed vs HEAD → don't spend time checking.
if git diff --quiet HEAD -- '*.py' '*.ts' '*.tsx' 'pyproject.toml' 2>/dev/null; then
  exit 0
fi

if out="$(make check 2>&1)"; then
  exit 0
fi

printf '%s\n\n[stop-hook] `make check` failed. Fix the above and continue — do not stop with a red gate.\n' "$out" >&2
exit 2
