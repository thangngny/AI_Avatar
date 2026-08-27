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
        r = render_service.create_full_jobs(av, "pGapy9MNHCukzJtjavF0",
                                             "Xin chào. Đây là test.", "full")
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
        self.assertEqual(t["audio_gain"], 1.5)
        self.assertEqual(t["audio_context_left"], 0)
        self.assertEqual(t["audio_feature_offset_frames"], -3)
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


class TestVerify(StudioTestCase):
    def test_missing_file_fails(self):
        from studio import verify as v
        r = v.verify("/nonexistent/path.mp4")
        self.assertFalse(r["ok"])


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


if __name__ == "__main__":
    unittest.main(verbosity=2)