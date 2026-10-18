"""A methodology applied to one snapshot: the object report builders and the service share."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .. import analysis
from ..snapshot import Snapshot
from ..store import Store
from .engine import Verdicts, evaluate, thresholds_for
from .loader import load_default
from .model import Methodology

PROBE_SNAPSHOTS = 12


@dataclass(frozen=True, eq=False)
class Lens:
    methodology: Methodology
    origin: str                     # request | binding | default | file
    verdicts: Verdicts
    snapshot: Snapshot

    @property
    def thresholds(self) -> analysis.Thresholds:
        return thresholds_for(self.methodology)

    def provenance(self) -> dict[str, Any]:
        return {**self.methodology.provenance(), "origin": self.origin, "parameters": self.verdicts.parameters,
                "parameterOverrides": self.verdicts.overrides}

    def header(self) -> list[tuple[str, str]]:
        """Report header entries naming the methodology, its parameters and the coverage counts."""
        m, v = self.methodology, self.verdicts
        params = ", ".join(f"{k}={val}" for k, val in sorted(v.parameters.items())) or "none"
        counts = v.counts()
        return [
            ("Methodology", f"{m.identity} ({m.short_hash}, {self.origin})"),
            ("Methodology Parameters", params),
            ("Methodology Coverage", f"{counts['skipped']} skipped, {counts['unsupported']} unsupported, "
                                     f"{counts['notEvaluable']} not evaluable"),
        ]


def build_lens(store: Store, snap: Snapshot, methodology: Methodology | None = None, origin: str = "default",
               overrides: dict[str, Any] | None = None) -> Lens:
    """Evaluate `methodology` (default: the neutral one) on `snap`, probing recent snapshots for data availability."""
    methodology = methodology or load_default()
    history = store.recent_snapshots(PROBE_SNAPSHOTS, snap.game_time)
    verdicts = evaluate(methodology, snap, overrides=overrides, probe_snapshots=history or [snap],
                        history=history or [snap], origin=origin)
    return Lens(methodology, origin, verdicts, snap)
