import os
import sys
import json
import cv2
import numpy as np


def evaluate_video(path: str, max_frames: int = 200):
    if not os.path.isfile(path):
        return None
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    full_sharpness_list = []
    mouth_sharpness_list = []
    ghosting_scores = []

    # Exact anatomical lower face / mouth region for doTrang_closeup (1080x1920)
    my1, my2 = 335, 560
    mx1, mx2 = 450, 630

    count = 0
    while cap.isOpened() and count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mouth_gray = gray[my1:my2, mx1:mx2]

        full_sharp = cv2.Laplacian(gray, cv2.CV_64F).var()
        mouth_sharp = cv2.Laplacian(mouth_gray, cv2.CV_64F).var()

        full_sharpness_list.append(full_sharp)
        mouth_sharpness_list.append(mouth_sharp)

        # Ghosting detection: ratio of blurred edge gradients to sharp edges
        sobel_x = cv2.Sobel(mouth_gray, cv2.CV_32F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(mouth_gray, cv2.CV_32F, 0, 1, ksize=3)
        grad_mag = np.sqrt(sobel_x**2 + sobel_y**2)
        crisp_edges = np.count_nonzero(grad_mag > 45)
        muddy_edges = np.count_nonzero((grad_mag >= 10) & (grad_mag <= 25))
        ghost_ratio = muddy_edges / max(crisp_edges, 1)
        ghosting_scores.append(ghost_ratio)
        count += 1

    cap.release()

    return {
        "file": os.path.basename(path),
        "fps": fps,
        "frames_evaluated": count,
        "total_frames": total_frames,
        "resolution": f"{w}x{h}",
        "full_sharpness": round(float(np.mean(full_sharpness_list)), 1),
        "mouth_sharpness": round(float(np.mean(mouth_sharpness_list)), 1),
        "ghosting_index": round(float(np.mean(ghosting_scores)), 2),
        "filesize_mb": round(os.path.getsize(path) / (1024 * 1024), 1)
    }


def main():
    renders_dir = r"D:\CongThang_AI_Avatar\renders"
    targets = [
        ("demo_expressive_living_avatar_25fps.mp4", "25 FPS Baseline (Bilinear Resampling)"),
        ("demo_sota_crystal_sharp_25fps.mp4",       "25 FPS SOTA (Lanczos-4 + Edge-Preserving)"),
        ("demo_expressive_living_avatar_60fps.mp4", "60 FPS Baseline (FFmpeg framerate blend)"),
        ("demo_crystal_clean_60fps.mp4",          "60 FPS SOTA Crystal-Clean (Zero Noise NVENC P7)")
    ]

    print("=" * 80)
    print("NEXTGEN AI AVATAR -- AUTOMATED OBJECTIVE QUALITY BENCHMARK")
    print("=" * 80)

    results = []
    for fname, label in targets:
        fpath = os.path.join(renders_dir, fname)
        res = evaluate_video(fpath)
        if res:
            res["label"] = label
            results.append(res)

    print(f"{'Video Edition':<46} | {'FPS':<5} | {'Mouth Sharp':<12} | {'Ghosting':<10} | {'Size MB'}")
    print("-" * 80)
    for r in results:
        print(f"{r['label']:<46} | {r['fps']:<5.0f} | {r['mouth_sharpness']:<12.1f} | {r['ghosting_index']:<10.2f} | {r['filesize_mb']} MB")
    print("=" * 80)

    if len(results) >= 4:
        r25_old, r25_new = results[0], results[1]
        r60_old, r60_new = results[2], results[3]

        m25_boost = (r25_new['mouth_sharpness'] / r25_old['mouth_sharpness'] - 1) * 100
        g60_cut = (1 - r60_new['ghosting_index'] / r60_old['ghosting_index']) * 100
        m60_boost = (r60_new['mouth_sharpness'] / r60_old['mouth_sharpness'] - 1) * 100

        print(f"\n[SOTA UPGRADE SUMMARY]:")
        print(f"1. Mouth Sharpness Boost (25 FPS): +{m25_boost:.1f}% ({r25_old['mouth_sharpness']} -> {r25_new['mouth_sharpness']})")
        print(f"2. Mouth Sharpness Boost (60 FPS): +{m60_boost:.1f}% ({r60_old['mouth_sharpness']} -> {r60_new['mouth_sharpness']})")
        print(f"3. Ghosting / Motion Blur Reduction (60 FPS): -{g60_cut:.1f}% ({r60_old['ghosting_index']} -> {r60_new['ghosting_index']})")
        print("=" * 80)

    # Save to JSON report
    out_json = os.path.join(renders_dir, "sota_quality_benchmark_report.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved benchmark report to: {out_json}")


if __name__ == "__main__":
    main()
