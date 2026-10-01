# Evaluation fixtures

`fixtures-v23/` is the active renderer regression set for MCP 0.23. Its inputs are exact, complete, non-persisted Core response shapes. `regress.py` uses this directory by default.

`fixtures/` contains pre-0.23 historical material for visual reference only. It is not active regression input and may contain removed tool shapes, local-adjustment totals, and synthetic alternatives.

Cross-workflow migration coverage lives in `tests/test_migration.py` with `tests/fixtures/exact-response-cases.json`. It covers ordinary, temporary-rate, temporary-discount, combined, blocked, and complete-comparison responses; passenger omission; source-request preservation; cache clearing; valid zero values; build-time MCP URL overrides; and rejection of local monetary mutation.

Do not promote a fixture that recomputes pricing. Assertions compare copied Core fields directly. The aggregate total is authoritative and is not required to equal the sum of line totals.
