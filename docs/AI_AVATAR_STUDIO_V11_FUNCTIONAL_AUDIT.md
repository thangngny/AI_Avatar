# AI Avatar Studio V1.1 — Functional Audit

Generated 2026-08-27. Evidence classes: **PROVEN_REAL** (executed + artifact
verified), **PROVEN_STATIC** (source/config inspected), **UNIT_TEST_ONLY**,
**FAIL**, **BLOCKED_EXTERNAL**.

## Test results

| # | Test | Status | Evidence | Command/API | Artifact/Notes |
|---|---|---|---|---|---|
| 1 | Server startup | PASS | PROVEN_REAL | `run_studio.py` → http://127.0.0.1:8077 | HTTP 200 on `/`, `/styles.css`, `/app.js` |
| 2 | Vietnamese UI | PASS | PROVEN_STATIC | inspect index.html + app.js | All 5 nav + all screens Vietnamese. Technical product names (MuseTalk, ElevenLabs Voice ID, CUDA Graph) retained by design |
| 3 | Avatar Library | PASS | PROVEN_REAL | GET /api/avatars | 17 READY / 1 INCOMPLETE; quality + production_confidence + counts real |
| 4 | Avatar detail modal | PASS | PROVEN_REAL | GET /api/avatars/{id}/quality | Provenance + production_confidence + dimensions + recommendation (close_up: source partial + prod TRUNG BÌNH; doTrang: CẢNH BÁO + prod CAO) |
| 5 | Create Avatar | PASS | PROVEN_REAL (prior) | POST /api/avatar/prepare | Repair-phase audit_repair_avatar: artifacts verified READY. V1.1 flow unchanged |
| 6 | WARN override | PASS | PROVEN_REAL (prior) | POST prepare (override=true) | override persisted; prepare→READY |
| 7 | TXT script | PASS | PROVEN_REAL | POST /api/script/parse | 12 words, ~4s |
| 8 | DOCX script | PASS | PROVEN_REAL | POST /api/script/parse (file) | Parsed; Vietnamese Unicode preserved |
| 9 | Paste script | PASS | PROVEN_REAL | POST /api/script/parse (text) | Returned text equals input |
| 10 | Voice check | PASS | PROVEN_REAL | POST /api/voice/check | pGapy9MNHCukzJtjavF0 → name "Hạnh - Smooth, Clear and Feminine" |
| 11 | Invalid voice | PASS | PROVEN_REAL | POST /api/voice/check | bogus → ok:false, fail-closed, no fallback |
| 12 | Voice preview | PASS | PROVEN_REAL | POST /api/voice/preview | 3.06s WAV generated, playback URL works |
| 13 | 10s test render | PASS | PROVEN_REAL | POST /api/render/test | 8.12s & 7.94s, 1080×1920 25fps h264+aac |
| 14 | Full render short | PASS | PROVEN_REAL | POST /api/render (auto) | 20.48s job completed, output exists |
| 15 | Auto Split | PASS | PROVEN_REAL | POST /api/script/split + /api/render | 3 parts, **1125 words preserved exactly** (no loss/dup/invent), 3 distinct-path jobs created; 1 real render generated |
| 16 | Render queue | PASS | PROVEN_REAL | GET /api/system/status (active_jobs) | Live states observed (Đang tạo giọng đọc → Đang tạo video → Hoàn tất) |
| 17 | Dual GPU | PASS | PROVEN_REAL | POST /api/render/test ×2 | GPU0 + GPU1 concurrent, both complete, distinct outputs, no clobber |
| 18 | Render history | PASS | PROVEN_REAL | GET /api/render/jobs + SQLite | doTrang_closeup 7 complete, outputs exist, truth_hash recorded |
| 19 | Settings | PASS | PROVEN_REAL | GET /api/settings + /api/elevenlabs/quota | tier pro, 442613/610000, rem 167387, key masked ...cefc, NOT exposed |
| 20 | System status | PASS | PROVEN_REAL | python system_status.py | Truth VALID, Ready YES, all params |
| 21 | Incomplete avatar | PASS | PROVEN_REAL | GET /api/avatars | 30_7_fullbody INCOMPLETE, not selectable, no fake quality |
| 22 | Output collision | PASS | UNIT_TEST_ONLY + PROVEN_REAL | tests.TestOutputUniqueness + T17 | 50 same-second paths unique; dual-GPU distinct |
| 23 | Timeout/failure | PASS | UNIT_TEST_ONLY | tests.test_timed_out_is_distinct_state | Real hung renderer not run (wasteful); TIMED_OUT state + no-COMPLETE-before-verify unit-tested |
| 24 | Production truth | PASS | PROVEN_REAL | system_status.py | gain 1.5, ctx 0, offset -3, 25fps, 1080×1920, CUDA Graph/WOLA/Coverage ON |
| 25 | Security | PASS | PROVEN_REAL/STATIC | git + DB + API | .env gitignored & untracked; no key column in DB; key not in git diff; path traversal blocked (../.. → "No video file provided"); filenames sanitized |

## Bugs found & fixed in this audit (V1.1.x)

1. **Recommendation overconfidence (UI bug).** `cu_recon_em10_jaw` was shown as
   global ★ KHUYẾN NGHỊ, but 11 of 17 READY avatars lack source-quality data
   (raw source missing) and were excluded from the comparison — so it was only
   "best among evaluated", not global. **Fix:** recommendation is now
   confidence-gated. When any READY avatar lacks quality data, the best one
   shows "TỐT NHẤT TRONG NHÓM ĐÃ ĐÁNH GIÁ"; global ★ only when ALL READY avatars
   have real quality data. (avatar_quality.py + app.js)
2. **"Chưa có dữ liệu" was the only signal for close_up.** close_up lost its
   raw source but has real render history + historical baseline evidence.
   **Fix:** introduced **production confidence** (CAO/TRUNG BÌNH/CHƯA KIỂM
   CHỨNG) from real render history, kept separate from source quality. close_up
   now shows source = CHƯA ĐỦ DỮ LIỆU + production = TRUNG BÌNH (1 render) +
   "Đã kiểm chứng" badge. doTrang_closeup shows source CẢNH BÁO + production CAO.
   (avatar_quality.py render_history + provenance; UI badges + modal section)
3. **Single-concept quality conflated READY with source quality.** Now
   technical status and source quality are distinct fields; incomplete avatars
   get no quality assessment.

## Remaining unproven / known limitations

- **Timeout (T23):** UNIT_TEST_ONLY — a real hung renderer was not triggered
  (wasteful); the TIMED_OUT state + clean-terminate + no-COMPLETE-before-verify
  path is unit-tested only.
- **Create Avatar (T5/T6):** PROVEN_REAL in the prior repair phase; not re-run
  in this audit (the V1.1 create flow is unchanged — labels only).
- **11 avatars with missing raw source:** source quality is honestly
  unknowable (CHƯA CÓ DỮ LIỆU); a prepared-data analysis (method 2) was
  designed but not implemented to avoid mislabeling prepared metrics as source
  metrics. See AVATAR_LIBRARY_MASTER_AUDIT.md.
- **close_up production confidence:** on-disk render count is 1 (TRUNG BÌNH);
  historical archive grades it A+ baseline, but UI confidence is based on
  verifiable on-disk renders only (not inflated by archive).

## Production safety

- `config/render_truth.json` unchanged; `generate_video_from_script.py`
  unchanged; MuseTalk / lip-sync / timing / masks / audio gain / TTS behavior /
  GPU scheduling / render queue unchanged.
- 33 unit tests pass; `python system_status.py` → Production Truth VALID, Ready YES.
- Real renders verified at 1080×1920 / 25 FPS / audio+video with locked truth.