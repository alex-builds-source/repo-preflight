# API

`repo-preflight` is a CLI-first tool.

## Machine-readable interface

### Command
`repo-preflight check --json --path <repo> [--strict] [--no-gitleaks]`

### Output schema (v0.1.1)

```json
{
  "path": "/abs/path",
  "strict": true,
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
- `2`: failures present, or warnings when `--strict` is enabled
