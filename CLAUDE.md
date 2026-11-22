# Project Instructions

Home Assistant custom integration (domain `nectr`) for the Nectr Energy GraphQL API. Flat layout:
the repo root *is* the component directory (`hacs.json` has `content_in_root`), so there is no
`custom_components/` folder. Code style: `.claude/rules/code-quality.md`.
Wiki page: `85-software-projects/nectr-energy`. Wiki: http://otterwiki/ (pages are Markdown in the
git clone `/projects/homelab-wiki-clone`; search it with grep). The wiki is private (LAN and
WireGuard only) and this repo is public: never copy wiki detail into the repo, commits or PRs.

## Testing

Two separate suites; never mix them in one pytest invocation.

- Stub tests, no install: `for f in tests/test_*.py; do python3 "$f"; done`
- Real-HA suite: `uv venv --python 3.14 .venv && uv pip install --python .venv/bin/python -r requirements_test.txt`,
  then `.venv/bin/pytest tests/ha` (the explicit path matters). List `recorder_mock` before `hass` in
  test signatures.

Mechanics and rationale (pytest.ini placement, conftest symlink): wiki page above.

## Deploy and verify

A merge to `master` runs CI only (`CI / stub-tests`, `CI / ha-tests`); nothing deploys. A release is a
tag: bump `manifest.json` `version` and add a `## X.Y.Z` section to `CHANGELOG.md` in a PR, merge, then
`git tag vX.Y.Z <merge-commit> && git push origin vX.Y.Z` on Gitea. The mirror carries the tag to
GitHub and `.github/workflows/release.yml` creates the GitHub Release (see the `forge-release` skill).
Installing on the live Home Assistant is a separate step documented in the wiki.

## Non-negotiable constraints

- **Gitea is primary; never push to the GitHub mirror** (`origin` is Gitea; `master` is protected, PR plus
  green CI; use `gt`, not `gh`). The mirror force-syncs and prunes refs, so a direct push is lost or
  destructive. GitHub Issues, Wiki, Projects and PRs are off.
- **Releases must keep appearing on GitHub.** HA installs this through HACS/Marketplace from GitHub
  Releases, made by `.github/workflows/release.yml` from the mirrored tag. Do not create releases by
  hand. `hacs.json` must not set `zip_release` (the workflow refuses to run if it is set).
- **No credentials in source.** Email and password come from the config flow entry only, because the
  repo is public.
- **A lock serialises every statistics write** (`coordinator.py`: refresh, hourly retry, backfill),
  because each derives its cumulative `sum` from the last stored row; concurrent writes corrupt sums.
- **Do not add a repo-root `pytest.ini`.** The root `__init__.py` would be imported as a top-level module
  and fail; the real-HA suite is rooted in `tests/ha/` on purpose.
- **Do not fix `test_duplicate_email_is_aborted` by removing its `xfail(strict=True)`.** It guards a known
  bug (`config_flow.py` wraps `async_set_unique_id` in a bare `except Exception`, swallowing `AbortFlow`).
  Fix the code, then remove the marker.
- **Known flake:** `tests/ha/test_hourly_history_retry.py` is timing sensitive; CI runs it with
  `--reruns 2`. A red `ha-tests` that goes green on re-run is this flake, not a regression.
- Never commit `nectr_graphql_logs.jsonl` (gitignored raw API log; may contain account data).

## Code review

- **Exposure:** not internet-facing; it runs inside Home Assistant and calls the Nectr cloud API. A
  compromise gives access to one Nectr account and the HA process. The repo itself is public.
- **What users rely on:** `coordinator.py` (writes hourly usage into HA long-term statistics, which
  the energy dashboards read; a bug can corrupt cumulative sums), `api.py` (auth and GraphQL),
  `config_flow.py` (stored credentials).
- **Out-of-repo infrastructure:** the Gitea-to-GitHub push mirror, the GitHub release workflow's runner,
  the HACS/Marketplace install path and the live HA install are not in this repo. "Nothing here
  implements X" findings about those are `UNVERIFIABLE FROM THIS REPO`.
- **Test reality:** the stub suite is fast and weak (everything stubbed); the real-HA suite needs
  Python 3.14 and a venv, and runs against HA 2026.9.x while live is newer, so green is necessary but not
  sufficient. The retry test is flaky; gaps older than 30 days are not covered.

## Wiki pages

- `85-software-projects/nectr-energy` (architecture, release, live deploy, rollback, history)
- `40-home-automation/integrations`, `40-home-automation/energy-solar-grid`
