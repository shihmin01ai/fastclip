import sys
import os
sys.path.append(os.getcwd())
import video_engine
from moviepy import AudioFileClip, VideoFileClip

media_dir = r"C:\Users\user\.gemini\antigravity\scratch\FastClip\相片"
audio_path = r"C:\Users\user\Videos\FastClip_202603131635_背景音樂.mp3"
output_path = r"C:\Users\user\Videos\debug_test_v2.mp4"
total_duration = 39

try:
    print(f"--- Diagnostic Check ---")
    if not os.path.exists(audio_path):
        print(f"ERROR: Audio file not found at {audio_path}")
    else:
        try:
            audio = AudioFileClip(audio_path)
            print(f"Audio loaded: {audio.duration:.2f}s")
            audio.close()
        except Exception as ae:
            print(f"ERROR: Failed to load audio: {ae}")

    # Inspect media files
    valid_img_exts = ('.jpg', '.jpeg', '.png', '.bmp')
    valid_vid_exts = ('.mp4', '.mov', '.avi')
    files = sorted([f for f in os.listdir(media_dir) if f.lower().endswith(valid_img_exts + valid_vid_exts)])
    print(f"Found {len(files)} media files.")

    print(f"\n--- Running create_video with verbose logging ---")
    
    def prog_cb(p):
        print(f"Progress: {p:.2f}%")

    # We will modify video_engine.create_video locally in memory if needed, 
    # but for now let's just run it and see if we can get MORE logs by modifying the engine file itself.
    
    video_engine.create_video(
        media_dir, 
        audio_path, 
        total_duration, 
        output_path, 
        min_clip_dur=3, 
        max_clip_dur=6, 
        progress_callback=prog_cb
    )
    
    if os.path.exists(output_path):
        size = os.path.getsize(output_path)
        print(f"FINISHED. Final file size: {size} bytes")
    else:
        print("FINISHED. But NO output file found!")

except Exception as e:
    import traceback
    traceback.print_exc()
