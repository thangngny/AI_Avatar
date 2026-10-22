"""
AI Avatar NextGen V2 - AI Performance Director
Linguistically-grounded Vietnamese Prosody, Emotion & Articulation Planning.
"""
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class SpeakingSegment:
    segment_id: int
    text: str
    tone: str                       # neutral, enthusiastic, serious, emphatic
    pace_rate: float                # 0.9 (slow/dignified), 1.0 (normal), 1.15 (dynamic)
    pause_after_ms: int             # Inter-sentence or inter-clause silence
    emphasis_words: List[str]       # Words requiring dynamic vocal pitch / visual nod
    has_labial_closure: bool        # Contains /b, m, p/ requiring full lip seal
    suggested_head_motion: str      # subtle_nod, tilt_left, steady, slight_affirm


@dataclass
class PerformancePlan:
    raw_script: str
    total_segments: int
    estimated_duration_sec: float
    overall_sentiment: str
    segments: List[SpeakingSegment]
    ssml_markup: Optional[str] = None


class PerformanceDirector:
    """
    Analyzes Vietnamese editorial text and generates an expressive,
    timing-aligned performance plan for TTS and video synthesis.
    """

    ENTHUSIASTIC_KEYWORDS = {
        "chào mừng", "hân hạnh", "tuyệt vời", "đặc biệt", "xuất sắc",
        "đột phá", "rất vui", "vinh dự", "nổi bật", "tự hào", "hoàn hảo",
        "thành công", "ấn tượng", "sôi động", "cuốn hút", "tươi mới"
    }

    SERIOUS_KEYWORDS = {
        "thưa quý vị", "thông báo", "bản tin", "chính phủ", "kinh tế",
        "thị trường", "quan trọng", "nguy hiểm", "lưu ý", "chú ý",
        "nguyên nhân", "thiệt hại", "khẩn cấp", "cảnh báo", "phức tạp"
    }

    EMPHATIC_WORDS = {
        "rất", "cực kỳ", "nhất", "hoàn toàn", "chắc chắn", "đặc biệt",
        "luôn luôn", "tất cả", "chính là", "quyết định", "vô cùng", "tuyệt đối"
    }

    # Vietnamese Bilabial initial & final phonemes requiring complete lip closure
    LABIAL_INITIALS = re.compile(r'\b(b[a-zà-ỹ]*|m[a-zà-ỹ]*|p[a-zà-ỹ]*)\b', re.IGNORECASE)
    LABIAL_FINALS = re.compile(r'\b[a-zà-ỹ]*(m|p)\b', re.IGNORECASE)

    def __init__(self):
        pass

    def analyze_script(self, script_text: str) -> PerformancePlan:
        """
        Parse raw script into structured, timing-aligned speaking segments.
        """
        # Clean & normalize whitespace
        cleaned = re.sub(r'\s+', ' ', script_text.strip())
        if not cleaned:
            return PerformancePlan("", 0, 0.0, "neutral", [])

        # Split on sentence boundaries (. ! ?) and major clause pauses (; ,)
        # Preserve delimiter for punctuation pause estimation
        raw_clauses = re.split(r'([.!?;:])', cleaned)
        sentences: List[str] = []
        current = ""
        for token in raw_clauses:
            if not token:
                continue
            if re.match(r'^[.!?;:]$', token):
                current += token
                sentences.append(current.strip())
                current = ""
            else:
                current += token
        if current.strip():
            sentences.append(current.strip())

        segments: List[SpeakingSegment] = []
        total_estimated_sec = 0.0
        tone_counts = {"neutral": 0, "enthusiastic": 0, "serious": 0}

        for idx, sentence in enumerate(sentences):
            if not sentence:
                continue
            lower_s = sentence.lower()

            # Determine clause pause
            if sentence.endswith('...') or sentence.endswith('…'):
                pause_ms = 850
            elif sentence.endswith('!') or sentence.endswith('?'):
                pause_ms = 600
            elif sentence.endswith('.'):
                pause_ms = 500
            elif sentence.endswith(';') or sentence.endswith(':'):
                pause_ms = 400
            elif sentence.endswith(','):
                pause_ms = 250
            else:
                pause_ms = 350

            # Tone & Sentiment classification
            tone = "neutral"
            if any(k in lower_s for k in self.ENTHUSIASTIC_KEYWORDS):
                tone = "enthusiastic"
            elif any(k in lower_s for k in self.SERIOUS_KEYWORDS):
                tone = "serious"
            tone_counts[tone] += 1

            # Speaking pace rate
            if tone == "enthusiastic":
                pace = 1.05
            elif tone == "serious":
                pace = 0.95
            else:
                pace = 1.0

            # Identify words for emphasis & head nodding
            words = sentence.split()
            emphasis = [w.strip(".,!?;:\"'") for w in words if w.lower().strip(".,!?;:\"'") in self.EMPHATIC_WORDS]

            # Detect bilateral phonemes
            has_labial = bool(self.LABIAL_INITIALS.search(sentence) or self.LABIAL_FINALS.search(sentence))

            # Suggest head motion based on structure
            if len(emphasis) > 0 or tone == "enthusiastic":
                motion = "subtle_nod"
            elif tone == "serious":
                motion = "steady"
            elif idx % 3 == 1:
                motion = "slight_affirm"
            else:
                motion = "steady"

            # Word count estimation: average Vietnamese speaking rate ~3.5 words/second
            est_speech_sec = len(words) / (3.5 * pace)
            est_total_sec = est_speech_sec + (pause_ms / 1000.0)
            total_estimated_sec += est_total_sec

            segments.append(SpeakingSegment(
                segment_id=idx + 1,
                text=sentence,
                tone=tone,
                pace_rate=pace,
                pause_after_ms=pause_ms,
                emphasis_words=emphasis,
                has_labial_closure=has_labial,
                suggested_head_motion=motion
            ))

        # Overall sentiment
        overall = max(tone_counts, key=tone_counts.get)

        # Build SSML Markup for EdgeTTS / compatible TTS engines
        ssml = self._build_ssml(segments)

        return PerformancePlan(
            raw_script=script_text,
            total_segments=len(segments),
            estimated_duration_sec=round(total_estimated_sec, 2),
            overall_sentiment=overall,
            segments=segments,
            ssml_markup=ssml
        )

    def _build_ssml(self, segments: List[SpeakingSegment]) -> str:
        ssml_parts = [
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="vi-VN">'
        ]
        for seg in segments:
            rate_pct = f"{int((seg.pace_rate - 1.0) * 100):+d}%"
            text_escaped = seg.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            ssml_parts.append(f'  <prosody rate="{rate_pct}">{text_escaped}</prosody>')
            if seg.pause_after_ms > 0:
                ssml_parts.append(f'  <break time="{seg.pause_after_ms}ms"/>')
        ssml_parts.append('</speak>')
        return "\n".join(ssml_parts)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    director = PerformanceDirector()
    test_text = (
        "Chào mừng quý vị đã quay trở lại với AI Avatar NextGen V2! "
        "Hôm nay, chúng tôi vô cùng hào hứng được giới thiệu giải pháp digital human đột phá nhất từ trước đến nay. "
        "Với chất lượng chuyển động tự nhiên, môi khép kín hoàn hảo, và giọng đọc truyền cảm, "
        "hệ thống chắc chắn sẽ mang đến trải nghiệm tuyệt vời cho mọi người xem."
    )
    plan = director.analyze_script(test_text)
    print(f"Overall sentiment: {plan.overall_sentiment}")
    print(f"Estimated duration: {plan.estimated_duration_sec}s across {plan.total_segments} segments.")
    for s in plan.segments:
        print(f"[{s.tone.upper()}] (Pace: {s.pace_rate}x, Pause: {s.pause_after_ms}ms, Motion: {s.suggested_head_motion}): {s.text}")
