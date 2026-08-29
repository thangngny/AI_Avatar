#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Avatar Studio — V1.6.0 runtime/deployment hardening acceptance tests.

Covers the proven incident class (code on disk changed while a stale server
kept an OLD route table in memory -> silent 404s). Verifies, at the unit level:

  * contract source-of-truth matches the frontend constant (no scattering);
  * canonical-interpreter enforcement (True/False detection);
  * startup vs disk code fingerprint -> CODE_DRIFT / restart_required;
  * frontend/backend contract mismatch is DETECTED (regression for the incident);
  * boot_id changes across restarts;
  * instance manifest carries no secrets;
  * stale-PID safety (dead / reused PID rejected);
  * single-instance decision (proceed / unknown-owner / already-running);
  * /api/system/status exposes process/code/contract + composite ready;
  * /api/studio/restart is owner-direct only + active-job-blocked + spawns only
    locally (Popen mocked);
  * post-start smoke flags a missing route (the original failure mode);
  * Production Truth hash unchanged.

These are UNIT_TEST_ONLY / PROVEN_STATIC (mocked or in-process). The REAL
port-8077 + Playwright verification is performed separately and documented in
docs/V1_6_RUNTIME_DEPLOYMENT_HARDENING.md.
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


class HardeningTestCase(unittest.TestCase):
    def setUp(self):
        from studio import config
        self._orig_db = config.DB_PATH
        self._orig_manifest = config.INSTANCE_MANIFEST_PATH
        self._orig_canonical = config.CANONICAL_INTERPRETER
        self.tmp = tempfile.mkdtemp(prefix="studio_hard_")
        config.DB_PATH = os.path.join(self.tmp, "test.db")
        config.INSTANCE_MANIFEST_PATH = os.path.join(self.tmp, "studio_instance.json")
        config.ensure_runtime_dirs()
        from studio import db
        db.init_db()
        from studio import render_service
        self._orig_disabled = render_service._WORKER_DISABLED
        render_service._WORKER_DISABLED = True
        from studio import runtime_guard as rg
        rg._STARTUP.clear()
        rg._LAST_REPORTED_FP = None
        rg._DISK_FP = {"fp": None, "ts": 0.0}
        self._orig_disk_fp = rg.current_disk_fingerprint

    def tearDown(self):
        from studio import config, render_service
        render_service._WORKER_DISABLED = self._orig_disabled
        config.DB_PATH = self._orig_db
        config.INSTANCE_MANIFEST_PATH = self._orig_manifest
        config.CANONICAL_INTERPRETER = self._orig_canonical
        from studio import runtime_guard as rg
        rg.current_disk_fingerprint = self._orig_disk_fp
        rg._STARTUP.clear()
        rg._LAST_REPORTED_FP = None
        rg._DISK_FP = {"fp": None, "ts": 0.0}
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestContractSourceOfTruth(HardeningTestCase):
    def test_contract_json_and_frontend_constant_match(self):
        from studio import runtime_guard as rg
        disk = rg.load_contract_version()
        # Frontend constant in app.js must equal the JSON source of truth.
        with open(os.path.join(ROOT, "studio", "static", "app.js"), "r", encoding="utf-8") as f:
            js = f.read()
        import re
        m = re.search(r'STUDIO_API_CONTRACT\s*=\s*"([^"]+)"', js)
        self.assertTrue(m, "STUDIO_API_CONTRACT not found in app.js")
        self.assertEqual(m.group(1), disk,
                         "Frontend contract constant must equal config/api_contract.json")
        self.assertTrue(disk, "contract version must be non-empty")


class TestCanonicalRuntime(HardeningTestCase):
    def test_canonical_interpreter_true_when_matching(self):
        from studio import config, runtime_guard as rg
        config.CANONICAL_INTERPRETER = r"D:\some\venv\Scripts\python.exe"
        self.assertTrue(rg.interpreter_is_canonical(r"D:\some\venv\Scripts\python.exe"))
        # Case/separator insensitive
        self.assertTrue(rg.interpreter_is_canonical(r"d:\some\venv/scripts\python.exe"))

    def test_canonical_interpreter_false_when_different(self):
        from studio import config, runtime_guard as rg
        config.CANONICAL_INTERPRETER = r"D:\canonical\python.exe"
        self.assertFalse(rg.interpreter_is_canonical(r"C:\System\python.exe"))

    def test_canonical_missing_detected(self):
        from studio import config, runtime_guard as rg
        config.CANONICAL_INTERPRETER = os.path.join(self.tmp, "nope.exe")
        self.assertFalse(rg.canonical_interpreter_exists())


class TestCodeFingerprint(HardeningTestCase):
    def test_fingerprint_is_content_based(self):
        from studio import runtime_guard as rg
        f = os.path.join(self.tmp, "mod.py")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("v1\n")
        a = rg.compute_code_fingerprint(rel_paths=[os.path.relpath(f, ROOT)])
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("v2-different-content\n")
        b = rg.compute_code_fingerprint(rel_paths=[os.path.relpath(f, ROOT)])
        self.assertNotEqual(a, b, "fingerprint must change when content changes")

    def test_fingerprint_stable_when_unchanged(self):
        from studio import runtime_guard as rg
        f = os.path.join(self.tmp, "mod2.py")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("stable\n")
        rel = os.path.relpath(f, ROOT)
        self.assertEqual(rg.compute_code_fingerprint(rel_paths=[rel]),
                         rg.compute_code_fingerprint(rel_paths=[rel]))

    def test_restart_sensitive_manifest_is_bounded_and_explicit(self):
        from studio import runtime_guard as rg
        self.assertGreater(len(rg.RESTART_SENSITIVE_FILES), 5)
        # No frontend / docs / contract JSON in the restart-sensitive set.
        for p in rg.RESTART_SENSITIVE_FILES:
            self.assertTrue(p.endswith(".py"), f"{p} should be a backend Python module")
            self.assertNotIn("app.js", p)
            self.assertNotIn("api_contract", p)


class TestCodeDrift(HardeningTestCase):
    def test_drift_detected_when_disk_differs_from_startup(self):
        from studio import runtime_guard as rg
        rg._STARTUP.clear()
        rg.init_at_startup()
        rg._STARTUP["startup_code_fingerprint"] = "AAAA"
        rg.current_disk_fingerprint = lambda force=False: "BBBB"
        snap = rg.runtime_status_snapshot("2026-08-29.1")
        self.assertEqual(snap["code_sync"], "STALE")
        self.assertTrue(snap["restart_required"])
        self.assertFalse(snap["studio_accepting_new_work"])

    def test_current_when_disk_matches_startup(self):
        from studio import runtime_guard as rg
        rg.init_at_startup()
        snap = rg.runtime_status_snapshot("2026-08-29.1")
        self.assertEqual(snap["code_sync"], "CURRENT")
        self.assertFalse(snap["restart_required"])


class TestContractMismatchRegression(HardeningTestCase):
    """Regression for the proven incident: server frozen at contract A, the
    served frontend represents contract B -> the system must DETECT this before
    the user hits a random 404, not after."""

    def test_mismatch_detected(self):
        from studio import runtime_guard as rg
        rg._STARTUP.clear()
        rg._STARTUP.update({
            "boot_id": "x", "pid": os.getpid(),
            "process_created_at": rg.process_creation_time(os.getpid()),
            "interpreter": rg.canonical_interpreter(),
            "startup_code_fingerprint": rg.compute_code_fingerprint(),
            "backend_contract_version": "contract-A",
        })
        snap = rg.runtime_status_snapshot(frontend_contract="contract-B")
        self.assertFalse(snap["contract"]["compatible"])
        self.assertEqual(snap["contract"]["backend_version"], "contract-A")
        self.assertEqual(snap["contract"]["frontend_version"], "contract-B")
        self.assertFalse(snap["studio_accepting_new_work"])

    def test_match_when_aligned(self):
        from studio import runtime_guard as rg
        rg._STARTUP.clear()
        rg._STARTUP.update({
            "boot_id": "y", "pid": os.getpid(),
            "process_created_at": rg.process_creation_time(os.getpid()),
            "interpreter": rg.canonical_interpreter(),
            "startup_code_fingerprint": rg.compute_code_fingerprint(),
            "backend_contract_version": "2026-08-29.1",
        })
        snap = rg.runtime_status_snapshot(frontend_contract="2026-08-29.1")
        self.assertTrue(snap["contract"]["compatible"])


class TestBootId(HardeningTestCase):
    def test_boot_id_changes_on_reinit(self):
        from studio import runtime_guard as rg
        rg._STARTUP.clear()
        a = rg.init_at_startup()["boot_id"]
        rg._STARTUP.clear()
        b = rg.init_at_startup()["boot_id"]
        self.assertNotEqual(a, b)


class TestInstanceManifest(HardeningTestCase):
    def test_manifest_has_no_secrets(self):
        from studio import runtime_guard as rg
        rg.init_at_startup()
        m = rg.read_instance_manifest()
        self.assertIsNotNone(m)
        blob = json.dumps(m)
        for secret in ("ELEVENLABS_API_KEY", "xi-api-key", "Authorization",
                       "CLOUDFLARE", "api_key", ".env"):
            self.assertNotIn(secret, blob)
        # Required identity fields present.
        for k in ("pid", "boot_id", "server_started_at", "interpreter",
                  "startup_code_fingerprint", "backend_contract_version",
                  "production_truth_hash"):
            self.assertIn(k, m)

    def test_stale_manifest_dead_pid_rejected(self):
        from studio import runtime_guard as rg
        m = {"pid": 9999999, "port": 8077,
             "process_created_at": 1000.0, "server_started_at": 1000.0}
        ok, reason = rg.pid_matches_manifest(m)
        self.assertFalse(ok)
        self.assertEqual(reason, "pid_dead")

    def test_stale_manifest_creation_time_mismatch_rejected(self):
        from studio import runtime_guard as rg
        # A live PID but a WRONG creation time => PID was reused (stale).
        m = {"pid": os.getpid(), "port": 8077,
             "process_created_at": 12345.0, "server_started_at": 12345.0}
        ok, reason = rg.pid_matches_manifest(m)
        self.assertFalse(ok)
        self.assertIn("creation_time", reason)


class TestSingleInstance(HardeningTestCase):
    def test_proceed_when_port_free(self):
        from studio import runtime_guard as rg
        import psutil
        orig = psutil.net_connections
        psutil.net_connections = lambda *a, **k: []
        try:
            d = rg.single_instance_decision(8077)
        finally:
            psutil.net_connections = orig
        self.assertEqual(d["action"], "proceed")

    def test_unknown_owner_not_killed(self):
        from studio import runtime_guard as rg
        import psutil

        class FakeAddr:
            def __init__(self, port, pid):
                self.laddr = type("L", (), {"port": port})()
                self.status = psutil.CONN_LISTEN
                self.pid = pid

        # A port owner whose command line is NOT run_studio.py.
        me = os.getpid()
        orig_nc = psutil.net_connections

        def fake_nc(*a, **k):
            # If WE are the owner, _owner_is_studio inspects OUR cmdline which
            # under unittest is "python -m unittest ...", not run_studio.py.
            return [FakeAddr(8077, me)]

        psutil.net_connections = fake_nc
        try:
            d = rg.single_instance_decision(8077)
        finally:
            psutil.net_connections = orig_nc
        self.assertEqual(d["action"], "unknown_owner",
                         "a non-Studio port owner must not be assumed Studio")


class TestProductionTruth(HardeningTestCase):
    def test_truth_hash_unchanged(self):
        from studio import runtime_guard as rg
        self.assertEqual(rg.production_truth_hash(),
                         "a5a0e55f46c29c1722efc5cc3f8fec3d902260f0")
        self.assertTrue(rg.production_truth_valid())


class TestStatusAPI(HardeningTestCase):
    def setUp(self):
        super().setUp()
        from studio.app import app
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_status_exposes_hardening_fields(self):
        from studio import runtime_guard as rg
        rg.init_at_startup()  # populate frozen startup state
        r = self.client.get("/api/system/status?frontend_contract=2026-08-29.1")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        for k in ("process", "code", "contract", "production_truth",
                 "code_sync", "contract_sync", "restart_required",
                 "studio_accepting_new_work", "ready"):
            self.assertIn(k, d)
        self.assertEqual(d["code_sync"], "CURRENT")
        self.assertTrue(d["contract_sync"])
        self.assertFalse(d["restart_required"])
        # No secret leak.
        from studio import envutil
        envutil.load_env(force=True)
        key = envutil.env_str("ELEVENLABS_API_KEY", "")
        if key:
            self.assertNotIn(key, json.dumps(d))

    def test_status_ready_false_on_drift(self):
        from studio import runtime_guard as rg
        rg.init_at_startup()
        rg._STARTUP["startup_code_fingerprint"] = "STALEAAAA"
        rg.current_disk_fingerprint = lambda force=False: "DISKBBBB"
        r = self.client.get("/api/system/status?frontend_contract=2026-08-29.1")
        d = r.get_json()
        self.assertFalse(d["ready"])
        self.assertTrue(d["restart_required"])
        self.assertFalse(d["studio_accepting_new_work"])
        self.assertEqual(d["code_sync"], "STALE")


class TestRestartEndpoint(HardeningTestCase):
    def setUp(self):
        super().setUp()
        from studio.app import app
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_remote_restart_forbidden(self):
        r = self.client.post("/api/studio/restart",
                             environ_overrides={"REMOTE_ADDR": "203.0.113.5"})
        self.assertEqual(r.status_code, 403)
        self.assertIn("quản trị viên", r.get_json()["error"])

    def test_local_restart_blocked_by_active_job(self):
        from studio import db
        db.create_job({
            "job_id": "j1", "kind": "render", "avatar_id": "a1",
            "voice_id": "v1", "script_text": "x", "status": "queued",
        })
        r = self.client.post("/api/studio/restart")  # loopback by default
        self.assertEqual(r.status_code, 409)
        self.assertTrue(r.get_json()["blocked"])
        self.assertEqual(r.get_json()["reason"], "ACTIVE_JOBS_BLOCK_RESTART")

    def test_local_restart_no_jobs_launches_orchestrator(self):
        import studio.app as appmod
        import subprocess
        launched = {}
        orig_popen = subprocess.Popen

        class FakePopen:
            def __init__(self, cmd, *a, **k):
                launched["cmd"] = cmd
        subprocess.Popen = FakePopen
        try:
            r = self.client.post("/api/studio/restart")
        finally:
            subprocess.Popen = orig_popen
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["restarting"])
        self.assertTrue(launched["cmd"][-1].endswith("restart_studio.py")
                        or any("restart_studio" in str(c) for c in launched["cmd"]))


class TestSmoke(HardeningTestCase):
    def test_smoke_flags_missing_route(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("rst", os.path.join(ROOT, "tools", "restart_studio.py"))
        rst = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rst)
        # All 200 except a sample route returns 404 -> smoke must fail.
        def fake_get(path, port=8077, timeout=8):
            if path.endswith("/sample"):
                return 404, {"Content-Type": "text/html"}, b""
            return 200, {"Content-Type": "audio/wav" if "sample" in path else "application/json"}, b""
        rst._http_get = fake_get
        ok, details = rst.smoke(8077)
        self.assertFalse(ok)

    def test_smoke_passes_when_all_200(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("rst2", os.path.join(ROOT, "tools", "restart_studio.py"))
        rst = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rst)
        def fake_get(path, port=8077, timeout=8):
            ct = "audio/wav" if "sample" in path else "application/json"
            return 200, {"Content-Type": ct}, b""
        rst._http_get = fake_get
        ok, details = rst.smoke(8077)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()