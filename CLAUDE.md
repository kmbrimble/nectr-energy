# Project Instructions

Home Assistant custom integration (domain: `nectr`) for the Nectr Energy GraphQL API.
Flat file layout at repo root (not nested under `custom_components/`) — this *is* the
component directory. Code style lives in `.claude/rules/code-quality.md`.

## Architecture

- `api.py` — `NectrApiClient`: raw GraphQL calls to `mobile.nectr.com.au/graphql`.
- `coordinator.py` — polls the API on the configured interval, backfills hourly usage
  into HA's recorder statistics.
- `sensor.py` — entities built from coordinator data.

## Don'ts

- Don't hardcode credentials — email/password come from the config flow entry, never
  from source.
