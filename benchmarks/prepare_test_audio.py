import os
import soundfile as sf
import numpy as np

src_audio = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\assets\demo_elevenlabs_16k.wav"
dst_dir = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\benchmarks\test_dataset"
os.makedirs(dst_dir, exist_ok=True)

data, sr = sf.read(src_audio)
print(f"Loaded master audio: {len(data)/sr:.2f}s, SR={sr}")

# Test A: Neutral Delivery (First 10.0 seconds)
test_a = data[:int(10.0 * sr)]
sf.write(os.path.join(dst_dir, "test_a_neutral.wav"), test_a, sr)
print(f"Test A written: {len(test_a)/sr:.2f}s")

# Test B: Expressive Delivery (Next 10.0 seconds [10.0 : 20.0])
test_b = data[int(10.0 * sr):int(20.0 * sr)]
sf.write(os.path.join(dst_dir, "test_b_expressive.wav"), test_b, sr)
print(f"Test B written: {len(test_b)/sr:.2f}s")

# Test C: Difficult Articulation (Full 21.92 seconds)
test_c = data
sf.write(os.path.join(dst_dir, "test_c_articulation.wav"), test_c, sr)
print(f"Test C written: {len(test_c)/sr:.2f}s")
