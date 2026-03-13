import video_engine
import os
import time

# Mocking data for test
media_dir = "相片"
audio_path = "temp/bgm_test.mp3" # Assume some audio exists or use a local one
if not os.path.exists("temp"):
    os.makedirs("temp")

# Test landscape output with vertical images
print("Testing Landscape (16:9) with vertical media...")
try:
    video_engine.create_video(
        media_dir=media_dir,
        audio_path="相片/LINE_ALBUM_20230608 畢業典禮_230620_14.MOV", # Use a local file as audio if needed or a dummy
        target_duration_sec=10,
        output_path="test_landscape.mp4",
        target_res=(1920, 1080)
    )
    print("Landscape test completed.")
except Exception as e:
    print(f"Landscape test failed: {e}")

# Test portrait output
print("\nTesting Portrait (9:16)...")
try:
    video_engine.create_video(
        media_dir=media_dir,
        audio_path="相片/LINE_ALBUM_20230608 畢業典禮_230620_14.MOV",
        target_duration_sec=10,
        output_path="test_portrait.mp4",
        target_res=(1080, 1920)
    )
    print("Portrait test completed.")
except Exception as e:
    print(f"Portrait test failed: {e}")
