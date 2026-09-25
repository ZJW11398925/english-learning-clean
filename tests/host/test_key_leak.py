"""The two key-leak pins (prep-1 deliverable E ②) — RA §24.3 made executable.

(a) No string the provider returns ever carries the key, on any vector: a
    rejected request whose error body echoes the header, a dead transport whose
    exception message quotes it, an unparseable body made of it, and a normal
    answer. Each vector also asserts the **negative control** — the transport
    really received ``Bearer <sentinel>`` — so the pin cannot pass by the key
    never having travelled.
(b) A whole turn through the real host with the real adapter leaves the key in
    no table of app.db, nor anywhere in the file or its WAL: V1's schema has
    neither a key column nor (yet) a ``secret_ref`` column, and canonical's
    intent is that app.db keeps only the *reference*, never the secret
    (DATA_MODEL §2; deletion/store.py "V1 keeps no secret in app.db"). The same
    holds when the provider answers a hostile 2xx that echoes the key back —
    that reply is refused (``key-echo``), so the echo never reaches the
    transcript either (prep-1 review F3).

Boundary registered honestly: a provider whose 2xx text merely *mentions* a
key-shaped string the adapter never sent is not a leak of this process's key
and is not filtered — the guard fires on the resolved key itself, and this
process never puts the key anywhere but the one header.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from elc.conversation.types import CommitUserTurn
from elc.host import open_host
from elc.persona.openai_provider import REASON_KEY_ECHO, OpenAICompatibleProvider
from elc.persona.types import CompiledPrompt
from elc.platform.types import (
    ClientMessageId,
    ConversationId,
    InputId,
    InteractionChannel,
    Ok,
    PersonaId,
    Result,
)
from elc.runtime.types import InputEnvelope, TurnCompletion
from tests.host.support import (
    REPLY_TEXT,
    SENTINEL_KEY,
    FixedSecret,
    RecordingPost,
    app_db_bytes,
    completion,
    config,
    db_text_cells,
)

CONV = ConversationId("leak-conv")


def compiled_prompt() -> CompiledPrompt:
    return CompiledPrompt(
        persona_id=PersonaId("persona-offline"),
        prompt_text="hello there",
        generation_contract="gc-normal-persona-reply",
    )


def command(text: str) -> CommitUserTurn:
    suffix = uuid.uuid4().hex
    return CommitUserTurn(
        conversation_id=CONV,
        envelope=InputEnvelope(
            input_id=InputId(f"leak-{suffix}"),
            client_message_id=ClientMessageId(f"leak-msg-{suffix}"),
            conversation_id=str(CONV),
            persona_id=None,
            scene_id=None,
            interaction_channel=InteractionChannel.TEXT,
            raw_payload=text,
            received_at=datetime.now(tz=UTC).isoformat(),
        ),
        raw_content=text,
        runtime_version="runtime-v1",
    )


def test_no_returned_string_carries_the_key() -> None:
    vectors = {
        "rejected-request-echoes-header": RecordingPost(
            status=401, payload=f"denied: Bearer {SENTINEL_KEY}".encode()
        ),
        "transport-exception-quotes-key": RecordingPost(
            raises=OSError(f"connect failed with header Bearer {SENTINEL_KEY}")
        ),
        "unparseable-body-is-the-key": RecordingPost(payload=SENTINEL_KEY.encode()),
        "hostile-2xx-echoes-header": RecordingPost(
            payload=completion(f"you said Bearer {SENTINEL_KEY}")
        ),
        "normal-answer": RecordingPost(payload=completion()),
    }
    outputs: dict[str, object] = {}
    for name, post in vectors.items():
        provider = OpenAICompatibleProvider(config(), FixedSecret(), transport=post)
        output = provider.call(compiled_prompt())
        outputs[name] = output
        # Negative control: the key really travelled in this vector.
        assert post.authorization == f"Bearer {SENTINEL_KEY}", name
        for value in (output.text, output.error, repr(output)):
            assert value is None or SENTINEL_KEY not in value, (name, value)
    # The hostile 2xx is refused rather than delivered (prep-1 review F3): a
    # reply can only carry the key by leaking it, so the whole text is dropped.
    assert (
        outputs["hostile-2xx-echoes-header"].error  # type: ignore[attr-defined]
        == REASON_KEY_ECHO
    )


def test_the_key_reaches_the_wire_and_never_reaches_app_db(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    post = RecordingPost(payload=completion(REPLY_TEXT))
    host = open_host(
        db_path,
        provider=OpenAICompatibleProvider(config(), FixedSecret(), transport=post),
        secrets=FixedSecret(),
    )
    try:
        assert isinstance(host.open_conversation(CONV), Ok)
        result: Result[TurnCompletion] = host.coordinator.begin_turn(command("hello"))
        assert isinstance(result, Ok), result
        assert result.value.reply_text == REPLY_TEXT
        # The turn really used the provider (a pin over an unused seam is void).
        assert post.authorization == f"Bearer {SENTINEL_KEY}"
        hits = [
            (table, value)
            for table, value in db_text_cells(host.db)
            if SENTINEL_KEY in value
        ]
        assert hits == []
    finally:
        host.close()
    assert SENTINEL_KEY.encode() not in app_db_bytes(db_path)


def test_an_echoing_2xx_reply_never_reaches_the_transcript_or_app_db(
    tmp_path: Path,
) -> None:
    """The durable half of the F3 guard: a hostile 2xx echo is refused as a
    value, so the key enters neither the transcript nor the database file."""

    db_path = tmp_path / "app.db"
    echo = RecordingPost(payload=completion(f"you said Bearer {SENTINEL_KEY}"))
    host = open_host(
        db_path,
        provider=OpenAICompatibleProvider(config(), FixedSecret(), transport=echo),
        secrets=FixedSecret(),
    )
    try:
        assert isinstance(host.open_conversation(CONV), Ok)
        result: Result[TurnCompletion] = host.coordinator.begin_turn(command("hello"))
        assert isinstance(result, Ok), result
        assert result.value.reply_text is None
        assert result.value.failure_reason == "key-echo"
        # The key really was sent (the echo is what the fake server answered)…
        assert echo.authorization == f"Bearer {SENTINEL_KEY}"
        # …and the refused reply left nothing behind: no assistant turn, and no
        # table cell anywhere in app.db.
        assert host.db.execute("SELECT COUNT(*) FROM assistant_turn").fetchone()[0] == 0
        hits = [
            (table, value)
            for table, value in db_text_cells(host.db)
            if SENTINEL_KEY in value
        ]
        assert hits == []
    finally:
        host.close()
    assert SENTINEL_KEY.encode() not in app_db_bytes(db_path)
