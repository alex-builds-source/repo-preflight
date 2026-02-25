# Changelog

All notable changes to this project will be documented in this file.

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
