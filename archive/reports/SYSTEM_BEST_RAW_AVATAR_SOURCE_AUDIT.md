# SYSTEM — Best Raw Avatar Source Audit

> **Discovery and quality assessment only.** No source files, production config,
> prepared avatars, or renders were modified. `config/render_truth.json` and
> `SYSTEM_CONTROL_BOARD.md` were read only and left untouched.
>
> Branch rule: this project tree is not a git repo on disk; per the control board the
> authoritative branch is **main**. Audit performed 2026-08-26.

This audit evaluated **ORIGINAL UNPROCESSED VIDEO FILES** — not prepared MuseTalk
avatar folders (`full_imgs/`, `latents.pt`, `coords.pkl`, `mask/`, `mask_coords.pkl`)
and not rendered/AI-generated outputs.

---

## Best Raw Source

The best **unprocessed, original** avatar-input video currently stored on the system:

```
C:\CongThang\AI_avatar\test17_8\Close Up.mp4
```

(1080×1920, 60 fps, 29.4 s, h264/yuv420p, ~14.2 Mbps, md5 `a502bdedafde6e4b37fb5840f23e202f`.)

**Important caveat — it is NOT better than the source behind the current production
avatar `close_up`.** The `close_up` original raw file is **missing** from the system
(see "Current close_up source comparison"); only its prepared avatar survives, and
that prepared avatar measures *better* (larger face, sharper face) than any surviving
raw video. So the file above is the best **surviving** raw, not the best possible.

---

## Top Candidate Ranking

Ordered by **avatar-suitability** (face size and framing for mouth articulation are
weighted heaviest, per the production issue: subtle / small visible articulation). CV
measurements via OpenCV on 6 sampled frames (0/20/40/60/80/100%). Pose = frontal face
detector + face aspect-ratio; mouth/chin = geometric region-in-frame check; source
mouth = Laplacian-variance proxy of the mouth region (low ≈ neutral, high ≈ talking).

| Rank | Raw source | Resolution | Face size (px @1080×1920) | Sharpness | Pose | Mouth | Chin | Source mouth | Score | Grade |
|---|---|---|---|---|---|---|---|---|---|---|
| — (baseline, not raw) | `close_up` prepared proxy (original MISSING) | 1080×1920 | 202 | 315 | frontal | PASS | PASS | neutral* | 86.6 | A+ |
| 1 | `C:\CongThang\AI_avatar\test17_8\Close Up.mp4` | 1080×1920 | 197 | 226 | frontal | PASS | PASS | TALKING | 68.1 | B |
| 2 | `C:\CongThang\AI_avatar\test17_8\Full Body (2).mp4` | 1080×1920 | 139 | 287 | frontal | PASS | PASS | STRONG_TALKING | 71.0 | B |
| 3 | `C:\CongThang\AI_avatar\experiments\master_plus\inputs\body_closeup.mp4` (LIKELY_DERIVED, 9 s) | 1080×1920 | 198 | 262 | frontal | PASS | PASS | TALKING | 68.1 | B |
| 4 | `C:\CongThang\AI_avatar\record_av.mp4` | 1080×1920 | 176 | 93 | frontal | PASS | PASS | LIGHT_TALKING | 60.8 | B |
| 5 | `C:\CongThang_AI_Avatar\AI_avatar\data\avatars\.uploads\musetalk_8960_6881921.mp4` (4K, = 30_7_fullbody source) | 2160×3840 | 143 | 24.6 | frontal | PASS | PASS | NEUTRAL | 40.0 | D |
| 6 | `C:\CongThang\AI_avatar\experiments\master_plus\inputs\body_fullbody.mp4` (LIKELY_DERIVED, 9 s) | 1080×1920 | 141 | 270 | frontal | PASS | PASS | STRONG_TALKING | 66.7 | B |
| 7 | `C:\CongThang\AI_avatar\experiments\master_plus\inputs\body_halfbody.mp4` (landscape, 9 s) | 1280×720 | 395 | 192 | frontal | PASS | PASS | LIGHT | 58.9 | B |
| 8 | `C:\CongThang\AI_avatar\Hearing-1.mp4` | 2160×3850 | 165 | 16.4 | frontal | PASS | PASS | NEUTRAL_CLOSED | 40.0 | D |

*`close_up` source-mouth marked neutral from its prepared-avatar behavior; raw mouth
signal unavailable because the original raw is gone.

Critical-failure overrides applied: any source with face-region sharpness < 40 is
capped at score 40 (D). This **disqualifies the 4K `.uploads` source
(`musetalk_8960_6881921.mp4`) and `Hearing-1.mp4`** despite their 4K resolution —
their faces are small (full-body framing) and soft. Resolution alone does not help
when the face fills only ~7–9% of the frame and is blurry.

---

## Duplicate Groups

MD5 over all serious candidates:

| md5 | canonical path | duplicate paths |
|---|---|---|
| `bfd1f79f4b2fa44800604afdb23a44af` | `C:\CongThang_AI_Avatar\AI_avatar\data\avatars\.uploads\musetalk_8960_6881921.mp4` | `…\.uploads\musetalk_10804_5835750.mp4` (orphan, not referenced by any avatar); `C:\CongThang\AI_avatar\data\avatars\.uploads\musetalk_8960_6881921.mp4` (second project copy). One unique 4K recording. |
| `a502bdedafde6e4b37fb5840f23e202f` | `C:\CongThang\AI_avatar\test17_8\Close Up.mp4` | (none) |
| `66d73b4674659bbc7b6494c638c64a64` | `C:\CongThang\AI_avatar\test17_8\Full Body (2).mp4` | (none) |
| `7811961a761b15eca1b938fc1e03fd4a` | `C:\CongThang\AI_avatar\Hearing-1.mp4` | (none) |
| `7bc7a8e3d4c5e33cad283cfb39905503` | `C:\CongThang\AI_avatar\record_av.mp4` | (none) |
| `471cde69747594492f7f6eecb2994f79` | `…\master_plus\inputs\body_closeup.mp4` | (none) |
| `fb60b819836ff055ab996746e99c236b` | `…\master_plus\inputs\body_fullbody.mp4` | (none) |
| `a26d3c43f36beb1fed8781f4955f7e10` | `…\master_plus\inputs\body_halfbody.mp4` | (none) |

The 4K `.uploads` group is **one** recording (md5 `bfd1f79f…`) present as 3 byte-identical
copies. Not ranked separately.

---

## Prepared-avatar → original-source trace (existence verified on disk)

From each `avator_info.json` `video_path` field, checked against the live filesystem:

| avatar_id | referenced original source path | exists on disk? |
|---|---|---|
| `close_up` | `D:\Noble\livetalking\data\avatars\.uploads\musetalk_4872_697362812.mp4` | **NO** (D:\Noble does not exist) |
| `fullbody_30_7_25fps` / `_jaw` / `_mouth_chin` / `_stable` | `C:\Users\Admin\Videos\30_7\Closeup.mp4` | **NO** |
| `30_7_fullbody` | `D:\AI_avatar\data\avatars\.uploads\musetalk_8960_6881921.mp4` | **NO** at that path — but an identical-md5 copy survives at `C:\CongThang_AI_Avatar\AI_avatar\data\avatars\.uploads\…` (relocated) |
| `23_7_avt` | `D:\AI_avatar\…\musetalk_15332_132232453.mp4` | NO |
| `30_7close` | `D:\AI_avatar_ship\…\musetalk_5412_642100515.mp4` | NO (D:\AI_avatar_ship does not exist) |
| `close_up_16_7` | `D:\AI_avatar\…\musetalk_16920_62453968.mp4` | NO |
| `fulbody_2_8` | `D:\AI_avatar\…\musetalk_8372_146445203.mp4` | NO |
| `full_body_16_7` | `D:\AI_avatar\…\musetalk_16920_70558687.mp4` | NO |
| `fullbody_30_7` | `D:\AI_avatar\…\musetalk_3164_7289750.mp4` | NO |
| `mc_hamai_mid` | `C:\CongThang_AI_Avatar\AI_avatar\input_25_8\Input\MID\Ver 1\MID_1.png` | YES (single photo, not a video) |

**Conclusion:** Of all 11 prepared avatars traced, only **one** has a surviving
original video source (`30_7_fullbody` → the 4K `.uploads` file, relocated). The
current production `close_up` avatar's raw original is **gone** — only the prepared
avatar (980 frames) remains.

---

## Current close_up source comparison

- **Current `close_up` original source (from metadata):**
  `D:\Noble\livetalking\data\avatars\.uploads\musetalk_4872_697362812.mp4`
- **Status:** MISSING. `D:\Noble` does not exist on this machine. The prepared avatar
  `data/avatars/close_up/` (980 PNG frames at 1080×1920) is the only surviving
  representation and was used as a **proxy baseline** for face metrics.

**Is the best discovered raw source better than the current close_up source?**

```
NO
```

Comparison of best raw (`test17_8\Close Up.mp4`) vs current `close_up` (proxy):

| Metric | best raw (test17_8 Close Up) | current close_up (proxy) | delta |
|---|---|---|---|
| Face height at 1080×1920 output | 197 px | 202 px | close_up +2.5% larger |
| Face-region sharpness (Laplacian var) | 226 | 315 | close_up +39% sharper |
| Source mouth state | TALKING | neutral (per avatar behavior) | close_up better (neutral preferred) |
| Frontal pose | PASS | PASS | tie |
| Mouth visibility | PASS | PASS | tie |
| Chin/jaw visibility | PASS | PASS | tie |
| Grade | B (68.1) | A+ (86.6) | close_up higher |

The best stored raw is **close but inferior** to the current `close_up` source on the
two metrics that matter most for MuseTalk articulation — face size and face sharpness
— and it carries a talking (non-neutral) mouth, which is suboptimal for MuseTalk
template extraction.

---

## Why the winner should produce better output

The winner, `C:\CongThang\AI_avatar\test17_8\Close Up.mp4`, is the **best surviving
raw original** because, among all stored unprocessed videos:

- **Largest usable face among true camera originals** — 197 px face at 1080×1920
  (10.3% of frame height), close-up framing. Larger face → more lip/teeth pixels for
  MuseTalk → clearer articulation (directly addresses the small-articulation issue).
- **Frontal, near-frontal pose** — frontal detector hit on all 6 sampled frames.
- **Mouth and chin/jaw fully in frame** on all samples (PASS / PASS) — suitable for
  jaw-mode and mouth_chin-mode MuseTalk processing.
- **Genuine camera original** — 60 fps, 29.4 s, h264, not a re-encoded experiment clip.

It beats the 4K `.uploads` source (which is 4K but a full-body shot with a 143 px,
blurry face — sharpness 24.6 — so 4K resolution is wasted) and beats
`Hearing-1.mp4` (4K but 8 s and very soft, sharpness 16.4).

**However**, it would *not* beat the current `close_up` output, and its talking
(non-neutral) source mouth is a drawback. See Limitations.

---

## Limitations

1. **The current `close_up` raw original is missing.** Comparisons against `close_up`
   use its *prepared* frames as a proxy, not the original raw — sharpness/face numbers
   are from re-extracted PNGs and may differ slightly from the raw.
2. **No stored raw combines a large sharp face with a neutral mouth.** The best-face
   raws (`test17_8\Close Up.mp4`, `master_plus\body_closeup.mp4`) show **talking**
   source mouths; the neutral-mouth sources (`uploads_4k`, `Hearing-1`) have small,
   blurry faces. This is a real tradeoff, not a measurement artifact.
3. **Pose yaw is estimated from the Haar frontal-face hit + face aspect ratio**, not
   from facial landmarks (mediapipe not installed; no landmark model on disk). All
   candidates passed the frontal check, consistent with their being talking-head
   recordings, but subtle yaw/tilt is not quantified. Human review of the contact
   sheets is recommended for pose/mouth-state confirmation.
4. **`master_plus\inputs\body_*` clips** (9.08 s, 25 fps) are classified
   `LIKELY_DERIVED` (re-encoded/trimmed experiment segments), so they are not primary
   raw-original candidates despite competitive sharpness. `body_halfbody` is
   additionally landscape (1280×720) with high motion — disqualified.
5. **Excluded per spec:** `D:\CongThang_AI_Avatar\noble_live_25_8\*` (lecture content),
   `C:\CongThang\Video_demo\…\Closeup_phan2.mp4` (4K but a 278 s edited lecture part),
   all `renders/`/output folders, and all prepared frame folders — none are clean
   avatar-template camera footage.
6. `Hearing-1.mp4` (2160×3850, 8.3 s) resolves to a **D** — very soft face + too short
   to be a master avatar source; treated as a test clip, not recommended.

---

## Recommendation

**Recommended next action:** `SOURCE_GOOD_BUT_NEEDS_NEW_RECORDING`

Rationale:

- A good raw source exists and is the best stored: `C:\CongThang\AI_avatar\test17_8\Close Up.mp4` (B, 68.1).
- It is **not better** than the current `close_up` source (A+ proxy, +2.5% face, +39% sharper, neutral mouth). Switching the master avatar to it would **not improve** output and could degrade it (smaller face, talking mouth).
- The current `close_up` raw original is **missing**, so it cannot be re-graded or re-derived from raw; the prepared `close_up` avatar should be **kept in production** meanwhile.
- To actually improve the subtle/small articulation, record a **new close-up 4K (vertical 2160×3840)** clip with: neutral-closed or light-idle mouth, face filling ~25–35% of frame height, stable lighting, frontal pose, minimal motion blur, ≥20 s. That is the only path to beat the current `close_up`.

Do **not** prepare or render the winning raw yet. This audit only recommends the next step.

---

## Human-review contact sheets

```
D:\CongThang_AI_Avatar\avatar_source_audit\
  rank00_close_up_CURRENT_proxy.jpg      (baseline: current close_up prepared frames)
  rank01_test17_8_close_up.jpg           (BEST RAW — winner)
  rank02_uploads_4k_30_7.jpg             (4K proven source, blurry full-body)
  rank03_test17_8_full_body.jpg           (sharp, small face)
  rank04_master_plus_body_closeup.jpg    (sharper, likely derived, 9 s)
  rank05_uploads_4k_HEARING1.jpg          (4K, soft, 8 s)
```

Generated with OpenCV (6 frames per source: 0/20/40/60/80/100%). For human visual
verification only — no video files were modified.

---

## Method / non-modification statement

- Branch rule: authoritative branch is `main` (control board). Tree is not a git repo
  on disk; no git operations performed.
- `SYSTEM_CONTROL_BOARD.md` and `config/render_truth.json` were **read only**; not
  modified.
- All measurements are numeric (ffprobe + OpenCV). No image or video content was
  loaded into the model. Contact sheets are written to disk for human review only.
- No source files, prepared avatars, renders, or configs were modified.
- Scripts written for this audit: `experiments/avatar_source_cv_audit.py`,
  `experiments/avatar_source_contact_sheets.py`; data:
  `avatar_source_audit_cv.json`, `avatar_source_audit_scores.json` (at
  `C:\CongThang_AI_Avatar\`).