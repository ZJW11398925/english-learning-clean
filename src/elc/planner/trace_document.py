"""The §14 ``factor_trace`` column's one encoding (Phase 9 P9-0).

docs/DATA_MODEL.md §14's ``PlannerEvaluation`` block carries ``factor_trace``
and spells nothing about its type. §27's rule applies — the column's physical
form is the implementation's — and P8-0 spent it on a bare JSON array of the
run's prose reasons (``_array_document(reason_trace)``): the durable row kept
*why* in sentences and none of *what the kernel looked at*. That gap is the
P9-0 carryover finding, and this module is the fix's single point: the
column now carries a **versioned structured document** whose ``candidates``
array holds every field of the kernel's :class:`~elc.planner.kernel.
CandidateTrace`, with the run's prose under ``reasons`` and two words saying
whether a kernel trace was recorded at all.

**The shape.** :class:`~elc.platform.types.FactorTraceDocument` (the shape
lives beside the record, in the platform leaf module) with the four keys
``version`` / ``provenance`` / ``reasons`` / ``candidates``. One encoder
(:func:`factor_trace_document`), one builder (:func:`factor_trace_of`), one
decoder (:func:`decode_factor_trace`) — the port (``elc.planner.records``)
documents the column map and the SQL adapter (``elc.platform.db.
planner_store``) performs it, exactly as P8-0 split them.

**Determinism, and which order is canonicalized.** Same input, same bytes:
the document is built with ``sort_keys=True`` and the compact separators
(``(",", ":")`` — the repository's ``_array_document`` spelling), and the
fields whose tuple order is *incidental* are canonicalized on the way in:

- ``candidates`` are ordered by ``candidate_id``;
- each candidate's ``benefit`` / ``cost`` readings are ordered by ``factor``
  name, and its ``gaps`` by ``(factor, authority)``.

The kernel's own candidate order is BF-02 §4's canonical order — by
``canonical_key`` — and it is **re-derivable** from the document itself
(every candidate carries its ``canonical_key``), so canonicalizing loses no
fact that the document does not already state. The fields whose order is a
datum rather than an artifact — ``merged_from``, ``dominated_by``,
``reasons`` — keep the order the trace carries them in.

**The legacy arm, and how a reader tells the two apart.** A row written
before this cut carries a JSON **array** (the prose lines); a row written
from this cut carries a JSON **object** with a ``version`` key. The decoder
answers the first as the tuple of lines it always was — the shape P8-0's
readers were built on — and the second as a
:class:`~elc.platform.types.FactorTraceDocument`. The discriminant is
``version``'s presence and nothing else (no heuristics on the array's
contents), which is what makes the two arms unambiguous; the reading is
registered in ``elc.planner.records`` judgement 9 with its revisit.

**Declared judgements.** Each entry is this cut's reading rather than a
quotation, and each names the condition that re-opens it.

1. **The prose stays, as one key of the document.** §14 gives the run's
   reason trace no column of its own, and P9-0's ruling splits ``factor_
   trace`` from ``reason_trace``: the column is no longer the prose array.
   This cut reads the split as "the prose travels as a named part of the
   structured document" rather than "the prose is dropped", for two reasons
   that are checkable: the store's replay agreement compares the durable
   evaluation, and dropping the prose would silently remove one of the five
   values it compares (a **weakening** of an existing pin); and the prose is
   the only durable answer to "why did this run go as it did" on rows that
   carry no candidate trace. Revisit: canonical text gives the reasons a
   column of their own (then the ``reasons`` key retires and this module
   gains a second mapped column), or a cut decides the durable row must not
   carry prose at all (then the replay comparison has to lose that arm on
   purpose, with the same tests moved).
2. **``provenance`` is recorded rather than inferred.** Two words —
   ``KERNEL_TRACE`` when the writer held the kernel's :class:`~elc.planner.
   kernel.PlannerTrace`, ``NOT_RECORDED`` when it did not (a leg that could
   not run records a degraded shape of its own and holds no trace). Without
   the key, an empty ``candidates`` array would conflate "the run planned
   over no canonical candidate" with "nobody wrote down what it looked at" —
   two different facts about a cycle (the ``ShadowRun.canonical_count``
   distinction, made durable). Revisit: a caller appears that legitimately
   holds no trace for a cycle the Planner *did* run (then the word needs a
   third value), or canonical text names this axis.
3. **The decoder is strict, and raises.** An unparseable document, or a
   JSON value that is neither the versioned object nor the legacy array,
   raises ``ValueError`` naming the key — the same shape the existing
   ``_array_from_document`` decode has (a dirty row raises rather than being
   smoothed into an empty value; the p6-2 F-2 family's registered
   convention). The refusal is element-deep where a key carries a list: every
   element of ``reasons`` / ``merged_from`` / ``dominated_by`` is read through
   the scalar rule, so a non-string element is refused rather than washed
   through ``str()``. Revisit: a read face wants the refusal as an ``Err`` rather
   than an exception (then this decoder grows a ``Result`` sibling, and
   every caller names which one it reads).
4. **The encoding is versioned, and the version is checked.** A document
   whose ``version`` is not :data:`FACTOR_TRACE_VERSION` is refused rather
   than decoded on a best-effort basis: a later version's rows must be read
   by a cut that says what changed, not guessed at by this one. Revisit: the
   shape changes and the decoder learns a second version (the ``ft1`` string
   is the discriminator the tests pin).
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from elc.planner.kernel import CandidateTrace, FactorGap, FactorReading
from elc.platform.types import (
    CandidateTraceDocument,
    FactorGapDocument,
    FactorReadingDocument,
    FactorTraceDocument,
)

__all__ = [
    "FACTOR_TRACE_PROVENANCE_KERNEL",
    "FACTOR_TRACE_PROVENANCE_NONE",
    "FACTOR_TRACE_VERSION",
    "decode_factor_trace",
    "factor_trace_document",
    "factor_trace_of",
]

#: The document's version word. It is the discriminant between this encoding
#: and the legacy bare array (judgement 3), and it is pinned by test.
FACTOR_TRACE_VERSION = "ft1"

#: ``provenance``'s two words (judgement 2): the writer held the kernel's own
#: trace, or it did not.
FACTOR_TRACE_PROVENANCE_KERNEL = "KERNEL_TRACE"
FACTOR_TRACE_PROVENANCE_NONE = "NOT_RECORDED"


def factor_trace_of(
    *,
    reasons: Sequence[str],
    candidates: Sequence[CandidateTrace] = (),
    traced: bool,
) -> FactorTraceDocument:
    """Build the document from a run's prose and its candidate traces.

    The two inputs are the two halves of one evaluation: ``reasons`` is
    ``PlannerEvaluation.reason_trace`` (the run's own sentences, in its own
    order) and ``candidates`` is ``PlannerTrace.candidates`` — present only
    when the writer held the trace (``traced``; judgement 2).

    This is the only place the field order and the canonicalization rules
    above are applied, so a document built here and a document decoded from a
    row this module wrote are the same object (round-tripped in the tests).
    """

    ordered = sorted(candidates, key=lambda candidate: candidate.candidate_id)
    return FactorTraceDocument(
        version=FACTOR_TRACE_VERSION,
        provenance=(
            FACTOR_TRACE_PROVENANCE_KERNEL
            if traced
            else FACTOR_TRACE_PROVENANCE_NONE
        ),
        reasons=tuple(str(reason) for reason in reasons),
        candidates=tuple(_candidate_document(candidate) for candidate in ordered),
    )


def factor_trace_document(document: FactorTraceDocument) -> str:
    """The document as the column's bytes (deterministic; pins the encoding).

    ``sort_keys=True`` and the compact separators are the repository's
    document spelling (``elc/teaching/store.py``'s ``_array_document``), so a
    stored document is one line with its keys in one fixed order — which is
    also what makes the encoder a function: two documents with equal content
    encode to equal bytes, and the decoder's inverse re-encodes to the same
    bytes it read.
    """

    return json.dumps(
        _document_payload(document), sort_keys=True, separators=(",", ":")
    )


def decode_factor_trace(raw: object) -> FactorTraceDocument | tuple[str, ...]:
    """One durable document, decoded into its structured shape (judgement 3).

    A JSON **object** carrying this module's ``version`` becomes a
    :class:`~elc.platform.types.FactorTraceDocument`; a JSON **array** is the
    legacy encoding and becomes the tuple of prose lines it always was. Any
    other value — or an object whose ``version`` is a word this module does
    not own — raises ``ValueError`` naming what was found, because a decoder
    that guesses is a reader that lies about the row.
    """

    loaded = json.loads(str(raw))
    if isinstance(loaded, list):
        return tuple(str(item) for item in loaded)
    if not isinstance(loaded, dict):
        raise ValueError(
            "factor_trace is neither a versioned object nor a legacy array:"
            f" {type(loaded).__name__}"
        )
    version = loaded.get("version")
    if version != FACTOR_TRACE_VERSION:
        raise ValueError(
            f"factor_trace carries version {version!r}, which this cut does"
            f" not decode (it owns {FACTOR_TRACE_VERSION!r})"
        )
    return FactorTraceDocument(
        version=FACTOR_TRACE_VERSION,
        provenance=_text(loaded, "provenance"),
        reasons=_text_tuple(loaded, "reasons"),
        candidates=tuple(
            _candidate_from_payload(item)
            for item in _sequence(loaded, "candidates")
        ),
    )


# -- the payload builders ----------------------------------------------------


def _document_payload(document: FactorTraceDocument) -> dict[str, Any]:
    return {
        "version": document.version,
        "provenance": document.provenance,
        "reasons": list(document.reasons),
        "candidates": [
            _candidate_payload(candidate) for candidate in document.candidates
        ],
    }


def _reading_document(reading: FactorReading) -> FactorReadingDocument:
    """One kernel reading, as the document carries it. The enums are recorded
    as their string values: the document is durable text and does not depend
    on an enum's identity."""

    return FactorReadingDocument(
        factor=str(reading.factor.value),
        value=float(reading.value),
        source=str(reading.source.value),
        authority=_optional_word(reading.authority),
    )


def _gap_document(gap: FactorGap) -> FactorGapDocument:
    return FactorGapDocument(
        factor=str(gap.factor.value),
        authority=str(gap.authority.value),
        reason=str(gap.reason),
    )


def _candidate_document(candidate: CandidateTrace) -> CandidateTraceDocument:
    readings = sorted(
        (_reading_document(reading) for reading in candidate.benefit),
        key=lambda reading: reading.factor,
    )
    costs = sorted(
        (_reading_document(reading) for reading in candidate.cost),
        key=lambda reading: reading.factor,
    )
    gaps = sorted(
        (_gap_document(gap) for gap in candidate.gaps),
        key=lambda gap: (gap.factor, gap.authority),
    )
    return CandidateTraceDocument(
        candidate_id=str(candidate.candidate_id),
        canonical_key=str(candidate.canonical_key),
        merged_from=tuple(str(item) for item in candidate.merged_from),
        initiative_class=str(candidate.initiative_class.value),
        request_priority=int(candidate.request_priority),
        coverage_service_state=str(candidate.coverage_service_state.value),
        benefit=tuple(readings),
        cost=tuple(costs),
        gaps=tuple(gaps),
        excluded=_optional_word(candidate.excluded),
        benefit_score=candidate.benefit_score,
        cost_score=candidate.cost_score,
        coverage_service_bonus=candidate.coverage_service_bonus,
        utility=candidate.utility,
        activation_path=_optional_word(candidate.activation_path),
        activation_threshold=candidate.activation_threshold,
        activated=candidate.activated,
        dominated_by=tuple(str(item) for item in candidate.dominated_by),
        in_tie_set=bool(candidate.in_tie_set),
        selected=bool(candidate.selected),
    )


def _optional_word(value: object) -> str | None:
    """A word-bearing value, or ``None`` — the kernel's enum or the absence."""

    if value is None:
        return None
    return str(getattr(value, "value", value))


def _reading_payload(reading: FactorReadingDocument) -> dict[str, Any]:
    return {
        "factor": reading.factor,
        "value": reading.value,
        "source": reading.source,
        "authority": reading.authority,
    }


def _gap_payload(gap: FactorGapDocument) -> dict[str, Any]:
    return {
        "factor": gap.factor,
        "authority": gap.authority,
        "reason": gap.reason,
    }


def _candidate_payload(candidate: CandidateTraceDocument) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "canonical_key": candidate.canonical_key,
        "merged_from": list(candidate.merged_from),
        "initiative_class": candidate.initiative_class,
        "request_priority": candidate.request_priority,
        "coverage_service_state": candidate.coverage_service_state,
        "benefit": [_reading_payload(item) for item in candidate.benefit],
        "cost": [_reading_payload(item) for item in candidate.cost],
        "gaps": [_gap_payload(item) for item in candidate.gaps],
        "excluded": candidate.excluded,
        "benefit_score": candidate.benefit_score,
        "cost_score": candidate.cost_score,
        "coverage_service_bonus": candidate.coverage_service_bonus,
        "utility": candidate.utility,
        "activation_path": candidate.activation_path,
        "activation_threshold": candidate.activation_threshold,
        "activated": candidate.activated,
        "dominated_by": list(candidate.dominated_by),
        "in_tie_set": candidate.in_tie_set,
        "selected": candidate.selected,
    }


# -- the payload readers -----------------------------------------------------


def _text(payload: dict[str, Any], key: str) -> str:
    return _strict_text(payload.get(key), key)


def _strict_text(value: object, key: str) -> str:
    """The string-or-refusal rule, shared by the scalar keys and by every
    element of the list keys (judgement 3): a value is a string, or it is
    refused — never spelled with ``str()``."""

    if not isinstance(value, str):
        raise ValueError(f"factor_trace.{key} is not a string: {value!r}")
    return value


def _text_tuple(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    """``reasons`` / ``merged_from`` / ``dominated_by``, element by element
    through the same strict rule as the scalars. The washed spelling this
    replaces (``tuple(str(item) …)``) answered ``[1, null]`` with
    ``("1", "None")`` — strings the row never carried (judgement 3)."""

    return tuple(_strict_text(item, key) for item in _sequence(payload, key))


def _sequence(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"factor_trace.{key} is not a list: {value!r}")
    return value


def _mapping(payload: object, key: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"factor_trace.{key} is not an object: {payload!r}")
    return payload


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"factor_trace.{key} is not a string or null: {value!r}")
    return value


def _number(payload: dict[str, Any], key: str) -> float | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"factor_trace.{key} is not a number or null: {value!r}")
    return float(value)


def _required_number(payload: dict[str, Any], key: str) -> float:
    value = _number(payload, key)
    if value is None:
        raise ValueError(f"factor_trace.{key} is null; a reading carries one")
    return value


def _integer(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"factor_trace.{key} is not an integer: {value!r}")
    return value


def _flag(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"factor_trace.{key} is not a boolean: {value!r}")
    return value


def _flag_or_absent(payload: dict[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"factor_trace.{key} is not a boolean or null: {value!r}")
    return value


def _reading_from_payload(payload: object) -> FactorReadingDocument:
    mapping = _mapping(payload, "benefit/cost[]")
    return FactorReadingDocument(
        factor=_text(mapping, "factor"),
        value=_required_number(mapping, "value"),
        source=_text(mapping, "source"),
        authority=_optional_str(mapping, "authority"),
    )


def _gap_from_payload(payload: object) -> FactorGapDocument:
    mapping = _mapping(payload, "gaps[]")
    return FactorGapDocument(
        factor=_text(mapping, "factor"),
        authority=_text(mapping, "authority"),
        reason=_text(mapping, "reason"),
    )


def _candidate_from_payload(payload: object) -> CandidateTraceDocument:
    mapping = _mapping(payload, "candidates[]")
    return CandidateTraceDocument(
        candidate_id=_text(mapping, "candidate_id"),
        canonical_key=_text(mapping, "canonical_key"),
        merged_from=_text_tuple(mapping, "merged_from"),
        initiative_class=_text(mapping, "initiative_class"),
        request_priority=_integer(mapping, "request_priority"),
        coverage_service_state=_text(mapping, "coverage_service_state"),
        benefit=tuple(
            _reading_from_payload(item)
            for item in _sequence(mapping, "benefit")
        ),
        cost=tuple(
            _reading_from_payload(item) for item in _sequence(mapping, "cost")
        ),
        gaps=tuple(
            _gap_from_payload(item) for item in _sequence(mapping, "gaps")
        ),
        excluded=_optional_str(mapping, "excluded"),
        benefit_score=_number(mapping, "benefit_score"),
        cost_score=_number(mapping, "cost_score"),
        coverage_service_bonus=_number(mapping, "coverage_service_bonus"),
        utility=_number(mapping, "utility"),
        activation_path=_optional_str(mapping, "activation_path"),
        activation_threshold=_number(mapping, "activation_threshold"),
        activated=_flag_or_absent(mapping, "activated"),
        dominated_by=_text_tuple(mapping, "dominated_by"),
        in_tie_set=_flag(mapping, "in_tie_set"),
        selected=_flag(mapping, "selected"),
    )
