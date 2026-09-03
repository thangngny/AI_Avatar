#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio V1.6.0 — Preview vs Render TTS consistency regression tests.

Targets the proven root cause of the "voice sounds correct in 'Listen to a sample'
but different after final render" defect:

  Preview/Script-Preview path resolves Thanh+vi -> eleven_v3 (HUMAN_BENCHMARK_APPROVED)
  via el.resolve_config + el.synth_master_cond. But a render job submitted with
  tts_config=None used to silently take the legacy el.synth_to_wav branch
  (hardcoded eleven_turbo_v2_5, 16 kHz, no language_code) -> a DIFFERENT model than
  the user auditioned.

The V1.6.0 fix: render_service re-resolves server-side (same resolver as preview)
when tts_config is None, and fails closed instead of silently falling back.

Stubs live ElevenLabs metadata so NO network/quota. Run from the repo root:
    python -m unittest tests.test_tts_preview_render_consistency -v
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
]

THANH_SETTINGS = {"stability": 0.5, "similarity_boost": 1.0, "style": 0.0,
                  "use_speaker_boost": True, "speed": 1.06}
HANH_SETTINGS = {"stability": 0.21, "similarity_boost": 0.53, "style": 0.0,
                 "use_speaker_boost": True, "speed": 1.0}

VI_VERIFIED = [
    {"language": "vi", "model_id": "eleven_turbo_v2_5", "accent": "x", "locale": "vi-VN"},
]


def _meta(vid, name):
    return {"ok": True, "metadata": {
        "voice_id": vid, "name": name, "labels": {"language": "vi"},
        "verified_languages": VI_VERIFIED,
        "high_quality_base_model_ids": ["eleven_turbo_v2_5"],
        "fine_tuning_language": "vi", "fine_tuning_state": {}, "description": "",
    }}


class ConsistencyTestCase(unittest.TestCase):
    def setUp(self):
        from studio import config
        self._orig_db = config.DB_PATH
        self.tmp = tempfile.mkdtemp(prefix="tts_consistency_test_")
        config.DB_PATH = os.path.join(self.tmp, "test.db")
        config.ensure_runtime_dirs()
        from studio import db
        db.init_db()  # seeds Thanh+vi -> eleven_v3 profile
        from studio import elevenlabs_client as el, render_service, avatar_service
        self.el = el
        self.render_service = render_service
        self._orig = {
            "get_models": el.get_models, "get_voice_settings": el.get_voice_settings,
            "get_voice_history": el.get_voice_history, "get_history_item": el.get_history_item,
            "get_voice_metadata": el.get_voice_metadata, "is_configured": el.is_configured,
            "model_id": el.model_id, "resolve_config": el.resolve_config,
            "list_avatars": avatar_service.list_avatars,
        }
        el.is_configured = lambda: True
        el.model_id = lambda: "eleven_turbo_v2_5"  # the legacy default the bug used
        el._CACHE.clear()
        self._orig_disabled = render_service._WORKER_DISABLED
        render_service._WORKER_DISABLED = True
        self._mock()

        # Mock a ready avatar so create_*_job does not skip on missing assets.
        self._fake_avatar = {"avatar_id": "av_test_001", "ready": True}
        avatar_service.list_avatars = lambda: [self._fake_avatar]

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
        # resolve_config stays REAL — it uses the mocked metadata/models above +
        # the seeded Thanh+vi profile. This proves the real resolver path.

    def tearDown(self):
        from studio import config, elevenlabs_client as el, render_service, avatar_service
        render_service._WORKER_DISABLED = self._orig_disabled
        for k, v in self._orig.items():
            if k == "list_avatars":
                avatar_service.list_avatars = v
            else:
                setattr(el, k, v)
        config.DB_PATH = self._orig_db
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _job_cfg(self, voice_id, model_id, settings, lang):
        return {"voice_id": voice_id, "target_language": lang, "model_id": model_id,
                "voice_settings": settings, "requested_output_format": "mp3_44100_128",
                "resolver_policy": "auto_current", "sync_mode": "auto_current"}


class TestRenderResolvesWhenNoConfig(ConsistencyTestCase):
    def test_full_render_resolves_thanh_vi_to_eleven_v3(self):
        """A render submitted WITHOUT tts_config must re-resolve to eleven_v3
        (same as preview), NOT fall to the legacy eleven_turbo_v2_5 branch."""
        r = self.render_service.create_full_jobs(
            "av_test_001", VOICE_B, "Xin chào, đây là đoản văn kiểm tra.", "full",
            tts_provider=self.render_service.ELEVENLABS,
            tts_config=None, target_language="vi")
        self.assertTrue(r["ok"], r)
        job = __import__("studio.db", fromlist=["db"]).get_job(r["job_ids"][0])
        self.assertIsNotNone(job["tts_config"], "tts_config must NOT be NULL after fix")
        cfg = json.loads(job["tts_config"])
        self.assertEqual(cfg["model_id"], "eleven_v3")
        self.assertEqual(cfg.get("language_code"), "vi")
        self.assertEqual(cfg.get("match_strength"), "human_approved_profile")

    def test_test_render_resolves_thanh_vi_to_eleven_v3(self):
        r = self.render_service.create_test_job(
            "av_test_001", VOICE_B, "Xin chào đoản văn.", test_mode=True,
            tts_provider=self.render_service.ELEVENLABS,
            tts_config=None, target_language="vi")
        self.assertTrue(r["ok"], r)
        job = __import__("studio.db", fromlist=["db"]).get_job(r["job_id"])
        cfg = json.loads(job["tts_config"])
        self.assertEqual(cfg["model_id"], "eleven_v3")
        self.assertEqual(cfg.get("language_code"), "vi")

    def test_render_does_not_reresolve_to_legacy_default(self):
        """The snapshotted model must NOT be the legacy eleven_turbo_v2_5 default
        for Thanh+vi."""
        r = self.render_service.create_full_jobs(
            "av_test_001", VOICE_B, "Đoản văn.", "full",
            tts_provider=self.render_service.ELEVENLABS,
            tts_config=None, target_language="vi")
        self.assertTrue(r["ok"])
        job = __import__("studio.db", fromlist=["db"]).get_job(r["job_ids"][0])
        cfg = json.loads(job["tts_config"])
        self.assertNotEqual(cfg["model_id"], "eleven_turbo_v2_5")
        self.assertEqual(cfg["model_id"], "eleven_v3")

    def test_no_silent_legacy_settings_when_resolved(self):
        """Resolved v3 config sends stability ONLY (not the 5 legacy fields)."""
        r = self.render_service.create_full_jobs(
            "av_test_001", VOICE_B, "Đoản văn.", "full",
            tts_provider=self.render_service.ELEVENLABS,
            tts_config=None, target_language="vi")
        self.assertTrue(r["ok"])
        job = __import__("studio.db", fromlist=["db"]).get_job(r["job_ids"][0])
        cfg = json.loads(job["tts_config"])
        eff = cfg.get("effective_voice_settings") or {}
        self.assertEqual(set(eff.keys()), {"stability"})
        self.assertNotIn("similarity_boost", eff)
        self.assertNotIn("use_speaker_boost", eff)


class TestRenderFailsClosed(ConsistencyTestCase):
    def test_render_fails_closed_when_resolve_fails(self):
        """If the resolver cannot confirm a config, the render must FAIL CLOSED —
        no job queued, no silent legacy fallback."""
        from studio import elevenlabs_client as el
        el.resolve_config = lambda *a, **k: {"ok": False, "unsupported_language": True,
                                             "error": "no model supports language 'zz'"}
        from studio import db
        before = len(db.list_jobs())
        r = self.render_service.create_full_jobs(
            "av_test_001", VOICE_B, "Đoản văn.", "full",
            tts_provider=self.render_service.ELEVENLABS,
            tts_config=None, target_language="zz")
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("fail_closed"))
        self.assertEqual(len(db.list_jobs()), before, "no job must be queued on fail-closed")

    def test_render_fails_closed_on_resolver_exception(self):
        from studio import elevenlabs_client as el
        def boom(*a, **k):
            raise RuntimeError("models API down")
        el.resolve_config = boom
        from studio import db
        before = len(db.list_jobs())
        r = self.render_service.create_full_jobs(
            "av_test_001", VOICE_B, "Đoản văn.", "full",
            tts_provider=self.render_service.ELEVENLABS,
            tts_config=None, target_language="vi")
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("fail_closed"))
        self.assertEqual(len(db.list_jobs()), before)


class TestPreviewRenderParity(ConsistencyTestCase):
    def test_preview_and_render_use_same_model_for_thanh_vi(self):
        """Preview resolver and render (post-fix) must both yield eleven_v3 for
        Thanh+vi, with the same config hash."""
        r_preview = self.el.resolve_config(VOICE_B, target_language="vi")
        self.assertTrue(r_preview["ok"])
        self.assertEqual(r_preview["config"]["model_id"], "eleven_v3")

        r_render = self.render_service.create_full_jobs(
            "av_test_001", VOICE_B, "Đoản văn.", "full",
            tts_provider=self.render_service.ELEVENLABS,
            tts_config=None, target_language="vi")
        self.assertTrue(r_render["ok"])
        job = __import__("studio.db", fromlist=["db"]).get_job(r_render["job_ids"][0])
        cfg = json.loads(job["tts_config"])
        self.assertEqual(cfg["model_id"], r_preview["config"]["model_id"])
        self.assertEqual(cfg.get("language_code"), r_preview["config"].get("language_code"))
        self.assertEqual(job["tts_config_hash"], r_preview["config"]["tts_config_hash"])

    def test_thanh_vi_remains_eleven_v3(self):
        r = self.el.resolve_config(VOICE_B, target_language="vi")
        self.assertEqual(r["config"]["model_id"], "eleven_v3")
        self.assertEqual(r["config"]["resolver_source"], "HUMAN_BENCHMARK_APPROVED")

    def test_explicit_config_is_trusted_not_reresolved(self):
        """When the caller supplies a resolved tts_config, it is snapshotted
        as-is (immutable) and NOT re-resolved."""
        from studio import elevenlabs_client as el
        calls = {"n": 0}
        orig = el.resolve_config
        def counting(*a, **k):
            calls["n"] += 1
            return orig(*a, **k)
        el.resolve_config = counting
        try:
            cfg = self._job_cfg(VOICE_B, "eleven_v3", {"stability": 0.5}, "vi")
            r = self.render_service.create_full_jobs(
                "av_test_001", VOICE_B, "Đoản văn.", "full",
                tts_provider=self.render_service.ELEVENLABS,
                tts_config=cfg, target_language="vi")
            self.assertTrue(r["ok"])
            job = __import__("studio.db", fromlist=["db"]).get_job(r["job_ids"][0])
            self.assertEqual(json.loads(job["tts_config"])["model_id"], "eleven_v3")
            self.assertEqual(calls["n"], 0, "explicit config must not trigger re-resolve")
        finally:
            el.resolve_config = orig

    def test_edge_provider_unaffected_by_resolve_guard(self):
        """Edge TTS test path must not be routed through the ElevenLabs resolve guard."""
        from studio import elevenlabs_client as el, edge_tts_client as edge
        calls = {"n": 0}
        orig = el.resolve_config
        el.resolve_config = lambda *a, **k: calls.__setitem__("n", calls["n"] + 1) or {"ok": False}
        edge_avail = edge.is_available
        edge.is_available = lambda: True
        try:
            r = self.render_service.create_test_job(
                "av_test_001", "vi-VN-HoaiMyNeural", "Đoản văn.", test_mode=True,
                tts_provider=self.render_service.EDGE_TTS_TEST,
                tts_config=None, target_language="vi")
            # Edge job is queued; the ElevenLabs resolver MUST NOT have been called.
            self.assertTrue(r["ok"])
            self.assertEqual(calls["n"], 0, "Edge path must not trigger ElevenLabs resolve guard")
            job = __import__("studio.db", fromlist=["db"]).get_job(r["job_id"])
            self.assertEqual(job["tts_provider"], "EDGE_TTS_TEST")
        finally:
            el.resolve_config = orig
            edge.is_available = edge_avail


if __name__ == "__main__":
    unittest.main()