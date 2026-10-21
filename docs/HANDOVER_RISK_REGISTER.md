# Risk Register (human-readable)

Machine-readable: `diagnostics/handover_risk_register.json`.
Severity = Impact(1-5) × Likelihood(1-5). LOW 1-4 · MEDIUM 5-9 · HIGH 10-15 · CRITICAL 16-25.

## Summary
- CRITICAL: 0 · HIGH: 3 · MEDIUM: 13 · LOW: 3
- MITIGATED: 9 · ACCEPTED: 8 · OPEN: 1
- Environment rebuild (R12): **FULLY_REPRODUCIBLE (PROVEN_REAL)** — fresh venv from system py310, deps from requirements-handover.lock + cu121 index, fresh-env locked render PASS, truth hash identical to existing env.

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
- **R04** RENDERS_DIR hardcoded to `D:\CongThang_AI_Avatar\renders`. **MITIGATED** — `STUDIO_RENDERS_DIR` env override (config.py) + `validate_renders_dir()` (existence/writable/free-space) + preflight "Render storage" block. Default unchanged (still D:).
- **R05** Torch env lives inside the experimental LatentSync repo. MITIGATED (STUDIO_TORCH_PYTHON env override; no code-level coupling). Recovery: set env var / rebuild env.
- **R06** No auto-reconciliation of in-flight jobs on Studio restart. **MITIGATED** — `render_service.start()` now calls `_reconcile_inflight_jobs()` on startup; transient jobs marked failed ("Studio đã khởi động lại trong khi job đang chạy"); GPU _BUSY fresh on restart. UNIT_TEST: TestReconcileInflight.
- **R07** Main launcher has no port-busy handling → raw traceback if 8077 occupied. OPEN. Mitigation: run Preflight first.
- **R08** No log rotation. **MITIGATED** — `scripts/cleanup.py` + `AI_Avatar_Studio_Cleanup.bat` path-scoped retention (logs 30d, master WAV 30d, uploads 1d), keeps active-job logs, never touches diagnostics/renders/avatars. Maintenance tool menu 6/7.
- **R09** Master audio cache never evicted. OPEN (low). Mitigation: cleanup tool includes temp/master/*.wav (30d).
- **R10** Prepared avatars 35 GB on C: (~80 GB free), expensive to reconstruct, no automated file backup. ACCEPTED. Mitigation: `scripts/backup_avatars.py` + sha256 manifest (procedure documented; representative restore PROVEN_REAL).
- **R11** DB restore PROVEN_REAL; 35 GB avatar file-restore. **MITIGATED** — representative avatar backup+restore PROVEN_REAL (1480 files, 0 checksum mismatches, `_check_ready`=True, render from restored copy PASS). FULL_35GB_COPY_NOT_EXECUTED (procedure documented).
- **R12** No requirements lock / env reproducibility. **MITIGATED** — requirements-handover.lock + fresh-env rebuild FULLY_REPRODUCIBLE (PROVEN_REAL).
- **R13** SQLite backup not scheduled. **MITIGATED** — `backup_studio.py --retain N` + optional `AI_Avatar_Studio_Setup_Backup.bat` Task Scheduler installer (explicit operator action).
- **R14** Dual-GPU historical hard-crash. MITIGATED (per-job CUDA_VISIBLE_DEVICES isolation, render_service.py:508).
- **R18** C: ~80 GB free declining. MITIGATED (preflight disk warning).
- **R19** Double-click submission → duplicate render (two unique jobs). ACCEPTED. Mitigation: UI disables button after click; cancel duplicate.
- **R20** Good source ≠ guaranteed perfect output. ACCEPTED. Mitigation: output acceptance checklist + final manual review.

## LOW (3)
- **R15** verify.py ffprobe fallback broken. **MITIGATED** — `_ffprobe` now resolves PATH → FFPROBE_PATH → sibling of imageio ffmpeg; when unavailable returns honest `ok=False` (no size-based fabrication). `ffprobe_resolved()` added. UNIT_TEST: TestVerifyFallback.
- **R16** Upload has no server-side extension allowlist (analyzer rejects non-video; path confined). ACCEPTED.
- **R17** Tracked secrets. MITIGATED (only .env.example tracked; .env gitignored; no secret values in repo).