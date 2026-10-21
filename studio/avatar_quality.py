"""Avatar source-quality evaluation for the Library UI.

Builds a Vietnamese, operator-facing quality assessment for each prepared
avatar from REAL validator output only — never fabricated, never LLM.

Flow per avatar:
  1. resolve the raw source (avator_info.json video_path + data/avatar_sources.json
     surviving_copy_path) — read-only.
  2. if a raw source exists on disk, run tools/avatar_source_quality/validator.py
     as a subprocess (read-only; never mutates the source) and parse its JSON.
  3. map the validator's measured fields to Vietnamese dimensions/levels/
     strengths/warnings/recommendation (deterministic).
  4. cache the structured result in the avatars DB table (quality_data).

If no source exists → quality_status = "CHUA_CO_DU_LIEU" (no metrics, no guess).
If the avatar is technically incomplete → quality is NOT assessed (the UI shows
INCOMPLETE technical status instead).

Quality status vs technical status are kept separate:
  technical_status: SAN_SANG / CHUA_HOAN_TAT / DANG_CHUAN_BI / LOI
  quality_status:   RAT_TOT / TOT / CANH_BAO / KHONG_KHUYEN_NGHI / CHUA_CO_DU_LIEU
"""
import os
import re
import json
import pickle
import sqlite3
import subprocess
from typing import Dict, Any, Optional, List

import cv2
import numpy as np

from . import config, db, runtime
from .avatar_service import _torch_python, _read_info, _check_ready

# Vietnamese quality levels (UI-facing).
RAT_TOT = "RẤT TỐT"
TOT = "TỐT"
CANH_BAO = "CẢNH BÁO"
KHONG_KHUYEN_NGHI = "KHÔNG KHUYẾN NGHỊ"
CHUA_CO_DU_LIEU = "CHƯA CÓ DỮ LIỆU"
CHUA_DU_DU_LIEU = "CHƯA ĐỦ DỮ LIỆU"  # partial (e.g. raw source missing)

# Production confidence (from REAL render history — not source quality).
PROD_CAO = "CAO"
PROD_TRUNG_BINH = "TRUNG BÌNH"
PROD_CHUA_KIEM_CHUNG = "CHƯA KIỂM CHỨNG"

# Quality provenance.
SRC_VALIDATOR = "RAW_VALIDATOR"
SRC_PREPARED = "PREPARED_ANALYSIS"
SRC_HISTORICAL = "HISTORICAL_AUDIT"
SRC_UNKNOWN = "UNKNOWN"


def render_history(avatar_id: str) -> Dict[str, Any]:
    """Count REAL successful renders for an avatar. Evidence for PRODUCTION
    CONFIDENCE (kept separate from source quality).

    Sources:
      * SQLite jobs table (authoritative, exact avatar_id match) — UI jobs.
      * external render files under D:\\CongThang_AI_Avatar\\renders whose path
        contains the avatar_id as a distinct token (boundary regex so close_up
        does NOT match close_up_16_7).
    Read-only; never counts in-progress/failed jobs as production evidence."""
    db_complete = 0
    try:
        conn = sqlite3.connect(config.DB_PATH)
        row = conn.execute("SELECT COUNT(*) FROM jobs WHERE avatar_id=? AND status='complete'",
                           (avatar_id,)).fetchone()
        db_complete = int(row[0]) if row else 0
        conn.close()
    except Exception:
        pass
    # external renders (pre-UI production outputs)
    external = 0
    rend_root = config.RENDERS_DIR
    if os.path.isdir(rend_root):
        pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(avatar_id) + r"(?![A-Za-z0-9_])")
        for root, _dirs, files in os.walk(rend_root):
            for f in files:
                if f.lower().endswith(".mp4"):
                    if pat.search(os.path.join(root, f)):
                        external += 1
    total = db_complete + external
    conf = (PROD_CAO if total >= 2 else PROD_TRUNG_BINH if total >= 1 else PROD_CHUA_KIEM_CHUNG)
    return {"db_complete": db_complete, "external": external, "total": total,
            "production_confidence": conf}


# --------------------------------------------------------------------------- #
# PREPARED AVATAR QUALITY ANALYSIS                                              #
# --------------------------------------------------------------------------- #
# Honest metrics derived ONLY from prepared artifacts (full_imgs, coords.pkl,
# mask, mask_coords.pkl, avator_info.json) for avatars whose raw source is
# missing. This is NOT source quality — it cannot tell us whether the original
# source was talking, original camera stability, original lighting, or raw
# resolution. Those dimensions are explicitly marked unavailable. Provenance =
# PREPARED_ANALYSIS. Never overwrites RAW_VALIDATOR source results.

_PREP_SAMPLE = 8  # frames to sample (keeps analysis fast, in-process cv2)


def _lapvar(img_gray):
    return float(cv2.Laplacian(img_gray, cv2.CV_64F).var())


def prepared_analysis(avatar_id: str) -> Dict[str, Any]:
    """Measure what is genuinely measurable from PREPARED artifacts. Read-only;
    never touches the prepared files. Returns a structured prepared-quality
    dict. Provenance = PREPARED_ANALYSIS."""
    d = os.path.join(config.AVATARS_ROOT, avatar_id)
    if not os.path.isdir(d):
        return {"prepared_status": CHUA_CO_DU_LIEU, "provenance": SRC_UNKNOWN,
                "dimensions": [], "strengths": [], "warnings": []}
    info = _read_info(d) or {}
    full_dir = os.path.join(d, "full_imgs")
    mask_dir = os.path.join(d, "mask")
    if not os.path.isdir(full_dir) or not os.path.isdir(mask_dir):
        return {"prepared_status": CHUA_CO_DU_LIEU, "provenance": SRC_UNKNOWN,
                "dimensions": [], "strengths": [], "warnings": []}

    full_imgs = sorted([f for f in os.listdir(full_dir)
                        if f.lower().endswith((".png", ".jpg", ".jpeg"))])
    masks = sorted([f for f in os.listdir(mask_dir)
                    if f.lower().endswith((".png", ".jpg", ".jpeg"))])
    coords = None
    try:
        with open(os.path.join(d, "coords.pkl"), "rb") as f:
            coords = pickle.load(f)
    except Exception:
        coords = None

    # First frame for resolution.
    first = cv2.imread(os.path.join(full_dir, full_imgs[0])) if full_imgs else None
    if first is None:
        return {"prepared_status": CHUA_CO_DU_LIEU, "provenance": SRC_UNKNOWN,
                "dimensions": [], "strengths": [], "warnings": []}
    H, W = first.shape[:2]

    # Sample frame indices evenly.
    n = len(full_imgs)
    n_sample = min(_PREP_SAMPLE, n)
    idxs = [int(i * (n - 1) / max(n_sample - 1, 1)) for i in range(n_sample)] if n_sample > 1 else [0]

    dims = []
    strengths = []
    warnings = []

    # 7. Frame count / integrity
    integrity_ok = (len(full_imgs) == len(masks) and coords is not None
                    and len(coords) == len(full_imgs) and len(full_imgs) >= 1)
    fc_level = TOT if (len(full_imgs) >= 100 and integrity_ok) else (CANH_BAO if integrity_ok else KHONG_KHUYEN_NGHI)
    dims.append({"key": "frame_integrity", "label": "Số frame / tính toàn vẹn",
                 "level": fc_level,
                 "explanation": (f"{len(full_imgs)} frame, đầy đủ full_imgs/mask/coords." if integrity_ok
                                 else "Thiếu frame hoặc không khớp full_imgs/mask/coords."),
                 "value": {"frames": len(full_imgs), "masks": len(masks), "coords": len(coords) if coords else 0}})

    # 8/9/10. Resolution, version, parsing mode (metadata, no level)
    dims.append({"key": "resolution", "label": "Độ phân giải đã chuẩn bị",
                 "level": None, "explanation": f"{W}×{H}", "value": {"width": W, "height": H}})
    dims.append({"key": "version", "label": "Phiên bản", "level": None,
                 "explanation": str(info.get("version")), "value": info.get("version")})
    dims.append({"key": "parsing_mode", "label": "Chế độ parsing", "level": None,
                 "explanation": str(info.get("parsing_mode")), "value": info.get("parsing_mode")})

    # 2. Prepared face size (bbox_h / frame_h). coords = [x1,y1,x2,y2].
    face_ratios = []
    chin_rooms = []
    centers = []
    if coords:
        for i in idxs:
            if i >= len(coords):
                continue
            b = coords[i]
            try:
                x1, y1, x2, y2 = b[0], b[1], b[2], b[3]
            except Exception:
                continue
            bh = y2 - y1
            if bh <= 0 or H <= 0:
                continue
            face_ratios.append(bh / float(H))
            chin_rooms.append((H - y2) / float(bh) if bh > 0 else 0)
            centers.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
    fr = float(np.median(face_ratios)) if face_ratios else None
    fs_level = (TOT if fr and fr >= 0.10 else CANH_BAO if fr and fr >= 0.07 else KHONG_KHUYEN_NGHI if fr else CHUA_CO_DU_LIEU)
    if fr and fr >= 0.10: strengths.append("Vùng mặt đủ lớn")
    elif fr: warnings.append("Vùng mặt hơi nhỏ")
    dims.append({"key": "face_size", "label": "Kích thước vùng mặt (đã chuẩn bị)",
                 "level": fs_level,
                 "explanation": (f"Tỉ lệ mặt/frame ≈ {fr:.3f}." if fr else "Không đo được."),
                 "value": round(fr, 4) if fr else None})

    # 6. Chin/mouth coverage
    cr = float(np.median(chin_rooms)) if chin_rooms else None
    cr_level = (TOT if cr and cr >= 0.3 else CANH_BAO if cr and cr >= 0.1 else KHONG_KHUYEN_NGHI if cr is not None else CHUA_CO_DU_LIEU)
    if cr and cr >= 0.3: strengths.append("Vùng cằm/miệng đầy đủ")
    elif cr is not None and cr < 0.1: warnings.append("Vùng cằm sát mép")
    dims.append({"key": "chin_coverage", "label": "Bao phủ vùng cằm/miệng",
                 "level": cr_level,
                 "explanation": (f"Không gian dưới mặt ≈ {cr:.2f}× chiều cao mặt." if cr is not None else "Không đo được."),
                 "value": round(cr, 3) if cr is not None else None})

    # 3. Crop position stability (std of bbox center across sampled frames)
    if len(centers) >= 2:
        arr = np.array(centers)
        cstd = float(np.mean([arr[:, 0].std(), arr[:, 1].std()]))
    else:
        cstd = None
    cp_level = (TOT if cstd is not None and cstd < 8 else CANH_BAO if cstd is not None and cstd < 25 else KHONG_KHUYEN_NGHI if cstd is not None else CHUA_CO_DU_LIEU)
    if cstd is not None and cstd < 8: strengths.append("Crop khuôn mặt ổn định")
    elif cstd is not None and cstd >= 25: warnings.append("Crop khuôn mặt lệch nhiều")
    dims.append({"key": "crop_stability", "label": "Độ ổn định vị trí crop",
                 "level": cp_level,
                 "explanation": (f"Độ lệch trung bình ≈ {cstd:.1f}px." if cstd is not None else "Không đo được (1 frame)."),
                 "value": round(cstd, 2) if cstd is not None else None})

    # 1. Face-crop sharpness (Laplacian var on the face bbox region — comparable
    # to the validator's face sharpness, NOT full-frame which is dominated by
    # smooth body/background).
    laps = []
    for i in idxs:
        img = cv2.imread(os.path.join(full_dir, full_imgs[i]))
        if img is None:
            continue
        crop = None
        if coords and i < len(coords):
            b = coords[i]
            try:
                x1, y1, x2, y2 = int(b[0]), int(b[1]), int(b[2]), int(b[3])
                crop = img[max(0, y1):min(H, y2), max(0, x1):min(W, x2)]
            except Exception:
                crop = None
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop is not None and crop.size else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        laps.append(_lapvar(g))
    sh = float(np.median(laps)) if laps else None
    sh_level = (TOT if sh and sh >= 120 else CANH_BAO if sh and sh >= 50 else KHONG_KHUYEN_NGHI if sh is not None else CHUA_CO_DU_LIEU)
    if sh and sh >= 120: strengths.append("Frame rõ")
    elif sh is not None and sh < 50: warnings.append("Frame hơi mờ")
    dims.append({"key": "sharpness", "label": "Độ nét vùng mặt (đã chuẩn bị)",
                 "level": sh_level,
                 "explanation": (f"Độ nét vùng mặt (Laplacian) ≈ {sh:.1f}." if sh else "Không đo được."),
                 "value": round(sh, 1) if sh else None})

    # 4. Motion in prepared frames (mean frame-to-frame diff, sampled)
    motion = None
    if len(idxs) >= 2:
        diffs = []
        prev = None
        for i in idxs:
            img = cv2.imread(os.path.join(full_dir, full_imgs[i]))
            if img is None:
                continue
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if prev is not None:
                diffs.append(float(cv2.absdiff(g, prev).mean()))
            prev = g
        motion = float(np.mean(diffs)) if diffs else None
    m_level = (TOT if motion is not None and motion < 15 else CANH_BAO if motion is not None and motion < 40 else KHONG_KHUYEN_NGHI if motion is not None else CHUA_CO_DU_LIEU)
    if motion is not None and motion < 15: strengths.append("Chuyển động prepared ổn định")
    elif motion is not None and motion >= 40: warnings.append("Chuyển động prepared nhiều")
    dims.append({"key": "motion", "label": "Độ ổn định chuyển động (prepared)",
                 "level": m_level,
                 "explanation": (f"Mean frame-to-frame diff ≈ {motion:.2f}." if motion is not None else "Không đo được (1 frame)."),
                 "value": round(motion, 2) if motion is not None else None})

    # 5. Mask stability (std of mask non-zero area across sampled masks)
    mask_areas = []
    for i in idxs:
        if i >= len(masks):
            continue
        m = cv2.imread(os.path.join(mask_dir, masks[i]), cv2.IMREAD_GRAYSCALE)
        if m is None:
            continue
        mask_areas.append(float((m > 0).sum()))
    if len(mask_areas) >= 2:
        ma = np.array(mask_areas)
        mask_cv = float(ma.std() / (ma.mean() + 1e-6))
    else:
        mask_cv = None
    mk_level = (TOT if mask_cv is not None and mask_cv < 0.10 else CANH_BAO if mask_cv is not None and mask_cv < 0.30 else KHONG_KHUYEN_NGHI if mask_cv is not None else CHUA_CO_DU_LIEU)
    if mask_cv is not None and mask_cv < 0.10: strengths.append("Mask ổn định")
    elif mask_cv is not None and mask_cv >= 0.30: warnings.append("Mask không ổn định")
    dims.append({"key": "mask_stability", "label": "Độ ổn định mask",
                 "level": mk_level,
                 "explanation": (f"Hệ số biến thiên diện tích mask ≈ {mask_cv:.3f}." if mask_cv is not None else "Không đo được (1 frame)."),
                 "value": round(mask_cv, 3) if mask_cv is not None else None})

    # Prepared overall: any KHÔNG KHUYẾN NGHỊ -> KHÔNG KHUYẾN NGHỊ; elif any
    # CẢNH BÁO -> CẢNH BÁO; else TỐT. (CHƯA CÓ DỮ LIỆU dims don't count.)
    levels = [x["level"] for x in dims if x.get("level") in (TOT, CANH_BAO, KHONG_KHUYEN_NGHI)]
    if KHONG_KHUYEN_NGHI in levels:
        prepared_status = KHONG_KHUYEN_NGHI
    elif CANH_BAO in levels:
        prepared_status = CANH_BAO
    elif levels:
        prepared_status = TOT
    else:
        prepared_status = CHUA_CO_DU_LIEU

    return {
        "prepared_status": prepared_status,
        "provenance": SRC_PREPARED,
        "dimensions": dims,
        "strengths": strengths,
        "warnings": warnings,
        "face_h_ratio_prepared": round(fr, 4) if fr else None,
    }


def resolve_raw_source(avatar_id: str) -> Optional[str]:
    """Resolve an on-disk raw source video for the avatar, or None.

    Order: avator_info.json video_path -> data/avatar_sources.json
    surviving_copy_path. Returns the first path that exists on disk.
    Read-only; never modifies anything."""
    d = os.path.join(config.AVATARS_ROOT, avatar_id)
    if not os.path.isdir(d):
        return None
    info = _read_info(d) or {}
    cands = []
    vp = info.get("video_path")
    if vp:
        # avator_info video_path may be repo-relative ("input/...") or absolute.
        if not os.path.isabs(vp):
            cands.append(os.path.join(config.ROOT, vp))
        cands.append(vp)
    # lineage index
    lineage_path = os.path.join(config.ROOT, "data", "avatar_sources.json")
    if os.path.exists(lineage_path):
        try:
            with open(lineage_path, "r", encoding="utf-8") as f:
                lin = json.load(f)
            entry = (lin.get("avatars") or {}).get(avatar_id, {})
            surv = entry.get("surviving_copy_path")
            if surv:
                cands.append(surv)
        except Exception:
            pass
    for c in cands:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    return None


def _run_validator(video_path: str) -> Optional[Dict[str, Any]]:
    """Run validator.py as a subprocess (read-only) and return its JSON.
    Returns None on failure."""
    out_json = os.path.join(config.TEMP_DIR, f"q_{os.getpid()}_{abs(hash(video_path))%100000}.json")
    try:
        os.unlink(out_json)
    except OSError:
        pass
    cmd = [_torch_python(), config.VALIDATOR, "--video", video_path, "--json", out_json]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                       cwd=runtime.repo_root())
    except Exception:
        return None
    if not os.path.exists(out_json):
        return None
    try:
        with open(out_json, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
    finally:
        try:
            os.unlink(out_json)
        except OSError:
            pass


# --- deterministic mapping: validator field -> Vietnamese dimension ----------

def _level_from_status(status: str, value=None, dim: str = ""):
    """Map a validator category status (PASS/WARN/FAIL) + value to a VI level."""
    if status == "FAIL":
        return KHONG_KHUYEN_NGHI
    if status == "WARN":
        return CANH_BAO
    # PASS -> TỐT, or RẤT TỐT for standout values
    if dim == "face_size" and isinstance(value, (int, float)) and value >= 0.16:
        return RAT_TOT
    if dim == "sharpness" and isinstance(value, (int, float)) and value >= 200:
        return RAT_TOT
    if dim == "frontalness" and isinstance(value, (int, float)) and value >= 0.95:
        return RAT_TOT
    return TOT


# Per-dimension Vietnamese metadata: (label, explanation-by-level)
_DIM_META = {
    "face_size": {
        "label": "Kích thước khuôn mặt",
        "explain": {
            RAT_TOT: "Khuôn mặt lớn và rõ — rất tốt cho khẩu hình.",
            TOT: "Khuôn mặt đủ lớn để hệ thống nhận diện môi rõ.",
            CANH_BAO: "Khuôn mặt hơi nhỏ. Khẩu hình có thể ít chi tiết hơn.",
            KHONG_KHUYEN_NGHI: "Khuôn mặt quá nhỏ trong khung hình.",
        },
    },
    "sharpness": {
        "label": "Độ nét khuôn mặt",
        "explain": {
            RAT_TOT: "Khuôn mặt và vùng môi rất sắc nét.",
            TOT: "Khuôn mặt và môi đủ sắc nét để tạo khẩu hình.",
            CANH_BAO: "Khuôn mặt hơi mềm. Nên dùng nguồn sắc nét hơn.",
            KHONG_KHUYEN_NGHI: "Khuôn mặt mờ, khẩu hình sẽ kém.",
        },
    },
    "frontalness": {
        "label": "Góc mặt",
        "explain": {
            RAT_TOT: "Nhân vật nhìn chính diện, rất phù hợp lipsync.",
            TOT: "Nhân vật nhìn gần chính diện, phù hợp lipsync.",
            CANH_BAO: "Mặt hơi lệch. Nên dùng nguồn chính diện hơn.",
            KHONG_KHUYEN_NGHI: "Mặt lệch nhiều, không tối ưu cho lipsync.",
        },
    },
    "mouth_visibility": {
        "label": "Miệng nhìn rõ",
        "explain": {
            RAT_TOT: "Miệng luôn nhìn rõ trong khung.",
            TOT: "Miệng nhìn rõ trong khung.",
            CANH_BAO: "Miệng partly ra khỏi khung ở vài khung.",
            KHONG_KHUYEN_NGHI: "Miệng không reliably nhìn thấy.",
        },
    },
    "chin_visibility": {
        "label": "Cằm / đường hàm",
        "explain": {
            RAT_TOT: "Cằm và đường hàm đầy đủ, rất ổn định.",
            TOT: "Cằm và đường hàm đầy đủ giúp vùng ghép miệng ổn định.",
            CANH_BAO: "Cằm hơi sát mép khung.",
            KHONG_KHUYEN_NGHI: "Cằm bị cắt hoặc che.",
        },
    },
    "source_mouth_state": {
        "label": "Trạng thái miệng nguồn",
        "explain": {
            RAT_TOT: "Miệng trung tính trong video gốc — phù hợp.",
            TOT: "Miệng trung tính trong video gốc — phù hợp.",
            CANH_BAO: "Nhân vật đang nói trong video gốc. Nên dùng nguồn miệng trung tính.",
            KHONG_KHUYEN_NGHI: "Nhân vật nói nhiều / biểu cảm mạnh — nguồn kém.",
        },
    },
    "motion": {
        "label": "Độ ổn định chuyển động",
        "explain": {
            RAT_TOT: "Rất ổn định.",
            TOT: "Chuyển động nhẹ và tự nhiên, phù hợp AI Avatar.",
            CANH_BAO: "Có chuyển động nhẹ / camera hơi rung.",
            KHONG_KHUYEN_NGHI: "Chuyển động nhiều, không ổn định.",
        },
    },
    "lighting": {
        "label": "Ánh sáng",
        "explain": {
            RAT_TOT: "Ánh sáng rất ổn định.",
            TOT: "Ánh sáng ổn định giúp khuôn mặt giữ chất lượng đồng đều.",
            CANH_BAO: "Ánh sáng hơi thay đổi.",
            KHONG_KHUYEN_NGHI: "Ánh sáng không ổn định.",
        },
    },
}

# Map validator category -> dimension key + short strength/warning text.
_CAT_TO_DIM = {
    "FACE_SIZE": ("face_size", "Khuôn mặt rõ", "Khuôn mặt hơi nhỏ", "Khuôn mặt quá nhỏ"),
    "FACE_SHARPNESS": ("sharpness", "Khuôn mặt sắc nét", "Khuôn mặt hơi mềm", "Khuôn mặt mờ"),
    "FRONTALNESS": ("frontalness", "Góc chính diện", "Mặt hơi lệch", "Mặt lệch nhiều"),
    "MOUTH_VISIBILITY": ("mouth_visibility", "Miệng nhìn rõ", "Miệng partly ra khung", "Miệng không rõ"),
    "CHIN_VISIBILITY": ("chin_visibility", "Cằm đầy đủ", "Cằm hơi sát mép", "Cằm bị cắt"),
    "SOURCE_MOUTH_STATE": ("source_mouth_state", "Miệng trung tính", "Nhân vật đang nói trong nguồn", "Biểu cảm mạnh trong nguồn"),
    "MOTION": ("motion", "Ổn định", "Có chuyển động", "Chuyển động nhiều"),
    "LIGHTING": ("lighting", "Ánh sáng ổn định", "Ánh sáng hơi thay đổi", "Ánh sáng không ổn định"),
}


def _overall_level(dimensions: List[dict], face_h_ratio) -> str:
    """Compute overall quality level from per-dimension levels (deterministic)."""
    levels = [d["level"] for d in dimensions]
    if KHONG_KHUYEN_NGHI in levels:
        return KHONG_KHUYEN_NGHI
    if CANH_BAO in levels:
        return CANH_BAO
    # all TỐT/RẤT TỐT
    if isinstance(face_h_ratio, (int, float)) and face_h_ratio >= 0.16:
        return RAT_TOT
    return TOT


def _recommendation(level: str, warnings: List[str]) -> str:
    if level == RAT_TOT:
        return "Avatar chất lượng cao, phù hợp sử dụng."
    if level == TOT:
        return "Avatar phù hợp sử dụng."
    if level == CANH_BAO:
        w = "; ".join(warnings[:3]) if warnings else "có điểm cần lưu ý"
        return f"Vẫn sử dụng được, nhưng chất lượng khẩu hình có thể thấp hơn mức tối ưu ({w})."
    return "Nên quay nguồn mới tốt hơn. Vẫn có thể dùng nếu cần."


def build_quality(avatar_id: str, vresult: Dict[str, Any],
                  source_path: str) -> Dict[str, Any]:
    """Map a validator JSON result to the Vietnamese quality structure."""
    cats = vresult.get("categories", {})
    face_h = vresult.get("face_h_ratio")
    dimensions = []
    strengths = []
    warnings = []
    for cat, (dim, ok_txt, warn_txt, bad_txt) in _CAT_TO_DIM.items():
        c = cats.get(cat)
        if not c:
            continue
        status = c.get("status", "PASS")
        value = c.get("value")
        level = _level_from_status(status, value, dim)
        meta = _DIM_META.get(dim, {})
        dimensions.append({
            "key": dim,
            "label": meta.get("label", cat),
            "level": level,
            "explanation": meta.get("explain", {}).get(level, c.get("note", "")),
            "value": value,  # advanced/technical
            "validator_status": status,
        })
        if status == "PASS":
            strengths.append(ok_txt)
        elif status == "WARN":
            warnings.append(warn_txt)
        else:  # FAIL
            warnings.append(bad_txt)

    integrity = vresult.get("integrity", {}) or {}
    overall = _overall_level(dimensions, face_h)
    rh = render_history(avatar_id)
    return {
        "avatar_id": avatar_id,
        "quality_status": overall,
        "quality_source": SRC_VALIDATOR,
        "source_path": source_path,
        "source_exists": True,
        "face_h_ratio": face_h,
        "dimensions": dimensions,
        "strengths": strengths,
        "warnings": warnings,
        "recommendation": _recommendation(overall, warnings),
        "production_confidence": rh["production_confidence"],
        "render_history": rh,
        "prepared_quality": prepared_analysis(avatar_id),
        "video": {
            "width": integrity.get("width"),
            "height": integrity.get("height"),
            "fps": integrity.get("fps"),
            "duration": integrity.get("duration"),
            "frames": integrity.get("frames"),
            "integrity_status": integrity.get("status"),
        },
    }


def _no_data_quality(avatar_id: str, source_path: Optional[str]) -> Dict[str, Any]:
    rh = render_history(avatar_id)
    # Source unknown, but production confidence may be high if real renders exist.
    has_renders = rh["total"] >= 1
    return {
        "avatar_id": avatar_id,
        "quality_status": CHUA_DU_DU_LIEU if has_renders else CHUA_CO_DU_LIEU,
        "quality_source": SRC_UNKNOWN,
        "source_path": source_path,
        "source_exists": bool(source_path),
        "face_h_ratio": None,
        "dimensions": [],
        "strengths": [],
        "warnings": [],
        "recommendation": ("Video nguồn gốc không còn — chưa đánh giá được chất "
                           "lượng nguồn. Đã có render thực tế (xem độ tin cậy "
                           "production)." if has_renders
                           else "Chưa có đủ dữ liệu để đánh giá chất lượng nguồn."),
        "production_confidence": rh["production_confidence"],
        "render_history": rh,
        "prepared_quality": prepared_analysis(avatar_id),
        "video": {},
    }


def evaluate_avatar(avatar_id: str, force: bool = False) -> Dict[str, Any]:
    """Evaluate one avatar's source quality (read-only), cache in DB, return it.
    Never fabricates. Incomplete avatars are NOT quality-assessed."""
    d = os.path.join(config.AVATARS_ROOT, avatar_id)
    if not os.path.isdir(d):
        return _no_data_quality(avatar_id, None)

    # Return cached unless forced.
    if not force:
        cached = _cached_quality(avatar_id)
        if cached:
            return cached

    # Only assess READY avatars (incomplete -> no quality, UI shows INCOMPLETE).
    if not _check_ready(d):
        return _no_data_quality(avatar_id, None)

    src = resolve_raw_source(avatar_id)
    if not src:
        q = _no_data_quality(avatar_id, None)
        _store_quality(avatar_id, q)
        return q

    vresult = _run_validator(src)
    if not vresult or "categories" not in vresult:
        # validator failed (e.g. a photo, not a video) -> honest no-data
        q = _no_data_quality(avatar_id, src)
        q["recommendation"] = "Không thể phân tích video nguồn — chưa có đánh giá đầy đủ."
        _store_quality(avatar_id, q)
        return q

    q = build_quality(avatar_id, vresult, src)
    _store_quality(avatar_id, q)
    return q


def _cached_quality(avatar_id: str) -> Optional[Dict[str, Any]]:
    row = db.get_avatar(avatar_id)
    if not row:
        return None
    qd = row.get("quality_data")
    if not qd:
        return None
    try:
        return json.loads(qd)
    except Exception:
        return None


def _store_quality(avatar_id: str, q: Dict[str, Any]) -> None:
    # Map VI overall -> legacy PASS/WARN/FAIL for the `quality` column.
    lvl = q.get("quality_status", "")
    legacy = (RAT_TOT if lvl == RAT_TOT else TOT if lvl == TOT
              else CANH_BAO if lvl == CANH_BAO
              else KHONG_KHUYEN_NGHI if lvl == KHONG_KHUYEN_NGHI else "UNKNOWN")
    db.upsert_avatar(avatar_id, quality=legacy,
                     quality_data=json.dumps(q, ensure_ascii=False))


def production_confidence_for_list(q: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Compact production-confidence info for the library card (from real
    render history, separate from source quality)."""
    if not q:
        return {"production_confidence": PROD_CHUA_KIEM_CHUNG, "render_count": 0}
    rh = q.get("render_history") or {}
    return {"production_confidence": q.get("production_confidence", PROD_CHUA_KIEM_CHUNG),
            "render_count": rh.get("total", 0)}


def evaluate_all(force: bool = False) -> Dict[str, Any]:
    """Backfill: evaluate every prepared avatar with an on-disk source.
    Read-only. Returns a summary. Does not touch incomplete avatars' quality."""
    if not os.path.isdir(config.AVATARS_ROOT):
        return {"evaluated": 0, "results": []}
    results = []
    for name in sorted(os.listdir(config.AVATARS_ROOT)):
        if name.startswith(".") or not os.path.isdir(os.path.join(config.AVATARS_ROOT, name)):
            continue
        q = evaluate_avatar(name, force=force)
        results.append({"avatar_id": name, "quality_status": q["quality_status"],
                        "source_exists": q.get("source_exists")})
    return {"evaluated": len(results), "results": results}


def quality_summary_for_list(q: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Compact quality info for the library card list (no big payload)."""
    if not q:
        return {"quality_status": CHUA_CO_DU_LIEU, "strengths": [], "warnings": [],
                "quality_source": SRC_UNKNOWN, "face_h_ratio": None,
                "production_confidence": PROD_CHUA_KIEM_CHUNG, "render_count": 0,
                "prepared_status": CHUA_CO_DU_LIEU,
                "prepared_strengths": [], "prepared_warnings": []}
    return {
        "quality_status": q.get("quality_status", CHUA_CO_DU_LIEU),
        "strengths": (q.get("strengths") or [])[:4],
        "warnings": (q.get("warnings") or [])[:4],
        "quality_source": q.get("quality_source", SRC_UNKNOWN),
        "face_h_ratio": q.get("face_h_ratio"),
        "production_confidence": q.get("production_confidence", PROD_CHUA_KIEM_CHUNG),
        "render_count": (q.get("render_history") or {}).get("total", 0),
        "prepared_status": ((q.get("prepared_quality") or {}).get("prepared_status")
                            or CHUA_CO_DU_LIEU),
        "prepared_strengths": ((q.get("prepared_quality") or {}).get("strengths") or [])[:4],
        "prepared_warnings": ((q.get("prepared_quality") or {}).get("warnings") or [])[:4],
    }