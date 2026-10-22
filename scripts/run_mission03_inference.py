"""
AI Avatar NextGen V2 - Mission 03 Automated Real Inference Harness
Executes SoulX-FlashHead Pro neural inference on RTX 5090 Blackwell,
tracks sub-second VRAM telemetry, and validates output MP4 with ffprobe.
"""
import os
import sys
import time
import json
import csv
import argparse
import subprocess
import threading
import shutil

REPO_ROOT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2"
SOULX_ENG_DIR = os.path.join(REPO_ROOT, "engines", "soulx_flashhead")
WEIGHTS_DIR = os.path.join(REPO_ROOT, "weights", "SoulX-FlashHead-1_3B")
STAGING_DIR = r"D:\CongThang_AI_Avatar\staging_weights\SoulX-FlashHead-1_3B\Model_Pro"
WAV2VEC_DIR = os.path.join(REPO_ROOT, "weights", "wav2vec2-base-960h")
REPORTS_DIR = os.path.join(REPO_ROOT, "reports", "mission03")
os.makedirs(REPORTS_DIR, exist_ok=True)

EXPECTED_SIZE = 6030864656
OFFICIAL_LFS_SHA256 = "e47e61b9023ea1aac60c0c0fff077289bc6cca443c71907e5a76a411480af250"
PRO_SAFETENSORS_NAME = "diffusion_pytorch_model.safetensors"
pro_staged = os.path.join(STAGING_DIR, PRO_SAFETENSORS_NAME)
pro_final = os.path.join(WEIGHTS_DIR, "Model_Pro", PRO_SAFETENSORS_NAME)
pro_staged_part = os.path.join(STAGING_DIR, PRO_SAFETENSORS_NAME + ".part")

LOG_FILE = os.path.join(REPORTS_DIR, "inference.log")

COND_IMAGE = os.path.join(REPO_ROOT, "data", "avatars", "doTrang_closeup", "portrait_512.png")
AUDIO_3S = os.path.join(REPO_ROOT, "benchmarks", "test_dataset", "test_a_neutral_3s.wav")
AUDIO_FULL = os.path.join(REPO_ROOT, "benchmarks", "test_dataset", "test_a_neutral.wav")


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] {msg}"
    print(formatted, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")


def check_checkpoint_ready():
    if os.path.exists(pro_final) and os.path.getsize(pro_final) == EXPECTED_SIZE:
        log(f"Verified Model_Pro weights present at final location: {pro_final} ({EXPECTED_SIZE} bytes)")
        return True

    if os.path.exists(pro_staged) and os.path.getsize(pro_staged) == EXPECTED_SIZE:
        log(f"Staged file verified ({EXPECTED_SIZE} bytes). Copying to {pro_final} ...")
        os.makedirs(os.path.dirname(pro_final), exist_ok=True)
        shutil.copy2(pro_staged, pro_final)
        log("Copy complete.")
        return True

    if os.path.exists(pro_staged_part):
        current_sz = os.path.getsize(pro_staged_part)
        pct = (current_sz / EXPECTED_SIZE) * 100
        log(f"Model_Pro safetensors is currently downloading: {current_sz}/{EXPECTED_SIZE} bytes ({pct:.2f}%)")
        return False

    log(f"Model_Pro safetensors not yet found at {pro_final} or {pro_staged}")
    return False


def verify_official_sha256(file_path):
    import hashlib
    log(f"Computing SHA256 digest for {file_path} (6.03 GB) ...")
    t0 = time.time()
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(16 * 1024 * 1024):
            h.update(chunk)
    digest = h.hexdigest().lower()
    elapsed = time.time() - t0
    log(f"Computed SHA256 in {elapsed:.2f}s: {digest}")
    log(f"Official Hugging Face LFS SHA256: {OFFICIAL_LFS_SHA256}")
    if digest == OFFICIAL_LFS_SHA256.lower():
        log("[PASS] Cryptographic SHA256 integrity verified 100% against official Hugging Face digest!")
        return True, digest
    else:
        log(f"[FAIL] SHA256 digest mismatch! Expected {OFFICIAL_LFS_SHA256}, got {digest}")
        return False, digest


def validate_safetensors_header(file_path):
    log("Validating safetensors header integrity...")
    from safetensors import safe_open
    with safe_open(file_path, framework="pt", device="cpu") as f:
        keys = list(f.keys())
        log(f"Safetensors validated! Total tensor keys: {len(keys)}")
        log(f"First 5 keys: {keys[:5]}")
    return len(keys)


def monitor_gpu(telemetry_path, stop_event, peak_holder):
    with open(telemetry_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_sec", "memory_used_mib", "memory_total_mib", "gpu_util_pct", "power_w", "temp_c"])
        t0 = time.time()
        while not stop_event.is_set():
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,power.draw,temperature.gpu", "--format=csv,noheader,nounits"],
                    timeout=1
                ).decode().strip()
                parts = [p.strip() for p in out.split(",")]
                mem_used = float(parts[0])
                if mem_used > peak_holder[0]:
                    peak_holder[0] = mem_used
                writer.writerow([round(time.time() - t0, 2)] + parts)
            except Exception:
                pass
            time.sleep(0.05)


def run_inference(cond_image, audio_path, output_mp4, duration_label):
    log("=" * 60)
    log(f"STARTING SOULX-FLASHHEAD PRO NEURAL INFERENCE ({duration_label}) ON RTX 5090")
    log("=" * 60)
    log(f"Condition image: {cond_image}")
    log(f"Audio input: {audio_path}")
    log(f"Output MP4: {output_mp4}")

    telemetry_csv = os.path.join(REPORTS_DIR, f"gpu_telemetry_{duration_label}.csv")
    manifest_json = os.path.join(REPORTS_DIR, f"inference_manifest_{duration_label}.json")

    cmd = [
        sys.executable,
        os.path.join(SOULX_ENG_DIR, "generate_video.py"),
        "--ckpt_dir", WEIGHTS_DIR,
        "--wav2vec_dir", WAV2VEC_DIR,
        "--model_type", "pro",
        "--cond_image", cond_image,
        "--audio_path", audio_path,
        "--audio_encode_mode", "stream",
        "--save_file", output_mp4
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = SOULX_ENG_DIR + os.pathsep + env.get("PYTHONPATH", "")

    stop_event = threading.Event()
    peak_holder = [0.0]
    mon_th = threading.Thread(target=monitor_gpu, args=(telemetry_csv, stop_event, peak_holder), daemon=True)
    mon_th.start()

    t_start = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        cwd=SOULX_ENG_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    for line in proc.stdout:
        log(f"[SOULX] {line.strip()}")

    proc.wait()
    t_end = time.perf_counter()
    stop_event.set()
    mon_th.join(timeout=1.0)

    total_time = t_end - t_start
    log(f"Inference process finished with return code {proc.returncode} in {total_time:.2f}s")
    log(f"Peak VRAM captured: {peak_holder[0]} MiB")

    if proc.returncode != 0:
        log("ERROR: SoulX Pro inference failed!")
        return False, total_time, peak_holder[0]

    # Validate output media with ffprobe
    log("Probing output MP4 with ffprobe...")
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration:format=duration,size",
        "-of", "json",
        output_mp4
    ]
    probe_res = subprocess.check_output(probe_cmd).decode()
    probe_data = json.loads(probe_res)
    log(f"Output video metadata: {json.dumps(probe_data, indent=2)}")

    manifest = {
        "model": "SoulX-FlashHead 1.3B Pro",
        "model_revision": "5fbd2e44ba08ab2deb28bd55cff2c15523e51ba5",
        "safetensors_sha256": OFFICIAL_LFS_SHA256,
        "safetensors_bytes": EXPECTED_SIZE,
        "gpu": "NVIDIA GeForce RTX 5090 Blackwell",
        "duration_label": duration_label,
        "input_image": cond_image,
        "input_audio": audio_path,
        "output_file": output_mp4,
        "wall_clock_time_sec": round(total_time, 2),
        "peak_vram_mib": peak_holder[0],
        "ffprobe_metadata": probe_data
    }
    with open(manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Also write canonical general manifest
    with open(os.path.join(REPORTS_DIR, "inference_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    log(f"Mission 03 inference manifest ({duration_label}) saved successfully!")
    return True, total_time, peak_holder[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=str, default="3s", choices=["3s", "10s"])
    args = parser.parse_args()

    ready = check_checkpoint_ready()
    if not ready:
        log("Checkpoint download is still underway. Exiting pre-check.")
        sys.exit(2)

    sha_ok, computed_sha = verify_official_sha256(pro_final)
    if not sha_ok:
        log("FATAL: Checkpoint SHA256 verification failed! Refusing to run inference on corrupt weights.")
        sys.exit(3)

    validate_safetensors_header(pro_final)

    if args.duration == "3s":
        audio = AUDIO_3S
        out_mp4 = os.path.join(REPORTS_DIR, "soulx_pro_3s.mp4")
    else:
        audio = AUDIO_FULL
        out_mp4 = os.path.join(REPORTS_DIR, "soulx_pro_10s.mp4")

    success, t_sec, peak_vram = run_inference(COND_IMAGE, audio, out_mp4, args.duration)
    if success:
        log(f"MISSION 03 INFERENCE ({args.duration}) COMPLETE!")
        if args.duration == "10s":
            log("Automatically executing aspect-preserving A/B composite...")
            comp_script = os.path.join(REPO_ROOT, "scripts", "composite_ab_test.py")
            subprocess.run([sys.executable, comp_script], cwd=REPO_ROOT)
        sys.exit(0)
    else:
        sys.exit(1)
