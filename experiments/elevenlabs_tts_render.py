#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EXPERIMENTAL offline ElevenLabs TTS for a script -> 16k mono WAV (for --audio).
Not production TTS architecture (renderer keeps EdgeTTS); this just pre-renders
master audio so generate_video_from_script.py --audio can be used with locked truth.
API key is read from ELEVENLABS_API_KEY env (never written to disk)."""
import os, sys, json, requests, numpy as np, soundfile as sf, re, time

KEY = os.environ.get("ELEVENLABS_API_KEY")
if not KEY:
    sys.exit("STOP: ELEVENLABS_API_KEY env not set. Refusing to proceed (no fallback).")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID")
if not VOICE_ID:
    sys.exit("STOP: ELEVENLABS_VOICE_ID env not set. Refusing to substitute/fallback to any other voice.")
MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
OUT = sys.argv[1] if len(sys.argv) > 1 else "D:/CongThang_AI_Avatar/renders/doTrang_26_8/audio_3min.wav"
SRC_TXT = sys.argv[2] if len(sys.argv) > 2 else "input/scripts_26_8/_script_extracted.txt"
TARGET_SEC = float(os.environ.get("TARGET_SEC", "180"))  # 3 min
WORDS_PER_SEC = float(os.environ.get("WORDS_PER_SEC", "3.0"))  # ~180 wpm Vietnamese (measured)

def synth(text):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}?output_format=pcm_16000"
    body = {"text": text, "model_id": MODEL_ID,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0,
                                "use_speaker_boost": True, "speed": 1.0}}
    r = requests.post(url, headers={"xi-api-key": KEY, "Content-Type": "application/json"},
                      json=body, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"elevenlabs {r.status_code}: {r.text[:300]}")
    return r.content  # raw 16-bit PCM mono 16kHz

def pcm_to_wav(pcm_bytes, sr=16000):
    a = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return a, sr

# load + trim script to ~TARGET_SEC (word-based, exact target words)
txt = open(SRC_TXT, encoding="utf-8").read()
words = txt.split()
target_words = int(TARGET_SEC * WORDS_PER_SEC)
trimmed = " ".join(words[:max(1, target_words)])
open(OUT + ".script.txt", "w", encoding="utf-8").write(trimmed)
print(f"script: total words={len(words)}  -> trimmed words={len(trimmed.split())}  chars={len(trimmed)}")

# synthesize in chunks of <=1800 chars to be safe; concatenate PCM
# split trimmed into sentence-ish pieces by punctuation, then pack
parts = re.split(r'(?<=[.!?…,;:])\s+', trimmed)
chunks = []; buf = ""
for sent in parts:
    if len(buf) + len(sent) + 1 > 1800 and buf:
        chunks.append(buf); buf = sent
    else:
        buf = (buf + " " + sent).strip()
if buf: chunks.append(buf)
print(f"synthesizing {len(chunks)} chunk(s)...")
all_pcm = b""
for k, ch in enumerate(chunks):
    print(f"  chunk {k+1}/{len(chunks)} ({len(ch)} chars)...", flush=True)
    for attempt in range(4):
        try:
            pcm = synth(ch); all_pcm += pcm; break
        except Exception as e:
            print(f"    retry {attempt+1}: {e}")
            if attempt == 3: raise
            time.sleep(2)
a, sr = pcm_to_wav(all_pcm)
sf.write(OUT, a, sr, subtype="FLOAT")
info = sf.info(OUT)
print(f"WROTE {OUT}  duration={info.duration:.2f}s  sr={info.samplerate}  frames={info.frames}")