#!/usr/bin/env bash
# Regenerate protocol/donna.schema.json (from Pydantic) and the TypeScript types.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
uv run --project "$root/core" python "$root/scripts/gen_protocol.py"
npm --prefix "$root/desktop" run --silent gen:protocol
echo "generated desktop/src/protocol/generated.ts"
