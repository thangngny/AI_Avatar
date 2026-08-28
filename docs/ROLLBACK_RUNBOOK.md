# Rollback Runbook

How to return to a known-good release if an update breaks the system.

## Known-good reference (current stable)
- Code tag: `ai-avatar-studio-ui-v1.3.1` (HEAD `598ee7f`)
- After this audit: `ai-avatar-studio-ui-v1.4.0`
- Production config: `config/render_truth.json` (do NOT roll back the truth — it is locked)
- Model manifest: `docs/MODEL_MANIFEST.md` + `diagnostics/handover/model_manifest.json`
- Dependency snapshot: `requirements-handover.lock` + `diagnostics/handover/pip_freeze_torch.txt`
- DB backup: latest bundle under `D:\CongThang_AI_Avatar\backups\studio_backup_<stamp>\`

## Rollback procedure
1. **Stop new jobs.** In Studio, do not submit new renders. Let running jobs finish or cancel them.
2. **Protect current data.** Run `scripts/backup_studio.ps1` (creates a fresh DB + config backup).
3. **Stop Studio.** Close the Studio window / kill the `run_studio.py` process.
4. **Checkout last known-good tag.**
   ```
   cd C:\CongThang_AI_Avatar\AI_avatar
   git fetch --tags
   git checkout ai-avatar-studio-ui-v1.3.1      # or v1.4.0
   ```
   (Do NOT force-push or move tags. Work on a branch if you want to keep the broken state: `git switch -c broken-<date>` first.)
5. **Restore compatible env/config if needed.** If the breakage was a dependency upgrade, recreate the env from `requirements-handover.lock` or re-point `STUDIO_TORCH_PYTHON` to the last working interpreter. The production truth (`config/render_truth.json`) is NOT rolled back unless it itself is the regressor.
6. **Run preflight.** `AI_Avatar_Studio_Preflight.bat` → expect SẴN SÀNG / SẴN SÀNG (cảnh báo).
7. **Run one short real render.** Mouth test (Edge TTS, free) → confirm output plays.
8. **Resume.** Start Studio normally (`AI_Avatar_Studio.bat`).

## If the database is the regressor
- Stop Studio. Restore `studio.db` from a backup bundle (see BACKUP_RESTORE.md). Never overwrite the live DB while Studio is running.

## If a prepared avatar is corrupted
- Re-prepare from its raw source (Create Avatar flow, ~20-30 min) OR restore `data/avatars/<id>/` from a file backup.

## NEVER
- Do not `git reset --hard` past uncommitted operator data.
- Do not roll back `config/render_truth.json` values (gain/ctx/offset/fps/resolution) — that is the locked lipsync truth.
- Do not move old tags.