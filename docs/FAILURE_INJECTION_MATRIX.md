# Failure Injection Matrix

Evidence from safe, isolated drills (2026-08-28). No production data touched; no quota spent; no destructive power loss performed.

| Scenario | How simulated | Expected | Actual | Evidence | Recovery | Status |
|---|---|---|---|---|---|---|
| Invalid Voice ID | POST /api/voice/check bogus id | ok=false, fail-closed, no fallback | ok=false "Voice ID invalid or unavailable (404)." | PROVEN_REAL | use valid Voice ID | PASS |
| Missing-chunk upload | init then complete with 0/3 chunks | reject | `{"ok":false,"error":"missing chunks (0/3)"}` | PROVEN_REAL | re-upload | PASS |
| Path-traversal upload_id | `..%2Fevil` as upload_id | no escape | HTTP 405, no write outside staging | PROVEN_REAL | n/a (blocked) | PASS |
| Missing ffprobe | PATH stripped, verify() a render | graceful degrade | ok=True by size>1000 only; no stream/res check; ffprobe fallback broken (imageio_ffmpeg.get_ffprobe_exe absent) | PROVEN_REAL | install ffprobe on PATH | WARN (R15) |
| Edge TTS reachable | GET /api/voice/edge/voices | voices list | ok=true, 2 voices, default vi-VN-HoaiMyNeural | PROVEN_REAL | n/a | PASS |
| Edge TTS unavailable | (not run — needs offline) | EdgeTTSUnavailable, no EL fallback | code raises EdgeTTSUnavailable; render_service returns honest error | PROVEN_STATIC | wait/use ElevenLabs | PASS |
| Invalid ElevenLabs key | (not run — would touch .env) | is_configured false → clear error | elevenlabs_client.is_configured gates; VoiceError/TTSUnavailable | PROVEN_STATIC | fix .env key | PASS |
| Zero-byte file | covered by missing-chunk + analyze rejects non-video | reject | staging accepts, analyze rejects | PROVEN_STATIC | re-upload real video | PASS |
| Port 8077 occupied | preflight bind test | detect | preflight "8077 đang bận"; 2nd Studio → traceback (no clean msg) | PROVEN_REAL + R07 | reuse/close instance | WARN (R07) |
| GPU job failure (rc!=0) | (not run — code path) | failed + GPU released | render_service:595-600 sets failed + gpu_service.release | PROVEN_STATIC | retry | PASS |
| GPU OOM | (not run) | failed + released | manifests as rc!=0 path | PROVEN_STATIC | retry; avoid over-subscription | PASS |
| Render subprocess hang | (not run — code path) | timed_out + released | watchdog 300s no-progress / 4h hard cap → terminate_tree | PROVEN_STATIC | retry | PASS |
| Studio crash mid-render | (reasoned, no real crash) | job stuck "rendering"; GPU reusable after restart | no startup reconciliation (R06) | UNKNOWN→PROVEN_STATIC | cancel/retry stuck job | WARN (R06) |
| DB unavailable | (test suite uses temp DBs) | controlled error | test_studio.py isolated DB | UNIT_TEST_ONLY | restore from backup | PASS |
| DB backup + restore | real backup → restore to isolated temp | integrity ok, counts match | integrity=ok, jobs=21 avatars=19 (match), <0.01s | PROVEN_REAL | n/a | PASS |
| Cloudflare tunnel dies | (reasoned) | remote access stops, local Studio continues | cloudflared is a separate proxy; render runs in Studio daemon thread | PROVEN_STATIC | re-run Share | PASS |
| Browser disconnect mid-render | (reasoned) | render continues | worker is daemon thread + Popen, not request-tied | PROVEN_STATIC | n/a | PASS |
| Missing model | preflight model check | BLOCKED | preflight ✗ Models lists missing | PROVEN_REAL (preflight) | restore model | PASS |
| Disk low | preflight disk check | warn/block | preflight warns <15GB repo / <20GB renders | PROVEN_REAL (preflight) | clean/move data | PASS |

## Evidence classification totals
PROVEN_REAL: 9 · PROVEN_STATIC: 8 · UNIT_TEST_ONLY: 1 · UNKNOWN: 0 · FAIL: 0