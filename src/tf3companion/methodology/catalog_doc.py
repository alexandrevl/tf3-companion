"""Generate the `methodology-fields` knowledge topic from the field registry.

Run `uv run python -m tf3companion.methodology.catalog_doc` after changing the registry; a test fails
when the committed topic is out of date.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from . import fields as fieldmod
from .model import ENTITIES

TOPIC = "methodology-fields.md"

INTRO = """# Methodology fields

The facts an analysis methodology may read. A methodology names these fields in conditions, measures, message
templates, tables and charts; it can never change them. The list is generated from the field registry in
`src/tf3companion/methodology/fields.py` (regenerate with `uv run python -m tf3companion.methodology.catalog_doc`),
so every field here exists in this companion release.

Two outcomes when a rule names a field:
- the name is **not in this list**: the rule is *unsupported* (reason `unknown field`, with the nearest name when close);
  the file still loads and every other rule is evaluated;
- the name is in this list but the save's snapshots do not carry its source data: the rule is *skipped*
  (reason `missing data: <snapshot path>`).
A single entity whose own value is missing is *not evaluable* for that rule; a missing value is never zero, never an
empty string and never satisfies a condition.

Fields marked **not collected yet** need data the bridge mod does not emit in this release (station positions);
rules using them are skipped until the collector provides it.

`<entity>.line.<field>` (for `vehicle` and `stop`) reads any `line.*` field below for the entity's line, for example
`vehicle.line.name` or `stop.line.carrier`. `line.name_capture.<name>` (also `vehicle.line.name_capture.<name>`) is a
named group captured by the first matching `name_patterns` entry; it is missing when no pattern matches. Every entity
has a `<entity>.role` field holding the role this methodology assigned, or `unclassified`.

Measurement caveats apply to every methodology: `line.load` is an instantaneous reading, `profitYear` is a rolling game
year (partial for young lines) and never calendar income, `line.age_years` is the oldest vehicle's age (a lower bound), and
ages divide by `meta.yearDuration`, which can differ from the calendar year.
"""


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_catalog() -> str:
    out = [INTRO]
    for entity in ENTITIES:
        specs = sorted((s for s in fieldmod.all_fields() if s.entity == entity), key=lambda s: s.name)
        title = {"stop": "stop (a stop of a line; aggregate rules only)"}.get(entity, entity)
        out += [f"## {title}", "", "| Field | Type | Source (snapshot path) | Meaning and caveat |", "|---|---|---|---|"]
        for spec in specs:
            sources = ", ".join(f"`{p}`" for p in spec.sources)
            note = spec.description + (f" **Caveat:** {spec.caveat}" if spec.caveat else "")
            flag = " **Not collected yet.**" if not spec.collected else ""
            out.append(f"| `{spec.name}` | {spec.type} | {sources} | {_cell(note)}{flag} |")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def topic_path() -> Path:
    return Path(str(files("tf3companion").joinpath("knowledge", TOPIC)))


def main() -> None:
    topic_path().write_text(render_catalog(), encoding="utf-8")


if __name__ == "__main__":
    main()
