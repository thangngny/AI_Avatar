# Dependency Inventory

Full freeze: `diagnostics/handover/pip_freeze_torch.txt` (107 pkgs) and `pip_freeze_py310.txt` (98).
Reproducible lock: `requirements-handover.lock` (production subset).

## Production runtime
| Package | Version | Role | Criticality | Upgrade risk |
|---|---|---|---|---|
| torch | 2.5.1+cu121 | MuseTalk UNet/VAE inference, CUDA graphs | CRITICAL | HIGH — pinned to CUDA 12.1; upgrading torch/CUDA can change lipsync output |
| torchvision | 0.20.1+cu121 | image ops | HIGH | tied to torch |
| numpy | 1.26.4 | numerics | CRITICAL | MED (diffusers/transformers pin range) |
| opencv-python | 4.11.0.86 | validator face detect, preprocessing | CRITICAL | LOW |
| opencv-contrib-python | 4.11.0.86 | extra cv2 modules | HIGH | LOW |
| diffusers | 0.32.2 | UNet/VAE loading | CRITICAL | HIGH (model API drift) |
| transformers | 4.48.0 | Whisper audio2feature | CRITICAL | HIGH |
| insightface | 1.0.1 | face detection/alignment | HIGH | MED |
| mediapipe | 0.10.11 | face mesh | HIGH | MED |
| face-alignment | 1.4.1 | landmark detection | HIGH | LOW |
| decord | 0.6.0 | video frame reading | HIGH | LOW |
| soundfile | 0.14.0 | WAV I/O | HIGH | LOW |
| librosa | 0.10.1 | audio features | HIGH | MED |
| ffmpeg-python | 0.2.0 | mux wrapper | MED | LOW |
| imageio-ffmpeg | 0.5.1 | bundled ffmpeg (verify fallback — note: ffprobe fallback broken, see R15) | MED | LOW |
| Flask | 3.1.3 | Studio web server (dev server, no waitress/gunicorn) | CRITICAL | LOW |
| edge-tts | 7.2.8 | free TTS test voice | HIGH | LOW (external MS service) |
| requests | 2.34.2 | ElevenLabs HTTP | HIGH | LOW |
| Pillow | 12.3.0 | image I/O | MED | LOW |
| psutil | 7.2.2 | process/resource info | MED | LOW |
| omegaconf | 2.3.0 | config loading | MED | LOW |
| einops | 0.7.0 | tensor ops | MED | LOW |
| accelerate | 0.26.1 | model loading accel | MED | MED |

## Dev / test (not required to run production)
- playwright (UI structural verification, run manually)
- unittest (stdlib — backend suite `tests/test_studio.py`)

## LatentSync experimental (NOT imported by production)
- `models/syncnet/latentsync_syncnet.pt` + `avatar_export/bench/syncnet_score.py` are bench/experimental only. Production renderer never imports LatentSync.

## External services
| Service | Purpose | Internet? | Credential? |
|---|---|---|---|
| ElevenLabs | production TTS | yes | API key (.env) |
| Microsoft Edge TTS | free test TTS | yes | none |
| Cloudflare | remote sharing (Quick Tunnel) | yes | none (anonymous tunnel) |
| HuggingFace | model download (recovery only) | yes | none |

## Upgrade procedure (DO NOT run during handover)
1. Snapshot env (`pip freeze > snapshot.txt`).
2. Create a branch / separate venv.
3. `pip install -U <pkg>` in the copy only.
4. Run `tests/test_studio.py` + one short real render + compare output.
5. Roll back if lipsync truth or output changes.
Never `pip install -U` the production env blindly — torch/CUDA upgrades can silently change render output.