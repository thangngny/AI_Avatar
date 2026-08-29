"""Centralized production voice allowlist for AI Avatar Studio (V1.6.0).

The normal "Render Video" flow exposes EXACTLY these two ElevenLabs voices.
Normal users no longer type arbitrary Voice IDs. The generic ElevenLabs
client/resolver is NOT weakened — internal diagnostics, operator tools, and
tests can still use arbitrary Voice IDs via the service layer; only the normal
production render API (Flask routes) enforces this allowlist.

Display names come from official ElevenLabs metadata (fetched live, cached),
NOT manually invented labels. The fallback names below are a snapshot of the
official metadata (2026-08-28) used only if the live metadata API is
unreachable — they are metadata-derived, not invented.
"""
from typing import Dict, Any, List, Optional


# ONE authoritative allowlist. Structured so it can carry enable state, display
# name, default language, and approval status. No API secrets here.
APPROVED_RENDER_VOICES: List[Dict[str, Any]] = [
    {
        "voice_id": "pGapy9MNHCukzJtjavF0",
        "enabled": True,
        "display_name_fallback": "Hạnh - Smooth, Clear and Feminine",  # from official metadata
        "description_fallback": "Giọng nữ Hà Nội, phù hợp quảng cáo và giải trí.",
        "default_language": "vi",
        "human_approved": False,   # technically resolved (verified-language policy)
    },
    {
        "voice_id": "N0Z0aL8qHhzwUHwRBcVo",
        "enabled": True,
        "display_name_fallback": "Thanh - Clear, Steady and Informative",  # from official metadata
        "description_fallback": "Giọng nữ Sài Gòn, phù hợp đọc tin, sách nói và giảng dạy.",
        "default_language": "vi",
        "human_approved": True,    # HUMAN_BENCHMARK_APPROVED profile exists
    },
]

# The set of approved Voice IDs for fast membership testing.
_APPROVED_IDS = {v["voice_id"] for v in APPROVED_RENDER_VOICES if v.get("enabled", True)}


def is_approved_render_voice(voice_id: str) -> bool:
    """True iff voice_id is one of the enabled production-approved render voices."""
    return (voice_id or "").strip() in _APPROVED_IDS


def approved_voice_ids() -> List[str]:
    return [v["voice_id"] for v in APPROVED_RENDER_VOICES if v.get("enabled", True)]


def list_approved_render_voices(refresh: bool = False) -> List[Dict[str, Any]]:
    """Return the approved voices enriched with LIVE official metadata names +
    profile status when available. Never exposes the API key. If the live
    metadata API is unreachable, falls back to the metadata-snapshot display
    name (clearly flagged) so the UI never invents a label."""
    from . import elevenlabs_client as el
    from . import db
    out: List[Dict[str, Any]] = []
    for v in APPROVED_RENDER_VOICES:
        if not v.get("enabled", True):
            continue
        vid = v["voice_id"]
        rec: Dict[str, Any] = {
            "voice_id": vid,
            "enabled": True,
            "display_name": v["display_name_fallback"],
            "description": v["description_fallback"],
            "default_language": v["default_language"],
            "human_approved": v["human_approved"],
            "name_source": "metadata_snapshot_fallback",
            "profile": None,
        }
        if el.is_configured():
            vm = el.get_voice_metadata(vid, refresh=refresh)
            if vm.get("ok"):
                rec["display_name"] = vm["metadata"].get("name") or rec["display_name"]
                rec["description"] = vm["metadata"].get("description") or rec["description"]
                rec["labels"] = vm["metadata"].get("labels") or {}
                rec["name_source"] = "ELEVENLABS_VOICE_METADATA_API"
        try:
            rec["profile"] = db.get_profile(vid, v["default_language"])
        except Exception:
            rec["profile"] = None
        out.append(rec)
    return out