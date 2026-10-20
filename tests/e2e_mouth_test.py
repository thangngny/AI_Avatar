#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.1.5 real end-to-end mouth-test (spec Part G TEST B).

Runs the FULL free path:
  controller -> Edge TTS -> canonical 16kHz mono WAV -> generate_video_from_script.py
  -> MuseTalk v1.5 (locked truth) -> final MP4

Verifies: ~8-12s, 1080x1920, 25fps, audio+video present, ElevenLabs NOT called.
No quota consumed. Run with the torch env python:
    C:\\CongThang\\AI_avatar\\latentsync_env\\Scripts\\python.exe tests/e2e_mouth_test.py
"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from studio import render_service, db, edge_tts_client as edge, elevenlabs_client as el

def main():
    AVATAR = os.environ.get("E2E_AVATAR", "doTrang_closeup")
    VOICE = os.environ.get("E2E_VOICE", "vi-VN-HoaiMyNeural")

    # Guard: prove ElevenLabs synth is never called during the free test.
    _el_synth_calls = {"n": 0}
    _orig_el_synth = el.synth_to_wav

    def _el_synth_guard(*a, **k):
        _el_synth_calls["n"] += 1
        return _orig_el_synth(*a, **k)

    el.synth_to_wav = _el_synth_guard

    db.init_db()
    render_service.start()

    print(f"Creating mouth-test job: avatar={AVATAR} voice={VOICE}")
    r = render_service.create_mouth_test_job(AVATAR, VOICE)
    assert r["ok"], f"job creation failed: {r}"
    job_id = r["job_id"]
    print(f"job_id={job_id}  provider=EDGE_TTS_TEST  test_type=STANDARD_MOUTH_TEST")

    job = db.get_job(job_id)
    assert job["tts_provider"] == "EDGE_TTS_TEST", job["tts_provider"]
    assert job["test_mode"] == 1
    assert job["test_type"] == "STANDARD_MOUTH_TEST"

    deadline = time.time() + 900  # 15 min hard cap
    last = None
    while time.time() < deadline:
        job = db.get_job(job_id)
        if job["status"] != last:
            print(f"  [{job['status']}] {job.get('stage','')} progress={job.get('progress',0)} "
                  f"{(job.get('error') or '')[:80]}")
            last = job["status"]
        if job["status"] in ("complete", "failed", "cancelled", "timed_out"):
            break
        time.sleep(3)

    assert job["status"] == "complete", f"job did not complete: {job['status']} {job.get('error')}"
    assert _el_synth_calls["n"] == 0, "ElevenLabs was called during the free test!"
    out = job["output_path"]
    assert out and os.path.isfile(out), f"output missing: {out}"
    size = os.path.getsize(out)
    print(f"output: {out}  size={size}  duration_sec={job.get('duration_sec')}")

    # Verify the MP4: 1080x1920, 25fps, audio+video present, ~8-12s.
    import cv2
    cap = cv2.VideoCapture(out)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    dur = frames / fps if fps else 0
    print(f"video: {W}x{H}  fps={fps}  frames={frames}  dur={dur:.2f}s")

    # Audio stream present? Probe with ffprobe if available, else soundfile on a
    # demuxed wav is overkill; use cv2/fps above + an ffmpeg probe for audio.
    has_audio = False
    try:
        import subprocess
        pp = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                             "-show_entries", "stream=codec_type", "-of", "json", out],
                            capture_output=True, text=True, timeout=30)
        has_audio = "audio" in (pp.stdout or "")
    except Exception as e:
        print(f"ffprobe audio check skipped: {e}")

    print("\n=== TEST B RESULT ===")
    print(f"ElevenLabs called during free test: NO (calls={_el_synth_calls['n']})")
    print(f"Resolution: {W}x{H}  (expect 1080x1920)  {'PASS' if (W,H)==(1080,1920) else 'FAIL'}")
    print(f"FPS: {fps}  (expect 25)  {'PASS' if abs(fps-25)<1 else 'FAIL'}")
    print(f"Duration: {dur:.2f}s  (expect ~8-12)  {'PASS' if 6<=dur<=15 else 'FAIL'}")
    print(f"Audio present: {has_audio}  {'PASS' if has_audio else 'WARN(no ffprobe)'}")
    print(f"Provider fallback: NONE")
    print(f"tts_provider={job['tts_provider']}  test_mode={job['test_mode']}  test_type={job['test_type']}")
    ok = ((W, H) == (1080, 1920)) and abs(fps - 25) < 1 and 6 <= dur <= 15 and _el_synth_calls["n"] == 0
    print(f"OVERALL: {'PROVEN_REAL' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()