"""lr-3 — the director's **free-input channel** (自由文本走向,
DEC-OPI-17b0a47f…7): the 走向 channel's second shape — the user's own
written direction — beside the wr-10 candidate menu (the two doors
coexist; the candidates stay the inspiration menu, the text is the
call). The pins, over the production assembly (the real ``run_web``
over the real ``open_host``, the wr-10/lr-4a suites' own shape):

1. **the prompt contract** (VAL ①) — ``free_direction`` rides its own
   section (the chosen-candidate section's sibling); the zero-change
   default holds **byte for byte** against the pre-lr-3 prompts (the
   absolute parent-run baselines below — the judgment face); the
   builder re-checks the bound (blank / over 200 / not a string ⇒
   ``ValueError``);
2. **the endpoint** (VAL ②) — ``POST /api/world/direction`` takes the
   ``{"text"}`` shape (strip-nonblank, ≤200, 200 accepted), refuses
   the malformed family with the two-shape grammar sentence, a free
   write overwrites a candidate write and vice versa (one row, the
   newest call, the ``source`` word tells them apart), ``{}`` clears
   idempotently, and no world binding is the honest 404;
3. **the read and the step** (VAL ③) — the read face answers
   ``("candidate", …)`` for the legacy unmarked row and the marked
   candidate row, ``("free", text)`` for the free row, and absence for
   everything else; a parked free direction exempts the
   directionless crank ceiling (the cap arm reads non-``None``); the
   directed step consumes it on success (选了即用即清 — the next
   prompt carries no written-direction section) and a refusing step
   leaves it parked; immersive never reads it and never passes it;
4. **the page and the sheet** (VAL ④) — the free-input form rides the
   served sources (``{text}`` submit, the parked note, the bilingual
   chrome, the postContinue law) and the direction row's styles are
   the row's own (P13: no ``.chip`` reuse, tokens only);
5. **the end to end** (VAL ⑤) — a directed letter parks, a written
   direction turns the world one step (the prompt carried the text),
   the round parks again, a bare continue walks to the letter and the
   re-entry answers — the full walk, the free-text door included.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from elc.web import _WebFace
from elc.world.narrator import (
    MAX_FREE_DIRECTION_CHARS,
    build_narrator_prompt,
)
from tests.host.test_a1_streaming import _post
from tests.host.test_lr4a_parked_rounds import (
    _CANDIDATES_A,
    _CANDIDATES_B,
    _REFUSING,
    _STEP1,
    _STEP2,
    _STEP3_LETTER,
    _finals,
    _SequencedNarrator,
    _set_directed,
)
from tests.host.test_w1_web import CLEAN_TEXT, REPLY, web_stack
from tests.host.test_wr2_post_turn_wiring import NARRATOR_MARK
from tests.host.test_wr10_web_directions import _pending_rows
from tests.world.test_wr2_narrator import _package

REPO = Path(__file__).resolve().parents[2]

WORLD_ID = "world-berrymoor"

#: The user's own written direction (no trailing period — the prompt
#: template's own ". " join reads clean with it).
FREE_TEXT = "a storm rolls in from the west"

#: The free write's stored row (the read face's contract).
_FREE_ROW = json.dumps({"text": FREE_TEXT, "source": "free"},
                       ensure_ascii=False)

# ---------------------------------------------------------------------------
# 1 — the prompt contract (VAL ①), the byte-for-byte judgment face
# ---------------------------------------------------------------------------

#: The default immersive prompt, machine-read off the post-C1-b builder
#: (the absolute zero-change baseline). C1-b (DEC-OPI-b290799a…17) re-cast
#: this literal from the pre-lr-3 original when the contract teaching
#: went unconditional (the cast-id roster + the optional-keys paragraph);
#: the judgment is unchanged — with ``free_direction`` at its default the
#: prompt is exactly this, byte for byte.
_A_BASELINE = (
    'You are the narrator of a small fictional world.\n\n'
    'Write what happens there next, as a novel would.\n\n'
    "The world moves on its own — weather, seasons, the town's"
    " rhythms, the cast's lives off-stage. It does not react to any"
    " correspondence: letters belong to the penpal layer, not to the"
    " world's narration.\n\n"
    '== The world ==\n\n'
    'Calendar is a small harbour town on a cold coast.\n\n'
    'The boats come in with the morning tide.\n\n'
    'Cast: Nell Alder\n\n'
    "Cast ids (a beat's ``participants`` names these ids and no"
    ' others): persona-nell = Nell Alder\n\n'
    "== The world's established facts ==\n\n"
    '- (Nothing is settled yet.)\n\n'
    '== The story so far ==\n\n'
    '- (The chronicle is empty — this is where the story begins.)\n\n'
    '== Your task ==\n\n'
    "Write the world's next beats — whatever happens next in the"
    " world's own life. Novel prose, small-town voice. Stay"
    " consistent with everything above; never repeat what already"
    " happened. Write exactly 1 or 2 beats. Each beat is one to three"
    " sentences of narration and spans 0, 1 or 2 story days (its"
    " ``days``).\n\n"
    'The narration is written in Chinese (中文).\n\n'
    'Answer with strict JSON only — no prose outside it: {"beats":'
    ' [{"kind": "<slug>", "narration": "<...>", "days": 0}]} The'
    ' ``kind`` is a short slug: lowercase letters, digits and hyphens'
    ' only, at most 32 characters.\n\n'
    'Beside the required ``kind``, ``narration`` and ``days``, each'
    " beat may carry two optional keys. ``effects`` is the beat's"
    ' state-effect proposals — an array, each element exactly {"key":'
    ' <the state key>, "statement": <what becomes true>}; include it'
    ' only when the beat genuinely changes what is true, and leave it'
    ' out when the beat settles nothing. ``participants`` is an array'
    ' of the cast ids present in or taking part in the beat — drawn'
    ' from the roster above and nothing else; leave it out when none'
    ' do.'
)

#: The directed+pending+letter shape's sections below the shared head
#: (machine-read off the parent commit's own code; the head is the
#: ``_A_BASELINE`` prefix above, itself pinned absolute).
_LETTER_SECTION = (
    '== A letter on its way ==\n\n'
    "A letter from the user's character is on its way to the cast —"
    " it was sent 2 days ago. That is a fact of the world's own"
    " calendar, not the letter's contents: the world never knows what"
    " the letter says, and never quotes it. The world moves"
    " naturally; when the letter naturally arrives and she reads it,"
    " mark that beat's stop as letter_arrives.\n\n"
)
_TASK_SECTION = (
    '== Your task ==\n\n'
    "Write the world's next beats — whatever happens next in the"
    " world's own life. Novel prose, small-town voice. Stay"
    " consistent with everything above; never repeat what already"
    " happened. Write exactly 1 or 2 beats. Each beat is one to three"
    " sentences of narration and spans 0, 1 or 2 story days (its"
    " ``days``).\n\n"
)
_DIRECTIONS_SECTION = (
    'Direction candidates: in the same answer, also write 2 to 4'
    ' directions — each is {"label": <a few words, never a sentence>,'
    ' "hint": <one sentence of how the world might go>}. A direction'
    " is the immediate next step the world takes — one concrete"
    " development right now, never a far horizon or a long-range"
    " plan; the user may pick one for it; list them under the"
    ' "directions" key beside the beats.\n\n'
)
_CHOSEN_SECTION = (
    "== The user's chosen direction ==\n\n"
    "The user has chosen where the world goes next: the fair arrives"
    " — Tents dot the cliff meadow.. The world moves in this"
    " direction.\n\n"
)
_LANGUAGE_LINE = "The narration is written in Chinese (中文).\n\n"
_STOP_JSON_LINE = (
    'Answer with strict JSON only — no prose outside it: {"beats":'
    ' [{"kind": "<slug>", "narration": "<...>", "days": 0}],'
    ' "directions": [{"label": "<short phrase>", "hint":'
    ' "<one sentence>"}], "stop": {"kind":'
    ' "<letter_arrives|she_thinks_of_you|awaits_you|none>"}} The'
    ' ``stop`` kind tells the world\'s own verdict: keep going (none,'
    " or no key at all), the letter arriving and read, or the world"
    " waiting on the user. The ``kind`` is a short slug: lowercase"
    " letters, digits and hyphens only, at most 32 characters."
)
_FREE_SECTION = (
    "== The user's written direction ==\n\n"
    "The user has written their own direction for where the world"
    f" goes next: {FREE_TEXT}. Honor it as the director's call — the"
    " world moves in this direction.\n\n"
)

#: C1-b's contract-teaching paragraph, as the assembly of the
#: directed+pending+letter shape reads it (the leading blank line joins
#: it to the stop-JSON line; the paragraph text is pinned inside
#: ``_A_BASELINE`` above — this constant exists so the assembly test
#: names the piece it gained at C1-b).
_C1B_CONTRACT = (
    "\n\n"
    'Beside the required ``kind``, ``narration`` and ``days``, each'
    " beat may carry two optional keys. ``effects`` is the beat's"
    ' state-effect proposals — an array, each element exactly {"key":'
    ' <the state key>, "statement": <what becomes true>}; include it'
    ' only when the beat genuinely changes what is true, and leave it'
    ' out when the beat settles nothing. ``participants`` is an array'
    ' of the cast ids present in or taking part in the beat — drawn'
    ' from the roster above and nothing else; leave it out when none'
    ' do.'
)


def test_the_free_direction_rides_its_own_section() -> None:
    """The written direction is its own section — the chosen-candidate
    section's sibling — carrying the text verbatim and the
    director's-call reading; the candidates requirement stays beside
    it (both doors coexist, the inspiration menu is not displaced)."""

    prompt = build_narrator_prompt(
        _package(),
        (),
        (),
        "zh",
        direction_mode="directed",
        pending_direction=("the fair arrives", "Tents dot the meadow."),
        free_direction=FREE_TEXT,
    )
    assert "== The user's written direction ==" in prompt
    assert (
        "The user has written their own direction for where the world"
        f" goes next: {FREE_TEXT}. Honor it as the director's call —"
        " the world moves in this direction."
    ) in prompt
    # The candidate menu and the chosen section ride beside it.
    assert "== The user's chosen direction ==" in prompt
    assert "Direction candidates:" in prompt
    # The section sits between the chosen section and the language
    # line (the sibling position).
    assert prompt.index("== The user's chosen direction ==") < prompt.index(
        "== The user's written direction =="
    ) < prompt.index("The narration is written in Chinese")
    # A free-only call (no candidate chosen) carries the section too.
    solo = build_narrator_prompt(
        _package(), (), (), "zh", free_direction=FREE_TEXT
    )
    assert "== The user's written direction ==" in solo
    assert FREE_TEXT in solo


def test_the_zero_change_default_holds_byte_for_byte() -> None:
    """The judgment face: with ``free_direction`` at its default the
    prompt is byte for byte the default text — the immersive default
    against the absolute baseline, the directed + pending + letter
    shape against the section assembly (the head is the pinned absolute
    baseline itself). C1-b (DEC-OPI-b290799a…17) re-cast the baseline
    when the contract teaching went unconditional; the judgment (the
    written door adds nothing at the baseline) is lr-3's own, held."""

    pkg = _package()
    assert build_narrator_prompt(pkg, (), (), "zh") == _A_BASELINE
    head = _A_BASELINE.split("== Your task ==")[0]
    assert build_narrator_prompt(
        pkg,
        (),
        (),
        "zh",
        direction_mode="directed",
        pending_direction=("the fair arrives", "Tents dot the cliff"
                           " meadow."),
        letter_elapsed_days=2,
    ) == (
        head
        + _LETTER_SECTION
        + _TASK_SECTION
        + _DIRECTIONS_SECTION
        + _CHOSEN_SECTION
        + _LANGUAGE_LINE
        + _STOP_JSON_LINE
        + _C1B_CONTRACT
    )


@pytest.mark.parametrize(
    "kwargs",
    (
        {"direction_mode": "directed"},
        {
            "direction_mode": "directed",
            "pending_direction": ("the fair arrives", "Tents."),
        },
    ),
    ids=("directed-no-pending", "directed-plus-candidate"),
)
def test_free_insertion_lands_exactly_at_the_language_seam(
    kwargs: dict,
) -> None:
    """The two remaining default shapes (directed without a pending
    row, directed with one) are byte-neutral too: the free-carrying
    prompt equals the default prompt with the free section inserted
    exactly once, exactly at the language line (nothing else moved —
    the two absolute baselines above pin the shapes themselves)."""

    pkg = _package()
    base = build_narrator_prompt(pkg, (), (), "zh", **kwargs)
    free = build_narrator_prompt(
        pkg, (), (), "zh", free_direction=FREE_TEXT, **kwargs
    )
    assert free == base.replace(
        "The narration is written in Chinese (中文).",
        _FREE_SECTION + "The narration is written in Chinese (中文).",
    )


def test_the_builder_re_checks_the_free_bound() -> None:
    """The prompt builder re-checks what the write face enforced: a
    blank, an over-cap or a non-string free direction is a
    ``ValueError`` naming the bound — a wider row cannot reach the
    prompt through this door."""

    pkg = _package()
    for bad in ("", "   ", "x" * (MAX_FREE_DIRECTION_CHARS + 1), 123,
                b"bytes"):
        with pytest.raises(ValueError, match="200"):
            build_narrator_prompt(pkg, (), (), "zh", free_direction=bad)  # type: ignore[arg-type]
    assert MAX_FREE_DIRECTION_CHARS == 200


# ---------------------------------------------------------------------------
# 2 — the endpoint's free-text shape (VAL ②)
# ---------------------------------------------------------------------------


def test_the_free_text_shape_parks_and_the_grammar_refuses(
    tmp_path: Path,
) -> None:
    """``{"text"}`` parks under the bound world's key marked
    ``source: "free"`` (200 accepted); the malformed family — blank,
    whitespace, over the cap, not a string, a mixed-key body, a
    non-object — is the 400 two-shape grammar sentence; the cap edge
    (exactly 200) passes."""

    with web_stack(tmp_path / "app.db") as stack:
        status, saved = stack.post(
            "/api/world/direction", {"text": FREE_TEXT}
        )
        assert status == 200
        assert saved == {"accepted": True, "cleared": False, "error": None}
        assert _pending_rows(tmp_path / "app.db") == [
            ("world_pending_direction:" + WORLD_ID, _FREE_ROW)
        ]
        # The cap edge: exactly 200 characters is in.
        status, saved = stack.post(
            "/api/world/direction", {"text": "x" * 200}
        )
        assert status == 200 and saved["accepted"] is True
        for body in (
            {"text": ""},
            {"text": "   "},
            {"text": "x" * 201},
            {"text": 123},
            {"text": "a", "label": "b"},
            "not an object",
        ):
            status, refused = stack.post("/api/world/direction", body)
            assert status == 400, body
            # The grammar names both shapes (the free door and the
            # candidate door).
            assert '"text"' in refused["error"]
            assert '"label"' in refused["error"]
        status, cleared = stack.post("/api/world/direction", {})
        assert status == 200 and cleared["cleared"] is True
        assert _pending_rows(tmp_path / "app.db") == []
        # The clear arm is idempotent.
        status, cleared = stack.post("/api/world/direction", {})
        assert status == 200 and cleared["cleared"] is True


def test_free_and_candidate_writes_overwrite_each_other(
    tmp_path: Path,
) -> None:
    """One pending key, two shapes: a free write overwrites a candidate
    write and vice versa — the newest call stands, the ``source`` word
    tells them apart, and ``{}`` clears either."""

    app_db = tmp_path / "app.db"
    with web_stack(app_db) as stack:
        status, _ = stack.post(
            "/api/world/direction",
            {"label": "the fair arrives", "hint": "Tents dot the meadow."},
        )
        assert status == 200
        rows = _pending_rows(app_db)
        assert len(rows) == 1
        assert json.loads(rows[0][1]) == {
            "label": "the fair arrives",
            "hint": "Tents dot the meadow.",
            "source": "candidate",
        }
        status, _ = stack.post("/api/world/direction", {"text": FREE_TEXT})
        assert status == 200
        rows = _pending_rows(app_db)
        assert len(rows) == 1
        assert json.loads(rows[0][1]) == {"text": FREE_TEXT,
                                          "source": "free"}
        status, _ = stack.post(
            "/api/world/direction",
            {"label": "a storm rolls in", "hint": "Weather braces."},
        )
        assert status == 200
        rows = _pending_rows(app_db)
        assert len(rows) == 1
        assert json.loads(rows[0][1])["source"] == "candidate"
        status, cleared = stack.post("/api/world/direction", {})
        assert status == 200
        assert _pending_rows(app_db) == []


def test_the_free_shape_404s_without_a_binding() -> None:
    """A conversation outside any world has no direction channel in
    either shape: the honest 404, never a parked row."""

    class _NoWorldHost:
        app_db_path = "stub.db"

    face = _WebFace(_NoWorldHost(), "web-test")  # type: ignore[arg-type]
    status, payload = face.world_direction_save({"text": FREE_TEXT})
    assert status == 404
    assert "没有绑定任何世界" in payload["error"]


# ---------------------------------------------------------------------------
# 3 — the read face and the step face (VAL ③)
# ---------------------------------------------------------------------------


class _Settings:
    """A minimal app_settings double (get/set/delete over a dict)."""

    def __init__(self) -> None:
        self.rows: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.rows.get(key)

    def set(self, key: str, value: str) -> None:
        self.rows[key] = value

    def delete(self, key: str) -> None:
        self.rows.pop(key, None)


class _Host:
    """The two attributes the face touches (the settings rows and the
    db path stamp the constructor reads)."""

    def __init__(self) -> None:
        self.app_db_path = "stub.db"
        self.app_settings = _Settings()


def test_the_read_face_tells_the_two_shapes() -> None:
    """The pending read answers ``("candidate", (label, hint))`` for
    the legacy unmarked row **and** the marked candidate row,
    ``("free", text)`` for the free row — and absence for every
    corrupt or oddly-shaped row (the defensive law, the two-shape
    edition)."""

    face = _WebFace(_Host(), "web-test")  # type: ignore[arg-type]
    key = "world_pending_direction:world-x"
    assert face._world_pending_direction("world-x") is None
    face._host.app_settings.set(
        key, json.dumps({"label": "a", "hint": "b"})
    )
    assert face._world_pending_direction("world-x") == (
        "candidate",
        ("a", "b"),
    )
    face._host.app_settings.set(
        key,
        json.dumps({"label": "a", "hint": "b", "source": "candidate"}),
    )
    assert face._world_pending_direction("world-x") == (
        "candidate",
        ("a", "b"),
    )
    face._host.app_settings.set(
        key, json.dumps({"text": FREE_TEXT, "source": "free"})
    )
    assert face._world_pending_direction("world-x") == ("free", FREE_TEXT)
    for corrupt in (
        "not json",
        json.dumps({"text": FREE_TEXT}),
        json.dumps({"text": FREE_TEXT, "source": "candidate"}),
        json.dumps({"label": "a", "hint": "b", "source": "free"}),
        json.dumps({"label": 1, "hint": "b"}),
        json.dumps({"label": "a", "hint": "b", "extra": 1}),
        json.dumps({"text": 9, "source": "free"}),
        json.dumps([1, 2]),
        # LOW-1 family (the disposal knife): a whitespace-only row is
        # corrupt too — the write face's strip law must not leak past
        # this reader (its own docstring promises absent, never a
        # prompt-builder ValueError downstream).
        json.dumps({"label": "   ", "hint": "b"}),
        json.dumps({"label": "a", "hint": "  ", "source": "candidate"}),
        json.dumps({"text": "   ", "source": "free"}),
    ):
        face._host.app_settings.set(key, corrupt)
        assert face._world_pending_direction("world-x") is None, corrupt


def test_a_parked_free_direction_bypasses_the_crank_ceiling(
    tmp_path: Path, monkeypatch
) -> None:
    """The cap arm reads non-``None``: with the ceiling at one and a
    **free-text** direction parked, a continue is not capped — the
    written direction moves the world past any count (the candidate
    shape's own law, the second shape included)."""

    import elc.web as web_module

    monkeypatch.setattr(web_module, "MAX_PARKED_STOPS", 1)
    provider = _SequencedNarrator([_STEP1, _STEP2])
    with web_stack(tmp_path / "app.db", provider=provider) as stack:
        _set_directed(stack)
        status, _raw = _post(stack.port, "/api/turn_stream",
                             {"text": CLEAN_TEXT})
        assert status == 200
        status, _ = stack.post("/api/world/direction", {"text": FREE_TEXT})
        assert status == 200
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 1
        assert final["parked"] is True
        assert final["capped"] is False


def test_immersive_never_reads_the_pending_direction(
    tmp_path: Path,
) -> None:
    """Immersive passes neither shape: with a free direction parked and
    the mode at its default, the step's prompt carries no written and
    no chosen section and no candidates requirement — and the row is
    **not consumed** (a mode that never read it cannot have used it)."""

    provider = _SequencedNarrator([_STEP1])
    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=provider) as stack:
        status, _ = stack.post("/api/world/direction", {"text": FREE_TEXT})
        assert status == 200
        status, _turn = stack.post("/api/turn", {"text": CLEAN_TEXT})
        assert status == 200
        prompt = next(
            text for text in provider.prompts if NARRATOR_MARK in text
        )
        assert "The user's written direction" not in prompt
        assert "The user's chosen direction" not in prompt
        assert "Direction candidates:" not in prompt
        rows = _pending_rows(app_db)
        assert len(rows) == 1
        assert rows[0][1] == _FREE_ROW


# ---------------------------------------------------------------------------
# 4 — the page and the sheet (VAL ④)
# ---------------------------------------------------------------------------


def test_the_page_carries_the_free_input_form() -> None:
    """The served sources carry the free-input shape: the ``{text}``
    submit with the trim-blank guard, the parked note (consumption
    made visible), the bilingual chrome, the postContinue law on both
    doors, and the P13 class rename (the row's own ``--on`` class, no
    ``chip`` reuse left in the direction code)."""

    app = (REPO / "src" / "elc" / "webui" / "app.js").read_text(
        encoding="utf-8"
    )
    api = (REPO / "src" / "elc" / "webui" / "api.js").read_text(
        encoding="utf-8"
    )
    # The free form: input + submit + payload.
    assert "world-direction-free" in app
    assert "world-direction-free-input" in app
    assert 'input.type = "text";' in app
    assert "input.maxLength = 200;" in app
    assert "const value = input.value.trim();" in app
    assert "if (!value) return;" in app
    assert "fetchSaveWorldDirection({ text: value })" in app
    # The parked note: consumption made visible (textContent).
    assert "world-direction-parked" in app
    assert "parked.textContent = T.directionParked + value;" in app
    # The bilingual chrome.
    assert "自己写一个走向……" in app
    assert "Write your own direction…" in app
    assert "记下这条走向" in app
    assert "Set this direction" in app
    assert "你的走向已记下：" in app
    assert "Your direction is set: " in app
    # lr-3T (DEC-OPI-09b3935b…13, the zero-template law): the ask
    # sentence is retired — the row is the candidates plus the free
    # form, and the input placeholder carries the affordance (pinned
    # above, both languages).
    assert "选一个走向，或自己写一个。" not in app
    assert "or write your own." not in app
    assert "T.directionAsk" not in app
    # The postContinue law rides both doors now.
    assert app.count("if (parkedRound) postContinue();") == 2
    # P13: the row's own classes; no chip reuse in the direction code.
    assert "world-direction-option--on" in app
    assert "chip world-direction-option" not in app
    start = app.find("function expireWorldDirectionRow")
    end = app.find("function renderWorldStory")
    assert start != -1 and end != -1 and start < end
    direction_code = app[start:end]
    assert "chip--on" not in direction_code
    assert "world-direction-option" in direction_code
    # Zero scroll hijack (wr-5 律) and textContent discipline hold.
    assert "scroll" not in direction_code.lower()
    assert ".innerHTML" not in app
    assert ".innerHTML" not in api
    # The api docstring names the two payload shapes.
    assert "{text}" in api
    assert 'postJson("/api/world/direction", payload)' in api


def test_the_sheet_declares_the_row_s_own_styles() -> None:
    """P13's landing: components.css owns the direction row — the row,
    the option, its on-state, the free form and the parked note — with
    no ``.chip`` reference and no literal color anywhere in the lr-3
    section (tokens only, EC8S)."""

    css = (REPO / "src" / "elc" / "webui" / "components.css").read_text(
        encoding="utf-8"
    )
    for selector in (
        ".world-direction-row {",
        ".world-direction-option {",
        ".world-direction-option--on {",
        ".world-direction-free {",
        ".world-direction-parked {",
    ):
        assert selector in css, selector
    marker = "/* ── lr-3（DEC-OPI-17b0a47f…7）：走向行专属样式"
    start = css.find(marker)
    assert start != -1
    section = css[start:]
    # The rule declarations reference no .chip (the section's own
    # prose may name the retired reuse — strip comments first).
    code = section
    while True:
        head_at = code.find("/*")
        if head_at < 0:
            break
        tail_at = code.find("*/", head_at)
        assert tail_at > head_at
        code = code[:head_at] + code[tail_at + 2:]
    assert ".chip" not in code
    assert "#" not in code
    # The hover lives inside its wrapper (the touch discipline).
    assert ":hover" in code
    hover_at = code.find(":hover")
    wrapper_before = code.rfind("@media (hover: hover)", 0, hover_at)
    assert wrapper_before != -1
    # lr-3V（DEC-OPI-41a4df20…1）：候选 chip 两行形——label 主行与 hint
    # 注行各自块化（摘要与内容两行可读，不再行内连排糊成一句）。
    label_at = code.find(".world-direction-option .world-direction-option-label {")
    hint_at = code.find(".world-direction-option .world-direction-option-hint {")
    assert label_at != -1 and hint_at != -1
    label_body = code[code.find("{", label_at) + 1 : code.find("}", label_at)]
    hint_body = code[code.find("{", hint_at) + 1 : code.find("}", hint_at)]
    assert "display: block" in label_body and "display: block" in hint_body
    assert "font-weight: 600" in label_body
    assert "margin: var(--sp-1) 0 0" in hint_body
    # 处置补（总控目验抓到尺寸倒挂）：label 是主行、hint 是注行——
    # 字号不许倒挂（.note 的 t-note 是 14.5px fs-small，比 chip 底字
    # 12.5px fs-ui 还大，hint 若不显式降档反而成为 chip 里最大的字）。
    assert "font-size: var(--fs-small)" in label_body
    assert "font-size: var(--fs-ui)" in hint_body
    # 反白保护：label 不显式设色——按钮态色由继承承担，显式 color 破 --on 反白。
    assert "color" not in label_body


# ---------------------------------------------------------------------------
# 5 — the end to end (VAL ⑤): the free door in the full walk
# ---------------------------------------------------------------------------


def test_the_directed_round_walks_on_a_written_direction(
    tmp_path: Path,
) -> None:
    """The full walk with the free-text door: a directed letter parks
    (candidates A), the user's written direction rides the continue's
    step prompt (the director's call, consumed on success), the round
    parks again (candidates B), a bare continue walks to the letter
    and the same-command re-entry answers — one turn record, the round
    closed, the written direction used exactly once."""

    provider = _SequencedNarrator([_STEP1, _STEP2, _STEP3_LETTER])
    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=provider) as stack:
        _set_directed(stack)
        status, raw = _post(stack.port, "/api/turn_stream",
                            {"text": CLEAN_TEXT})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 1
        assert final["parked"] is True
        assert final["directions"] == list(_CANDIDATES_A)
        # The written direction parks.
        status, saved = stack.post(
            "/api/world/direction", {"text": FREE_TEXT}
        )
        assert status == 200 and saved["accepted"] is True
        # The continue turns one step with it.
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, worlds = _finals(raw)
        assert len(worlds) == 1
        assert final["parked"] is True
        assert final["directions"] == list(_CANDIDATES_B)
        prompts = [
            text for text in provider.prompts if NARRATOR_MARK in text
        ]
        assert "The user's written direction" in prompts[-1]
        assert FREE_TEXT in prompts[-1]
        assert _pending_rows(app_db) == []
        # A bare continue walks to the letter — the written direction
        # is gone from the prompt (consumed), the re-entry answers.
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, _worlds = _finals(raw)
        assert final["reply"] == REPLY
        assert final["turn_status"] == "COMPLETED"
        prompts = [
            text for text in provider.prompts if NARRATOR_MARK in text
        ]
        assert "The user's written direction" not in prompts[-1]
        assert _pending_rows(app_db) == []
        assert _parked_rows(app_db) == []


def _parked_rows(app_db: Path) -> list[tuple[str, str]]:
    """The parking rows off the serving database (the lr-4a posture,
    re-declared here to keep this module's imports flat)."""

    import sqlite3

    ro = sqlite3.connect(app_db.as_uri() + "?mode=ro", uri=True)
    try:
        return list(
            ro.execute(
                "SELECT key, value FROM app_setting"
                " WHERE key LIKE 'world_parked_turn:%' ORDER BY key"
            ).fetchall()
        )
    finally:
        ro.close()


def test_a_refusing_step_keeps_the_written_direction_parked(
    tmp_path: Path,
) -> None:
    """拒收不清, the free shape included: a narrator refusal on the
    continue's step leaves the written direction parked — the world
    never heard it, so it waits for the next step."""

    provider = _SequencedNarrator([_STEP1, _REFUSING])
    app_db = tmp_path / "app.db"
    with web_stack(app_db, provider=provider) as stack:
        _set_directed(stack)
        status, _raw = _post(stack.port, "/api/turn_stream",
                             {"text": CLEAN_TEXT})
        assert status == 200
        status, _ = stack.post("/api/world/direction", {"text": FREE_TEXT})
        assert status == 200
        status, raw = _post(stack.port, "/api/world/continue", {})
        assert status == 200
        final, worlds = _finals(raw)
        assert worlds == []
        assert final["parked"] is True
        rows = _pending_rows(app_db)
        assert len(rows) == 1
        assert rows[0][1] == _FREE_ROW
