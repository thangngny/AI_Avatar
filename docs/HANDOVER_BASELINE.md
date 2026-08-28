# AI Avatar Studio — Handover Baseline (Phase A freeze)

Captured 2026-08-28 before any hardening. This is the reproducible baseline.

## Git
- Branch: `main`
- HEAD: `598ee7f` (commit "polish simplified studio UX before user documentation (V1.4.0)")
- Tag at HEAD: `ai-avatar-studio-ui-v1.3.1`
- Working tree: clean except untracked docs/ asset packs and (after this audit) new handover files

## Operating environment
- OS: Windows 11 Pro 10.0.26200
- Shell: PowerShell 7 + Git Bash
- GPU: 2 × NVIDIA GeForce RTX 3090 (24 576 MiB each), driver 610.88
- CUDA (PyTorch-observed): 12.1
- Drives: C: used 399GB / free ~80GB · D: used 1990GB / free ~804GB · E: used 1779GB / free ~84GB (avoid E:)

## Python runtimes
- Torch-capable interpreter (production renderer): `C:\CongThang\AI_avatar\latentsync_env\Scripts\python.exe` — Python 3.10.11, pip 23.0.1
- System Python 3.10 (controller may also run here, but launcher uses the torch env): `C:\Users\Admin\AppData\Local\Programs\Python\Python310\python.exe`
- Node (UI tooling only): v26.3.0
- ffmpeg: 9.0 (gyan build, on PATH at `C:\Users\Admin\AppData\Local\Microsoft\WinGet\Links\ffmpeg.EXE`)
- cloudflared: 2026.8.2

## Key library versions (torch env)
torch 2.5.1+cu121 · torchvision 0.20.1+cu121 · numpy 1.26.4 · opencv-python 4.11.0.86 · Flask 3.1.3 · edge-tts 7.2.8 · soundfile 0.14.0 · librosa 0.10.1 · diffusers 0.32.2 · transformers 4.48.0 · insightface 1.0.1 · mediapipe 0.10.11 · face-alignment 1.4.1 · decord 0.6.0 · Pillow 12.3.0

## Studio runtime
- Studio port: 8077 (127.0.0.1)
- Database: `C:\CongThang_AI_Avatar\AI_avatar\data\studio_runtime\studio.db` (151 552 bytes, WAL mode, integrity=ok, jobs=21, avatars=19)
- Render output: `D:\CongThang_AI_Avatar\renders\studio\` (92 files, 782 MB, largest 99 MB)
- Avatar data: `C:\CongThang_AI_Avatar\AI_avatar\data\avatars\` (19 dirs, 34.9 GB)
- Raw sources: `C:\CongThang_AI_Avatar\AI_avatar\data\input\avatar_sources\` (9 files, 155 MB)
- Models: `C:\CongThang_AI_Avatar\AI_avatar\models\` + `gfpgan\weights\` (33 files, 8.85 GB)
- Temp/logs: `C:\CongThang_AI_Avatar\AI_avatar\data\studio_runtime\` (16.1 MB)
- TTS config: `C:\CongThang_AI_Avatar\AI_avatar\.env` (gitignored, NOT in repo)

## Locked production truth (config/render_truth.json)
pipeline=musetalk_v15 · audio_gain=1.5 · audio_context_left=0 · audio_feature_offset_frames=-3 · fps=25 · 1080×1920 · cuda_graph=true · long_audio_wola=true · feature_coverage_assertion=true
system_status.py → Production Truth: VALID · Ready: YES

## Evidence artifacts (this audit, non-secret)
`diagnostics/handover/` — pip_freeze_torch.txt, pip_freeze_py310.txt, model_manifest_raw.json, model_manifest.json, _disk.ps1, _checksum_models.py
`diagnostics/handover_risk_register.json` — machine-readable risk register