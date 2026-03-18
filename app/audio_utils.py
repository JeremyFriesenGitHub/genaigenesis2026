import base64
import audioop

import numpy as np


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
    """No-op denoiser — passes audio through unchanged."""

    def __init__(self, sample_rate: int = 24000, **kwargs):
        pass

    def process(self, pcm_bytes: bytes) -> bytes:
        return pcm_bytes


class EchoCanceller:
    """SpeexDSP AEC + optional RNNoise for real-time echo/noise removal.

    Feed the playback signal (what the caller hears) via ``feed_reference()``,
    then process the recording signal (caller's mic) via ``process()``.
    Total added latency: ~20 ms (one 20 ms frame).
    """

    def __init__(self, sample_rate: int = 8000, frame_ms: int = 20, use_rnnoise: bool = True):
        self.sample_rate = sample_rate
        self.frame_size = sample_rate * frame_ms // 1000  # samples per frame (160 @ 8 kHz)
        self.frame_bytes = self.frame_size * 2             # 16-bit PCM

        # SpeexDSP AEC — filter_length covers ~100 ms echo tail
        try:
            from speexdsp import EchoCanceller as SpxAEC
            filter_length = self.frame_size * 5  # 5 frames ≈ 100 ms
            self._aec = SpxAEC.create(self.frame_size, filter_length, sample_rate)
            self._has_aec = True
        except Exception:
            self._has_aec = False

        # RNNoise (operates at 48 kHz internally) — use C lib directly
        self._has_rnnoise = False
        if use_rnnoise:
            try:
                import ctypes
                from pyrnnoise.rnnoise import create as rnnoise_create, lib as rnnoise_lib
                self._rnnoise_state = rnnoise_create()
                self._rnnoise_lib = rnnoise_lib
                self._ctypes = ctypes
                self._has_rnnoise = True
                self._rnnoise_up_state = None    # audioop ratecv state for 8k→48k
                self._rnnoise_down_state = None  # audioop ratecv state for 48k→8k
            except Exception:
                pass

        # Buffers for frame-aligned processing
        self._ref_buf = bytearray()
        self._rec_buf = bytearray()

    def feed_reference(self, pcm_bytes: bytes) -> None:
        """Feed playback audio (agent voice sent to caller) as AEC reference."""
        self._ref_buf.extend(pcm_bytes)
        # Prevent unbounded growth if recv loop is slower
        max_buf = self.frame_bytes * 50  # ~1 s
        if len(self._ref_buf) > max_buf:
            self._ref_buf = self._ref_buf[-max_buf:]

    def process(self, pcm_bytes: bytes) -> bytes:
        """Process caller mic audio: AEC → RNNoise → return cleaned PCM."""
        self._rec_buf.extend(pcm_bytes)
        output = bytearray()

        while len(self._rec_buf) >= self.frame_bytes:
            rec_frame = bytes(self._rec_buf[:self.frame_bytes])
            del self._rec_buf[:self.frame_bytes]

            # --- AEC ---
            if self._has_aec and len(self._ref_buf) >= self.frame_bytes:
                ref_frame = bytes(self._ref_buf[:self.frame_bytes])
                del self._ref_buf[:self.frame_bytes]
                rec_frame = self._aec.process(rec_frame, ref_frame)
            elif self._has_aec:
                # No reference yet — feed silence as reference so AEC state stays valid
                silence = b"\x00" * self.frame_bytes
                rec_frame = self._aec.process(rec_frame, silence)

            # --- RNNoise ---
            if self._has_rnnoise:
                rec_frame = self._apply_rnnoise(rec_frame)

            output.extend(rec_frame)

        return bytes(output)

    def _apply_rnnoise(self, pcm_8k: bytes) -> bytes:
        """Resample 8 kHz → 48 kHz, run RNNoise frame-by-frame via C lib, resample back."""
        # Upsample to 48 kHz
        pcm_48k, self._rnnoise_up_state = audioop.ratecv(
            pcm_8k, PCM_WIDTH_BYTES, PCM_CHANNELS,
            self.sample_rate, 48000, self._rnnoise_up_state,
        )

        # Convert to float32 for RNNoise (expects float32 scaled to int16 range)
        samples = np.frombuffer(pcm_48k, dtype=np.int16).astype(np.float32)
        # RNNoise expects 480-sample frames (10 ms at 48 kHz)
        frame_len = 480
        i = 0
        while i + frame_len <= len(samples):
            frame = samples[i:i + frame_len].copy()
            ptr = frame.ctypes.data_as(self._ctypes.POINTER(self._ctypes.c_float))
            self._rnnoise_lib.rnnoise_process_frame(self._rnnoise_state, ptr, ptr)
            samples[i:i + frame_len] = frame
            i += frame_len

        # Back to int16 PCM
        pcm_48k_clean = samples.clip(-32768, 32767).astype(np.int16).tobytes()

        # Downsample back to 8 kHz
        pcm_8k_clean, self._rnnoise_down_state = audioop.ratecv(
            pcm_48k_clean, PCM_WIDTH_BYTES, PCM_CHANNELS,
            48000, self.sample_rate, self._rnnoise_down_state,
        )

        return pcm_8k_clean


def decode_twilio_media(payload_b64: str) -> bytes:
    """Decode Twilio mulaw payload: base64 decode then mulaw → PCM16."""
    return mulaw_to_pcm16(base64.b64decode(payload_b64))


def encode_twilio_media(pcm_bytes: bytes) -> str:
    """Encode PCM16 for Twilio: PCM16 → mulaw then base64 encode."""
    return base64.b64encode(pcm16_to_mulaw(pcm_bytes)).decode("ascii")


# Telnyx L16 helpers — L16 is raw PCM16, just base64 encoded
def decode_telnyx_media(payload_b64: str) -> bytes:
    return base64.b64decode(payload_b64)


def encode_telnyx_media(pcm_bytes: bytes) -> str:
    return base64.b64encode(pcm_bytes).decode("ascii")
