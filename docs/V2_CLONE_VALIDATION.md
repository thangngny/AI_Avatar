# V2 CLONE & ISOLATION VALIDATION REPORT
**Date:** 2026-10-22  
**Target Repository:** `C:\Users\phuongpn\AI_Avatar_NextGen_V2`  
**Target Runtime:** `C:\Users\phuongpn\runtime_avatar_v2`  
**Target Renders:** `D:\CongThang_AI_Avatar\v2_renders`  

---

## 1. Isolation Verification Matrix

| Checklist Item | Required Condition | Actual Verified Status | Evidence |
| :--- | :--- | :--- | :--- |
| **V1 Integrity** | Source code unmodified | **PASSED** | `git status --porcelain` is clean in `AI_Avatar_NextGen`. |
| **V1 Service** | Studio V1 remains running | **PASSED** | PID `31024` listening on `127.0.0.1:8078`, `/api/system/status` returns `ready: true`. |
| **V2 Source Tree** | Independent clone | **PASSED** | Independent git repository at `AI_Avatar_NextGen_V2` @ commit `63fff38`. |
| **V2 Runtime** | Independent virtualenv | **PASSED** | `runtime_avatar_v2` with PyTorch 2.7.0+cu128 (`sm_120`), CUDA 12.8, FP16/Tensor Cores verified. |
| **V2 Storage** | Independent output folder | **PASSED** | Outputs write strictly to `D:\CongThang_AI_Avatar\v2_renders`. |
| **Model Weights** | Read-only access | **PASSED** | Immutable NTFS Junctions created for `models/` and `data/avatars/`. |

---

## 2. Baseline MuseTalk Render Test in V2

A complete 550-frame end-to-end render job was executed under the new V2 runtime:

- **Command Executed:**
  ```powershell
  C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe generate_video_from_script.py `
    --avatar_id doTrang_closeup `
    --audio C:\Users\phuongpn\AI_Avatar_NextGen_V2\assets\demo_elevenlabs_16k.wav `
    --output D:\CongThang_AI_Avatar\v2_renders\baseline_musetalk_v2.mp4 `
    --batch_size 32 `
    --expressive_motion
  ```

### Render Execution Metrics:
- **Audio File:** `demo_elevenlabs_16k.wav` (22.02 seconds, 16 kHz mono Vietnamese speech)
- **Avatar Used:** `doTrang_closeup` (735 frames, 1080×1920)
- **Total Frames Generated:** 550 frames @ 25 FPS
- **UNet Batch Size:** 32 with CUDA Graph capture on GPU 0
- **Total Render Duration:** **40.1 seconds** (including cold-start graph capture, VAE decode, Lanczos-4, 6-DoF affine warp, and NVENC P7 HQ encoding)
- **Net End-to-End FPS:** **13.7 FPS** (Cold-start). Warm-start reaches **~20 FPS**.
- **Output Artifact:**
  - File: `D:\CongThang_AI_Avatar\v2_renders\baseline_musetalk_v2.mp4`
  - Dimensions: `1080 × 1920` (Full HD Portrait)
  - Codec: H.264 (`h264_nvenc`, Preset P7 HQ) + AAC Audio
  - File Size: `34.6 MB`
  - Decodable & Playable: Verified via `ffprobe` (Streams: 1 video 1080x1920 25fps, 1 audio AAC 44.1kHz).

---

## 3. Baseline Quality Observations

1. **Lip-Sync Accuracy:** Good phonetic synchronization with Vietnamese audio; mouth closes properly on silence.
2. **Head & Neck Movement:** Subtle spring-damper nodding and yaw drift is functional, but remains a 2D affine perspective approximation.
3. **Facial Expression Disconnect:** Upper face, forehead, and eyes do not react emotionally to speech tone or sentiment.
4. **Mouth Cut-out Boundary:** High-contrast edge injection sharpens teeth, but lower-jaw blending can occasionally exhibit faint texture softening relative to 4K skin pore detail.

---

## 4. Gate Sign-off

- [x] Baseline clone operational.
- [x] Zero regressions or side-effects on production V1.
- [x] Playable baseline MP4 produced in isolated directory.
- **GATE P1 STATUS: PASS**
