"""
AI Avatar NextGen V2 - Automated Quality Control (QC) Gate
Performs deep frame-level integrity, audio-video sync, and visual seam verification.
"""
import os
import sys
import json
import cv2
import soundfile as sf
import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


class QualityControlGate:
    def __init__(self, fps_tolerance: float = 0.5, duration_tolerance_sec: float = 0.5):
        self.fps_tolerance = fps_tolerance
        self.duration_tolerance_sec = duration_tolerance_sec

    def verify_video(self, video_path: str, reference_audio_path: str) -> dict:
        """
        Executes multi-stage validation checks on a rendered video.
        """
        if not os.path.exists(video_path):
            return {"passed": False, "error": f"Video file not found: {video_path}"}
        if not os.path.exists(reference_audio_path):
            return {"passed": False, "error": f"Reference audio not found: {reference_audio_path}"}

        checks = {}

        # 1. Media Container & Codec Check
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"passed": False, "error": "Video container is corrupted or undecodable"}

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        video_dur = total_frames / fps if fps > 0 else 0.0

        checks["resolution_valid"] = (width == 1080 and height == 1920) or (width >= 720 and height >= 720)
        checks["fps_valid"] = abs(fps - 25.0) < self.fps_tolerance or abs(fps - 60.0) < self.fps_tolerance

        # 2. Audio Duration Alignment Check
        audio_info = sf.info(reference_audio_path)
        audio_dur = audio_info.duration
        dur_diff = abs(video_dur - audio_dur)
        checks["duration_matched"] = dur_diff <= self.duration_tolerance_sec

        # 3. Visual Artifact & Boundary Seam Analysis
        prev_frame_gray = None
        jitter_diffs = []
        sampled_frames = 0
        corrupted_frames = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame is None or frame.size == 0:
                corrupted_frames += 1
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev_frame_gray is not None and sampled_frames < 300:
                diff = np.mean(np.abs(gray.astype(np.float32) - prev_frame_gray.astype(np.float32)))
                jitter_diffs.append(diff)
            prev_frame_gray = gray
            sampled_frames += 1

        cap.release()

        checks["zero_corrupted_frames"] = (corrupted_frames == 0)
        checks["frame_continuity"] = (sampled_frames == total_frames)

        avg_jitter = float(np.mean(jitter_diffs)) if jitter_diffs else 0.0
        checks["temporal_stability_acceptable"] = avg_jitter < 2.5 # lower is better

        all_passed = all(checks.values())

        return {
            "passed": all_passed,
            "video_path": video_path,
            "metrics": {
                "width": width,
                "height": height,
                "fps": fps,
                "total_frames": total_frames,
                "video_duration_sec": round(video_dur, 2),
                "audio_duration_sec": round(audio_dur, 2),
                "duration_delta_sec": round(dur_diff, 3),
                "temporal_jitter_score": round(avg_jitter, 3),
                "corrupted_frames": corrupted_frames
            },
            "checks": checks
        }


if __name__ == "__main__":
    if len(sys.argv) > 2:
        qc = QualityControlGate()
        res = qc.verify_video(sys.argv[1], sys.argv[2])
        print(json.dumps(res, indent=2))
