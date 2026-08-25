#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 5 — generate ONE byte-identical master WAV for all A/B/C candidates.

Renders the continuous Vietnamese passage through EdgeTTS vi-VN-HoaiMyNeural
(the production TTS) then converts to 16 kHz mono with the same apad tail the
render pipeline uses (convert_audio_to_wav). This single master WAV is the only
audio source for every Stage 5 candidate, guaranteeing byte-identical audio so
the only variable that changes is articulation.

Usage:
  latentsync_env\\Scripts\\python.exe stage5_make_audio.py \
    --script script_stage5_continuous.txt \
    --out D:\\CongThang_AI_Avatar\\stage5\\master_continuous.wav
"""
import argparse, os, re, subprocess, tempfile, asyncio
import soundfile as sf


def split_script(text, split_by='sentence'):
    text = text.strip()
    if split_by == 'line':
        return [l.strip() for l in text.splitlines() if l.strip()]
    if split_by == 'sentence':
        chunks = re.split(r'(?<=[.!?\u3000\uff01\uff1f])\s+', text)
        return [c.strip() for c in chunks if c.strip()]
    return [text.strip()]


def generate_edge_tts(text, out_mp3, voice='vi-VN-HoaiMyNeural'):
    import edge_tts
    async def _g():
        await edge_tts.Communicate(text, voice).save(out_mp3)
    asyncio.get_event_loop().run_until_complete(_g())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--script', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--voice', default='vi-VN-HoaiMyNeural')
    ap.add_argument('--split_by', default='sentence')
    args = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.script, 'r', encoding='utf-8') as f:
        raw = f.read()
    chunks = split_script(raw, args.split_by)
    full = ' '.join(chunks)
    print(f'[audio] {len(chunks)} chunks, {len(full)} chars, {sum(1 for c in full if c.isalpha())} letters')
    with tempfile.TemporaryDirectory() as td:
        mp3 = os.path.join(td, 'tts.mp3')
        generate_edge_tts(full, mp3, args.voice)
        # identical to generate_video_from_script.convert_audio_to_wav
        subprocess.run(
            ['ffmpeg', '-y', '-i', mp3, '-ar', '16000', '-ac', '1', '-af', 'apad=pad_len=1600', args.out],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    info = sf.info(args.out)
    print(f'[audio] wrote {args.out}: {info.duration:.2f}s {info.samplerate}Hz {info.channels}ch')
    print(f'[audio] duration {info.duration:.2f}s -> {"OK" if 15 <= info.duration <= 35 else "WARN: outside 15-30s target"}')


if __name__ == '__main__':
    main()