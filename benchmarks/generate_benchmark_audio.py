"""
AI Avatar NextGen V2 - Benchmark Audio Synthesizer
Generates 3 standardized Vietnamese benchmark audio tracks:
  TEST A - Neutral News Delivery
  TEST B - Enthusiastic / Expressive Product Intro
  TEST C - Complex Articulation with Bilabial Plosives & Pauses
"""
import os
import sys
import asyncio
import edge_tts

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

BENCHMARK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_dataset")
os.makedirs(BENCHMARK_DIR, exist_ok=True)

SCRIPTS = {
    "test_a_neutral": {
        "text": (
            "Kính chào quý vị và các bạn đang theo dõi bản tin công nghệ số. "
            "Hôm nay, trung tâm nghiên cứu trí tuệ nhân tạo công bố bước tiến mới trong việc phát triển người số kỹ thuật số, "
            "giúp tối ưu hóa trải nghiệm giao tiếp tự nhiên và nâng cao hiệu suất truyền tải thông tin."
        ),
        "voice": "vi-VN-NamMinhNeural",
        "rate": "+0%"
    },
    "test_b_expressive": {
        "text": (
            "Chào mừng tất cả các bạn đã quay trở lại với sự kiện công nghệ đặc biệt ngày hôm nay! "
            "Chúng tôi thực sự vô cùng phấn khích khi được mang đến cho các bạn một sản phẩm đột phá chưa từng có. "
            "Hãy cùng trải nghiệm hình ảnh sắc nét, biểu cảm chân thực và sống động đến kinh ngạc!"
        ),
        "voice": "vi-VN-HoaiMyNeural",
        "rate": "+4%"
    },
    "test_c_articulation": {
        "text": (
            "Biết bao bỡ ngỡ, mỗi bước đi ban đầu đều mang lại bài học quý báu. "
            "Bốn bề muôn vàn thử thách, nhưng với sự bền bỉ, chúng ta hoàn toàn có thể bứt phá, "
            "chinh phục đỉnh cao và mở ra những cánh cửa tương lai tươi sáng."
        ),
        "voice": "vi-VN-HoaiMyNeural",
        "rate": "-2%"
    }
}


async def generate_audio():
    for name, data in SCRIPTS.items():
        mp3_path = os.path.join(BENCHMARK_DIR, f"{name}.mp3")
        wav_path = os.path.join(BENCHMARK_DIR, f"{name}.wav")
        print(f"Synthesizing {name} with voice {data['voice']}...")
        communicate = edge_tts.Communicate(data["text"], data["voice"], rate=data["rate"])
        await communicate.save(mp3_path)

        # Convert to 16kHz mono WAV for feature extraction
        cmd = f'ffmpeg -y -i "{mp3_path}" -ar 16000 -ac 1 "{wav_path}"'
        os.system(cmd)
        print(f"Saved: {wav_path}")


if __name__ == "__main__":
    asyncio.run(generate_audio())
