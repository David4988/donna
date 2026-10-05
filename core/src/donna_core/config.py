from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Origins a browser-based client may connect from. Non-browser clients (the
# CLI) send no Origin header at all, which is allowed; they still need the token.
DEFAULT_ALLOWED_ORIGINS: tuple[str, ...] = (
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "http://localhost:1420",
    "http://127.0.0.1:1420",
)


def default_session_file() -> Path:
    home = os.environ.get("DONNA_HOME")
    base = Path(home) if home else Path.home() / ".donna"
    return base / "session.json"


@dataclass(frozen=True, slots=True)
class Config:
    port: int = 0  # 0 = pick a free port
    token: str | None = None  # None = generate a random one per launch
    llm: str = "fake"
    simulate_speech: bool = False
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS
    session_file: Path = field(default_factory=default_session_file)
    hello_timeout_s: float = 5.0
    tool_timeout_s: float = 10.0
