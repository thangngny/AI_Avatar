"""
AI Avatar NextGen V2 - Restoration Blend Strength Evaluation (Mission 06)
Compares GFPGAN blend strengths (30%, 50%, 70%) on 3s sample
to determine optimal trade-off between dental crispness and authentic skin texture.
"""
import os
import sys
import json
import shutil
import cv2
import torch
import numpy as np

REPO_ROOT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2"
sys.path.insert(0, os.path.join(REPO_ROOT, "avatars"))
from gfpgan_clean import GFPGANv1Clean

INPUT_VIDEO = os.path.join(REPO_ROOT, "reports", "mission03", "soulx_pro_3s.mp4")
OUT_DIR = os.path.join(REPO_ROOT, "reports", "mission06", "blend_eval")
os.makedirs(OUT_DIR, exist_ok=True)
HANDOVER_DIR = r"D:\CongThang_AI_Avatar\v2_renders\V6_FINAL_ACCEPTANCE"

GFPGAN_CKPT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\models\GFPGANv1.4.pth"


def load_gfpgan():
    model = GFPGANv1Clean(
        out_size=512,
        num_style_feat=512,
        channel_multiplier=2,
        decoder_load_path=None,
        fix_decoder=False,
        num_mlp=8,
        input_is_latent=True,
        different_w=True,
        narrow=1,
        sft_half=True
    )
    ckpt = torch.load(GFPGAN_CKPT, map_location="cpu")
    sd = ckpt.get("params_ema", ckpt.get("params", ckpt))
    model.load_state_dict(sd, strict=False)
    model.eval().to("cuda")
    return model


def evaluate_blends():
    cap = cv2.VideoCapture(INPUT_VIDEO)
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()

    gfp_model = load_gfpgan()
    gfp_frames = []

    batch_size = 8
    with torch.no_grad():
        for i in range(0, len(frames), batch_size):
            batch = frames[i:i + batch_size]
            t_batch = torch.stack([
                torch.from_numpy(f).permute(2, 0, 1).float() / 127.5 - 1.0
                for f in batch
            ]).to("cuda")
            out = gfp_model(t_batch, return_rgb=True)
            if isinstance(out, tuple):
                out = out[0]
            out_np = ((out.permute(0, 2, 3, 1).cpu().numpy() + 1.0) * 127.5).clip(0, 255).astype(np.uint8)
            for gfp_f in out_np:
                gfp_frames.append(gfp_f)

    ratios = [0.30, 0.50, 0.70]
    results = {}

    for alpha in ratios:
        name = f"blend_{int(alpha*100)}"
        blended_frames = []
        diffs = []
        prev = None

        for raw_f, gfp_f in zip(frames, gfp_frames):
            b = (alpha * gfp_f.astype(float) + (1.0 - alpha) * raw_f.astype(float)).clip(0, 255).astype(np.uint8)
            up = cv2.resize(b, (1024, 1024), interpolation=cv2.INTER_LANCZOS4)
            blended_frames.append(up)

            gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
            if prev is not None:
                diffs.append(np.mean(np.abs(gray.astype(float) - prev.astype(float))))
            prev = gray

        # Save sample frame 40 (mid-speech)
        sample_img = blended_frames[40]
        sample_path = os.path.join(OUT_DIR, f"{name}_frame40.png")
        cv2.imwrite(sample_path, sample_img)
        shutil.copy2(sample_path, os.path.join(HANDOVER_DIR, f"{name}_frame40.png"))

        # Save teeth close-up crop (around mouth: Y=600..850, X=360..664)
        mouth_crop = sample_img[600:850, 360:664]
        mouth_path = os.path.join(OUT_DIR, f"{name}_mouth_frame40.png")
        cv2.imwrite(mouth_path, mouth_crop)
        shutil.copy2(mouth_path, os.path.join(HANDOVER_DIR, f"{name}_mouth_frame40.png"))

        # Measure sharpness
        sharpnesses = [cv2.Laplacian(f, cv2.CV_64F).var() for f in blended_frames]

        results[name] = {
            "alpha_gfpgan": alpha,
            "alpha_native": round(1.0 - alpha, 2),
            "avg_sharpness": float(np.mean(sharpnesses)),
            "temporal_jitter_mean": float(np.mean(diffs)),
            "temporal_jitter_std": float(np.std(diffs)),
            "sample_image": sample_path,
            "mouth_crop": mouth_path
        }

    results_path = os.path.join(OUT_DIR, "blend_evaluation_metrics.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    shutil.copy2(results_path, os.path.join(HANDOVER_DIR, "blend_evaluation_metrics.json"))

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    evaluate_blends()
