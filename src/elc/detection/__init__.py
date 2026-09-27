"""elc.detection — the execution half of ``EXECUTABLY_VERIFIED`` (D-2).

Skeleton state in V1: the registry ships empty (no matcher is registered);
the build step (elc.content.build) is the only EV grantor and it hands in
a registry explicitly. See the package modules for the contract.
"""

from elc.detection.registry import GLOBAL_REGISTRY, DetectorEntry, DetectorRegistry
from elc.detection.runner import run_fixture, run_fixtures
from elc.detection.types import (
    DetectionFixture,
    DetectionMatch,
    FixtureOutcome,
    Matcher,
    VerificationOutcome,
)

__all__ = [
    "GLOBAL_REGISTRY",
    "DetectionFixture",
    "DetectionMatch",
    "DetectorEntry",
    "DetectorRegistry",
    "FixtureOutcome",
    "Matcher",
    "VerificationOutcome",
    "run_fixture",
    "run_fixtures",
]
