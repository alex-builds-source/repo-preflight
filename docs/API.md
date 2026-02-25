# API

`repo-preflight` is a CLI-first tool.

## Machine-readable interface

### Commands
- `repo-preflight check --json --path <repo> [--profile <quick|full|ci>] [--strict|--no-strict] [--gitleaks|--no-gitleaks] [--config <path>] [--no-config]`
- `repo-preflight list-checks`

### Output schema (v0.1.2)

```json
{
  "path": "/abs/path",
  "profile": "ci",
  "strict": true,
  "config_path": "/abs/path/.repo-preflight.toml",
  "check_ids": ["readme_present", "tracked_env_files"],
  "summary": { "pass": 0, "warn": 0, "fail": 0 },
  "exit_code": 0,
  "results": [
    {
      "id": "readme_present",
      "status": "pass|warn|fail",
      "message": "...",
      "fix": "..."
    }
  ]
}
```

### Exit code behavior

- `0`: all checks pass
- `1`: warnings only in default mode
- `2`: failures present, or warnings when strict mode is enabled
