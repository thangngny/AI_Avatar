# START HERE — AI Avatar Studio

Read this first. This is the operator's quick orientation.

## What it is
AI Avatar Studio turns a **prepared AI Avatar** + a **script** + a **voice** into a talking-head video (1080×1920, 25 fps) using the locked MuseTalk v1.5 lipsync pipeline. It runs locally on a Windows PC with 2× RTX 3090.

## Where things are
- Repo: `C:\CongThang_AI_Avatar\AI_avatar`
- Renders go to: `D:\CongThang_AI_Avatar\renders\studio\`
- Avatars (35 GB): `data\avatars\`
- Database: `data\studio_runtime\studio.db`
- API key (ElevenLabs): `.env` (secret, gitignored)

## Start the system
1. Double-click `AI_Avatar_Studio_Preflight.bat` → confirms SẴN SÀNG (read-only, no render).
2. Double-click `AI_Avatar_Studio.bat` → opens http://127.0.0.1:8077.

## Stop the system
Close the Studio console window (the `run_studio.py` process). Running renders are killed when Studio stops — let them finish first if you need the output.

## Make a video (existing Avatar)
1. Home → **Tạo video từ Avatar có sẵn**.
2. Step 1: pick an Avatar (TỐT = good quality). *Tiếp tục*.
3. Step 2: type/paste the script. *Tiếp tục*.
4. Step 3: choose **ELEVENLABS** (production) or **TEST MIỄN PHÍ** (Edge TTS, free, no quota). *Tiếp tục*.
5. Step 4 (optional): **TEST KHẨU HÌNH** to preview mouth motion for free.
6. Step 5: **TẠO VIDEO**. Watch the footer **HÀNG ĐỢI RENDER** (click it for the queue drawer).
7. Output appears in **Lịch sử render** and on disk under `D:\CongThang_AI_Avatar\renders\studio\`.

## Create a new Avatar
1. Home → **Tạo AI Avatar mới**.
2. Step 1: watch the sample video. Step 2: read the source requirements (30-60s, 9:16, face large, not speaking, …). Step 3: upload a video.
3. Step 4: review quality (TỐT / CẦN LƯU Ý) + confirm mouth state.
4. Step 5: **TẠO AVATAR** (~20-30 min). It then appears in Thư viện Avatar.

## What needs Internet
- ElevenLabs (production voice) — yes
- Edge TTS (free test voice) — yes
- Cloudflare sharing (remote access) — yes
- Rendering with an already-prepared avatar + already-generated audio — no (local GPU)

## What needs GPU
- Rendering and Create-Avatar preparation. The studio UI, library, history, settings, and TTS voice check work without GPU.

## Where to get help when something fails
- `OPERATIONS_RUNBOOK.md` — daily operations.
- `TROUBLESHOOTING.md` — symptom → check → fix.
- `BACKUP_RESTORE.md` — backup/restore.
- `ROLLBACK_RUNBOOK.md` — return to a known-good release.
- `DISASTER_RECOVERY_QUICK_CARD.md` — emergency one-liners.
- Run `AI_Avatar_Studio_Preflight.bat` any time — it tells you what's wrong.
- `AI_Avatar_Studio_Maintenance.bat` — one menu for preflight / backup / verify / cleanup.

## Golden rules
- **Production truth is locked.** Never change MuseTalk/gain/ctx/offset/FPS/resolution (config/render_truth.json).
- **ElevenLabs never silently switches voice.** A bad Voice ID fails closed — you must fix it.
- **Good source ≠ perfect output.** Always do a final visual review of important renders (see output acceptance checklist).
- **Only create Avatars/voices from material you are authorized to use.** This system is not a rights validator.