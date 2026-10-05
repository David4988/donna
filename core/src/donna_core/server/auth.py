"""Authentication helpers for the local WebSocket server.

Threat model: the server only listens on 127.0.0.1, but *any* local process and
any web page open in a browser can try to connect to a localhost port (browsers
don't apply CORS to WebSockets). So:

* a random token, generated per launch, must be sent in the first message;
* browser clients must also come from an allowed Origin (Tauri / Vite dev).
"""

from __future__ import annotations

import hmac
import secrets

# Application-defined WebSocket close codes (4000-4999 are free for apps).
CLOSE_BAD_REQUEST = 4400
CLOSE_UNAUTHORIZED = 4401
CLOSE_AUTH_TIMEOUT = 4408


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def token_matches(expected: str, given: str) -> bool:
    """Constant-time comparison, so timing doesn't leak how much of the token matched."""
    return hmac.compare_digest(expected.encode(), given.encode())
