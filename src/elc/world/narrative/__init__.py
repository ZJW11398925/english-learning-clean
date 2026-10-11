"""The Narrative V3 foundations (V3-1, DEC-OPI-bab4da9f…11/…16) — the
sub-package of the World bounded context that carries the new
paradigm's durable foundations: the record shapes and lifecycle
vocabularies (:mod:`elc.world.narrative.types`) and their SQLite face
(:mod:`elc.world.narrative.store`, migration 0029's four tables).

The foundations only: chapter/scene lifecycle words, the Plan/Canon
boundary as typed records and physical tables, the story_tick
primitives next door (:mod:`elc.world.time`). The commit transactions
(NCP-1..NCP-4), the POV Writer, the User Gate / Action Resolver and the
planning engines are the later cuts' — nothing here writes canon.
"""

from elc.world.narrative.store import SqliteNarrativeStore
from elc.world.narrative.types import (
    CanonProgressRecord,
    ChapterStatus,
    PlanFaceRecord,
    PlanRevisionStatus,
    SceneStatus,
    WorldChapterPlanRecord,
    WorldChapterRecord,
    WorldSceneDossierRecord,
    WorldSceneRecord,
    decode_scenes,
    encode_scenes,
)

__all__ = [
    "SqliteNarrativeStore",
    "CanonProgressRecord",
    "PlanFaceRecord",
    "ChapterStatus",
    "SceneStatus",
    "PlanRevisionStatus",
    "WorldChapterRecord",
    "WorldChapterPlanRecord",
    "WorldSceneRecord",
    "WorldSceneDossierRecord",
    "encode_scenes",
    "decode_scenes",
]
