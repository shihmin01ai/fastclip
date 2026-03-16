import os
import sys
import random
import traceback
import time
import subprocess
import re

def log_message(msg):
    """Write debug messages to a local log file."""
    try:
        with open("fastclip_debug.log", "a", encoding="utf-8") as f:
            t = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{t}] {msg}\n")
    except Exception:
        pass

def get_ffmpeg_path():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def download_audio(url_or_path, output_dir="temp"):
    """Download audio from YouTube or copy local file."""
    import yt_dlp
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    ffmpeg_path = get_ffmpeg_path()
    
    if "youtube.com" in url_or_path or "youtu.be" in url_or_path:
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

def get_media_info(path, is_video):
    if is_video:
        try:
            from moviepy import VideoFileClip
            with VideoFileClip(path) as clip:
                dur = clip.duration
                w, h = clip.size
                has_audio = clip.audio is not None
                return {"duration": dur, "w": w, "h": h, "has_audio": has_audio}
        except Exception as e:
            log_message(f"Error reading video metadata {path}: {e}")
            return None
    else:
        try:
            from PIL import Image
            with Image.open(path) as img:
                w, h = img.size
                return {"duration": 0, "w": w, "h": h, "has_audio": False}
        except Exception as e:
            log_message(f"Error reading image metadata {path}: {e}")
            return None

def create_video(media_dir, audio_path, target_duration_sec, output_path="output.mp4", min_clip_dur=3, max_clip_dur=10, progress_callback=None, do_ducking=False, target_res=(1920, 1080), duck_volume=0.15):
    """Assemble images and videos using highly optimized pure FFmpeg commands."""
    try:
        log_message(f"Starting native FFmpeg video creation: target={target_duration_sec}s, res={target_res}, ducking={do_ducking}")
        
        valid_img_exts = ('.jpg', '.jpeg', '.png', '.bmp')
        valid_vid_exts = ('.mp4', '.mov', '.avi')
        
        files = sorted([f for f in os.listdir(media_dir) if f.lower().endswith(valid_img_exts + valid_vid_exts)])
        if not files:
            raise ValueError("資料夾中沒有發現有效的照片或影片檔案。")

        vid_files = [f for f in files if f.lower().endswith(valid_vid_exts)]
        img_files = [f for f in files if f.lower().endswith(valid_img_exts)]

        # Phase 1: Metadata Extraction
        media_list = []
        sum_vid_durs = 0.0
        
        for f in vid_files:
            path = os.path.join(media_dir, f)
            info = get_media_info(path, True)
            if info:
                dur = info['duration']
                take_dur = min(max(dur, min_clip_dur), max_clip_dur)
                take_dur = min(take_dur, dur)
                media_list.append({
                    "path": path, "is_video": True, "target_dur": take_dur, 
                    "has_audio": info['has_audio']
                })
                sum_vid_durs += take_dur

        num_imgs = len(img_files)
        img_duration = 0.0
        if num_imgs > 0:
            total_img_dur_required = target_duration_sec - sum_vid_durs + (len(vid_files) + num_imgs - 1) * 0.5
            img_duration = max(1.0, total_img_dur_required / num_imgs)
            
            for f in img_files:
                path = os.path.join(media_dir, f)
                info = get_media_info(path, False)
                if info:
                    media_list.append({
                        "path": path, "is_video": False, "target_dur": img_duration, 
                        "has_audio": False
                    })
                    
        # Sort media list to Original order based on filename
        media_list.sort(key=lambda x: os.path.basename(x["path"]))
        
        # Build FFmpeg command
        ffmpeg_exe = get_ffmpeg_path()
        cmd = [ffmpeg_exe, "-y"]
        
        # Variables
        tw, th = target_res
        fps = 24
        
        # Inputs
        for i, media in enumerate(media_list):
            if not media['is_video']:
                cmd.extend(["-t", str(media['target_dur']), "-loop", "1", "-framerate", str(fps), "-i", media['path']])
            else:
                cmd.extend(["-i", media['path']])

        # BGM Input (Loop infinite at stream level)
        bgm_idx = len(media_list)
        cmd.extend(["-stream_loop", "-1", "-i", audio_path])
        
        # Variables
        tw, th = target_res
        fps = 24
        
        filter_lines = []
        video_out_nodes = []
        audio_out_nodes = []
        duck_intervals = []
        curr_t = 0.0
        
        # Phase 2 & 3: Filter Graph Generation
        for i, media in enumerate(media_list):
            dur = media['target_dur']
            is_vid = media['is_video']
            
            filter_lines.append(f"[{i}:v]format=yuv420p,setsar=1[v{i}_norm];")
            
            if is_vid:
                # Video processing: Scale and pad to fit target resolution, then blur background
                filter_lines.append(f"[v{i}_norm]split=2[v{i}_bg][v{i}_fg];")
                filter_lines.append(f"[v{i}_bg]scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th},boxblur=20:5[bg{i}];")
                filter_lines.append(f"[v{i}_fg]scale={tw}:{th}:force_original_aspect_ratio=decrease[fg{i}];")
                filter_lines.append(f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,trim=0:{dur},setpts=PTS-STARTPTS,fps={fps}[base{i}];")
            else:
                frames = int(dur * fps)
                zoom_expr = "min(zoom+0.001,1.1)" if i % 2 == 0 else "max(1.1-0.001*on,1.0)"
                
                # Image Processing: 
                # 1. Create a static properly sized/padded frame first
                filter_lines.append(f"[v{i}_norm]split=2[v{i}_bg][v{i}_fg];")
                filter_lines.append(f"[v{i}_bg]scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th},boxblur=20:5[bg{i}];")
                filter_lines.append(f"[v{i}_fg]scale={tw}:{th}:force_original_aspect_ratio=decrease[fg{i}];")
                filter_lines.append(f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,scale=iw*3:ih*3[base_img{i}];")
                
                # 2. Apply zoompan to the padded image. Since input aspect ratio == output aspect ratio, stretching is disabled.
                filter_lines.append(f"[base_img{i}]zoompan=z='{zoom_expr}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={tw}x{th},setpts=PTS-STARTPTS,fps={fps}[base{i}];")
                
            video_out_nodes.append(f"[base{i}]")
            
            # Audio Handling
            if is_vid and media['has_audio']:
                if do_ducking:
                    duck_intervals.append((curr_t, curr_t + dur))
                filter_lines.append(f"[{i}:a]atrim=0:{dur},asetpts=PTS-STARTPTS[a{i}_t];")
                delay_ms = int(curr_t * 1000)
                if delay_ms > 0:
                    filter_lines.append(f"[a{i}_t]adelay={delay_ms}|{delay_ms}[a{i}_dl];")
                    audio_out_nodes.append(f"[a{i}_dl]")
                else:
                    audio_out_nodes.append(f"[a{i}_t]")
                    
            curr_t += dur - 0.5  # 0.5s fade
            
        bgm_dur = curr_t + 0.5 # Total exact output duration
        
        # Frame exact calculation
        if len(video_out_nodes) == 1:
            filter_lines.append(f"{video_out_nodes[0]}copy[vout];")
        else:
            last_out = video_out_nodes[0]
            # Time at which the NEXT clip should START fading in
            current_video_length = media_list[0]['target_dur'] 
            
            for i in range(1, len(video_out_nodes)):
                xfade_offset = current_video_length - 0.5
                filter_lines.append(f"{last_out}{video_out_nodes[i]}xfade=transition=fade:duration=0.5:offset={xfade_offset:.3f},fps={fps}[xf{i}];")
                last_out = f"[xf{i}]"
                
                # The new total length is the old length + new video length - 0.5 overlap
                current_video_length = current_video_length + media_list[i]['target_dur'] - 0.5
                
            filter_lines.append(f"{last_out}copy[vout];")

        # BGM Processing
        filter_lines.append(f"[{bgm_idx}:a]atrim=0:{bgm_dur},asetpts=PTS-STARTPTS[bgm_base];")
        
        if do_ducking and duck_intervals:
            duck_expr = "+".join([f"between(t,{s},{e})" for s, e in duck_intervals])
            filter_lines.append(f"[bgm_base]volume={duck_volume}:enable='{duck_expr}'[bgm_duck];")
            bgm_out = "[bgm_duck]"
        else:
            bgm_out = "[bgm_base]"
            
        if audio_out_nodes:
            amix_inputs = "".join(audio_out_nodes) + bgm_out
            num_inputs = len(audio_out_nodes) + 1
            filter_lines.append(f"{amix_inputs}amix=inputs={num_inputs}:duration=longest:dropout_transition=2[aout_mix];")
        else:
            filter_lines.append(f"{bgm_out}anull[aout_mix];")
            
        fade_start = max(0, bgm_dur - 2.0)
        filter_lines.append(f"[aout_mix]afade=t=out:st={fade_start}:d=2[aout];")
        
        filter_txt = "temp_filter.txt"
        with open(filter_txt, "w", encoding="utf-8") as f:
            f.write("\n".join(filter_lines))
            
        total_frames = int(bgm_dur * fps)
        
        cmd.extend([
            "-filter_complex_script", filter_txt,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "faster",  # Significantly faster encoding
            "-threads", "8",      # Multi-treading
            "-c:a", "aac",
            "-b:a", "192k",
            "-r", str(fps),
            "-t", str(bgm_dur),   # Force exact stop time
            output_path
        ])

        log_message(f"FFmpeg command: {' '.join(cmd)}")
        
        # Phase 4: Execution
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding='utf-8'
        )
        
        for line in process.stderr:
            if "frame=" in line and "fps=" in line:
                m = re.search(r'frame=\s*(\d+)', line)
                if m and progress_callback:
                    current_frame = int(m.group(1))
                    progress_callback({
                        "prefix": "frame_index",
                        "index": current_frame,
                        "total": total_frames,
                        "percentage": (current_frame / max(1, total_frames)) * 100
                    })
            log_message(line.strip())
            
        process.wait()
        
        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg failed with exit code {process.returncode}. See fastclip_debug.log")

        log_message("create_video finished successfully.")
    except Exception as e:
        err_msg = traceback.format_exc()
        log_message(f"CRITICAL ERROR in create_video: {err_msg}")
        raise e
