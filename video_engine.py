import os
import sys
import random
import traceback
import time

def log_message(msg):
    """Write debug messages to a local log file."""
    try:
        with open("fastclip_debug.log", "a", encoding="utf-8") as f:
            t = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{t}] {msg}\n")
    except Exception:
        pass

def download_audio(url_or_path, output_dir="temp"):
    """Download audio from YouTube or copy local file."""
    import yt_dlp
    import imageio_ffmpeg
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    
    if "youtube.com" in url_or_path or "youtu.be" in url_or_path:
        # Use a unique ID to avoid file locks
        uid = int(time.time())
        output_file = f"bgm_{uid}.mp3"
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(output_dir, f'bgm_{uid}.%(ext)s'),
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
            log_message(f"Downloading YouTube audio: {url_or_path}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url_or_path])
            return os.path.join(output_dir, output_file)
        except Exception as e:
            log_message(f"YouTube download failed: {str(e)}")
            if "not available" in str(e).lower():
                raise ValueError("無法取得 YouTube 影片：該影片已被刪除、設為私人，或有地區限制。請換一個網址試試！")
            else:
                raise ValueError(f"下載 YouTube 音訊失敗：{str(e)}")
    else:
        return url_or_path

import proglog

class GuiLogger(proglog.ProgressBarLogger):
    """Custom logger to send progress back to the GUI callback."""
    def __init__(self, callback, expected_frames=None):
        super().__init__()
        self.gui_callback = callback
        self.expected_frames = expected_frames
    
    def bars_callback(self, bar_prefix, bar, index, total):
        # MoviePy 2.x uses this for frames/tasks
        # We override the 'total' for frame_index to keep it stable
        display_total = total
        if bar_prefix == "frame_index" and self.expected_frames:
            display_total = self.expected_frames
            
        if display_total and display_total > 0:
            # Cap index at total to avoid overshooting
            display_index = min(index, display_total)
            # Pass detailed info back as a dict
            self.gui_callback({
                'prefix': bar_prefix,
                'index': display_index,
                'total': display_total,
                'percentage': (display_index / display_total) * 100
            })

def create_video(media_dir, audio_path, target_duration_sec, output_path="output.mp4", min_clip_dur=3, max_clip_dur=10, progress_callback=None):
    """Assemble images and videos into a single video with background music."""
    try:
        from moviepy import ImageClip, VideoFileClip, concatenate_videoclips, AudioFileClip, ColorClip, CompositeVideoClip
        import moviepy.video.fx as vfx
        import moviepy.audio.fx as afx
        
        log_message(f"Starting video creation: target={target_duration_sec}s, output={output_path}")

        # List all media files
        valid_img_exts = ('.jpg', '.jpeg', '.png', '.bmp')
        valid_vid_exts = ('.mp4', '.mov', '.avi')
        
        files = sorted([f for f in os.listdir(media_dir) if f.lower().endswith(valid_img_exts + valid_vid_exts)])
        
        if not files:
            raise ValueError("資料夾中沒有發現有效的照片或影片檔案。")

        # Target resolution
        RES = (1920, 1080)
        FPS = 24
        
        loaded_vid_clips = []
        img_clips = []
        try:
            vid_files = [f for f in files if f.lower().endswith(valid_vid_exts)]
            img_files = [f for f in files if f.lower().endswith(valid_img_exts)]
            
            # Pre-calculate video clips 
            for f in vid_files:
                path = os.path.join(media_dir, f)
                clip = VideoFileClip(path)
                clip.fps = FPS
                
                original_dur = clip.duration
                take_dur = min(max(original_dur, min_clip_dur), max_clip_dur)
                take_dur = min(take_dur, original_dur)
                
                if take_dur < original_dur:
                    clip = clip.subclipped(0, take_dur)
                    
                clip = clip.resized(height=1080)
                if clip.w > 1920:
                    clip = clip.resized(width=1920)
                
                bg = ColorClip(size=RES, color=(0,0,0)).with_duration(clip.duration)
                bg.fps = FPS
                comp = CompositeVideoClip([bg, clip.with_position("center")])
                comp.fps = FPS
                loaded_vid_clips.append(comp)
            
            num_vids = len(loaded_vid_clips)
            num_imgs = len(img_files)
            num_total = num_vids + num_imgs
            
            sum_vid_durs = sum(c.duration for c in loaded_vid_clips)
            
            if num_imgs > 0:
                total_img_dur_required = target_duration_sec - sum_vid_durs + (num_total - 1) * 0.5
                img_duration = max(1.0, total_img_dur_required / num_imgs)
            else:
                img_duration = 0
            
            for f in img_files:
                path = os.path.join(media_dir, f)
                clip = ImageClip(path).with_duration(img_duration)
                clip.fps = FPS
                clip = clip.resized(height=1080)
                if clip.w > 1920:
                    clip = clip.resized(width=1920)
                
                final_img_dur = clip.duration
                # Re-enabling Ken Burns
                if random.random() > 0.5:
                    clip = clip.resized(lambda t: 1.0 + 0.1 * (t / final_img_dur))
                else:
                    clip = clip.resized(lambda t: 1.1 - 0.1 * (t / final_img_dur))
                
                bg = ColorClip(size=RES, color=(0,0,0)).with_duration(clip.duration)
                bg.fps = FPS
                comp = CompositeVideoClip([bg, clip.with_position("center")])
                comp.fps = FPS
                img_clips.append(comp)
                
            final_clips = []
            vid_idx = 0
            img_idx = 0
            for f in files:
                if f.lower().endswith(valid_img_exts):
                    clip = img_clips[img_idx]
                    img_idx += 1
                else:
                    clip = loaded_vid_clips[vid_idx]
                    vid_idx += 1
                    
                if len(final_clips) > 0:
                    trans_dur = min(0.5, clip.duration / 2)
                    if trans_dur > 0:
                        clip = clip.with_effects([vfx.CrossFadeIn(trans_dur)])
                
                final_clips.append(clip)
         
            # Restoring transitions and compose method
            final_video = concatenate_videoclips(final_clips, method="compose", padding=-0.5)
            final_video.fps = FPS
            
            if abs(final_video.duration - target_duration_sec) < 5.0:
                final_video = final_video.with_duration(target_duration_sec)
            
            log_message(f"Loading audio: {audio_path}")
            audio = AudioFileClip(audio_path)
            if audio.duration < final_video.duration:
                audio = audio.with_effects([afx.AudioLoop(duration=final_video.duration)])
            else:
                audio = audio.subclipped(0, final_video.duration)
                
            audio = audio.with_effects([afx.AudioFadeOut(2)])
            final_video = final_video.with_audio(audio)
            
            # Accurate frame count for progress bar
            total_frames = int(final_video.duration * FPS)
            logger = GuiLogger(progress_callback, expected_frames=total_frames) if progress_callback else None
            log_message("Starting write_videofile...")
            
            # Using multi-threading again
            final_video.write_videofile(
                output_path, 
                fps=24, 
                codec="libx264", 
                audio_codec="aac", 
                threads=os.cpu_count() or 4,
                logger=logger
            )
            log_message("write_videofile finished successfully.")
            
        finally:
            log_message("Cleaning up clips...")
            if 'final_video' in locals():
                final_video.close()
            if 'audio' in locals():
                audio.close()
            for c in loaded_vid_clips:
                try: c.close()
                except: pass
            for c in img_clips:
                try: c.close()
                except: pass
            log_message("Cleanup finished.")

    except Exception as e:
        err_msg = traceback.format_exc()
        log_message(f"CRITICAL ERROR in create_video: {err_msg}")
        raise e
