## 1. Implementation
- [x] Validate bounds before refresh/log/query side effects.
- [x] Serialize refresh writers and atomically publish requests and reports.
- [x] Fail current-state queries on import errors; retain diagnostic disclosure.
- [x] Keep offline knowledge and doctor independent of game discovery.
- [x] Match catalog availability to collector year boundaries.
- [x] Escape report text and validate annual coverage/year arguments.
- [x] Acknowledge bridge output only on success and throttle failures; bump revision to 2.

## 2. Verification
- [x] Run integrated behavior regressions.
- [x] Exercise real CLI and MCP stdio with isolated player fixtures.
- [x] Build and install the wheel; inspect packaged knowledge and mod content.
- [x] Inspect offline HTML in a browser.
- [x] Verify bridge failure/retry behavior with a Lua harness.

## 3. Live release gate
- [ ] Validate revision 2 after game reload on macOS and Windows; do not infer game compatibility from the harness.
