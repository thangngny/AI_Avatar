# Master Avatar Source Spec

> Purpose: a short brief a camera operator can follow to record the **one** master
> avatar source that fixes the remaining small/narrow mouth-articulation problem.
> Production render config is NOT changed by this — only the source/avatar input.

The current production avatar `close_up` is the best prepared avatar, but its
original raw source is **missing**. The best surviving raw
(`C:\CongThang\AI_avatar\test17_8\Close Up.mp4`) is only a fallback because the
subject is **talking** in it. No surviving raw source materially beats `close_up`,
and the geometry sweep (extra_margin / parsing_mode) on close_up's identity gave
only a marginal crop change. Therefore a **new master recording** is required.

---

## A. HUMAN-SIMPLE VERSION (for the camera operator)

Record **one** vertical video of the person, then send the **original file** (not a
re-encoded/compressed copy).

Do:
- **Vertical** phone/camera (portrait, 9:16). 1080×1920 or 4K (2160×3840).
- Stand **close**: head + upper chest fill the frame. The face should be **large**
  (head roughly from shoulders to near the top of the frame — not a full-body shot).
- Look **straight at the lens**, head level. No tilt, no turning away.
- **Do NOT talk.** Mouth closed and relaxed, neutral expression. Light closed-mouth
  breathing is fine. (A talking source bakes an open mouth into the avatar.)
- Lips and **full chin and jaw** visible — no hand, mic, or hair over the mouth/chin.
- **Natural small motion**: blink normally, tiny head sway, breathing. Do NOT freeze
  stiff; do NOT move energetically. No walking, no gesturing.
- **Fixed camera** on a tripod, stable. No handheld shake.
- **Stable, even lighting** on the face. No flicker, no strong shadows on the lips.
- Sharp focus on the face. Avoid motion blur.
- Record at least **30–60 seconds**. 25/30 fps is fine (60 fps is also OK).

Don't:
- Don't talk, smile wide, or move the head around.
- Don't record full-body from far away (face too small = the current problem).
- Don't move the camera or walk.
- Don't apply beauty filters / heavy compression. Send the original high-quality file.

---

## B. TECHNICAL ACCEPTANCE VERSION (run the source-quality gate)

Validate with (offline, no mutation of the file):

```
python tools/avatar_source_quality/validator.py --video <file> --json report.json
```

Acceptance criteria (overall = PASS, no FAIL category):

| Category | Required | Target |
|---|---|---|
| VIDEO_INTEGRITY | PASS | ≥1080×1920, ≥25 fps, ≥30 s, opens cleanly |
| FACE_SIZE | PASS | face_h / frame_height ≥ 0.16 (close-up) — current close_up is only 0.116; a larger face is the key lever for articulation |
| FACE_SHARPNESS | PASS | Laplacian var on face crop ≥ 150 (current close_up ≈ 282; failing 4K full-body sources were 16–26) |
| FRONTALNESS | PASS | frontal_ratio ≥ 0.8; both eyes visible |
| MOUTH_VISIBILITY | PASS | mouth region fully in frame on all samples |
| CHIN_VISIBILITY | PASS | full chin/jaw below face (chin_ratio ≥ 1.0) |
| SOURCE_MOUTH_STATE | PASS | NEUTRAL_CLOSED or NEUTRAL_SLIGHTLY_OPEN (talking_proxy < 0.02). A talking source is a WARN/FAIL — this is the main reason test17_8 is only a fallback |
| MOTION | PASS | median frame-to-frame diff ≤ 3 (natural breathing/blink, no shake/walk) |
| LIGHTING | PASS | luma std across samples ≤ 2 (stable, no flicker) |

Notes:
- Resolution alone does NOT pass the gate. A 4K full-body source with a tiny face
  FAILS (this was the case for the existing 4K `.uploads` source: 2160×3840 but
  face_h_ratio 0.074, sharpness 25.6 → FAIL). Usable face pixels and neutral mouth
  dominate the ranking.
- The current best prepared avatar (`close_up`) has face_h_ratio ≈ 0.116 — usable
  but on the small side. The new master should target **≥ 0.16** (a meaningfully
  larger face) to give MuseTalk more lip/jaw pixels to work with.
- Prefer the **original file** (high bitrate, low compression). Re-exporting through
  messaging/social apps recompresses and can drop FACE_SHARPNESS below threshold.

If a candidate passes, prepare it with the canonical v1.5 path into a NEW avatar id
(never overwrite `close_up`):
```
python -m avatars.musetalk.genavatar --file <master.mp4> --avatar_id <new_id> \
  --version v15 --extra_margin 10 --parsing_mode jaw \
  --left_cheek_width 90 --right_cheek_width 90 --bbox_shift 0
```
then A/B it against `close_up` under the locked render truth before any promotion.