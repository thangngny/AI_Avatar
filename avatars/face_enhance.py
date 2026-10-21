"""GFPGAN Face Super-Resolution & Restoration (RTX 5090 Blackwell FP16 Optimized).

MuseTalk generates lip-synced faces at 256x256. When pasted back into 1080p/4K video,
the face bbox is typically ~400-500px, which causes slight softness.
This module passes the face crops through GFPGANv1.4 in pure PyTorch FP16 on the RTX 5090,
restoring teeth edges, lip textures, and skin pores at 512x512 resolution (110+ FPS).

Zero external dependencies (no basicsr / facexlib C++ build required).
"""
import os
import threading
import cv2
import numpy as np
import torch
import torch.nn.functional as F

from utils.app_root import app_root
from avatars.gfpgan_clean import GFPGANv1Clean

_default_model = str(app_root() / "models" / "GFPGANv1.4.pth")

_state_lock = threading.Lock()
_enabled = None
_weight = 0.6
_device = "cuda"
_model = None
_model_lock = threading.Lock()


def _bool_env(name, default=False):
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def is_enabled():
    """True if LIVETALKING_FACE_ENHANCE is on."""
    global _enabled, _weight, _device
    if _enabled is None:
        with _state_lock:
            if _enabled is None:
                _enabled = _bool_env("LIVETALKING_FACE_ENHANCE", False)
                try:
                    _weight = float(os.getenv("LIVETALKING_FACE_ENHANCE_WEIGHT", "0.6"))
                except ValueError:
                    _weight = 0.6
                dev = os.getenv("LIVETALKING_FACE_ENHANCE_DEVICE", "cuda").strip().lower() or "cuda"
                _device = dev if dev in ("cuda", "cpu") else "cuda"
    return _enabled


def set_enabled(enabled=True, weight=None):
    """Explicitly enable or disable face enhancement."""
    global _enabled, _weight
    with _state_lock:
        _enabled = bool(enabled)
        if weight is not None:
            _weight = float(weight)


def _get_model():
    """Lazily load GFPGANv1Clean model in FP16 on CUDA. Thread-safe singleton."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        model_path = os.getenv("LIVETALKING_FACE_ENHANCE_MODEL", _default_model)
        if not os.path.isfile(model_path):
            try:
                from utils.logger import logger
                logger.warning("face_enhance: model not found at %s", model_path)
            except Exception:
                pass
            return None

        dev = _device if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if dev == "cuda" else torch.float32

        checkpoint = torch.load(model_path, map_location="cpu")
        weights = checkpoint.get("params_ema", checkpoint.get("params"))

        net = GFPGANv1Clean(
            out_size=512,
            num_style_feat=512,
            channel_multiplier=2,
            decoder_load_path=None,
            fix_decoder=False,
            num_mlp=8,
            input_is_latent=True,
            different_w=True,
            narrow=1,
            sft_half=True
        )
        net.load_state_dict(weights, strict=True)
        net.eval().to(dev, dtype=dtype)
        _model = (net, dev, dtype)
        try:
            from utils.logger import logger
            logger.info("face_enhance: GFPGANv1.4 loaded in %s (%s)", dtype, dev)
        except Exception:
            pass
        return _model


def enhance_faces(faces, weight=None, target_size=512):
    """Restore and upscale a batch of lip-synced face crops with GFPGAN.

    Args:
        faces: list of HxWx3 BGR uint8 numpy arrays (256x256 crops).
        weight: 0..1 restore strength (default: 0.6).
        target_size: output size (512 or 256).

    Returns:
        list of target_size x target_size BGR uint8 restored faces.
    """
    n = len(faces)
    if n == 0 or not is_enabled():
        return faces

    model_bundle = _get_model()
    if model_bundle is None:
        return faces

    net, dev, dtype = model_bundle
    w = float(weight if weight is not None else _weight)

    try:
        # Preprocess batch to 512x512 RGB [-1, 1]
        processed_tensors = []
        for img in faces:
            h, w_img = img.shape[:2]
            if h != 512 or w_img != 512:
                img_512 = cv2.resize(img, (512, 512), interpolation=cv2.INTER_LANCZOS4)
            else:
                img_512 = img
            # BGR -> RGB
            img_rgb = img_512[:, :, ::-1].astype(np.float32) / 255.0
            # [0, 1] -> [-1, 1]
            img_norm = (img_rgb - 0.5) / 0.5
            # HWC -> CHW
            tensor = torch.from_numpy(img_norm.transpose(2, 0, 1))
            processed_tensors.append(tensor)

        batch_tensor = torch.stack(processed_tensors, dim=0).to(dev, dtype=dtype)

        with torch.no_grad():
            out = net(batch_tensor, return_rgb=False, weight=w)
            if isinstance(out, (tuple, list)):
                out = out[0]

        # Postprocess [-1, 1] RGB -> [0, 255] BGR uint8
        out = (out.clamp(-1.0, 1.0) * 0.5 + 0.5) * 255.0
        out_np = out.permute(0, 2, 3, 1).cpu().float().numpy().astype(np.uint8)

        restored = []
        for i in range(n):
            img_bgr = cv2.cvtColor(out_np[i], cv2.COLOR_RGB2BGR)
            if target_size != 512:
                img_bgr = cv2.resize(img_bgr, (target_size, target_size), interpolation=cv2.INTER_AREA)
            restored.append(img_bgr)

        if dev == "cuda":
            torch.cuda.synchronize()

        return restored
    except Exception as exc:
        try:
            from utils.logger import logger
            logger.warning("face_enhance: enhance failed (%s) -> returning original faces", exc)
        except Exception:
            pass
        return faces
