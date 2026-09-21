"""BF-05 sensitive-memory gate for Relationship Memory (P4-1).

Authority: behavioral_baselines/security/security_privacy_policy_v1.json
(BF-05, frozen read-only baseline) ``sensitive_memory_policy`` — word for
word:

    transcript_storage                ALLOWED_AS_USER_AUTHORED_CONTENT
    automatic_profile_promotion       DENY
    automatic_relationship_promotion  DENY
    explicit_user_persistence         ALLOW_AFTER_VALIDATION
    system_inference                  DENY_FOR_HIGH_SENSITIVITY

and SECURITY_PRIVACY_DELETION_CONTRACT_v1.0.md §8 (高敏感 Relationship
Memory):

    transcript storage ≠ long-term relationship-memory permission
    自动 promotion: DENY
    只有明确 persistence permission 后才允许保存

with DOMAIN_MODEL.md §18.1 ("高敏感 Profile/Relationship persistence 需要
显式用户许可；模型不得把推断的高敏感属性直接提交为长期事实").

Decision order (fixed, documented, tested):

1. ``PERSONAL`` — the BF-05 class whose examples include "relationship
   memories" — is the ordinary §5 write flow; no extra permission is
   required, and the row records ``VALIDATED_DOMAIN_WRITE`` (BF-05
   ``trust_classes.TRUSTED_AUTHORITY``: "domain-validated canonical write").

2. ``HIGH_SENSITIVITY`` **inferred** (provenance SYSTEM_INFERRED_FACT or
   PERSONA_IMPRESSION — anything that is not the user's own statement) →
   ``DENY``. system_inference = DENY_FOR_HIGH_SENSITIVITY: an inferred
   high-sensitivity attribute is never promoted to a durable relationship
   memory, whatever authorization the proposal claims. This is the arm
   DOMAIN_MODEL §18.1 names ("模型不得把推断的高敏感属性直接提交为长期事实").

3. ``HIGH_SENSITIVITY`` + USER_STATED_FACT + no ``USER_EXPLICIT_CONSENT`` →
   ``DENY`` (automatic_relationship_promotion = DENY). The user's own
   sentence is in the transcript (transcript_storage =
   ALLOWED_AS_USER_AUTHORED_CONTENT) but nothing promotes it into long-term
   memory on its own.

4. ``HIGH_SENSITIVITY`` + USER_STATED_FACT + ``USER_EXPLICIT_CONSENT`` →
   ``ALLOW_AFTER_VALIDATION`` (explicit_user_persistence). Migration 0009's
   cross-column CHECK — HIGH_SENSITIVITY ⇒ USER_EXPLICIT_CONSENT — is the
   durable half of this same rule, so a denied row is unwritable even if it
   somehow reached the store.

The decision words are BF-05's own (``ALLOW_AFTER_VALIDATION`` / ``DENY``);
the reason words below are this implementation's trace vocabulary. The gate
decides *persistence* and nothing else: a stored HIGH_SENSITIVITY row still
obeys disclosure policy (BF-05 §8: 保存之后仍遵守 Profile/Persona disclosure
policy — which persona and which provider action may see it is P4-3's
disclosure face, not this gate).

Where the consent comes from: in P4-1 the proposal face is the write-path
input, and the explicit-persistence flag travels on it. A typed user consent
command / UI is not in this slice (no user-facing memorial face exists
before P4-3), so the flag is a declared fact of the trusted write path —
what the gate refuses to accept is consent claimed for an *inferred*
attribute, and any high-sensitivity row without the flag.

Pure module: no storage, no clock, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass

from elc.relationship.types import (
    MemoryProvenance,
    MemorySensitivityClass,
    PersistenceAuthorization,
)

__all__ = [
    "ALLOW_AFTER_VALIDATION",
    "DENY",
    "DENY_REASONS",
    "PersistenceDecision",
    "REASON_EXPLICIT_USER_PERSISTENCE",
    "REASON_HIGH_SENSITIVITY_SYSTEM_INFERENCE",
    "REASON_HIGH_SENSITIVITY_WITHOUT_CONSENT",
    "REASON_ORDINARY_PERSONAL_WRITE",
    "decide_persistence",
]

#: BF-05 ``sensitive_memory_policy.explicit_user_persistence``, verbatim.
ALLOW_AFTER_VALIDATION = "ALLOW_AFTER_VALIDATION"

#: BF-05 ``sensitive_memory_policy.automatic_relationship_promotion``,
#: verbatim.
DENY = "DENY"

#: Trace words (implementation-defined): which rule produced the decision.
REASON_ORDINARY_PERSONAL_WRITE = "ORDINARY_PERSONAL_WRITE"
REASON_HIGH_SENSITIVITY_SYSTEM_INFERENCE = "HIGH_SENSITIVITY_SYSTEM_INFERENCE"
REASON_HIGH_SENSITIVITY_WITHOUT_CONSENT = (
    "HIGH_SENSITIVITY_WITHOUT_EXPLICIT_CONSENT"
)
REASON_EXPLICIT_USER_PERSISTENCE = "EXPLICIT_USER_PERSISTENCE"

#: The two reasons that deny a write (canonical word ``DENY``).
DENY_REASONS = (
    REASON_HIGH_SENSITIVITY_SYSTEM_INFERENCE,
    REASON_HIGH_SENSITIVITY_WITHOUT_CONSENT,
)


@dataclass(frozen=True)
class PersistenceDecision:
    """One gate decision: the BF-05 word, the rule that produced it, and the
    human-readable detail a refusal carries back to the caller."""

    allowed: bool
    decision: str
    reason: str
    detail: str


def decide_persistence(
    *,
    sensitivity_class: MemorySensitivityClass,
    persistence_authorization: PersistenceAuthorization,
    provenance: MemoryProvenance,
) -> PersistenceDecision:
    """The BF-05 gate: may this memory be persisted? (see module docstring)"""

    if sensitivity_class is MemorySensitivityClass.PERSONAL:
        return PersistenceDecision(
            allowed=True,
            decision=ALLOW_AFTER_VALIDATION,
            reason=REASON_ORDINARY_PERSONAL_WRITE,
            detail=(
                "PERSONAL is the BF-05 class whose examples include"
                " 'relationship memories'; the ordinary §5 write flow applies"
            ),
        )
    if provenance is not MemoryProvenance.USER_STATED_FACT:
        return PersistenceDecision(
            allowed=False,
            decision=DENY,
            reason=REASON_HIGH_SENSITIVITY_SYSTEM_INFERENCE,
            detail=(
                "high-sensitivity content inferred by a model never becomes a"
                f" long-term relationship memory (provenance="
                f"{provenance.value}; BF-05 sensitive_memory_policy"
                " system_inference = DENY_FOR_HIGH_SENSITIVITY; DOMAIN_MODEL"
                " §18.1 模型不得把推断的高敏感属性直接提交为长期事实). The"
                " transcript keeps what the user said"
                " (transcript_storage = ALLOWED_AS_USER_AUTHORED_CONTENT)"
            ),
        )
    if persistence_authorization is not (
        PersistenceAuthorization.USER_EXPLICIT_CONSENT
    ):
        return PersistenceDecision(
            allowed=False,
            decision=DENY,
            reason=REASON_HIGH_SENSITIVITY_WITHOUT_CONSENT,
            detail=(
                "high-sensitivity content is not promoted automatically"
                " (BF-05 automatic_relationship_promotion = DENY /"
                " SECURITY_PRIVACY_DELETION_CONTRACT §8); it needs explicit"
                " persistence permission"
                " (USER_EXPLICIT_CONSENT) before it may be saved"
            ),
        )
    return PersistenceDecision(
        allowed=True,
        decision=ALLOW_AFTER_VALIDATION,
        reason=REASON_EXPLICIT_USER_PERSISTENCE,
        detail=(
            "explicit persistence permission on a user-stated high-"
            "sensitivity fact (BF-05 explicit_user_persistence ="
            " ALLOW_AFTER_VALIDATION); validation and dedupe still apply,"
            " and the stored row still obeys disclosure policy"
        ),
    )
