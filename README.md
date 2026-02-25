# repo-preflight

Check whether a repository is safe and ready to publish.

Designed for both humans and agents:
- Human-friendly summary output
- Compact output for CI logs
- Machine-friendly JSON and SARIF output
- Policy-doc output for easy policy review

## Install

```bash
pip install -e .
```

## Usage

```bash
repo-preflight check
repo-preflight check --path /path/to/repo
repo-preflight check --profile quick
repo-preflight check --profile ci
repo-preflight check --rule-pack oss-library
repo-preflight check --check-group diff
repo-preflight check --check-group foundation --check-group secrets
repo-preflight check --strict
repo-preflight check --gitleaks
repo-preflight check --no-gitleaks
repo-preflight check --max-file-kib 2048
repo-preflight check --max-history-kib 2048
repo-preflight check --history-object-limit 5000
repo-preflight check --max-diff-files 200 --max-diff-changed-lines 4000 --max-diff-object-kib 5120
repo-preflight check --diff-mode pr --pr-base-ref origin/main
repo-preflight check --diff-base origin/main --diff-target HEAD
repo-preflight check --json
repo-preflight check --compact
repo-preflight check --sarif
repo-preflight policy-doc --path . --output POLICY.md
repo-preflight policy-template --rule-pack oss-library --output .repo-preflight.toml
repo-preflight list-checks
repo-preflight list-rule-packs
```

## Profiles

- `quick`: fast checks, skips `gitleaks_scan` by default
- `full`: all checks, warnings allowed
- `ci`: all checks, strict by default

CLI flags can override profile defaults.

## Rule packs

- `oss-library`: stricter docs/license/security expectations
- `internal-service`: internal service defaults with strict repo hygiene and strict diff severity
- `cli-tool`: balanced CLI project defaults

Rule packs set policy defaults and can still be overridden by config/CLI.

## Diff-aware checks

When a diff base is available (`--diff-base` or `--diff-mode pr`), preflight evaluates changed files in the range:

- `diff_changed_files`
- `diff_large_files`
- `diff_object_sizes`
- `diff_patch_size`

`--diff-mode pr` is CI-friendly and auto-resolves refs from PR/MR env vars with fallback base ref.

## Config file (`.repo-preflight.toml`)

By default, `repo-preflight` loads config from the target path.
You can override with `--config <path>` or disable with `--no-config`.

Example:

```toml
[preflight]
profile = "ci"
rule_pack = "oss-library"
strict = true
diff_mode = "pr"
pr_base_ref = "origin/main"
diff_target = "HEAD"
max_tracked_file_kib = 2048
max_history_blob_kib = 2048
max_diff_files = 200
max_diff_changed_lines = 4000
max_diff_object_kib = 5120
history_object_limit = 10000

[checks]
exclude = ["clean_worktree"]

[severity_overrides]
license_present = "fail"
```

## Check groups

Use `--check-group` (repeatable) to run focused subsets of checks:

- `foundation`: git/repo hygiene (`git_repository`, `remote_origin`, `clean_worktree`, `default_branch_style`)
- `docs`: docs/license/security policy checks
- `secrets`: secret-exposure focused checks (including `gitleaks_scan`)
- `size`: tracked/history/diff size checks
- `diff`: PR/diff-aware checks

## Checks (v0.1.9)

- `git_repository` (fail)
- `remote_origin` (warn)
- `clean_worktree` (warn)
- `default_branch_style` (warn)
- `readme_present` (fail)
- `license_present` (warn)
- `license_identifier` (warn)
- `security_policy_present` (warn)
- `gitignore_basics` (fail/warn)
- `tracked_env_files` (fail)
- `tracked_keylike_files` (fail)
- `tracked_large_files` (warn)
- `history_large_blobs` (warn)
- `diff_changed_files` (pass/warn)
- `diff_large_files` (pass/warn)
- `diff_object_sizes` (pass/warn)
- `diff_patch_size` (pass/warn)
- `gitleaks_scan` (pass/warn/fail)

Exit codes:
- `0` all checks pass
- `1` warnings only (default mode)
- `2` failures present, or warnings in strict mode

## Security notes

- `repo-preflight` never prints raw secret values.
- `gitleaks` is run with `--redact`.

## License

MIT
