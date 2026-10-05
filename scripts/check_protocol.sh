#!/usr/bin/env bash
# CI drift check: generated protocol files must match the Pydantic source of truth.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
"$root/scripts/gen_protocol.sh"
files=(protocol/donna.schema.json desktop/src/protocol/generated.ts)
# --porcelain also catches generated files that were never committed.
if [ -n "$(git -C "$root" status --porcelain -- "${files[@]}")" ]; then
  git -C "$root" --no-pager diff -- "${files[@]}" | head -50
  echo "Protocol files are stale. Run scripts/gen_protocol.sh and commit the result." >&2
  exit 1
fi
echo "protocol files are up to date"
