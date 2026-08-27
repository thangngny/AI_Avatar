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
import json
import subprocess
from typing import Dict, Any, Optional, List

from . import config, db, runtime
from .avatar_service import _torch_python, _read_info, _check_ready

# Vietnamese quality levels (UI-facing).
RAT_TOT = "RẤT TỐT"
TOT = "TỐT"
CANH_BAO = "CẢNH BÁO"
KHONG_KHUYEN_NGHI = "KHÔNG KHUYẾN NGHỊ"
CHUA_CO_DU_LIEU = "CHƯA CÓ DỮ LIỆU"

# Quality provenance.
SRC_VALIDATOR = "VALIDATOR"
SRC_STORED = "STORED_SOURCE_ANALYSIS"
SRC_UNKNOWN = "UNKNOWN"


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
    return {
        "avatar_id": avatar_id,
        "quality_status": CHUA_CO_DU_LIEU,
        "quality_source": SRC_UNKNOWN,
        "source_path": source_path,
        "source_exists": bool(source_path),
        "face_h_ratio": None,
        "dimensions": [],
        "strengths": [],
        "warnings": [],
        "recommendation": "Chưa có đủ dữ liệu để đánh giá chất lượng nguồn.",
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
                "quality_source": SRC_UNKNOWN, "face_h_ratio": None}
    return {
        "quality_status": q.get("quality_status", CHUA_CO_DU_LIEU),
        "strengths": (q.get("strengths") or [])[:4],
        "warnings": (q.get("warnings") or [])[:4],
        "quality_source": q.get("quality_source", SRC_UNKNOWN),
        "face_h_ratio": q.get("face_h_ratio"),
    }