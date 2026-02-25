# API

`repo-preflight` is a CLI-first tool.

## Machine-readable interface

### Command
`repo-preflight check --json --path <repo>`

### Output schema (v0)

```json
{
  "path": "/abs/path",
  "summary": { "pass": 0, "warn": 0, "fail": 0 },
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
