import os
import sys
import time
import json
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from studio import config, db, app as studio_app, avatar_service, render_service


class TestManagementSafetyCore(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_mgmt_safety_")
        self.orig_db_path = config.DB_PATH
        self.test_db_path = os.path.join(self.tmp_dir, "test_studio.db")
        config.DB_PATH = self.test_db_path
        config.ensure_runtime_dirs()
        db.init_db()

        self.orig_avatars_root = config.AVATARS_ROOT
        self.test_avatars_root = os.path.join(self.tmp_dir, "avatars")
        os.makedirs(self.test_avatars_root, exist_ok=True)
        config.AVATARS_ROOT = self.test_avatars_root

        self.orig_raw_root = config.RAW_SOURCES_ROOT
        self.test_raw_root = os.path.join(self.tmp_dir, "avatar_sources")
        os.makedirs(self.test_raw_root, exist_ok=True)
        config.RAW_SOURCES_ROOT = self.test_raw_root

        self.orig_renders_dir = config.RENDERS_DIR
        self.test_renders_dir = os.path.join(self.tmp_dir, "renders")
        os.makedirs(self.test_renders_dir, exist_ok=True)
        config.RENDERS_DIR = self.test_renders_dir

        self.orig_worker_disabled = render_service._WORKER_DISABLED
        render_service._WORKER_DISABLED = True

        studio_app.app.config["TESTING"] = True
        self.client = studio_app.app.test_client()

    def tearDown(self):
        render_service._WORKER_DISABLED = self.orig_worker_disabled
        config.DB_PATH = self.orig_db_path
        config.AVATARS_ROOT = self.orig_avatars_root
        config.RAW_SOURCES_ROOT = self.orig_raw_root
        config.RENDERS_DIR = self.orig_renders_dir
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_mock_avatar(self, avatar_id, name=None, ready=True):
        d = os.path.join(self.test_avatars_root, avatar_id)
        os.makedirs(os.path.join(d, "full_imgs"), exist_ok=True)
        with open(os.path.join(d, "full_imgs", "00000.png"), "wb") as f:
            f.write(b"PNG")
        if ready:
            os.makedirs(os.path.join(d, "mask"), exist_ok=True)
            with open(os.path.join(d, "mask", "00000.png"), "wb") as f:
                f.write(b"PNG")
            for f_name in ("coords.pkl", "latents.pt", "mask_coords.pkl"):
                with open(os.path.join(d, f_name), "wb") as f:
                    f.write(b"DATA")
            with open(os.path.join(d, "avator_info.json"), "w", encoding="utf-8") as f:
                json.dump({"version": "v15", "video_path": os.path.join(self.test_raw_root, "source.mp4")}, f)

        db.upsert_avatar(avatar_id, name=name or avatar_id, ready=1 if ready else 0)
        return d

    # ----------------------------------------------------------------------- #
    # 1. Database Migrations & Invariants                                     #
    # ----------------------------------------------------------------------- #
    def test_database_idempotent_migration(self):
        db.upsert_avatar("test_av", name="Test Name")
        db.init_db()
        av = db.get_avatar("test_av")
        self.assertIsNotNone(av)
        self.assertEqual(av["name"], "Test Name")
        self.assertEqual(av.get("is_deleted"), 0)

    def test_activity_logging_redacts_secrets(self):
        db.log_activity(
            "TEST_ACTION", "avatar", "av_123",
            {"api_key": "secret_key_12345", "xi-api-key": "secret_token", "normal_data": "visible"},
            result="SUCCESS"
        )
        logs = db.list_activity_logs(10)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["action"], "TEST_ACTION")
        self.assertEqual(logs[0]["result"], "SUCCESS")
        details = json.loads(logs[0]["details"])
        self.assertEqual(details["api_key"], "***REDACTED***")
        self.assertEqual(details["xi-api-key"], "***REDACTED***")
        self.assertEqual(details["normal_data"], "visible")

    # ----------------------------------------------------------------------- #
    # 2. Avatar Management: Rename, Soft Delete, Restore                      #
    # ----------------------------------------------------------------------- #
    def test_avatar_rename_display_metadata(self):
        self._create_mock_avatar("mc_nu_01", name="MC Nữ Gốc")
        res = avatar_service.rename_avatar("mc_nu_01", "MC Nữ - Áo Trắng Đẹp (VTV1)")
        self.assertTrue(res["ok"])
        self.assertEqual(res["name"], "MC Nữ - Áo Trắng Đẹp (VTV1)")

        # Verify on-disk folder did NOT change
        self.assertTrue(os.path.isdir(os.path.join(self.test_avatars_root, "mc_nu_01")))

        # Verify DB reflects new name
        row = db.get_avatar("mc_nu_01")
        self.assertEqual(row["name"], "MC Nữ - Áo Trắng Đẹp (VTV1)")

        # Verify list_avatars uses new name
        avs = avatar_service.list_avatars()
        matched = next(a for a in avs if a["avatar_id"] == "mc_nu_01")
        self.assertEqual(matched["name"], "MC Nữ - Áo Trắng Đẹp (VTV1)")

    def test_avatar_rename_validation(self):
        self._create_mock_avatar("av_val")
        # Empty name rejected
        res = avatar_service.rename_avatar("av_val", "   ")
        self.assertFalse(res["ok"])

        # Overly long name rejected (>80 chars)
        res = avatar_service.rename_avatar("av_val", "A" * 81)
        self.assertFalse(res["ok"])

    def test_avatar_soft_delete_and_restore(self):
        self._create_mock_avatar("av_del_test", name="To Be Deleted")

        # Initial list contains avatar
        self.assertTrue(any(a["avatar_id"] == "av_del_test" for a in avatar_service.list_avatars()))

        # Soft delete
        del_res = avatar_service.delete_avatar("av_del_test")
        self.assertTrue(del_res["ok"])

        # Should disappear from normal list_avatars()
        self.assertFalse(any(a["avatar_id"] == "av_del_test" for a in avatar_service.list_avatars()))

        # Should appear in list_trash_avatars()
        trash = avatar_service.list_trash_avatars()
        self.assertTrue(any(a["avatar_id"] == "av_del_test" for a in trash))

        # Files on disk must remain completely untouched
        self.assertTrue(os.path.isfile(os.path.join(self.test_avatars_root, "av_del_test", "coords.pkl")))

        # Restore
        rest_res = avatar_service.restore_avatar("av_del_test")
        self.assertTrue(rest_res["ok"])

        # Should reappear in normal list_avatars()
        self.assertTrue(any(a["avatar_id"] == "av_del_test" for a in avatar_service.list_avatars()))

    def test_restore_fails_if_on_disk_artifacts_missing(self):
        # Create avatar in DB as deleted, but no files on disk
        db.soft_delete_avatar("missing_on_disk")
        res = avatar_service.restore_avatar("missing_on_disk")
        self.assertFalse(res["ok"])
        self.assertIn("không còn đầy đủ", res["error"])

    def test_avatar_delete_does_not_delete_raw_source(self):
        raw_path = os.path.join(self.test_raw_root, "common_source.mp4")
        with open(raw_path, "wb") as f:
            f.write(b"RAW_VIDEO_CONTENT")

        # Two avatars share the same raw source
        self._create_mock_avatar("av_var_1")
        self._create_mock_avatar("av_var_2")

        avatar_service.delete_avatar("av_var_1")

        # Raw file is still present on disk
        self.assertTrue(os.path.isfile(raw_path))
        # Variant 2 is still active and ready
        self.assertTrue(any(a["avatar_id"] == "av_var_2" for a in avatar_service.list_avatars()))

    def test_avatar_delete_blocked_when_active_jobs_exist(self):
        self._create_mock_avatar("av_busy")
        db.create_job({
            "job_id": "job_active_1",
            "kind": "test10s",
            "avatar_id": "av_busy",
            "voice_id": "pGapy9MNHCukzJtjavF0",
            "status": "rendering",
            "stage": "Rendering",
        })

        # Attempting to delete av_busy must fail with conflict (HTTP 409)
        res = avatar_service.delete_avatar("av_busy")
        self.assertFalse(res["ok"])
        self.assertTrue(res.get("conflict"))
        self.assertIn("job_active_1", res.get("active_jobs", []))

        # API endpoint should return 409
        resp = self.client.post("/api/avatars/av_busy/delete")
        self.assertEqual(resp.status_code, 409)

    def test_soft_deleted_avatar_cannot_create_job(self):
        self._create_mock_avatar("av_deleted_test")
        avatar_service.delete_avatar("av_deleted_test")

        res = render_service.create_test_job(
            avatar_id="av_deleted_test",
            voice_id="pGapy9MNHCukzJtjavF0",
            script_text="Hello test script"
        )
        self.assertFalse(res["ok"])
        self.assertIn("Thùng rác", res["error"])

    # ----------------------------------------------------------------------- #
    # 3. Render Management: Soft Delete, Restore, Retry                       #
    # ----------------------------------------------------------------------- #
    def test_render_soft_delete_and_restore(self):
        out_mp4 = os.path.join(self.test_renders_dir, "sample_render.mp4")
        with open(out_mp4, "wb") as f:
            f.write(b"MP4_VIDEO_BYTES")

        db.create_job({
            "job_id": "job_render_complete",
            "kind": "full",
            "avatar_id": "av_test",
            "voice_id": "pGapy9MNHCukzJtjavF0",
            "output_path": out_mp4,
            "status": "complete",
            "stage": "Complete",
        })

        # Normal list shows job
        jobs = db.list_jobs(include_deleted=False)
        self.assertTrue(any(j["job_id"] == "job_render_complete" for j in jobs))

        # Soft delete
        del_res = render_service.delete_render("job_render_complete")
        self.assertTrue(del_res["ok"])

        # Disappears from normal list
        jobs_after = db.list_jobs(include_deleted=False)
        self.assertFalse(any(j["job_id"] == "job_render_complete" for j in jobs_after))

        # Appears in trash
        trash_jobs = db.list_trash_jobs()
        self.assertTrue(any(j["job_id"] == "job_render_complete" for j in trash_jobs))

        # MP4 file stays on disk!
        self.assertTrue(os.path.isfile(out_mp4))

        # Restore
        rest_res = render_service.restore_render("job_render_complete")
        self.assertTrue(rest_res["ok"])

        # Reappears in normal list
        jobs_restored = db.list_jobs(include_deleted=False)
        self.assertTrue(any(j["job_id"] == "job_render_complete" for j in jobs_restored))

    def test_cannot_delete_active_rendering_job(self):
        db.create_job({
            "job_id": "job_rendering_now",
            "kind": "full",
            "avatar_id": "av_test",
            "voice_id": "pGapy9MNHCukzJtjavF0",
            "status": "rendering",
            "stage": "Rendering",
        })
        res = render_service.delete_render("job_rendering_now")
        self.assertFalse(res["ok"])
        self.assertIn("đang render", res["error"])

    def test_job_cancel_and_retry_preserves_immutable_snapshot(self):
        db.create_job({
            "job_id": "job_to_cancel",
            "kind": "full",
            "avatar_id": "av_test",
            "voice_id": "pGapy9MNHCukzJtjavF0",
            "script_text": "Immutable script",
            "tts_provider": "ELEVENLABS",
            "status": "queued",
            "stage": "Queued",
        })

        # Cancel queued job
        c_res = render_service.cancel_job("job_to_cancel")
        self.assertTrue(c_res["ok"])
        job_c = db.get_job("job_to_cancel")
        self.assertEqual(job_c["status"], "cancelled")

        # Retry cancelled job
        r_res = render_service.retry_job("job_to_cancel")
        self.assertTrue(r_res["ok"])
        job_r = db.get_job("job_to_cancel")
        self.assertEqual(job_r["status"], "queued")
        self.assertEqual(job_r["script_text"], "Immutable script")
        self.assertEqual(job_r["voice_id"], "pGapy9MNHCukzJtjavF0")

    # ----------------------------------------------------------------------- #
    # 4. API Endpoints & Trash Route                                          #
    # ----------------------------------------------------------------------- #
    def test_trash_api_endpoint(self):
        self._create_mock_avatar("av_in_trash")
        avatar_service.delete_avatar("av_in_trash")

        db.create_job({
            "job_id": "job_in_trash",
            "kind": "full",
            "avatar_id": "av_in_trash",
            "voice_id": "pGapy9MNHCukzJtjavF0",
            "status": "failed",
            "stage": "Failed",
            "is_deleted": 1,
            "deleted_at": time.time(),
        })

        resp = self.client.get("/api/trash")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertTrue(any(a["avatar_id"] == "av_in_trash" for a in data["avatars"]))
        self.assertTrue(any(j["job_id"] == "job_in_trash" for j in data["jobs"]))

    def test_activity_logs_api_endpoint(self):
        db.log_activity("TEST_API_LOG", "avatar", "test_id", {"info": "ok"}, "SUCCESS")
        resp = self.client.get("/api/activity-logs")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertTrue(any(l["action"] == "TEST_API_LOG" for l in data["logs"]))


if __name__ == "__main__":
    unittest.main()
