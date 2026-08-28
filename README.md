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
tariff data. Each poll also catches up any missing hourly grid/export/controlled-load usage into
Home Assistant's recorder statistics, so the Energy dashboard has continuous history rather than
a gap before setup.

On first install, once the sensor entities exist, the integration automatically backfills up to a
year of hourly history in the background (see **Historical data** below) — this only happens
once, the first time a tracked statistic has no data yet.

## Historical data

**Initial backfill.** After setup, once entities are created, the integration imports up to a
year of hourly Grid Consumption / Export Consumption / Controlled Load history in the background.
This runs automatically exactly once, the first time each statistic has no existing data — it
won't re-run on every restart.

**Re-running a backfill.** If you want to redo the backfill (for example, you'd only just joined
Nectr when you installed, or the initial run missed data due to a transient API issue), call the
**Nectr: Backfill history** action (`nectr.backfill_history`) from **Developer Tools → Actions**,
with an optional `days` field (default 365, max 1095) for how far back to go. This **clears and
fully re-imports** the tracked statistics rather than trying to splice older data in front of
what's already there — Home Assistant statistics require a monotonically increasing cumulative
sum, and a freshly computed earlier window starting its own sum from 0 would create a
discontinuity against whatever sum the existing data already reached. The Energy dashboard reads
deltas, so this reset doesn't affect what it displays.

**Recent history not showing up.** Home Assistant's History page prefers an entity's raw recorded
states over its long-term statistics whenever both exist for the same period, and it keeps raw
states for roughly the last 10 days by default. That means recently imported hourly statistics
can be invisible in History even though they imported correctly — it's showing you the sensor's
regular state updates instead, which won't have hourly granularity. To check statistics
directly, use the Energy dashboard (it always reads statistics, never raw states) or the
`recorder.get_statistics` action. If you want History itself to show the hourly data for that
window, clear the raw state history for the affected sensors — it doesn't touch the imported
statistics — with **Recorder: Purge entities** (`recorder.purge_entities`):

```yaml
action: recorder.purge_entities
data:
  entity_id:
    - sensor.your_grid_consumption_entity
    - sensor.your_export_consumption_entity
    - sensor.your_controlled_load_entity
  keep_days: 0
```

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
