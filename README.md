# Nectr Energy

Home Assistant custom integration for [Nectr Energy](https://www.nectr.com.au/), an Australian
electricity retailer. Pulls account, usage, and tariff data from Nectr's GraphQL API and exposes
it as Home Assistant sensors.

## Features

- Authenticates with your Nectr email/password
- Sensors for:
  - Energy usage (grid consumption, solar export, controlled load)
  - Account status
  - Billing info
  - Power Perks credit
  - Tariff rates
- Backfills historical daily energy data into Home Assistant's long-term statistics (recorder)
- Configurable update interval (1, 3, 6, 12, or 24 hours — default 24)

## Installation

Install via [HACS](https://hacs.xyz/) as a custom repository, or copy this directory into your
Home Assistant `custom_components/nectr` folder.

## Configuration

Set up via the Home Assistant UI (Settings → Devices & Services → Add Integration → Nectr
Energy). You'll need:

- Your Nectr account email
- Your Nectr account password

The integration validates your credentials and confirms you have at least one active account
before completing setup.

## How it works

| File | Purpose |
|------|---------|
| `api.py` | GraphQL client (`NectrApiClient`) for Nectr's API at `mobile.nectr.com.au/graphql` |
| `config_flow.py` | Config UI flow — prompts for and validates credentials |
| `coordinator.py` | Polls the API on the configured interval and injects historical stats |
| `sensor.py` | Sensor entities: energy, account/billing, and tariff sensors |
| `const.py` | Domain and config constants |

## Disclaimer

This is an unofficial, community-maintained integration and is not affiliated with or endorsed
by Nectr Energy.
