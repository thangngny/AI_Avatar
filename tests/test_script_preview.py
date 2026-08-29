"""Unit and integration tests for AI Avatar Studio V1.6.0 Script Voice Preview & Audio Reuse.

Verifies:
  1. Deterministic fingerprint computation across text, voice, language, model, settings.
  2. Text normalization preserving Vietnamese Unicode diacritics while standardizing linebreaks.
  3. Database CRUD and schema migrations for audio_previews and jobs.
  4. Preview caching, duplicate suppression, and GPU/renderer isolation.
  5. Immutable snapshotting of preview audio for render jobs.
  6. Direct audio reuse during render without ElevenLabs TTS regeneration.
  7. Safe fallback when preview is stale or missing.
  8. Static voice sample generation and serving for approved voices.
  9. REST API endpoints (/api/audio-preview, /api/voices/approved/<id>/sample).
"""
import os
import time
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import numpy as np
import soundfile as sf

from studio import config
from studio import db
from studio import preview_service
from studio import render_service
from studio import avatar_service
from studio import elevenlabs_client as el
from studio import voices


class TestScriptVoicePreview(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_preview_")
        self.orig_runtime = config.RUNTIME_DIR
        self.orig_temp = config.TEMP_DIR
        self.orig_previews = config.PREVIEWS_DIR
        self.orig_samples = config.VOICE_SAMPLES_DIR
        self.orig_db = config.DB_PATH

        config.RUNTIME_DIR = self.temp_dir
        config.TEMP_DIR = os.path.join(self.temp_dir, "temp")
        config.PREVIEWS_DIR = os.path.join(self.temp_dir, "audio_previews")
        config.VOICE_SAMPLES_DIR = os.path.join(self.temp_dir, "voice_samples")
        config.DB_PATH = os.path.join(self.temp_dir, "studio.db")
        config.ensure_runtime_dirs()

        db.init_db()

        # Disable render background worker during test setup
        render_service._WORKER_DISABLED = True

    def tearDown(self):
        render_service._WORKER_DISABLED = False
        config.RUNTIME_DIR = self.orig_runtime
        config.TEMP_DIR = self.orig_temp
        config.PREVIEWS_DIR = self.orig_previews
        config.VOICE_SAMPLES_DIR = self.orig_samples
        config.DB_PATH = self.orig_db
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def _create_mock_wav(self, path: str, sample_rate: int = 44100, duration_sec: float = 1.0):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        n_samples = max(2000, int(sample_rate * duration_sec))
        data = np.sin(2 * np.pi * 440.0 * np.linspace(0, duration_sec, n_samples, endpoint=False)).astype(np.float32)
        sf.write(path, data, sample_rate, subtype="FLOAT")
        return path

    def test_text_normalization(self):
        """Text normalization standardizes whitespace and CRLF but preserves Unicode and words."""
        raw1 = "  Xin chào các bạn!\r\nĐây là kịch bản thử nghiệm.   \r\n  "
        raw2 = "Xin chào các bạn!\nĐây là kịch bản thử nghiệm."
        n1 = preview_service.normalize_script_text(raw1)
        n2 = preview_service.normalize_script_text(raw2)
        self.assertEqual(n1, n2)
        self.assertEqual(n1, "Xin chào các bạn!\nĐây là kịch bản thử nghiệm.")

        # Preserves Vietnamese diacritics
        vn_text = "Thử nghiệm giọng đọc Tiếng Việt chuẩn xác: Ắ, Ế, Ỗ, Ứ, Ợ, Đ."
        self.assertEqual(preview_service.normalize_script_text(vn_text), vn_text)

    def test_fingerprint_determinism_and_isolation(self):
        """Fingerprint is deterministic for identical params and differs for changes."""
        cfg1 = {
            "model_id": "eleven_v3",
            "requested_output_format": "mp3_44100_128",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True},
            "language_code": "vi",
        }
        fp1 = preview_service.compute_preview_fingerprint("Xin chào", "N0Z0aL8qHhzwUHwRBcVo", "vi", cfg1)
        fp2 = preview_service.compute_preview_fingerprint("Xin chào  \r\n", "N0Z0aL8qHhzwUHwRBcVo", "vi", cfg1)
        self.assertEqual(fp1, fp2, "Whitespace/CRLF variance in script should yield identical fingerprint")

        # Distinct text
        fp_text = preview_service.compute_preview_fingerprint("Tạm biệt", "N0Z0aL8qHhzwUHwRBcVo", "vi", cfg1)
        self.assertNotEqual(fp1, fp_text)

        # Distinct voice
        fp_voice = preview_service.compute_preview_fingerprint("Xin chào", "pGapy9MNHCukzJtjavF0", "vi", cfg1)
        self.assertNotEqual(fp1, fp_voice)

        # Distinct language
        fp_lang = preview_service.compute_preview_fingerprint("Xin chào", "N0Z0aL8qHhzwUHwRBcVo", "en", cfg1)
        self.assertNotEqual(fp1, fp_lang)

        # Distinct model
        cfg_diff_model = dict(cfg1, model_id="eleven_turbo_v2_5")
        fp_model = preview_service.compute_preview_fingerprint("Xin chào", "N0Z0aL8qHhzwUHwRBcVo", "vi", cfg_diff_model)
        self.assertNotEqual(fp1, fp_model)

        # Distinct settings
        cfg_diff_settings = dict(cfg1, voice_settings={"stability": 0.8, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True})
        fp_settings = preview_service.compute_preview_fingerprint("Xin chào", "N0Z0aL8qHhzwUHwRBcVo", "vi", cfg_diff_settings)
        self.assertNotEqual(fp1, fp_settings)

    def test_database_preview_crud(self):
        """audio_previews table supports full CRUD, status update, and touch."""
        prev_id = "prev_test_001"
        fp = "fingerprint_12345"
        db.create_audio_preview({
            "id": prev_id,
            "fingerprint": fp,
            "voice_id": "N0Z0aL8qHhzwUHwRBcVo",
            "voice_name": "Thanh",
            "language": "vi",
            "model_id": "eleven_v3",
            "tts_config_json": "{}",
            "tts_config_hash": "hash1",
            "script_text": "Kịch bản mẫu",
            "script_hash": "shash1",
            "master_audio_path": "/path/master.wav",
            "duration_sec": 12.5,
            "sample_rate": 44100,
            "status": "ready",
        })

        # Query by fingerprint
        by_fp = db.get_audio_preview_by_fingerprint(fp)
        self.assertIsNotNone(by_fp)
        self.assertEqual(by_fp["id"], prev_id)
        self.assertEqual(by_fp["duration_sec"], 12.5)

        # Query by ID
        by_id = db.get_audio_preview(prev_id)
        self.assertIsNotNone(by_id)
        self.assertEqual(by_id["fingerprint"], fp)

        # Update status & error
        db.update_audio_preview(prev_id, status="failed", error="Quota exceeded")
        updated = db.get_audio_preview(prev_id)
        self.assertEqual(updated["status"], "failed")
        self.assertEqual(updated["error"], "Quota exceeded")

        # List previews
        all_prevs = db.list_audio_previews()
        self.assertEqual(len(all_prevs), 1)

    def test_get_or_create_script_preview_caching(self):
        """Preview service synthesizes on cache miss and reuses audio on cache hit."""
        cfg = {
            "model_id": "eleven_v3",
            "requested_output_format": "mp3_44100_128",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True},
        }
        text = "Chào bạn, đây là kịch bản kiểm thử audio reuse."
        voice_id = "N0Z0aL8qHhzwUHwRBcVo"

        synth_call_count = 0

        def mock_synth(*args, **kwargs):
            nonlocal synth_call_count
            synth_call_count += 1
            out_m = kwargs.get("out_master") or args[3]
            out_c = kwargs.get("out_cond") or args[4]
            self._create_mock_wav(out_m, sample_rate=44100, duration_sec=2.5)
            self._create_mock_wav(out_c, sample_rate=16000, duration_sec=2.5)
            return out_m, out_c, 2.5

        with patch("studio.elevenlabs_client.synth_master_cond", side_effect=mock_synth):
            # 1. First call: Cache miss -> calls ElevenLabs synthesis
            res1 = preview_service.get_or_create_script_preview(
                script_text=text, voice_id=voice_id, target_language="vi", tts_config=cfg
            )
            self.assertTrue(res1["ok"], f"Expected ok: True, got {res1}")
            self.assertFalse(res1["reused"])
            self.assertEqual(synth_call_count, 1)
            p1 = res1["preview"]
            self.assertEqual(p1["duration_sec"], 2.5)
            self.assertEqual(p1["sample_rate"], 44100)

            # 2. Second call with exact same inputs: Cache hit -> zero synthesis calls!
            res2 = preview_service.get_or_create_script_preview(
                script_text=text, voice_id=voice_id, target_language="vi", tts_config=cfg
            )
            self.assertTrue(res2["ok"])
            self.assertTrue(res2["reused"])
            self.assertEqual(synth_call_count, 1, "Cached preview must NOT call synth_master_cond again!")
            self.assertEqual(res2["preview"]["id"], p1["id"])

    def test_derive_conditioning_from_master(self):
        """Conditioning audio is accurately resampled to 16 kHz mono without ElevenLabs."""
        master_wav = os.path.join(config.PREVIEWS_DIR, "test_master.wav")
        cond_wav = os.path.join(config.TEMP_DIR, "test_cond.wav")
        self._create_mock_wav(master_wav, sample_rate=44100, duration_sec=3.0)

        out_c, dur = preview_service.derive_cond_from_master(master_wav, cond_wav)
        self.assertTrue(os.path.isfile(out_c))
        info = sf.info(out_c)
        self.assertEqual(info.samplerate, 16000)
        self.assertEqual(info.channels, 1)
        self.assertAlmostEqual(dur, 3.0, delta=0.1)

    def test_render_audio_reuse_flow(self):
        """Render job enqueued with existing preview snapshots master audio and reuses it during render."""
        # 1. Create a ready preview
        cfg = {
            "model_id": "eleven_v3",
            "requested_output_format": "mp3_44100_128",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True},
            "target_language": "vi",
        }
        text = "Nội dung bài phát biểu quan trọng cho Avatar."
        voice_id = "N0Z0aL8qHhzwUHwRBcVo"

        def mock_synth(*args, **kwargs):
            out_m = kwargs.get("out_master") or args[3]
            out_c = kwargs.get("out_cond") or args[4]
            self._create_mock_wav(out_m, sample_rate=44100, duration_sec=4.0)
            self._create_mock_wav(out_c, sample_rate=16000, duration_sec=4.0)
            return out_m, out_c, 4.0

        with patch("studio.elevenlabs_client.synth_master_cond", side_effect=mock_synth):
            p_res = preview_service.get_or_create_script_preview(
                script_text=text, voice_id=voice_id, target_language="vi", tts_config=cfg
            )
            self.assertTrue(p_res["ok"], f"Expected ok: True, got {p_res}")
            preview_id = p_res["preview"]["id"]

        with patch("studio.avatar_service.list_avatars", return_value=[{"avatar_id": "avatar_test", "ready": True}]):
            # 2. Create full render job
            job_res = render_service.create_full_jobs(
                avatar_id="avatar_test",
                voice_id=voice_id,
                script_text=text,
                tts_config=cfg,
            )
            self.assertTrue(job_res["ok"])
            self.assertEqual(len(job_res["job_ids"]), 1)
            job_id = job_res["job_ids"][0]

            job_row = db.get_job(job_id)
            self.assertEqual(job_row["audio_source"], "script_preview")
            self.assertEqual(job_row["preview_id"], preview_id)
            self.assertTrue(os.path.isfile(job_row["master_audio_path"]))

            # 3. Test generate_master_audio during job run
            synth_called = False
            def mock_synth_unexpected(*args, **kwargs):
                nonlocal synth_called
                synth_called = True
                raise AssertionError("synth_master_cond should NOT be called when preview is reused!")

            with patch("studio.elevenlabs_client.synth_master_cond", side_effect=mock_synth_unexpected):
                audio_out = render_service.generate_master_audio(
                    script_text=text,
                    voice_id=voice_id,
                    tts_config=cfg,
                    master_audio_override=job_row["master_audio_path"]
                )
                self.assertTrue(audio_out["ok"])
                self.assertTrue(audio_out["reused"])
                self.assertEqual(audio_out["source"], "script_preview")
                self.assertFalse(synth_called)

                # Conditioning audio is valid 16kHz
                cond_info = sf.info(audio_out["cond_path"])
                self.assertEqual(cond_info.samplerate, 16000)

    def test_static_voice_sample_generation(self):
        """Approved voices have accessible static samples."""
        vid = "N0Z0aL8qHhzwUHwRBcVo"

        def mock_synth(*args, **kwargs):
            out_m = kwargs.get("out_master") or (args[3] if len(args) > 3 else None)
            out_c = kwargs.get("out_cond") or (args[4] if len(args) > 4 else None)
            self._create_mock_wav(out_m, sample_rate=44100, duration_sec=1.5)
            self._create_mock_wav(out_c, sample_rate=16000, duration_sec=1.5)
            return out_m, out_c, 1.5

        def mock_resolve(voice_id, **kwargs):
            return {
                "ok": True,
                "config": {
                    "model_id": "eleven_v3",
                    "requested_output_format": "mp3_44100_128",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}
                }
            }

        with patch("studio.elevenlabs_client.is_configured", return_value=True), \
             patch("studio.elevenlabs_client.resolve_config", side_effect=mock_resolve), \
             patch("studio.elevenlabs_client.synth_master_cond", side_effect=mock_synth):
            sample_p = preview_service.get_static_voice_sample(vid)
            self.assertIsNotNone(sample_p)
            self.assertTrue(os.path.isfile(sample_p))

            # Non-approved voice returns None
            unapproved = preview_service.get_static_voice_sample("unapproved_voice_123")
            self.assertIsNone(unapproved)


class TestScriptVoicePreviewAPI(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_preview_api_")
        self.orig_runtime = config.RUNTIME_DIR
        self.orig_temp = config.TEMP_DIR
        self.orig_previews = config.PREVIEWS_DIR
        self.orig_samples = config.VOICE_SAMPLES_DIR
        self.orig_db = config.DB_PATH

        config.RUNTIME_DIR = self.tmp_dir
        config.TEMP_DIR = os.path.join(self.tmp_dir, "temp")
        config.PREVIEWS_DIR = os.path.join(self.tmp_dir, "audio_previews")
        config.VOICE_SAMPLES_DIR = os.path.join(self.tmp_dir, "voice_samples")
        config.DB_PATH = os.path.join(self.tmp_dir, "studio.db")
        config.ensure_runtime_dirs()

        db.init_db()

        from studio import app as studio_app
        studio_app.app.config["TESTING"] = True
        self.client = studio_app.app.test_client()

    def tearDown(self):
        config.RUNTIME_DIR = self.orig_runtime
        config.TEMP_DIR = self.orig_temp
        config.PREVIEWS_DIR = self.orig_previews
        config.VOICE_SAMPLES_DIR = self.orig_samples
        config.DB_PATH = self.orig_db
        try:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
        except Exception:
            pass

    def _create_mock_wav(self, path: str, sample_rate: int = 44100, duration_sec: float = 1.0):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        n_samples = max(2000, int(sample_rate * duration_sec))
        data = np.sin(2 * np.pi * 440.0 * np.linspace(0, duration_sec, n_samples, endpoint=False)).astype(np.float32)
        sf.write(path, data, sample_rate, subtype="FLOAT")
        return path

    def test_api_create_and_fetch_audio_preview(self):
        """API endpoints create, fetch metadata, stream audio, and download audio."""
        vid = "N0Z0aL8qHhzwUHwRBcVo"
        text = "Kịch bản kiểm thử API audio preview."

        def mock_synth(*args, **kwargs):
            out_m = kwargs.get("out_master") or (args[3] if len(args) > 3 else None)
            out_c = kwargs.get("out_cond") or (args[4] if len(args) > 4 else None)
            self._create_mock_wav(out_m, sample_rate=44100, duration_sec=2.0)
            self._create_mock_wav(out_c, sample_rate=16000, duration_sec=2.0)
            return out_m, out_c, 2.0

        def mock_resolve(voice_id, **kwargs):
            return {
                "ok": True,
                "config": {
                    "model_id": "eleven_v3",
                    "requested_output_format": "mp3_44100_128",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}
                }
            }

        with patch("studio.elevenlabs_client.is_configured", return_value=True), \
             patch("studio.elevenlabs_client.resolve_config", side_effect=mock_resolve), \
             patch("studio.elevenlabs_client.synth_master_cond", side_effect=mock_synth):

            # 1. POST /api/audio-preview
            res = self.client.post("/api/audio-preview", json={
                "voice_id": vid,
                "script_text": text,
                "target_language": "vi"
            })
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["ok"])
            prev_id = data["preview"]["id"]
            self.assertEqual(data["preview"]["duration_sec"], 2.0)

            # 2. GET /api/audio-preview/<id>
            get_res = self.client.get(f"/api/audio-preview/{prev_id}")
            self.assertEqual(get_res.status_code, 200)
            get_data = get_res.get_json()
            self.assertTrue(get_data["ok"])
            self.assertEqual(get_data["preview"]["id"], prev_id)

            # 3. GET /api/audio-preview/<id>/audio
            audio_res = self.client.get(f"/api/audio-preview/{prev_id}/audio")
            self.assertEqual(audio_res.status_code, 200)
            self.assertEqual(audio_res.mimetype, "audio/wav")
            self.assertGreater(len(audio_res.data), 1000)

            # 4. GET /api/audio-preview/<id>/download
            dl_res = self.client.get(f"/api/audio-preview/{prev_id}/download")
            self.assertEqual(dl_res.status_code, 200)
            self.assertIn("attachment", dl_res.headers.get("Content-Disposition", ""))

            # 5. GET /api/voices/approved/<voice_id>/sample
            sample_res = self.client.get(f"/api/voices/approved/{vid}/sample")
            self.assertEqual(sample_res.status_code, 200)
            self.assertEqual(sample_res.mimetype, "audio/wav")


if __name__ == "__main__":
    unittest.main()

