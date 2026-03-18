import base64

import pytest


@pytest.mark.parametrize("pcm_samples", [
    b"\x00\x00" * 100,
    (b"\x00\x01\x00\x02" * 50),
])
def test_mulaw_roundtrip_length(pcm_samples):
    from app.audio_utils import pcm16_to_mulaw, mulaw_to_pcm16

    mulaw = pcm16_to_mulaw(pcm_samples)
    restored = mulaw_to_pcm16(mulaw)

    # mu-law is 8-bit, PCM16 is 16-bit; roundtrip should preserve sample count
    assert len(mulaw) * 2 == len(restored)


def test_resample_8k_to_24k_length():
    from app.audio_utils import resample_pcm16

    # 100 samples @ 8kHz -> 300 samples @ 24kHz
    pcm_8k = b"\x00\x00" * 100
    pcm_24k = resample_pcm16(pcm_8k, in_rate=8000, out_rate=24000)
    assert len(pcm_24k) == len(pcm_8k) * 3


def test_twilio_payload_helpers_roundtrip():
    from app.audio_utils import decode_twilio_media, encode_twilio_media

    raw = b"hello world"
    encoded = encode_twilio_media(raw)
    assert isinstance(encoded, str)
    decoded = decode_twilio_media(encoded)
    assert decoded == raw
