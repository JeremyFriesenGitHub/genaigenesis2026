from xml.etree import ElementTree as ET


def test_stream_twiml_contains_ws_url():
    from app.routers.voice import make_stream_twiml

    ws_url = "wss://example.ngrok.app/voice/stream"
    xml = make_stream_twiml(ws_url)

    root = ET.fromstring(xml)
    stream = root.find(".//Stream")
    assert stream is not None
    assert stream.attrib.get("url") == ws_url
