"""Full-duplex streaming client for PersonaPlex WebSocket server.

Protocol:
  0x00  Handshake (server → client, signals system prompts loaded)
  0x01  Audio    (bidirectional, Opus-encoded at 24 kHz)
  0x02  Text     (server → client, UTF-8 token fragments)

sphn PyPI API:
  OpusStreamWriter.append_pcm(float32) → bytes   (Opus encoded)
  OpusStreamReader.append_bytes(bytes)  → float32 (PCM decoded)
"""

import asyncio
import logging
import os
import ssl
from typing import Optional
from urllib.parse import quote

import numpy as np
import sphn
import websockets

logger = logging.getLogger(__name__)

MSG_HANDSHAKE = 0x00
MSG_AUDIO = 0x01
MSG_TEXT = 0x02

SAMPLE_RATE = 24_000


class PersonaPlexClient:
    """Async context-manager that streams audio to/from a PersonaPlex server."""

    def __init__(
        self,
        server_url: str,
        voice_prompt: str = "NATF2.pt",
        text_prompt: str = "",
        seed: int = -1,
    ):
        self._server_url = server_url
        self._voice_prompt = voice_prompt
        self._text_prompt = text_prompt
        self._seed = seed

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._opus_writer: Optional[sphn.OpusStreamWriter] = None
        self._opus_reader: Optional[sphn.OpusStreamReader] = None

        self._ready = asyncio.Event()
        self._audio_out: asyncio.Queue[bytes] = asyncio.Queue()
        self._opus_send: asyncio.Queue[bytes] = asyncio.Queue()
        self._closed = False
        self._recv_task: Optional[asyncio.Task] = None
        self._send_task: Optional[asyncio.Task] = None

    @classmethod
    def from_env(cls) -> "PersonaPlexClient":
        return cls(
            server_url=os.environ.get("PERSONAPLEX_STREAM_URL", ""),
            voice_prompt=os.environ.get("PERSONAPLEX_VOICE", "NATF2.pt"),
            text_prompt=os.environ.get("PERSONAPLEX_TEXT_PROMPT", ""),
            seed=int(os.environ.get("PERSONAPLEX_SEED", "-1")),
        )

    # -- lifecycle --------------------------------------------------------

    async def connect(self):
        """Open WebSocket, start background loops, wait for handshake."""
        # Workaround: Don't send seed to avoid PersonaPlex server bug (KeyError on request['seed'])
        params = (
            f"?voice_prompt={quote(self._voice_prompt)}"
            f"&text_prompt={quote(self._text_prompt)}"
        )
        url = self._server_url.rstrip("/") + params
        logger.info("Connecting to PersonaPlex at %s", self._server_url)

        ssl_ctx = None
        if url.startswith("wss://"):
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        self._ws = await websockets.connect(url, max_size=None, ssl=ssl_ctx)
        self._opus_writer = sphn.OpusStreamWriter(SAMPLE_RATE)
        self._opus_reader = sphn.OpusStreamReader(SAMPLE_RATE)
        self._closed = False

        self._recv_task = asyncio.create_task(self._recv_loop())
        self._send_task = asyncio.create_task(self._send_loop())

        logger.info("Waiting for PersonaPlex handshake …")
        await self._ready.wait()
        logger.info("PersonaPlex ready")

    async def close(self):
        self._closed = True
        for t in (self._recv_task, self._send_task):
            if t:
                t.cancel()
        if self._ws:
            await self._ws.close()

    async def __aenter__(self) -> "PersonaPlexClient":
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    # -- public API -------------------------------------------------------

    _send_pcm_calls = 0
    _opus_frames_produced = 0

    def send_pcm(self, pcm16_bytes: bytes) -> None:
        """Feed signed-int16 PCM at 24 kHz.  Non-blocking; buffers internally."""
        self._send_pcm_calls += 1
        samples = np.frombuffer(pcm16_bytes, dtype=np.int16)
        pcm_f32 = samples.astype(np.float32) / 32767.0
        opus_bytes = self._opus_writer.append_pcm(pcm_f32)
        if opus_bytes and len(opus_bytes) > 0:
            self._opus_frames_produced += 1
            self._opus_send.put_nowait(opus_bytes)
        if self._send_pcm_calls % 50 == 1:
            logger.info(f"send_pcm called {self._send_pcm_calls}x, opus frames produced: {self._opus_frames_produced}, input samples: {len(samples)}")

    async def recv_audio(self, timeout: float = 0.05) -> Optional[bytes]:
        """Return next chunk of signed-int16 PCM at 24 kHz, or None on timeout."""
        try:
            return await asyncio.wait_for(self._audio_out.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    @property
    def is_closed(self) -> bool:
        return self._closed

    # -- internal ---------------------------------------------------------

    async def _recv_loop(self):
        try:
            async for message in self._ws:
                if not isinstance(message, bytes) or len(message) == 0:
                    continue
                kind = message[0]
                payload = message[1:]

                if kind == MSG_HANDSHAKE:
                    self._ready.set()
                elif kind == MSG_AUDIO:
                    pcm_f32 = self._opus_reader.append_bytes(payload)
                    if pcm_f32 is not None and pcm_f32.shape[-1] > 0:
                        pcm_i16 = (pcm_f32 * 32767).clip(-32768, 32767).astype(np.int16)
                        await self._audio_out.put(pcm_i16.tobytes())
                elif kind == MSG_TEXT:
                    text = payload.decode("utf-8")
                    logger.debug("PersonaPlex text: %s", text)
        except websockets.ConnectionClosed:
            logger.info("PersonaPlex connection closed")
        except Exception:
            logger.exception("PersonaPlex recv error")
        finally:
            self._closed = True

    async def _send_loop(self):
        import time
        sends = 0
        try:
            while not self._closed:
                try:
                    opus_bytes = await asyncio.wait_for(
                        self._opus_send.get(), timeout=0.1
                    )
                except asyncio.TimeoutError:
                    continue
                t0 = time.perf_counter()
                await self._ws.send(bytes([MSG_AUDIO]) + opus_bytes)
                t1 = time.perf_counter()
                sends += 1
                if sends % 250 == 1:
                    logger.info(f"[LATENCY] WS send to PersonaPlex: {(t1-t0)*1000:.2f}ms ({len(opus_bytes)} bytes, send #{sends})")
        except websockets.ConnectionClosed:
            pass
        except Exception:
            logger.exception("PersonaPlex send error")
        finally:
            self._closed = True
