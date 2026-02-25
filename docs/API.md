# API

`repo-preflight` is a CLI-first tool.

## Machine-readable interface

### Commands
- `repo-preflight check --json --path <repo> [--profile <quick|full|ci>] [--rule-pack <name>] [--strict|--no-strict] [--gitleaks|--no-gitleaks] [--max-file-kib <int>] [--max-history-kib <int>] [--history-object-limit <int>] [--max-diff-files <int>] [--max-diff-changed-lines <int>] [--diff-mode <manual|pr>] [--pr-base-ref <ref>] [--diff-base <ref>] [--diff-target <ref>] [--config <path>] [--no-config]`
- `repo-preflight check --sarif ...` (SARIF 2.1.0 output)
- `repo-preflight check --compact ...` (compact CI log output)
- `repo-preflight policy-doc [--output <path>] ...` (render effective policy markdown)
- `repo-preflight policy-template --rule-pack <name> [--profile <quick|full|ci>] [--strict|--no-strict] [--output <path>]`
- `repo-preflight list-checks`
- `repo-preflight list-rule-packs`

### JSON output schema (v0.1.7)

```json
{
  "path": "/abs/path",
  "profile": "ci",
  "rule_pack": "oss-library",
  "strict": true,
  "config_path": "/abs/path/.repo-preflight.toml",
  "max_tracked_file_kib": 2048,
  "max_history_blob_kib": 2048,
  "history_object_limit": 10000,
  "max_diff_files": 200,
  "max_diff_changed_lines": 4000,
  "diff_mode": "pr",
  "pr_base_ref": "origin/main",
  "diff_base": "origin/main",
  "diff_target": "HEAD",
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

### SARIF output

- Schema: `2.1.0`
- Includes repo-preflight checks as SARIF rules
- Emits only non-pass results as SARIF findings
- Includes diff metadata in run properties

### Exit code behavior

- `0`: all checks pass
- `1`: warnings only in default mode
- `2`: failures present, or warnings when strict mode is enabled
