import os
import soundfile as sf
import numpy as np

src_audio = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\assets\demo_elevenlabs_16k.wav"
dst_audio = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\assets\master_60s_vietnamese.wav"

data, sr = sf.read(src_audio)
pause = np.zeros(int(0.5 * sr), dtype=data.dtype)

# Repeat 3 times to get ~66.7 seconds of continuous Vietnamese speech
long_data = np.concatenate([data, pause, data, pause, data])

# Trim to exactly 60.0 seconds
target_samples = int(60.0 * sr)
final_data = long_data[:target_samples]

sf.write(dst_audio, final_data, sr)
print(f"Created 60s master audio: {dst_audio} ({len(final_data)/sr:.2f} seconds, SR={sr})")
