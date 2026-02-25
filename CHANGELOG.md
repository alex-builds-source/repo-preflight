# Changelog

All notable changes to this project will be documented in this file.

## [0.1.4] - 2026-02-25
### Added
- History-aware large-blob check: `history_large_blobs`.
- Config support for history scan controls:
  - `preflight.max_history_blob_kib`
  - `preflight.history_object_limit`
- New output modes:
  - `--compact` for concise CI logs
  - `--sarif` for SARIF 2.1.0 output

### Changed
- JSON output now includes history scan settings.
- Expanded tests for history-blob detection and SARIF payload generation.

## [0.1.3] - 2026-02-25
### Added
- Rule packs: `oss-library`, `internal-service`, `cli-tool`.
- Large binary hygiene check: `tracked_large_files` with configurable threshold.
- `list-rule-packs` command.
- Config support for `preflight.rule_pack` and `preflight.max_tracked_file_kib`.

### Changed
- Runtime policy resolution now merges: profile defaults + rule pack + config + CLI overrides.
- JSON payload now includes `rule_pack` and `max_tracked_file_kib`.
- Expanded tests for rule packs, config fields, and large-file behavior.

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
