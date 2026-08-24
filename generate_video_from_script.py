#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline script -> lip-synced MP4 renderer (optimized for 2×RTX 3090).

Pipes a text script through EdgeTTS (free, vi-VN) -> Whisper features ->
MuseTalk UNet+VAE inference -> paste-back -> ffmpeg libx264, with:

  * batch_size 16 default (3090 24GB has headroom; offline has no 25fps budget).
  * cuDNN benchmark + TF32 + fp16-reduced-precision flags (the realtime server
    sets these in musetalk_avatar.load_model; the offline path used to omit them
    and ran on slow default conv algorithms).
  * CUDA Graph capture around the UNet+PE forward on single-GPU runs (fixed
    MuseTalk shapes -> eliminates per-launch overhead). Multi-GPU runs use
    DataParallel eager instead (graphs can't capture multi-GPU scatter/gather).
  * 2×3090 DataParallel for the UNet when 2+ GPUs are visible and
    OFFLINE_USE_MULTI_GPU!=false (default on for offline; PXB topology is fine
    here because there is no realtime audio-pacing constraint and bs16 amortizes
    the scatter/gather).
  * Full-HD output: avatar composite is capped at 1920px long-side
    (LIVETALKING_COMPOSITE_MAX_DIM, same knob as the realtime server) so a 4K
    avatar renders at 1080p without the paste-back+x264 cost that capped offline
    at ~15fps.
  * ffmpeg rawvideo -> libx264 ultrafast CRF16 pipe instead of cv2.VideoWriter
    (mp4v): ~5x faster encode and visibly sharper.
  * Optional GFPGAN face restoration (--face_enhance), safe offline because
    there is no 25fps A/V budget.

Bug fixed vs the previous version: `pred.cpu().numpy()` assumed decode_latents
returned a tensor, but it returns a uint8 BGR numpy array -> AttributeError on
every run. Now `pred` is used directly.
"""
import argparse, os, sys, re, subprocess, tempfile
import cv2, numpy as np, torch, pickle, glob, soundfile as sf
from tqdm import tqdm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from avatars.musetalk.utils.utils import load_all_model
from avatars.musetalk.myutil import get_image_blending
from avatars.musetalk.whisper.audio2feature import Audio2Feature
from utils.image import read_imgs, mirror_index
from utils.device import initialize_device
from utils.cuda_graph import GraphRunner

device = initialize_device()


def split_script(text, split_by='sentence'):
    text = text.strip()
    if not text: return []
    if split_by == 'line': return [l.strip() for l in text.splitlines() if l.strip()]
    if split_by == 'sentence':
        chunks = re.split(r'(?<=[.!?\u3000\uff01\uff1f])\s+', text)
        return [c.strip() for c in chunks if c.strip()]
    return [text.strip()]

def generate_audio_edge_tts(text, output_path, voice='vi-VN-HoaiMyNeural'):
    import edge_tts, asyncio
    async def _gen():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
    asyncio.get_event_loop().run_until_complete(_gen())

def convert_audio_to_wav(src_path, dst_path):
    subprocess.run(['ffmpeg','-y','-i',src_path,'-ar','16000','-ac','1','-af','apad=pad_len=1600',dst_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def _model_dtype(model_module):
    inner = model_module.module if isinstance(model_module, torch.nn.DataParallel) else model_module
    return inner.dtype if hasattr(inner, "dtype") else next(inner.parameters()).dtype


def setup_torch_flags():
    """One-time global flags: cuDNN benchmark + TF32 + fp16-reduced matmul.

    Identical to musetalk_avatar.load_model. The UNet/VAE conv input shape is
    constant across batches, so cuDNN benchmark picks the fastest algo and
    caches it. TF32/fp16-reduced let Ampere tensor cores use the faster path.
    Safe to call once at import; only changes algorithm selection, never when
    kernels execute."""
    torch.backends.cudnn.benchmark = True
    torch.backends.cudnn.deterministic = False
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cuda.matmul.allow_fp16_reduced_precision_reduction = True


def load_avatar_data(avatar_id):
    """Load avatar frames/masks/coords/latents, downscaling the composite to
    Full HD (1920 long-side) so paste-back + x264 stay fast. Mirrors the
    LIVETALKING_COMPOSITE_MAX_DIM logic in musetalk_avatar.load_avatar."""
    p = f'./data/avatars/{avatar_id}'
    input_latent_list_cycle = torch.load(f'{p}/latents.pt', map_location='cpu')
    with open(f'{p}/coords.pkl','rb') as f: coord_list_cycle = pickle.load(f)
    imgs = sorted(glob.glob(os.path.join(f'{p}/full_imgs','*.[jpJP][pnPN]*[gG]')),
                  key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))
    frame_list_cycle = read_imgs(imgs)
    with open(f'{p}/mask_coords.pkl','rb') as f: mask_coords_list_cycle = pickle.load(f)
    masks = sorted(glob.glob(os.path.join(f'{p}/mask','*.[jpJP][pnPN]*[gG]')),
                   key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))
    mask_list_cycle = read_imgs(masks)

    _max_dim = int(os.getenv("LIVETALKING_COMPOSITE_MAX_DIM", "1920"))
    if frame_list_cycle and mask_list_cycle and _max_dim > 0:
        _h0, _w0 = frame_list_cycle[0].shape[:2]
        _long = max(_h0, _w0)
        if _long > _max_dim:
            _scale = _max_dim / float(_long)
            _nw = max(2, int(round(_w0 * _scale)))
            _nh = max(2, int(round(_h0 * _scale)))
            print(f'[load_avatar] downscale composite {_w0}x{_h0} -> {_nw}x{_nh} '
                  f'(scale {_scale:.3f}, LIVETALKING_COMPOSITE_MAX_DIM={_max_dim})')
            frame_list_cycle = [cv2.resize(f, (_nw, _nh)) for f in frame_list_cycle]
            coord_list_cycle = [[int(round(float(v) * _scale)) for v in c] for c in coord_list_cycle]
            mask_coords_list_cycle = [[int(round(float(v) * _scale)) for v in c] for c in mask_coords_list_cycle]
            mask_list_cycle = [
                cv2.resize(m, (max(2, int(round(m.shape[1] * _scale))),
                               max(2, int(round(m.shape[0] * _scale)))))
                for m in mask_list_cycle
            ]
    return frame_list_cycle, mask_list_cycle, coord_list_cycle, mask_coords_list_cycle, input_latent_list_cycle


def _maybe_wrap_dataparallel(unet, model_dtype):
    """Offline-only: spread the UNet across all visible GPUs with DataParallel.
    PXB (PCIe, no NVLink) is acceptable offline because bs16 amortizes the
    scatter/gather and there is no realtime audio-pacing constraint. The VAE
    stays on the primary device (its output is small and decode is cheap
    relative to the UNet). Disabled when OFFLINE_USE_MULTI_GPU=false or only one
    GPU is visible. Returns (unet, used_multi_gpu)."""
    use_multi = os.getenv("OFFLINE_USE_MULTI_GPU", "true").strip().lower() not in ("0", "false", "no", "off")
    if not use_multi or torch.cuda.device_count() < 2:
        return unet, False
    device_ids = list(range(torch.cuda.device_count()))
    unet.device = device
    unet.model = unet.model.to(device)
    unet.model = torch.nn.DataParallel(unet.model, device_ids=device_ids, output_device=0)
    print(f'[multi-gpu] DataParallel UNet on GPUs {device_ids}')
    return unet, True


def _build_graph_runner(model, batch_size, model_dtype):
    """Capture a CUDA graph around pe+UNet for fixed shape (batch_size). Returns
    a GraphRunner (enabled=True) or a disabled one (caller falls back to eager).
    Only used on single-GPU runs; DataParallel is not graph-capturable."""
    vae, unet, pe, timesteps, audio_processor = model
    static_audio = torch.zeros((batch_size, 50, 384), device=device, dtype=model_dtype)
    static_latent = torch.zeros((batch_size, 8, 32, 32), device=device, dtype=model_dtype)
    static_ts = torch.zeros((batch_size,), device=device, dtype=torch.long)

    def _forward(audio_feat, latent):
        audio_emb = pe(audio_feat)
        return unet.model(latent, static_ts, encoder_hidden_states=audio_emb, return_dict=False)[0]

    runner = GraphRunner(device, _forward, warmup_iters=3)
    ok = runner.capture(
        {"audio_feat": static_audio, "latent": static_latent},
        label="offline_musetalk_unet",
    )
    return runner, ok


def render_video(audio_path, avatar_data, model, output_path, fps=25, batch_size=16, face_enhance=False, audio_feature_offset_frames=0, audio_context_left=0):
    vae, unet, pe, timesteps, audio_processor = model
    frame_list_cycle, mask_list_cycle, coord_list_cycle, mask_coords_list_cycle, input_latent_list_cycle = avatar_data
    wav_data, sr = sf.read(audio_path, dtype='float32')
    if wav_data.ndim > 1: wav_data = wav_data.mean(axis=1)
    if len(wav_data) == 0: raise ValueError('Audio file is empty')
    print('Extracting Whisper audio features...')
    whisper_feature = audio_processor.audio2feat(wav_data)
    audio_len_sec = len(wav_data) / sr
    num_frames = int(audio_len_sec * fps)
    print(f'Audio duration: {audio_len_sec:.2f}s = {num_frames} frames @ {fps}fps')

    # Strict feature-coverage validation (Stage 2, Phase 4/5).
    # The old single-call audio2feat truncated any audio > 30 s to 1500 features
    # and the renderer silently clamped out-of-range indices -> mouth froze past
    # 30 s. This assertion makes under-coverage a loud, early failure instead of
    # a silent render defect. Whisper features run at ~50 Hz; the last video
    # frame maps to feature index ~num_frames*2, so we need at least that many
    # features (plus the right-context window). Tolerance absorbs the ±1 rounding
    # at chunk boundaries and the +100 ms apad silence tail.
    FEATURE_HZ = 50.0
    actual_feats = int(whisper_feature.shape[0])
    # Need features up to the last frame's right-context edge:
    # center = (num_frames-1)*2, right = center + (2+2+1)*2 = center+10.
    required_feats = (num_frames - 1) * 2 + 10
    coverage_sec = actual_feats / FEATURE_HZ
    feat_tolerance = max(2, int(round(0.2 * FEATURE_HZ)))  # 200 ms tolerance
    if actual_feats < required_feats - feat_tolerance:
        raise RuntimeError(
            "Whisper feature coverage error:\n"
            f"  audio_duration   = {audio_len_sec:.3f}s\n"
            f"  actual_features  = {actual_feats}\n"
            f"  expected_features≈ {int(round(audio_len_sec * FEATURE_HZ))}\n"
            f"  required_for_frames = {required_feats}\n"
            f"  feature_coverage ≈ {coverage_sec:.3f}s\n"
            "  The feature array does not cover the full audio. This is the "
            "30-second truncation regression — audio2feat must chunk long audio."
        )
    print(f'Feature coverage OK: {actual_feats} features (~{coverage_sec:.2f}s) for '
          f'{num_frames} frames (required ~{required_feats})')
    # Stage 3 temporal offset: shift the audio-conditioning feature window in
    # time WITHOUT changing its shape (context size unchanged). The center feature
    # index for video frame i becomes (i + audio_feature_offset_frames) * (50/fps)
    # instead of i * (50/fps). Sign convention:
    #   +1 frame -> use audio features 40 ms LATER  (mouth anticipates / leads more)
    #   -1 frame -> use audio features 40 ms EARLIER (mouth lags more / leads less)
    # Default 0 = unchanged Stage 2 behavior. Does NOT touch the final audio track,
    # WAV, ffmpeg mux, video duration, or Whisper feature generation.
    if audio_feature_offset_frames:
        print(f'Audio feature offset: {audio_feature_offset_frames} frames '
              f'({audio_feature_offset_frames*1000/fps:+.0f} ms)  [center=(i+off)*{50/fps:.0f}]')
    # Stage 4 audio context: how many of the 10 conditioning features sit BEFORE
    # the aligned center. The offline path's get_sliced_feature uses a FUTURE-ONLY
    # window [center, center+10) (left=0). Realtime/official-style uses a roughly
    # symmetric [-4, +6) (left=4). audio_context_left shifts the 10-feature window
    # earlier without changing its length (MuseTalk conditioning stays [50,384],
    # pe/UNet shapes unchanged). Default 0 = unchanged Stage 3 behavior.
    #   left=0  -> relative [ 0, +10)  (current offline, future-only)
    #   left=4  -> relative [-4,  +6)  (realtime/official-style)
    #   left=5  -> relative [-5,  +5)  (symmetric)
    # NOTE: changing left shifts the window's effective center earlier, so the
    # Stage 3 offset must be re-calibrated per context (left+1 -> center earlier by
    # 20ms -> offset must increase ~0.5 frame to keep av_offset 0).
    AUDIO_CONTEXT_TOTAL = 10  # features (MuseTalk conditioning = 10 * 5 = 50 rows)
    if audio_context_left:
        print(f'Audio context: left={audio_context_left} total={AUDIO_CONTEXT_TOTAL} '
              f'window=[center-{audio_context_left}, center+{AUDIO_CONTEXT_TOTAL-audio_context_left})')
    h, w = frame_list_cycle[0].shape[:2]
    length = len(input_latent_list_cycle)
    model_dtype = _model_dtype(unet.model)
    n_feat = whisper_feature.shape[0]  # total Whisper features (full coverage)

    # Multi-GPU DataParallel (offline) OR single-GPU CUDA graph — mutually exclusive.
    unet, used_multi_gpu = _maybe_wrap_dataparallel(unet, model_dtype)
    graph_runner, graph_ok = (None, False)
    # CUDA graph only on single-GPU runs (DataParallel scatter/gather is not
    # graph-capturable). Default on; disable with LIVETALKING_CUDA_GRAPH=false.
    cuda_graph_wanted = os.getenv("LIVETALKING_CUDA_GRAPH", "true").strip().lower() not in ("0", "false", "no", "off")
    if not used_multi_gpu and cuda_graph_wanted:
        graph_runner, graph_ok = _build_graph_runner(model, batch_size, model_dtype)

    # Optional GFPGAN face restoration (offline = no 25fps budget, safe to enable).
    enhancer = None
    if face_enhance:
        os.environ.setdefault("LIVETALKING_FACE_ENHANCE", "true")
        from avatars import face_enhance as _fe
        if _fe.is_enabled():
            enhancer = _fe
            print('[face_enhance] GFPGAN enabled (offline, no fps budget)')

    print('Preparing audio features per frame...')
    all_whisper_chunks = []
    feat_mult = 50 // fps  # 2 feature positions per video frame
    for i in tqdm(range(num_frames), desc='Feature chunks'):
        # Stage 3+4: aligned center in feature units, then a 10-feature window with
        # `audio_context_left` features before it. Window SHAPE is always 10 features
        # -> [50,384] (identical to get_sliced_feature's contract); only WHICH 10
        # features (and thus the audio time window) changes. Out-of-range indices
        # clamp to [0, n_feat-1] (natural start/end padding, same as get_sliced_feature).
        center = (i + audio_feature_offset_frames) * feat_mult
        start_f = center - audio_context_left
        sel = np.stack([
            whisper_feature[max(0, min(n_feat - 1, idx))]
            for idx in range(start_f, start_f + AUDIO_CONTEXT_TOTAL)
        ], axis=0)  # [10, 5, 384]
        all_whisper_chunks.append(sel.reshape(-1, 384))  # [50, 384]

    # ffmpeg rawvideo -> libx264 ultrafast pipe (replaces cv2.VideoWriter mp4v).
    # mp4v is slow and soft; libx264 ultrafast is ~5x faster and sharper at CRF16.
    temp_video_path = output_path.replace('.mp4', '_temp.mp4')
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-an',
        '-f', 'rawvideo', '-vcodec', 'rawvideo', '-pix_fmt', 'bgr24',
        '-s', f'{w}x{h}', '-r', str(fps), '-i', '-',
        '-pix_fmt', 'yuv420p', '-vcodec', 'libx264',
        '-preset', os.getenv('LIVETALKING_OFFLINE_X264_PRESET', 'ultrafast'),
        '-crf', os.getenv('LIVETALKING_OFFLINE_CRF', '16'),
        '-movflags', '+faststart',
        temp_video_path,
    ]
    pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    import time as _time
    render_start = _time.perf_counter()
    frames_done = 0
    print(f'Rendering {num_frames} frames in batches of {batch_size} '
          f'(multi_gpu={used_multi_gpu}, cuda_graph={graph_ok})...')
    try:
        for i in tqdm(range(0, num_frames, batch_size), desc='Rendering'):
            actual_batch = min(batch_size, num_frames - i)
            whisper_batch = np.stack([all_whisper_chunks[i+j] for j in range(actual_batch)])
            latent_batch = torch.cat([input_latent_list_cycle[mirror_index(length, i+j)] for j in range(actual_batch)], dim=0)
            audio_feature_batch = torch.from_numpy(whisper_batch).to(device=device, dtype=model_dtype)
            latent_batch = latent_batch.to(device=device, dtype=model_dtype)

            # Full-size batch -> replay the captured graph (single-GPU path).
            # Partial last batch or multi-GPU / no-graph -> eager forward.
            if graph_ok and actual_batch == batch_size:
                pred_latents = graph_runner.replay(
                    {"audio_feat": audio_feature_batch, "latent": latent_batch}
                )
            else:
                audio_emb = pe(audio_feature_batch)
                ts = torch.zeros((actual_batch,), device=device, dtype=torch.long)
                with torch.no_grad():
                    pred_latents = unet.model(latent_batch, ts,
                                              encoder_hidden_states=audio_emb, return_dict=False)[0]

            # decode_latents returns uint8 BGR numpy [B,H,W,3] (vae.py).
            pred = vae.decode_latents(pred_latents)
            if enhancer is not None:
                pred = enhancer.enhance_faces(list(pred))
            for j in range(actual_batch):
                idx = mirror_index(length, i+j)
                bbox = coord_list_cycle[idx]
                x1, y1, x2, y2 = bbox
                if x2 < x1: x1, x2 = x2, x1
                if y2 < y1: y1, y2 = y2, y1
                ori_frame = frame_list_cycle[idx].copy()
                wj, hj = x2 - x1, y2 - y1
                if wj <= 0 or hj <= 0 or x1 < 0 or y1 < 0:
                    pipe.stdin.write(ori_frame.tobytes())
                    continue
                res_frame = cv2.resize(pred[j].astype(np.uint8), (wj, hj))
                combine_frame = get_image_blending(ori_frame, res_frame, (x1, y1, x2, y2),
                                                   mask_list_cycle[idx], mask_coords_list_cycle[idx])
                pipe.stdin.write(combine_frame.tobytes())
                frames_done += 1
    finally:
        try:
            pipe.stdin.close()
        except Exception:
            pass
        pipe.wait()

    elapsed = _time.perf_counter() - render_start
    print(f'Render done: {frames_done} frames in {elapsed:.1f}s = {frames_done/elapsed:.1f} fps')

    print('Muxing audio + video with ffmpeg...')
    subprocess.run(['ffmpeg','-y','-i',temp_video_path,'-i',audio_path,
                    '-c:v','libx264','-preset','ultrafast','-c:a','aac','-b:a','192k',
                    '-shortest','-movflags','+faststart',output_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(temp_video_path)
    print(f'Done: {output_path}')


def main():
    parser = argparse.ArgumentParser(description='LiveTalking Offline Script Video Generator (optimized)')
    parser.add_argument('--script', required=True)
    parser.add_argument('--avatar_id', required=True)
    parser.add_argument('--output', default=os.path.join('D:\\', 'CongThang_AI_Avatar', 'renders', 'output.mp4'))
    parser.add_argument('--fps', type=int, default=25)
    parser.add_argument('--voice', default='vi-VN-HoaiMyNeural')
    parser.add_argument('--batch_size', type=int, default=16)
    parser.add_argument('--split_by', choices=['line','sentence','all'], default='sentence')
    parser.add_argument('--face_enhance', action='store_true', help='Enable GFPGAN face restoration (needs models/GFPGANv1.4.pth)')
    parser.add_argument('--audio-feature-offset-frames', type=int, default=0,
                        help='Stage 3 temporal offset in VIDEO frames. +N = use audio '
                             'features N*40ms LATER (mouth anticipates/leads more); '
                             '-N = use audio N*40ms EARLIER (mouth lags more). '
                             'Default 0 = unchanged. Does not touch the final audio track.')
    parser.add_argument('--audio-context-left', type=int, default=0,
                        help='Stage 4 audio context: number of the 10 conditioning '
                             'features placed BEFORE the aligned center (0=future-only '
                             '[0,+10) current offline; 4=realtime/official [-4,+6); '
                             '5=symmetric [-5,+5)). Default 0 = unchanged Stage 3. '
                             'Total stays 10 -> MuseTalk conditioning [50,384] unchanged.')
    args = parser.parse_args()
    if not os.path.exists(args.script):
        print(f'Script file not found: {args.script}'); sys.exit(1)
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.script, 'r', encoding='utf-8') as f: raw_text = f.read()
    chunks = split_script(raw_text, args.split_by)
    if not chunks: print('Script is empty.'); sys.exit(1)
    full_text = ' '.join(chunks)
    print(f'Script: {len(chunks)} chunks, {len(full_text)} chars')
    print(f'Voice: {args.voice} | batch_size: {args.batch_size} | fps: {args.fps}')

    setup_torch_flags()

    with tempfile.TemporaryDirectory() as tmpdir:
        tts_path = os.path.join(tmpdir, 'tts.mp3')
        wav_path = os.path.join(tmpdir, 'audio.wav')
        print('Generating TTS audio (EdgeTTS, free)...')
        generate_audio_edge_tts(full_text, tts_path, voice=args.voice)
        print('Converting to WAV 16kHz mono...')
        convert_audio_to_wav(tts_path, wav_path)
        print('Loading MuseTalk model...')
        vae, unet, pe = load_all_model()
        pe = pe.half().to(device)
        vae.vae = vae.vae.half().to(device)
        unet.model = unet.model.half().to(device)
        audio_processor = Audio2Feature(model_path='./models/whisper')
        model = (vae, unet, pe, torch.tensor([0], device=device), audio_processor)
        print(f'Loading avatar: {args.avatar_id}')
        avatar_data = load_avatar_data(args.avatar_id)
        render_video(wav_path, avatar_data, model, args.output,
                     fps=args.fps, batch_size=args.batch_size, face_enhance=args.face_enhance,
                     audio_feature_offset_frames=args.audio_feature_offset_frames,
                     audio_context_left=args.audio_context_left)

if __name__ == '__main__':
    main()