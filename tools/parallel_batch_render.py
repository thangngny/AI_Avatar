#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NextGen RTX 5090 Multi-Stream Parallel Batch Rendering Engine.

Khai thác 32GB VRAM GDDR7 và 24 cores i9-14900KF để render đồng thời 2-3 video
song song với hiệu suất tối đa, tự động đồng bộ lên Google Drive.
"""
import os
import sys
import time
import argparse
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed

PYTHON_BIN = os.path.join(r"C:\Users\phuongpn\runtime_nextgen\venv\Scripts", "python.exe")
SCRIPT_BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generate_video_from_script.py")


def _run_single_job(job_args):
    """Worker task that runs an isolated render subprocess."""
    worker_id, avatar_id, audio_path, output_path, smooth_60fps, batch_size = job_args
    t0 = time.time()
    cmd = [
        PYTHON_BIN,
        SCRIPT_BIN,
        "--avatar_id", avatar_id,
        "--audio", audio_path,
        "--output", output_path,
        "--batch_size", str(batch_size)
    ]
    if smooth_60fps:
        cmd.append("--smooth_60fps")

    print(f"[Worker-{worker_id}] STARTING render: avatar={avatar_id} -> {os.path.basename(output_path)}")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    dt = time.time() - t0

    success = (proc.returncode == 0) and os.path.isfile(output_path)
    if success:
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[Worker-{worker_id}] FINISHED in {dt:.1f}s ({size_mb:.1f} MB) -> {os.path.basename(output_path)}")
    else:
        print(f"[Worker-{worker_id}] FAILED in {dt:.1f}s:\n{proc.stdout[-500:] if proc.stdout else ''}")

    return {
        "worker_id": worker_id,
        "avatar_id": avatar_id,
        "output_path": output_path,
        "success": success,
        "duration_sec": dt,
        "stdout_tail": proc.stdout[-500:] if proc.stdout else ""
    }


def main():
    parser = argparse.ArgumentParser(description="NextGen RTX 5090 Parallel Batch Renderer")
    parser.add_argument("--workers", type=int, default=2, help="Number of concurrent workers (default: 2, max: 3)")
    parser.add_argument("--batch_size", type=int, default=32, help="UNet batch size per worker")
    args = parser.parse_args()

    audio_src = os.path.join(r"C:\Users\phuongpn\AI_Avatar_NextGen\renders", "demo_elevenlabs_16k.wav")
    if not os.path.isfile(audio_src):
        print(f"Audio source not found: {audio_src}")
        sys.exit(1)

    out_dir = r"D:\CongThang_AI_Avatar\renders"
    os.makedirs(out_dir, exist_ok=True)

    # Define 2 or 3 distinct benchmark jobs
    jobs = [
        (1, "doTrang_closeup", audio_src, os.path.join(out_dir, "parallel_stream1_doTrang_closeup.mp4"), False, args.batch_size),
        (2, "close_up", audio_src, os.path.join(out_dir, "parallel_stream2_close_up.mp4"), False, args.batch_size),
    ]
    if args.workers >= 3:
        jobs.append((3, "mc_hamai_mid", audio_src, os.path.join(out_dir, "parallel_stream3_mc_hamai_mid.mp4"), False, args.batch_size))

    print("=" * 60)
    print(f"RTX 5090 PARALLEL BATCH RENDER: Launching {len(jobs)} concurrent streams")
    print(f"Workers: {args.workers} | Batch size per worker: {args.batch_size}")
    print("=" * 60)

    total_t0 = time.time()
    results = []

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_run_single_job, job): job for job in jobs}
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)

    total_dt = time.time() - total_t0
    successful = sum(1 for r in results if r["success"])

    print("=" * 60)
    print(f"PARALLEL BATCH SUMMARY: {successful}/{len(jobs)} jobs completed successfully")
    print(f"Total wall time: {total_dt:.1f}s")
    for r in results:
        status = "OK" if r["success"] else "FAIL"
        print(f" - Worker {r['worker_id']}: {status} in {r['duration_sec']:.1f}s -> {os.path.basename(r['output_path'])}")
    
    # Calculate aggregate throughput
    # Each job has 550 frames
    total_frames = successful * 550
    agg_fps = total_frames / total_dt if total_dt > 0 else 0
    print(f"Aggregate System Throughput: {agg_fps:.1f} FPS (Total {total_frames} frames rendered in {total_dt:.1f}s)")
    print("=" * 60)


if __name__ == "__main__":
    main()
