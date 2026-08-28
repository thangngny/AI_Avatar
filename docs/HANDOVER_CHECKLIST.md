# Handover Checklist

Use at actual technology transfer. Recipient should be able to perform each item using only the documentation (teach-back).

## Repository & release
- [ ] Repository accessible at `C:\CongThang_AI_Avatar\AI_avatar`
- [ ] Known-good git tag documented (`ai-avatar-studio-ui-v1.4.0` / `v1.3.1`)
- [ ] HDSD delivered (`docs/HDSD_*` + UI screenshots)
- [ ] START_HERE.md delivered
- [ ] HANDOVER_RELEASE_MANIFEST.json delivered

## Environment
- [ ] Python runtime confirmed (torch env, Python 3.10.11)
- [ ] Models present + checksums valid (MODEL_MANIFEST.md)
- [ ] GPU test completed (2× RTX 3090)
- [ ] FFmpeg test completed
- [ ] `requirements-handover.lock` present
- [ ] `STUDIO_TORCH_PYTHON` override understood (runtime.py)

## Startup & readiness
- [ ] `AI_Avatar_Studio_Preflight.bat` → SẴN SÀNG
- [ ] `AI_Avatar_Studio.bat` startup completed
- [ ] Database integrity checked (preflight: integrity=ok)

## Backup & recovery
- [ ] Backup created (`scripts/backup_studio.ps1`)
- [ ] Restore drill completed (PROVEN_REAL)
- [ ] File backup of `data/avatars` + raw sources understood

## TTS
- [ ] ElevenLabs configured (.env key)
- [ ] ElevenLabs quota workflow understood (no silent fallback/switch)
- [ ] Edge TTS tested (free mouth test)

## Function
- [ ] Create Avatar tested (or an existing avatar used)
- [ ] 10s mouth test completed (Edge TTS, free)
- [ ] Production render completed (ElevenLabs)
- [ ] Output playback verified (Xem video)

## Sharing
- [ ] Cloudflare sharing demonstrated (Share bat)
- [ ] Link-only access risk explained (full control to URL holder; trusted only)
- [ ] Stop Sharing demonstrated

## Operations & ops hygiene
- [ ] Disk cleanup explained (C: ~80 GB free; renders on D:)
- [ ] Logs location explained (`data/studio_runtime/logs/`, `diagnostics/`)
- [ ] Troubleshooting guide reviewed
- [ ] Rollback demonstrated (ROLLBACK_RUNBOOK.md)

## Production truth
- [ ] Locked truth explained (MuseTalk v1.5, gain 1.5, ctx 0, offset -3, 25fps, 1080×1920, CUDA Graph/WOLA/Coverage Guard ON)
- [ ] `config/render_truth.json` must not be changed without separate approval

## Teach-back (recipient performs without developer help)
- [ ] 1. Start system (preflight + launcher)
- [ ] 2. Preflight
- [ ] 3. Select Avatar
- [ ] 4. Edge TTS mouth test
- [ ] 5. ElevenLabs short production test
- [ ] 6. Locate output (Lịch sử render + D: drive)
- [ ] 7. Create/share Cloudflare link
- [ ] 8. Stop sharing
- [ ] 9. Create backup
- [ ] 10. Identify where to look if a render fails (History error + per-job log)

Any unchecked item that needs undocumented developer knowledge = HANDOVER GAP.