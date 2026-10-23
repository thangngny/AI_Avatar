"""
AI Avatar NextGen V2 - Frame-Level Timeline Manifest Generator (Mission 06.1)
Builds exact sample-to-frame mapping across all 54 chunks of the 60-second master output.
"""
import os
import json

REPO_ROOT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2"
HANDOVER_DIR = r"D:\CongThang_AI_Avatar\v2_renders\V6_FINAL_ACCEPTANCE"
OUT_JSON = os.path.join(HANDOVER_DIR, "V6_1_TIMELINE_FRAME_MANIFEST.json")
DOCS_OUT = os.path.join(REPO_ROOT, "docs", "V6_1_TIMELINE_FRAME_MANIFEST.json")


def generate_timeline_manifest():
    audio_sr = 16000
    video_fps = 25.0
    audio_total_sec = 60.000000
    total_audio_samples = int(audio_sr * audio_total_sec) # 960,000
    frames_per_chunk = 28
    samples_per_chunk = int(frames_per_chunk * audio_sr / video_fps) # 17,920
    motion_context_frames = 5
    raw_frames_per_chunk = 33

    chunks_manifest = []
    accum_frames = 0
    accum_samples = 0

    total_chunks = (total_audio_samples + samples_per_chunk - 1) // samples_per_chunk # 54

    for c_idx in range(total_chunks):
        c_sample_start = accum_samples
        c_sample_target_end = min(accum_samples + samples_per_chunk, total_audio_samples)
        real_samples = c_sample_target_end - c_sample_start
        pad_samples = samples_per_chunk - real_samples

        real_frames = int(round(real_samples * video_fps / audio_sr))
        pad_frames = frames_per_chunk - real_frames

        c_frame_start = accum_frames
        c_frame_end = c_frame_start + real_frames

        chunks_manifest.append({
            "chunk_id": c_idx,
            "time_start_sec": round(c_sample_start / audio_sr, 4),
            "time_end_sec": round(c_sample_target_end / audio_sr, 4),
            "audio_sample_start": c_sample_start,
            "audio_sample_end": c_sample_target_end,
            "audio_real_samples": real_samples,
            "audio_pad_samples": pad_samples,
            "raw_latent_frames_generated": raw_frames_per_chunk,
            "context_overlap_frames_trimmed": motion_context_frames,
            "unique_frames_generated": frames_per_chunk,
            "speech_aligned_frames_retained": real_frames,
            "padded_silence_frames_excluded": pad_frames,
            "timeline_frame_start": c_frame_start,
            "timeline_frame_end": c_frame_end - 1
        })

        accum_samples = c_sample_target_end
        accum_frames += real_frames

    manifest = {
        "master_audio": {
            "path": "assets/master_60s_vietnamese.wav",
            "sample_rate": audio_sr,
            "total_duration_sec": audio_total_sec,
            "total_samples": total_audio_samples
        },
        "video_timeline": {
            "target_fps": video_fps,
            "total_frames_target": int(audio_total_sec * video_fps), # 1500
            "total_chunks_computed": total_chunks, # 54
            "total_unique_frames_generated": total_chunks * frames_per_chunk, # 1512
            "total_speech_frames_retained": accum_frames, # 1500
            "total_padded_frames_excluded": (total_chunks * frames_per_chunk) - accum_frames, # 12
            "exclusion_reason": "Trailing silence padding added to satisfy chunk audio window (17,920 samples). Truncation discards zero speech phonemes."
        },
        "chunks": chunks_manifest
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    with open(DOCS_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Timeline Frame Manifest generated successfully: {OUT_JSON}")


if __name__ == "__main__":
    generate_timeline_manifest()
