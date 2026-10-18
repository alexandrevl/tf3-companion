"""A methodology applied to one snapshot: the object report builders and the service share."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .. import analysis
from ..snapshot import Snapshot
from ..store import Store
from .engine import Verdicts, _evaluate_prepared
from .loader import load_default
from .model import Methodology

PROBE_SNAPSHOTS = 12


@dataclass(frozen=True, eq=False)
class Lens:
    methodology: Methodology
    origin: str                     # request | binding | default | file
    verdicts: Verdicts
    snapshot: Snapshot
    report_context: Any
    clock: Any

    @property
    def thresholds(self) -> analysis.Thresholds:
        return self.report_context.thresholds

    def provenance(self) -> dict[str, Any]:
        return {**self.methodology.provenance(), "origin": self.origin, "parameters": self.verdicts.parameters,
                "parameterOverrides": self.verdicts.overrides, "selection": dict(self.methodology.selection),
                "timeBasis": self.clock.time_basis, **self.report_context.provenance()}

    def header(self) -> list[tuple[str, str]]:
        """Report header entries naming the methodology, its parameters and the coverage counts."""
        m, v = self.methodology, self.verdicts
        params = ", ".join(f"{k}={val}" for k, val in sorted(v.parameters.items())) or "none"
        counts = v.counts()
        return [
            ("Methodology", f"{m.identity} ({m.short_hash}, {self.origin})"),
            ("Selection", str(dict(m.selection))),
            ("Time basis", str(self.clock.time_basis)),
            ("Methodology Parameters", params),
            ("Methodology Coverage", f"{counts['skipped']} skipped, {counts['unsupported']} unsupported, "
                                     f"{counts['notEvaluable']} not evaluable"),
        ]


def build_lens(store: Store, snap: Snapshot, methodology: Methodology | None = None, origin: str = "packaged-default",
               overrides: dict[str, Any] | None = None) -> Lens:
    from ..report_policy import resolve_context
    from .prepare import prepare
    methodology = prepare(methodology or load_default(), overrides)
    history = store.recent_snapshots(PROBE_SNAPSHOTS, snap.game_time)
    clock = store.time_context(snap)
    verdicts = _evaluate_prepared(methodology, snap, overrides=overrides, probe_snapshots=history or [snap],
                        history=history or [snap], origin=origin, clock=clock)
    return Lens(methodology, origin, verdicts, snap, resolve_context(methodology), clock)
