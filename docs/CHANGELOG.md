# Changelog

## Unreleased

### Changed
- Canonicalization duplicate-key error code corrected from `CANON_DUPLICATE_KEY_AFTER_NORMALIZE` to `CANON_DUPLICATE_KEY_AFTER_NORMALIZATION`.
- Added legacy alias emission (`legacy: CANON_DUPLICATE_KEY_AFTER_NORMALIZE`) in immune pipeline canonicalization failures to support transition compatibility.

### Fixed
- `/v1/submit` now checks quarantine publish acknowledgements on reject paths and returns HTTP 503 if broker publish is rejected.

### Documentation
- Updated repository layout docs to include `reports/` and linked the main performance report.
