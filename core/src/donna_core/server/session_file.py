"""The session file tells local clients where the core is and how to authenticate.

``~/.donna/session.json`` = ``{"port": ..., "token": ..., "pid": ...}``. It lives
in the user's home directory with owner-only permissions, so the token never
needs to be hardcoded anywhere or committed.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SessionInfo:
    port: int
    token: str
    pid: int

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}"


def write_session_file(path: Path, port: int, token: str) -> SessionInfo:
    info = SessionInfo(port=port, token=token, pid=os.getpid())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"port": info.port, "token": info.token, "pid": info.pid}, fh)
    os.replace(tmp, path)
    return info


def read_session_file(path: Path) -> SessionInfo:
    data = json.loads(path.read_text(encoding="utf-8"))
    return SessionInfo(port=int(data["port"]), token=str(data["token"]), pid=int(data["pid"]))


def remove_session_file(path: Path) -> None:
    """Remove the file, but only if it still belongs to this process."""
    with contextlib.suppress(FileNotFoundError, ValueError, KeyError):
        if read_session_file(path).pid == os.getpid():
            path.unlink()
