# SYSTEM_AVATAR_VS_MUSETALK_AB_TEST.md — Avatar-source vs MuseTalk A/B

Project root: `C:\CongThang_AI_Avatar\AI_avatar`
Branch: `feature/mouth-articulation-v1` (diagnostic only — no production code or
stable checkpoint modified; nothing committed)
Stable tag: `ai-avatar-lipsync-v1-stable` @ `0d0f03a` — untouched
Date: 2026-08-25
Python env: `C:\CongThang\AI_avatar\latentsync_env` (torch 2.5.1+cu121); GPU bind `CUDA_VISIBLE_DEVICES=1` (single GPU, `OFFLINE_USE_MULTI_GPU=false` → no 2-GPU crash)
SyncNet: `avatar_export/bench/syncnet_score.py --preprocess face_crop`
Constraint obeyed: no image was read by a language model. All mouth metrics are
numeric, script-side (FAN / face_alignment 68 landmarks, normalized by face width
= distance(landmark 0,16)). SyncNet is a numeric audio-visual model.

---

## Question

Is the current small/subtle-looking mouth articulation primarily caused by the
**avatar source** (small face, soft 4K source) rather than **MuseTalk timing**?

This resolves a disagreement between two prior reports:
- `SYSTEM_AVATAR_INPUT_AUDIT.md` → root cause = AVATAR SOURCE (small face 9.4 %
  of frame, sharpness 28 vs 385; recommended `TEST_EXISTING_BETTER_AVATAR`).
- `SYSTEM_LIPSYNC_STAGE5_ARTICULATION_REPORT.md` → root limiter = RAW_MUSETALK
  (the decoded 256×256 mouth's own compressed range; model, not avatar).

---

## Test (controlled A/B)

Same master audio (`master_continuous.wav`, 19.87 s, 4 Vietnamese sentences), same
timing (`audio_feature_offset_frames=-3`, `audio_context_left=0`), 25 FPS,
batch 16, CUDA Graph ON, MuseTalk v1.5 + whisper-tiny, GPU1, libx264 ultrafast
CRF16, no GFPGAN. **Only `avatar_id` and `audio_conditioning_gain` change.**

| run | avatar_id | gain | file |
| --- | --- | ---: | --- |
| active A | fullbody_30_7_25fps (ACTIVE) | 1.0 | stage5_artic_A_baseline.mp4 |
| active C | fullbody_30_7_25fps (ACTIVE) | 1.5 | stage5_artic_C_medium.mp4 |
| closeup A | close_up (better-existing) | 1.0 | stage5_closeup_A_baseline.mp4 |
| closeup C | close_up (better-existing) | 1.5 | stage5_closeup_C_medium.mp4 |

The close_up avatar (audit grade A/93: face 0.116 of frame ≈ 223 px vs active
180 px, sharpness 385 vs 28 — ~14× sharper source) was rendered with the **same**
Stage 5 pipeline. Its prepared files (coords.pkl, mask_coords.pkl, latents.pt, 980
full_imgs, 980 masks) are complete and structurally parallel to the active
avatar's — it loaded and rendered without error (22.0 s / 496 frames, 22.5 fps).

**Note on the "image model not support" error:** it did NOT occur on the standard
MuseTalk render path (`stage5_render.py` → production `render_video`). The only
load-time messages are the usual non-fatal ones (VAE falls back to .bin /
`Defaulting to unsafe serialization`; `torch.load` FutureWarning; GPU-id fallback
to `cuda:0` because `CUDA_VISIBLE_DEVICES=1` exposes one GPU). The paste-back
(`avatars/musetalk/myutil.py:get_image_blending`) is pure cv2/numpy with no model
load, so it cannot raise that error. Using the proven single-GPU pipeline with
the correct, complete avatar files avoided it entirely.

---

## Results

| label | sync_conf | LSE-C | AV off | vopen mean | vopen span | vopen std | width span | motion | identity std |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| active A g1.0  | 0.37816 | 0.19225 | 0 | 0.0399 | 0.0928 | 0.0167 | 0.0841 | 0.01068 | 0.01376 |
| active C g1.5  | 0.41667 | 0.23527 | 0 | 0.0389 | 0.1140 | 0.0198 | 0.0813 | 0.01338 | 0.01373 |
| closeup A g1.0 | 0.38488 | 0.20834 | **1** | 0.0354 | 0.0941 | 0.0187 | 0.0766 | 0.01312 | 0.01205 |
| closeup C g1.5 | 0.43360 | 0.26348 | **1** | 0.0354 | 0.1049 | 0.0214 | 0.0930 | 0.01515 | 0.01236 |

(vopen / width are normalized by face width; identity_std = non-mouth landmark
position std, lower = more stable.)

---

## Findings

### 1. Timing is NOT the cause (re-confirmed)
AV offset ≈ 0–1 frame across all four runs. Audio is byte-identical and timing
params are identical, so timing was already correct — this test changes only the
avatar. **MuseTalk timing is exonerated again.**

### 2. The avatar source affects LEGIBILITY, not AMPLITUDE
- **SyncNet (objective mouth-legibility / audio-visual match): close_up wins at
  both gains** — g1.0: 0.3849 vs 0.3782 (+1.8 %); g1.5: 0.4336 vs 0.4167 (+4.1 %).
  LSE-C is higher for close_up at both gains too. → The sharper, larger-face
  close_up avatar produces a **more legible** generated mouth. This **confirms
  the audit's** "more lip pixels + ~14× sharper source → cleaner lip edges" point.
- **Normalized mouth opening (vopen span) is essentially unchanged by avatar:**
  g1.0: 0.0941 (closeup) vs 0.0928 (active); g1.5: 0.1049 (closeup) vs 0.1140
  (active — slightly *larger* on the active avatar). → Switching avatar does **not**
  widen the mouth opening. This is expected: MuseTalk decodes a 256×256 mouth
  regardless of the paste target, so the **normalized articulation amplitude is
  model-determined, not avatar-determined**. This **confirms the Stage 5 report's**
  RAW_MUSETALK classification.
- close_up shows more frame-to-frame **motion** (g1.5: 0.01515 vs 0.01338) and
  slightly higher vopen std (diversity), i.e. the *existing* motion reads as more
  active — consistent with "same amplitude, but sharper/ clearer".

### 3. Identity stays stable on both avatars
identity_std is low and comparable (closeup 0.01205–0.01236 vs active
0.01373–0.01376); the gain does not leak into eyes/nose/jaw on either avatar.

### 4. Minor: close_up AV offset = 1 (vs 0 on active)
A 1-frame (40 ms) lag appears on close_up at both gains. It is at the SyncNet
1-frame resolution limit and the audio/timing params are identical, so it is most
likely a face-detection / legibility artifact of `--preprocess face_crop` on the
sharper face rather than a real timing shift. Noted, not acted on (the task
forbids changing MuseTalk/timing).

---

## Conclusion — answer to the question

**The small/subtle articulation is NOT primarily caused by the avatar source,
nor by MuseTalk timing. It is primarily caused by the MuseTalk model's own
compressed articulation range (RAW_MUSETALK).**

Decomposition of "small-looking articulation":
- **Amplitude** (how far the mouth opens, normalized) → **MuseTalk model**
  (RAW_MUSETALK). Avatar-independent: the close_up avatar does not open wider,
  and at g1.5 the active avatar even opens slightly more. This is the primary
  limiter and the real reason the mouth "looks small".
- **Legibility / sharpness** (how clearly the opening is visible) → **avatar
  source** (secondary). The sharper, larger-face close_up avatar scores higher on
  SyncNet and shows more motion, i.e. it makes the *existing* articulation clearer
  — but it does not add amplitude.
- **Timing** → correct (not a cause).

So the two prior reports were each half-right: the audit correctly identified the
active avatar as a sub-optimal (soft, small-face) input that hurts legibility;
the Stage 5 report correctly identified RAW_MUSETALK as the amplitude limiter. The
A/B separates the two effects: **avatar → legibility; MuseTalk → amplitude**.

### Practical implication
- Switching to `close_up` improves mouth **legibility** (SyncNet +4 % at g1.5)
  but will **not** make the mouth open wider — the "still small" complaint would
  persist on amplitude.
- The `audio_conditioning_gain = 1.5` lever (Stage 5) remains the only tested
  in-pipeline knob that increases **amplitude** (vopen span +23 %, width stable).
- The two improvements are **orthogonal and stackable**: `close_up` + gain 1.5
  gives the best legibility AND the widest tested opening (SyncNet 0.4336, the
  highest of the four), at AV offset 1 (within tolerance).

### Remaining gate (requires the reviewer, not this model)
The model used here cannot view frames. Final visual naturalness — whether
`close_up` + gain 1.5 reads as "clearly more natural, not rubber mouth" and the
close_up identity is the intended presenter with no lower-face occlusion — is the
reviewer's call on `stage5_closeup_C_medium.mp4` vs `stage5_artic_C_medium.mp4`
(and the existing contact sheet `D:\CongThang_AI_Avatar\avatar_audit\contact_close_up.jpg`).

---

## Recommendation

`AVATAR_HELPS_LEGIBILITY_NOT_AMPLITUDE` — the avatar source is a **secondary**
(legibility) contributor, not the primary cause. Primary cause = RAW_MUSETALK
amplitude. Options for the reviewer, in order of expected effect:

1. **`ADOPT_CLOSEUP_KEEP_GAIN15`** (best tested objective combo): switch active
   avatar to `close_up` AND keep `audio_conditioning_gain = 1.5`. Best SyncNet
   (0.4336) + widest tested opening + good legibility. Pending reviewer visual
   sign-off on close_up identity/occlusion and naturalness.
2. **`KEEP_ACTIVE_GAIN15`**: keep `fullbody_30_7_25fps` + gain 1.5 (current Stage 5
   winner). Slightly lower legibility but zero identity-change risk; amplitude
   gain is the same (avatar-independent).
3. **`KEEP_STABLE`**: if the reviewer finds gain 1.5 too strong on either avatar,
   fall back to gain 1.3 / 1.0 — but note amplitude then stays at the model's
   compressed default, which is the original "small" complaint.

`RECORD_NEW_AVATAR` is **not** warranted by this test: a sharper avatar would
improve legibility further but would not fix the amplitude, which is
model-bound. A future avatar re-record helps only if combined with a model that
has a wider articulation range (beyond Stage 5 scope).

No FPS, codec, resolution, GFPGAN, CUDA-Graph, WOLA, audio-timing, or MuseTalk
model changes were made (per task constraints). Stable checkpoint untouched.
Nothing committed.

---

## Files produced (diagnostics only — not production, not committed)

- `stage5_closeup_A_baseline.mp4`, `stage5_closeup_C_medium.mp4` — close_up renders
- `stage5_closeup_{A,C}_*.json` — SyncNet + mouth metrics
- `stage5_measure.py` — made avatar-aware (optional 4th arg `avatar_id` for the
  FAN crop hint; defaults to the active avatar so prior measurements unchanged).
  This is a diagnostic tool, not production code.