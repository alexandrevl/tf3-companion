"""Finite report judgments and one immutable resolved analysis context."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, make_dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .analysis import Thresholds

REGISTRY_VERSION = 1


@dataclass(frozen=True)
class Criterion:
    default: float
    minimum: float
    maximum: float
    unit: str
    comparison: str
    integer: bool = False
    exclusive_minimum: bool = False


REGISTRY = {
    "industries": {
        "below_capacity_ratio": Criterion(
            0.9, 0, 1, "ratio", "produced < ratio * positive capacity", exclusive_minimum=True
        ),
        "production_decline_min": Criterion(30, 0, 1e9, "recorded production counter", "first minus last >= minimum"),
    },
    "lines-history": {
        "relative_change_ratio": Criterion(0.15, 0, 1, "ratio", "relative term in maximum threshold"),
        "noise_factor": Criterion(2, 0, 10, "MAD multiplier", "noise term in maximum threshold"),
        "floor_share": Criterion(0.02, 0, 1, "ratio", "current absolute profit floor multiplier"),
    },
    "bottlenecks": {
        "persistence_streak": Criterion(3, 3, 36, "eligible samples", "latest streak >= minimum", True),
        "noisy_min_share": Criterion(0.4, 0, 1, "ratio", "sightings / eligible samples >= minimum"),
        "pileup_min": Criterion(3, 2, 1000, "recorded terminal vehicles", "count >= minimum", True),
        "long_wait_days": Criterion(
            10, 0, 36500, "raw daysAtTerminal (unit unverified)", "counter >= minimum", exclusive_minimum=True
        ),
        "rising_stock_min_fill": Criterion(0.5, 0, 1, "ratio", "fill >= minimum and < effective full_stock_ratio"),
        "rising_stock_min_slope": Criterion(
            0.02, 0, 1, "capacity fraction / sample", "slope >= minimum", exclusive_minimum=True
        ),
    },
    "expansion": {
        **{
            f"weight_{k}": Criterion(v, 0, 100, "points", "component budget; budgets sum to 100")
            for k, v in (("volume", 30), ("distance", 20), ("urgency", 20), ("pull", 10), ("chain", 10), ("proven", 10))
        },
        "volume_reference": Criterion(
            150, 0, 1e9, "recorded annual cargo counter", "volume / reference capped at 1", exclusive_minimum=True
        ),
        **{
            f"distance_{k}_km": Criterion(v, 0, 100000, "straight-line km", "short < sweet_from <= sweet_to < long")
            for k, v in (("short", 0.5), ("sweet_from", 3), ("sweet_to", 10), ("long", 20))
        },
        "distance_long_floor": Criterion(0.4, 0, 1, "budget fraction", "distance fraction at/beyond long"),
        "closing_penalty": Criterion(30, 0, 100, "points per closing endpoint", "deduct per endpoint"),
        "full_input_penalty": Criterion(15, 0, 100, "points", "deduct when fill >= effective full_stock_ratio"),
    },
}
FAMILY_TYPES = {
    family: make_dataclass(
        "".join(x.title() for x in family.split("-")) + "Policy",
        [(key, int if spec.integer else float) for key, spec in values.items()],
        frozen=True,
    )
    for family, values in REGISTRY.items()
}


def validate_report_policies(raw: Any) -> list[tuple[str, str]]:
    issues = []
    if not isinstance(raw, Mapping):
        return [("/report_policies", f"expected object, got {raw!r}")]
    valid = True
    for family, supplied in raw.items():
        path = f"/report_policies/{family}"
        if family not in REGISTRY:
            issues.append((path, f"unsupported family {family!r}; supported: {', '.join(REGISTRY)}"))
            valid = False
            continue
        if not isinstance(supplied, Mapping):
            issues.append((path, f"expected object, got {supplied!r}"))
            valid = False
            continue
        for key, value in supplied.items():
            spec = REGISTRY[family].get(key)
            location = f"{path}/{key}"
            if spec is None:
                issues.append((location, f"unsupported key {key!r}; supported: {', '.join(REGISTRY[family])}"))
                valid = False
                continue
            numeric = type(value) is int or (type(value) is float and math.isfinite(value))
            if (
                not numeric
                or (spec.integer and value != int(value))
                or not (spec.minimum < value if spec.exclusive_minimum else spec.minimum <= value)
                or value > spec.maximum
            ):
                issues.append(
                    (
                        location,
                        f"got {value!r}; expected finite {'integer' if spec.integer else 'number'} in {'(' if spec.exclusive_minimum else '['}{spec.minimum}, {spec.maximum}]",
                    )
                )
                valid = False
    if valid:
        values = {
            k: {n: s.default for n, s in entries.items()} | dict(raw.get(k, {})) for k, entries in REGISTRY.items()
        }
        expansion = values["expansion"]
        if not math.isclose(
            sum(v for k, v in expansion.items() if k.startswith("weight_")), 100, abs_tol=1e-9, rel_tol=0
        ):
            issues.append(
                (
                    "/report_policies/expansion/weight_volume",
                    "effective component weights must sum to 100 (absolute tolerance 1e-9)",
                )
            )
        if (
            not expansion["distance_short_km"]
            < expansion["distance_sweet_from_km"]
            <= expansion["distance_sweet_to_km"]
            < expansion["distance_long_km"]
        ):
            issues.append(
                (
                    "/report_policies/expansion/distance_short_km",
                    "effective distances require short < sweet_from <= sweet_to < long",
                )
            )
    return issues


@dataclass(frozen=True)
class ReportAnalysisContext:
    thresholds: Thresholds
    policies: Mapping[str, Any]
    origins: Mapping[str, Mapping[str, str]]
    threshold_origins: Mapping[str, str]

    def provenance(self) -> dict[str, Any]:
        return {
            "reportPolicy": {
                "registryVersion": REGISTRY_VERSION,
                "values": {k: asdict(v) for k, v in self.policies.items()},
                "origins": {k: dict(v) for k, v in self.origins.items()},
            },
            "engineThresholds": asdict(self.thresholds),
            "engineThresholdOrigins": dict(self.threshold_origins),
        }


def resolve_context(methodology=None, *, thresholds: Thresholds | None = None) -> ReportAnalysisContext:
    if methodology is not None and thresholds is not None:
        raise ValueError("methodology and explicit thresholds are mutually exclusive")
    data = methodology.data if methodology is not None else {}
    raw = data.get("report_policies", {})
    issues = validate_report_policies(raw)
    if issues:
        raise ValueError("; ".join(f"{path}: {message}" for path, message in issues))
    engine = (data.get("engine") or {}).get("thresholds") or {}
    effective = thresholds if thresholds is not None else Thresholds(**engine)
    defaults = asdict(Thresholds())
    for key, value in asdict(effective).items():
        numeric = type(value) is int or (type(value) is float and math.isfinite(value))
        integer = type(defaults[key]) is int
        if not numeric or value < 0 or (integer and (type(value) is not int)):
            raise ValueError(
                f"/engine/thresholds/{key}: got {value!r}; expected finite nonnegative {'integer' if integer else 'number'}"
            )
    policies, origins = {}, {}
    for family, entries in REGISTRY.items():
        explicit = raw.get(family, {})
        values = {key: explicit.get(key, spec.default) for key, spec in entries.items()}
        policies[family] = FAMILY_TYPES[family](**values)
        origins[family] = MappingProxyType({key: "methodology" if key in explicit else "default" for key in entries})
    return ReportAnalysisContext(
        effective,
        MappingProxyType(policies),
        MappingProxyType(origins),
        MappingProxyType({key: "methodology" if key in engine else "default" for key in asdict(effective)}),
    )
