import numpy as np
import cv2
import os


def _env_bool(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "no", "off")


def _match_skin_lab(source, generated, skin_mask):
    valid = skin_mask > 0.25
    if np.count_nonzero(valid) < 100:
        return generated

    # Fast vectorised C++ path (Reinhard LAB transfer) for NextGen
    fast_match = _env_bool("LIVETALKING_FAST_SKIN_MATCH", True)
    if fast_match:
        mask_u8 = (valid.astype(np.uint8)) * 255
        src_lab = cv2.cvtColor(source, cv2.COLOR_BGR2LAB)
        gen_lab = cv2.cvtColor(generated, cv2.COLOR_BGR2LAB)
        src_m, src_s = cv2.meanStdDev(src_lab, mask=mask_u8)
        gen_m, gen_s = cv2.meanStdDev(gen_lab, mask=mask_u8)
        src_m = src_m.flatten()
        gen_m = gen_m.flatten()
        src_s = src_s.flatten()
        gen_s = gen_s.flatten()

        scale = np.clip(src_s / np.maximum(gen_s, 1.0), 0.85, 1.15)
        max_shift = np.array([12.0, 8.0, 8.0], dtype=np.float32)
        shift = np.clip(src_m - gen_m, -max_shift, max_shift)

        gen_f = gen_lab.astype(np.float32)
        gen_f = (gen_f - gen_m) * scale + gen_m + shift
        gen_lab = np.clip(gen_f, 0, 255).astype(np.uint8)
        return cv2.cvtColor(gen_lab, cv2.COLOR_LAB2BGR)

    src_lab = cv2.cvtColor(source, cv2.COLOR_BGR2LAB).astype(np.float32)
    gen_lab = cv2.cvtColor(generated, cv2.COLOR_BGR2LAB).astype(np.float32)
    max_shift = (12.0, 8.0, 8.0)

    for channel in range(3):
        src_values = src_lab[..., channel][valid]
        gen_values = gen_lab[..., channel][valid]
        src_median = float(np.median(src_values))
        gen_median = float(np.median(gen_values))
        shift = float(np.clip(src_median - gen_median, -max_shift[channel], max_shift[channel]))

        src_iqr = float(np.percentile(src_values, 75) - np.percentile(src_values, 25))
        gen_iqr = float(np.percentile(gen_values, 75) - np.percentile(gen_values, 25))
        gain = float(np.clip(src_iqr / max(gen_iqr, 1.0), 0.85, 1.15))
        gen_lab[..., channel] = (gen_lab[..., channel] - gen_median) * gain + gen_median + shift

    gen_lab = np.clip(gen_lab, 0, 255).astype(np.uint8)
    return cv2.cvtColor(gen_lab, cv2.COLOR_LAB2BGR)


def _restore_source_skin_texture(source, generated, skin_mask):
    strength = float(os.getenv("LIVETALKING_SKIN_TEXTURE_STRENGTH", "0.55"))
    if strength <= 0.0:
        return generated
    src_float = source.astype(np.float32)
    gen_float = generated.astype(np.float32)
    source_low = cv2.GaussianBlur(src_float, (0, 0), 1.1)
    source_detail = src_float - source_low
    textured = np.clip(gen_float + source_detail * strength, 0, 255).astype(np.uint8)
    blend = np.clip(skin_mask, 0.0, 1.0)[..., None].astype(np.float32)
    return np.clip(textured.astype(np.float32) * blend + generated.astype(np.float32) * (1.0 - blend), 0, 255).astype(np.uint8)


def _prepare_hybrid_generated(source_crop, generated_crop, alpha):
    if not _env_bool("LIVETALKING_MOUTH_CHIN_COLOR_MATCH", True):
        return generated_crop
    skin_mask = np.clip((alpha - 0.18) / 0.55, 0.0, 1.0)
    mouth_mask = alpha >= 0.82
    skin_mask[mouth_mask] = 0.0
    if np.count_nonzero(skin_mask > 0.25) < 100:
        return generated_crop

    matched = _match_skin_lab(source_crop, generated_crop, skin_mask)
    matched = _restore_source_skin_texture(source_crop, matched, skin_mask)
    out = generated_crop.copy()
    blend = skin_mask[..., None].astype(np.float32)
    out = np.clip(matched.astype(np.float32) * blend + out.astype(np.float32) * (1.0 - blend), 0, 255).astype(np.uint8)
    out[mouth_mask] = generated_crop[mouth_mask]
    return out

def get_image_blending(image, face, face_box, mask_array, crop_box):
    body = image
    x, y, x1, y1 = face_box
    x_s, y_s, x_e, y_e = crop_box
    face_large = body[y_s:y_e, x_s:x_e].copy()
    dst_h, dst_w = face_large.shape[:2]

    # Place the generated face at the correct offset inside crop_box.
    # The original MuseTalk logic pastes face into crop_box at the face_box
    # offset (x-x_s, y-y_s). Pasting at (0,0) shifts the whole face region
    # and visibly distorts the avatar. We keep the .copy() optimisation
    # (C memcpy, much faster than copy.deepcopy) but restore the proper
    # offset and clamp to the destination bounds for safety.
    y_off = max(0, y - y_s)
    x_off = max(0, x - x_s)
    y_end = min(dst_h, y1 - y_s)
    x_end = min(dst_w, x1 - x_s)
    paste_h = max(0, y_end - y_off)
    paste_w = max(0, x_end - x_off)
    if paste_h > 0 and paste_w > 0:
        face_large[y_off:y_off + paste_h, x_off:x_off + paste_w] = face[:paste_h, :paste_w]

    if mask_array.ndim == 2 and mask_array.dtype == np.float32:
        mask_image = mask_array
    else:
        mask_image = cv2.cvtColor(mask_array, cv2.COLOR_BGR2GRAY) if mask_array.ndim == 3 else mask_array
        mask_image = (mask_image / 255.0).astype(np.float32)

    # Guard: mask and crop may differ by 1px after 1080p downscale of a 4K avatar.
    # blendLinear requires identical sizes, otherwise it raises and paste_back fails.
    if mask_image.shape[:2] != face_large.shape[:2]:
        mask_image = cv2.resize(mask_image, (face_large.shape[1], face_large.shape[0]))

    face_large = _prepare_hybrid_generated(body[y_s:y_e, x_s:x_e], face_large, mask_image)

    # NextGen SOTA: Edge-preserving boundary feathering
    # Protect inner mouth cavity & teeth from being softened by Gaussian blur
    soft_feather = _env_bool("LIVETALKING_SOFT_FEATHER", True)
    if soft_feather:
        blend_mask = cv2.GaussianBlur(mask_image, (7, 7), 2.0)
        inner_mouth = mask_image >= 0.82
        blend_mask[inner_mouth] = 1.0
    else:
        blend_mask = mask_image

    body[y_s:y_e, x_s:x_e] = cv2.blendLinear(
        face_large, body[y_s:y_e, x_s:x_e], blend_mask, 1.0 - blend_mask
    )

    return body
