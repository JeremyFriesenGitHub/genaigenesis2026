"""Records call audio and transcribes after the call ends. Uploads to S3."""

import asyncio
import io
import logging
import os
import time
import wave

import numpy as np

logger = logging.getLogger(__name__)


class CallRecorder:
    """Accumulates PCM audio from both sides of a call."""

    def __init__(self, call_id: str, sample_rate: int = 24000):
        self.call_id = call_id
        self.sample_rate = sample_rate
        self._user_chunks: list[bytes] = []
        self._agent_chunks: list[bytes] = []
        self._start_time = time.time()

    def record_user(self, pcm_bytes: bytes) -> None:
        self._user_chunks.append(pcm_bytes)

    def record_agent(self, pcm_bytes: bytes) -> None:
        self._agent_chunks.append(pcm_bytes)

    def _merge_to_wav(self) -> bytes:
        """Mix user and agent audio into a single mono WAV."""
        user_audio = np.frombuffer(b"".join(self._user_chunks), dtype=np.int16).astype(np.float32)
        agent_audio = np.frombuffer(b"".join(self._agent_chunks), dtype=np.int16).astype(np.float32)

        # Pad shorter track to match longer
        max_len = max(len(user_audio), len(agent_audio))
        if len(user_audio) < max_len:
            user_audio = np.pad(user_audio, (0, max_len - len(user_audio)))
        if len(agent_audio) < max_len:
            agent_audio = np.pad(agent_audio, (0, max_len - len(agent_audio)))

        # Mix both channels
        mixed = (user_audio + agent_audio) / 2.0
        mixed = np.clip(mixed, -32768, 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(mixed.tobytes())
        return buf.getvalue()

    def save_and_transcribe(self) -> None:
        """Save WAV and transcribe in a background thread, then upload to S3."""
        if not self._user_chunks and not self._agent_chunks:
            logger.info("No audio recorded for call %s", self.call_id)
            return
        asyncio.get_event_loop().run_in_executor(None, self._save_and_transcribe_sync)

    def _save_and_transcribe_sync(self) -> None:
        try:
            wav_data = self._merge_to_wav()
            duration = len(wav_data) / (self.sample_rate * 2)
            logger.info("Merged recording for %s (%.1fs)", self.call_id, duration)

            # Transcribe with faster-whisper (in-memory)
            import tempfile
            from faster_whisper import WhisperModel

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(wav_data)
                tmp_path = tmp.name

            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(tmp_path)
            transcript = " ".join(seg.text.strip() for seg in segments)
            os.unlink(tmp_path)

            logger.info("Transcript for %s: %s", self.call_id, transcript)

            # Upload WAV and transcript to S3
            import boto3
            bucket = os.environ.get("S3_BUCKET", "personaplex-recordings")
            s3 = boto3.client("s3")

            s3.put_object(
                Bucket=bucket,
                Key=f"recordings/{self.call_id}.wav",
                Body=wav_data,
            )
            s3.put_object(
                Bucket=bucket,
                Key=f"transcripts/{self.call_id}.txt",
                Body=transcript.encode(),
            )
            logger.info("Uploaded WAV and transcript to S3 for %s", self.call_id)

        except Exception:
            logger.exception("Failed to save/transcribe call %s", self.call_id)
