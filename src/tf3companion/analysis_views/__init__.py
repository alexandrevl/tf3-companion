"""Finite structured analyses over stored evidence, independent of reports.

Seven families (`VIEW_NAMES`) each expose `evaluate(evidence, *, context)` in their own module; their
evidence is prepared from the Store by the matching `<family>_evidence.load(reader, context)`.
`evaluate_views` is the one closed, explicit dispatch: no registry, no plugin protocol.
"""

from __future__ import annotations

from ..store import Store
from .models import VIEW_NAMES, AnalysisViews, EvaluationContext, select_views
from .reader import EvidenceReader


def evaluate_views(store: Store, context: EvaluationContext, names: tuple[str, ...]) -> AnalysisViews:
    """Evaluate exactly the selected views at the context's endpoint; an empty selection reads nothing."""
    names = select_views(names)
    if not names:
        return AnalysisViews()
    reader = EvidenceReader(store, context)
    results: dict[str, object] = {}
    for name in names:
        if name == "bottlenecks":
            from . import bottlenecks, bottlenecks_evidence

            results[name] = bottlenecks.evaluate(bottlenecks_evidence.load(reader, context), context=context)
        elif name == "expansion":
            from . import expansion, expansion_evidence

            results[name] = expansion.evaluate(expansion_evidence.load(reader, context), context=context)
        elif name == "lines-history":
            from . import lines_history, lines_history_evidence

            results[name] = lines_history.evaluate(lines_history_evidence.load(reader, context), context=context)
        elif name == "history":
            from . import history, history_evidence

            results[name] = history.evaluate(history_evidence.load(reader, context), context=context)
        elif name == "industries":
            from . import industries, industries_evidence

            results[name] = industries.evaluate(industries_evidence.load(reader, context), context=context)
        elif name == "vehicle-roi":
            from . import vehicle_roi, vehicle_roi_evidence

            results[name] = vehicle_roi.evaluate(vehicle_roi_evidence.load(reader, context), context=context)
        else:
            from . import towns, towns_evidence

            results[name] = towns.evaluate(towns_evidence.load(reader, context), context=context)
    return AnalysisViews(**{name.replace("-", "_"): view for name, view in results.items()})


__all__ = ["VIEW_NAMES", "AnalysisViews", "EvaluationContext", "EvidenceReader", "evaluate_views", "select_views"]
