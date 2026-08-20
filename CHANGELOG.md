# Changelog

## 1.1.0

- Config flow: added a sensor visibility step (visible/disabled multi-select lists) after
  authentication, replacing hardcoded per-sensor visibility
- Fixed historical statistics backfill using the wrong statistics `source` for its entity-id
  `statistic_id`, which broke coordinator setup
- Fixed historical usage backfill resetting the cumulative sum on every import instead of
  continuing from the last stored total
- Fixed the API client silently swallowing GraphQL errors returned after authentication
- Rewrote README for HACS custom component conventions

## 0.1.0 - Initial commit

- Home Assistant custom integration for Nectr Energy
- GraphQL client authenticating against Nectr's mobile API
- Config flow for email/password setup with configurable poll interval
- Sensors for energy usage, account status, billing, Power Perks credit, and tariff rates
- Historical daily energy data backfilled into Home Assistant's recorder statistics
