# Operations Runbook — daily operations

## Start Studio
1. `AI_Avatar_Studio_Preflight.bat` → confirm SẴN SÀNG.
2. `AI_Avatar_Studio.bat` → http://127.0.0.1:8077 opens.
3. If port 8077 is busy, an existing Studio is already running — reuse it, or close it first.

## Check readiness
- Preflight (above), or in the UI: **Trạng thái hệ thống** → "HỆ THỐNG SẴN SÀNG" with ✓ AI Avatar / GPU / ElevenLabs / Edge TTS.
- Or `python system_status.py` → "Production Truth: VALID · Ready: YES".

## Normal production render (ElevenLabs)
Tạo video → pick Avatar → script → ELEVENLABS + Voice ID → (optional TEST) → TẠO VIDEO.
- Voice ID: paste from ElevenLabs; click **Kiểm tra giọng** to verify before rendering.
- Long scripts auto-split into parts; each part is a separate job.

## Free mouth test (no quota)
Tạo video → pick Avatar → step 3 choose **TEST MIỄN PHÍ** (Edge TTS) → step 4 **TEST KHẨU HÌNH**.
- Uses the standardized Vietnamese diagnostic script by default.
- Does NOT consume ElevenLabs quota. Good for comparing Avatar A vs B.

## Create an Avatar
Tạo AI Avatar mới → sample → requirements → upload → quality check → mouth confirm → TẠO AVATAR (~20-30 min). Monitor in Thư viện Avatar (incomplete → ready).

## Share a Cloudflare link (trusted collaborators only)
1. Studio must be running.
2. `AI_Avatar_Studio_Share.bat` → prints a `https://<random>.trycloudflare.com` link.
3. Send the link to the trusted collaborator. They get FULL Studio access (link-only).
4. **Stop sharing:** `AI_Avatar_Studio_Stop_Sharing.bat`. The link dies immediately.
- Quick Tunnel is for trusted testing only, NOT a production deployment. Anyone with the URL can use ElevenLabs quota / create avatars.

## Find outputs
- UI: **Lịch sử render** → ▶ Xem video / Tải video.
- Disk: `D:\CongThang_AI_Avatar\renders\studio\<timestamp>_<kind>_<avatar>_<label>_<uuid>.mp4`.
- On localhost only: a "Mở thư mục" button opens the render folder.

## Check the queue
- Footer bar **HÀNG ĐỢI RENDER** shows live state. Click it for the queue drawer.
- States: Đang chờ · Đang render · Hoàn tất · Lỗi.

## Check history
- **Lịch sử render** — filter Tất cả / Hoàn tất / Đang chạy / Lỗi-Đã hủy. TEST vs VIDEO HOÀN CHỈNH badges.

## Safe shutdown
1. Let running renders finish (or cancel them from History if you must).
2. Close the Studio console window.
3. If sharing: run Stop Sharing first.

## After a PC restart / crash (V1.4.1)
1. `AI_Avatar_Studio_Preflight.bat` → confirm SẴN SÀNG.
2. `AI_Avatar_Studio.bat`.
3. **Lịch sử render** — any job that was running when power was lost now shows "failed" with "Studio đã khởi động lại trong khi job đang chạy." (V1.4.1 auto-reconciliation on startup). Click **Thử lại** if you still want it. Completed jobs are untouched.
4. If you were sharing, re-run `AI_Avatar_Studio_Share.bat` (new link).
5. Check Trạng thái hệ thống = SẴN SÀNG.

## Maintenance tool (V1.4.1)
`AI_Avatar_Studio_Maintenance.bat` — one menu:
1 Preflight · 2 Backup Database · 3 Verify Database · 4 Verify Models · 5 Check Disk · 6 Clean Old Logs (confirm) · 7 Clean Stale Uploads (confirm) · 8 Verify Prepared Avatars · 9 Show Backup Status · 10 Exit. Destructive cleanup asks confirmation. Also: `AI_Avatar_Studio_Cleanup.bat` (dry-run by default).

## Render storage (V1.4.1)
Renders go to `STUDIO_RENDERS_DIR` (default `D:\CongThang_AI_Avatar\renders`). To relocate (e.g. another machine), set `STUDIO_RENDERS_DIR=<path>` before starting Studio. Preflight shows the resolved path + free space + writability.

## Backup (do before any risky change)
`scripts/backup_studio.ps1` → bundle under `D:\CongThang_AI_Avatar\backups\` (DB via SQLite online backup API + .env + render_truth.json + lineage manifest). See BACKUP_RESTORE.md. The 35 GB avatar binaries are NOT in the bundle — back up `data\avatars` separately.

## Disk hygiene
- Renders on D: (800 GB free) — healthy.
- C: only ~80 GB free; avatars (35 GB) + models (8.85 GB) live here. Periodically delete old renders you no longer need and old `diagnostics/*.log` / `data/studio_runtime/logs/*.log`.