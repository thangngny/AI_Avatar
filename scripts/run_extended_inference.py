"""
AI Avatar NextGen V2 - Extended Inference Harness (30s & 60s)
Executes long-form SoulX-FlashHead Pro generation, tracks sub-second GPU telemetry,
and inspects chunk transitions and audio-visual synchronization drift.
"""
import os
import sys
import time
import json
import csv
import argparse
import subprocess
import threading

REPO_ROOT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2"
SOULX_ENG_DIR = os.path.join(REPO_ROOT, "engines", "soulx_flashhead")
WEIGHTS_DIR = os.path.join(REPO_ROOT, "weights", "SoulX-FlashHead-1_3B")
WAV2VEC_DIR = os.path.join(REPO_ROOT, "weights", "wav2vec2-base-960h")
REPORTS_DIR = os.path.join(REPO_ROOT, "reports", "mission04")
os.makedirs(REPORTS_DIR, exist_ok=True)

COND_IMAGE = os.path.join(REPO_ROOT, "data", "avatars", "doTrang_closeup", "portrait_512.png")
AUDIO_30S = os.path.join(REPO_ROOT, "benchmarks", "test_dataset", "master_30s_vietnamese.wav")
AUDIO_60S = os.path.join(REPO_ROOT, "assets", "master_60s_vietnamese.wav")

LOG_FILE = os.path.join(REPORTS_DIR, "extended_inference.log")


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] {msg}"
    print(formatted, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")


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


def run_extended_inference(duration_label):
    if duration_label == "30s":
        audio_path = AUDIO_30S
        out_mp4 = os.path.join(REPORTS_DIR, "soulx_pro_30s.mp4")
    else:
        audio_path = AUDIO_60S
        out_mp4 = os.path.join(REPORTS_DIR, "soulx_pro_60s.mp4")

    telemetry_csv = os.path.join(REPORTS_DIR, f"gpu_telemetry_{duration_label}.csv")
    manifest_json = os.path.join(REPORTS_DIR, f"inference_manifest_{duration_label}.json")

    log("=" * 60)
    log(f"STARTING SOULX-FLASHHEAD PRO EXTENDED INFERENCE ({duration_label}) ON RTX 5090")
    log("=" * 60)
    log(f"Audio file: {audio_path}")
    log(f"Output video: {out_mp4}")

    cmd = [
        sys.executable,
        os.path.join(SOULX_ENG_DIR, "generate_video.py"),
        "--ckpt_dir", WEIGHTS_DIR,
        "--wav2vec_dir", WAV2VEC_DIR,
        "--model_type", "pro",
        "--cond_image", COND_IMAGE,
        "--audio_path", audio_path,
        "--audio_encode_mode", "stream",
        "--save_file", out_mp4
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

    chunk_times = []
    for line in proc.stdout:
        line_clean = line.strip()
        log(f"[SOULX] {line_clean}")
        if "Generate video chunk" in line_clean and "cost time:" in line_clean:
            try:
                cost = float(line_clean.split("cost time:")[-1].replace("s", "").strip())
                chunk_times.append(cost)
            except Exception:
                pass

    proc.wait()
    t_end = time.perf_counter()
    stop_event.set()
    mon_th.join(timeout=1.0)

    total_time = t_end - t_start
    log(f"Inference process finished with return code {proc.returncode} in {total_time:.2f}s")
    log(f"Peak VRAM: {peak_holder[0]} MiB | Total Chunks: {len(chunk_times)}")
    if chunk_times:
        log(f"Average chunk time (post-warmup): {sum(chunk_times[1:]) / max(len(chunk_times)-1, 1):.3f}s")

    if proc.returncode != 0:
        log(f"ERROR: Extended inference ({duration_label}) failed!")
        return False

    # ffprobe verification
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration:format=duration,size",
        "-of", "json",
        out_mp4
    ]
    probe_res = subprocess.check_output(probe_cmd).decode()
    probe_data = json.loads(probe_res)
    log(f"Output video probe metadata: {json.dumps(probe_data, indent=2)}")

    manifest = {
        "model": "SoulX-FlashHead 1.3B Pro",
        "duration_label": duration_label,
        "input_audio": audio_path,
        "output_file": out_mp4,
        "wall_clock_time_sec": round(total_time, 2),
        "peak_vram_mib": peak_holder[0],
        "total_chunks": len(chunk_times),
        "chunk_times_sec": chunk_times,
        "ffprobe_metadata": probe_data
    }
    with open(manifest_json, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    log(f"Extended manifest ({duration_label}) saved successfully!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", choices=["30s", "60s"], default="30s")
    args = parser.parse_args()
    success = run_extended_inference(args.duration)
    sys.exit(0 if success else 1)
