"""Operation-local, endpoint-bounded evidence access for the view loaders.

An `EvidenceReader` wraps the Store for one evaluation operation. Every query is bounded at or
before the selected endpoint in SQL; full-snapshot hydrations and the catalog are memoised for the
operation only (never persisted) and counted so coverage reports what was really read. Pure view
functions never see the reader: loaders turn what they read into immutable evidence.
"""

from __future__ import annotations

from typing import Any, Collection, Iterator

from ..snapshot import Snapshot
from ..store import Store
from .models import EvaluationContext, SampleRef


class EvidenceReader:
    def __init__(self, store: Store, context: EvaluationContext) -> None:
        self.store = store
        self.context = context
        self.endpoint = context.endpoint
        self._snapshots: dict[int, Snapshot | None] = {context.endpoint: context.snapshot}
        self._catalog: tuple[Snapshot | None] | None = None
        self._clocks: dict[int, Any] = {context.endpoint: context.clock}
        self._hydrated: set[int] = set()

    # ---- full snapshots (bounded hydration) -------------------------------------------
    def _bounded(self, tick: int) -> None:
        if tick > self.endpoint:
            raise ValueError(f"tick {tick} is after the selected endpoint {self.endpoint}")

    def hydrate(self, tick: int) -> Snapshot | None:
        """The full snapshot stored at exactly this tick (at or before the endpoint)."""
        self._bounded(tick)
        if tick not in self._snapshots:
            self._snapshots[tick] = self.store.hydrate(tick)
        if self._snapshots[tick] is not None and tick != self.endpoint:
            self._hydrated.add(tick)
        return self._snapshots[tick]

    def at_or_before(self, tick: int) -> Snapshot | None:
        """The newest stored snapshot at or before `tick` (never after the endpoint)."""
        self._bounded(tick)
        snap = self._snapshots.get(tick)
        if snap is None:
            snap = self.store.snapshot_at_or_before(tick)
            if snap is not None:
                snap = self._snapshots.setdefault(snap.game_time, snap)
                if snap.game_time != self.endpoint:
                    self._hydrated.add(snap.game_time)
        return snap

    def recent(self, limit: int) -> list[Snapshot]:
        """At most `limit` newest full snapshots at or before the endpoint, oldest first."""
        out = []
        for snap in self.store.recent_snapshots(limit, self.endpoint):
            snap = self._snapshots.setdefault(snap.game_time, snap)
            if snap.game_time != self.endpoint:
                self._hydrated.add(snap.game_time)
            out.append(snap)
        return out

    def catalog(self) -> Snapshot | None:
        """The newest stored catalog snapshot at or before the endpoint, hydrated once per operation."""
        if self._catalog is None:
            snap = self.store.latest_with_catalog(self.endpoint)
            if snap is not None:
                snap = self._snapshots.setdefault(snap.game_time, snap)
                if snap.game_time != self.endpoint:
                    self._hydrated.add(snap.game_time)
            self._catalog = (snap,)
        return self._catalog[0]

    def clock_at(self, snapshot: Snapshot):
        """Calendar evidence bounded at that sample's own tick."""
        if snapshot.game_time not in self._clocks:
            self._bounded(snapshot.game_time)
            self._clocks[snapshot.game_time] = self.store.time_context(snapshot)
        return self._clocks[snapshot.game_time]

    # ---- compact projections (streamed in batches) ---------------------------------------
    def count_samples(self) -> int:
        return self.store.count_samples(self.endpoint)

    def sample_index(self) -> Iterator[tuple[int, str, dict[str, Any] | None]]:
        return self.store.iter_sample_index(self.endpoint)

    def company_points(self) -> Iterator[dict[str, Any]]:
        return self.store.iter_company_points(self.endpoint)

    def line_points(self, line_id: int | None = None) -> Iterator[dict[str, Any]]:
        return self.store.iter_line_points(self.endpoint, line_id)

    def projection(self, keys: tuple[str, ...], ticks: Collection[int] | None = None):
        return self.store.iter_projection(self.endpoint, keys, ticks)

    # ---- accounting -------------------------------------------------------------------
    @property
    def hydrated(self) -> int:
        """Full snapshots loaded besides the already-selected endpoint."""
        return len(self._hydrated)

    def ref(self, snapshot: Snapshot) -> SampleRef:
        return SampleRef(snapshot.game_time, snapshot.date_label)
