"""Helpers for REL-04 / D-049: simulate a dead or stuck chain endpoint with local sockets only.

No `.env` is read or needed: every chain setting a test depends on is set explicitly through
`chain_env`, which restores the previous process environment (including whatever the session's
`local_chain` fixture set) and the cached settings/web3 objects afterwards.
"""

import os
import socket
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import pytest

from app.core.config import get_settings
from app.services import blockchain as chain

# A fake API key in the URL path: nothing in a response, record, audit row or log may contain it.
SECRET = "SECRETKEYABCDEF123456"
# Hardhat's public default dev account #0. An externally-owned account: no contract code there.
NO_CODE_ADDRESS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


def dead_port_url() -> str:
    """A localhost URL with nothing listening (connection refused), carrying a fake key."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}/v2/{SECRET}"


@contextmanager
def blackhole() -> Iterator[str]:
    """A localhost server that accepts connections and never answers (a stuck node)."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(16)
    held: list[socket.socket] = []
    stop = threading.Event()

    def _accept() -> None:
        server.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            held.append(conn)

    thread = threading.Thread(target=_accept, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.getsockname()[1]}/v2/{SECRET}"
    finally:
        stop.set()
        thread.join(timeout=2)
        for conn in held:
            conn.close()
        server.close()


@pytest.fixture
def chain_env() -> Iterator[Callable[..., None]]:
    """`chain_env(SEPOLIA_RPC_URL=..., CONTRACT_ADDRESS=..., CHAIN_READ_TIMEOUT_SEC=...)`.

    Request it after `local_chain` so it is torn down first."""
    saved: dict[str, str | None] = {}

    def apply(**values: object) -> None:
        for key, value in values.items():
            saved.setdefault(key, os.environ.get(key))
            os.environ[key] = str(value)
        get_settings.cache_clear()
        chain._w3 = None

    yield apply
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()
    chain._w3 = None
