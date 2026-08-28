# DISASTER RECOVERY — QUICK CARD (emergency)

For operators under pressure. Each case: (1) run Preflight, (2) exact next action, (3) where to find detail.

**Always first:** `AI_Avatar_Studio_Preflight.bat` — it tells you what's wrong.

---

## STUDIO KHÔNG MỔ
1. Preflight — check Python / port 8077 / DB.
2. **Fix:** nếu port bận → đã có Studio đang chạy, mở http://127.0.0.1:8077. Nếu thiếu Python/DB → xem TROUBLESHOOTING.md "Studio không mở".
3. Chi tiết: `docs/TROUBLESHOOTING.md`, `docs/START_HERE.md`.

## GPU KHÔNG NHẬN
1. Preflight — mục GPU.
2. **Fix:** `nvidia-smi` trong cmd. Nếu lỗi → cài lại driver NVIDIA. Studio cần GPU để render/prepare.
3. Chi tiết: TROUBLESHOOTING.md "GPU missing / CUDA OOM".

## ELEVENLABS LỖI
1. Preflight — mục "ElevenLabs configured".
2. **Fix:** key sai/hết quota → UI Cài đặt dán key hợp lệ; Voice ID sai → dùng "Kiểm tra giọng". Hệ thống KHÔNG tự đổi giọng — phải sửa tay.
3. Chi tiết: TROUBLESHOOTING.md "ElevenLabs invalid key / quota / Voice ID".

## Ổ ĐĨA ĐẦY
1. Preflight — mục "Render storage" + "Disk (repo)".
2. **Fix:** xóa render cũ trên D: (Lịch sử render → xóa file không cần); chạy `AI_Avatar_Studio_Maintenance.bat` → mục 6 (Clean Old Logs). Render đi D: (800GB free).
3. Chi tiết: OPERATIONS_RUNBOOK.md "Disk hygiene", BACKUP_RESTORE.md.

## DATABASE LỖI
1. Preflight — mục Database (integrity).
2. **Fix:** DB hỏng/khóa → dừng Studio → khôi phục từ backup: `scripts/backup_studio.ps1` đã có bundle ở `D:\CongThang_AI_Avatar\backups\` → copy `studio.db` vào `data/studio_runtime/`.
3. Chi tiết: BACKUP_RESTORE.md "Restore (DB)".

## RENDER BỊ TREO
1. UI Lịch sử render — job stuck "Đang render" lâu.
2. **Fix:** Hủy job (nút Hủy) rồi Thử lại. Nếu Studio restart rồi job vẫn treo → V1.4.1 tự đánh dấu "failed" lúc khởi động; bấm Thử lại. Log chi tiết: `data/studio_runtime/logs/<job_id>.log`.
3. Chi tiết: TROUBLESHOOTING.md "Render stuck / failed".

## MẤT LINK CLOUDFLARE
1. Preflight — mục "Cloudflare Quick Tunnel" (cảnh báo).
2. **Fix:** chạy lại `AI_Avatar_Studio_Share.bat` (link mới). Local Studio + render đang chạy KHÔNG bị ảnh hưởng. Dùng xong → `AI_Avatar_Studio_Stop_Sharing.bat`.
3. Chi tiết: TROUBLESHOOTING.md "Cloudflare link unavailable".

## MÁY VỪA RESTART
1. Chạy Preflight. 2. Chạy `AI_Avatar_Studio.bat`. 3. Kiểm tra Lịch sử render — các job đang chạy khi mất điện sẽ hiện "failed" (Studio khởi động lại trong khi job đang chạy); bấm Thử lại nếu cần. 4. Nếu có share → chạy lại Share bat. 5. Kiểm tra Trạng thái hệ thống = SẴN SÀNG.
- Chi tiết: OPERATIONS_RUNBOOK.md "Safe shutdown" + ROLLBACK_RUNBOOK.md.

---
**Sao lưu nhanh:** `AI_Avatar_Studio_Maintenance.bat` → 2 (Backup Database).
**Kiểm tra sẵn sàng:** `AI_Avatar_Studio_Preflight.bat`.