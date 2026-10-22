"""
AI Avatar NextGen V2 - Quality Video Generator (SoulX Pro + GFPGAN 50/50 + NVENC)
Tier 2 'QUALITY' Engine Backend Adapter for AI Avatar Studio V2.
"""
import os
import sys
import time
import subprocess
import cv2
import torch
import numpy as np

REPO_ROOT = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2"
PYTHON_BIN = r"C:\Users\phuongpn\runtime_avatar_v2\Scripts\python.exe"
SOULX_ENG_DIR = os.path.join(REPO_ROOT, "engines", "soulx_flashhead")
WEIGHTS_DIR = os.path.join(REPO_ROOT, "weights", "SoulX-FlashHead-1_3B")
WAV2VEC_DIR = os.path.join(REPO_ROOT, "weights", "wav2vec2-base-960h")
GFPGAN_CKPT = r"C:\Users\phuongpn\AI_Avatar\models\GFPGANv1.4.pth"

sys.path.insert(0, os.path.join(REPO_ROOT, "avatars"))
try:
    from gfpgan_clean import GFPGANv1Clean
except ImportError:
    GFPGANv1Clean = None


class QualityVideoGenerator:
    def __init__(self, output_root: str = r"D:\CongThang_AI_Avatar\v2_renders"):
        self.output_root = output_root
        os.makedirs(output_root, exist_ok=True)
        self.gfp_model = None

    def _get_cond_image(self, avatar_id: str) -> str:
        avatar_dir = os.path.join(REPO_ROOT, "data", "avatars", avatar_id)
        p512 = os.path.join(avatar_dir, "portrait_512.png")
        if os.path.exists(p512):
            return p512

        # Fallback to first full image resized to 512x512
        full_imgs = os.path.join(avatar_dir, "full_imgs")
        if os.path.exists(full_imgs):
            imgs = sorted([f for f in os.listdir(full_imgs) if f.endswith(".png") or f.endswith(".jpg")])
            if imgs:
                src_path = os.path.join(full_imgs, imgs[0])
                img = cv2.imread(src_path)
                if img is not None:
                    h, w = img.shape[:2]
                    crop_size = min(h, w)
                    top = 0
                    left = (w - crop_size) // 2
                    cropped = img[top:top + crop_size, left:left + crop_size]
                    resized = cv2.resize(cropped, (512, 512), interpolation=cv2.INTER_AREA)
                    cv2.imwrite(p512, resized)
                    return p512

        # Ultimate fallback to default doTrang portrait
        return os.path.join(REPO_ROOT, "data", "avatars", "doTrang_closeup", "portrait_512.png")

    def _load_gfpgan(self):
        if self.gfp_model is not None:
            return self.gfp_model
        if GFPGANv1Clean is None:
            return None
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
        if os.path.exists(GFPGAN_CKPT):
            ckpt = torch.load(GFPGAN_CKPT, map_location="cpu")
            sd = ckpt.get("params_ema", ckpt.get("params", ckpt))
            model.load_state_dict(sd, strict=False)
            model.eval().to("cuda")
            self.gfp_model = model
        return self.gfp_model

    def render_quality_video(self, job_id: str, avatar_id: str, master_audio_path: str,
                             final_output_path: str, make_vertical: bool = False,
                             progress_callback=None) -> dict:
        t_start = time.perf_counter()
        tmp_native = os.path.join(self.output_root, f"{job_id}_native_tmp.mp4")
        cond_image = self._get_cond_image(avatar_id)

        # Stage 1: SoulX DiT Neural Generation
        cmd_soulx = [
            PYTHON_BIN,
            os.path.join(SOULX_ENG_DIR, "generate_video.py"),
            "--ckpt_dir", WEIGHTS_DIR,
            "--wav2vec_dir", WAV2VEC_DIR,
            "--model_type", "pro",
            "--cond_image", cond_image,
            "--audio_path", master_audio_path,
            "--audio_encode_mode", "stream",
            "--save_file", tmp_native
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = SOULX_ENG_DIR + os.pathsep + env.get("PYTHONPATH", "")

        proc = subprocess.run(cmd_soulx, cwd=SOULX_ENG_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if proc.returncode != 0 or not os.path.exists(tmp_native):
            return {"success": False, "error": f"SoulX inference failed: {proc.stdout[-500:] if proc.stdout else 'Unknown'}"}

        if progress_callback:
            progress_callback(0.70)

        # Stage 2: GFPGAN 50/50 + Lanczos 1024 Master Enhancement
        gfp_model = self._load_gfpgan()
        cap = cv2.VideoCapture(tmp_native)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        tmp_enhanced = final_output_path if not make_vertical else os.path.join(self.output_root, f"{job_id}_enh_tmp.mp4")

        cmd_nvenc = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", "1024x1024", "-pix_fmt", "bgr24", "-r", str(fps),
            "-i", "-",
            "-i", master_audio_path,
            "-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq",
            "-rc", "vbr", "-cq", "16", "-b:v", "0",
            "-spatial-aq", "1", "-temporal-aq", "1", "-multipass", "fullres",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", tmp_enhanced
        ]

        pipe_proc = subprocess.Popen(cmd_nvenc, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        batch_size = 8
        frame_buffer = []

        def process_batch(batch):
            if gfp_model is not None:
                with torch.no_grad():
                    t_batch = torch.stack([
                        torch.from_numpy(f).permute(2, 0, 1).float() / 127.5 - 1.0
                        for f in batch
                    ]).to("cuda")
                    out = gfp_model(t_batch, return_rgb=True)
                    if isinstance(out, tuple):
                        out = out[0]
                    out_np = ((out.permute(0, 2, 3, 1).cpu().numpy() + 1.0) * 127.5).clip(0, 255).astype(np.uint8)

                    for raw_f, gfp_f in zip(batch, out_np):
                        blended = (0.50 * gfp_f.astype(float) + 0.50 * raw_f.astype(float)).clip(0, 255).astype(np.uint8)
                        up = cv2.resize(blended, (1024, 1024), interpolation=cv2.INTER_LANCZOS4)
                        pipe_proc.stdin.write(up.tobytes())
            else:
                for raw_f in batch:
                    up = cv2.resize(raw_f, (1024, 1024), interpolation=cv2.INTER_LANCZOS4)
                    pipe_proc.stdin.write(up.tobytes())

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_buffer.append(frame)
            if len(frame_buffer) == batch_size:
                process_batch(frame_buffer)
                frame_buffer = []

        if frame_buffer:
            process_batch(frame_buffer)

        cap.release()
        pipe_proc.stdin.close()
        pipe_proc.wait()

        if os.path.exists(tmp_native):
            try:
                os.remove(tmp_native)
            except Exception:
                pass

        # Stage 3: If vertical requested, run Strategy B
        if make_vertical:
            if progress_callback:
                progress_callback(0.90)
            filter_b = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5,colorchannelmixer=aa=0.8:rr=0.6:gg=0.6:bb=0.6[bg];"
                "[0:v]scale=1080:1080[fg];"
                "[bg][fg]overlay=x=0:y=420[v]"
            )
            cmd_vert = [
                "ffmpeg", "-y", "-i", tmp_enhanced,
                "-filter_complex", filter_b,
                "-map", "[v]", "-map", "0:a",
                "-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq",
                "-rc", "vbr", "-cq", "16", "-b:v", "0",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-shortest", final_output_path
            ]
            subprocess.run(cmd_vert, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(tmp_enhanced):
                try:
                    os.remove(tmp_enhanced)
                except Exception:
                    pass

        t_end = time.perf_counter()
        dur = total_frames / fps if fps > 0 else 0.0

        return {
            "success": True,
            "engine": "QUALITY (SoulX-FlashHead Pro 1.3B + GFPGAN 50/50)",
            "output_path": final_output_path,
            "duration_sec": round(dur, 2),
            "wall_clock_sec": round(t_end - t_start, 2),
            "net_fps": round(total_frames / (t_end - t_start), 1) if (t_end - t_start) > 0 else 0.0,
            "total_frames": total_frames
        }
