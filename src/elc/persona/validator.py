"""Response Validator — deterministic minimum rule set (Phase 1 P1B).

docs/RUNTIME_ARCHITECTURE.md §12 position:
    Persona Runtime output → Response Validator → PreDeliveryGuard → Delivery
docs/STATE_MACHINES.md §15: output vocabulary ACCEPT / RETRY / FALLBACK /
ABORT_DELIVERY, "Retry bounded"; the validator writes no Learning /
Relationship / Teaching truth and never patches teaching text itself.

P1B minimum deterministic rules (IMPLEMENTATION_PLAN §3 "Response Validator
minimum deterministic rules"):
1. no-output            → RETRY   (empty provider output — §12 provider
                                    no-output handling; retry stays at the
                                    action level, bounded by the caller)
2. max_length exceeded  → RETRY   (GenerationContract compliance, §12)
3. forbidden claim hit  → ABORT_DELIVERY (§21 forbidden_claims — no false
                                    mastery claim is ever delivered)
4. otherwise            → ACCEPT

The validator is a pure function of (output, contract): same inputs always
yield the same decision and reason codes — no randomness, no I/O.
"""

from __future__ import annotations

from elc.persona.types import (
    GenerationContract,
    ProviderOutput,
    ValidatorDecision,
    ValidatorResult,
)
from elc.platform.types import ActionId

#: Bumped when the rule set changes; rides every ValidatorResult (§21.1).
VALIDATOR_VERSION = "response-validator-v1-p1b"

#: §21.1 reason codes (deterministic vocabulary of this validator version).
REASON_NO_OUTPUT = "PROVIDER_NO_OUTPUT"
REASON_LENGTH_EXCEEDED = "MAX_LENGTH_EXCEEDED"
REASON_FORBIDDEN_CLAIM = "FORBIDDEN_CLAIM"


def _new_id(action_id: ActionId, attempt_no: int) -> str:
    return f"vr-{action_id}-{attempt_no}"


class ResponseValidator:
    """Deterministic minimum validator (STATE_MACHINES §15; DOMAIN_MODEL §18
    proposal-only — results ride the runtime trace, own no domain writes)."""

    def validate(
        self,
        action_id: ActionId,
        attempt_no: int,
        output: ProviderOutput,
        contract: GenerationContract | None,
        created_at: str | None = None,
    ) -> ValidatorResult:
        decision, reason_codes = self.decide(output, contract)
        return ValidatorResult(
            validator_result_id=_new_id(action_id, attempt_no),
            action_id=action_id,
            attempt_no=attempt_no,
            decision=decision,
            reason_codes=reason_codes,
            validator_version=VALIDATOR_VERSION,
            created_at=created_at,
        )

    def decide(
        self, output: ProviderOutput, contract: GenerationContract | None
    ) -> tuple[ValidatorDecision, tuple[str, ...]]:
        """Pure decision core: (decision, reason codes)."""
        if not output.has_output():
            return ValidatorDecision.RETRY, (REASON_NO_OUTPUT,)
        text = output.text or ""
        if contract is not None and contract.max_length is not None:
            if len(text) > contract.max_length:
                return ValidatorDecision.RETRY, (REASON_LENGTH_EXCEEDED,)
        if contract is not None:
            for claim in contract.forbidden_claims:
                if claim and claim in text:
                    return ValidatorDecision.ABORT_DELIVERY, (
                        REASON_FORBIDDEN_CLAIM,
                    )
        return ValidatorDecision.ACCEPT, ()
