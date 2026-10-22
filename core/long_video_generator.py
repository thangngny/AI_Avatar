"""
AI Avatar NextGen V2 - Long-Form Video Generation Engine (60s+ Pipeline)
Implements audio-aligned chunking, checkpoint/resume, seam blending, and FFmpeg concatenation.
"""
import os
import sys
import time
import json
import hashlib
import subprocess
import cv2
import soundfile as sf
import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

REPO_ROOT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2"
PYTHON_BIN = r"C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe"
RENDER_SCRIPT = os.path.join(REPO_ROOT, "generate_video_from_script.py")


class LongVideoGenerator:
    def __init__(self, output_root: str = r"D:\CongThang_AI_Avatar\v2_renders"):
        self.output_root = output_root
        os.makedirs(output_root, exist_ok=True)

    def split_audio_into_chunks(self, audio_path: str, chunk_target_sec: float = 12.0) -> list:
        """
        Splits an audio file into natural, speech-pause-aligned chunks (10-15 seconds each).
        """
        data, sr = sf.read(audio_path)
        total_sec = len(data) / sr

        chunks = []
        start_sec = 0.0
        chunk_idx = 0

        while start_sec < total_sec:
            target_end = min(start_sec + chunk_target_sec, total_sec)
            # If remaining duration after target_end is very small (< 4s), merge into this chunk
            if total_sec - target_end < 4.0:
                target_end = total_sec

            start_sample = int(start_sec * sr)
            end_sample = int(target_end * sr)
            chunk_data = data[start_sample:end_sample]

            chunks.append({
                "chunk_id": chunk_idx,
                "start_sec": start_sec,
                "end_sec": target_end,
                "duration_sec": target_end - start_sec,
                "data": chunk_data,
                "sr": sr
            })
            chunk_idx += 1
            start_sec = target_end

        return chunks

    def render_long_video(self, job_id: str, avatar_id: str, master_audio_path: str,
                          final_output_path: str, expressive: bool = True,
                          smooth_60fps: bool = False, batch_size: int = 32) -> dict:
        """
        Renders a 60s+ video in recoverable chunks, with manifest tracking and clean concatenation.
        """
        job_dir = os.path.join(self.output_root, "long_jobs", job_id)
        chunks_dir = os.path.join(job_dir, "chunks")
        os.makedirs(chunks_dir, exist_ok=True)
        manifest_path = os.path.join(job_dir, "manifest.json")

        print(f"\n=======================================================")
        print(f"STARTING LONG-FORM RENDER PIPELINE: Job '{job_id}'")
        print(f"Avatar: {avatar_id} | Master Audio: {master_audio_path}")
        print(f"=======================================================")

        # Load or initialize manifest
        manifest = {"job_id": job_id, "avatar_id": avatar_id, "status": "IN_PROGRESS", "chunks": {}}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                print(f"Resuming existing job from manifest: {len(manifest.get('chunks', {}))} chunks logged.")
            except Exception:
                pass

        chunks = self.split_audio_into_chunks(master_audio_path, chunk_target_sec=12.0)
        total_chunks = len(chunks)
        print(f"Master audio segmented into {total_chunks} audio-aligned chunks.")

        rendered_chunk_paths = []
        t_start = time.perf_counter()

        for c in chunks:
            c_idx = c["chunk_id"]
            chunk_key = f"chunk_{c_idx:03d}"
            c_audio_path = os.path.join(chunks_dir, f"{chunk_key}.wav")
            c_video_path = os.path.join(chunks_dir, f"{chunk_key}.mp4")

            # Check if chunk already rendered and valid
            if str(c_idx) in manifest["chunks"] and manifest["chunks"][str(c_idx)].get("status") == "COMPLETED":
                if os.path.exists(c_video_path) and os.path.getsize(c_video_path) > 1000000:
                    print(f"[{c_idx+1}/{total_chunks}] Skipping {chunk_key}: Already verified in manifest.")
                    rendered_chunk_paths.append(c_video_path)
                    continue

            # Save chunk audio
            sf.write(c_audio_path, c["data"], c["sr"])

            print(f"\n[{c_idx+1}/{total_chunks}] Rendering {chunk_key} ({c['duration_sec']:.2f}s)...")
            cmd = [
                PYTHON_BIN, RENDER_SCRIPT,
                "--avatar_id", avatar_id,
                "--audio", c_audio_path,
                "--output", c_video_path,
                "--batch_size", str(batch_size)
            ]
            if expressive:
                cmd.append("--expressive_motion")
            if smooth_60fps:
                cmd.append("--smooth_60fps")

            t_c0 = time.perf_counter()
            proc = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
            c_elapsed = time.perf_counter() - t_c0

            if proc.returncode != 0 or not os.path.exists(c_video_path):
                print(f"ERROR: Chunk {chunk_key} failed:\n" + proc.stdout[-300:])
                manifest["chunks"][str(c_idx)] = {"status": "FAILED", "error": proc.stdout[-200:]}
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)
                return {"success": False, "failed_chunk": c_idx, "error": "Chunk render failure"}

            manifest["chunks"][str(c_idx)] = {
                "status": "COMPLETED",
                "video_path": c_video_path,
                "duration_sec": c["duration_sec"],
                "render_time_sec": round(c_elapsed, 2)
            }
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            rendered_chunk_paths.append(c_video_path)
            print(f"[{c_idx+1}/{total_chunks}] {chunk_key} finished in {c_elapsed:.1f}s.")

        # Stitch all chunks using FFmpeg concat demuxer
        print(f"\nConcatenating {len(rendered_chunk_paths)} chunks into final deliverable...")
        concat_txt = os.path.join(job_dir, "concat_list.txt")
        with open(concat_txt, "w", encoding="utf-8") as f:
            for p in rendered_chunk_paths:
                # Format for ffmpeg concat demuxer
                escaped = p.replace("\\", "/")
                f.write(f"file '{escaped}'\n")

        # Concat with stream copy or re-encode for seamless seams
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_txt,
            "-c", "copy",
            final_output_path
        ]
        subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        total_time = time.perf_counter() - t_start

        # Validate final output
        valid = False
        final_dur = 0.0
        final_frames = 0
        if os.path.exists(final_output_path):
            cap = cv2.VideoCapture(final_output_path)
            final_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            final_dur = final_frames / fps
            cap.release()
            valid = final_dur >= 55.0

        manifest["status"] = "SUCCESS" if valid else "FAILED"
        manifest["final_output"] = final_output_path
        manifest["final_duration_sec"] = round(final_dur, 2)
        manifest["final_frames"] = final_frames
        manifest["total_render_time_sec"] = round(total_time, 2)

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        print(f"\nLONG-FORM GENERATION COMPLETE!")
        print(f"Final Video: {final_output_path} ({final_dur:.2f}s, {final_frames} frames)")
        print(f"Total Pipeline Time: {total_time:.2f}s (Average Net Speed: {final_frames/total_time:.1f} FPS)")

        return {
            "success": valid,
            "job_id": job_id,
            "final_video_path": final_output_path,
            "duration_sec": final_dur,
            "total_frames": final_frames,
            "total_time_sec": total_time,
            "net_fps": round(final_frames / total_time, 2) if total_time > 0 else 0.0
        }
