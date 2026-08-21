# Changelog

## 1.2.2

- Fixed "expected str" error when submitting the credentials screen, caused by the Refresh
  Interval dropdown's default value not being a string
- Moved Refresh Interval off the credentials screen; new installs default to 24h and it's now
  editable afterwards via Settings > Devices & Services > Nectr > Configure (#25)

## 1.2.1

- Added local `brand/` images (`icon.png`, `icon@2x.png`, `logo.png`, `logo@2x.png`) so the
  integration icon shows in the Home Assistant UI without submitting to `home-assistant/brands`.
  Requires **Home Assistant 2026.3 or later** — on older versions the integrations list will
  still show the generic placeholder, since local brand image support (the Brands Proxy API)
  was introduced in 2026.3.

## 1.2.0

- Config flow: Refresh Interval is now a dropdown selector (was a radio-style list)
- Config flow: replaced the separate visible/disabled sensor multi-select lists with a
  single visible/hidden/disabled dropdown per sensor
- Added `strings.json` and `translations/en.json` for the config flow UI labels
- Added brand icons (`brands/icon.png`, `brands/icon@2x.png`)
- Fixed repository structure for HACS (`content_in_root`)

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
