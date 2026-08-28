# Troubleshooting — symptom → check → fix → escalate

### Studio không mở (page won't load)
- CHECK: is Studio running? `netstat -ano | findstr :8077`.
- FIX: run `AI_Avatar_Studio.bat`. If port busy, an instance is already running — open http://127.0.0.1:8077.
- ESCALATE IF: preflight reports BLOCKED (missing model/db/python).

### Port 8077 busy / "Address already in use"
- CHECK: another `run_studio.py` is running.
- FIX: reuse it, or kill it (`Stop-Process -Name python` carefully) then restart.
- NOTE: the main launcher does not yet give a clean "already running" message (R07).

### GPU missing / "0 GPUs"
- CHECK: `nvidia-smi`. Driver present?
- FIX: reinstall/restart NVIDIA driver. Studio falls back to a single CPU slot only if nvidia-smi returns nothing — rendering will likely fail without GPU.
- ESCALATE IF: nvidia-smi works but Studio shows 0 — check `studio/gpu_service.detect()`.

### CUDA OOM / render crash
- SYMPTOM: job → Lỗi, error mentions CUDA/out of memory or renderer exit code.
- CHECK: History → job error line; per-job log `data/studio_runtime/logs/<job_id>.log`.
- FIX: the failed job releases its GPU automatically; retry (History → Thử lại). Avoid running two heavy full renders + Create-Avatar prepare at once on the same GPU.
- NOTE: a Studio crash mid-render can leave a job stuck "rendering" (R06) — cancel it from History.

### Model missing
- SYMPTOM: renderer fails fast mentioning a .pth/.bin path; preflight shows ✗ Models.
- FIX: restore the missing model (see MODEL_MANIFEST.md recovery sources) and re-run preflight.

### FFmpeg missing
- SYMPTOM: render fails at mux step; verify can't inspect output.
- FIX: install ffmpeg/ffprobe on PATH (gyan.dev build). The renderer needs ffmpeg for muxing.
- NOTE: if ffprobe is missing, post-render verify degrades to size-only (R15) — a corrupt-with-streams file could pass, so keep ffprobe installed.

### ElevenLabs invalid key
- SYMPTOM: TTS error "ElevenLabs API key not configured" or 401/403.
- CHECK: `.env` has a valid `ELEVENLABS_API_KEY`. Settings page → Cài đặt.
- FIX: paste a valid key in Cài đặt → Lưu. Key lives only in .env (never in DB).

### ElevenLabs quota exhausted
- SYMPTOM: 429 / "quota" / character limit reached.
- FIX: wait for monthly reset or upgrade plan. Use **TEST MIỄN PHÍ** (Edge TTS) for non-production checks. The system NEVER silently falls back or switches voice.

### Voice ID invalid
- SYMPTOM: "Voice ID invalid or unavailable (404)" — fail-closed (PROVEN_REAL).
- FIX: use a valid ElevenLabs Voice ID; click **Kiểm tra giọng** to verify first.

### Edge TTS unavailable
- SYMPTOM: "Giọng test miễn phí (Edge TTS) hiện không khả dụng."
- FIX: check Internet / Microsoft service status. No ElevenLabs fallback (by design) — wait or use ElevenLabs.

### Upload fails
- SYMPTOM: chunk error or "missing chunks".
- FIX: re-upload. Large files via Cloudflare are slower (~100 MB request cap → chunked); upload from the host machine is faster.
- Zero-byte / non-video files are accepted to staging but rejected at analyze.

### Render stuck (no progress)
- SYMPTOM: job stays Đang render, no % change.
- CHECK: a watchdog kills a truly hung renderer after 300s of no stdout (or 4h hard cap). If it's still progressing slowly, wait.
- FIX: if truly stuck, History → Hủy, then Thử lại.

### Render failed (exit code)
- CHECK: job error + `data/studio_runtime/logs/<job_id>.log` tail.
- FIX: retry; if repeated, check GPU/disk/models.

### Output has no audio
- CHECK: History → ▶ Xem video. If silent, the master audio generation may have failed.
- FIX: verify voice config (ElevenLabs key / Voice ID, or Edge TTS online) and re-render. Post-render verify rejects missing audio stream.

### Disk low
- SYMPTOM: preflight warns "chỉ còn X GB".
- FIX: delete old renders on D:, old logs in diagnostics/ and data/studio_runtime/logs/, old master WAVs in data/studio_runtime/temp/master/. Move data/avatars to D: if C: is critical.

### Database locked
- SYMPTOM: "database is locked" errors.
- CHECK: another Studio instance? WAL mode usually handles concurrency.
- FIX: ensure only one Studio runs. If corrupt: restore from backup (BACKUP_RESTORE.md).

### Cloudflare link unavailable
- SYMPTOM: share link doesn't open.
- CHECK: is cloudflared running? Internet up?
- FIX: re-run `AI_Avatar_Studio_Share.bat`. Local Studio + running renders are unaffected by tunnel issues.

### Sample video unavailable
- SYMPTOM: Create Avatar step 1 shows "Video mẫu chuẩn đang được cập nhật."
- NOTE: the current sample is a TEMPORARY best-existing source (honestly labeled). Use it as a reference only; the source requirements in step 2 are authoritative.

### Avatar incomplete
- SYMPTOM: card shows CHƯA HOÀN TẤT / disabled Chọn Avatar.
- CAUSE: prepare didn't finish or data missing.
- FIX: re-create the Avatar from its raw source (Create Avatar flow).