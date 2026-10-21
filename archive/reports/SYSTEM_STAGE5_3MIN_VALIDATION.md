# SYSTEM_STAGE5_3MIN_VALIDATION.md — Stage 5 Candidate C long-form validation render

Project root: `C:\CongThang_AI_Avatar\AI_avatar`
Branch: `feature/mouth-articulation-v1` (NOT committed; stable tag untouched)
Date: 2026-08-25
Python env: `C:\CongThang\AI_avatar\latentsync_env` (torch 2.5.1+cu121), `CUDA_VISIBLE_DEVICES=1`
SyncNet: `C:\CongThang\AI_avatar\avatar_export\bench\syncnet_score.py --preprocess face_crop`
No image was read by a language model; all mouth measurements are numeric, script-side (FAN / face_alignment 68 landmarks, normalized by face width = distance(landmark 0,16); freeze check via `diag_motion.py` mouth-ROI motion vs audio RMS).

---

## Configuration

```
audio_gain                      = 1.5
audio_context_left              = 0
audio_feature_offset_frames     = -3
FPS                             = 25
resolution                      = 1080x1920
CUDA Graph                      = ON
MuseTalk                        = v1.5 (models/musetalkV15/unet.pth) + whisper-tiny
avatar                          = fullbody_30_7_25fps
TTS                             = EdgeTTS vi-VN-HoaiMyNeural (ElevenLabs NOT used)
batch_size                      = 16
encoding                        = libx264 ultrafast CRF16 (rawvideo pipe) + AAC 192k mux
face_enhance / GFPGAN           = OFF
```

Nothing else was modified vs the stable checkpoint except the single `audio_conditioning_gain = 1.5` knob (default 1.0 = bit-identical to stable). WOLA, context timing, offset, CUDA Graph, batch behavior, compositing, encoding and avatar preparation are unchanged.

---

## Input

```
script path   : C:\CongThang_AI_Avatar\AI_avatar\script_stage5_3min.txt
audio path    : D:\CongThang_AI_Avatar\stage5\master_3min.wav
audio duration: 193.219 s
sample rate   : 16000 Hz
channels      : 1 (mono)
frames        : 3 091 499 samples
```

Script: ~14 connected natural Vietnamese sentences (a friendly talk on building
healthy family daily habits). Not a phonetic drill; natural mix of m/b/p, a/ă/â,
e/ê/i, o/ô/ơ, u/ư, tr/ch, ng/nh, with both short and long phrases and natural
pauses. Two TTS length adjustments were made to land inside 160–200 s (first
attempt 131 s → too short; second 205.7 s → slightly over 200 s; final 193.2 s).

---

## Feature coverage

Whisper long-audio WOLA extraction (logged before inference):

```
windows            = 7  (30 s windows, 1.00 s overlap)
actual features    = 9661
expected features  = ~9668   ((4830-1)*2 + 10)
coverage duration  = 193.220 s
uncovered          = 0
expected video frames = 4830
```

The renderer's strict coverage assertion passed (it raises before inference on
under-coverage — no silent clamping). **PASS.**

---

## Render

```
video path   : D:\CongThang_AI_Avatar\renders\stage5_gain15_3min.mp4
frames       : 4830
duration     : 193.200 s (video) / 193.219 s (master audio) -> A/V diff 0.019 s (<1 frame)
render FPS   : 29.5 (MuseTalk UNet+VAE, CUDA Graph ON, single GPU)
total render wall (model load + features + render + mux): 201 s
WOLA windows : 7 (boundaries at 30 / 60 / 90 / 120 / 150 / 174 s)
```

---

## SyncNet segment results

| Segment | Sync Confidence | LSE-C | AV Offset |
| ------- | --------------: | ----: | --------: |
| FULL (0–193 s) | 0.45592 | 0.28352 | 0 |
| 5–15 s   | 0.37057 | 0.20312 | 0 |
| 25–35 s  | 0.44072 | 0.26426 | 0 |
| 55–65 s  | 0.35875 | 0.17384 | 0 |
| 85–95 s  | 0.47110 | 0.30746 | 0 |
| 115–125 s| 0.41846 | 0.22985 | 0 |
| 145–155 s| 0.47193 | 0.33719 | 0 |
| 165–175 s| 0.33464 | 0.13701 | 1 |
| 180–190 s| 0.48049 | 0.29192 | 0 |

AV offset is 0 on the full video and on 7 of 8 segments. The single +1 on
165–175 s is one frame (40 ms) within SyncNet's 1-frame resolution; that segment
straddles the 174 s WOLA boundary. There is **no growing drift** (the sequence is
0,0,0,0,0,0,1,0 — not 0→1→2→3…). Sync confidence stays in a healthy 0.33–0.48
band across all segments with no late collapse. Estimated lag = AV offset × 40 ms
≈ 0 ms overall (≤40 ms on the one segment).

---

## Long-duration stability

Mouth-ROI motion (diag_motion, 5 s buckets) vs audio RMS — no "FROZEN but audio
active" flag in any bucket; motion stays 7.5–10.9 across 0–190 s.

```
30 s  : PASS   (motion 8.80, audio active)
60 s  : PASS   (motion 7.53, audio active)
90 s  : PASS   (motion 10.17, audio active)
120 s : PASS   (motion 9.46, audio active)
150 s : PASS   (motion 9.26, audio active)
```

---

## WOLA boundary result

Boundaries at 30 / 60 / 90 / 120 / 150 / 174 s. Mouth motion at the buckets
straddling each boundary: 30 s=8.8, 60 s=7.5, 90 s=10.2, 120 s=9.5, 150 s=9.3,
174 s=9.0→9.5 — no cliff, no static-mouth region, no sudden reset. SyncNet on
boundary-spanning segments: 25–35 s=0, 55–65 s=0, 85–95 s=0, 115–125 s=0,
145–155 s=0, 165–175 s=+1 (one frame, noted above). **PASS.**

---

## Articulation continuity

Stage 5 gain-1.5 improvement is preserved across the full 3 minutes (FAN
landmarks, normalized by face width), aggregated into 25 s windows:

| window | vopen mean | vopen std (diversity) | vopen range | width mean | intra-bucket motion |
| ------ | ---------: | -------------------: | ----------: | ---------: | ------------------: |
| 0–25 s   | 0.0409 | 0.0177 | 0.1128 | 0.3073 | 0.01209 |
| 25–50 s  | 0.0380 | 0.0168 | 0.0955 | 0.3066 | 0.01253 |
| 50–75 s  | 0.0355 | 0.0179 | 0.0934 | 0.3082 | 0.01504 |
| 75–100 s | 0.0400 | 0.0173 | 0.0937 | 0.3047 | 0.01293 |
| 100–125 s| 0.0369 | 0.0180 | 0.0928 | 0.3058 | 0.01336 |
| 125–150 s| 0.0408 | 0.0175 | 0.0923 | 0.3039 | 0.01427 |
| 150–175 s| 0.0403 | 0.0188 | 0.0934 | 0.3081 | 0.01370 |
| 175–200 s| 0.0359 | 0.0171 | 0.0788 | 0.3116 | 0.01196 |

Full-video: vopen_inner span **0.113** (vs Stage 5 baseline 0.093 → +23 %),
motion **0.01328** (vs baseline 0.0107 → +25 %), width mean 0.307 (unchanged),
identity_std (non-mouth landmarks) **0.01364** (≈ baseline 0.01376 → identity
stable over 3 min).

Early (0–30 s) vs late (150–193 s): diversity (vopen std) is flat (0.0181 →
0.0181); late intra-bucket motion (0.01297) is **≥** early (0.01200). There is
no "good articulation early, mouth becomes smaller or repetitive later" pattern.
The 175–200 s dip in range is the quieter closing "Cảm ơn… chúc quý vị…"
sentence (natural). **PASS.**

---

## Suggested manual review timestamps

The model cannot view frames; these are the reviewer's checkpoints. Approximate
sentence start times (by char proportion) are listed for context.

| Time | What is being said (approx.) | Inspect |
| ---- | --- | --- |
| 00:10 | "…mình xin được trò chuyện cùng quý vị về một chủ đề… / Chúng ta đều biết rằng sức khỏe…" | Opening articulation, tr/ch (trò chuyện), ng/nh (gần gũi), overall naturalness |
| 00:35 | "Một ly nước ấm vào buổi sáng sẽ giúp cơ thể sảng khoái hơn…" | **m/b/p closure** (Một, ấm, buổi), **rounded vowel** (khoái), open vowels |
| 01:00 | "…vận động cơ thể mỗi ngày… / Đặc biệt với những người làm việc văn phòng… đứng dậy vươn vai vài phút mỗi giờ để cổ vai gáy được thư giãn…" | **fast connected speech** (long phrase), transitions, jaw/lower-face stability |
| 01:30 | "Đối với các gia đình có con nhỏ, mình nghĩ chúng ta nên cùng nhau tạo ra không khí vui vẻ khi ăn uống…" | **m/b/p** (mình, nhau), **open vowels** (vui vẻ), ng/nh, identity mid-video |
| 02:00 | "Quý vị có thể dành vài phút mỗi tối để đọc một cuốn sách yêu thích…" | **m/b/p** (phút, mỗi, một), **rounded** (cuốn), fast connected |
| 02:30 | "Những buổi đi dạo… / Bên cạnh đó… hạn chế thời gian sử dụng các thiết bị điện tử…" | tr/ch (chế, thiết), long phrase, late-video identity stability |
| 02:50 | "Cuối cùng, mình mong quý vị hãy nhớ rằng thay đổi thói quen không cần phải ồ ạt hay vội vã…" | **open vowel** (ồ ạt), late articulation flexibility, no fatigue |
| 03:00 | "Cảm ơn quý vị đã dành thời gian lắng nghe… chúc quý vị và gia đình thật nhiều sức khỏe, niềm vui…" | **m/b/p closure** (Cảm ơn, mình), **rounded** (sức khỏe ô/ơ), closing smile/closure, final-10–15 s smoothness |

Phonetic highlight moments for focused lip inspection:
- **m/b/p lip closure:** 00:35 (Một/ấm/buổi), 01:30 (mình/nhau), 02:00 (phút/mỗi/một), 03:00 (Cảm ơn/mình).
- **open vowels (a/ă/â):** 00:44 (bữa sáng đầy đủ năng lượng), 01:30 (vui vẻ), 02:50 (ồ ạt).
- **rounded vowels (o/ô/ơ/u/ư):** 00:30 (uống đủ nước), 00:37 (khoái), 01:15 (mười giờ), 02:00 (cuốn), 03:00 (sức khỏe).
- **faster connected speech:** 01:05 (đứng dậy vươn vai vài phút mỗi giờ để cổ vai gáy được thư giãn), 02:30 (hạn chế thời gian sử dụng các thiết bị điện tử).

---

## Performance

```
TTS generation time (final 193 s master WAV, EdgeTTS cloud): ~21 s wall (variable)
Whisper feature extraction (7 WOLA windows): ~10 s
MuseTalk render time (4830 frames, UNet+VAE): 163.8 s
average render FPS: 29.5
final encoding (ffmpeg libx264 rawvideo pipe during render + AAC mux): ~2 s mux
total output frames: 4830
final video duration: 193.200 s
final audio duration: 193.219 s (master) / 193.152 s (muxed AAC)
A/V duration difference: 0.019 s (< 1 frame)
peak GPU VRAM: not separately captured during render; unchanged vs Stage 5 by design
  (same model, same fixed CUDA-Graph shapes [16,50,384] audio / [16,8,32,32] latent,
   gain adds zero tensors)
total render wall (model load + features + render + mux): 201 s
```

No performance optimization was performed in this task.

---

## Decision

This is a long-form **validation render only**. All objective guardrails pass:

- Feature coverage PASS (9661 feats, uncovered 0, full 193 s).
- No mouth freeze at 30 / 60 / 90 / 120 / 150 s; no static-mouth regions.
- WOLA boundaries clean (no reset/artifact; one 1-frame SyncNet offset on the 174 s boundary, no drift).
- AV offset ≈ 0 overall and per segment; no growing temporal drift.
- Articulation improvement (+23 % vertical opening, +25 % motion) preserved through the full 3 min; identity stable; lip closure preserved; no late fatigue.

The **final aesthetic decision** (naturally wider, enough flexibility, no rubber
mouth, identity preserved, convincing over long speech) is the human reviewer's
gate and was NOT auto-promoted. No production default was changed; no commit or
tag was created. The stable tag `ai-avatar-lipsync-v1-stable` and commit
`0d0f03a` remain untouched.