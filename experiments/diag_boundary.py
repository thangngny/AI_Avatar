# TEMPORARY diagnostic — NOT production. Chunk-boundary discontinuity check.
# Computes the per-step feature difference around the 30s/60s chunk boundaries
# (feature index 1500, 3000) and compares to the average step. A boundary step
# much larger than the median step indicates a segmentation artifact.
import os, sys, subprocess, tempfile, asyncio
os.environ.setdefault("CUDA_VISIBLE_DEVICES","1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, soundfile as sf, torch

async def gen_tts(text, mp3):
    import edge_tts
    await edge_tts.Communicate(text,"vi-VN-HoaiMyNeural").save(mp3)

root = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
mp3 = os.path.join(tmp,"t.mp3"); wav = os.path.join(tmp,"a.wav")
asyncio.get_event_loop().run_until_complete(gen_tts(open(os.path.join(root,"script_5min.txt"),encoding="utf-8").read(), mp3))
subprocess.run(["ffmpeg","-y","-i",mp3,"-ar","16000","-ac","1","-af","apad=pad_len=1600",wav],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
w,sr = sf.read(wav,dtype="float32"); w = w.mean(axis=1) if w.ndim>1 else w

from avatars.musetalk.whisper.audio2feature import Audio2Feature
ap = Audio2Feature(model_path=os.path.join(root,"models","whisper"), device=torch.device("cuda:0"))
feat = ap.audio2feat(w)  # [T,5,384]
T = feat.shape[0]
print(f"feature shape {feat.shape}, T={T}")

# per-step L2 distance between consecutive features (flattened)
flat = feat.reshape(T, -1).astype(np.float64)
steps = np.linalg.norm(np.diff(flat, axis=0), axis=1)  # length T-1
med = float(np.median(steps)); mean = float(np.mean(steps)); p95 = float(np.percentile(steps,95))
print(f"step stats: median={med:.3f} mean={mean:.3f} p95={p95:.3f} max={steps.max():.3f}")

def step_at(feature_index):
    if 0 <= feature_index < len(steps):
        return float(steps[feature_index])
    return None

print("\nBoundary steps (30s=index1500, 60s=index3000, 90s=4500, 120s=6000, 150s=7500):")
for boundary_feat in [1500, 3000, 4500, 6000, 7500]:
    # the step BETWEEN feature[boundary-1] and feature[boundary] is steps[boundary-1]
    s = step_at(boundary_feat-1)
    neigh = [step_at(boundary_feat-2), step_at(boundary_feat-1), step_at(boundary_feat), step_at(boundary_feat+1)]
    ratio = (s/med) if (s and med) else 0
    flag = " <-- BOUNDARY JUMP" if s and s > max(p95, med*4) else ""
    print(f"  feat idx {boundary_feat:5d} (~{boundary_feat/50:.1f}s): step={s:.3f} (x{ratio:.2f} median){flag}")

# also check the mouth-side: feature value mean around boundary
print("\nFeature mean around 30s boundary (idx 1498..1502):")
for i in [1498,1499,1500,1501,1502]:
    if i < T: print(f"  feat[{i}] mean={float(feat[i].mean()):.4f} std={float(feat[i].std()):.4f} norm={float(np.linalg.norm(feat[i])):.3f}")