# Human QA Delivery Protocol — Windows / Local Checkpoint

Status: **mandatory project operating rule**. Read with `AGENTS.md`.

## Definition of done

A machine-specific test is ready to request only when the agent has prepared a **tested, single-entry, bounded deployment-and-run path**. The agent, not the user, owns setup and evidence collection. Automation PASS does not imply HUMAN PASS.

### Required preflight

- [ ] Confirm exact commit/PR and successful relevant CI; identify the exact artifact and retain its immutable run/ID.
- [ ] Verify the artifact contains the declared executable, expected model(s), SHA-256 and a runnable invocation; test extraction and a smoke run in CI.
- [ ] Check existing `tools/qa-portable.ps1`, cached runtime, models and the fixed Checkpoint directory before making anything new.
- [ ] Prepare a single invocation that downloads and verifies only what is necessary; prefer a tested incremental overlay and reuse installed EXE/runtime/model assets.
- [ ] All download, temp, staging, output and log paths must be explicitly under the configured data-drive workspace on the user's workstation, currently G:, with no new default writes to C:/system TEMP.
- [ ] Stage safely: no mutation of original dataset; no deletion outside a dedicated/sentinel-guarded managed folder; handle stale/failed partial downloads and reruns deterministically.
- [ ] One invocation must cover launch, watchdog/timeout, exit code, and result capture; failure should preserve the last stage and one named log/report.
- [ ] For a GPU probe, disable or explicitly measure all fallback routes and record actual execution evidence; no false GPU PASS from CPU recovery.
- [ ] State actual human QA debt and scope precisely; CI/lab-machine success never changes HUMAN UNVERIFIED.

### User-facing test handoff

Give **one** copyable PowerShell command, identify the target directory and the **single** result/report the user should return. Do not instruct the user to enter GitHub Actions, download an Artifact manually, unpack ZIP(s), move files, choose versions/branches, install Python/Conda/CUDA or inspect multiple logs. Do not require the user to find the run ID or artifact name manually.

For urgent tests, a low-cost interactive invocation is acceptable only if it fully encapsulates the same preparation and logging. If the automation is missing, fix or build it first; otherwise report the blocker and mark HUMAN UNVERIFIED, not “ready for QA.”

### When work can continue without human testing

Continue with bounded, reversible changes after relevant automation PASS. Batch human QA according to the existing risk-based rules. A risky startup/data-loss/destructive change requires prompt QA, **but not a lower-quality manual deployment**.

### Current reusable paths

- Project QA runtime/overlay entry: `tools/qa-portable.ps1` (managed root defaults to `G:\\FaceLoRA-QA` if G: exists).
- DirectML research checkpoint already on target: `G:\\ComfyUI-aki\\FaceLoRA-DirectML-GPU-Debug\\checkpoint`.
- An isolated diagnostic may use its own bounded wrapper, but it should stage into the existing checkpoint and must not replace stable product runtime.
- Avoid a full Portable refresh unless its runtime compatibility manifest proves necessary; keep the model cache.

### Proof required before declaring delivery complete

Record the one-command launcher path/invocation in the associated PR, the CI run that validated deployment and packaging, model/artifact SHA when applicable, the expected single report path, and any prerequisites the launcher verifies automatically. A PR checklist alone is not proof that the launcher works.
