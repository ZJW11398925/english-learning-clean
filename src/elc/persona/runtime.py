"""PersonaRuntime — the generation pipeline orchestrator body (Phase 1 P1B).

docs/RUNTIME_ARCHITECTURE.md §4 steps 11-13 (Persona Runtime builds final
prompt → Provider generation → Response Validator) realized on the
docs/STATE_MACHINES.md §14 GenerationActionStatus state machine:

    PREPARED → REQUESTED → GENERATING → VALIDATING
      VALIDATING → READY_TO_DELIVER (validator ACCEPT; BUFFERED_VALIDATED)
      VALIDATING → REQUESTED        (validator RETRY, bounded — §15)
      VALIDATING → TERMINAL         (FALLBACK / ABORT_DELIVERY — §15)
      GENERATING → REQUESTED        (provider failure — action-level retry)
      READY_TO_DELIVER → DELIVERING → TERMINAL (buffered delivery completes)
      <nonterminal> → TERMINAL      (bounded retries exhausted → failed)

Action-level retry only (RUNTIME §16 "Never retry whole Turn"; R-INV-007):
every retry appends one ProviderAttempt under the SAME stable action_id;
UserTurn / TurnRecord are never rebuilt. One action has many attempts but
at most one canonical accepted result (§14; RUNTIME §16).

BUFFERED_VALIDATED (RUNTIME §13): provider completes → full validation →
delivery. The validated output is buffered (READY_TO_DELIVER + the returned
:class:`BufferedReply`) before the orchestrator hands it to the conversation
store for canonicalization; canonicalization itself is exactly-once
(RUNTIME §16 "Internal canonical state").

Late results: once an action is TERMINAL (or its owner_epoch was fenced by
a restart), no result of it may produce a canonical side effect
(STATE_MACHINES §14; enforced durably by the store's TERMINAL-immutability
and epoch-fenced CAS).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from elc.persona.commands import GenerationActionStore, PromptCompiler
from elc.persona.provider import (
    PersonaProvider,
    request_hash,
    result_hash,
)
from elc.persona.types import (
    CompiledPrompt,
    GenerationContract,
    PromptCompilationRequest,
    ProviderOutput,
    ValidatorDecision,
    ValidatorResult,
)
from elc.persona.validator import ResponseValidator
from elc.platform.types import (
    ActionId,
    DecisionCycleId,
    DomainError,
    DomainErrorCode,
    Err,
    Ok,
    ProviderAttemptId,
    Result,
    TurnId,
)
from elc.runtime.types import (
    GenerationActionIntentRecord,
    GenerationActionStatus,
    GenerationActionType,
    ProviderAttemptRecord,
)

__all__ = [
    "BufferedReply",
    "GenerationOutcome",
    "PersonaRuntime",
    "DEFAULT_MAX_PROVIDER_ATTEMPTS",
    "action_intent_for_turn",
]

#: Retry bounded (STATE_MACHINES §15) — default provider-attempt budget per
#: action; deterministic, no backoff in the fake Phase 1 provider.
DEFAULT_MAX_PROVIDER_ATTEMPTS = 3


@dataclass(frozen=True)
class BufferedReply:
    """A fully validated reply waiting for delivery (RUNTIME §13
    BUFFERED_VALIDATED: provider complete → full validation → delivery).

    The buffer is the queue the validated output enters first; the
    orchestrator then drives it through the conversation store's
    canonicalization (exactly-once, RUNTIME §16)."""

    action_id: ActionId
    assistant_turn_id: str
    attempt_no: int
    validator_result: ValidatorResult
    text: str


@dataclass(frozen=True)
class GenerationOutcome:
    """Terminal view of one run_action pass."""

    action_id: ActionId
    final_status: GenerationActionStatus
    attempts_used: int
    buffered_reply: BufferedReply | None
    failure_reason: str | None
    validator_results: tuple[ValidatorResult, ...]


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _new_attempt_id() -> ProviderAttemptId:
    return ProviderAttemptId(f"pa-{uuid.uuid4().hex}")


class PersonaRuntime:
    """Persona Runtime — sole owner of the final prompt and the generation
    action state machine (DOMAIN_MODEL §4; SM §14)."""

    def __init__(
        self,
        actions: GenerationActionStore,
        provider: PersonaProvider,
        compiler: PromptCompiler | None = None,
        validator: ResponseValidator | None = None,
        max_provider_attempts: int = DEFAULT_MAX_PROVIDER_ATTEMPTS,
    ) -> None:
        self._actions = actions
        self._provider = provider
        self._compiler = compiler if compiler is not None else PromptCompiler()
        self._validator = validator if validator is not None else ResponseValidator()
        self._max_attempts = max_provider_attempts

    # -- generation pipeline (RUNTIME §4 steps 11-13) -----------------------

    def run_action(
        self,
        intent: GenerationActionIntentRecord,
        request: PromptCompilationRequest,
        contract: GenerationContract | None = None,
    ) -> Result[GenerationOutcome]:
        """Drive one generation action from PREPARED to a buffered reply
        (READY_TO_DELIVER) or a failed TERMINAL, with bounded action-level
        retry (R-INV-007)."""

        prompt_result = self._compiler.compile(request)
        if isinstance(prompt_result, Err):
            return prompt_result
        prompt = prompt_result.value

        create_result = self._actions.create_action(intent)
        if isinstance(create_result, Err):
            return create_result

        # §14: PREPARED → REQUESTED. Recovery re-dispatch (same stable
        # action_id, RUNTIME §23 "继续同 action_id") may already have the
        # action at REQUESTED — that replay is tolerated.
        ensure = self._ensure_requested(intent)
        if isinstance(ensure, Err):
            return ensure
        current: GenerationActionStatus = ensure.value

        validator_results: list[ValidatorResult] = []
        # Durable attempt sequence: a re-dispatched action continues its
        # ProviderAttempt numbering from the durable attempt_count (§20
        # UNIQUE(action_id, attempt_no) never collides on recovery).
        attempts_used = intent.attempt_count
        budget_end = intent.attempt_count + self._max_attempts
        failure_reason: str | None = None

        while attempts_used < budget_end:
            if current != GenerationActionStatus.GENERATING:
                stepped = self._advance(
                    intent.action_id, current, GenerationActionStatus.GENERATING
                )
                if isinstance(stepped, Err):
                    return stepped
                current = stepped.value.status
            attempts_used += 1
            output = self._call_provider(prompt)

            if not output.has_output():
                recorded = self._record_attempt(
                    intent.action_id,
                    attempts_used,
                    prompt,
                    failed=True,
                )
                if isinstance(recorded, Err):
                    return recorded
                failure_reason = (
                    output.error
                    if output.error is not None
                    else "provider no-output"
                )
                if attempts_used >= budget_end:
                    break
                back = self._advance(
                    intent.action_id,
                    GenerationActionStatus.GENERATING,
                    GenerationActionStatus.REQUESTED,
                )
                if isinstance(back, Err):
                    return back
                current = back.value.status
                continue

            recorded = self._record_attempt(
                intent.action_id,
                attempts_used,
                prompt,
                failed=False,
                output_text=output.text or "",
            )
            if isinstance(recorded, Err):
                return recorded
            stepped = self._advance(
                intent.action_id,
                GenerationActionStatus.GENERATING,
                GenerationActionStatus.VALIDATING,
            )
            if isinstance(stepped, Err):
                return stepped
            current = stepped.value.status

            validator_result = self._validator.validate(
                intent.action_id,
                attempts_used,
                output,
                contract if contract is not None else request.generation_contract,
                created_at=_now(),
            )
            validator_results.append(validator_result)

            if validator_result.decision == ValidatorDecision.ACCEPT:
                ready = self._advance(
                    intent.action_id,
                    GenerationActionStatus.VALIDATING,
                    GenerationActionStatus.READY_TO_DELIVER,
                )
                if isinstance(ready, Err):
                    return ready
                return Ok(
                    GenerationOutcome(
                        action_id=intent.action_id,
                        final_status=GenerationActionStatus.READY_TO_DELIVER,
                        attempts_used=attempts_used,
                        buffered_reply=BufferedReply(
                            action_id=intent.action_id,
                            assistant_turn_id=intent.assistant_turn_id,
                            attempt_no=attempts_used,
                            validator_result=validator_result,
                            text=output.text or "",
                        ),
                        failure_reason=None,
                        validator_results=tuple(validator_results),
                    )
                )

            if validator_result.decision == ValidatorDecision.RETRY:
                if attempts_used >= budget_end:
                    failure_reason = "validator retry budget exhausted"
                    break
                back = self._advance(
                    intent.action_id,
                    GenerationActionStatus.VALIDATING,
                    GenerationActionStatus.REQUESTED,
                )
                if isinstance(back, Err):
                    return back
                current = back.value.status
                continue

            # FALLBACK / ABORT_DELIVERY — Phase 1 has no fallback text
            # source (no teaching pipeline yet), so both end the action
            # undelivered; recorded as a Phase 2+ hook.
            failure_reason = f"validator decision {validator_result.decision.value}"
            break

        terminal = self._advance(
            intent.action_id, current, GenerationActionStatus.TERMINAL
        )
        if isinstance(terminal, Err):
            return terminal
        return Ok(
            GenerationOutcome(
                action_id=intent.action_id,
                final_status=GenerationActionStatus.TERMINAL,
                attempts_used=attempts_used,
                buffered_reply=None,
                failure_reason=failure_reason or "generation failed",
                validator_results=tuple(validator_results),
            )
        )

    # -- buffered delivery legs (RUNTIME §13 BUFFERED_VALIDATED) ------------

    def begin_delivery(self, action_id: ActionId) -> Result[GenerationActionStatus]:
        """READY_TO_DELIVER → DELIVERING (the orchestrator canonicalizes
        between this and :meth:`complete_delivery`)."""

        stepped = self._actions.transition_action(
            action_id,
            GenerationActionStatus.READY_TO_DELIVER,
            GenerationActionStatus.DELIVERING,
        )
        if isinstance(stepped, Err):
            return stepped
        return Ok(stepped.value.status)

    def complete_delivery(
        self, action_id: ActionId
    ) -> Result[GenerationActionStatus]:
        """DELIVERING → TERMINAL after successful canonicalization."""

        stepped = self._actions.transition_action(
            action_id,
            GenerationActionStatus.DELIVERING,
            GenerationActionStatus.TERMINAL,
        )
        if isinstance(stepped, Err):
            return stepped
        return Ok(stepped.value.status)

    def terminalize_failure(
        self, action_id: ActionId, from_status: GenerationActionStatus
    ) -> Result[GenerationActionStatus]:
        """Force a nonterminal action to TERMINAL undelivered (late callback
        discard / supervisor abort). Undelivered content never reaches the
        transcript (DOMAIN_MODEL §3 key rule)."""

        stepped = self._actions.transition_action(
            action_id, from_status, GenerationActionStatus.TERMINAL
        )
        if isinstance(stepped, Err):
            return stepped
        return Ok(stepped.value.status)

    # -- internals -----------------------------------------------------------

    def _call_provider(self, prompt: CompiledPrompt) -> ProviderOutput:
        """One provider call — strictly outside any DB transaction (the
        store calls happen before/after; R-INV-004). Provider exceptions
        surface as deterministic failure values."""

        try:
            return self._provider.call(prompt)
        except Exception as exc:  # noqa: BLE001 — provider boundary
            return ProviderOutput(text=None, error=f"provider raised: {exc}")

    def _ensure_requested(
        self, intent: GenerationActionIntentRecord
    ) -> Result[GenerationActionStatus]:
        """PREPARED → REQUESTED, tolerating an already-REQUESTED action
        (recovery re-dispatch under the same stable action_id, §23)."""

        fetched = self._actions.get_action(intent.action_id)
        if isinstance(fetched, Err):
            return fetched
        action = fetched.value
        if action is None:
            return Err(
                DomainError(
                    code=DomainErrorCode.NOT_FOUND,
                    message=f"generation action not found: {intent.action_id}",
                )
            )
        if action.status == GenerationActionStatus.PREPARED:
            stepped = self._actions.transition_action(
                intent.action_id,
                GenerationActionStatus.PREPARED,
                GenerationActionStatus.REQUESTED,
            )
            if isinstance(stepped, Err):
                return stepped
            return Ok(stepped.value.status)
        if action.status == GenerationActionStatus.REQUESTED:
            return Ok(GenerationActionStatus.REQUESTED)
        return Err(
            DomainError(
                code=DomainErrorCode.CONFLICT,
                message=(
                    "action re-dispatch from status"
                    f" {action.status.value} is outside the Phase 1 pipeline"
                ),
            )
        )

    def _advance(
        self,
        action_id: ActionId,
        expected: GenerationActionStatus,
        new: GenerationActionStatus,
    ) -> Result[GenerationActionIntentRecord]:
        stepped = self._actions.transition_action(action_id, expected, new)
        if isinstance(stepped, Err):
            return stepped
        return Ok(stepped.value)

    def _record_attempt(
        self,
        action_id: ActionId,
        attempt_no: int,
        prompt: CompiledPrompt,
        *,
        failed: bool,
        output_text: str = "",
    ) -> Result[ProviderAttemptRecord]:
        record = ProviderAttemptRecord(
            provider_attempt_id=_new_attempt_id(),
            action_id=action_id,
            attempt_no=attempt_no,
            request_hash=request_hash(prompt),
            status="FAILED" if failed else "SUCCEEDED",
            provider_request_id=None,
            result_hash=None if failed else result_hash(output_text),
            created_at=_now(),
            terminal_at=_now(),
        )
        return self._actions.record_attempt(record)


def action_intent_for_turn(
    *,
    turn_id: TurnId,
    action_type: GenerationActionType,
    generation_contract_id: str,
    decision_cycle_id: str | None = None,
) -> GenerationActionIntentRecord:
    """Build the PREPARED intent for a turn's generation action, minting
    the stable action_id and its pre-allocated assistant_turn_id together
    (DATA_MODEL §1.2 stable opaque ids)."""

    suffix = uuid.uuid4().hex
    return GenerationActionIntentRecord(
        action_id=ActionId(f"ga-{suffix}"),
        turn_id=turn_id,
        decision_cycle_id=(
            DecisionCycleId(decision_cycle_id) if decision_cycle_id else None
        ),
        moment_id=None,
        assistant_turn_id=f"aturn-{suffix}",
        action_type=action_type,
        generation_contract_id=generation_contract_id,
        status=GenerationActionStatus.PREPARED,
        attempt_count=0,
        created_at=None,
        owner_epoch=None,
    )
