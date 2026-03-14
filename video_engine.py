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

def create_video(media_dir, audio_path, target_duration_sec, output_path="output.mp4", min_clip_dur=3, max_clip_dur=10, progress_callback=None, do_ducking=False, target_res=(1920, 1080)):
    """Assemble images and videos into a single video with background music."""
    try:
        from moviepy import ImageClip, VideoFileClip, concatenate_videoclips, AudioFileClip, ColorClip, CompositeVideoClip, CompositeAudioClip
        import moviepy.video.fx as vfx
        import moviepy.audio.fx as afx
        import numpy as np
        from PIL import Image, ImageFilter
        
        log_message(f"Starting video creation: target={target_duration_sec}s, res={target_res}, output={output_path}, ducking={do_ducking}")

        # List all media files
        valid_img_exts = ('.jpg', '.jpeg', '.png', '.bmp')
        valid_vid_exts = ('.mp4', '.mov', '.avi')
        
        files = sorted([f for f in os.listdir(media_dir) if f.lower().endswith(valid_img_exts + valid_vid_exts)])
        
        if not files:
            raise ValueError("資料夾中沒有發現有效的照片或影片檔案。")

        # Target resolution
        RES = target_res
        FPS = 24
        
        def process_aspect_ratio(clip, target_res):
            """Apply blurred background if clip aspect ratio differs from target."""
            tw, th = target_res
            cw, ch = clip.size
            
            # If aspect ratio matches (within tolerance), just resize
            target_ratio = tw / th
            clip_ratio = cw / ch
            
            if abs(target_ratio - clip_ratio) < 0.05:
                return clip.resized(target_res)
            
            # Otherwise, create blurred background
            # 1. Background: resize to fill and blur
            bg = clip.resized(height=th) if clip_ratio > target_ratio else clip.resized(width=tw)
            # Center crop bg to target_res
            x1 = max(0, (bg.w - tw) // 2)
            y1 = max(0, (bg.h - th) // 2)
            bg = bg.cropped(x1=x1, y1=y1, x2=x1+tw, y2=y1+th)
            try:
                def blur_frame(image):
                    pil_img = Image.fromarray(image)
                    pil_img = pil_img.filter(ImageFilter.GaussianBlur(radius=20))
                    return np.array(pil_img)
                bg = bg.image_transform(blur_frame)
            except Exception as e:
                # Fallback or older moviepy
                pass
            
            # 2. Foreground: resize to fit
            fg = clip.resized(height=th) if clip_ratio < target_ratio else clip.resized(width=tw)
            
            # Ensure background has same duration as foreground
            bg = bg.with_duration(fg.duration)
            
            comp = CompositeVideoClip([bg, fg.with_position("center")], size=target_res)
            return comp.with_duration(fg.duration)

        loaded_vid_clips = []
        img_clips = []
        try:
            vid_files = [f for f in files if f.lower().endswith(valid_vid_exts)]
            img_files = [f for f in files if f.lower().endswith(valid_img_exts)]
            
            # Pre-calculate video clips 
            for f in vid_files:
                path = os.path.join(media_dir, f)
                clip = VideoFileClip(path)
                
                # If no ducking, we strip audio from source
                if not do_ducking:
                    clip = clip.without_audio()
                
                clip.fps = FPS
                
                original_dur = clip.duration
                take_dur = min(max(original_dur, min_clip_dur), max_clip_dur)
                take_dur = min(take_dur, original_dur)
                
                if take_dur < original_dur:
                    clip = clip.subclipped(0, take_dur)
                    
                processed_clip = process_aspect_ratio(clip, RES)
                processed_clip.fps = FPS
                loaded_vid_clips.append(processed_clip)
            
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
                
                final_img_dur = clip.duration
                # Ken Burns (Apply before aspect ratio processing to maintain motion)
                if random.random() > 0.5:
                    clip = clip.resized(lambda t: 1.0 + 0.1 * (t / final_img_dur))
                else:
                    clip = clip.resized(lambda t: 1.1 - 0.1 * (t / final_img_dur))
                
                processed_clip = process_aspect_ratio(clip, RES)
                processed_clip.fps = FPS
                img_clips.append(processed_clip)
                
            final_clips = []
            duck_intervals = []
            curr_time = 0.0
            
            vid_idx = 0
            img_idx = 0
            for f in files:
                is_vid = False
                if f.lower().endswith(valid_img_exts):
                    clip = img_clips[img_idx]
                    img_idx += 1
                else:
                    clip = loaded_vid_clips[vid_idx]
                    vid_idx += 1
                    is_vid = True
                
                # Apply transition (CrossFadeIn)
                # Note: We handle the overlapping manually via curr_time
                if len(final_clips) > 0:
                    trans_dur = min(0.5, clip.duration / 2)
                    if trans_dur > 0:
                        clip = clip.with_effects([vfx.CrossFadeIn(trans_dur)])
                        curr_time -= trans_dur
                
                # Important: ducking interval must match the clip's final position in the timeline
                if is_vid and do_ducking:
                    duck_intervals.append((curr_time, curr_time + clip.duration))
                    
                final_clips.append(clip.with_start(curr_time))
                curr_time += clip.duration
         
            # Using CompositeVideoClip instead of concatenate_videoclips 
            # because we already manually handled start times and transitions
            final_video = CompositeVideoClip(final_clips, size=RES)
            final_video.fps = FPS
            
            if abs(final_video.duration - target_duration_sec) < 5.0:
                final_video = final_video.with_duration(target_duration_sec)
            
            log_message(f"Loading audio: {audio_path}")
            bgm = AudioFileClip(audio_path)
            if bgm.duration < final_video.duration:
                bgm = bgm.with_effects([afx.AudioLoop(duration=final_video.duration)])
            else:
                bgm = bgm.subclipped(0, final_video.duration)
                
            if do_ducking and duck_intervals:
                log_message(f"Applying ducking to {len(duck_intervals)} intervals.")
                ducking_effects = []
                for start, end in duck_intervals:
                    ducking_effects.append(afx.MultiplyVolume(0.15, start_time=start, end_time=end))
                
                bgm = bgm.with_effects(ducking_effects)
                
                if final_video.audio:
                    log_message("Merging BGM with source audio...")
                    final_audio = CompositeAudioClip([bgm, final_video.audio])
                else:
                    final_audio = bgm
            else:
                final_audio = bgm
                
            final_audio = final_audio.with_effects([afx.AudioFadeOut(2)])
            final_video = final_video.with_audio(final_audio)
            
            # Accurate frame count for progress bar
            total_frames = int(final_video.duration * FPS)
            logger = GuiLogger(progress_callback, expected_frames=total_frames) if progress_callback else None
            log_message(f"Starting write_videofile... duration={final_video.duration}")
            
            final_video.write_videofile(
                output_path, 
                fps=FPS, 
                codec="libx264", 
                audio_codec="aac",
                audio_bitrate="192k",
                audio_fps=44100,
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
