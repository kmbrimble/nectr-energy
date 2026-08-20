# Nectr Energy

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/kmbrimble/nectr-energy)](https://github.com/kmbrimble/nectr-energy/releases)

Home Assistant custom integration for [Nectr Energy](https://www.nectr.com.au/), an Australian
electricity retailer. Pulls account, usage, and tariff data from Nectr's GraphQL API and exposes
it as Home Assistant sensors, with historical usage backfilled into the Energy dashboard.

## How it works

The integration authenticates against Nectr's mobile GraphQL API
(`mobile.nectr.com.au/graphql`) with your account email and password, then polls it on a
configurable interval for each active account on your login: usage, billing, Power Perks, and
tariff data. Each poll also backfills the previous day's hourly grid/export/controlled-load usage
into Home Assistant's recorder statistics, so the Energy dashboard has continuous history rather
than a gap before setup.

## Pre-requisites

- A Nectr Energy account with at least one active service
- Home Assistant's built-in `recorder` integration enabled (on by default) — required for
  historical usage backfill

## Installation

### Option 1: HACS (recommended)

1. In HACS, go to **Integrations** → the **⋮** menu → **Custom repositories**
2. Add this repository URL (`https://github.com/kmbrimble/nectr-energy`) with category
   **Integration**
3. Search for **Nectr Energy** in HACS and install it
4. Restart Home Assistant

### Option 2: Manual

1. Copy this repository's contents into `<config>/custom_components/nectr/`
2. Restart Home Assistant

## Configuration

Set up via the Home Assistant UI: **Settings → Devices & Services → Add Integration → Nectr
Energy**.

The config flow has two steps:

1. **Account** — enter your Nectr email and password, and choose an update interval (1, 3, 6,
   12, or 24 hours — default 24). Credentials are validated against the API and setup fails if no
   active account is found.
2. **Sensors** — choose which sensors to expose, from a single screen with two multi-select
   lists:
   - **Visible sensors** — shown in the entity list by default (defaults to the three energy
     sensors: Grid Consumption, Export Consumption, Controlled Load)
   - **Disabled sensors** — not created at all (defaults to none)

   Any sensor left off both lists is still created but hidden from the default entity list — you
   can make it visible later from the entity registry. A sensor listed as disabled takes
   precedence over being listed as visible.

## Sensors

| Sensor | Default | Notes |
|---|---|---|
| Grid Consumption | Visible | kWh, long-term statistics |
| Export Consumption | Visible | kWh, long-term statistics |
| Controlled Load | Visible | kWh, long-term statistics |
| Account Status | Hidden | |
| Plan Name | Hidden | |
| Billing Period Start / End | Hidden | |
| Account Balance | Hidden | |
| Power Perks Credit | Hidden | |
| Power Perks Status | Hidden | |
| Tariff General Usage | Hidden | |
| Tariff Solar Export | Hidden | |
| Tariff Controlled Load | Hidden | |
| Tariff Supply Charge | Hidden | |

One set of sensors is created per active Nectr account on your login.

## Requirements

- Home Assistant with the `recorder` integration available
- No additional Python dependencies beyond Home Assistant's bundled `aiohttp`

## Disclaimer

This is an unofficial, community-maintained integration and is not affiliated with or endorsed
by Nectr Energy.
