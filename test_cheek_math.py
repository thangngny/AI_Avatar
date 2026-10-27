import numpy as np

dst_w = 330
x, x1 = 335, 555
x_s = 280
cx = (x + x1) * 0.5 - x_s
half_mouth_w = (x1 - x) * 0.5

cols = np.arange(dst_w, dtype=np.float32)
rel_x = np.abs(cols - cx) / half_mouth_w
t_cheek = np.clip((rel_x - 0.85) / 0.40, 0.0, 1.0)
cheek_fade = (1.0 - t_cheek * t_cheek * (3.0 - 2.0 * t_cheek))

print(f"Center: {cx:.1f}, half_w: {half_mouth_w:.1f}")
print(f"Cheek fade at center (x={int(cx)}): {cheek_fade[int(cx)]:.2f}")
print(f"Cheek fade at mouth corner (x={int(cx+half_mouth_w*0.8)}): {cheek_fade[int(cx+half_mouth_w*0.8)]:.2f}")
print(f"Cheek fade on outer cheek (x={int(cx+half_mouth_w*1.3)}): {cheek_fade[int(cx+half_mouth_w*1.3)]:.2f}")
print(f"Cheek fade on far left edge (x=0): {cheek_fade[0]:.2f}")
print(f"Cheek fade on far right edge (x=329): {cheek_fade[329]:.2f}")
