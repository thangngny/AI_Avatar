# V2 PRODUCTION DEPENDENCIES & ISOLATION MATRIX

## 1. Dependency Cross-Reference

| Resource | Production (V1) Location | V2 Location | Access Mode | Isolation Protection |
| :--- | :--- | :--- | :--- | :--- |
| **Source Code** | `C:\Users\phuongpn\AI_Avatar_NextGen` | `C:\Users\phuongpn\AI_Avatar_NextGen_V2` | Independent Clone | Completely decoupled Git repository and files. |
| **Python Runtime** | `C:\Users\phuongpn\runtime_nextgen\venv` | `C:\Users\phuongpn\runtime_avatar_v2` | Independent Virtualenv | Separate python binary, site-packages, and Scripts. |
| **Render Output** | `D:\CongThang_AI_Avatar\renders` | `D:\CongThang_AI_Avatar\v2_renders` | Dedicated Directory | Separate directory on Drive D. V2 never touches V1 outputs. |
| **Model Checkpoints** | `C:\Users\phuongpn\AI_Avatar\models` | `C:\Users\phuongpn\AI_Avatar_NextGen_V2\models` | Read-Only NTFS Junction | Immutable model weights shared read-only to avoid wasting 20GB+ SSD. |
| **Prepared Avatars** | `C:\Users\phuongpn\AI_Avatar\data\avatars` | `C:\Users\phuongpn\AI_Avatar_NextGen_V2\data\avatars` | Read-Only NTFS Junction | Immutable preprocessed avatar frames and latents shared read-only. |
| **Web Service Port** | `127.0.0.1:8078` (Studio) | `127.0.0.1:8178` (Studio V2) | Network Bind | Distinct TCP port; no conflict with active PID 31024. |
| **API Service Port** | `127.0.0.1:8077` (Backend) | `127.0.0.1:8177` (Backend V2) | Network Bind | Distinct TCP port; completely independent listener. |
| **Studio DB / State** | `data/studio.db` | `data/studio_v2.db` | Independent SQLite | Isolated job queue, history, and avatar registry. |

---

## 2. Shared Read-Only Asset Audit

The following model checkpoints reside in `C:\Users\phuongpn\AI_Avatar\models` and are accessed read-only:
1. `musetalkV15/` (MuseTalk UNet checkpoints, Whisper PE, etc.)
2. `sd-vae/` (Stable Diffusion VAE Decoder/Encoder)
3. `whisper/` (OpenAI Whisper tiny/base audio feature extractor)
4. `dwpose/` & `face-parse-bisent/` (Face and landmark parsers)
5. `GFPGANv1.4.pth` (Face restoration checkpoint)

**Safety Verification:**
- Neither V1 nor V2 inference scripts open model files in write (`'w'`) or append (`'a'`) mode.
- PyTorch loads weights via `torch.load(..., map_location=...)` or `safetensors.torch.load_file(...)` which are strictly read operations.
- New candidate model weights (InfiniteTalk, EchoMimic, SoulX, LatentSync) will be downloaded and housed in dedicated V2 directories (`AI_Avatar_NextGen_V2/weights/`) without polluting V1.

---

## 3. Environment Variable Isolation (`.env.v2`)

V2 maintains its own configuration file `C:\Users\phuongpn\AI_Avatar_NextGen_V2\.env`:
- `STUDIO_PORT=8178`
- `STUDIO_API_PORT=8177`
- `RENDERS_DIR=D:\CongThang_AI_Avatar\v2_renders`
- `CANONICAL_INTERPRETER=C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe`
- `STUDIO_DB_PATH=data/studio_v2.db`

**GATE P0 COMPLETION: VERIFIED SAFE FOR IMPLEMENTATION.**
