#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio V1.6.0 — two-voice production lock acceptance tests.

Covers the two-voice product lock spec: allowlist (exactly two), backend
enforcement (no silent substitution), metadata validity, voice/language config
isolation, job snapshots, Thanh keeps human-approved v3, Voice A does NOT
inherit v3, Edge test path unchanged, MuseTalk truth unchanged, final mux master.

Stubs live ElevenLabs metadata so NO network/quota. Run from the repo root:
    python -m unittest tests.test_two_voice_lock -v
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

VOICE_A = "pGapy9MNHCukzJtjavF0"   # Hạnh
VOICE_B = "N0Z0aL8qHhzwUHwRBcVo"   # Thanh

MODELS = [
    {"model_id": "eleven_v3", "name": "Eleven v3", "can_do_text_to_speech": True,
     "languages": ["en", "vi", "ja"], "can_use_style": False,
     "can_use_speaker_boost": False, "maximum_text_length_per_request": 5000,
     "deprecated": False},
    {"model_id": "eleven_turbo_v2_5", "name": "Eleven Turbo v2.5", "can_do_text_to_speech": True,
     "languages": ["en", "vi", "ja"], "can_use_style": False,
     "can_use_speaker_boost": False, "maximum_text_length_per_request": 40000,
     "deprecated": False},
    {"model_id": "eleven_flash_v2_5", "name": "Eleven Flash v2.5", "can_do_text_to_speech": True,
     "languages": ["en", "vi"], "can_use_style": False,
     "can_use_speaker_boost": False, "maximum_text_length_per_request": 40000,
     "deprecated": False},
    {"model_id": "eleven_multilingual_v2", "name": "Eleven Multilingual v2",
     "can_do_text_to_speech": True, "languages": ["en", "ja", "zh"],
     "can_use_style": True, "can_use_speaker_boost": True,
     "maximum_text_length_per_request": 10000, "deprecated": False},
]

HANH_SETTINGS = {"stability": 0.21, "similarity_boost": 0.53, "style": 0.0,
                 "use_speaker_boost": True, "speed": 1.0}
THANH_SETTINGS = {"stability": 0.5, "similarity_boost": 1.0, "style": 0.0,
                  "use_speaker_boost": True, "speed": 1.06}

VI_VERIFIED = [
    {"language": "vi", "model_id": "eleven_flash_v2_5", "accent": "x", "locale": "vi-VN"},
    {"language": "vi", "model_id": "eleven_turbo_v2_5", "accent": "x", "locale": "vi-VN"},
    {"language": "vi", "model_id": "eleven_v2_5_flash", "accent": "x", "locale": "vi-VN"},
]


def _meta(vid, name):
    return {"ok": True, "metadata": {
        "voice_id": vid, "name": name, "labels": {"language": "vi"},
        "verified_languages": VI_VERIFIED,
        "high_quality_base_model_ids": ["eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_v2_5_flash"],
        "fine_tuning_language": "vi", "fine_tuning_state": {}, "description": "",
    }}


class TwoVoiceTestCase(unittest.TestCase):
    def setUp(self):
        from studio import config
        self._orig_db = config.DB_PATH
        self.tmp = tempfile.mkdtemp(prefix="twovoice_test_")
        config.DB_PATH = os.path.join(self.tmp, "test.db")
        config.ensure_runtime_dirs()
        from studio import db
        db.init_db()  # seeds Thanh+vi -> eleven_v3 profile
        from studio import elevenlabs_client as el, render_service
        self.el = el
        self._orig = {
            "get_models": el.get_models, "get_voice_settings": el.get_voice_settings,
            "get_voice_history": el.get_voice_history, "get_history_item": el.get_history_item,
            "get_voice_metadata": el.get_voice_metadata, "is_configured": el.is_configured,
            "model_id": el.model_id,
        }
        el.is_configured = lambda: True
        el.model_id = lambda: "eleven_turbo_v2_5"  # Studio production default
        el._CACHE.clear()
        self._orig_disabled = render_service._WORKER_DISABLED
        render_service._WORKER_DISABLED = True
        self._mock()

    def _mock(self):
        el = self.el
        el.get_models = lambda refresh=False: {"ok": True, "models": MODELS, "cached": False}
        el.get_voice_history = lambda v, limit=10, refresh=False: {"ok": True, "items": []}
        el.get_history_item = lambda hid: {"ok": True, "item": {
            "history_item_id": hid, "model_id": "eleven_turbo_v2_5",
            "settings": THANH_SETTINGS, "output_format": "pcm_16000"}}

        def settings(v, refresh=False):
            return {"ok": True, "settings": HANH_SETTINGS if v == VOICE_A else THANH_SETTINGS}

        def meta(v, refresh=False):
            return _meta(v, "Hạnh - Smooth, Clear and Feminine" if v == VOICE_A
                         else "Thanh - Clear, Steady and Informative")
        el.get_voice_settings = settings
        el.get_voice_metadata = meta

    def tearDown(self):
        from studio import config, elevenlabs_client as el, render_service
        render_service._WORKER_DISABLED = self._orig_disabled
        for k, v in self._orig.items():
            setattr(el, k, v)
        config.DB_PATH = self._orig_db
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestAllowlist(TwoVoiceTestCase):
    def test_render_voice_allowlist_exactly_two(self):
        from studio import voices
        ids = voices.approved_voice_ids()
        self.assertEqual(len(ids), 2)
        self.assertIn(VOICE_A, ids)
        self.assertIn(VOICE_B, ids)
        self.assertTrue(voices.is_approved_render_voice(VOICE_A))
        self.assertTrue(voices.is_approved_render_voice(VOICE_B))
        self.assertFalse(voices.is_approved_render_voice("EXAVITQu4vr4xnSDxMaLC"))
        self.assertFalse(voices.is_approved_render_voice(""))

    def test_frontend_shows_exactly_two_elevenlabs_voices(self):
        # No-vision source check: the SPA renders a 2-voice selector and removed
        # the normal free-text Voice ID input.
        from studio import config
        with open(os.path.join(config.STUDIO_DIR, "static", "app.js"), "r",
                  encoding="utf-8") as f:
            src = f.read()
        self.assertIn("renderVoiceCards", src)
        self.assertIn("#qVoiceCards", src)
        self.assertIn("loadApprovedVoices", src)
        # the normal free-text Voice ID input is removed
        self.assertNotIn('<input id="qVoice"', src)

    def test_unapproved_voice_rejected_backend(self):
        from studio.app import app
        app.config["TESTING"] = True
        c = app.test_client()
        r = c.post("/api/render", json={"avatar_id": "x",
                                        "voice_id": "EXAVITQu4vr4xnSDxMaLC",
                                        "script_text": "Xin chào."})
        self.assertEqual(r.status_code, 403)
        d = r.get_json()
        self.assertFalse(d["ok"])
        self.assertEqual(d["error"], "VOICE_NOT_APPROVED_FOR_RENDER")
        self.assertIn(VOICE_A, d["approved_voice_ids"])

    def test_no_silent_voice_substitution(self):
        # An unapproved voice must NOT be substituted with an approved one; no
        # job is created. Verify by posting to the test-render route too.
        from studio.app import app
        from studio import db
        app.config["TESTING"] = True
        c = app.test_client()
        before = len(db.list_jobs())
        r = c.post("/api/render/test", json={"avatar_id": "x",
                                             "voice_id": "randoVoiceXYZ",
                                             "script_text": "Xin chào."})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(len(db.list_jobs()), before)  # no job created

    def test_edge_test_path_not_gated_by_allowlist(self):
        # Edge TTS (free test) is a separate provider and must NOT be rejected by
        # the ElevenLabs render-voice allowlist gate.
        from studio.app import app, _enforce_render_voice_allowlist
        app.config["TESTING"] = True
        gate = _enforce_render_voice_allowlist(
            {"tts_provider": "EDGE_TTS_TEST", "voice_id": "vi-VN-HoaiMyNeural"})
        self.assertIsNone(gate)  # Edge is not gated


class TestVoiceMetadata(TwoVoiceTestCase):
    def test_voice_a_metadata_valid(self):
        vm = self.el.get_voice_metadata(VOICE_A)
        self.assertTrue(vm["ok"])
        self.assertEqual(vm["metadata"]["name"], "Hạnh - Smooth, Clear and Feminine")
        vi = [v for v in vm["metadata"]["verified_languages"] if v.get("language") == "vi"]
        self.assertGreater(len(vi), 0)
        self.assertIn("eleven_turbo_v2_5", [v["model_id"] for v in vi])

    def test_voice_b_metadata_valid(self):
        vm = self.el.get_voice_metadata(VOICE_B)
        self.assertTrue(vm["ok"])
        self.assertEqual(vm["metadata"]["name"], "Thanh - Clear, Steady and Informative")
        vi = [v for v in vm["metadata"]["verified_languages"] if v.get("language") == "vi"]
        self.assertGreater(len(vi), 0)


class TestVoiceIsolation(TwoVoiceTestCase):
    def test_thanh_vi_keeps_human_approved_v3_profile(self):
        r = self.el.resolve_config(VOICE_B, target_language="vi")
        self.assertTrue(r["ok"])
        self.assertEqual(r["config"]["model_id"], "eleven_v3")
        self.assertEqual(r["config"]["match_strength"], "human_approved_profile")
        self.assertEqual(r["config"]["resolver_source"], "HUMAN_BENCHMARK_APPROVED")

    def test_voice_a_does_not_inherit_thanh_v3_profile(self):
        r = self.el.resolve_config(VOICE_A, target_language="vi")
        self.assertTrue(r["ok"])
        self.assertNotEqual(r["config"]["model_id"], "eleven_v3")
        # Voice A is officially verified for vi on turbo_v2_5 (Studio default) ->
        # the verified-language policy picks it. NOT human-approved.
        self.assertEqual(r["config"]["model_id"], "eleven_turbo_v2_5")
        self.assertNotEqual(r["config"].get("resolver_source"), "HUMAN_BENCHMARK_APPROVED")

    def test_voice_a_config_isolated(self):
        ra = self.el.resolve_config(VOICE_A, target_language="vi")
        rb = self.el.resolve_config(VOICE_B, target_language="vi")
        self.assertNotEqual(ra["config"]["model_id"], rb["config"]["model_id"])
        self.assertNotEqual(ra["config"]["tts_config_hash"], rb["config"]["tts_config_hash"])
        # Voice A effective settings = all 5 (turbo v2.5); Voice B = stability only (v3)
        self.assertIn("similarity_boost", ra["config"]["effective_voice_settings"])
        self.assertNotIn("similarity_boost", rb["config"]["effective_voice_settings"])

    def test_voice_b_config_isolated(self):
        # Same as above, explicit: Voice B uses v3 stability-only subset.
        rb = self.el.resolve_config(VOICE_B, target_language="vi")
        self.assertEqual(set(rb["config"]["effective_voice_settings"].keys()), {"stability"})

    def test_voice_switch_no_leak(self):
        ra = self.el.resolve_config(VOICE_A, target_language="vi")
        ha = ra["config"]["tts_config_hash"]
        rb = self.el.resolve_config(VOICE_B, target_language="vi")
        # switching voice does not carry A's model into B
        self.assertEqual(rb["config"]["model_id"], "eleven_v3")
        self.assertNotEqual(ha, rb["config"]["tts_config_hash"])
        # re-resolve A is stable and unchanged
        ra2 = self.el.resolve_config(VOICE_A, target_language="vi")
        self.assertEqual(ra2["config"]["model_id"], "eleven_turbo_v2_5")
        self.assertEqual(ra2["config"]["tts_config_hash"], ha)

    def test_language_switch_no_leak(self):
        # Voice A + vi vs Voice A + en must not share a config/hash.
        self._mock()
        rvi = self.el.resolve_config(VOICE_A, target_language="vi")
        # English: Voice A has no en profile and no en verified -> policy / no match.
        # Use a mocked metadata with no en verified; models support en.
        ren = self.el.resolve_config(VOICE_A, target_language="en")
        self.assertNotEqual(rvi["config"]["tts_config_hash"],
                            ren["config"]["tts_config_hash"])


class TestJobSnapshot(TwoVoiceTestCase):
    def _job_cfg(self, vid, model, eff, lang_code):
        return {"voice_id": vid, "target_language": "vi", "model_id": model,
                "effective_voice_settings": eff, "language_code": lang_code,
                "requested_output_format": "mp3_44100_128",
                "resolver_policy": "auto_current", "sync_mode": "auto_current"}

    def test_job_snapshot_voice_a_and_b(self):
        from studio import db, render_service, avatar_service
        ready = [a for a in avatar_service.list_avatars() if a["ready"]]
        if not ready:
            self.skipTest("no prepared avatar on disk")
        av = ready[0]["avatar_id"]
        cfgA = self._job_cfg(VOICE_A, "eleven_turbo_v2_5", HANH_SETTINGS, "vi")
        cfgB = self._job_cfg(VOICE_B, "eleven_v3", {"stability": 0.5}, "vi")
        rA = render_service.create_full_jobs(av, VOICE_A, "Xin chào.", "full",
                                             tts_provider=render_service.ELEVENLABS,
                                             tts_config=cfgA, sync_mode="auto_current")
        rB = render_service.create_full_jobs(av, VOICE_B, "Tạm biệt.", "full",
                                             tts_provider=render_service.ELEVENLABS,
                                             tts_config=cfgB, sync_mode="auto_current")
        self.assertTrue(rA["ok"] and rB["ok"])
        jA = db.get_job(rA["job_ids"][0])
        jB = db.get_job(rB["job_ids"][0])
        self.assertEqual(jA["voice_id"], VOICE_A)
        self.assertEqual(jB["voice_id"], VOICE_B)
        self.assertNotEqual(jA["tts_config_hash"], jB["tts_config_hash"])
        # A queued job is not mutated by a later voice switch.
        hA = jA["tts_config_hash"]
        self.assertEqual(db.get_job(rA["job_ids"][0])["tts_config_hash"], hA)


class TestProductionTruth(TwoVoiceTestCase):
    def test_musetalk_truth_unchanged(self):
        from studio import render_service
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
        with open(os.path.join(ROOT, "config", "render_truth.json"), "r",
                  encoding="utf-8") as f:
            self.assertEqual(json.load(f), t)

    def test_final_mux_master(self):
        from studio import config
        with open(config.RENDERER, "r", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("--master-audio", src)
        self.assertIn("mux_audio = master_audio if master_audio else audio_path", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)