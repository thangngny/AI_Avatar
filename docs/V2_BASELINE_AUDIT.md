# V2 BASELINE AUDIT & PRODUCTION DISCOVERY REPORT
**Date:** 2026-10-22  
**Host Machine:** Windows 11 Pro 64-bit Workstation  
**Author:** AI Research & Systems Engineering Lead  

---

## 1. Hardware & Runtime Infrastructure Audit

| Component | Physical Hardware / Configuration | Verified State & Metric |
| :--- | :--- | :--- |
| **GPU** | NVIDIA GeForce RTX 5090 (Blackwell architecture, `sm_120`) | Driver: `617.42`, VRAM Total: `32,607 MiB`, Free: `~29,228 MiB`, Temp: `52°C`, Power Cap: `575W` |
| **CPU** | Intel Core i9-14900KF | 24 Cores (8P + 16E), 32 Threads, up to 6.0 GHz |
| **System RAM** | 128 GB DDR5 (4 × 32GB Kingston FURY Beast) | Running @ 4000 MHz JEDEC for LGA1700 quad-DIMM stability |
| **Storage C:** | Samsung SSD 990 EVO Plus 1TB (NTFS) | Total: `930.4 GB`, Free: `713.5 GB` |
| **Storage D:** | Samsung SSD 990 PRO with Heatsink 4TB (NTFS) | Total: `3,726.0 GB`, Free: `3,723.5 GB` (Dedicated Scratch & Render disk) |
| **Mainboard** | MSI Z790 GAMING PLUS WIFI (MS-7E06) | BIOS / Chipset Z790 |
| **FFmpeg** | FFmpeg 9.0.2 (gyan.dev build) | Full NVENC support: `h264_nvenc`, `hevc_nvenc`, `av1_nvenc` |
| **WSL2 / Docker** | Windows Subsystem for Linux / Docker Desktop | **Not installed** (Environment is 100% Native Windows 11) |
| **Python Tooling** | `uv` package manager (`C:\Users\phuongpn\.local\bin\uv.exe`) | Version 0.13.3; CPython 3.11.17 |
| **PyTorch Stack** | PyTorch 2.7.0+cu128 (`torch-2.7.0+cu128-cp311-win_amd64.whl`) | CUDA 12.8; Arch list explicitly includes `sm_120` (Blackwell native) |

---

## 2. Existing Production System Audit (AI_Avatar_NextGen)

- **Source Location:** `C:\Users\phuongpn\AI_Avatar_NextGen`
- **Current Git Branch & HEAD:** `main` @ `63fff388e4a2687c9eaa9a4e8c9760205d95d812`
- **Working Tree State:** Completely clean (`git status --porcelain` returns empty).
- **Active Process:**
  - PID: `31024` running `run_studio.py --host 127.0.0.1 --port 8078 --no-browser`
  - Listening Port: `http://127.0.0.1:8078`
- **Primary Model Checkpoints & Avatar Storage:**
  - `models/` is an NTFS Directory Junction pointing to `C:\Users\phuongpn\AI_Avatar\models`
  - `data/avatars/` is an NTFS Directory Junction pointing to `C:\Users\phuongpn\AI_Avatar\data\avatars`
  - `dist_assets/` is an NTFS Directory Junction pointing to `C:\Users\phuongpn\AI_Avatar\dist_assets`
- **Render Output Location:** `D:\CongThang_AI_Avatar\renders`
- **TTS Configuration:**
  - Primary: ElevenLabs (`eleven_v4`, voice ID: `N0Z0aL8qHhzwUHwRBcVo`, pcm_16000)
  - Fallback: Edge TTS (`vi-VN-HoaiMyNeural` / `vi-VN-NamMinhNeural`)

---

## 3. Critical Verification of Baseline Claims

### 3.1. Claim: 17–25 FPS Realtime End-to-End Render
* **Verification:** **CONFIRMED ACCURATE.**
* The MuseTalk UNet inference runs in FP16 on Blackwell Tensor Cores at **~608 FPS** (batch size 32/48 with CUDA Graph enabled).
* However, the SD-VAE decoder operates at ~133 FPS, and disk read + frame blending + FFmpeg NVENC pipe bring the net end-to-end throughput down to **17.5 – 25.2 FPS**.
* For a 22-second clip (550 frames), total wall-clock time is ~22–32 seconds.

### 3.2. Claim: Native 1080×1920 Inference
* **Verification:** **NUANCED (Composited, NOT Native Full-Body Diffusion).**
* The neural network (MuseTalk) only generates a **256×256 latent bounding box** centered on the lower face / mouth.
* The 256×256 decoded RGB patch is upscaled / filtered via Lanczos-4, bilateral sharpened, and alpha-feathered onto the original 1080×1920 video frame.
* The head, hair, eyes, torso, and background are **from the original video source**, not generated frame-by-frame.

### 3.3. Claim: Forward-Loop Momentum
* **Verification:** **CONFIRMED.**
* The renderer avoids ping-pong mirroring (`mirror_index`) by cycling through a calibrated slice `[325:525]`. At frame 524 -> 325, torso pixel shift is minimal ($\le 1px$).
* **Limitation:** While it prevents the jerky reverse motion of mirroring, a 200-frame loop (8 seconds @ 25 FPS) repeats every 8 seconds. In a 60-second video, the MC's breathing and small body movements cycle 7.5 times.

### 3.4. Claim: 6-DoF Expressive Motion
* **Verification:** **PARTIALLY VALIDATED.**
* `avatars/expressive_motion.py` extracts audio pitch and RMS energy, passing them through a 2nd-order spring-damper differential equation to generate pitch nodding and yaw drift.
* The transformation is executed via 2D affine grid sampling (`F.grid_sample`) around the neck pivot.
* **Limitation:** This is a **2D affine approximation**. It tilts and shears the video frame, but cannot generate true 3D out-of-plane head rotation, chin elevation, perspective foreshortening, or eye saccades.

### 3.5. Claim: -40ms Audio-Feature Offset
* **Verification:** **CONFIRMED.**
* `audio_feature_offset_frames: -1` in `config/render_truth.json` advances audio features by 1 frame (40ms @ 25 FPS) so mouth articulation anticipates sound onset.

---

## 4. Root-Cause Analysis of Current Quality Limitations

1. **"Mouth-Glued-On" Effect (Paste-Back Boundary):**
   Even with Reinhard LAB color blending and Gaussian feathering, the 256×256 patch often has slightly different high-frequency grain, sub-surface scattering, or lighting than the source frame.
2. **Fixed Facial Expressions (Affect Disconnect):**
   MuseTalk only modifies the mouth and lower jaw. The upper face (eyes, eyebrows, forehead, smile lines) remains in whatever state the original video frame was in. If the MC smiles in speech, but the source frame has relaxed eyes, the avatar appears emotionally dead or mismatched.
3. **Repetitive Upper-Body Gestures:**
   Source video frames are looped. Arms and hands do not emphasize words, point, or react to the narrative.
4. **Phoneme Jitter on Rapid Vietnamese Syllables:**
   Vietnamese tones and compound vowels (e.g. `uyên`, `uông`, `ngh`) sometimes cause micro-flicker or insufficient mouth closure on labial plosives (`b`, `m`, `p`) when audio features are smoothed over fixed temporal contexts.

---

## 5. Isolation & Safety Sign-off

- [x] Host hardware parameters verified (`sm_120`, 32GB VRAM, 128GB RAM).
- [x] Production system state documented and verified clean.
- [x] Production processes (PID 31024 on port 8078) left completely undisturbed.
- [x] Ports 8177 and 8178 confirmed open and assigned to V2.
- [x] Target directories established:
  - V2 Repo: `C:\Users\phuongpn\AI_Avatar_NextGen_V2`
  - V2 Runtime: `C:\Users\phuongpn\runtime_avatar_v2`
  - V2 Renders: `D:\CongThang_AI_Avatar\v2_renders`
- **GATE P0 STATUS: PASS**
