"""Run the DONNA core: ``python -m donna_core`` (or ``donna-core``)."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import signal
from pathlib import Path

from donna_core.app import build_core
from donna_core.config import DEFAULT_ALLOWED_ORIGINS, Config, default_session_file
from donna_core.server.auth import generate_token
from donna_core.server.gateway import Gateway
from donna_core.server.session_file import remove_session_file, write_session_file

log = logging.getLogger("donna_core")

DEV_UI_URL = "http://localhost:1420"


def parse_args(argv: list[str] | None = None) -> tuple[Config, argparse.Namespace]:
    p = argparse.ArgumentParser(prog="donna-core", description="Run DONNA's Python core.")
    p.add_argument("--port", type=int, default=0, help="port on 127.0.0.1 (default: random)")
    p.add_argument("--llm", choices=["fake", "openai_compat"], default="fake")
    p.add_argument(
        "--simulate-speech",
        action="store_true",
        help="make SPEAKING take time (lets you test cancelling mid-reply)",
    )
    p.add_argument(
        "--allow-origin", action="append", default=[], help="extra allowed browser Origin"
    )
    p.add_argument("--session-file", type=Path, default=None)
    p.add_argument(
        "--print-ui-url",
        action="store_true",
        help="print a browser dev URL that includes the token (local use only)",
    )
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)
    config = Config(
        port=args.port,
        token=os.environ.get("DONNA_TOKEN") or None,
        llm=args.llm,
        simulate_speech=args.simulate_speech,
        allowed_origins=(*DEFAULT_ALLOWED_ORIGINS, *args.allow_origin),
        session_file=args.session_file or default_session_file(),
    )
    return config, args


async def serve(config: Config, print_ui_url: bool = False) -> None:
    token = config.token or generate_token()
    core = build_core(config)
    gateway = Gateway(core, core.bus, token, config.allowed_origins, config.hello_timeout_s)
    port = await gateway.start(config.port)
    write_session_file(config.session_file, port, token)
    log.info("DONNA core listening on ws://127.0.0.1:%d (llm=%s)", port, config.llm)
    log.info("session file: %s", config.session_file)
    if print_ui_url:
        print(f"Dev UI: {DEV_UI_URL}/#port={port}&token={token}", flush=True)

    stop = asyncio.Event()
    with contextlib.suppress(NotImplementedError):  # not available on Windows
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stop.set)
    try:
        await stop.wait()
    finally:
        await core.cancel("shutting down")
        await gateway.stop()
        remove_session_file(config.session_file)
        log.info("DONNA core stopped")


def main(argv: list[str] | None = None) -> None:
    config, args = parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)s %(name)s: %(message)s")
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(serve(config, args.print_ui_url))


if __name__ == "__main__":
    main()
