"""Evidence selection for the bottlenecks view: the newest stored snapshots at or before the endpoint.

At most `LOAD_LIMIT` full snapshots are hydrated through the reader (endpoint-bounded in SQL), then
near-simultaneous samples are merged exactly as the report always did. Nothing after the endpoint is
ever read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..snapshot import Snapshot
from .models import EvaluationContext
from .reader import EvidenceReader

LOAD_LIMIT = 240       # newest full snapshots read from the store
MERGE_FRACTION = 48    # samples closer than a 48th of a game year are one observation


@dataclass(frozen=True)
class BottlenecksEvidence:
    history: tuple[Snapshot, ...]            # merged samples, oldest first; the last one is the endpoint
    eligible: int                            # stored samples at or before the endpoint
    read: int                                # full snapshots hydrated before merging
    hydrated: int                            # hydrations besides the already-selected endpoint
    known_depots: Mapping[Any, str]          # depot names seen anywhere in the read history


def dedupe(snaps: list[Snapshot]) -> list[Snapshot]:
    """Collapse near-simultaneous samples (e.g. a refresh request just after an interval sample)."""
    out: list[Snapshot] = []
    for s in sorted(snaps, key=lambda x: x.game_time):
        if out and s.year_duration and (s.game_time - out[-1].game_time) < s.year_duration / MERGE_FRACTION:
            out[-1] = s
        else:
            out.append(s)
    return out


def load(reader: EvidenceReader, context: EvaluationContext) -> BottlenecksEvidence:
    snaps = reader.recent(LOAD_LIMIT) or [context.snapshot]
    history = dedupe(snaps)
    depots = {d["id"]: d["name"] for s in history for d in s.depots if d.get("name")}
    return BottlenecksEvidence(tuple(history), reader.count_samples(), len(snaps), reader.hydrated, depots)
