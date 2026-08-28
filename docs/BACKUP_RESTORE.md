# Backup & Restore

## What is backed up (the bundle)
`scripts/backup_studio.ps1` creates `D:\CongThang_AI_Avatar\backups\studio_backup_<stamp>\` containing:
- `studio.db` — via the **SQLite online backup API** (`sqlite3.Connection.backup()`), transaction-safe on the live WAL database. NOT a blind file copy.
- `render_truth.json` — locked production config.
- `.env` — ElevenLabs API key (SECRET — the bundle is as sensitive as the original .env).
- `lineage.json` — list of prepared avatar dirs (artifacts) + raw source filenames (lineage, not the 35 GB binaries).
- `backup_report.json` — manifest of the bundle (paths, sha256, sizes).

## What is NOT backed up (back up separately)
- `data/avatars/` (35 GB prepared avatar binaries) and `data/input/avatar_sources/` (raw videos) — file-copy these to D: periodically (see below). They are irreplaceable / expensive to reconstruct.
- Render outputs on D: (regenerable).
- Python env / models (reinstallable from requirements-handover.lock + MODEL_MANIFEST.md).

## Backup command
```
scripts\backup_studio.ps1
:: or with a custom destination:
scripts\backup_studio.ps1 E:\backups
```
Default destination: `D:\CongThang_AI_Avatar\backups`.

## File backup of avatars + raw sources (do periodically)
```
robocopy C:\CongThang_AI_Avatar\AI_avatar\data\avatars D:\CongThang_AI_Avatar\backup_avatars /MIR
robocopy C:\CongThang_AI_Avatar\AI_avatar\data\input\avatar_sources D:\CongThang_AI_Avatar\backup_raw_sources /MIR
```
(35 GB — run when avatar set changes or before risky maintenance.)

## Restore (DB) — PROVEN_REAL drill
1. **Stop Studio.**
2. Copy `studio.db` from a backup bundle to `data\studio_runtime\studio.db` (overwrite).
3. Also restore `.env` and `render_truth.json` from the bundle if needed.
4. Start Studio → Trạng thái hệ thống should be SẴN SÀNG; Lịch sử render shows the restored jobs.
- Drill evidence (2026-08-28): restored DB opened in <0.01s, `PRAGMA integrity_check`=ok, jobs=21 avatars=19 — matched production. Isolated temp location, production untouched.

## Restore (avatars)
```
robocopy D:\CongThang_AI_Avatar\backup_avatars C:\CongThang_AI_Avatar\AI_avatar\data\avatars /MIR
```
(File restore is documented but NOT yet drilled — see R11. Run a one-time drill before relying on it.)

## Verify a restore
```
python scripts/preflight.py --detail
python system_status.py
```
Expect: DB integrity=ok, Production Truth VALID, Ready YES, avatar/library counts match.

## Frequency / retention (recommendation, justify to your own usage)
- DB + .env + config: **before any risky change** and at least **weekly** (small, fast).
- Avatars + raw sources: when the avatar set changes or **monthly** (35 GB).
- Retention: keep the last 4 weekly DB bundles + the last 2 monthly avatar backups. Adjust to your own change cadence — the point is never to lose the only copy of an irreplaceable prepared avatar.