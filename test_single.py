import sys
import os
from moviepy import ImageClip, ColorClip, CompositeVideoClip

media_dir = r"C:\Users\user\.gemini\antigravity\scratch\FastClip\相片"
output_path = r"C:\Users\user\Videos\single_clip_test.mp4"

try:
    print("--- Single Clip Render Test ---")
    files = [f for f in os.listdir(media_dir) if f.lower().endswith(('.jpg', '.png'))]
    if not files:
        print("No images found!")
        sys.exit(1)
    
    first_image = os.path.join(media_dir, files[0])
    print(f"Testing with: {first_image}")
    
    clip = ImageClip(first_image).with_duration(3)
    # clip = clip.resized(height=1080) # Let's skip resizing too
    
    print("Starting write_videofile for single clip...")
    clip.write_videofile(output_path, fps=24, codec="libx264")
    
    if os.path.exists(output_path):
        size = os.path.getsize(output_path)
        print(f"FINISHED. File size: {size} bytes")
    else:
        print("FAILED. No file produced.")

except Exception as e:
    import traceback
    traceback.print_exc()
