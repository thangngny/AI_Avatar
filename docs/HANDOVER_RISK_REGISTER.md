# Risk Register (human-readable)

Machine-readable: `diagnostics/handover_risk_register.json`.
Severity = Impact(1-5) × Likelihood(1-5). LOW 1-4 · MEDIUM 5-9 · HIGH 10-15 · CRITICAL 16-25.

## Summary
- CRITICAL: 0 · HIGH: 3 · MEDIUM: 13 · LOW: 3
- MITIGATED: 5 · ACCEPTED: 8 · OPEN: 8

## TOP RISKS (HIGH)

### R01 — Cloudflare Quick Tunnel link-only full access  (score 12, ACCEPTED)
- Impact 4 / Likelihood 3 / Detectability EASY
- Anyone with the active share URL gets full Studio control (use ElevenLabs quota, create avatars, render). URL is temporary/random. API key itself is NOT leaked (server-side only).
- Evidence: PROVEN_STATIC — share_auth.py + Share launcher; link-only by design (V1.2.2).
- Mitigation: only share with trusted collaborators; Stop Sharing when done.
- Recovery: `AI_Avatar_Studio_Stop_Sharing.bat` kills the tunnel immediately.
- Escalation: migrate to Named Cloudflare Tunnel + Cloudflare Access + stable hostname before untrusted access.

### R02 — Automated mouth-state detector unreliable  (score 12, ACCEPTED)
- Impact 3 / Likelihood 4 / Detectability EASY
- Cannot reliably distinguish talking vs neutral in the observed overlap range.
- Evidence: PROVEN_STATIC — validator.py SOURCE_MOUTH_STATE returns UNKNOWN for borderline; UI requires manual confirmation.
- Mitigation: manual mouth-state confirmation in Create Avatar; raw auto evidence stored separately, never overwrites user choice.
- Do NOT "fix" by inventing a threshold.

### R03 — Knowledge concentration in one developer  (score 12, MITIGATED)
- Impact 4 / Likelihood 3 / Detectability EASY
- Evidence: this handover package + proven backup/restore/preflight drills.
- Mitigation: START_HERE, OPERATIONS_RUNBOOK, TROUBLESHOOTING, BACKUP_RESTORE, ROLLBACK_RUNBOOK, HANDOVER_CHECKLIST.

## MEDIUM (13)
- **R04** RENDERS_DIR hardcoded to `D:\CongThang_AI_Avatar\renders` (config.py:27), not env-overridable. OPEN. Recovery: edit config.py.
- **R05** Torch env lives inside the experimental LatentSync repo. MITIGATED (STUDIO_TORCH_PYTHON env override; no code-level coupling). Recovery: set env var / rebuild env.
- **R06** No auto-reconciliation of in-flight jobs on Studio restart (crash mid-render → job stuck "rendering"). OPEN. Recovery: cancel/retry stuck job in History.
- **R07** Main launcher has no port-busy handling → raw traceback if 8077 occupied. OPEN. Mitigation: run Preflight first.
- **R08** No log rotation (per-job logs + diagnostics accumulate). OPEN. Recovery: periodic cleanup.
- **R09** Master audio cache never evicted. OPEN. Recovery: delete temp/master/*.wav.
- **R10** Prepared avatars 35 GB on C: (~80 GB free), expensive to reconstruct, no automated file backup. ACCEPTED. Mitigation: periodic file-copy to D:.
- **R11** DB restore PROVEN_REAL, but 35 GB avatar file-restore not drilled. OPEN. Recovery: robocopy data/avatars back.
- **R12** No requirements lock committed (now created: requirements-handover.lock). MITIGATED.
- **R13** SQLite backup not scheduled. OPEN. Mitigation: schedule backup_studio.ps1.
- **R14** Dual-GPU historical hard-crash. MITIGATED (per-job CUDA_VISIBLE_DEVICES isolation, render_service.py:508).
- **R18** C: ~80 GB free declining. MITIGATED (preflight disk warning).
- **R19** Double-click submission → duplicate render (two unique jobs). ACCEPTED. Mitigation: UI disables button after click; cancel duplicate.
- **R20** Good source ≠ guaranteed perfect output. ACCEPTED. Mitigation: output acceptance checklist + final manual review.

## LOW (3)
- **R15** verify.py ffprobe fallback broken (imageio_ffmpeg.get_ffprobe_exe absent); degrades to size-only if ffprobe missing. OPEN. Mitigation: keep ffprobe on PATH.
- **R16** Upload has no server-side extension allowlist (analyzer rejects non-video; path confined). ACCEPTED.
- **R17** Tracked secrets. MITIGATED (only .env.example tracked; .env gitignored; no secret values in repo).