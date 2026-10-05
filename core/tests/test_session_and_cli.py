import json
import os
import stat
import sys
from pathlib import Path

import pytest

from donna_core.app import build_core
from donna_core.cli.client import run
from donna_core.config import DEFAULT_ALLOWED_ORIGINS
from donna_core.server.gateway import Gateway
from donna_core.server.session_file import (
    read_session_file,
    remove_session_file,
    write_session_file,
)


def test_session_file_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "session.json"
    info = write_session_file(path, 4321, "tok")
    assert read_session_file(path) == info
    assert info.url == "ws://127.0.0.1:4321"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_session_file_is_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    write_session_file(path, 1, "tok")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_remove_only_own_session_file(tmp_path: Path) -> None:
    path = tmp_path / "session.json"
    path.write_text(json.dumps({"port": 1, "token": "x", "pid": os.getpid() + 1}))
    remove_session_file(path)
    assert path.exists()  # belongs to another core: left alone
    write_session_file(path, 1, "tok")
    remove_session_file(path)
    assert not path.exists()


async def test_cli_connects_and_runs_a_turn(capsys: pytest.CaptureFixture[str]) -> None:
    core = build_core()
    gateway = Gateway(core, core.bus, "tok", DEFAULT_ALLOWED_ORIGINS)
    port = await gateway.start(0)
    try:
        code = await run(f"ws://127.0.0.1:{port}", "tok", "find my TrialGuard files", False)
    finally:
        await gateway.stop()
    out = capsys.readouterr().out
    assert code == 0
    assert "You > find my TrialGuard files" in out
    assert "DONNA > Searching files..." in out
    assert "[r_1] TrialGuard_Proposal.pdf" in out
    assert "DONNA > I found 4 files" in out


async def test_cli_reports_bad_token(capsys: pytest.CaptureFixture[str]) -> None:
    core = build_core()
    gateway = Gateway(core, core.bus, "tok", DEFAULT_ALLOWED_ORIGINS)
    port = await gateway.start(0)
    try:
        code = await run(f"ws://127.0.0.1:{port}", "wrong", "hello", False)
    finally:
        await gateway.stop()
    assert code == 1
    assert "4401" in capsys.readouterr().err
