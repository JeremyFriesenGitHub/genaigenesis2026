from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.personaplex_client import PersonaPlexClient

logger = logging.getLogger(__name__)
_pool: dict[str, tuple["PersonaPlexClient", float]] = {}  # call_control_id → (client, stored_at)
PREWARM_TTL = float(os.environ.get("PREWARM_TTL_SECONDS", "30"))


async def store(call_control_id: str, client: "PersonaPlexClient") -> None:
    _pool[call_control_id] = (client, time.monotonic())


async def retrieve(call_control_id: str, timeout: float = 10.0) -> "PersonaPlexClient | None":
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if call_control_id in _pool:
            client, _ = _pool.pop(call_control_id)
            return client
        await asyncio.sleep(0.05)
    return None


async def cleanup_expired() -> None:
    now = time.monotonic()
    expired = [k for k, (_, ts) in _pool.items() if now - ts > PREWARM_TTL]
    for k in expired:
        client, _ = _pool.pop(k)
        await client.close()


async def close_all() -> None:
    for client, _ in list(_pool.values()):
        await client.close()
    _pool.clear()
