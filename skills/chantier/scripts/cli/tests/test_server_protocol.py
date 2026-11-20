"""The protocol's schemas: the shipped `protocol.json` is what the models say, byte for byte, and
the tables list what the server serves."""

from __future__ import annotations

import json
import re
from pathlib import Path

from chantier.board.api import ops, protocol, topics

SHIPPED = Path(protocol.__file__).with_name("protocol.json")


def test_the_shipped_schema_is_the_models_text() -> None:
    raw = SHIPPED.read_bytes()
    assert raw == protocol.canonical().encode("utf-8"), "run `just protocol-schema`"
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw and raw.endswith(b"}\n")


def test_every_op_and_topic_has_its_schema_and_its_code() -> None:
    found = json.loads(SHIPPED.read_text("utf-8"))
    for op in protocol.OPS:
        assert f"op.{op}" in found
    for topic in protocol.TOPICS:
        assert f"topic.{topic}" in found
    for kind in protocol.FRAMES:
        assert f"frame.{kind}" in found
    assert set(ops.HANDLERS) == set(protocol.OPS) and set(topics.READS) == set(protocol.TOPICS)


WEB = Path(topics.__file__).parents[1] / "web" / "js"
TRANSPORT_FILES = {"core/transport.js", "core/ws-link.js", "core/http-link.js"}
OP_CALL = re.compile(r"\b(?:read|post|call|httpCall)\(\s*'([a-z_.]+)'")
TOPIC_CALL = re.compile(r"\bsubscribe\(\s*'([a-z_]+)'")
MAX_LINES = 300


def _sources() -> dict[str, str]:
    return {p.relative_to(WEB).as_posix(): p.read_text("utf-8") for p in WEB.rglob("*.js")}


def test_the_web_client_names_only_published_ops_and_topics_and_opens_no_socket_but_its_link() -> (
    None
):
    found = _sources()
    named_ops = {m for text in found.values() for m in OP_CALL.findall(text)}
    named_topics = {m for text in found.values() for m in TOPIC_CALL.findall(text)}
    assert named_ops and named_topics
    assert named_ops <= set(protocol.OPS), named_ops - set(protocol.OPS)
    assert named_topics <= set(protocol.TOPICS), named_topics - set(protocol.TOPICS)
    for name, text in found.items():
        if name not in TRANSPORT_FILES:
            assert "WebSocket(" not in text and "api/v1" not in text.replace("fileUrl", ""), name
        assert len(text.splitlines()) <= MAX_LINES, name
