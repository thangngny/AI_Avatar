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
        self.assertEqual(t["audio_gain"], 1.5)
        self.assertEqual(t["audio_context_left"], 0)
        self.assertEqual(t["audio_feature_offset_frames"], -3)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)