# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Filter pseudo-locations «над містом», «над селом» in SKIP_WORDS and Event.is_valid
- Extended SKIP_WORDS: невизначено, орієнтовно, приблизно
- Tests on real message fixtures (`tests/fixtures/sample_messages.txt`, `test_parse_real_messages`)
- Parallel geocoding in dispatcher (`_enrich_regions` with asyncio.gather)
- pytest-cov in CI with coverage report
- Integration tests (`tests/integration/test_pipeline.py`)
- Geo and dispatcher unit tests
- Metrics: events_parsed, events_sent, geocode_cache_hit, geocode_api_called
- Structured logging (LOG_FORMAT=json)
- Health check HTTP endpoint (HEALTH_CHECK_PORT)
- Env validation at startup (SOURCE_CHANNELS, TARGET_CHANNEL)
- Architecture diagram in README

### Changed
- CI runs pytest with coverage (--cov-fail-under=40)
