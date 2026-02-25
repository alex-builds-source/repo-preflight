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
repo-preflight check --no-gitleaks
```

## Checks (v0)

- `readme_present` (fail)
- `license_present` (warn)
- `security_policy_present` (warn)
- `gitignore_basics` (fail/warn)
- `tracked_env_files` (fail)
- `tracked_keylike_files` (fail)
- `gitleaks_scan` (pass/warn/fail)

Exit codes:
- `0` pass
- `1` warnings only
- `2` failures present

## Security notes

- `repo-preflight` never prints raw secret values.
- `gitleaks` is run with `--redact`.

## License

MIT
