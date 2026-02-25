# repo-preflight

Check whether a repository is safe and ready to publish.

Designed for both humans and agents:
- Human-friendly summary output
- Compact output for CI logs
- Machine-friendly JSON and SARIF output

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
repo-preflight check --strict
repo-preflight check --gitleaks
repo-preflight check --no-gitleaks
repo-preflight check --max-file-kib 2048
repo-preflight check --max-history-kib 2048
repo-preflight check --history-object-limit 5000
repo-preflight check --json
repo-preflight check --compact
repo-preflight check --sarif
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
- `internal-service`: internal service defaults with strict repo hygiene
- `cli-tool`: balanced CLI project defaults

Rule packs set policy defaults and can still be overridden by config/CLI.

## Config file (`.repo-preflight.toml`)

By default, `repo-preflight` loads config from the target path.
You can override with `--config <path>` or disable with `--no-config`.

Example:

```toml
[preflight]
profile = "ci"
rule_pack = "oss-library"
strict = true
max_tracked_file_kib = 2048
max_history_blob_kib = 2048
history_object_limit = 10000

[checks]
exclude = ["clean_worktree"]

[severity_overrides]
license_present = "fail"
```

## Checks (v0.1.4)

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
