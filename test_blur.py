import os
from moviepy import ColorClip
import numpy as np
from PIL import Image, ImageFilter

def test_blur():
    try:
        print("Creating ColorClip (1080x1920)")
        clip = ColorClip(size=(1080, 1920), color=(255, 0, 0), duration=1)
        bg = clip.resized(width=1920)
        print("Before blur size:", bg.size)
        
        def blur_frame(image):
            pil_img = Image.fromarray(image)
            pil_img = pil_img.filter(ImageFilter.GaussianBlur(radius=20))
            return np.array(pil_img)
            
        bg = bg.image_transform(blur_frame)
        print("Blur applied successfully. Output frame shape:", bg.get_frame(0).shape)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("Blur failed:", str(e))

if __name__ == "__main__":
    test_blur()
