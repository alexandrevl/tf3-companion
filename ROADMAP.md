# TF3 Companion Roadmap

A local, explainable transport-company analyst. Players keep control of every gameplay action.

## Two independently distributable parts

- **TF3 Companion Bridge:** a read-only game mod that collects snapshots. Its public release needs verified activation/reload behavior, schema compatibility, original metadata and real-game thumbnail/screenshots.
- **TF3 Companion:** the Python package, `tf3c` CLI and agent-independent MCP server. It keeps local history, explains findings, generates reports and supports a player decision journal.

## Delivery sequence

| Stage | Outcome | Status / exit criterion |
| --- | --- | --- |
| Source build | English product, portable discovery/installer, explainable findings, six reports, MCP workflows and safe local storage | Implemented and exercised locally; evidence in [review notes](docs/review-notes.md) |
| Trustworthy game integration | Windows/macOS activation and refresh; persistent save lineage and isolated histories | Requires player-controlled live-game probes; no town-id fingerprinting |
| Distribution rehearsal | Clean-machine quickstart, intended AI-client setup, inspected package/mod artifacts and hosted CI | Package artifacts exercised locally; real clients, game platforms and first hosted CI remain gates |
| Public release | Reviewed compatibility matrix, original branding, tested mod thumbnail, release checklist and changelog | Publish only after gates pass and publication is separately approved |
| Deeper company decisions | Verified station-linked cargo diagnosis, calibrated fleet renewal, configurable collection and longitudinal follow-up | Planned in OpenSpec; recommendations require measured fields and verified units |

## Reporting principles

Annual reports describe observations, baselines and gaps. They never sum overlapping `profitYear` windows into invented calendar income. Occupancy trends describe samples, not time-weighted utilization. Missing collector data and uncertain mechanics stay visible.

The [detailed roadmap](docs/ROADMAP.md) is the canonical workstream inventory. [OpenSpec changes](openspec/changes/) hold designs and acceptance criteria. Implemented source, fixture verification, real-game evidence and publication are tracked separately.
