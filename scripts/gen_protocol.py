"""Write protocol/donna.schema.json from the Pydantic models (the source of truth).

Run: uv run --project core python scripts/gen_protocol.py
TypeScript types are then generated from the schema by `npm run gen:protocol`
in desktop/ (scripts/gen_protocol.sh does both).
"""

from __future__ import annotations

import json
from pathlib import Path

from donna_core.protocol.codec import json_schema

OUT = Path(__file__).resolve().parent.parent / "protocol" / "donna.schema.json"


def main() -> None:
    OUT.write_text(json.dumps(json_schema(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(OUT.parent.parent)}")


if __name__ == "__main__":
    main()
