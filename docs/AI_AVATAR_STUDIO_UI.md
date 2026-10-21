# AI Avatar Studio UI — Operator Guide

AI Avatar Studio is a **local Windows operator UI** for the existing, validated
AI Avatar / MuseTalk v1.5 production system. It is a *controller*, not a second
rendering system. It makes the current workflow easy; it does **not** introduce a
competing pipeline.

```
UI  →  Application Controller  →  Existing validator / avatar prep / TTS / renderer
                                 →  Existing MuseTalk v1.5 production system
```

## How to launch

Double-click **`AI_Avatar_Studio.bat`** in the repo root, or run:

```
python run_studio.py
```

The launcher starts the local Flask controller and opens the browser at
`http://127.0.0.1:8077`. The operator does not need to launch multiple
terminals. The controller runs in the torch-capable interpreter
(`C:\CongThang\AI_avatar\latentsync_env`) so it can spawn the production
entrypoints as subprocesses.

> The CLI production renderer (`generate_video_from_script.py`) still works
> independently. The UI is **not** mandatory for CLI production use.

## Quick Render (default screen)

Workflow: **Avatar → Script → Voice ID → TEST 10s → RENDER VIDEO**.

1. **Avatar** — select a prepared (READY) avatar from the dropdown, or
   **＋ Add New Avatar** (jumps to Create Avatar).
2. **Script** — upload a `.docx`/`.txt` file **or** paste text. The UI shows the
   word count and an estimated speech duration.
3. **ElevenLabs Voice ID** — paste the exact Voice ID (e.g.
   `pGapy9MNHCukzJtjavF0`). Click **Check Voice** to verify it and see the
   voice name/labels. Click **▶ Preview Voice** to hear ~9s of the script in
   that voice.
4. **Length** — choose Full Script / First 30s / First 1 min / First 3 min /
   Auto Split.
5. **TEST 10s** — renders ~10 seconds using the **same locked production
   quality** as a full render (no lower-quality test profile).
6. **RENDER VIDEO** — queues the full render.

A read-only production profile banner is shown:
```
MuseTalk v1.5 · 1080×1920 · 25 FPS · Lip-sync LOCKED · Production Verified
```

## Create Avatar

Workflow: **Upload Video → Analyze → Quality Report → User Decision →
Prepare Avatar → Ready**.

1. **Upload** a source video (.mp4/.mov/.avi/.mkv/.webm).
2. **Analyze** runs the existing source-quality validator and reports each
   category in plain language:
   - Face Size, Sharpness, Front View, Mouth Visible, Chin Visible,
     Source Talking, Motion, Lighting.
3. **Quality Report** — shows an overall status (GOOD / WARNING / POOR) and
   human-readable messages, e.g.:
   > "Face is small in the frame. A closer recording may produce clearer
   > mouth movements."
   > "The person is already speaking in the source video. A neutral-mouth
   > source is recommended."
4. **User Decision**:
   - **Choose Another Video** — pick a different source.
   - **Use Anyway & Prepare** — override the warning and proceed.
5. **Prepare Avatar** — enter an Avatar Name. A safe `avatar_id` is generated;
   existing avatars are **never overwritten**. Preparation runs the canonical
   `avatars/musetalk/genavatar.py` (MuseTalk v1.5, `parsing_mode=jaw`).
6. **Ready** — when preparation finishes, click **Use This Avatar** to return
   to Quick Render with the new avatar selected.

### Quality warning behavior

Quality problems (small face, source talking, blur, motion, lighting) are
**warnings, not blocks**. You are always allowed to use a low-quality source
with **Use Anyway**. The override is recorded (`user_override=true/false`) so
future debugging can distinguish low-quality input from renderer problems.

**Technical failures** (unreadable/corrupted file, no face detected, missing
model) are separate: they are *not* quality warnings, the source cannot be
used, and the UI does not offer "Use Anyway".

## Voice ID usage

The primary voice control is a **text input** for the ElevenLabs Voice ID.
Copy the Voice ID from ElevenLabs and paste it. The system verifies it via the
ElevenLabs API and shows real metadata (name, language, gender, style) when
available — it never fabricates metadata.

**Fail-closed:** if the Voice ID is invalid or unavailable, the system shows
an error and **never substitutes a default voice**. No render happens.

The TTS model is fixed to the validated production-batch model
(`eleven_turbo_v2_5`) and is **not** exposed as a user control.

## ElevenLabs key configuration

The API key is stored in `.env` (`ELEVENLABS_API_KEY`), the same file the
existing system uses. It is **never** committed to Git, displayed in full,
put in render manifests, or put in logs. The **Settings** screen shows:

```
ElevenLabs   ● Connected
API Key      ••••••••••••••••347e
TTS Model    eleven_turbo_v2_5
[ Update Key ]
```

You only enter the key once (via Settings → Update Key). It is not required
on every render.

## Test 10s / Full Render

- **TEST 10s** trims the script to ~10s, generates one master audio with the
  exact Voice ID, and invokes the existing production renderer with the
  **locked** `config/render_truth.json`.
- **RENDER VIDEO** creates one job per script part (Auto Split → multiple
  parts) and queues them.

The controller passes only `--avatar_id`, `--audio` (master WAV), and
`--output` to the renderer. The renderer itself forces the locked quality
config. The UI has **no** independent lip-sync truth and exposes **no**
editable gain/ctx/offset/fps/resolution controls.

## Auto Split

Auto Split groups whole sentences into ~3-minute parts. It never cuts a word
or sentence in half, and never invents filler content. The final short part is
rendered as-is.

## Render Queue

The footer queue shows live job state: `QUEUED → PREPARING_AUDIO →
RENDERING → ENCODING → VERIFYING → COMPLETE / FAILED / CANCELLED`, with
honest stage-level progress (frame % is parsed from the renderer when
available; otherwise indeterminate stage labels are shown — no fake
percentages).

One render process runs per GPU (job-level parallelism). The controller
detects the 2 × RTX 3090 and assigns queued jobs to free GPUs automatically.
Normal users never choose a GPU. If only one GPU is free, jobs render
sequentially (reliability over concurrency).

## History

Every job is persisted in a local SQLite database (`data/studio_runtime/`):
job id, time, avatar, script segment, Voice ID, voice metadata, master audio
path, output path, duration, status, quality/override state, and a hash of
`render_truth.json` at job time. The **ElevenLabs API key is never recorded.**

Completed renders stay visible after restart. Failed jobs can be retried
without re-rendering successful parts; voice/model/avatar/config never change
silently during retry.

## Output locations

- Raw avatar sources: `data/input/avatar_sources/`
- Prepared avatars: `data/avatars/<avatar_id>/`
- Temporary audio / previews: `data/studio_runtime/temp/`
- Production renders: `D:\CongThang_AI_Avatar\renders\studio\`
- Database / logs: `data/studio_runtime/`

Large render files are never placed in Git-tracked source folders.

## Troubleshooting

- **ElevenLabs NOT CONNECTED** — set the API key in Settings (or in `.env`).
- **Voice ID invalid** — copy the exact ID from ElevenLabs; the system does
  not fall back to another voice.
- **ElevenLabs quota error (401)** — the account has reached its character
  quota. The render fails closed (no fallback). Top up the account or wait for
  the quota to reset.
- **Avatar not READY** — the prepared-avatar folder is missing required
  artifacts (`full_imgs/ mask/ coords.pkl mask_coords.pkl latents.pt
  avator_info.json` with `version=v15`). Re-prepare it via Create Avatar.
- **No GPU detected** — the controller falls back to a single sequential job
  if `nvidia-smi` is unavailable.
- **Production Truth INVALID** — do not render. Run `python system_status.py`
  to diagnose. The truth file is `config/render_truth.json`.

## Locked production profile (read-only)

The UI never exposes or changes these. They come only from
`config/render_truth.json`:

| Parameter | Value |
|---|---|
| Pipeline | MuseTalk v1.5 |
| audio_gain | 1.5 |
| audio_context_left | 0 |
| audio_feature_offset_frames | -3 |
| FPS | 25 |
| Resolution | 1080×1920 |
| CUDA Graph | ON |
| Long-audio WOLA | ON |
| Feature Coverage Guard | ON |

**Do not edit gain/ctx/offset to "fix" a render.** Those are locked
experimentally-validated values. If a render looks wrong, the cause is almost
always the source avatar or the script, not the locked lip-sync config.

LatentSync remains **experimental only** and is unreachable from this UI.

---

# V1.1 — Giao diện tiếng Việt & Thư viện chất lượng

Từ V1.1, toàn bộ giao diện operator là **tiếng Việt** (điều hướng, nút, nhãn,
cảnh báo, thông báo, trạng thái job, trạng thái hệ thống, cài đặt). Enum kỹ thuật
giữ tiếng Anh ở backend; UI dịch sang tiếng Việt.

## Thư viện AI Avatar — hệ thống đánh giá chất lượng

Thư viện phân biệt hai khái niệm tách biệt:

- **Trạng thái kỹ thuật (technical status)**: `SẴN SÀNG` / `CHƯA HOÀN TẤT`.
  SẴN SÀNG = đủ artifact để render.
- **Chất lượng nguồn (quality status)**: `RẤT TỐT` / `TỐT` / `CẢNH BÁO` /
  `KHÔNG KHUYẾN NGHỊ` / `CHƯA CÓ DỮ LIỆU`.
  Chất lượng = nguồn gốc tốt cỡ nào cho lipsync — KHÔNG đồng nghĩa với sẵn sàng.

Một avatar có thể `SẴN SÀNG` nhưng `CẢNH BÁO` (dùng được nhưng chất lượng
khẩu hình thấp hơn tối ưu). Một avatar `CHƯA HOÀN TẤT` không hiển thị chất
lượng (chưa đủ dữ liệu để đánh giá).

### Đánh giá đến từ đâu (không bịa đặt)

- Chất lượng được tính từ **validator thật** (`tools/avatar_source_quality/validator.py`)
  chạy read-only trên **video nguồn** của avatar (nếu còn trên đĩa), hoặc từ
  kết quả đã lưu.
- Nếu video nguồn không còn → `CHƯA CÓ DỮ LIỆU` (không đoán).
- Nếu avatar chưa hoàn tất → không đánh giá chất lượng.
- Không có điểm số giả (87/100…). Chỉ phân loại + điểm tốt/điểm yếu thật.

Mỗi thẻ avatar hiện: thumbnail, tên, loại (Cận cảnh/Toàn thân), trạng thái kỹ
thuật, nhãn chất lượng, điểm tốt (✓), điểm cần lưu ý (⚠), nút **Sử dụng Avatar**
(chỉ bật khi SẴN SÀNG) và **Xem đánh giá chi tiết** (modal với 8 tiêu chí +
khuyến nghị + thông tin kỹ thuật).

### Hành vi Use Anyway (không chặn cứng)

Cảnh báo chất lượng (khuôn mặt nhỏ, nhân vật đang nói trong nguồn, mờ, camera
rung, ánh sáng) là **cảnh báo, không phải chặn**. Operator luôn có thể chọn
**Vẫn sử dụng video này** khi tạo avatar; `user_override` được ghi lại.

### Avatar CHƯA HOÀN TẤT

Không thể chọn để render. Hiển thị `CHƯA HOÀN TẤT` + lý do (thiếu artifact).
Không khẳng định chất lượng tốt/kém.

### Tìm kiếm / lọc / sắp xếp thư viện

Lọc: Tất cả / Rất tốt / Tốt / Có cảnh báo / Không khuyến nghị / Chưa có dữ
liệu / Sẵn sàng / Chưa hoàn tất. Sắp xếp: Chất lượng tốt nhất / Mới nhất /
Tên A–Z. Tìm theo tên. Nút **Đánh giá tất cả** chạy validator read-only cho
mọi avatar còn video nguồn.

### Kích thước khuôn mặt (khuyến nghị, không chặn)

Nghiên cứu nguồn: mặt chuẩn production ≈ 0.116; khuyến nghị nguồn mới
`face_h_ratio >= 0.16`. UI dịch sang tiếng người ("Khuôn mặt hơi nhỏ"…) và
**không tự động loại** giá trị thấp — vẫn dùng được khi kỹ thuật khả thi.