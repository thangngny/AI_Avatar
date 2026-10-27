import os

MYUTIL_PATH = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\avatars\musetalk\myutil.py"

with open(MYUTIL_PATH, "r", encoding="utf-8") as f:
    code = f.read()

target = '''    face_large = _prepare_hybrid_generated(body[y_s:y_e, x_s:x_e], face_large, mask_image)

    # NextGen C1-Continuous Smoothstep Boundary Feathering (Zero Step Discontinuity)'''

replacement = '''    face_large = _prepare_hybrid_generated(body[y_s:y_e, x_s:x_e], face_large, mask_image)

    # NextGen SOTA Cheek-Guard: Confine mask strictly to mouth aperture & lips
    # Tapers off horizontally towards left and right cheeks so cheeks remain 100% authentic 1080p camera skin
    enable_cheek_guard = _env_bool("LIVETALKING_CHEEK_GUARD", True)
    if enable_cheek_guard:
        cx = (x + x1) * 0.5 - x_s
        half_mouth_w = max(1.0, (x1 - x) * 0.5)
        cols = np.arange(dst_w, dtype=np.float32)
        rel_x = np.abs(cols - cx) / half_mouth_w
        t_cheek = np.clip((rel_x - 0.85) / 0.40, 0.0, 1.0)
        cheek_fade = (1.0 - t_cheek * t_cheek * (3.0 - 2.0 * t_cheek))[np.newaxis, :]
        mask_image = mask_image * cheek_fade

    # NextGen C1-Continuous Smoothstep Boundary Feathering (Zero Step Discontinuity)'''

if target in code:
    code = code.replace(target, replacement, 1)
    with open(MYUTIL_PATH, "w", encoding="utf-8") as f:
        f.write(code)
    print("SUCCESS: Cheek-Guard successfully integrated into myutil.py!")
else:
    print("ERROR: Target block not found in myutil.py")
