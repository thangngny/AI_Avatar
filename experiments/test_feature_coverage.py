# TEMPORARY regression test — NOT production. Verifies long-audio feature coverage.
# Run: python test_feature_coverage.py
# Generates synthetic sine wavs of exact durations + real TTS for 55s/167.6s,
# runs audio2feat, asserts feature count covers the full duration (>1500 for >30s).
import os, sys, asyncio, subprocess, tempfile
os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, soundfile as sf, torch

SR = 16000
def sine_wav(seconds, path):
    t = np.linspace(0, seconds, int(SR*seconds), endpoint=False, dtype=np.float32)
    # mix of tones so features are non-trivial
    x = 0.3*np.sin(2*np.pi*220*t) + 0.2*np.sin(2*np.pi*440*t) + 0.1*np.sin(2*np.pi*880*t)
    sf.write(path, x, SR, subtype='FLOAT')

async def gen_tts(text, out_mp3):
    import edge_tts
    await edge_tts.Communicate(text, "vi-VN-HoaiMyNeural").save(out_mp3)

def tts_wav(text, wav_path):
    tmp = tempfile.mkdtemp()
    mp3 = os.path.join(tmp, "t.mp3")
    asyncio.get_event_loop().run_until_complete(gen_tts(text, mp3))
    subprocess.run(["ffmpeg","-y","-i",mp3,"-ar",str(SR),"-ac","1","-af","apad=pad_len=1600",wav_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def expected_feats(seconds):
    return int(round(seconds * 50))

from avatars.musetalk.whisper.audio2feature import Audio2Feature
ap = Audio2Feature(model_path=os.path.join(os.path.dirname(__file__), "models", "whisper"),
                   device=torch.device("cuda:0"))

root = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp()
results = []

def check(label, seconds, wav_path, expect_fn=None):
    w, sr = sf.read(wav_path, dtype="float32")
    if w.ndim > 1: w = w.mean(axis=1)
    dur = len(w)/sr
    feat = ap.audio2feat(w)
    n = feat.shape[0]
    exp = expect_fn(dur) if expect_fn else expected_feats(dur)
    # pass criteria: covers full duration (not stuck at 1500 for >30s)
    covers = n >= int(dur*50) - 3
    not_truncated = (dur <= 30.5) or (n > 1500)
    ok = covers and not_truncated
    results.append((label, dur, n, exp, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {label:12s} dur={dur:7.3f}s feats={n:6d} exp~{exp:6d} covers={covers} not_truncated={not_truncated}")
    return ok

# exact-duration synthetic sines
for sec in [10, 29, 30, 31]:
    p = os.path.join(tmp, f"sine_{sec}.wav"); sine_wav(sec, p)
    check(f"synth {sec}s", sec, p)

# real TTS 55s and 167.6s
p55 = os.path.join(tmp, "tts_55.wav"); tts_wav(open(os.path.join(root,"script_50s.txt"),encoding="utf-8").read(), p55)
check("tts 55s", 55, p55)
p167 = os.path.join(tmp, "tts_167.wav"); tts_wav(open(os.path.join(root,"script_5min.txt"),encoding="utf-8").read(), p167)
check("tts 167s", 167, p167)

print("\n=== summary ===")
allok = all(r[4] for r in results)
for label,dur,n,exp,ok in results:
    print(f"  {label:12s} {dur:7.3f}s  before-fix would be {'1500 (truncated)' if dur>30.5 else n}  after={n}  exp~{exp}  {'PASS' if ok else 'FAIL'}")
print("\nALL PASS" if allok else "\nSOME FAILED")
sys.exit(0 if allok else 1)