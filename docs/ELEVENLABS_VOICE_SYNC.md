# ElevenLabs Voice Sync (V1.5.0)

AI Avatar Studio now **automatically syncs each ElevenLabs voice's real
configuration** so the Studio generation matches what you hear on ElevenLabs —
you no longer need to copy stability/similarity/style/speaker-boost/speed
sliders by hand.

## Why
The same Voice ID can sound different between ElevenLabs and Studio because
TTS depends on `model_id` + `voice_settings` + `output_format`, not just the
Voice ID. Before V1.5.0, Studio used one hardcoded setting set for every voice.

## Normal user flow
1. In **Tạo video từ Avatar có sẵn → Step 3 (Giọng)**, choose **ELEVENLABS** and
   paste your **Voice ID**.
2. Click **Kiểm tra giọng**. Studio validates the voice **and** automatically
   fetches that voice's current settings from ElevenLabs (server-side; the API
   key never leaves the backend).
3. You see a truthful status line:
   - `✓ Đã đồng bộ cấu hình ElevenLabs` — a matching ElevenLabs generation was
     found and its model/output were resolved.
   - `✓ Đã đồng bộ cài đặt giọng · Model đầu ra đang dùng cấu hình Studio` — the
     voice settings synced, but no matching generation was found, so the model/
     output use Studio policy. For an exact match, use Mode B (below).
4. Continue to **Tạo video**. The resolved config is snapshotted into the job.

> **Note:** TTS is a generative model — results may have small variations
> between generations. "Sync" means **config match**, not a guaranteed
> identical waveform.

## Optional: match a specific ElevenLabs generation (Mode B)
Under **Cấu hình giọng — đồng bộ ElevenLabs**, open the **Khớp bản đã tạo** tab,
click **Tải lịch sử**, pick one of your recent ElevenLabs generations, and click
**DÙNG CẤU HÌNH NÀY**. Studio imports that generation's public
`model_id` / `voice_settings` / `output_format` (the history text is **not**
imported into your script — only the config).

## Advanced (Mode C)
**Tùy chỉnh** lets a technical user set model / stability / similarity / style /
speaker boost / speed / output format manually.

## Failure handling
If the ElevenLabs settings API is unreachable, Studio shows
`Không thể đồng bộ cấu hình ElevenLabs.` and offers **THỬ LẠI** or
**DÙNG CẤU HÌNH STUDIO** (explicit choice — it never silently falls back).

## For operators / technicians
- **API key:** server-side only (`.env` `ELEVENLABS_API_KEY`). Never returned to
  the browser, never stored in jobs/logs/diagnostics.
- **Generic per voice:** no voice-id special-casing; nothing Thanh-specific is
  hardcoded. Each Voice ID resolves its own config; switching Voice ID clears
  the previous config (no leak). A queued job keeps its snapshotted config.
- **Two-audio-path (audio fidelity):** the lossless ElevenLabs **master** (at
  the resolved `output_format`'s native sample rate) is used for the **final MP4
  audio**; a separate 16 kHz mono **conditioning** copy is derived for
  MuseTalk/Whisper only. MuseTalk/lipsync truth is unchanged.
- **Caching:** voice settings 5 min, models 30 min, history 2 min. **LÀM MỚI**
  bypasses the cache.
- **Job metadata:** each render job stores `tts_config` (sanitized JSON),
  `tts_config_hash`, `sync_mode`, `history_item_id`. History cards show a
  `Đồng bộ` / `Match History` / `Cài đặt giọng` / `Tùy chỉnh` badge.
- **Edge TTS** (TEST MIỄN PHÍ) is unaffected — it never calls ElevenLabs config
  endpoints.
- **Production truth unchanged:** MuseTalk v1.5 · gain 1.5 · ctx 0 · offset -3 ·
  25 FPS · 1080×1920 · CUDA Graph ON · WOLA ON · Coverage Guard ON.