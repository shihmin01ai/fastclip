import os
import sys
import yt_dlp
import imageio_ffmpeg
from moviepy import ImageClip, VideoFileClip, concatenate_videoclips, AudioFileClip, ColorClip, CompositeVideoClip
# In MoviePy 2.x, effects are accessed differently
import moviepy.video.fx as vfx
import moviepy.audio.fx as afx
from PIL import Image
import random

def download_audio(url_or_path, output_dir="temp"):
    """Download audio from YouTube or copy local file."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    
    if "youtube.com" in url_or_path or "youtu.be" in url_or_path:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(output_dir, 'bgm.%(ext)s'),
            'ffmpeg_location': ffmpeg_path,
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url_or_path])
        except Exception as e:
            if "not available" in str(e).lower():
                raise ValueError("無法取得 YouTube 影片：該影片已被刪除、設為私人，或有地區限制。請換一個網址試試！")
            else:
                raise ValueError(f"下載 YouTube 音訊失敗：{str(e)}")
        return os.path.join(output_dir, "bgm.mp3")
    else:
        return url_or_path

class GuiLogger:
    """Custom logger to send progress back to the GUI callback."""
    def __init__(self, callback):
        self.callback = callback
    
    def __call__(self, **kwargs):
        return self

    def log(self, type=None, message=None, values=None, **kwargs):
        # Fallback for some MoviePy operations
        if type == 'progress' and values and 'index' in values and 'total' in values:
            if values['total'] > 0:
                progress = (values['index'] / values['total']) * 100
                self.callback(progress)

    def iter_bar(self, **kwargs):
        # CRITICAL: Must return the iterable for MoviePy to loop over it
        return kwargs.get('iterable', [])
    
    def bars_callback(self, bar_prefix, bar, index, total):
        # Granular progress updates for frames/tasks
        if total > 0:
            progress = (index / total) * 100
            self.callback(progress)

def create_video(media_dir, audio_path, target_duration_sec, output_path="output.mp4", min_clip_dur=3, max_clip_dur=10, progress_callback=None):
    """Assemble images and videos into a single video with background music."""
    # List all media files
    valid_img_exts = ('.jpg', '.jpeg', '.png', '.bmp')
    valid_vid_exts = ('.mp4', '.mov', '.avi')
    
    files = sorted([f for f in os.listdir(media_dir) if f.lower().endswith(valid_img_exts + valid_vid_exts)])
    
    if not files:
        raise ValueError("No valid media files found in directory.")

    # Target resolution
    RES = (1920, 1080)
    
    clips = []
    video_clips_total_dur = 0
    vid_files = [f for f in files if f.lower().endswith(valid_vid_exts)]
    img_files = [f for f in files if f.lower().endswith(valid_img_exts)]
    
    # Pre-calculate video clips to know remaining time for images
    loaded_vid_clips = []
    for f in vid_files:
        path = os.path.join(media_dir, f)
        clip = VideoFileClip(path)
        
        # Apply Min/Max duration logic
        original_dur = clip.duration
        take_dur = min(max(original_dur, min_clip_dur), max_clip_dur)
        # However, we can't take more than the original duration
        take_dur = min(take_dur, original_dur)
        
        if take_dur < original_dur:
            clip = clip.subclipped(0, take_dur)
            
        # Resize logic in V2
        clip = clip.resized(height=1080)
        if clip.w > 1920:
            clip = clip.resized(width=1920)
        
        # Render into padded composite
        bg = ColorClip(size=RES, color=(0,0,0)).with_duration(clip.duration)
        clip = CompositeVideoClip([bg, clip.with_position("center")])
        
        loaded_vid_clips.append(clip)
    
    # Correct Duration Calculation
    # Total Final Duration = sum(d_i) - (num_clips - 1) * 0.5
    # target = sum(vid_durs) + num_imgs * img_dur - (num_vids + num_imgs - 1) * 0.5
    # num_imgs * img_dur = target - sum(vid_durs) + (num_vids + num_imgs - 1) * 0.5
    
    num_vids = len(loaded_vid_clips)
    num_imgs = len(img_files)
    num_total = num_vids + num_imgs
    
    sum_vid_durs = sum(c.duration for c in loaded_vid_clips)
    
    if num_imgs > 0:
        total_img_dur_required = target_duration_sec - sum_vid_durs + (num_total - 1) * 0.5
        img_duration = max(1.0, total_img_dur_required / num_imgs) # At least 1s per image
    else:
        img_duration = 0
    
    # Process images
    for f in img_files:
        path = os.path.join(media_dir, f)
        clip = ImageClip(path).with_duration(img_duration)
        clip = clip.resized(height=1080)
        if clip.w > 1920:
            clip = clip.resized(width=1920)
        
        # Apply Ken Burns effect (Random Zoom In or Zoom Out)
        final_img_dur = clip.duration
        if random.random() > 0.5:
            # Zoom In: 1.0 -> 1.1
            clip = clip.resized(lambda t: 1.0 + 0.1 * (t / final_img_dur))
        else:
            # Zoom Out: 1.1 -> 1.0
            clip = clip.resized(lambda t: 1.1 - 0.1 * (t / final_img_dur))
        
        bg = ColorClip(size=RES, color=(0,0,0)).with_duration(clip.duration)
        # Center on background
        clip = CompositeVideoClip([bg, clip.with_position("center")])
        
        clips.append(clip)
        
    # Combine (alternating or just sequential?)
    # For now, let's just put all images then all videos, or preserve directory order
    final_clips = []
    vid_idx = 0
    img_idx = 0
    for f in files:
        if f.lower().endswith(valid_img_exts):
            clip = clips[img_idx]
            img_idx += 1
        else:
            clip = loaded_vid_clips[vid_idx]
            vid_idx += 1
            
        # Add CrossFadeIn to all clips except the very first one
        if len(final_clips) > 0:
            # Transition duration should not be more than half the clip
            trans_dur = min(0.5, clip.duration / 2)
            if trans_dur > 0:
                clip = clip.with_effects([vfx.CrossFadeIn(trans_dur)])
        
        final_clips.append(clip)
 
    # Concatenate with padding to create crossfade effect
    final_video = concatenate_videoclips(final_clips, method="compose", padding=-0.5)
    
    # Safety: force duration to target if it strayed slightly due to float precision
    if abs(final_video.duration - target_duration_sec) < 1.0:
        final_video = final_video.with_duration(target_duration_sec)
    
    # Load audio
    audio = AudioFileClip(audio_path)
    if audio.duration < final_video.duration:
        # Loop audio if too short
        audio = audio.with_effects([afx.AudioLoop(duration=final_video.duration)])
    else:
        audio = audio.subclipped(0, final_video.duration)
        
    # Add a 2-second fade out to the audio
    audio = audio.with_effects([afx.AudioFadeOut(2)])
        
    final_video = final_video.with_audio(audio)
    
    # Use multi-threading to speed up rendering (threads=os.cpu_count() or a safe number like 4-8)
    # logger=None is crucial for windowed apps without a console, 
    # but we use GuiLogger if a callback is provided.
    logger = GuiLogger(progress_callback) if progress_callback else None
    final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", threads=os.cpu_count(), logger=logger)
    
    # Cleanup loaded clips
    for c in loaded_vid_clips:
        c.close()
    audio.close()
