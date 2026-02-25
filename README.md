# repo-preflight

Check whether a repository is safe and ready to publish.

Designed for both humans and agents:
- Human-friendly summary output
- Machine-friendly `--json` output

## Install

```bash
pip install -e .
```

## Usage

```bash
repo-preflight check
repo-preflight check --path /path/to/repo
repo-preflight check --json
repo-preflight check --strict
repo-preflight check --no-gitleaks
```

## Modes

- Default mode: warnings return exit code `1`
- Strict mode (`--strict`): warnings are treated as failures (exit code `2`)

## Checks (v0.1.1)

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
