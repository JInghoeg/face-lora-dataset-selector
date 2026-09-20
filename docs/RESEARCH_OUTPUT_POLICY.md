# Research Output Policy

Research artifacts must not default to the Windows system drive.

## Default location

Use a disposable output directory inside or beside the active project/worktree on the same drive as the project, for example:

```
<project>/_research_output/
```

This directory is local-only and ignored by Git.

## Applies to

- benchmark outputs
- contact sheets
- temporary crops
- model evaluation results
- downloaded research-only model weights when practical
- logs
- intermediate JSON/CSV
- temporary virtual environments created only for research

## Rules

- Do not default to `%LOCALAPPDATA%`, `%TEMP%`, Desktop, Documents, or another C: location for large/repeated research artifacts.
- Prefer relative paths derived from the active repository/worktree so moving the project also moves its research workspace.
- Keep research outputs easy to delete as one directory.
- Production user data/cache policy is separate and must be decided explicitly.
- C: may be used only when explicitly requested or required by a third-party runtime that cannot be redirected.
