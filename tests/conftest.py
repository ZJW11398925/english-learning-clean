"""Shared test fixtures / paths."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "elc"
DOCS_ROOT = REPO_ROOT / "docs"
BASELINES = REPO_ROOT / "behavioral_baselines"

# Phase 0 packages: the domains from docs/IMPLEMENTATION_PLAN.md §2 plus
# the User Configuration/Profile bounded context (docs/DOMAIN_MODEL.md
# §5.1) and the World/Lore bounded context (docs/DOMAIN_MODEL.md §2
# Authority Matrix / §1 domain map). platform is the shared kernel, not a
# domain.
DOMAIN_PACKAGES = (
    "conversation",
    "persona",
    "relationship",
    "learning",
    "curriculum",
    "scheduler",
    "planner",
    "teaching",
    "runtime",
    "content",
    "user_config",
    "world_lore",
)
