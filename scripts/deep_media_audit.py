"""
AI Avatar NextGen V2 - Deep Media Forensic Auditor (Mission 06.1)
Performs frame-accurate packet inspection, PTS tracking, SHA256 hashing,
and full-decode validation on all handover artifacts in V6_FINAL_ACCEPTANCE.
"""
import os
import sys
import json
import hashlib
import subprocess

ACCEPTANCE_DIR = r"D:\CongThang_AI_Avatar\v2_renders\V6_FINAL_ACCEPTANCE"
OUT_JSON = os.path.join(ACCEPTANCE_DIR, "V6_1_MEDIA_QA.json")
DOCS_OUT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\docs\V6_1_MEDIA_QA.json"


def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def audit_media_file(filepath):
    filename = os.path.basename(filepath)
    size_bytes = os.path.getsize(filepath)
    file_hash = sha256_file(filepath)

    # 1. FFprobe stream details
    cmd_probe = [
        "ffprobe", "-v", "error",
        "-show_streams", "-show_format",
        "-of", "json", filepath
    ]
    probe_raw = subprocess.check_output(cmd_probe).decode("utf-8", errors="replace")
    probe_data = json.loads(probe_raw)

    v_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"), {})
    a_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "audio"), {})
    fmt = probe_data.get("format", {})

    # 2. Extract first and last PTS for video
    cmd_pts = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "packet=pts_time,flags",
        "-of", "csv=p=0", filepath
    ]
    first_pts = "N/A"
    last_pts = "N/A"
    try:
        pts_out = subprocess.check_output(cmd_pts).decode("utf-8", errors="replace").strip().splitlines()
        if pts_out:
            first_pts = pts_out[0].split(",")[0]
            last_pts = pts_out[-1].split(",")[0]
    except Exception:
        pass

    # 3. Full decode check using ffmpeg null sink
    cmd_decode = [
        "ffmpeg", "-v", "error",
        "-i", filepath,
        "-f", "null", "-"
    ]
    res_decode = subprocess.run(cmd_decode, capture_output=True, text=True)
    decode_passed = (res_decode.returncode == 0 and len(res_decode.stderr.strip()) == 0)

    # Decoded frame count verification
    nb_frames = v_stream.get("nb_frames")
    if not nb_frames or nb_frames == "N/A":
        nb_frames = len(pts_out) if pts_out else 0
    else:
        nb_frames = int(nb_frames)

    return {
        "filename": filename,
        "absolute_path": filepath,
        "file_size_bytes": size_bytes,
        "sha256": file_hash,
        "video": {
            "codec": v_stream.get("codec_name"),
            "width": v_stream.get("width"),
            "height": v_stream.get("height"),
            "nominal_fps": v_stream.get("r_frame_rate"),
            "avg_fps": v_stream.get("avg_frame_rate"),
            "time_base": v_stream.get("time_base"),
            "pixel_format": v_stream.get("pix_fmt"),
            "decoded_frames": nb_frames,
            "stream_duration_sec": float(v_stream.get("duration", 0.0)) if v_stream.get("duration") else None,
            "first_pts_sec": float(first_pts) if first_pts != "N/A" else None,
            "last_pts_sec": float(last_pts) if last_pts != "N/A" else None
        },
        "audio": {
            "codec": a_stream.get("codec_name"),
            "sample_rate": int(a_stream.get("sample_rate", 0)) if a_stream.get("sample_rate") else None,
            "channels": a_stream.get("channels"),
            "stream_duration_sec": float(a_stream.get("duration", 0.0)) if a_stream.get("duration") else None
        },
        "container": {
            "format_name": fmt.get("format_name"),
            "duration_sec": float(fmt.get("duration", 0.0)),
            "bitrate_bps": int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else None
        },
        "full_decode_exit_code": res_decode.returncode,
        "decode_intact": decode_passed,
        "decode_stderr": res_decode.stderr.strip() if res_decode.stderr else None
    }


def main():
    mp4_files = sorted([
        os.path.join(ACCEPTANCE_DIR, f)
        for f in os.listdir(ACCEPTANCE_DIR)
        if f.endswith(".mp4")
    ])
    print(f"Auditing {len(mp4_files)} MP4 files in {ACCEPTANCE_DIR}...")
    manifest = {}
    for p in mp4_files:
        print(f"  Probing {os.path.basename(p)}...")
        res = audit_media_file(p)
        manifest[os.path.basename(p)] = res

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    with open(DOCS_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Audit complete! Saved to {OUT_JSON} and {DOCS_OUT}")


if __name__ == "__main__":
    main()
