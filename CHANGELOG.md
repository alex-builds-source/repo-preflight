# Changelog

All notable changes to this project will be documented in this file.

## [0.1.2] - 2026-02-25
### Added
- Check profiles: `quick`, `full`, `ci`.
- Config file support via `.repo-preflight.toml` (or `--config`).
- Severity override system (`[severity_overrides]`).
- `list-checks` command for discoverable check ids.
- Example config file: `.repo-preflight.toml.example`.

### Changed
- JSON payload now includes `profile`, `config_path`, and `check_ids`.
- Runtime resolution now merges profile defaults + config + CLI overrides.
- Expanded test coverage for config parsing and profile behavior.

## [0.1.1] - 2026-02-25
### Added
- `--strict` mode to treat warnings as failures for CI/agent gating.
- New hygiene checks: `remote_origin`, `clean_worktree`, `default_branch_style`, `license_identifier`.
- JSON payload now includes `strict` and computed `exit_code`.

### Changed
- Added explicit `git_repository` failure check at the start of preflight.
- Expanded test coverage for strict mode and new checks.

## [0.1.0] - 2026-02-25
### Added
- Initial `repo-preflight` release.
- `repo-preflight check` command with pass/warn/fail checks.
- JSON output mode for agent integration.
- Core checks for docs presence, tracked env/key files, gitignore baseline, and gitleaks.
