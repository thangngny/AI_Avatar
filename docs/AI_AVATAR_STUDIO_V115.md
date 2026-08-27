# AI Avatar Studio UI V1.1.5

> Guided avatar input + sample video + free mouth-motion test (Edge TTS).
> Production MuseTalk v1.5 truth is **unchanged** — both voice paths feed the
> SAME locked production renderer.

## What changed

### Part A — Guided Create Avatar input

The Create Avatar view is now a guided flow: see a sample → understand
requirements → upload → automatic check → user decision → prepare.

- **Requirements panel** (always visible): 30–60 giây, khung dọc 9:16, khuôn
  mặt đủ lớn, góc gần chính diện, không nói, cằm/đường hàm đầy đủ, camera cố
  định, ánh sáng ổn định, chuyển động nhẹ, file gốc chất lượng cao. The
  authoritative duration is **30–60 seconds**
  (`docs/MASTER_AVATAR_SOURCE_SPEC.md`); 20–40 is intentionally NOT used.
- **Detailed NÊN / TRÁNH guide** (collapsible) + schematic framing diagram.
- **Pre-upload checklist** (informational, not mandatory).
- **Post-upload comparison** ("KIỂM TRA VIDEO CỦA BẨN") with per-dimension
  ✓/⚠/✗ and an overall TỐT / CẢNH BÁO / KHÔNG KHUYẾN NGHỊ.
- **Manual mouth-state confirmation** (spec A10/A11): V1.1.4 proved the
  automatic `talking_proxy` cannot reliably separate talking vs neutral in the
  normal range, so the user confirms explicitly. Stored SEPARATELY:
  `mouth_state_auto` (raw evidence, never overwritten), `mouth_state_user`
  (`NOT_TALKING` / `TALKING` / `UNSURE`), `mouth_state_provenance`
  (`AUTO` / `USER_CONFIRMED` / `UNKNOWN`). If the user says "Có nói", a warning
  is shown with overridable [Chọn video khác] / [Vẫn sử dụng video này].
- **Face size**: the `face_h / frame_height >= 0.16` target is a
  RECOMMENDATION, not a hard block. The UI shows "Khuôn mặt đủ lớn" / "Hơi nhỏ"
  wording, never the numerical ratio on the normal screen (advanced details
  may show it). A source is never rejected solely for a ratio below 0.16.
- **Resolution**: never claims "4K = good avatar". Face size in frame is
  stressed over raw resolution; a 4K full-body source with a tiny face still
  gets a face-size warning.

### Sample video (spec A7/A8/H)

A reusable sample-video slot probes `/api/avatar/sample`. If a human-approved
compliant raw-source MP4 + `manifest.json` exists under
`studio/static/assets/avatar_source_example/`, the slot shows a video player
with play/pause/mute/seek (no autoplay audio) and the compliance checks.
Otherwise it shows the honest pending state:

> "Video mẫu chuẩn đang được cập nhật."

plus the schematic framing guide. **No fabricated real-person sample.** Known
talking sources (e.g. `test17_8/Close Up.mp4`) are explicitly NOT used as the
ideal-source example.

**SAMPLE VIDEO status: `SAMPLE_ASSET_PENDING_HUMAN_APPROVAL`** — one
human-approved compliant MP4 + `manifest.json` is required to flip this to
`REAL_COMPLIANT_SOURCE`.

### Part B — Free mouth-motion test (Edge TTS)

Quick Render now offers TWO explicit voice sources:

1. **ELEVENLABS** — production voice. Exact Voice ID, fail-closed, no
   fallback. Unchanged from V1.1.4.
2. **TEST MIỄN PHÍ — EDGE TTS** — no API key, no ElevenLabs quota. Intended
   ONLY for testing mouth motion / mask / chin / lipsync, not final voice
   production.

- Vietnamese voices: `vi-VN-HoaiMyNeural` (Nữ — Hoài My, default) and
  `vi-VN-NamMinhNeural` (Nam — Nam Minh), discovered dynamically at runtime
  with a known-voice fallback.
- Voice tuning FIXED at rate/pitch/volume = +0 (spec B6) so comparisons stay
  consistent. No voice-tuning panel in MVP.
- Edge TTS audio is decoded/resampled to the canonical **16 kHz mono FLOAT
  WAV** (same master-audio format as ElevenLabs), then fed to the SAME
  `generate_video_from_script.py` → MuseTalk v1.5 renderer. No second lipsync
  engine.
- **Standard mouth test** (spec B9/B10/B11): a dedicated
  `TEST KHẨU HÌNH 10 GIÂY (MIỄN PHÍ)` action uses the standardized Vietnamese
  diagnostic script:
  > "Ba mẹ mỉm cười và Minh mua một hộp bánh mì. Phương nói hôm nay trời đẹp,
  > chúng ta cùng quay video thật tự nhiên."
  containing bilabials (m/b/p), wide/open + rounded vowels, and natural
  sentence flow. `test_type = STANDARD_MOUTH_TEST` makes Avatar A vs Avatar B
  comparable under identical text/voice/profile. The renderer is NOT optimized
  for this sentence; it is only a repeatable visual test stimulus.

### Provider contract (spec B8/C) — NO silent fallback

- Edge TTS fails → honest error ("Giọng test miễn phí hiện không khả dụng."),
  never silently calls ElevenLabs.
- ElevenLabs fails → never silently uses Edge.
- Providers remain explicit at all times.

### Privacy (spec Part I)

Edge TTS is an ONLINE service. A notice in Settings states that test text is
sent to the TTS service. No API keys, avatar video, or prepared images are
sent — only the test text.

### Render history / metadata (spec Part D/E)

Each job records `tts_provider`, `voice_id`, `test_mode`, `test_type`,
`edge_voice`. History visually distinguishes `BẢN TEST` / `BẢN TEST KHẨU HÌNH`
/ `BẢN PRODUCTION` with an Edge TTS / ElevenLabs provider tag. No API secret is
ever stored.

## Future provider (spec B14) — NOT implemented

Azure Speech Free F0 offers a monthly free Neural TTS allowance but requires
an Azure account + Speech resource + API credentials. It is documented as a
possible future official provider only. V1.1.5 has exactly two user-facing
voice paths: ElevenLabs + Edge TTS free test.

## Production truth — unchanged

`config/render_truth.json` is read-only and unmodified:

| parameter | value |
|---|---|
| pipeline | musetalk_v15 |
| audio_gain | 1.5 |
| audio_context_left | 0 |
| audio_feature_offset_frames | -3 |
| fps | 25 |
| resolution | 1080×1920 |
| cuda_graph | ON |
| long_audio_wola | ON |
| feature_coverage_assertion | ON |

`generate_video_from_script.py` lipsync behavior, MuseTalk inference,
Whisper/WOLA, mask geometry, production timing, and production gain are all
unchanged.

## Tests

- `tests/test_studio.py` — extended with Edge TTS, mouth-test, mouth-state,
  sample-endpoint, edge-route, and locked-truth tests (49 tests, all pass).
- `tests/e2e_mouth_test.py` — real end-to-end free mouth-test render
  (spec Part G TEST B). Run with the torch env python.

## Real E2E results (this build)

- TEST A — real free Vietnamese Edge TTS audio: 16 kHz mono FLOAT wav, ~5.8s.
- TEST B — real free mouth-test MP4 (`doTrang_closeup`, Hoài My): 1080×1920,
  25 fps, 8.08 s, audio present, ElevenLabs NOT called. `PROVEN_REAL`.
- TEST C — ElevenLabs regression: configured, model `eleven_turbo_v2_5`,
  `pcm_16000`, exact-voice fail-closed path intact, production Voice ID
  reachable.
- TEST D — Create Avatar guidance: all requirement strings present.
- `python system_status.py` — Production Truth: VALID, Ready: YES.