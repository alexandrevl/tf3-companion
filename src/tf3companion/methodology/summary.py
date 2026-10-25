"""The `analyse` summary returned to the CLI and the MCP server: a capped presentation of an evaluation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_KINDS = ("company", "lines", "fleet", "cargo")
TOP_FINDINGS = 10
TOP_RECOMMENDATIONS = 15


def summarise(evaluation: dict[str, Any], folder: Path, files: list[str]) -> dict[str, Any]:
    """Cap an evaluation's findings and recommendations for display and add the output folder/files.

    The display caps live only here; the evaluation itself is always complete.
    """
    findings = evaluation["findings"]
    roles = {
        entity: {key: value for key, value in summary.items() if key != "assignments"}
        for entity, summary in evaluation["roles"].items()
    }
    markers = {r["id"]: r["markerCounts"] for r in evaluation["ruleResults"] if r["status"] == "ok"}
    coverage = evaluation["coverage"]
    return {
        "methodology": evaluation["methodology"],
        "timeBasis": evaluation["timeBasis"],
        "reportPolicy": evaluation["reportPolicy"],
        "engineThresholds": evaluation["engineThresholds"],
        "engineThresholdOrigins": evaluation["engineThresholdOrigins"],
        "save": evaluation["save"],
        "snapshot": evaluation["snapshot"],
        "roles": roles,
        "markersByRule": markers,
        "findings": {
            "bySeverity": dict(Counter(f["severity"] for f in findings)),
            "bySource": dict(Counter(f["source"] for f in findings)),
            "top": [
                {
                    "severity": f["severity"],
                    "code": f["code"],
                    "source": f["source"],
                    "title": f["title"],
                    "detail": f["detail"],
                    **({"untrusted": True} if f.get("untrusted") else {}),
                }
                for f in findings[:TOP_FINDINGS]
            ],
        },
        "recommendations": evaluation["recommendations"][:TOP_RECOMMENDATIONS],
        "skipped": coverage["skipped"],
        "unsupported": coverage["unsupported"],
        "notEvaluable": coverage["notEvaluable"],
        "disabledFindings": evaluation["disabledFindings"],
        "outputFolder": str(folder),
        "files": files,
        "note": evaluation["note"],
    }
