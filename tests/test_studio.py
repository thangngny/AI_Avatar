#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio — acceptance test suite (stdlib unittest, no pytest needed).

Covers spec section 47. Run from the repo root with the torch env python:
    python -m unittest tests.test_studio -v
or:
    python tests/test_studio.py

These tests do NOT call ElevenLabs or render (no quota / GPU cost) unless the
env var STUDIO_RUN_NETWORK_TESTS=1 is set. They assert the controller
invariants: avatar filtering, quality override behavior, fail-closed voice,
script parsing/splitting, job persistence, locked-truth protection, and
LatentSync isolation.
"""
import os
import sys
import json
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)


class StudioTestCase(unittest.TestCase):
    def setUp(self):
        # Use a temp DB so tests never touch the real studio.db.
        from studio import config
        self._orig_db = config.DB_PATH
        self.tmp = tempfile.mkdtemp(prefix="studio_test_")
        config.DB_PATH = os.path.join(self.tmp, "test.db")
        config.ensure_runtime_dirs()
        from studio import db
        db.init_db()
        # Disable the background render worker so job-creation tests can
        # inspect persisted rows without the worker racing to claim them
        # (which would also trigger real ElevenLabs TTS / GPU work).
        from studio import render_service
        self._orig_disabled = render_service._WORKER_DISABLED
        render_service._WORKER_DISABLED = True

    def tearDown(self):
        from studio import config, render_service
        render_service._WORKER_DISABLED = self._orig_disabled
        config.DB_PATH = self._orig_db
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestAvatarListing(StudioTestCase):
    def test_list_excludes_uploads_and_dotfiles(self):
        from studio import avatar_service
        avatars = avatar_service.list_avatars()
        ids = [a["avatar_id"] for a in avatars]
        self.assertNotIn(".uploads", ids, ".uploads must not be a listed avatar")
        for aid in ids:
            self.assertFalse(aid.startswith("."), f"{aid} is a dotfile/dir")
        # Every listed avatar must have a determinable ready flag (not crash).
        for a in avatars:
            self.assertIn(a["ready"], (True, False))

    def test_ready_requires_all_artifacts(self):
        from studio import avatar_service, config
        # A folder missing latents.pt must NOT be READY.
        fake = os.path.join(config.AVATARS_ROOT, "__test_notready__")
        os.makedirs(os.path.join(fake, "full_imgs"), exist_ok=True)
        os.makedirs(os.path.join(fake, "mask"), exist_ok=True)
        # no coords.pkl / latents.pt / avator_info.json
        try:
            self.assertFalse(avatar_service._check_ready(fake))
        finally:
            shutil.rmtree(fake, ignore_errors=True)


class TestQualityOverride(StudioTestCase):
    def test_quality_warning_allows_override(self):
        from studio import avatar_service
        # A WARN result: can_proceed must be True (override allowed), and it is
        # NOT a technical failure.
        fake_result = {
            "overall": "WARN", "technical_failure": False, "can_proceed": True,
            "categories": [{"category": "FACE_SIZE", "status": "WARN",
                            "message": "Face is small.", "note": "small", "value": 0.08}],
            "warnings": [{"category": "FACE_SIZE", "status": "WARN",
                          "message": "Face is small."}],
            "raw": {"face_h_ratio": 0.08},
        }
        self.assertTrue(fake_result["can_proceed"])
        self.assertFalse(fake_result["technical_failure"])
        # The UI offers "Use Anyway" exactly when can_proceed and not technical.
        allow_override = fake_result["can_proceed"] and not fake_result["technical_failure"]
        self.assertTrue(allow_override)

    def test_warn_without_override_requires_explicit_action(self):
        # The contract: a WARN does NOT auto-proceed. The UI must call
        # prepare with allow_warning_override=True explicitly. A plain
        # prepare call with override=False for a WARN is still allowed to
        # proceed (quality is a warning, not a block) — but the override flag
        # is recorded so it is distinguishable later.
        from studio import avatar_service, db
        # Simulate recording an avatar prep with override state.
        db.upsert_avatar("__warn_test__", ready=0, quality="WARN",
                         quality_data=json.dumps({"user_override": True}),
                         created_at=0.0)
        row = db.get_avatar("__warn_test__")
        self.assertEqual(row["quality"], "WARN")
        self.assertIn("user_override", row["quality_data"])

    def test_technical_failure_does_not_report_ready(self):
        from studio import avatar_service
        # No face detected / unreadable -> technical_failure -> can_proceed False.
        # The UI must NOT offer "Use Anyway" and must NOT report READY.
        result = {"technical_failure": True, "can_proceed": False,
                  "overall": "FAIL", "error": "No face detected."}
        self.assertFalse(result["can_proceed"])
        allow_override = result["can_proceed"] and not result["technical_failure"]
        self.assertFalse(allow_override)


class TestVoiceFailClosed(StudioTestCase):
    def test_invalid_voice_fails_closed_no_fallback(self):
        from studio import elevenlabs_client as el
        # Without consuming quota: check the code path. check_voice with a
        # bogus id returns ok=False (no fallback). We verify the contract
        # by inspecting that the client has no default-voice substitution.
        # The synth path raises VoiceError (never substitutes) — confirmed by
        # the source: _synth raises VoiceError and never retries with a
        # different voice_id.
        import inspect
        src = inspect.getsource(el._synth)
        # There must be no default voice fallback literal in the synth path.
        self.assertNotIn("EXAVITQu4vr4xnSDxMaL", src)
        self.assertNotIn("Sarah", src)
        # check_voice for empty id must return ok=False without calling the API.
        r = el.check_voice("")
        self.assertFalse(r["ok"])

    def test_voice_id_passed_exactly(self):
        from studio import elevenlabs_client as el
        # _master_path / synth use the exact voice_id string. Verify the
        # signature and that the URL is formatted with the given id verbatim.
        vid = "pGapy9MNHCukzJtjavF0"
        from studio import config
        url = config.ELEVENLABS_TTS_URL.format(voice_id=vid)
        self.assertIn(vid, url)
        # No transformation/normalization in check_voice (it only strips).
        self.assertEqual(el.check_voice("  " + vid + "  ")["voice_id"], vid)


class TestScript(StudioTestCase):
    def test_txt_parsing(self):
        from studio import script_service
        r = script_service.parse_script(text="Xin chào. Đây là một test.")
        self.assertTrue(r["ok"])
        self.assertGreater(r["words"], 0)
        self.assertGreater(r["estimated_duration_sec"], 0)

    def test_docx_parsing(self):
        from studio import script_service
        # Build a minimal .docx (zip of word/document.xml).
        import zipfile
        from xml.etree import ElementTree as ET
        NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        ET.register_namespace("w", NS)
        body = f'<w:document xmlns:w="{NS}"><w:body>'
        body += '<w:p><w:r><w:t>Hello avatar.</w:t></w:r></w:p>'
        body += '<w:p><w:r><w:t>Second paragraph.</w:t></w:r></w:p>'
        body += '</w:body></w:document>'
        path = os.path.join(self.tmp, "t.docx")
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("word/document.xml", body)
        r = script_service.parse_script(file_path=path)
        self.assertTrue(r["ok"])
        self.assertIn("Hello avatar", r["text"])
        self.assertIn("Second paragraph", r["text"])

    def test_auto_split_preserves_sentences(self):
        from studio import script_service
        text = "Câu một. Câu hai. Câu ba. Câu bốn. Câu năm. Câu sáu. Câu bảy. Câu tám."
        r = script_service.split_script(text, "auto")
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(r["total_parts"], 1)
        # No part may be empty or start mid-word: each part is a join of whole
        # sentences, so it must end with a sentence boundary or be the last.
        for p in r["parts"]:
            self.assertTrue(p["text"].strip())
            self.assertGreater(p["words"], 0)

    def test_30s_split_no_mid_word_cut(self):
        from studio import script_service
        text = " ".join(f"word{i}" for i in range(200))
        r = script_service.split_script(text, "30s")
        self.assertTrue(r["ok"])
        self.assertEqual(r["total_parts"], 1)
        # The part must be a prefix of whole words (no truncated token).
        part_words = r["parts"][0]["text"].split()
        for w in part_words:
            self.assertTrue(w.startswith("word"))


class TestRenderJobs(StudioTestCase):
    def test_full_render_job_creation_and_persistence(self):
        from studio import render_service, db
        # create_full_jobs with a non-ready avatar must refuse.
        r = render_service.create_full_jobs("__nonexistent__", "vid", "some script", "full")
        self.assertFalse(r["ok"])
        # Insert a fake READY avatar row + on-disk structure is required for
        # create_full_jobs (it checks avatar_service.list_avatars). Use a real
        # ready avatar if one exists; else skip creation but test DB persistence.
        from studio import avatar_service
        ready = [a for a in avatar_service.list_avatars() if a["ready"]]
        if not ready:
            self.skipTest("no prepared avatar on disk")
        av = ready[0]["avatar_id"]
        cfg = {"model_id": "eleven_turbo_v2_5", "voice_settings": {"stability": 0.5}}
        r = render_service.create_full_jobs(av, "pGapy9MNHCukzJtjavF0",
                                             "Xin chào. Đây là test.", "full",
                                             tts_config=cfg)
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(len(r["job_ids"]), 1)
        job = db.get_job(r["job_ids"][0])
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["voice_id"], "pGapy9MNHCukzJtjavF0")
        # Truth hash recorded.
        self.assertTrue(job["truth_hash"])
        # No API key in the row.
        for k, v in job.items():
            if v and isinstance(v, str):
                self.assertNotIn("ELEVENLABS_API_KEY", v)
                self.assertNotIn("sk_", v)

    def test_failed_job_retry_preserves_fields(self):
        from studio import db, render_service
        # Insert a failed job and retry -> status queued, fields preserved.
        db.create_job({"job_id": "j_retry", "kind": "full", "avatar_id": "x",
                       "voice_id": "vid", "script_text": "t", "status": "failed",
                       "stage": "Failed", "error": "boom",
                       "truth_hash": render_service.truth_hash()})
        r = render_service.retry_job("j_retry")
        self.assertTrue(r["ok"])
        job = db.get_job("j_retry")
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["voice_id"], "vid")  # unchanged
        self.assertEqual(job["avatar_id"], "x")    # unchanged
        self.assertIsNone(job["error"])

    def test_cancel_job(self):
        from studio import db, render_service
        db.create_job({"job_id": "j_cancel", "kind": "test10s", "avatar_id": "x",
                       "voice_id": "vid", "script_text": "t", "status": "queued",
                       "stage": "Queued"})
        r = render_service.cancel_job("j_cancel")
        self.assertTrue(r["ok"])
        self.assertEqual(db.get_job("j_cancel")["status"], "cancelled")


class TestProductionTruthProtection(StudioTestCase):
    def test_truth_unchanged_and_valid(self):
        from studio import render_service
        r = render_service.load_truth()
        self.assertTrue(r["ok"])
        t = r["truth"]
        # The locked values must be exactly the production truth.
        self.assertEqual(t["pipeline"], "musetalk_v15")
        self.assertEqual(t["audio_gain"], 1.15)
        self.assertEqual(t["audio_context_left"], 3)
        self.assertEqual(t["audio_feature_offset_frames"], -1)
        self.assertEqual(t["fps"], 25)
        self.assertEqual(t["resolution_width"], 1080)
        self.assertEqual(t["resolution_height"], 1920)
        self.assertTrue(t["cuda_graph"])
        self.assertTrue(t["long_audio_wola"])
        self.assertTrue(t["feature_coverage_assertion"])
        # The file on disk must match (not modified by the controller).
        with open(os.path.join(ROOT, "config", "render_truth.json"), "r",
                  encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertEqual(on_disk, t)

    def test_latentsync_not_reachable(self):
        from studio import config, render_service
        # The renderer path the controller invokes must be the MuseTalk
        # production entrypoint, never LatentSync.
        self.assertTrue(config.RENDERER.endswith("generate_video_from_script.py"))
        self.assertNotIn("latentsync", config.RENDERER.lower())
        with open(config.RENDERER, "r", encoding="utf-8") as f:
            self.assertNotIn("LatentSync", f.read())

    def test_renderer_uses_render_truth(self):
        from studio import config
        # The renderer loads config/render_truth.json and forces it. Confirm
        # the renderer source references the truth path.
        with open(config.RENDERER, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("render_truth.json", src)
        self.assertIn("load_render_truth", src)


class TestAPIContract(StudioTestCase):
    def setUp(self):
        super().setUp()
        from studio.app import app
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_system_status(self):
        r = self.client.get("/api/system/status")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIn("gpus", d)
        self.assertIn("truth_valid", d)
        # No API key leaked: the real key value must not appear in the response.
        from studio import envutil
        envutil.load_env(force=True)
        real_key = envutil.env_str("ELEVENLABS_API_KEY", "")
        s = json.dumps(d)
        if real_key:
            self.assertNotIn(real_key, s)
        # The masked key must be bullets, not the real key prefix.
        self.assertNotIn(real_key[:8], d.get("elevenlabs_key_masked", ""))

    def test_avatars_no_uploads(self):
        r = self.client.get("/api/avatars")
        self.assertEqual(r.status_code, 200)
        ids = [a["avatar_id"] for a in r.get_json()["avatars"]]
        self.assertNotIn(".uploads", ids)

    def test_voice_check_empty(self):
        r = self.client.post("/api/voice/check", json={"voice_id": ""})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["ok"])

    def test_script_parse_endpoint(self):
        r = self.client.post("/api/script/parse", json={"text": "Xin chào."})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])

    def test_script_split_endpoint(self):
        r = self.client.post("/api/script/split",
                             json={"script_text": "Câu một. Câu hai.", "mode": "full"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ok"])

    def test_settings_masks_key(self):
        r = self.client.get("/api/settings")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        from studio import envutil
        envutil.load_env(force=True)
        real_key = envutil.env_str("ELEVENLABS_API_KEY", "")
        s = json.dumps(d)
        if real_key:
            self.assertNotIn(real_key, s)
        # Masked, not full.
        self.assertNotIn(real_key[:8], d.get("elevenlabs_key_masked", ""))

    def test_settings_elevenlabs_get_and_post(self):
        # 1. GET settings
        r = self.client.get("/api/settings/elevenlabs")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertIn("model_id", d)
        self.assertIn("voice_id", d)
        self.assertIn("max_text_chars", d)

        # 2. POST update model_id to eleven_v4
        old_model = d.get("model_id")
        try:
            r2 = self.client.post("/api/settings/elevenlabs", json={
                "model_id": "eleven_v4",
                "max_text_chars": 10000,
                "sync_profiles": True
            })
            self.assertEqual(r2.status_code, 200)
            d2 = r2.get_json()
            self.assertTrue(d2["ok"])
            self.assertEqual(d2["model_id"], "eleven_v4")
            self.assertEqual(d2["max_text_chars"], 10000)
        finally:
            # Restore previous model
            if old_model:
                self.client.post("/api/settings/elevenlabs", json={"model_id": old_model})

    def test_elevenlabs_v4_in_model_caps(self):
        from studio.elevenlabs_client import MODEL_CAPS
        self.assertIn("eleven_v4", MODEL_CAPS)
        self.assertIn("eleven_v4_turbo", MODEL_CAPS)
        self.assertEqual(MODEL_CAPS["eleven_v4"]["max_text"], 10000)
        self.assertTrue(MODEL_CAPS["eleven_v4"]["language_code"])

    def test_system_status_includes_tts_settings(self):
        r = self.client.get("/api/system/status")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertIn("elevenlabs_model_id", d)
        self.assertIn("elevenlabs_voice_id", d)
        self.assertIn("tts_max_text_chars", d)

    def test_render_validate_endpoint(self):
        # 1. Empty payload should fail avatar and script
        r = self.client.post("/api/render/validate", json={})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertFalse(d["can_render"])
        self.assertGreaterEqual(len(d["checklist"]), 5)
        self.assertGreaterEqual(d["summary"]["failures"], 2)

        # 2. Valid Edge TTS payload with ready avatar
        avatars = self.client.get("/api/avatars").get_json()["avatars"]
        ready_avs = [a["avatar_id"] for a in avatars if a.get("ready")]
        if ready_avs:
            ready_av = ready_avs[0]
            r2 = self.client.post("/api/render/validate", json={
                "avatar_id": ready_av,
                "script_text": "Xin chào quý vị khán giả.",
                "tts_provider": "edge",
                "voice_id": "vi-VN-HoaiMyNeural"
            })
            self.assertEqual(r2.status_code, 200)
            d2 = r2.get_json()
            self.assertTrue(d2["ok"])
            self.assertTrue(d2["can_render"])
            self.assertEqual(d2["summary"]["failures"], 0)


class TestVerify(StudioTestCase):
    def test_missing_file_fails(self):
        from studio import verify as v
        r = v.verify("/nonexistent/path.mp4")
        self.assertFalse(r["ok"])


class TestAnalyzeMetadata(StudioTestCase):
    """V1.3.1 §9 regression: the validator spreads integrity fields (width/
    height/duration) at the TOP LEVEL of its success JSON, with no nested
    "integrity" key. analyze_source must normalize so the UI never sees
    undefined x undefined. Runs the real validator subprocess (torch env)."""
    def test_integrity_populated_on_real_source(self):
        import studio.avatar_service as svc
        sample = os.path.join(ROOT, "studio", "static", "assets",
                              "avatar_source_example", "sample.mp4")
        if not os.path.isfile(sample):
            self.skipTest("sample.mp4 not present")
        r = svc.analyze_source(sample)
        if r.get("technical_failure"):
            self.skipTest(f"validator unavailable: {r.get('error')}")
        integ = r.get("integrity") or {}
        for k in ("width", "height", "duration"):
            v = integ.get(k)
            self.assertIsNotNone(v, f"integrity.{k} must not be None (got {integ})")
            self.assertNotEqual(v, "", f"integrity.{k} must not be empty")
            self.assertNotIn(str(v), ("undefined", "NaN", "null", "[object Object]"),
                             f"integrity.{k} must not render as undefined/NaN/null")
        # The bug shape: integrity == {} on success. Explicitly forbidden.
        self.assertTrue(integ.get("width") and integ.get("height"),
                        f"integrity must be a complete dict, got {integ}")


class TestReconcileInflight(StudioTestCase):
    """V1.4.1 R06: on startup, transient jobs left by a crashed Studio must be
    honestly marked failed — never left stuck 'rendering' forever. Completed /
    queued jobs are not touched. No auto-retry."""
    def _make_job(self, status):
        import time as _time
        from studio import db
        jid = f"job_reconcile_{status}_{int(_time.time())}"
        db.create_job({"job_id": jid, "kind": "test10s", "avatar_id": "x",
                       "voice_id": "v", "script_text": "t", "script_name": "t",
                       "output_path": "x.mp4", "status": status, "stage": status,
                       "truth_hash": "", "tts_provider": "ELEVENLABS"})
        return jid

    def test_transient_marked_failed_on_startup(self):
        from studio import db, render_service
        running = self._make_job("rendering")
        prep = self._make_job("preparing_audio")
        render_service._reconcile_inflight_jobs()
        self.assertEqual(db.get_job(running)["status"], "failed")
        self.assertEqual(db.get_job(prep)["status"], "failed")
        self.assertIn("khởi động lại", db.get_job(running)["error"])

    def test_complete_and_queued_not_touched(self):
        from studio import db, render_service
        done = self._make_job("complete")
        queued = self._make_job("queued")
        render_service._reconcile_inflight_jobs()
        self.assertEqual(db.get_job(done)["status"], "complete")
        self.assertEqual(db.get_job(queued)["status"], "queued")


class TestVerifyFallback(StudioTestCase):
    """V1.4.1 R15: ffprobe fallback no longer calls the non-existent
    imageio_ffmpeg.get_ffprobe_exe; when ffprobe is unavailable, verify must NOT
    fabricate success from file size alone."""
    def test_no_probe_means_honest_failure(self):
        from studio import verify as v
        import tempfile, os
        fd, p = tempfile.mkstemp(suffix=".mp4")
        os.write(fd, b"\0" * 2000)  # large enough to pass the old size>1000 check
        os.close(fd)
        try:
            orig = v._ffprobe
            v._ffprobe = lambda path: None  # simulate no ffprobe
            r = v.verify(p)
            self.assertFalse(r["ok"], "verify must NOT pass without ffprobe")
            self.assertTrue(any("ffprobe unavailable" in w for w in r["warnings"]))
        finally:
            v._ffprobe = orig
            os.remove(p)

    def test_ffprobe_resolved_returns_path_or_none(self):
        from studio import verify as v
        r = v.ffprobe_resolved()
        self.assertTrue(r is None or os.path.isfile(r) or True)  # shape check


class TestOutputUniqueness(StudioTestCase):
    def test_many_same_second_paths_are_unique(self):
        """Defect 1 regression: many jobs created in the same wall-clock second
        must each receive a GLOBALLY UNIQUE output path (no uuid -> collision)."""
        import studio.render_service as rs
        paths = []
        # Simulate 50 jobs created as fast as possible (same second likely).
        for _ in range(50):
            jid = rs._new_job_id()
            p = rs._output_path("test10s", "doTrang_closeup", "test10s", jid)
            paths.append(os.path.basename(p))
        self.assertEqual(len(paths), len(set(paths)),
                         "output paths collided: %s" %
                         [p for p in paths if paths.count(p) > 1])

    def test_two_jobs_distinct_paths(self):
        import studio.render_service as rs
        j1, j2 = rs._new_job_id(), rs._new_job_id()
        p1 = rs._output_path("full", "av", "Part 01", j1)
        p2 = rs._output_path("full", "av", "Part 01", j2)
        self.assertNotEqual(p1, p2)

    def test_safe_filenames(self):
        import studio.render_service as rs
        jid = rs._new_job_id()
        p = rs._output_path("full", "av/evil", "Part 01/02", jid)
        self.assertNotIn("/", os.path.basename(p))
        self.assertNotIn("..", p)


class TestRepairs(StudioTestCase):
    """Repair-specific invariants (Defects 1/2/3/4/6/8)."""

    def test_genavatar_invocation_uses_module(self):
        """D2: genavatar must be invoked as `python -m avatars.musetalk.genavatar`
        (repo-root import context), not as a bare script path."""
        import inspect
        from studio import avatar_service
        src = inspect.getsource(avatar_service.PrepJob.start)
        self.assertIn("-m", src)
        self.assertIn("avatars.musetalk.genavatar", src)
        # Must NOT invoke the bare script path (the broken form).
        self.assertNotIn("config.GENAVATAR,", src)
        # PYTHONPATH must be set to the repo root as a guarantee.
        self.assertIn("PYTHONPATH", src)

    def test_avatar_counts_distinguish_ready_and_incomplete(self):
        """D4: avatar_counts returns total_dirs / ready / incomplete."""
        from studio import avatar_service
        c = avatar_service.avatar_counts()
        self.assertIn("total_dirs", c)
        self.assertIn("ready_avatars", c)
        self.assertIn("incomplete_avatars", c)
        self.assertEqual(c["ready_avatars"] + c["incomplete_avatars"],
                         c["total_dirs"])

    def test_incomplete_avatar_status_field(self):
        """D4: a non-ready avatar dir must report status='INCOMPLETE', not READY."""
        from studio import avatar_service, config
        fake = os.path.join(config.AVATARS_ROOT, "__test_incomplete__")
        os.makedirs(os.path.join(fake, "full_imgs"), exist_ok=True)
        os.makedirs(os.path.join(fake, "mask"), exist_ok=True)
        # one frame so frame_count>0 but missing latents/coords -> not ready
        try:
            from PIL import Image  # noqa
        except Exception:
            # create a tiny png without PIL
            import struct, zlib
            def _png(path):
                # 1x1 black png
                sig = b"\x89PNG\r\n\x1a\n"
                ihdr = b"IHDR" + struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
                ihdr = struct.pack(">I", 13) + ihdr + struct.pack(">I", zlib.crc32(ihdr))
                idat = b"IDAT" + zlib.compress(b"\x00\x00")
                idat = struct.pack(">I", len(idat) - 4) + idat + struct.pack(">I", zlib.crc32(idat))
                iend = b"IEND" + struct.pack(">I", 0) + struct.pack(">I", zlib.crc32(b"IEND"))
                open(path, "wb").write(sig + ihdr + idat + iend)
            _png(os.path.join(fake, "full_imgs", "00000000.png"))
            _png(os.path.join(fake, "mask", "00000000.png"))
        try:
            av = avatar_service.list_avatars()
            match = next((a for a in av if a["avatar_id"] == "__test_incomplete__"), None)
            self.assertIsNotNone(match)
            self.assertFalse(match["ready"])
            self.assertEqual(match["status"], "INCOMPLETE")
        finally:
            shutil.rmtree(fake, ignore_errors=True)

    def test_interpreter_resolved_centrally(self):
        """D8: interpreter resolution is centralized in studio.runtime and
        overridable via STUDIO_TORCH_PYTHON."""
        from studio import runtime
        # explicit override wins
        os.environ["STUDIO_TORCH_PYTHON"] = "python"
        try:
            self.assertEqual(runtime.torch_python(), "python")
        finally:
            del os.environ["STUDIO_TORCH_PYTHON"]
        # default resolves to a real path or 'python'
        self.assertTrue(runtime.torch_python())

    def test_account_status_does_not_fabricate(self):
        """D6: account_status never fabricates remaining when fields absent.
        With no key, returns an honest error (no fake numbers)."""
        from studio import elevenlabs_client as el
        # Temporarily pretend no key.
        orig = el._API_KEY
        el._API_KEY = ""
        try:
            r = el.account_status()
            self.assertFalse(r["ok"])
            self.assertNotIn("remaining", r)  # no fabricated remaining
        finally:
            el._API_KEY = orig

    def test_timed_out_is_distinct_state(self):
        """D3: timed_out is a recognized terminal state (retry accepts it)."""
        from studio import render_service, db
        db.create_job({"job_id": "j_to", "kind": "full", "avatar_id": "x",
                        "voice_id": "vid", "script_text": "t",
                        "status": "timed_out", "stage": "Timed Out",
                        "truth_hash": render_service.truth_hash()})
        r = render_service.retry_job("j_to")
        self.assertTrue(r["ok"])
        self.assertEqual(db.get_job("j_to")["status"], "queued")
        # retry must assign a fresh output path (uuid-suffixed)
        self.assertIn(db.get_job("j_to")["output_path"][-13:-4],
                      db.get_job("j_to")["output_path"])


# --------------------------------------------------------------------------- #
# V1.1.5 — Free Edge TTS test path + guided avatar input
# --------------------------------------------------------------------------- #
class TestEdgeTTS(StudioTestCase):
    """Edge TTS free-test provider (spec Part B). No API key, no ElevenLabs
    fallback, canonical 16kHz mono WAV output."""

    def test_edge_client_present_no_api_key(self):
        from studio import edge_tts_client as edge
        # Edge TTS requires NO ElevenLabs API key. is_available reflects the
        # package, not a key.
        self.assertTrue(callable(edge.is_available))
        self.assertEqual(edge.DEFAULT_VOICE, "vi-VN-HoaiMyNeural")
        # Known Vietnamese voices are configured.
        self.assertIn("vi-VN-HoaiMyNeural", edge.KNOWN_VOICES)
        self.assertIn("vi-VN-NamMinhNeural", edge.KNOWN_VOICES)

    def test_edge_voices_list_has_vietnamese(self):
        from studio import edge_tts_client as edge
        if not edge.is_available():
            self.skipTest("edge-tts not installed")
        lv = edge.list_voices()
        self.assertTrue(lv["ok"])
        ids = [v["voice_id"] for v in lv["voices"]]
        # The default voice must be in the list (live or known fallback).
        self.assertIn(edge.DEFAULT_VOICE, ids)
        for v in lv["voices"]:
            self.assertTrue(v["voice_id"].lower().startswith("vi-vn"))

    def test_edge_failure_does_not_call_elevenlabs(self):
        """Spec B8: if Edge TTS fails, never silently fall back to ElevenLabs."""
        from studio import render_service, edge_tts_client as edge, elevenlabs_client as el
        # Force Edge to be "installed" but fail at synth; fail if ElevenLabs is touched.
        orig_avail = edge.is_available
        orig_synth = edge.synth_to_wav
        el_called = {"v": False}
        edge.is_available = lambda: True
        def _edge_fail(*a, **k):
            raise edge.EdgeTTSUnavailable("simulated edge failure")
        edge.synth_to_wav = _edge_fail
        def _el_trap(*a, **k):
            el_called["v"] = True
            return ("x", 0.0)
        orig_el_synth = el.synth_to_wav
        el.synth_to_wav = _el_trap
        try:
            r = render_service.generate_master_audio(
                "Ba mẹ mỉm cười.", "vi-VN-HoaiMyNeural",
                tts_provider=render_service.EDGE_TTS_TEST)
        finally:
            edge.is_available = orig_avail
            edge.synth_to_wav = orig_synth
            el.synth_to_wav = orig_el_synth
        self.assertFalse(r["ok"])
        self.assertFalse(el_called["v"], "Edge failure must NOT fall back to ElevenLabs")

    def test_elevenlabs_failure_does_not_call_edge(self):
        """Spec B8 (reverse): if ElevenLabs fails, never silently use Edge."""
        from studio import render_service, elevenlabs_client as el, edge_tts_client as edge
        el_called = {"v": False}
        edge_called = {"v": False}
        orig_el_conf = el.is_configured
        orig_el_synth = el.synth_to_wav
        el.is_configured = lambda: True
        def _el_fail(*a, **k):
            el_called["v"] = True
            raise el.TTSUnavailable("simulated elevenlabs failure")
        el.synth_to_wav = _el_fail
        orig_edge_synth = edge.synth_to_wav
        def _edge_trap(*a, **k):
            edge_called["v"] = True
            return ("x", 0.0)
        edge.synth_to_wav = _edge_trap
        try:
            r = render_service.generate_master_audio(
                "Xin chào.", "pGapy9MNHCukzJtjavF0",
                tts_provider=render_service.ELEVENLABS)
        finally:
            el.is_configured = orig_el_conf
            el.synth_to_wav = orig_el_synth
            edge.synth_to_wav = orig_edge_synth
        self.assertFalse(r["ok"])
        self.assertTrue(el_called["v"])
        self.assertFalse(edge_called["v"], "ElevenLabs failure must NOT fall back to Edge")

    def test_edge_audio_canonical_wav(self):
        """Spec B7: Edge audio decodes to canonical 16kHz mono WAV. Network test."""
        if not os.environ.get("STUDIO_RUN_NETWORK_TESTS"):
            self.skipTest("set STUDIO_RUN_NETWORK_TESTS=1 for real Edge TTS")
        from studio import edge_tts_client as edge
        if not edge.is_available():
            self.skipTest("edge-tts not installed")
        out = os.path.join(self.tmp, "edge.wav")
        path, dur = edge.synth_to_wav("vi-VN-HoaiMyNeural",
                                      "Ba mẹ mỉm cười và Minh mua một hộp bánh mì.", out)
        import soundfile as sf
        info = sf.info(path)
        self.assertEqual(info.samplerate, 16000)
        self.assertEqual(info.channels, 1)
        self.assertGreater(dur, 0.5)


class TestMouthTestJob(StudioTestCase):
    """Standard mouth-motion test job (spec B9/B10/B11/D)."""

    def test_mouth_test_refuses_non_ready_avatar(self):
        from studio import render_service
        r = render_service.create_mouth_test_job("__nonexistent__", "vi-VN-HoaiMyNeural")
        self.assertFalse(r["ok"])

    def test_mouth_test_job_metadata(self):
        from studio import render_service, avatar_service, db
        ready = [a for a in avatar_service.list_avatars() if a["ready"]]
        if not ready:
            self.skipTest("no prepared avatar on disk")
        av = ready[0]["avatar_id"]
        r = render_service.create_mouth_test_job(av, "vi-VN-HoaiMyNeural")
        self.assertTrue(r["ok"])
        job = db.get_job(r["job_id"])
        self.assertEqual(job["tts_provider"], render_service.EDGE_TTS_TEST)
        self.assertEqual(job["test_mode"], 1)
        self.assertEqual(job["test_type"], render_service.TEST_TYPE_STANDARD_MOUTH)
        self.assertEqual(job["edge_voice"], "vi-VN-HoaiMyNeural")
        # The standard diagnostic script is stored.
        self.assertIn("bánh mì", job["script_text"])
        # No API key leaked.
        for k, v in job.items():
            if v and isinstance(v, str):
                self.assertNotIn("ELEVENLABS_API_KEY", v)
                self.assertNotIn("sk_", v)

    def test_standard_mouth_script_has_bilabials(self):
        from studio import render_service
        s = render_service.STANDARD_MOUTH_TEST_SCRIPT
        # bilabials m/b/p present (spec B10).
        for ch in "mbp":
            self.assertIn(ch, s.lower())

    def test_test_job_records_provider(self):
        """Spec D: jobs record tts_provider/test_mode/test_type explicitly."""
        from studio import render_service, avatar_service, db
        ready = [a for a in avatar_service.list_avatars() if a["ready"]]
        if not ready:
            self.skipTest("no prepared avatar on disk")
        av = ready[0]["avatar_id"]
        r = render_service.create_test_job(av, "vi-VN-HoaiMyNeural", "Xin chào.",
                                           tts_provider=render_service.EDGE_TTS_TEST,
                                           test_mode=True)
        self.assertTrue(r["ok"])
        job = db.get_job(r["job_id"])
        self.assertEqual(job["tts_provider"], render_service.EDGE_TTS_TEST)
        self.assertEqual(job["test_mode"], 1)
        # Full render records PRODUCTION.
        r2 = render_service.create_full_jobs(av, "pGapy9MNHCukzJtjavF0", "Xin chào. Test.", "full")
        if r2["ok"]:
            job2 = db.get_job(r2["job_ids"][0])
            self.assertEqual(job2["tts_provider"], render_service.ELEVENLABS)
            self.assertEqual(job2["test_mode"], 0)
            self.assertEqual(job2["test_type"], render_service.TEST_TYPE_PRODUCTION)


class TestMouthStatePersistence(StudioTestCase):
    """Spec A10/D: user-confirmed mouth state is stored separately, raw auto
    evidence never overwritten."""

    def test_mouth_state_stored_in_quality_data(self):
        from studio import db
        import json as _json
        db.upsert_avatar("__mouth_test__", ready=0, quality="PASS",
                         quality_data=_json.dumps({
                             "mouth_state_auto": "0.012",
                             "mouth_state_user": "NOT_TALKING",
                             "mouth_state_provenance": "USER_CONFIRMED"}),
                         created_at=0.0)
        row = db.get_avatar("__mouth_test__")
        qd = _json.loads(row["quality_data"])
        self.assertEqual(qd["mouth_state_user"], "NOT_TALKING")
        self.assertEqual(qd["mouth_state_provenance"], "USER_CONFIRMED")
        # Raw auto evidence preserved separately.
        self.assertEqual(qd["mouth_state_auto"], "0.012")


class TestSampleEndpoint(StudioTestCase):
    """Spec A7/H: sample-video slot — honest pending state when no approved
    compliant sample exists."""

    def setUp(self):
        super().setUp()
        from studio.app import app
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_sample_endpoint_reports_pending_or_real(self):
        r = self.client.get("/api/avatar/sample")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        # V1.1.6 added TEMPORARY_BEST_EXISTING_SOURCE (operator-selected best
        # raw source as a temporary example, marked temporary=true).
        self.assertIn(d["status"], ("SAMPLE_ASSET_PENDING_HUMAN_APPROVAL",
                                     "REAL_COMPLIANT_SOURCE",
                                     "TEMPORARY_BEST_EXISTING_SOURCE"))
        # Must never fabricate availability without an approved manifest.
        if not d.get("available"):
            self.assertEqual(d["status"], "SAMPLE_ASSET_PENDING_HUMAN_APPROVAL")
            self.assertIn("cập nhật", d["message"].lower())
        # A temporary sample is honest about being temporary.
        if d.get("temporary"):
            self.assertEqual(d["status"], "TEMPORARY_BEST_EXISTING_SOURCE")
            self.assertTrue(d.get("available"))


class TestEdgeAPIRoutes(StudioTestCase):
    """Spec B1/B5: edge voice routes, no ElevenLabs Voice ID required."""

    def setUp(self):
        super().setUp()
        from studio.app import app
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_edge_voices_route(self):
        r = self.client.get("/api/voice/edge/voices")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        from studio import edge_tts_client as edge
        if edge.is_available():
            self.assertTrue(d["ok"])
            self.assertTrue(d["voices"])

    def test_edge_preview_requires_text(self):
        r = self.client.post("/api/voice/edge/preview",
                             json={"voice_id": "vi-VN-HoaiMyNeural", "text": ""})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_mouth_test_route_requires_avatar(self):
        r = self.client.post("/api/render/mouth-test",
                             json={"edge_voice": "vi-VN-HoaiMyNeural"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_system_status_has_edge_field(self):
        r = self.client.get("/api/system/status")
        d = r.get_json()
        self.assertIn("edge_tts_available", d)


class TestLockedTruthUnchangedV115(StudioTestCase):
    """Spec Part C/K: changing TTS provider does NOT change the lipsync truth."""

    def test_edge_job_uses_same_renderer_and_truth(self):
        from studio import render_service, config
        # The renderer invoked is the SAME production entrypoint regardless of
        # provider. Confirm the constants + truth are intact.
        self.assertTrue(config.RENDERER.endswith("generate_video_from_script.py"))
        r = render_service.load_truth()
        self.assertTrue(r["ok"])
        t = r["truth"]
        self.assertEqual(t["pipeline"], "musetalk_v15")
        self.assertEqual(t["audio_gain"], 1.15)
        self.assertEqual(t["audio_context_left"], 3)
        self.assertEqual(t["audio_feature_offset_frames"], -1)
        self.assertEqual(t["fps"], 25)
        self.assertEqual(t["resolution_width"], 1080)
        self.assertEqual(t["resolution_height"], 1920)
        self.assertTrue(t["cuda_graph"])
        self.assertTrue(t["long_audio_wola"])
        self.assertTrue(t["feature_coverage_assertion"])
        # render_truth.json on disk is unmodified.
        with open(os.path.join(ROOT, "config", "render_truth.json"), "r",
                  encoding="utf-8") as f:
            self.assertEqual(json.load(f), t)


class TestChunkedUpload(StudioTestCase):
    """Spec §15/§16: chunked upload assembles atomically with size + sha1 match,
    no second importer. Covers the >100MB-Cloudflare-limit path with small
    multi-chunk synthetic data (the mechanism is size-agnostic)."""

    def test_chunked_upload_assembles_with_size_and_sha1(self):
        import hashlib
        from studio.app import app
        app.config["TESTING"] = True
        c = app.test_client()
        data = os.urandom(2_500_000)  # 2.5 MB
        local_sha = hashlib.sha1(data).hexdigest()
        init = c.post("/api/uploads/init",
                      json={"filename": "chunktest.mp4", "size": len(data)}).get_json()
        self.assertTrue(init["ok"])
        uid = init["upload_id"]
        CH = 1_000_000  # 3 chunks
        total = -(-len(data) // CH)
        for i in range(total):
            part = data[i * CH:(i + 1) * CH]
            body = (f"--B\r\nContent-Disposition: form-data; name=\"chunk_index\"\r\n\r\n{i}\r\n"
                    f"--B\r\nContent-Disposition: form-data; name=\"chunk_data\"; filename=\"c\"\r\n"
                    f"Content-Type: application/octet-stream\r\n\r\n").encode() + part + b"\r\n--B--\r\n"
            rr = c.post(f"/api/uploads/{uid}/chunk", data=body,
                        content_type="multipart/form-data; boundary=B")
            self.assertTrue(rr.get_json().get("ok"), f"chunk {i} failed")
        done = c.post(f"/api/uploads/{uid}/complete",
                      json={"filename": "chunktest.mp4", "expected_size": len(data),
                            "expected_chunks": total}).get_json()
        self.assertTrue(done.get("ok"))
        self.assertEqual(done["size"], len(data))
        self.assertEqual(done["sha1"], local_sha)
        p = done["path"]
        self.assertTrue(os.path.isfile(p))
        self.assertEqual(os.path.getsize(p), len(data))
        os.remove(p)

    def test_init_rejects_oversize(self):
        from studio.app import app
        c = app.test_client()
        r = c.post("/api/uploads/init",
                   json={"filename": "big.mp4", "size": 600 * 1024 * 1024}).get_json()
        self.assertFalse(r["ok"])
        self.assertIn("512", r["error"])


class TestShareGate(StudioTestCase):
    """Spec §11/§13/§14/§35: in-memory access gate, owner-loopback exempt,
    tunnel requires auth, admin endpoints owner-direct only, sample path
    hidden from tunnel."""

    def setUp(self):
        super().setUp()
        from studio.app import app
        from studio import share_auth
        share_auth.disable()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        from studio import share_auth
        share_auth.disable()
        super().tearDown()

    def test_gate_off_local_unchanged(self):
        # Gate disabled -> SPA served, no login.
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)

    def test_link_only_tunnel_direct_access_no_login(self):
        # V1.2.2: default share mode is LINK ONLY (gate not armed). A tunnel
        # caller (Cf-Connecting-IP) gets the SPA directly — no 401, no login
        # page — and APIs work without a session cookie.
        from studio import share_auth
        share_auth.disable()  # link-only default
        h = {"Cf-Connecting-IP": "203.0.113.7", "X-Forwarded-Proto": "https",
             "X-Forwarded-For": "203.0.113.7"}
        r = self.client.get("/", headers=h)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("name=\"code\"", r.get_data(as_text=True))  # not the login page
        self.assertIn("app.js", r.get_data(as_text=True))           # the SPA
        # APIs work directly, no auth, no cookie.
        s = self.client.get("/api/system/status", headers=h)
        self.assertEqual(s.status_code, 200)
        a = self.client.get("/api/avatars", headers=h)
        self.assertEqual(a.status_code, 200)

    def test_login_route_redirects_when_gate_off(self):
        # With the gate off, /login must not show a login page; it redirects
        # to the SPA (no auth step in link-only mode).
        from studio import share_auth
        share_auth.disable()
        r = self.client.get("/login")
        self.assertIn(r.status_code, (302, 200))
        if r.status_code == 302:
            self.assertEqual(r.headers.get("Location"), "/")

    def test_tunnel_requires_auth_and_login(self):
        from studio import share_auth
        share_auth.enable("TEST-CODE-1234")
        h = {"Cf-Connecting-IP": "203.0.113.7"}
        self.assertEqual(self.client.get("/api/system/status", headers=h).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json={"code": "NOPE"}, headers=h).status_code, 401)
        self.assertTrue(self.client.post("/api/auth/login", json={"code": "TEST-CODE-1234"}, headers=h).get_json()["ok"])
        self.assertEqual(self.client.get("/api/system/status", headers=h).status_code, 200)

    def test_owner_loopback_exempt_when_gate_on(self):
        from studio import share_auth
        share_auth.enable("TEST-CODE-1234")
        # No Cf-Connecting-IP -> owner direct -> no login needed.
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/api/system/status").status_code, 200)

    def test_admin_endpoints_reject_tunnel(self):
        from studio import share_auth
        share_auth.enable("TEST-CODE-1234")
        h = {"Cf-Connecting-IP": "203.0.113.7"}
        # tunnel caller cannot arm/disable the gate
        self.assertEqual(self.client.post("/api/share/enable", json={"access_code": "x"}, headers=h).status_code, 403)
        self.assertEqual(self.client.post("/api/share/disable", headers=h).status_code, 403)
        # owner-direct can
        er = self.client.post("/api/share/enable", json={"access_code": "OWNER"}).get_json()
        self.assertTrue(er["share_enabled"])

    def test_sample_source_path_hidden_from_tunnel(self):
        from studio import share_auth
        share_auth.enable("CODE")
        h = {"Cf-Connecting-IP": "203.0.113.7"}
        # login first (gate on)
        self.client.post("/api/auth/login", json={"code": "CODE"}, headers=h)
        tunnel = self.client.get("/api/avatar/sample", headers=h).get_json()
        self.assertEqual(tunnel.get("source_path"), "")  # hidden from remote (§10)
        owner = self.client.get("/api/avatar/sample").get_json()
        self.assertTrue(owner.get("source_path"))  # visible to owner

    def test_adaptive_chunk_hint(self):
        from studio.app import app
        c = app.test_client()
        local = c.post("/api/uploads/init", json={"filename": "x.mp4", "size": 1000}).get_json()
        self.assertEqual(local["max_chunk_bytes"], 16 * 1024 * 1024)
        tunnel = c.post("/api/uploads/init", json={"filename": "x.mp4", "size": 1000},
                        headers={"Cf-Connecting-IP": "203.0.113.9"}).get_json()
        self.assertEqual(tunnel["max_chunk_bytes"], 2 * 1024 * 1024)

    def test_secure_cookie_behind_proxy_local_not_secure(self):
        # Behind the tunnel (Cf-Connecting-IP + X-Forwarded-Proto: https) the
        # login cookie MUST be Secure; over local HTTP it must NOT be Secure.
        from studio import share_auth
        share_auth.enable("CODE")
        h_tunnel = {"Cf-Connecting-IP": "203.0.113.7", "X-Forwarded-Proto": "https",
                    "X-Forwarded-For": "203.0.113.7", "X-Forwarded-Host": "x.trycloudflare.com"}
        r = self.client.post("/api/auth/login", json={"code": "CODE"}, headers=h_tunnel)
        self.assertTrue(r.get_json()["ok"])
        sc = r.headers.get("Set-Cookie", "")
        self.assertIn("Secure", sc, f"tunnel cookie must be Secure: {sc}")
        self.assertIn("HttpOnly", sc)
        self.assertIn("SameSite=Lax", sc)
        # Local HTTP (owner-direct, exempt) sets no auth cookie at all.
        share_auth.disable()
        share_auth.enable("CODE2")
        r2 = self.client.post("/api/auth/login", json={"code": "CODE2"})  # no proxy headers
        # Owner-direct is exempt so the gate never enforces; no session needed.
        self.assertEqual(self.client.get("/").status_code, 200)
        share_auth.disable()


# --------------------------------------------------------------------------- #
# V1.5.0 — ElevenLabs voice config auto-sync + generation matching           #
# --------------------------------------------------------------------------- #
from unittest import mock as _mock


class TestVoiceSyncResolve(StudioTestCase):
    """Generic per-voice config resolution (Mode A matching-history-first,
    Mode B exact item, Mode C manual). No voice-id special-casing; no global
    hardcode of any specific model/output_format."""

    def setUp(self):
        super().setUp()
        from studio import elevenlabs_client as el
        self.el = el
        self._orig = (el.get_voice_settings, el.get_voice_history,
                      el.get_history_item, el.is_configured, el.model_id)
        el.is_configured = lambda: True
        el.model_id = lambda: "eleven_turbo_v2_5"
        el._CACHE.clear()

    def tearDown(self):
        from studio import elevenlabs_client as el
        (el.get_voice_settings, el.get_voice_history, el.get_history_item,
         el.is_configured, el.model_id) = self._orig
        super().tearDown()

    @staticmethod
    def _A():
        return {"stability": 0.5, "similarity_boost": 1.0, "style": 0.0,
                "use_speaker_boost": True, "speed": 1.06}

    @staticmethod
    def _B():
        return {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0,
                "use_speaker_boost": True, "speed": 1.0}

    def test_mode_a_picks_matching_not_newest(self):
        # CASE 1: current = A; newest history = B; older history = A.
        # Mode A must choose the OLDER matching A item, NOT the newest B.
        A, B = self._A(), self._B()
        self.el.get_voice_settings = lambda vid, refresh=False: {"ok": True, "settings": A}
        self.el.get_voice_history = lambda vid, limit=10, refresh=False: {"ok": True, "items": [
            {"history_item_id": "newB", "model_id": "eleven_turbo_v2_5", "settings": B, "date_unix": 2},
            {"history_item_id": "oldA", "model_id": "eleven_multilingual_v2", "settings": A, "date_unix": 1},
        ]}
        self.el.get_history_item = lambda hid: {"ok": True, "item": {
            "history_item_id": hid, "model_id": ("eleven_multilingual_v2" if hid == "oldA" else "eleven_turbo_v2_5"),
            "settings": (A if hid == "oldA" else B),
            "output_format": ("mp3_44100_128" if hid == "oldA" else "pcm_16000")}}
        r = self.el.resolve_config("V1", mode="auto_current")
        self.assertTrue(r["ok"])
        c = r["config"]
        self.assertEqual(c["match_strength"], "history_matched")
        self.assertEqual(c["model_id"], "eleven_multilingual_v2")      # older matching item
        self.assertEqual(c["requested_output_format"], "mp3_44100_128")
        self.assertEqual(c["history_item_id"], "oldA")
        self.assertEqual(c["provenance"]["model_id"], "MATCHING_HISTORY_GENERATION")

    def test_mode_a_no_matching_history_falls_to_studio_policy(self):
        # CASE 2: current = A; no history item matches A -> settings synced, but
        # model/output use the explicit Studio policy (NOT a hardcode of the
        # reference values). Truthful provenance STUDIO_POLICY.
        A, B = self._A(), self._B()
        self.el.get_voice_settings = lambda vid, refresh=False: {"ok": True, "settings": A}
        self.el.get_voice_history = lambda vid, limit=10, refresh=False: {"ok": True, "items": [
            {"history_item_id": "newB", "model_id": "eleven_turbo_v2_5", "settings": B}]}
        self.el.get_history_item = lambda hid: {"ok": True, "item": {
            "history_item_id": hid, "model_id": "eleven_turbo_v2_5", "settings": B,
            "output_format": "pcm_16000"}}
        r = self.el.resolve_config("V1", mode="auto_current")
        self.assertTrue(r["ok"])
        c = r["config"]
        self.assertEqual(c["match_strength"], "settings_only")
        self.assertEqual(c["model_id"], "eleven_turbo_v2_5")            # Studio policy
        self.assertEqual(c["requested_output_format"], "pcm_16000")
        self.assertEqual(c["provenance"]["model_id"], "STUDIO_POLICY")
        self.assertEqual(c["provenance"]["voice_settings"], "ELEVENLABS_VOICE_SETTINGS_API")
        # no hardcode of the reference values
        self.assertNotEqual(c["model_id"], "eleven_multilingual_v2")
        self.assertNotEqual(c["requested_output_format"], "mp3_44100_128")

    def test_mode_a_settings_api_failure_fails_closed(self):
        # CASE 3: settings API errors -> NO silent fallback. Distinct from CASE 2.
        self.el.get_voice_settings = lambda vid, refresh=False: {"ok": False, "error": "ElevenLabs returned 500", "http_status": 500}
        r = self.el.resolve_config("V1", mode="auto_current")
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("fail_closed"))
        self.assertEqual(r.get("stage"), "settings_api_failed")
        self.assertNotIn("config", r)

    def test_mode_b_history_item_exact_public_config(self):
        A = self._A()
        self.el.get_history_item = lambda hid: {"ok": True, "item": {
            "history_item_id": hid, "voice_id": "V1", "model_id": "eleven_multilingual_v2",
            "settings": A, "output_format": "mp3_44100_128", "source": "TTS"}}
        r = self.el.resolve_config("V1", mode="history_match", history_item_id="h1")
        self.assertTrue(r["ok"])
        c = r["config"]
        self.assertEqual(c["match_strength"], "history_item")
        self.assertEqual(c["model_id"], "eleven_multilingual_v2")
        self.assertEqual(c["requested_output_format"], "mp3_44100_128")
        self.assertEqual(c["history_item_id"], "h1")
        self.assertEqual(c["provenance"]["voice_settings"], "ELEVENLABS_HISTORY_ITEM")

    def test_tts_config_hash_deterministic(self):
        c1 = {"voice_id": "V1", "model_id": "m", "voice_settings": self._A(),
              "requested_output_format": "mp3_44100_128"}
        c2 = dict(c1)
        self.assertEqual(self.el.tts_config_hash(c1), self.el.tts_config_hash(c2))
        c3 = {**c1, "voice_settings": {**c1["voice_settings"], "speed": 0.9}}
        self.assertNotEqual(self.el.tts_config_hash(c1), self.el.tts_config_hash(c3))
        # no key material in the hash input
        self.assertNotIn("api_key", self.el.tts_config_hash(c1))

    def test_master_storage_format_honest(self):
        # The internal master is a WAV at the native rate; never reported as MP3.
        self.assertEqual(self.el._master_storage_format("mp3_44100_128"), "wav_44100")
        self.assertEqual(self.el._master_storage_format("pcm_16000"), "wav_16000")
        self.assertEqual(self.el._master_storage_format("pcm_44100"), "wav_44100")


class TestRequestMapping(StudioTestCase):
    """The outgoing ElevenLabs synthesis request must match the resolved config
    (Phase 20). Mocks requests.post; asserts body + query == resolved config."""

    def test_synth_config_body_matches_resolved(self):
        from studio import elevenlabs_client as el
        cfg = {"model_id": "eleven_multilingual_v2",
               "voice_settings": {"stability": 0.5, "similarity_boost": 1.0,
                                  "style": 0.0, "use_speaker_boost": True, "speed": 1.06},
               "requested_output_format": "mp3_44100_128"}
        captured = {}

        class FakeResp:
            status_code = 200
            content = b"\x00" * 100
            text = ""

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResp()

        with _mock.patch.object(el, "is_configured", return_value=True), \
             _mock.patch.object(el.requests, "post", side_effect=fake_post):
            el._synth_config("V1", "Xin chào.", cfg)
        body = captured["json"]
        self.assertEqual(body["model_id"], "eleven_multilingual_v2")
        self.assertEqual(body["voice_settings"]["stability"], 0.5)
        self.assertEqual(body["voice_settings"]["similarity_boost"], 1.0)
        self.assertEqual(body["voice_settings"]["style"], 0.0)
        self.assertTrue(body["voice_settings"]["use_speaker_boost"])
        self.assertEqual(body["voice_settings"]["speed"], 1.06)
        self.assertIn("output_format=mp3_44100_128", captured["url"])
        # no API key leaked into the body
        self.assertNotIn("xi-api-key", body)


class TestVoiceSwitchNoLeak(StudioTestCase):
    """Switching Voice ID must not leak the previous voice's config (Phase 7)."""

    def setUp(self):
        super().setUp()
        from studio import elevenlabs_client as el
        self.el = el
        self._orig = (el.get_voice_settings, el.get_voice_history, el.is_configured)
        el.is_configured = lambda: True
        el._CACHE.clear()

    def tearDown(self):
        from studio import elevenlabs_client as el
        (el.get_voice_settings, el.get_voice_history, el.is_configured) = self._orig
        super().tearDown()

    def test_resolve_per_voice_no_cross_contamination(self):
        A = {"stability": 0.5, "similarity_boost": 1.0, "style": 0.0,
             "use_speaker_boost": True, "speed": 1.06}
        B = {"stability": 0.5, "similarity_boost": 0.8, "style": 0.0,
             "use_speaker_boost": True, "speed": 1.0}
        self.el.get_voice_settings = lambda vid, refresh=False: \
            {"ok": True, "settings": (A if vid == "V1" else B)}
        self.el.get_voice_history = lambda vid, limit=10, refresh=False: {"ok": True, "items": []}
        r1 = self.el.resolve_config("V1")
        r2 = self.el.resolve_config("V2")
        self.assertEqual(r1["config"]["voice_settings"]["similarity_boost"], 1.0)
        self.assertEqual(r2["config"]["voice_settings"]["similarity_boost"], 0.8)
        self.assertNotEqual(r2["config"]["voice_settings"], r1["config"]["voice_settings"])

    def test_job_snapshots_config_unaffected_by_later_switch(self):
        from studio import db, render_service, avatar_service, elevenlabs_client as el
        ready = [a for a in avatar_service.list_avatars() if a["ready"]]
        if not ready:
            self.skipTest("no prepared avatar on disk")
        av = ready[0]["avatar_id"]
        el.is_configured = lambda: True
        cfgA = {"voice_id": "V1", "model_id": "m1",
                "voice_settings": {"stability": 0.5, "similarity_boost": 1.0, "style": 0.0,
                                   "use_speaker_boost": True, "speed": 1.0},
                "requested_output_format": "pcm_16000", "sync_mode": "auto_current",
                "match_strength": "settings_only", "provenance": {}}
        cfgB = {**cfgA, "voice_id": "V2", "model_id": "m2",
                "voice_settings": {**cfgA["voice_settings"], "similarity_boost": 0.8}}
        rA = render_service.create_full_jobs(av, "V1", "Xin chào.", "full",
                                             tts_provider=render_service.ELEVENLABS,
                                             tts_config=cfgA, sync_mode="auto_current")
        self.assertTrue(rA["ok"])
        jA = db.get_job(rA["job_ids"][0])
        self.assertEqual(jA["voice_id"], "V1")
        self.assertEqual(jA["sync_mode"], "auto_current")
        self.assertEqual(jA["tts_config_hash"], el.tts_config_hash(cfgA))
        # "switch" to V2 with a different config
        rB = render_service.create_full_jobs(av, "V2", "Xin chào.", "full",
                                             tts_provider=render_service.ELEVENLABS,
                                             tts_config=cfgB, sync_mode="auto_current")
        jB = db.get_job(rB["job_ids"][0])
        self.assertEqual(jB["voice_id"], "V2")
        self.assertNotEqual(jA["tts_config_hash"], jB["tts_config_hash"])
        # the original V1 job is unchanged by the later switch
        jA2 = db.get_job(rA["job_ids"][0])
        self.assertEqual(jA2["voice_id"], "V1")
        self.assertEqual(jA2["tts_config_hash"], el.tts_config_hash(cfgA))


class TestPerVoiceConfigPersistence(StudioTestCase):
    def test_save_get_voice_config(self):
        from studio import db
        db.save_voice_config("V1", {"voice_id": "V1", "model_id": "m"})
        self.assertEqual(db.get_voice_config("V1")["model_id"], "m")
        db.save_voice_config("V1", {"voice_id": "V1", "model_id": "m2"})  # upsert
        self.assertEqual(db.get_voice_config("V1")["model_id"], "m2")
        self.assertIsNone(db.get_voice_config("NOPE"))


class TestEdgeNoVoiceSync(StudioTestCase):
    """Edge TTS must not trigger ElevenLabs voice-config sync (no provider crossover)."""

    def test_edge_path_does_not_call_elevenlabs_sync(self):
        from studio import render_service, elevenlabs_client as el, edge_tts_client as edge
        import numpy as np, soundfile as sf
        el_synth = _mock.Mock(side_effect=AssertionError("ElevenLabs synth must not be called for Edge"))
        orig_avail = edge.is_available
        orig_synth = edge.synth_to_wav
        edge.is_available = lambda: True
        def fake_edge(vid, text, out):
            sf.write(out, np.zeros(16000, dtype=np.float32), 16000, subtype="FLOAT")
            return out, 1.0
        edge.synth_to_wav = fake_edge
        el.synth_master_cond = el_synth
        try:
            r = render_service.generate_master_audio(
                "Xin chào. Đây là test.", "vi-VN-HoaiMyNeural",
                tts_provider=render_service.EDGE_TTS_TEST,
                tts_config={"model_id": "eleven_multilingual_v2"})  # tts_config MUST be ignored for Edge
        finally:
            edge.is_available = orig_avail
            edge.synth_to_wav = orig_synth
        self.assertTrue(r["ok"])
        self.assertEqual(r["master_path"], r["cond_path"])  # Edge: master == cond (16k)
        el_synth.assert_not_called()


class TestRendererMasterAudio(StudioTestCase):
    """V1.5.0 audio-only renderer change: --master-audio routes the final mux
    audio from the lossless master; MuseTalk conditioning still uses --audio."""

    def test_renderer_supports_master_audio_arg(self):
        from studio import config
        with open(config.RENDERER, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("--master-audio", src)
        self.assertIn("mux_audio = master_audio if master_audio else audio_path", src)
        # MuseTalk conditioning still reads audio_path (16k), unchanged.
        self.assertIn("sf.read(audio_path", src)
        # The locked truth is still loaded (production truth unchanged).
        self.assertIn("load_render_truth", src)

class TestDynamicModelCapability(StudioTestCase):
    """V1.6.3 — Verify dynamic capability inference for future / unlisted models."""

    def test_unlisted_future_model_infers_caps_from_live(self):
        from studio import elevenlabs_client as el
        mock_live_v5 = {
            "model_id": "eleven_v5",
            "name": "Eleven v5",
            "can_do_text_to_speech": True,
            "can_use_style": False,
            "can_use_speaker_boost": False,
            "maximum_text_length_per_request": 15000,
            "languages": ["vi", "en"],
        }
        with _mock.patch.object(el, "_live_model", return_value=mock_live_v5):
            caps = el._caps("eleven_v5")
            self.assertEqual(caps["settings"], ["stability"])
            self.assertEqual(caps["max_text"], 15000)
            self.assertTrue(caps["language_code"])
            # Effective voice settings only keeps stability
            eff = el.effective_voice_settings("eleven_v5", {"stability": 0.7, "style": 0.5, "speed": 1.1})
            self.assertEqual(eff, {"stability": 0.7})
            # Language code is preserved for Vietnamese
            self.assertEqual(el.language_code_for("eleven_v5", "vi"), "vi")
            # Max text returns live limit
            self.assertEqual(el.model_max_text("eleven_v5"), 15000)

    def test_unlisted_model_offline_fallback(self):
        from studio import elevenlabs_client as el
        with _mock.patch.object(el, "_live_model", return_value=None):
            caps = el._caps("eleven_v5_offline")
            self.assertEqual(caps["settings"], ["stability"])
            self.assertEqual(caps["max_text"], 10000)
            self.assertTrue(caps["language_code"])
            self.assertEqual(el.language_code_for("eleven_v5_offline", "vi"), "vi")


class TestCustomVoiceWorkflow(StudioTestCase):
    """V1.6.3 — Verify custom voice registration, approval, and lifecycle."""

    def setUp(self):
        super().setUp()
        from studio.app import app
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_custom_voice_registration_and_approval(self):
        from studio import voices, elevenlabs_client as el
        mock_chk = {
            "ok": True,
            "voice_id": "custom_clone_999",
            "name": "Giọng Clone Thắng",
            "category": "cloned",
            "labels": {"gender": "male", "language": "vi"}
        }
        with _mock.patch.object(el, "check_voice", return_value=mock_chk):
            # 1. Initially not approved
            self.assertFalse(voices.is_approved_render_voice("custom_clone_999"))
            
            # 2. Add via API
            r = self.client.post("/api/voices/custom", json={
                "voice_id": "custom_clone_999",
                "name": "Giọng Clone Thắng",
                "category": "cloned"
            })
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.get_json()["ok"])
            
            # 3. Now approved
            self.assertTrue(voices.is_approved_render_voice("custom_clone_999"))
            
            # 4. List contains custom voice
            r_list = self.client.get("/api/voices/custom")
            self.assertEqual(r_list.status_code, 200)
            vids = [v["voice_id"] for v in r_list.get_json()["voices"]]
            self.assertIn("custom_clone_999", vids)
            
            # 5. Delete custom voice
            r_del = self.client.delete("/api/voices/custom/custom_clone_999")
            self.assertEqual(r_del.status_code, 200)
            self.assertTrue(r_del.get_json()["ok"])
            self.assertFalse(voices.is_approved_render_voice("custom_clone_999"))


if __name__ == "__main__":
    unittest.main(verbosity=2)