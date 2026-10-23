# V6.1 FORENSIC RECONCILIATION REPORT
**AI Avatar NextGen V2 — Photorealistic Production Engineering**  
**Date:** 23 October 2026  
**Auditor:** Principal ML Systems Engineer & Forensic Benchmark Auditor  
**Hardware Verified:** NVIDIA GeForce RTX 5090 Blackwell (`sm_120`, 32GB VRAM), Driver 617.42, Windows 11 Pro  
**Workspace:** `C:\Users\phuongpn\AI_Avatar_NextGen_V2`  

---

## 1. RECONCILIATION MATRIX OF PREVIOUS DISCREPANCIES

| Item / Claim | Original Source | Actual Forensic Evidence | Recalculated / Reconciled Reality | Status | Corrective Action |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **DiT Compute Time (60s)** | V6 claimed `25.80s` | `extended_inference.log` lines 305–795 | **129.71 seconds** ($54 \times 2.402\text{s}$). `25.80s` belonged to the **10-second** test! | **CORRECTED** | Replace with true 129.71s compute time across all tables. |
| **DiT Generation FPS** | V6 claimed `37.1 FPS` | `inference_manifest_60s.json` | **11.66 FPS** ($1,512 \text{ frames} / 129.71\text{s}$). `37.1` was a denoise step latency artifact ($0.371\text{s}$). | **CORRECTED** | Document true DiT compute FPS (11.66) vs end-to-end delivery FPS (8.0). |
| **Duration of Script Demo** | V6 claimed `22.144s` for 552 frames | `ffprobe -show_streams script_demo` | Video is exactly **22.080s** ($552 / 25$). Container is 22.144s due to $0.064\text{s}$ audio-priming packet delay. | **VERIFIED** | Document exact PTS/DTS timeline alignment. Video has zero dropped frames. |
| **12-Frame Chunk Difference** | V6 claimed `shortest` trimmed frames | `generate_video.py` lines 184–192 | Audio is $960,000$ samples. Chunk stride is $17,920$. Remainder is $10,240$ samples. Padded silence is $7,680$ samples ($12$ frames). | **VERIFIED** | Published `V6_1_TIMELINE_FRAME_MANIFEST.json` proving zero speech lost. |
| **NCC Min Outlier 0.8191** | V6 reported min NCC `0.8191` | Frame 25 extraction & template match | Occurred at Frame 25 ($t=1.0\text{s}$) due to natural head nod on *"Chào"*, shifting face by 15px. Not identity loss. | **RESOLVED** | Saved `outlier_inspection_ref_f0_f25.png` to handover folder. |
| **Blinking in MuseTalk** | V6 claimed `0 blinks/min` | `doTrang_closeup/full_imgs` (735 frames) | MuseTalk source video contains pre-recorded blinks in a 735-frame cycle; MuseTalk loops them cyclically. | **CORRECTED** | Clarify cyclic looping vs SoulX's autonomous biological blinking (14 bpm). |
| **NVENC Engine Count** | V6 claimed `Dual NVENC` | NVIDIA RTX 5090 Blackwell Whitepaper | RTX 5090 desktop GPU has **three (3)** 9th-Gen NVENC engines. Single FFmpeg stream binds to 1 engine instance. | **CORRECTED** | Update documentation to reflect 3 NVENC engines on Blackwell RTX 5090. |
| **Attention VRAM Math** | V6 claimed `>120GB VRAM` from $N^2$ | `attention.py` line 521 | PyTorch SDPA uses FlashAttention (tiled memory $O(N)$). Bottleneck is 3D RoPE embeddings & activation memory. | **CORRECTED** | Provide rigorous architectural explanation for 512p native resolution. |

---

## 2. ROOT CAUSE AUDIT: THE 25.80s / 37.1 FPS CONTRADICTION

### 2.1 The Forensic Discovery
In Mission 04, the engineering team recorded benchmark times across three separate durations in `docs/MISSION04_PERFORMANCE_BREAKDOWN.md`:
- **10-Second Test (Chunks 0–8, 9 chunks):** Neural compute time was **25.80 seconds** ($6.55\text{s cold warmup} + 19.25\text{s}$). Total wall-clock was **40.48 seconds**.
- **30-Second Test (Chunks 0–26, 27 chunks):** Neural compute time was **64.63 seconds**. Total wall-clock was **76.70 seconds**.
- **60-Second Test (Chunks 0–53, 54 chunks):** Neural compute time was **129.71 seconds**. Total wall-clock was **141.45 seconds**.

In Mission 05 and V6, a transcription error occurred: the agent accidentally copied the **10-second** neural compute time (`25.80s`) into the **60-second** summary table. When dividing 1,512 frames by an unrelated denoise step latency figure (`0.371s per denoise step`, logged in `extended_inference.log`), the artificial figure "37.1 FPS" was mistakenly derived.

### 2.2 The Truth Reconciled
- **Real 60-Second DiT Compute Time:** $54 \text{ chunks} \times 2.402 \text{s/chunk} = \mathbf{129.71 \text{ seconds}}$.
- **Real DiT Pure Compute FPS:**
  $$\text{DiT Compute FPS} = \frac{1,512 \text{ frames}}{129.71 \text{ seconds}} = \mathbf{11.66 \text{ FPS}}.$$
- **Real Real-Time Factor (RTF):**
  $$\text{DiT RTF} = \frac{129.71 \text{ seconds}}{60.00 \text{ seconds audio}} = \mathbf{2.16\times \text{ Real-Time}}.$$
- **Real End-to-End Delivery Time (Warm Start):**
  $$129.71\text{s (DiT)} + 44.90\text{s (GFPGAN)} + 11.20\text{s (Compositing)} + 1.72\text{s (NVENC)} = \mathbf{187.53 \text{ seconds}} \implies \mathbf{8.00 \text{ Effective FPS}}.$$
- **Verdict:** Fully reconciled and documented in `V6_1_PERFORMANCE_TRUTH_TABLE.csv`.

---

## 3. MASTER MEDIA INTEGRITY & TIMESTAMP AUDIT

All 11 MP4 files in [`D:\CongThang_AI_Avatar\v2_renders\V6_FINAL_ACCEPTANCE\`](file:///D:/CongThang_AI_Avatar/v2_renders/V6_FINAL_ACCEPTANCE/) were subjected to deep packet-level inspection and full-decode validation via FFmpeg null sink:

- **100% of files passed full decode** with exit code 0 and zero decode stderr errors.
- **Timestamp Analysis of `script_to_video_demo_22s.mp4`:**
  - Video stream: $552 \text{ frames} / 25.0 \text{ fps} = \mathbf{22.080000 \text{ seconds}}$ video duration.
  - Video start time: $t = 0.063984\text{s}$ (standard MP4 initial priming sample offset).
  - Audio stream duration: $22.128000\text{s}$ ($346 \text{ packets} \times 1024 / 16000$).
  - Container duration: $22.080000 + 0.063984 = \mathbf{22.143984 \text{ seconds}}$.
  - Conclusion: Zero video frames dropped, zero audio truncation. The 64ms container delta is a standard container muxing offset.

---

## 4. MATHEMATICAL VALIDATION OF CHUNK CONTINUITY (1,512 VS 1,500 FRAMES)

The frame-accurate timeline manifest [`V6_1_TIMELINE_FRAME_MANIFEST.json`](file:///C:/Users/phuongpn/AI_Avatar_NextGen_V2/docs/V6_1_TIMELINE_FRAME_MANIFEST.json) proves:

1. **Audio Parameters:** $60.000000\text{s}$ @ 16kHz = $960,000\text{ samples}$.
2. **Chunk Stride:** $28 \text{ unique frames} \times 16,000 / 25 = 17,920 \text{ audio samples/chunk}$.
3. **Chunk Count:** $\lceil 960,000 / 17,920 \rceil = \mathbf{54 \text{ chunks}}$.
4. **Chunk 53 (Final Chunk) Composition:**
   - Real speech samples: $960,000 \pmod{17,920} = 10,240 \text{ samples} \implies \mathbf{16 \text{ frames of real speech}}$.
   - Padded silence samples: $17,920 - 10,240 = 7,680 \text{ samples} \implies \mathbf{12 \text{ frames of silence padding}}$.
5. **Frame Allocation:**
   - Frames 0 to 1,483: Chunks 0 to 52 ($53 \times 28 = 1,484$ frames).
   - Frames 1,484 to 1,499: Chunk 53 real speech frames ($16$ frames).
   - Frames 1,500 to 1,511: Chunk 53 padded silence frames ($12$ frames).
6. **Muxing Result:**
   - FFmpeg with `-shortest` terminates encoding when the master audio track ends at exactly $60.000000\text{s}$ (frame 1,499).
   - Discarding frames 1,500–1,511 removes only the synthetic trailing silence padding. Zero speech phonemes are excluded.

---

## 5. RECONCILING IDENTITY & NCC METRICS

### 5.1 The Frame 25 ($t=1.0\text{s}$) Outlier
- In Mission 05, the template normalized cross-correlation (NCC) scored a minimum of **0.8191** at Second 1 (Frame 25).
- Forensic frame extraction confirms:
  - At Frame 25, the presenter performs a natural forward head nod upon articulating the opening syllable *"Chào"*, displacing facial features downward and to the right by ~15 pixels.
  - Because `matchTemplate` was computed across the full unaligned 1024×1024 frame, spatial translation lowered template correlation.
  - Visual inspection of [`outlier_inspection_ref_f0_f25.png`](file:///D:/CongThang_AI_Avatar/v2_renders/V6_FINAL_ACCEPTANCE/outlier_inspection_ref_f0_f25.png) confirms that the presenter's facial identity, skin texture, eyes, and mouth are 100% intact and anatomically natural.
- **Rule Confirmed:** NCC measures template correlation, **NOT** percentage of biological identity.

---

## 6. HARDWARE SPECIFICATIONS: NVENC & RTX 5090 BLACKWELL

- **NVENC Count:** The NVIDIA GeForce RTX 5090 Blackwell desktop GPU features **three (3) independent 9th-generation NVENC encoders**.
- **Encoder Utilization:** A single FFmpeg stream (`-c:v h264_nvenc`) utilizes **one (1) encoder engine**. When scaling to multi-avatar parallel production, Studio V2 can dispatch up to 3 concurrent encode jobs without GPU encoder contention.
- **Multipass Mode:** `-multipass fullres` is a macroblock-level two-pass lookahead within the NVENC hardware buffer, adding $<5\%$ overhead while preserving edge sharpness.
