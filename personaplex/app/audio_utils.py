import base64
import audioop

import numpy as np
import noisereduce as nr


PCM_WIDTH_BYTES = 2
PCM_CHANNELS = 1


def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    return audioop.ulaw2lin(mulaw_bytes, PCM_WIDTH_BYTES)


def pcm16_to_mulaw(pcm_bytes: bytes) -> bytes:
    return audioop.lin2ulaw(pcm_bytes, PCM_WIDTH_BYTES)


def resample_pcm16(pcm_bytes: bytes, in_rate: int, out_rate: int) -> bytes:
    if in_rate == out_rate:
        return pcm_bytes

    converted, _ = audioop.ratecv(
        pcm_bytes,
        PCM_WIDTH_BYTES,
        PCM_CHANNELS,
        in_rate,
        out_rate,
        None,
    )

    expected_len = int(len(pcm_bytes) * (out_rate / in_rate))
    if len(converted) < expected_len:
        converted += b"\x00" * (expected_len - len(converted))
    elif len(converted) > expected_len:
        converted = converted[:expected_len]

    return converted


class StatefulResampler:
    """Resampler that preserves audioop state across calls for continuous audio."""

    def __init__(self, in_rate: int, out_rate: int):
        self.in_rate = in_rate
        self.out_rate = out_rate
        self._state = None

    def resample(self, pcm_bytes: bytes) -> bytes:
        if self.in_rate == self.out_rate:
            return pcm_bytes
        converted, self._state = audioop.ratecv(
            pcm_bytes,
            PCM_WIDTH_BYTES,
            PCM_CHANNELS,
            self.in_rate,
            self.out_rate,
            self._state,
        )
        return converted


class StreamingDenoiser:
    """Spectral noise suppression for continuous audio streams.

    Buffers small chunks until we have enough samples for the FFT window,
    then denoises the full buffer and drains it in original chunk sizes.
    The stream stays continuous; no gating or silencing.
    """

    def __init__(self, sample_rate: int = 24000, prop_decrease: float = 0.6,
                 min_samples: int = 4096):
        self.sample_rate = sample_rate
        self.prop_decrease = prop_decrease
        self.min_samples = min_samples
        self._buffer = np.array([], dtype=np.float32)
        self._output = b""

    def process(self, pcm_bytes: bytes) -> bytes:
        chunk = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        self._buffer = np.concatenate([self._buffer, chunk])

        if len(self._buffer) < self.min_samples:
            # Not enough for denoising yet — pass through raw audio
            return pcm_bytes

        cleaned = nr.reduce_noise(
            y=self._buffer,
            sr=self.sample_rate,
            stationary=True,
            prop_decrease=self.prop_decrease,
        )
        result = (np.clip(cleaned, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
        self._buffer = np.array([], dtype=np.float32)

        # Return only the last chunk-sized portion, prepend rest to output queue
        chunk_len = len(pcm_bytes)
        self._output += result[:-chunk_len]
        current = result[-chunk_len:]

        # If we have queued output, drain one chunk from the front instead
        if len(self._output) >= chunk_len:
            current = self._output[:chunk_len]
            self._output = self._output[chunk_len:]

        return current


def decode_twilio_media(payload_b64: str) -> bytes:
    return base64.b64decode(payload_b64)


def encode_twilio_media(raw_bytes: bytes) -> str:
    return base64.b64encode(raw_bytes).decode("ascii")


# Telnyx L16 helpers — L16 is raw PCM16, just base64 encoded
def decode_telnyx_media(payload_b64: str) -> bytes:
    return base64.b64decode(payload_b64)


def encode_telnyx_media(pcm_bytes: bytes) -> str:
    return base64.b64encode(pcm_bytes).decode("ascii")
