import os

gen_path = r"C:\Users\phuongpn\AI_Avatar_NextGen_V2\engines\soulx_flashhead\generate_video.py"
with open(gen_path, "r", encoding="utf-8") as f:
    text = f.read()

old_fn = """def save_video(frames_list, video_path, audio_path, fps):
    temp_video_path = video_path.replace('.mp4', '_tmp.mp4')
    with imageio.get_writer(temp_video_path, format='mp4', mode='I',
                            fps=fps , codec='h264', ffmpeg_params=['-bf', '0']) as writer:
        for frames in frames_list:
            frames = frames.numpy().astype(np.uint8)
            for i in range(frames.shape[0]):
                frame = frames[i, :, :, :]
                writer.append_data(frame)
    
    # merge video and audio
    cmd = ['ffmpeg', '-i', temp_video_path, '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac', '-shortest', video_path, '-y']
    subprocess.run(cmd)
    os.remove(temp_video_path)"""

new_fn = """def save_video(frames_list, video_path, audio_path, fps):
    first_chunk = frames_list[0].numpy()
    h, w = first_chunk.shape[1], first_chunk.shape[2]
    logger.info(f"Exporting studio master video ({w}x{h} @ {fps}fps) via hardware NVENC CQ=16...")

    cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', f'{w}x{h}', '-pix_fmt', 'rgb24', '-r', str(fps),
        '-i', '-',
        '-i', audio_path,
        '-c:v', 'h264_nvenc', '-preset', 'p7', '-tune', 'hq',
        '-rc', 'vbr', '-cq', '16', '-b:v', '0',
        '-spatial-aq', '1', '-temporal-aq', '1', '-multipass', 'fullres',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest',
        video_path
    ]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for frames in frames_list:
            raw_bytes = frames.numpy().astype(np.uint8).tobytes()
            proc.stdin.write(raw_bytes)
        proc.stdin.close()
        proc.wait()
        if proc.returncode != 0:
            err = proc.stderr.read().decode('utf-8', errors='ignore')
            logger.error(f"FFmpeg NVENC error: {err}")
    except Exception as e:
        logger.error(f"Error in save_video direct NVENC: {e}")"""

text_norm = text.replace("\r\n", "\n")
old_norm = old_fn.replace("\r\n", "\n")
assert old_norm in text_norm, "old_fn not found in generate_video.py!"
text_norm = text_norm.replace(old_norm, new_fn)

with open(gen_path, "w", encoding="utf-8") as f:
    f.write(text_norm)
print("Successfully patched save_video in generate_video.py!")
