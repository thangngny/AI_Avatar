#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 5 — thin render driver that reuses the PRODUCTION render_video with a
pre-made byte-identical master WAV (so A/B/C candidates differ only by the
articulation variable, never by TTS audio). Loads model + avatar once.

Articulation is controlled entirely by environment variables read inside the
production pipeline (myutil.get_image_blending) — this driver passes NO
articulation argument; it just calls render_video with the stable timing
params (audio_feature_offset_frames=-3, audio_context_left=0). When the
articulation env vars are unset/zero, behaviour is bit-identical to the
ai-avatar-lipsync-v1-stable checkpoint.

Usage:
  set CUDA_VISIBLE_DEVICES=1
  latentsync_env\\Scripts\\python.exe stage5_render.py \
    --audio D:\\CongThang_AI_Avatar\\stage5\\master_continuous.wav \
    --avatar_id fullbody_30_7_25fps \
    --output D:\\CongThang_AI_Avatar\\stage5\\stage5_baseline_continuous.mp4
"""
import argparse, os, sys, torch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")
from generate_video_from_script import (setup_torch_flags, load_all_model,
                                         load_avatar_data, render_video)
from avatars.musetalk.whisper.audio2feature import Audio2Feature
from utils.device import initialize_device

device = initialize_device()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audio', required=True)
    ap.add_argument('--avatar_id', default='fullbody_30_7_25fps')
    ap.add_argument('--output', required=True)
    ap.add_argument('--fps', type=int, default=25)
    ap.add_argument('--batch_size', type=int, default=16)
    ap.add_argument('--offset', type=int, default=-3, help='audio_feature_offset_frames')
    ap.add_argument('--ctx-left', type=int, default=0, help='audio_context_left')
    ap.add_argument('--audio-gain', type=float, default=1.0,
                    help='Stage 5 articulation conditioning gain (1.0 = stable)')
    args = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    setup_torch_flags()
    print('[stage5] loading model...')
    vae, unet, pe = load_all_model()
    pe = pe.half().to(device)
    vae.vae = vae.vae.half().to(device)
    unet.model = unet.model.half().to(device)
    audio_processor = Audio2Feature(model_path='./models/whisper')
    model = (vae, unet, pe, torch.tensor([0], device=device), audio_processor)
    print(f'[stage5] loading avatar {args.avatar_id}...')
    avatar_data = load_avatar_data(args.avatar_id)
    print(f'[stage5] rendering -> {args.output}')
    render_video(args.audio, avatar_data, model, args.output,
                 fps=args.fps, batch_size=args.batch_size,
                 audio_feature_offset_frames=args.offset,
                 audio_context_left=args.ctx_left,
                 audio_conditioning_gain=args.audio_gain)
    print('[stage5] done.')


if __name__ == '__main__':
    main()