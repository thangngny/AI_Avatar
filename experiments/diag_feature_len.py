# TEMPORARY diagnostic — NOT production. Tests H1: Whisper long-audio truncation.
import os, sys, subprocess, asyncio, tempfile
os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np, soundfile as sf, torch
import edge_tts

async def gen_tts(text, out_mp3):
    c = edge_tts.Communicate(text, "vi-VN-HoaiMyNeural")
    await c.save(out_mp3)

def main():
    text = open(os.path.join(os.path.dirname(__file__), "script_5min.txt"), encoding="utf-8").read()
    tmp = tempfile.mkdtemp()
    mp3 = os.path.join(tmp, "tts.mp3"); wav = os.path.join(tmp, "audio.wav")
    print("Generating EdgeTTS...")
    asyncio.get_event_loop().run_until_complete(gen_tts(text, mp3))
    subprocess.run(["ffmpeg","-y","-i",mp3,"-ar","16000","-ac","1","-af","apad=pad_len=1600",wav],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    w, sr = sf.read(wav, dtype="float32")
    if w.ndim > 1: w = w.mean(axis=1)
    dur = len(w)/sr
    print(f"WAV: samples={len(w)} sr={sr} duration={dur:.3f}s channels=mono")
    print(f"EXPECTED 50Hz features (full): {int(dur*50)}")
    print(f"EXPECTED video frames @25fps: {int(dur*25)}")
    print(f"SUSPICIOUS 30s-truncation feature count: 1500")

    from avatars.musetalk.whisper.audio2feature import Audio2Feature
    ap = Audio2Feature(model_path=os.path.join(os.path.dirname(__file__), "models", "whisper"),
                       device=torch.device("cuda:0"))
    print("feature_extractor:", type(ap.feature_extractor).__name__,
          "chunk_length=", getattr(ap.feature_extractor, "chunk_length", "?"),
          "n_samples=", getattr(ap.feature_extractor, "n_samples", "?"))
    feat = ap.audio2feat(w)
    print(f"ACTUAL feature shape: {feat.shape}")
    print(f"ACTUAL feature length (axis0): {feat.shape[0]}")
    # fingerprint: are late features identical (clamped)?
    L = feat.shape[0]
    f0 = feat[0].ravel()
    fmid = feat[L//2].ravel()
    flast = feat[L-1].ravel()
    def h(a): return hash(a.tobytes()) & 0xffffffff
    print(f"feat[0]      checksum={h(f0):08x} mean={f0.mean():.4f} std={f0.std():.4f}")
    print(f"feat[L/2={L//2}] checksum={h(fmid):08x} mean={fmid.mean():.4f} std={fmid.std():.4f}")
    print(f"feat[L-1={L-1}] checksum={h(flast):08x} mean={flast.mean():.4f} std={flast.std():.4f}")
    print(f"TRUNCATED? { 'YES ~30s' if 1400 <= L <= 1600 else 'no (full length)' }")

if __name__ == "__main__":
    main()