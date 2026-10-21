# Backup & Restore

## What is backed up (the bundle)
`scripts/backup_studio.ps1` creates `D:\CongThang_AI_Avatar\backups\studio_backup_<stamp>\` containing:
- `studio.db` — via the **SQLite online backup API** (`sqlite3.Connection.backup()`), transaction-safe on the live WAL database. NOT a blind file copy.
- `render_truth.json` — locked production config.
- `.env` — ElevenLabs API key (SECRET — the bundle is as sensitive as the original .env).
- `lineage.json` — list of prepared avatar dirs (artifacts) + raw source filenames (lineage, not the 35 GB binaries).
- `backup_report.json` — manifest of the bundle (paths, sha256, sizes).

## What is NOT backed up (back up separately)
- `data/avatars/` (35 GB prepared avatar binaries) and `data/input/avatar_sources/` (raw videos) — file-copy these to D: periodically using `scripts/backup_avatars.py` (see below). They are irreplaceable / expensive to reconstruct.
- Render outputs on D: (regenerable).
- Python env / models (reinstallable from requirements-handover.lock + MODEL_MANIFEST.md).

## Prepared-Avatar backup (V1.4.1)
`scripts/backup_avatars.py` copies prepared avatar folders (structure + images + mask + coords + latents) and writes a per-file SHA-256 manifest so a receiving engineer can verify completeness/corruption.
```
:: representative (fast):
scripts\backup_avatars.py --avatars doTrang_closeup,mc_hamai_mid --dest D:\CongThang_AI_Avatar\backup_avatars
:: all ~35 GB (slow; run when avatar set changes):
scripts\backup_avatars.py --all --dest D:\CongThang_AI_Avatar\backup_avatars
:: manifest only (no copy):
scripts\backup_avatars.py --all --manifest-only --dest D:\...\backup_avatars
```
Output: `<dest>\<avatar_id>\…` + `avatar_manifest.json` (per-file size + sha256).

## Prepared-Avatar restore (PROVEN_REAL drill, V1.4.1)
1. Copy `<dest>\<avatar_id>` back to `data\avatars\<avatar_id>` (robocopy/copytree).
2. Verify against `avatar_manifest.json` (recompute sha256 per file — 0 mismatches expected).
3. Confirm recognized: `python -c "import sys;sys.path.insert(0,'.');from studio import avatar_service;print(avatar_service._check_ready(r'data\avatars\<id>'))"` → True.
- Drill evidence (2026-08-28): doTrang_closeup + mc_hamai_mid restored to an isolated location, 1480 files, 0 checksum mismatches, both `_check_ready`=True; a short render from the restored copy produced a valid 1080×1920 25fps MP4. Production avatars untouched; test artifacts cleaned up. **REPRESENTATIVE_RESTORE_PROVEN. FULL_35GB_COPY_NOT_EXECUTED** (procedure above; run once before relying on it).

## Backup retention (V1.4.1)
`scripts/backup_studio.py --retain N` (default 14) prunes all but the N most recent DB bundles after each backup. DB bundles are tiny; 14 is plenty.

## Optional scheduled backup (V1.4.1)
`AI_Avatar_Studio_Setup_Backup.bat` (runs `scripts/setup_backup_schedule.py`):
```
:: install (daily 03:17 DB backup task):
AI_Avatar_Studio_Setup_Backup.bat install
:: verify:
AI_Avatar_Studio_Setup_Backup.bat verify
:: remove:
AI_Avatar_Studio_Setup_Backup.bat remove
```
Explicit operator action only — never auto-registers on install. No secrets printed.

## Frequency / retention (separated, V1.4.1)
- **DB + .env + config**: before any risky change + at least weekly (tiny, fast). Retain last 14 daily bundles.
- **Prepared avatars + raw sources (35 GB)**: when the avatar set changes or monthly. Retain last 2 monthly copies. These change rarely and are large — different cadence from DB.

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