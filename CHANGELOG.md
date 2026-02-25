# Changelog

All notable changes to this project will be documented in this file.

## [0.1.9] - 2026-02-25
### Added
- Optional repeatable check-group filtering via `--check-group` for faster focused runs.
- Built-in check groups: `foundation`, `docs`, `secrets`, `size`, `diff`.

### Changed
- `diff_object_sizes` now evaluates blobs in a base/target tree-aware way for PR/diff robustness.
- Expanded tests for check-group runtime filtering and tree-aware diff object-size behavior.

## [0.1.8] - 2026-02-25
### Added
- Diff object-size check: `diff_object_sizes`.
- Diff object-size controls:
  - `--max-diff-object-kib`
  - `preflight.max_diff_object_kib`

### Changed
- Rule-pack diff defaults expanded to include `diff_patch_size`, `diff_large_files`, and `diff_object_sizes` severities.
- JSON output now includes `max_diff_object_kib`.
- Expanded tests for diff object-size checks and updated runtime/config coverage.

## [0.1.7] - 2026-02-25
### Added
- Diff-depth threshold check: `diff_patch_size`.
- Diff threshold controls:
  - `--max-diff-files`
  - `--max-diff-changed-lines`
  - `preflight.max_diff_files`
  - `preflight.max_diff_changed_lines`
- `policy-template` command for rule-pack-oriented `.repo-preflight.toml` generation.

### Changed
- JSON output now includes diff-depth threshold settings.
- Expanded tests for diff patch-size behavior and policy-template generation.

## [0.1.6] - 2026-02-25
### Added
- PR/CI-aware diff mode (`--diff-mode pr`) with fallback base ref control (`--pr-base-ref`).
- Config support for diff mode settings:
  - `preflight.diff_mode`
  - `preflight.pr_base_ref`
- `policy-doc` command to render effective policy as markdown.

### Changed
- JSON and SARIF outputs now include diff mode metadata (`diff_mode`, `pr_base_ref`).
- Expanded tests for PR diff-mode behavior and policy-doc generation.

## [0.1.5] - 2026-02-25
### Added
- Diff-aware checks:
  - `diff_changed_files`
  - `diff_large_files`
- Diff controls via CLI/config:
  - `--diff-base`, `--diff-target`
  - `preflight.diff_base`, `preflight.diff_target`

### Changed
- JSON output now includes `diff_base` and `diff_target`.
- SARIF output now includes diff metadata in run properties.
- Expanded tests for diff-aware behavior.

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
