# Output Quality Acceptance Checklist

Apply to every important production render before delivery. Subjective quality must NOT be fully automated — a human reviews.

## VIDEO
- [ ] Opens successfully
- [ ] Correct Avatar
- [ ] Correct content (script matches)
- [ ] Correct voice
- [ ] Audio present (not silent)
- [ ] No freeze / hang
- [ ] No obvious frame corruption
- [ ] Mouth moves naturally enough
- [ ] No obvious mask/chin artifact
- [ ] No severe AV drift (audio vs mouth)
- [ ] Full duration (not truncated)
- [ ] Correct resolution 1080×1920, ~25 fps (post-render verify checks this automatically; confirm visually too)
- [ ] **Final output manually reviewed**

## If a check fails
- Re-render. If the issue is avatar-level (small mouth, artifacts), try a different avatar or re-create the avatar from a better source (see CUSTOMER_SOURCE_ACCEPTANCE_CHECKLIST.md).
- If the issue is audio/voice, verify the Voice ID and ElevenLabs/Edge TTS config before re-rendering.

## Automated checks already enforced (studio/verify.py)
File exists + size > 1000 + video stream + audio stream + 1080×1920 + ~25 fps + duration ≥ 0.3s. A render that fails these is marked Lỗi, not Hoàn tất.