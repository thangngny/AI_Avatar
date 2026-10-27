import cv2
import numpy as np
import pickle

orig = cv2.imread(r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\data\avatars\doTrang_closeup\full_imgs\00000075.png")

cap = cv2.VideoCapture(r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\reports\doTrang_photoreal_enamel_10s.mp4")
cap.set(cv2.CAP_PROP_POS_FRAMES, 75)
_, gen_frame = cap.read()
cap.release()

mask = cv2.imread(r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\data\avatars\doTrang_closeup\mask\00000075.png", cv2.IMREAD_GRAYSCALE)
with open(r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\data\avatars\doTrang_closeup\mask_coords.pkl", "rb") as f:
    mc = pickle.load(f)[75]
y_s, x_s, y_e, x_e = mc

h, w = mask.shape

# Cheek attenuation filter: allow horizontal spread up to 0.22 from center, then fall smoothly to 0
X = np.linspace(-1, 1, w)
Y = np.linspace(-1, 1, h)
XX, YY = np.meshgrid(X, Y)

# Taper off towards left and right cheeks
cheek_attenuation = np.clip(1.0 - np.maximum(0, (np.abs(XX) - 0.20) / 0.16), 0.0, 1.0)
cheek_attenuation = cv2.GaussianBlur(cheek_attenuation.astype(np.float32), (15, 15), 3.0)

tight_mask = (mask.astype(np.float32) / 255.0) * cheek_attenuation
tight_mask_u8 = (tight_mask * 255).astype(np.uint8)

cv2.imwrite(r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\reports\frames_inspect\tight_mask_75.jpg", tight_mask_u8)

# Now composite both on full frame
# A: with old wide mask
wide_comp = orig.copy()
# B: with cheek-protected tight mask
tight_comp = orig.copy()

# The generated crop inside mask_coords
gen_crop = gen_frame[y_s:y_e, x_s:x_e]
orig_crop = orig[y_s:y_e, x_s:x_e]

# Blend A (wide mask)
alpha_wide = (mask.astype(np.float32) / 255.0)[:, :, None]
blend_a = (gen_crop.astype(np.float32) * alpha_wide + orig_crop.astype(np.float32) * (1.0 - alpha_wide)).astype(np.uint8)
wide_comp[y_s:y_e, x_s:x_e] = blend_a

# Blend B (cheek-protected tight mask)
alpha_tight = tight_mask[:, :, None]
blend_b = (gen_crop.astype(np.float32) * alpha_tight + orig_crop.astype(np.float32) * (1.0 - alpha_tight)).astype(np.uint8)
tight_comp[y_s:y_e, x_s:x_e] = blend_b

# Crop cheek & mouth region: y: 450 to 650, x: 320 to 650
# Left side of this crop (x: 320 to 450) is the LEFT CHEEK that the user noticed!
cheek_crop_a = wide_comp[450:650, 320:650]
cheek_crop_b = tight_comp[450:650, 320:650]
cheek_crop_orig = orig[450:650, 320:650]

comp = np.zeros((200 + 40, 330 * 3 + 40, 3), dtype=np.uint8)
comp.fill(25)
font = cv2.FONT_HERSHEY_SIMPLEX
cv2.putText(comp, "A: Bi lo phan ma (Mask cu)", (10, 25), font, 0.48, (100, 100, 255), 1, cv2.LINE_AA)
cv2.putText(comp, "B: Bao ve ma 100% (Cheek-Guard)", (350, 25), font, 0.48, (50, 230, 100), 2, cv2.LINE_AA)
cv2.putText(comp, "C: Ma that 1080p (Reference)", (690, 25), font, 0.48, (200, 200, 200), 1, cv2.LINE_AA)

comp[35:235, 10:340] = cheek_crop_a
comp[35:235, 350:680] = cheek_crop_b
comp[35:235, 690:1020] = cheek_crop_orig

cv2.imwrite(r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\reports\frames_inspect\cheek_protection_comparison.jpg", comp)
print("Saved cheek protection comparison!")
