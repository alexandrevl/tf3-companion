"""Evaluate one analysis view (and optionally its report document) over a test store's latest snapshot."""
from __future__ import annotations

from tf3companion.analysis import Thresholds
from tf3companion.analysis_views import EvaluationContext, evaluate_views
from tf3companion.report_policy import resolve_context

MODULES = {"bottlenecks": "report_bottlenecks", "expansion": "report_expansion", "lines-history": "report_lines_history",
           "history": "report_history", "industries": "report_industries", "vehicle-roi": "report_vehicle_roi",
           "towns": "report_towns"}


def context(store, thresholds: Thresholds | None = None, lens=None) -> EvaluationContext:
    """The operation context of the store's latest snapshot: a lens's captured policies, or explicit/default thresholds."""
    snap = store.latest()
    if snap is None:
        raise ValueError("No snapshot found. Load a save with the bridge enabled and run tf3c refresh.")
    if lens is not None:
        return EvaluationContext.from_lens(lens, None, store.previous_of(snap))
    return EvaluationContext(snap, resolve_context(thresholds=thresholds), store.time_context(snap), None,
                             store.previous_of(snap))


def view(store, name: str, thresholds: Thresholds | None = None, lens=None):
    ctx = context(store, thresholds, lens)
    return getattr(evaluate_views(store, ctx, (name,)), name.replace("-", "_"))


def document(store, name: str, thresholds: Thresholds | None = None, lens=None):
    """The family report document built from its evaluated view, as the report composer does."""
    from importlib import import_module
    ctx = context(store, thresholds, lens)
    result = getattr(evaluate_views(store, ctx, (name,)), name.replace("-", "_"))
    return import_module(f"tf3companion.{MODULES[name]}").build(result, context=ctx)
