#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio V1.6.0 — language-aware ElevenLabs resolver acceptance tests.

Covers the Phase B spec test list. Stubs the live ElevenLabs metadata GETs
(get_models / get_voice_settings / get_voice_history / get_history_item /
get_voice_metadata) so NO network, NO quota. Real TTS synthesis tests are gated
behind STUDIO_RUN_NETWORK_TESTS=1.

Run from the repo root with the torch env python:
    python -m unittest tests.test_language_resolver -v
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

THANH = "N0Z0aL8qHhzwUHwRBcVo"

# A realistic /v1/models-shaped list (only the fields the resolver uses).
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
    {"model_id": "eleven_turbo_v2", "name": "Eleven Turbo v2", "can_do_text_to_speech": True,
     "languages": ["en"], "can_use_style": False, "can_use_speaker_boost": False,
     "maximum_text_length_per_request": 30000, "deprecated": True},
]

THANH_SETTINGS = {"stability": 0.5, "similarity_boost": 1.0, "style": 0.0,
                  "use_speaker_boost": True, "speed": 1.06}


def _meta(vid, verified=None, hq=None, lang="vi"):
    verified = verified if verified is not None else [
        {"language": "vi", "model_id": "eleven_turbo_v2_5", "accent": "southern"},
        {"language": "vi", "model_id": "eleven_flash_v2_5", "accent": "southern"},
    ]
    return {"ok": True, "metadata": {
        "voice_id": vid, "name": "Thanh", "labels": {"language": lang},
        "verified_languages": verified, "high_quality_base_model_ids": hq or [],
        "fine_tuning_language": lang, "fine_tuning_state": {}, "description": "",
    }}


class LangTestCase(unittest.TestCase):
    def setUp(self):
        from studio import config
        self._orig_db = config.DB_PATH
        self.tmp = tempfile.mkdtemp(prefix="lang_test_")
        config.DB_PATH = os.path.join(self.tmp, "test.db")
        config.ensure_runtime_dirs()
        from studio import db
        db.init_db()  # seeds the Thanh+vi -> eleven_v3 profile (generic data)
        from studio import elevenlabs_client as el
        self.el = el
        self._orig = {
            "get_models": el.get_models, "get_voice_settings": el.get_voice_settings,
            "get_voice_history": el.get_voice_history, "get_history_item": el.get_history_item,
            "get_voice_metadata": el.get_voice_metadata, "is_configured": el.is_configured,
            "model_id": el.model_id,
        }
        el.is_configured = lambda: True
        el.model_id = lambda: "eleven_turbo_v2_5"
        el._CACHE.clear()
        # Disable the background render worker so job-creation tests can inspect
        # persisted rows without the worker racing to claim them (real TTS/GPU).
        from studio import render_service
        self._orig_disabled = render_service._WORKER_DISABLED
        render_service._WORKER_DISABLED = True

    def tearDown(self):
        from studio import config, elevenlabs_client as el, render_service
        render_service._WORKER_DISABLED = self._orig_disabled
        for k, v in self._orig.items():
            setattr(el, k, v)
        config.DB_PATH = self._orig_db
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _mock_meta(self, vid=THANH, settings=THANH_SETTINGS, history=None,
                   verified=None, hq=None, lang="vi"):
        el = self.el
        el.get_models = lambda refresh=False: {"ok": True, "models": MODELS, "cached": False}
        el.get_voice_settings = lambda v, refresh=False: {"ok": True, "settings": settings}
        el.get_voice_history = lambda v, limit=10, refresh=False: {"ok": True, "items": history or []}
        el.get_history_item = lambda hid: {"ok": True, "item": {
            "history_item_id": hid, "model_id": "eleven_turbo_v2_5",
            "settings": settings, "output_format": "pcm_16000"}}
        el.get_voice_metadata = lambda v, refresh=False: _meta(v, verified=verified, hq=hq, lang=lang)


class TestLanguageIdentity(LangTestCase):
    def test_language_in_config_identity(self):
        self._mock_meta()
        r = self.el.resolve_config(THANH, target_language="vi")
        self.assertTrue(r["ok"])
        c = r["config"]
        self.assertEqual(c["target_language"], "vi")
        self.assertIn("compatibility", c)
        self.assertEqual(c["compatibility"]["language_supported"], True)

    def test_config_hash_includes_language(self):
        self._mock_meta()
        r_vi = self.el.resolve_config(THANH, target_language="vi")
        self._mock_meta(lang="en", verified=[])
        # same voice, English target -> different model/policy, different hash
        r_en = self.el.resolve_config(THANH, target_language="en")
        self.assertTrue(r_vi["ok"] and r_en["ok"])
        self.assertNotEqual(r_vi["config"]["tts_config_hash"],
                            r_en["config"]["tts_config_hash"])


class TestHumanProfile(LangTestCase):
    def test_v3_profile_for_thanh_vi(self):
        self._mock_meta()
        r = self.el.resolve_config(THANH, target_language="vi")
        self.assertTrue(r["ok"])
        c = r["config"]
        self.assertEqual(c["model_id"], "eleven_v3")
        self.assertEqual(c["match_strength"], "human_approved_profile")
        self.assertEqual(c["resolver_source"], "HUMAN_BENCHMARK_APPROVED")
        self.assertEqual(c["language_code"], "vi")

    def test_human_profile_not_applied_to_other_voice(self):
        self._mock_meta()
        # A different voice with vi -> must NOT inherit Thanh's v3 profile.
        r = self.el.resolve_config("OTHERVOICE", target_language="vi")
        self.assertTrue(r["ok"])
        self.assertNotEqual(r["config"]["model_id"], "eleven_v3")
        self.assertNotEqual(r["config"].get("resolver_source"), "HUMAN_BENCHMARK_APPROVED")

    def test_human_profile_not_applied_to_other_language(self):
        self._mock_meta(lang="en", verified=[])
        # Thanh + English -> profile is vi-only, must not apply; resolve independently.
        r = self.el.resolve_config(THANH, target_language="en")
        self.assertTrue(r["ok"])
        self.assertNotEqual(r["config"].get("resolver_source"), "HUMAN_BENCHMARK_APPROVED")

    def test_model_compatibility_checked_before_profile_use(self):
        # Profile says v3, but v3 no longer supports vi in the live models list ->
        # the profile is skipped (not blindly used), falling through to policy.
        el = self.el
        el.get_models = lambda refresh=False: {"ok": True, "models": [
            {**m, "languages": ([l for l in m["languages"] if l != "vi"]
                                if m["model_id"] == "eleven_v3" else m["languages"])}
            for m in MODELS], "cached": False}
        el.get_voice_settings = lambda v, refresh=False: {"ok": True, "settings": THANH_SETTINGS}
        el.get_voice_history = lambda v, limit=10, refresh=False: {"ok": True, "items": []}
        el.get_voice_metadata = lambda v, refresh=False: _meta(v)
        r = self.el.resolve_config(THANH, target_language="vi")
        self.assertTrue(r["ok"])
        self.assertNotEqual(r["config"]["model_id"], "eleven_v3",
                            "an invalidated profile model must not be used")

    def test_removed_or_unavailable_model_invalidates_profile(self):
        # Profile model v3 is gone from /v1/models entirely -> skip profile.
        el = self.el
        el.get_models = lambda refresh=False: {"ok": True, "models": [
            m for m in MODELS if m["model_id"] != "eleven_v3"], "cached": False}
        el.get_voice_settings = lambda v, refresh=False: {"ok": True, "settings": THANH_SETTINGS}
        el.get_voice_history = lambda v, limit=10, refresh=False: {"ok": True, "items": []}
        el.get_voice_metadata = lambda v, refresh=False: _meta(v)
        r = self.el.resolve_config(THANH, target_language="vi")
        self.assertTrue(r["ok"])
        self.assertNotEqual(r["config"]["model_id"], "eleven_v3")


class TestModelAwareSettings(LangTestCase):
    def test_effective_settings_model_aware(self):
        self.assertEqual(self.el.effective_voice_settings("eleven_v3", THANH_SETTINGS),
                         {"stability": 0.5})
        self.assertEqual(self.el.effective_voice_settings("eleven_turbo_v2_5", THANH_SETTINGS),
                         THANH_SETTINGS)
        # multilingual_v2 supports all 5 too.
        self.assertEqual(self.el.effective_voice_settings("eleven_multilingual_v2", THANH_SETTINGS),
                         THANH_SETTINGS)

    def test_unsupported_v3_settings_not_sent(self):
        from unittest import mock as _mock
        cfg = {"model_id": "eleven_v3",
               "effective_voice_settings": {"stability": 0.5},
               "language_code": "vi",
               "requested_output_format": "mp3_44100_128",
               "voice_settings": THANH_SETTINGS}
        captured = {}

        class FakeResp:
            status_code = 200
            content = b"\x00" * 100
            text = ""

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["json"] = json
            return FakeResp()

        with _mock.patch.object(self.el, "is_configured", return_value=True), \
                _mock.patch.object(self.el.requests, "post", side_effect=fake_post):
            self.el._synth_config("V1", "Xin chào.", cfg)
        body = captured["json"]
        self.assertEqual(body["voice_settings"], {"stability": 0.5})
        self.assertNotIn("similarity_boost", body["voice_settings"])
        self.assertNotIn("style", body["voice_settings"])
        self.assertNotIn("use_speaker_boost", body["voice_settings"])
        self.assertNotIn("speed", body["voice_settings"])
        self.assertEqual(body["language_code"], "vi")

    def test_turbo_sends_all_settings(self):
        from unittest import mock as _mock
        cfg = {"model_id": "eleven_turbo_v2_5",
               "effective_voice_settings": THANH_SETTINGS,
               "language_code": "vi",
               "requested_output_format": "mp3_44100_128"}
        captured = {}

        class FakeResp:
            status_code = 200
            content = b"\x00" * 100
            text = ""

        def fake_post(url, headers=None, json=None, timeout=None):
            captured["json"] = json
            return FakeResp()

        with _mock.patch.object(self.el, "is_configured", return_value=True), \
                _mock.patch.object(self.el.requests, "post", side_effect=fake_post):
            self.el._synth_config("V1", "Xin chào.", cfg)
        self.assertEqual(set(captured["json"]["voice_settings"].keys()),
                         set(THANH_SETTINGS.keys()))


class TestLanguageCode(LangTestCase):
    def test_language_code_model_aware(self):
        self.assertEqual(self.el.language_code_for("eleven_v3", "vi"), "vi")
        self.assertEqual(self.el.language_code_for("eleven_turbo_v2_5", "vi"), "vi")
        # multilingual_v2 does NOT support language_code (official doc).
        self.assertIsNone(self.el.language_code_for("eleven_multilingual_v2", "vi"))
        self.assertIsNone(self.el.language_code_for("eleven_v3", None))


class TestOutputFormatSeparation(LangTestCase):
    def test_output_format_separate_from_model(self):
        self._mock_meta()
        r = self.el.resolve_config(THANH, target_language="vi")
        c = r["config"]
        self.assertEqual(c["model_id"], "eleven_v3")
        self.assertEqual(c["requested_output_format"], "mp3_44100_128")
        self.assertEqual(c["master_storage_format"], "wav_44100")
        # changing output format must not change model selection fields.


class TestLanguageGuards(LangTestCase):
    def test_history_cannot_override_language_guard(self):
        # A matching-settings history item whose model is multilingual_v2 (no vi)
        # must NOT be used for target_language=vi; the resolver skips it.
        el = self.el
        el.get_models = lambda refresh=False: {"ok": True, "models": MODELS, "cached": False}
        el.get_voice_settings = lambda v, refresh=False: {"ok": True, "settings": THANH_SETTINGS}
        el.get_voice_history = lambda v, limit=10, refresh=False: {"ok": True, "items": [
            {"history_item_id": "h1", "model_id": "eleven_multilingual_v2",
             "settings": THANH_SETTINGS, "date_unix": 2}]}
        el.get_history_item = lambda hid: {"ok": True, "item": {
            "history_item_id": hid, "model_id": "eleven_multilingual_v2",
            "settings": THANH_SETTINGS, "output_format": "mp3_44100_128"}}
        el.get_voice_metadata = lambda v, refresh=False: _meta(v)
        # No profile for this synthetic voice -> Priority 4 must skip the
        # incompatible multilingual_v2 history item and fall to Priority 5.
        r = self.el.resolve_config("SYNTH", target_language="vi")
        self.assertTrue(r["ok"])
        self.assertNotEqual(r["config"]["model_id"], "eleven_multilingual_v2")

    def test_mode_b_incompatible_history_warns(self):
        # Explicit Mode B selection of an incompatible history item must NOT
        # silently generate -> returns ok=False with incompatible=True.
        el = self.el
        el.get_models = lambda refresh=False: {"ok": True, "models": MODELS, "cached": False}
        el.get_history_item = lambda hid: {"ok": True, "item": {
            "history_item_id": hid, "model_id": "eleven_multilingual_v2",
            "settings": THANH_SETTINGS, "output_format": "mp3_44100_128"}}
        el.get_voice_metadata = lambda v, refresh=False: _meta(v)
        r = self.el.resolve_config("SYNTH", mode="history_match",
                                    history_item_id="h1", target_language="vi")
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("incompatible"))

    def test_no_model_supports_language(self):
        el = self.el
        el.get_models = lambda refresh=False: {"ok": True, "models": [
            {**m, "languages": ["en"]} for m in MODELS], "cached": False}
        el.get_voice_settings = lambda v, refresh=False: {"ok": True, "settings": THANH_SETTINGS}
        el.get_voice_history = lambda v, limit=10, refresh=False: {"ok": True, "items": []}
        el.get_voice_metadata = lambda v, refresh=False: _meta(v, verified=[])
        # A voice with no vi profile and no vi-capable model.
        r = self.el.resolve_config("NOVI", target_language="vi")
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("unsupported_language"))

    def test_deprecated_model_not_auto_preferred(self):
        # Priority 5 must prefer a non-deprecated model over a deprecated one
        # when both support the language. Here only turbo_v2 (deprecated, en-only)
        # vs others -> use a non-deprecated vi model.
        el = self.el
        # Models: only deprecated turbo_v2 supports 'vi' (artificial), plus a
        # non-deprecated flash_v2_5 supporting vi.
        el.get_models = lambda refresh=False: {"ok": True, "models": [
            {"model_id": "eleven_turbo_v2", "can_do_text_to_speech": True, "languages": ["vi"],
             "deprecated": True, "maximum_text_length_per_request": 30000},
            {"model_id": "eleven_flash_v2_5", "can_do_text_to_speech": True, "languages": ["vi"],
             "deprecated": False, "maximum_text_length_per_request": 40000},
        ], "cached": False}
        el.get_voice_settings = lambda v, refresh=False: {"ok": True, "settings": THANH_SETTINGS}
        el.get_voice_history = lambda v, limit=10, refresh=False: {"ok": True, "items": []}
        el.get_voice_metadata = lambda v, refresh=False: _meta(v, verified=[])
        el.model_id = lambda: "eleven_turbo_v2"  # Studio default is the deprecated one
        r = self.el.resolve_config("SYNTH", target_language="vi")
        self.assertTrue(r["ok"])
        self.assertNotEqual(r["config"]["model_id"], "eleven_turbo_v2")


class TestSemanticChunking(unittest.TestCase):
    def test_semantic_chunking_no_missing_text(self):
        from studio import elevenlabs_client as el
        text = ("Câu một. Câu hai. Câu ba.\n\nĐoạn thứ hai. Câu năm. "
                + "X" * 200 + ". Câu cuối.")
        chunks = el.semantic_chunks(text, 50)
        self.assertEqual("".join(chunks), text)

    def test_semantic_chunking_no_duplicate_text(self):
        from studio import elevenlabs_client as el
        text = "Một. Hai. Ba. Bốn. Năm. Sáu. Bảy. Tám. Chín. Mười."
        chunks = el.semantic_chunks(text, 15)
        self.assertEqual("".join(chunks), text)
        # no chunk exceeds the limit except when a single token is longer.
        for c in chunks:
            self.assertLessEqual(len(c), 15 + 1)

    def test_sentence_boundary_preference(self):
        from studio import elevenlabs_client as el
        # 4 short sentences; max_chars large enough to hold 2 -> should break at
        # sentence boundaries, never mid-word.
        text = "Xin chào quý vị. Đây là test. Hôm nay trời đẹp. Tạm biệt."
        chunks = el.semantic_chunks(text, 30)
        self.assertEqual("".join(chunks), text)
        for c in chunks:
            # never starts mid-word: each chunk boundary was a sentence boundary
            self.assertFalse(c.startswith(" "))
        # every chunk except possibly the last ends with sentence punctuation
        for c in chunks[:-1]:
            self.assertTrue(c.rstrip().endswith((" ", ".")))

    def test_paragraph_split(self):
        from studio import elevenlabs_client as el
        text = "Đoạn một câu một. Câu hai.\n\nĐoạn hai câu một. Câu hai."
        chunks = el.semantic_chunks(text, 32)
        # paragraph boundary is preferred over the sentence boundary -> two chunks
        self.assertEqual(len(chunks), 2)
        self.assertEqual("".join(chunks), text)


class TestContextFields(unittest.TestCase):
    def test_context_fields_model_aware_single_chunk_no_context(self):
        from studio import elevenlabs_client as el
        from unittest import mock as _mock
        captured = []

        class FakeResp:
            status_code = 200
            content = b"\x00" * 100
            text = ""

        def fake_post(url, headers=None, json=None, timeout=None):
            captured.append(json)
            return FakeResp()

        cfg = {"model_id": "eleven_v3", "effective_voice_settings": {"stability": 0.5},
               "language_code": "vi", "requested_output_format": "mp3_44100_128"}
        with _mock.patch.object(el, "is_configured", return_value=True), \
                _mock.patch.object(el.requests, "post", side_effect=fake_post):
            # single chunk -> no previous_text/next_text
            el._synth_config("V1", "Xin chào.", cfg)
        self.assertNotIn("previous_text", captured[0])
        self.assertNotIn("next_text", captured[0])

    def test_v3_context_not_sent_even_when_provided(self):
        # v3 rejects previous_text/next_text (live-proven 400). The request
        # builder must NEVER send them for v3, even when context values are
        # supplied (multi-chunk path).
        from studio import elevenlabs_client as el
        from unittest import mock as _mock
        captured = []

        class FakeResp:
            status_code = 200
            content = b"\x00" * 100
            text = ""

        def fake_post(url, headers=None, json=None, timeout=None):
            captured.append(json)
            return FakeResp()

        cfg = {"model_id": "eleven_v3", "effective_voice_settings": {"stability": 0.5},
               "language_code": "vi", "requested_output_format": "mp3_44100_128"}
        with _mock.patch.object(el, "is_configured", return_value=True), \
                _mock.patch.object(el.requests, "post", side_effect=fake_post):
            el._synth_config("V1", "Đoạn hai.", cfg,
                             previous_text="Đoạn một.", next_text="Đoạn ba.")
        self.assertNotIn("previous_text", captured[0])
        self.assertNotIn("next_text", captured[0])
        # turbo v2.5 DOES support context -> context IS sent when provided.
        captured.clear()
        cfg_t = {**cfg, "model_id": "eleven_turbo_v2_5",
                 "effective_voice_settings": THANH_SETTINGS}
        with _mock.patch.object(el, "is_configured", return_value=True), \
                _mock.patch.object(el.requests, "post", side_effect=fake_post):
            el._synth_config("V1", "Đoạn hai.", cfg_t,
                             previous_text="Đoạn một.", next_text="Đoạn ba.")
        self.assertEqual(captured[0].get("previous_text"), "Đoạn một.")
        self.assertEqual(captured[0].get("next_text"), "Đoạn ba.")


class TestCacheIdentity(LangTestCase):
    def test_voice_language_config_save_get(self):
        from studio import db
        cfg = {"voice_id": "V1", "target_language": "vi", "model_id": "eleven_v3"}
        db.save_voice_language_config("V1", "vi", "auto_current", cfg)
        got = db.get_voice_language_config("V1", "vi", "auto_current")
        self.assertIsNotNone(got)
        self.assertEqual(got["model_id"], "eleven_v3")
        # different language -> different config, no leak
        cfg_en = {"voice_id": "V1", "target_language": "en", "model_id": "eleven_turbo_v2_5"}
        db.save_voice_language_config("V1", "en", "auto_current", cfg_en)
        self.assertEqual(db.get_voice_language_config("V1", "vi", "auto_current")["model_id"],
                         "eleven_v3")
        self.assertEqual(db.get_voice_language_config("V1", "en", "auto_current")["model_id"],
                         "eleven_turbo_v2_5")
        self.assertIsNone(db.get_voice_language_config("V1", "ja", "auto_current"))

    def test_profile_crud(self):
        from studio import db
        self.assertTrue(db.get_profile(THANH, "vi"))  # seeded
        db.save_profile("VX", "ja", "eleven_v3", "USER_MANUAL")
        self.assertEqual(db.get_profile("VX", "ja")["preferred_model_id"], "eleven_v3")
        self.assertTrue(db.delete_profile("VX", "ja"))
        self.assertIsNone(db.get_profile("VX", "ja"))


class TestEdgeNoElevenMetadata(unittest.TestCase):
    def test_edge_path_no_elevenlabs_metadata_calls(self):
        # Edge TTS must not trigger ElevenLabs metadata resolution.
        from studio import render_service, elevenlabs_client as el, edge_tts_client as edge
        import numpy as np, soundfile as sf
        from unittest import mock as _mock
        el_calls = {"v": False}

        def _trap(*a, **k):
            el_calls["v"] = True
            raise AssertionError("ElevenLabs metadata must not be called for Edge")

        orig_avail = edge.is_available
        orig_synth = edge.synth_to_wav
        edge.is_available = lambda: True

        def fake_edge(vid, text, out):
            sf.write(out, np.zeros(16000, dtype=np.float32), 16000, subtype="FLOAT")
            return out, 1.0

        orig_settings = el.get_voice_settings
        orig_models = el.get_models
        orig_metadata = el.get_voice_metadata

        edge.synth_to_wav = fake_edge
        el.get_voice_settings = _trap
        el.get_models = _trap
        el.get_voice_metadata = _trap
        try:
            r = render_service.generate_master_audio(
                "Xin chào. Test.", "vi-VN-HoaiMyNeural",
                tts_provider=render_service.EDGE_TTS_TEST,
                tts_config={"model_id": "eleven_v3"})
        finally:
            edge.is_available = orig_avail
            edge.synth_to_wav = orig_synth
            el.get_voice_settings = orig_settings
            el.get_models = orig_models
            el.get_voice_metadata = orig_metadata
        self.assertTrue(r["ok"])
        self.assertFalse(el_calls["v"])


class TestJobSnapshotImmutable(LangTestCase):
    def test_job_snapshot_survives_language_change(self):
        from studio import db, render_service, avatar_service
        ready = [a for a in avatar_service.list_avatars() if a["ready"]]
        if not ready:
            self.skipTest("no prepared avatar on disk")
        av = ready[0]["avatar_id"]
        cfg_vi = {"voice_id": THANH, "target_language": "vi", "model_id": "eleven_v3",
                  "effective_voice_settings": {"stability": 0.5}, "language_code": "vi",
                  "requested_output_format": "mp3_44100_128",
                  "resolver_policy": "auto_current", "sync_mode": "auto_current"}
        cfg_en = {**cfg_vi, "target_language": "en", "model_id": "eleven_turbo_v2_5",
                  "language_code": "en"}
        rA = render_service.create_full_jobs(av, THANH, "Xin chào.", "full",
                                             tts_provider=render_service.ELEVENLABS,
                                             tts_config=cfg_vi, sync_mode="auto_current")
        self.assertTrue(rA["ok"])
        jA = db.get_job(rA["job_ids"][0])
        hA = jA["tts_config_hash"]
        # later switch to English config
        rB = render_service.create_full_jobs(av, THANH, "Hello.", "full",
                                             tts_provider=render_service.ELEVENLABS,
                                             tts_config=cfg_en, sync_mode="auto_current")
        jB = db.get_job(rB["job_ids"][0])
        self.assertNotEqual(hA, jB["tts_config_hash"])
        # original vi job unchanged
        self.assertEqual(db.get_job(rA["job_ids"][0])["tts_config_hash"], hA)


# --------------------------------------------------------------------------- #
# DOM / contract tests (Playwright-intent: DOM/accessibility assertions, no   #
# image vision). Playwright browsers are not installed in this env, so these   #
# run against the Flask test client + the SPA source — the same invariants   #
# the browser would assert, without a real browser.                           #
# --------------------------------------------------------------------------- #
class TestLanguageUI(LangTestCase):
    def setUp(self):
        super().setUp()
        self._mock_meta()
        from studio.app import app
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_spa_wires_language_selector(self):
        # The SPA source must wire the language selector (no-vision source check).
        from studio import config
        with open(os.path.join(config.STUDIO_DIR, "static", "app.js"), "r",
                  encoding="utf-8") as f:
            src = f.read()
        self.assertIn("#qLang", src)
        self.assertIn("effectiveTargetLanguage", src)
        self.assertIn("target_language", src)
        # the language selector must re-resolve on change (no leak across langs)
        self.assertIn("state.voiceConfig = null", src)

    def test_resolve_route_applies_thanh_vi_profile(self):
        r = self.client.post("/api/elevenlabs/voice-config/resolve",
                             json={"voice_id": THANH, "mode": "auto_current",
                                   "target_language": "vi"})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["config"]["model_id"], "eleven_v3")
        self.assertEqual(d["config"]["language_code"], "vi")
        self.assertEqual(d["config"]["match_strength"], "human_approved_profile")

    def test_resolve_route_other_voice_vi_not_v3(self):
        r = self.client.post("/api/elevenlabs/voice-config/resolve",
                             json={"voice_id": "OTHERVOICE", "mode": "auto_current",
                                   "target_language": "vi"})
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertNotEqual(d["config"]["model_id"], "eleven_v3")

    def test_resolve_route_thanh_en_not_profile(self):
        # Thanh + English must NOT reuse the vi profile.
        self._mock_meta(lang="en", verified=[])
        r = self.client.post("/api/elevenlabs/voice-config/resolve",
                             json={"voice_id": THANH, "mode": "auto_current",
                                   "target_language": "en"})
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertNotEqual(d["config"].get("resolver_source"), "HUMAN_BENCHMARK_APPROVED")

    def test_language_detect_vietnamese(self):
        r = self.client.post("/api/language/detect",
                             json={"text": "Hôm nay chúng ta sẽ cùng xem lại dự án mới."})
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["language"], "vi")
        self.assertGreater(d["confidence"], 0.6)

    def test_profiles_route_lists_seeded_thanh(self):
        r = self.client.get("/api/elevenlabs/profiles")
        d = r.get_json()
        self.assertTrue(d["ok"])
        ids = [p["voice_id"] for p in d["profiles"]]
        self.assertIn(THANH, ids)
        thanh = [p for p in d["profiles"] if p["voice_id"] == THANH][0]
        self.assertEqual(thanh["preferred_model_id"], "eleven_v3")
        self.assertEqual(thanh["language_code"], "vi")
        self.assertEqual(thanh["selection_source"], "HUMAN_BENCHMARK_APPROVED")
        # No API key in the response.
        from studio import envutil
        envutil.load_env(force=True)
        key = envutil.env_str("ELEVENLABS_API_KEY", "")
        if key:
            self.assertNotIn(key, json.dumps(d))

    def test_resolve_route_no_key_leak(self):
        r = self.client.post("/api/elevenlabs/voice-config/resolve",
                             json={"voice_id": THANH, "target_language": "vi"})
        from studio import envutil
        envutil.load_env(force=True)
        key = envutil.env_str("ELEVENLABS_API_KEY", "")
        body = r.get_data(as_text=True)
        if key:
            self.assertNotIn(key, body)


if __name__ == "__main__":
    unittest.main(verbosity=2)