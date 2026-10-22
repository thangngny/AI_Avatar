import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.long_video_generator import LongVideoGenerator

if __name__ == "__main__":
    generator = LongVideoGenerator(output_root=r"D:\CongThang_AI_Avatar\v2_renders")
    res = generator.render_long_video(
        job_id="job_long_60s_broadcast_001",
        avatar_id="doTrang_closeup",
        master_audio_path=r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\assets\master_60s_vietnamese.wav",
        final_output_path=r"D:\CongThang_AI_Avatar\v2_renders\long_60s_broadcast_v2.mp4",
        expressive=True,
        smooth_60fps=False, # 25 FPS standard broadcast
        batch_size=32
    )
    print("Result:", res)
